from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from .panel_models import Panel, EdgeBandSpec
from ..space.space_models import Space
from ..constants.enums import PanelRole, EdgeBandFace, PanelOrientation
from ..constants.tolerance import DIMENSION_TOLERANCE
from ..dirty.dirty_flags import DirtyFlag
from ..panel.rules.panel_clearance_rules import get_clearance
from ..panel.rules.panel_edge_band_rules import get_edge_band_thickness
from ..panel.rules.panel_defaults import get_panel_defaults


# ================================================================
# 计算结果
# ================================================================

@dataclass
class CalcResult:
    """单块板件的尺寸计算结果快照。"""
    panel_id:    str
    panel_name:  str

    # 外观尺寸（含封边，用于展示）
    gross_width:     float = 0.0
    gross_height:    float = 0.0
    thickness:       float = 0.0

    # 开料尺寸（扣封边厚度，交 CNC）
    net_width:       float = 0.0
    net_height:      float = 0.0

    # 封边扣减明细（mm）
    band_left:       float = 0.0
    band_right:      float = 0.0
    band_top:        float = 0.0
    band_bottom:     float = 0.0

    # 缝隙扣减明细（mm）
    clearance_left:  float = 0.0
    clearance_right: float = 0.0
    clearance_top:   float = 0.0
    clearance_bottom:float = 0.0

    errors:  list[str] = field(default_factory=list)
    warnings:list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return len(self.errors) == 0

    def __repr__(self) -> str:
        return (
            f"CalcResult({self.panel_name}  "
            f"gross={self.gross_width:.1f}×{self.gross_height:.1f}  "
            f"net={self.net_width:.1f}×{self.net_height:.1f}  "
            f"t={self.thickness:.1f})"
        )


# ================================================================
# 封边扣减
# ================================================================

def _band_deduction(panel: Panel) -> dict[str, float]:
    """
    计算四个方向的封边厚度扣减量。

    封边厚度影响开料净尺寸：
      net_width  = gross_width  - band_left  - band_right
      net_height = gross_height - band_top   - band_bottom

    封边宽度（visible width）不影响开料尺寸，
    封边厚度（thickness of band strip）才影响。
    """
    def _t(face: EdgeBandFace) -> float:
        spec = panel.edge_bands.get(face)
        return spec.thickness if spec and spec.is_valid() else 0.0

    return {
        "left":   _t(EdgeBandFace.LEFT),
        "right":  _t(EdgeBandFace.RIGHT),
        "top":    _t(EdgeBandFace.TOP),
        "bottom": _t(EdgeBandFace.BOTTOM),
    }


# ================================================================
# 缝隙扣减
# ================================================================

def _clearance_deduction(
    panel: Panel,
    space: Space,
) -> dict[str, float]:
    """
    计算板件四个方向的安装缝隙扣减量。

    缝隙规则来源：
      - 门板/抽屉前板：panel_clearance_rules 按角色返回标准缝隙
      - 其他结构板：通常缝隙为 0（已在 wrap_rules 里处理）

    缝隙影响外观尺寸（gross），不影响开料尺寸（net）：
      gross_width  = space_opening_width  - clearance_left - clearance_right
      gross_height = space_opening_height - clearance_top  - clearance_bottom
    """
    clearance = get_clearance(panel.role, space)
    return {
        "left":   clearance.left,
        "right":  clearance.right,
        "top":    clearance.top,
        "bottom": clearance.bottom,
    }


# ================================================================
# 核心计算
# ================================================================

