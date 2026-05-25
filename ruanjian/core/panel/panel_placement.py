from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from .panel_bounds import panel_world_aabb_at
from .panel_models import Panel
from ..space.space_models import Space
from ..space.tree import walk_dfs
from ..constants.enums import PanelRole, PanelOrientation
from ..constants.tolerance import DIMENSION_TOLERANCE
from ..dirty.dirty_flags import DirtyFlag
from ..panel.rules.panel_defaults import get_panel_defaults
from ..panel.rules.panel_wrap_rules import get_wrap_rule


def left_side_stack_offset_x(space: Space) -> float:
    """该 Space 上已有 ``LEFT_SIDE`` 板沿 +X 堆叠的累计厚度（mm）；新板定位前调用。"""
    off = 0.0
    for g in getattr(space, "panel_groups", []) or []:
        for p in getattr(g, "panels", []) or []:
            r = getattr(p, "role", None)
            if r == PanelRole.LEFT_SIDE or getattr(r, "value", None) == PanelRole.LEFT_SIDE.value:
                off += float(getattr(p, "thickness", 18.0))
    return off


def place_left_side_panel(panel: Panel, space: Space) -> None:
    """左侧板：与 Space 左前下角对齐；+X 按已有 ``LEFT_SIDE`` 厚度累加，避免多块重叠在同一 x。"""
    stack = left_side_stack_offset_x(space)
    panel.set_position(
        x=float(space.x) + float(stack),
        y=float(space.y),
        z=float(space.z),
    )


# ================================================================
# 定位结果
# ================================================================

@dataclass
class PlacementResult:
    """单块板件的定位结果快照。"""
    panel_id:   str
    panel_name: str
    x: float = 0.0
    y: float = 0.0
    z: float = 0.0
    orientation: Optional[PanelOrientation] = None
    errors:   list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return len(self.errors) == 0

    def __repr__(self) -> str:
        return (
            f"Placement({self.panel_name}  "
            f"@({self.x:.1f}, {self.y:.1f}, {self.z:.1f})  "
            f"{self.orientation.value if self.orientation else '?'})"
        )


@dataclass
class PlacementBatch:
    """一次批量定位的汇总结果。"""
    results: list[PlacementResult] = field(default_factory=list)
    errors:  list[str]             = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return len(self.errors) == 0

    def print_summary(self) -> None:
        bad = [r for r in self.results if not r.ok]
        print(
            f"[Placement] 共定位 {len(self.results)} 块  "
            f"失败={len(bad)}  全局错误={len(self.errors)}"
        )
        for r in bad:
            for e in r.errors:
                print(f"  ✗ {r.panel_name}: {e}")


# ================================================================
# 单板件定位
# ================================================================

def place(
    panel: Panel,
    space: Space,
    *,
    apply_to_panel: bool = True,
) -> PlacementResult:
    """
    计算单块板件在 Space 坐标系内的原点坐标和朝向。

    坐标系约定：
      原点在柜体左下角前方（space.x, space.y, space.z）
      x → 右（宽度方向）
      y → 上（高度方向）
      z → 前（深度方向，z 增大 = 靠近用户）

    每种板件角色有固定的定位逻辑：
      LEFT   → x = space.x，紧贴左边界
      LEFT_SIDE → 通用 ``place()`` 内为 ``space.x +`` 堆叠厚度；由 ``add_left_side_panel`` 添加的板
      则改由 ``place_left_side_panel`` 贴 ``(space.x, space.y, space.z)``
      RIGHT  → x = space.x + space.width - thickness，紧贴右边界
      TOP    → y = space.y + space.height - thickness，紧贴顶边界
      BOTTOM → y = space.y，紧贴底边界
      BACK   → z = space.z，紧贴后边界
      SHELF  → y 由外部传入（层板 y 坐标由 Space 切割决定）
      DIVIDER→ x 由外部传入（中隔板 x 坐标由 Space 切割决定）
      DOOR_* → x/y 按开口位置 + 缝隙偏移
      DRAWER_FRONT → x/y 按开口位置 + 缝隙偏移

    Args:
        panel:          待定位的板件
        space:          板件所属 Space
        apply_to_panel: True → 直接写入 panel.x/y/z 和 orientation

    Returns:
        PlacementResult 快照
    """
    r = PlacementResult(
        panel_id=panel.id,
        panel_name=panel.name or panel.role.value,
    )

    defaults  = get_panel_defaults(space.space_type)
    wrap_rule = get_wrap_rule(space.space_type)

    try:
        x, y, z, orient = _calc_position(panel, space, defaults, wrap_rule)
    except Exception as e:
        r.errors.append(f"定位计算异常：{e}")
        return r

    # 越界检查（警告级，不阻断）
    _check_bounds(r, panel, space, x, y, z)

    r.x = x
    r.y = y
    r.z = z
    r.orientation = orient

    if apply_to_panel and r.ok:
        panel.set_position(x, y, z)
        panel.orientation = orient
        panel.dirty_flag = DirtyFlag.CLEAN

    return r