def calculate(
    panel: Panel,
    space: Space,
    *,
    apply_to_panel: bool = True,
) -> CalcResult:
    """
    单块板件的完整尺寸计算：

      1. 从所属 Space 的开口尺寸出发
      2. 扣减安装缝隙 → 得到外观尺寸（gross）
      3. 扣减封边厚度 → 得到开料净尺寸（net）
      4. 验证净尺寸合法性

    Args:
        panel:          待计算的板件
        space:          板件所属 Space 节点
        apply_to_panel: True → 计算完直接写入 panel 字段
                        False → 只返回 CalcResult，不修改 panel

    Returns:
        CalcResult 快照，无论 apply_to_panel 是否为 True 都返回

    典型调用：
        # 计算并写入
        result = calculate(panel, space)

        # 只预览，不写入（用于 UI 实时显示）
        result = calculate(panel, space, apply_to_panel=False)
    """
    result = CalcResult(panel_id=panel.id, panel_name=panel.name or panel.role.value)

    # ── Step 1：从 Space 取开口尺寸 ──────────────────────────
    opening_w, opening_h = _get_opening_size(panel, space)

    # ── Step 2：扣减缝隙 → 外观尺寸 ─────────────────────────
    clr = _clearance_deduction(panel, space)
    gross_w = opening_w - clr["left"] - clr["right"]
    gross_h = opening_h - clr["top"]  - clr["bottom"]

    result.clearance_left   = clr["left"]
    result.clearance_right  = clr["right"]
    result.clearance_top    = clr["top"]
    result.clearance_bottom = clr["bottom"]

    # ── Step 3：扣减封边厚度 → 净尺寸 ───────────────────────
    band = _band_deduction(panel)
    net_w = gross_w - band["left"] - band["right"]
    net_h = gross_h - band["top"]  - band["bottom"]

    result.band_left   = band["left"]
    result.band_right  = band["right"]
    result.band_top    = band["top"]
    result.band_bottom = band["bottom"]

    # ── Step 4：厚度（由 defaults / material 决定，此处直接读取）
    thickness = panel.thickness   # 已由 generator 写入

    # ── Step 5：合法性检查 ───────────────────────────────────
    from ..constants.dimensions import MIN_PANEL_WIDTH, MIN_PANEL_HEIGHT

    if gross_w < MIN_PANEL_WIDTH:
        result.errors.append(
            f"外观宽度 {gross_w:.1f} mm < 最小值 {MIN_PANEL_WIDTH} mm"
        )
    if gross_h < MIN_PANEL_HEIGHT:
        result.errors.append(
            f"外观高度 {gross_h:.1f} mm < 最小值 {MIN_PANEL_HEIGHT} mm"
        )
    if net_w <= 0:
        result.errors.append(
            f"净宽度 {net_w:.1f} mm ≤ 0，封边厚度配置有误"
        )
    if net_h <= 0:
        result.errors.append(
            f"净高度 {net_h:.1f} mm ≤ 0，封边厚度配置有误"
        )
    if net_w < gross_w * 0.8:
        result.warnings.append(
            f"净宽度 {net_w:.1f} mm 比外观宽度 {gross_w:.1f} mm "
            f"小超过 20%，封边厚度是否异常？"
        )

    # ── 写入 CalcResult ──────────────────────────────────────
    result.gross_width  = max(gross_w, 0.0)
    result.gross_height = max(gross_h, 0.0)
    result.thickness    = thickness
    result.net_width    = max(net_w,   0.0)
    result.net_height   = max(net_h,   0.0)

    # ── 写回 Panel ───────────────────────────────────────────
    if apply_to_panel and result.ok:
        panel.set_size(
            width=result.gross_width,
            height=result.gross_height,
            thickness=result.thickness,
        )
        panel.dirty_flag = DirtyFlag.CLEAN

    return result


def calculate_left_side_panel(panel: Panel, space: Space, *, thickness: float | None = None) -> None:
    """
    左侧竖板（``PanelRole.LEFT_SIDE``）尺寸：写入 ``width/height/thickness``，朝向 ``VERTICAL_X``。

    不经由通用 ``calculate`` 的缝隙/封边链，避免未走 generator 时开口尺寸为 0。
    尺寸语义与 ``panel_bounds`` 中 ``VERTICAL_X`` 一致：``width``→世界 Z、``height``→Y、``thickness``→X。
    """
    t = float(thickness) if thickness is not None else float(panel.thickness or 18.0)
    t = max(6.0, min(t, 80.0))
    panel.orientation = PanelOrientation.VERTICAL_X
    panel.set_size(
        width=float(space.depth),
        height=float(space.height),
        thickness=t,
    )


# ================================================================
# 开口尺寸提取
# ================================================================