# ================================================================
# 定位核心：按角色分发
# ================================================================

def _calc_position(
    panel: Panel,
    space: Space,
    defaults,
    wrap_rule,
) -> tuple[float, float, float, PanelOrientation]:
    """
    按 panel.role 分发到对应的定位函数。
    返回 (x, y, z, orientation)。
    """
    role = panel.role
    dispatch = {
        PanelRole.LEFT:         _place_left,
        PanelRole.LEFT_SIDE:    _place_left_side,
        PanelRole.RIGHT:        _place_right,
        PanelRole.TOP:          _place_top,
        PanelRole.BOTTOM:       _place_bottom,
        PanelRole.BACK:         _place_back,
        PanelRole.SHELF:        _place_shelf,
        PanelRole.DIVIDER:      _place_divider,
        PanelRole.DOOR_LEFT:    _place_door,
        PanelRole.DOOR_RIGHT:   _place_door,
        PanelRole.DOOR_DOUBLE:  _place_door,
        PanelRole.DRAWER_FRONT: _place_drawer_front,
    }
    fn = dispatch.get(role, _place_fallback)
    return fn(panel, space, defaults, wrap_rule)


# ── 旁板 ───────────────────────────────────────────────────────

def _place_left(panel, space, defaults, wrap):
    """
    左旁板：紧贴 Space 左边界。
    y 起点取决于包裹规则（旁板包顶底 → y = space.y；否则 y 上移底板厚）
    z 起点考虑背板是否嵌槽（通常 z = space.z）
    """
    x = space.x
    y = space.y + (0 if wrap.side_wraps_bottom else defaults.bottom_thickness)
    z = space.z
    return x, y, z, PanelOrientation.VERTICAL_X


def _place_left_side(panel, space, defaults, wrap):
    """左侧板：与左旁板同向，x 含多块 ``LEFT_SIDE`` 沿 +X 堆叠。"""
    x = space.x + left_side_stack_offset_x(space)
    y = space.y + (0 if wrap.side_wraps_bottom else defaults.bottom_thickness)
    z = space.z
    return x, y, z, PanelOrientation.VERTICAL_X


def _place_right(panel, space, defaults, wrap):
    """右旁板：紧贴 Space 右边界（内侧）。"""
    x = space.x + space.width - defaults.side_thickness
    y = space.y + (0 if wrap.side_wraps_bottom else defaults.bottom_thickness)
    z = space.z
    return x, y, z, PanelOrientation.VERTICAL_X


# ── 顶/底板 ────────────────────────────────────────────────────

def _place_top(panel, space, defaults, wrap):
    """
    顶板：紧贴 Space 顶边界（内侧）。
    x 起点：旁板包顶 → x 向内缩旁板厚；顶板包旁 → x = space.x
    """
    x = space.x + (defaults.side_thickness if wrap.side_wraps_top else 0)
    y = space.y + space.height - defaults.top_thickness
    z = space.z
    return x, y, z, PanelOrientation.HORIZONTAL