def _get_opening_size(panel: Panel, space: Space) -> tuple[float, float]:
    """
    根据板件角色和朝向，从 Space 中提取对应方向的开口尺寸。

    板件角色与开口尺寸的对应关系：

      旁板（LEFT/RIGHT）     → opening_w = space.depth，opening_h = space.height
      顶/底板（TOP/BOTTOM）  → opening_w = space.width，opening_h = space.depth
      背板（BACK）           → opening_w = space.width，opening_h = space.height
      层板（SHELF）          → opening_w = space.width，opening_h = space.depth
      中隔板（DIVIDER）      → opening_w = space.depth，opening_h = space.height
      门板（DOOR_*）         → 使用 opening/ 计算后的开口净尺寸
      抽屉前板（DRAWER_FRONT）→ 使用 opening/ 计算后的开口净尺寸
    """
    role = panel.role

    # 结构板：直接从 Space 尺寸推算
    STRUCTURAL_MAP: dict[PanelRole, tuple[float, float]] = {
        PanelRole.LEFT:       (space.depth, space.height),
        PanelRole.LEFT_SIDE:  (space.depth, space.height),
        PanelRole.RIGHT:   (space.depth,  space.height),
        PanelRole.TOP:     (space.width,  space.depth),
        PanelRole.BOTTOM:  (space.width,  space.depth),
        PanelRole.BACK:    (space.width,  space.height),
        PanelRole.SHELF:   (space.width,  space.depth),
        PanelRole.DIVIDER: (space.depth,  space.height),
    }
    if role in STRUCTURAL_MAP:
        return STRUCTURAL_MAP[role]

    # 开口板（门/抽屉前板）：从 Space.metadata 读取 opening 计算结果
    # opening/ 模块会在 metadata["opening_width"] / ["opening_height"] 写入
    if role in (PanelRole.DOOR_LEFT, PanelRole.DOOR_RIGHT,
                PanelRole.DOOR_DOUBLE, PanelRole.DRAWER_FRONT):
        ow = space.metadata.get("opening_width",  space.width)
        oh = space.metadata.get("opening_height", space.height)
        return float(ow), float(oh)

    # 未知角色：退化到 Space 宽高
    return space.width, space.height


# ================================================================
# 批量计算
# ================================================================

def calculate_all(
    panels: list[Panel],
    space_map: dict[str, Space],
    *,
    dirty_only: bool = False,
    apply_to_panel: bool = True,
) -> list[CalcResult]:
    """
    批量计算板件列表的净尺寸。

    Args:
        panels:         板件列表
        space_map:      space_id → Space 对象的字典，由 generator 提供
        dirty_only:     True → 只计算脏板件，跳过 CLEAN 板件
        apply_to_panel: 是否将结果写回 panel 对象

    Returns:
        CalcResult 列表，与 panels 一一对应（跳过的返回空快照）

    典型调用：
        space_map = {s.id: s for s in walk_dfs(root)}
        results = calculate_all(panel_list, space_map)
    """
    results = []

    for panel in panels:
        # dirty_only 模式跳过干净板件
        if dirty_only and not panel.is_dirty:
            results.append(CalcResult(
                panel_id=panel.id,
                panel_name=panel.name,
                gross_width=panel.width,
                gross_height=panel.height,
                thickness=panel.thickness,
                net_width=panel.net_width,
                net_height=panel.net_height,
            ))
            continue

        space = space_map.get(panel.space_id or "")
        if space is None:
            r = CalcResult(panel_id=panel.id, panel_name=panel.name)
            r.errors.append(
                f"找不到关联 Space（space_id={panel.space_id}），跳过计算"
            )
            results.append(r)
            continue

        results.append(calculate(panel, space, apply_to_panel=apply_to_panel))

    return results


def recalculate_dirty(
    panels: list[Panel],
    space_map: dict[str, Space],
) -> list[CalcResult]:
    """
    只重算脏板件，供 incremental_solver 在 generate_incremental 之后调用。
    等价于 calculate_all(..., dirty_only=True, apply_to_panel=True)。
    """
    return calculate_all(panels, space_map, dirty_only=True, apply_to_panel=True)


# ================================================================
# 调试
# ================================================================

def print_calc_report(results: list[CalcResult]) -> None:
    """打印所有板件的尺寸计算报告，开发期核查封边/缝隙扣减是否正确。"""
    errors = [r for r in results if not r.ok]
    print(f"[Calculator] 共 {len(results)} 块  错误={len(errors)}")
    print(
        f"{'名称':<16} {'外观W':>8} {'外观H':>8} "
        f"{'净W':>8} {'净H':>8} {'厚':>6} "
        f"{'封边扣(L/R/T/B)':>20}"
    )
    print("─" * 82)
    for r in results:
        band_detail = (
            f"{r.band_left:.1f}/"
            f"{r.band_right:.1f}/"
            f"{r.band_top:.1f}/"
            f"{r.band_bottom:.1f}"
        )
        flag = " ✗" if not r.ok else ""
        print(
            f"{r.panel_name:<16} "
            f"{r.gross_width:>8.1f} {r.gross_height:>8.1f} "
            f"{r.net_width:>8.1f} {r.net_height:>8.1f} "
            f"{r.thickness:>6.1f} "
            f"{band_detail:>20}"
            f"{flag}"
        )
    if errors:
        print()
        for r in errors:
            for e in r.errors:
                print(f"  ✗ {r.panel_name}: {e}")