def _place_bottom(panel, space, defaults, wrap):
    """底板：紧贴 Space 底边界。"""
    x = space.x + (defaults.side_thickness if wrap.side_wraps_bottom else 0)
    y = space.y
    z = space.z
    return x, y, z, PanelOrientation.HORIZONTAL


# ── 背板 ───────────────────────────────────────────────────────

def _place_back(panel, space, defaults, wrap):
    """
    背板：紧贴 Space 后边界。
    背板通常嵌入旁板槽内，x 向内缩旁板厚（如果 side_wraps_back）。
    z = space.z（后边界）。
    """
    x = space.x + (defaults.side_thickness if wrap.side_wraps_back else 0)
    y = space.y + (defaults.bottom_thickness if wrap.bottom_wraps_back else 0)
    z = space.z
    return x, y, z, PanelOrientation.VERTICAL_Z


# ── 层板 ───────────────────────────────────────────────────────

def _place_shelf(panel, space, defaults, wrap):
    """
    层板：x/z 与底板相同，y 由 panel.y 现有值决定（已由 generator 写入）。
    此函数只重算 x/z，不覆盖 y。
    """
    x = space.x + defaults.side_thickness
    y = panel.y    # 保持 generator 写入的 y 坐标
    z = space.z
    return x, y, z, PanelOrientation.HORIZONTAL


# ── 中隔板 ─────────────────────────────────────────────────────

def _place_divider(panel, space, defaults, wrap):
    """
    中隔板：y/z 与旁板相同，x 由 panel.x 现有值决定（已由 generator 写入）。
    此函数只重算 y/z，不覆盖 x。
    """
    x = panel.x    # 保持 generator 写入的 x 坐标
    y = space.y + (0 if wrap.side_wraps_bottom else defaults.bottom_thickness)
    z = space.z
    return x, y, z, PanelOrientation.VERTICAL_X


# ── 门板 ───────────────────────────────────────────────────────

def _place_door(panel, space, defaults, wrap):
    """
    门板：覆盖在 Space 正面（z = space.z + space.depth - panel.thickness）。

    x 起点：从 opening/ 模块写入的 metadata 读取开口 x，加上左缝隙偏移。
    y 起点：从 metadata 读取开口 y，加上下缝隙偏移。

    开口信息由 opening/calculator.py 提前写入 space.metadata：
      metadata["opening_x"]       开口左边界 x
      metadata["opening_y"]       开口下边界 y
      metadata["gap_left"]        左缝隙
      metadata["gap_bottom"]      下缝隙
    """
    gap_left   = float(space.metadata.get("gap_left",   defaults.door_gap_side))
    gap_bottom = float(space.metadata.get("gap_bottom", defaults.door_gap_bottom))
    opening_x  = float(space.metadata.get("opening_x",  space.x))
    opening_y  = float(space.metadata.get("opening_y",  space.y))

    x = opening_x  + gap_left
    y = opening_y  + gap_bottom
    z = space.z + space.depth - panel.thickness   # 门板贴正面
    return x, y, z, PanelOrientation.VERTICAL_Z


# ── 抽屉前板 ───────────────────────────────────────────────────

def _place_drawer_front(panel, space, defaults, wrap):
    """
    抽屉前板：与门板类似，覆盖在 Space 正面。
    y 坐标通常与抽屉体 y 一致，由 metadata["drawer_y"] 提供。
    """
    gap_left   = float(space.metadata.get("gap_left",    defaults.door_gap_side))
    gap_bottom = float(space.metadata.get("drawer_gap_bottom", defaults.drawer_gap))
    opening_x  = float(space.metadata.get("opening_x",  space.x))
    drawer_y   = float(space.metadata.get("drawer_y",   space.y))

    x = opening_x + gap_left
    y = drawer_y  + gap_bottom
    z = space.z + space.depth - panel.thickness
    return x, y, z, PanelOrientation.VERTICAL_Z


# ── 兜底 ───────────────────────────────────────────────────────

def _place_fallback(panel, space, defaults, wrap):
    """未识别角色，返回 Space 原点，朝向保持不变。"""
    return space.x, space.y, space.z, panel.orientation


# ================================================================
# 越界检查
# ================================================================

def _check_bounds(
    r: PlacementResult,
    panel: Panel,
    space: Space,
    x: float, y: float, z: float,
) -> None:
    """
    检查板件包围盒是否完全落在 Space 范围内。
    超出时记录 warning（不升为 error，允许门板/覆盖板略微超出）。
    """
    tol = DIMENSION_TOLERANCE

    x0, x1, y0, y1, z0, z1 = panel_world_aabb_at(panel, x, y, z)
    px0, px1 = x0, x1
    py0, py1 = y0, y1
    pz0, pz1 = z0, z1

    sx0 = space.x;              sx1 = space.x + space.width
    sy0 = space.y;              sy1 = space.y + space.height
    sz0 = space.z;              sz1 = space.z + space.depth

    def _warn(msg: str) -> None:
        r.warnings.append(msg)

    if px0 < sx0 - tol: _warn(f"x 起点 {px0:.1f} < Space 左边界 {sx0:.1f}")
    if px1 > sx1 + tol: _warn(f"x 终点 {px1:.1f} > Space 右边界 {sx1:.1f}")
    if py0 < sy0 - tol: _warn(f"y 起点 {py0:.1f} < Space 下边界 {sy0:.1f}")
    if py1 > sy1 + tol: _warn(f"y 终点 {py1:.1f} > Space 上边界 {sy1:.1f}")
    if pz0 < sz0 - tol: _warn(f"z 起点 {pz0:.1f} < Space 后边界 {sz0:.1f}")
    if pz1 > sz1 + tol: _warn(f"z 终点 {pz1:.1f} > Space 前边界 {sz1:.1f}")


# ================================================================
# 批量定位
# ================================================================

def place_all(
    panels: list[Panel],
    space_map: dict[str, Space],
    *,
    dirty_only: bool = False,
    apply_to_panel: bool = True,
) -> PlacementBatch:
    """
    批量定位板件列表。

    Args:
        panels:         板件列表
        space_map:      space_id → Space，由调用方从 walk_dfs 构建
        dirty_only:     只定位脏板件
        apply_to_panel: 是否将结果写回 panel

    Returns:
        PlacementBatch

    典型调用：
        space_map = {s.id: s for s in walk_dfs(root)}
        batch = place_all(panels, space_map)
        batch.print_summary()
    """
    batch = PlacementBatch()

    for panel in panels:
        if dirty_only and not panel.is_dirty:
            continue

        space = space_map.get(panel.space_id or "")
        if space is None:
            r = PlacementResult(panel_id=panel.id, panel_name=panel.name)
            r.errors.append(
                f"找不到关联 Space（space_id={panel.space_id}），跳过定位"
            )
            batch.results.append(r)
            continue

        batch.results.append(
            place(panel, space, apply_to_panel=apply_to_panel)
        )

    return batch


def relocate_dirty(
    panels: list[Panel],
    space_map: dict[str, Space],
) -> PlacementBatch:
    """
    只重定位脏板件，供 incremental_solver 在 calculate 之后调用。
    等价于 place_all(..., dirty_only=True, apply_to_panel=True)。
    """
    return place_all(panels, space_map, dirty_only=True, apply_to_panel=True)


# ================================================================
# 调试
# ================================================================

def print_placement_report(panels: list[Panel]) -> None:
    """打印所有板件的定位报告，核查坐标是否正确。"""
    print(
        f"{'名称':<16} {'角色':<12} {'朝向':<12} "
        f"{'x':>8} {'y':>8} {'z':>8}  {'W×H×T'}"
    )
    print("─" * 80)
    for p in panels:
        dirty_mark = " ✦" if p.is_dirty else ""
        print(
            f"{p.name or p.id[:8]:<16} "
            f"{p.role.value:<12} "
            f"{p.orientation.value:<12} "
            f"{p.x:>8.1f} {p.y:>8.1f} {p.z:>8.1f}  "
            f"{p.width:.1f}×{p.height:.1f}×{p.thickness:.1f}"
            f"{dirty_mark}"
        )
