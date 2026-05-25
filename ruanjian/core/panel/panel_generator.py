from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from .panel_models import Panel, PanelGroup, EdgeBandSpec
from ..space.space_models import Space
from ..space.tree import walk_dfs, iter_leaves
from ..constants.enums import (
    PanelRole,
    EdgeBandFace,
    PanelOrientation,
    SpaceType,
    is_split_along_x,
    is_split_along_y,
    is_split_along_z,
    AnchorType,
    PlacementMode,
)
from ..panel.rules.panel_wrap_rules import WrapRule, get_wrap_rule
from ..panel.rules.panel_defaults import get_panel_defaults
from ..panel.rules.panel_edge_band_rules import apply_edge_band_rules
from ..dirty.dirty_flags import DirtyFlag


# ================================================================
# 生成结果
# ================================================================

@dataclass
class GenerateResult:
    """一次 generate() 调用的完整输出。"""
    groups:  list[PanelGroup] = field(default_factory=list)   # 按 Space 分组
    errors:  list[str]        = field(default_factory=list)
    skipped: list[str]        = field(default_factory=list)   # 跳过的 Space id

    @property
    def all_panels(self) -> list[Panel]:
        """展平所有组，返回完整板件列表。"""
        result = []
        for g in self.groups:
            result.extend(g.panels)
        return result

    @property
    def ok(self) -> bool:
        return len(self.errors) == 0

    def by_space(self, space_id: str) -> Optional[PanelGroup]:
        for g in self.groups:
            if g.space_id == space_id:
                return g
        return None

    def print_summary(self) -> None:
        total = len(self.all_panels)
        print(
            f"[PanelGenerator] 共生成 {total} 块板件  "
            f"组数={len(self.groups)}  "
            f"跳过={len(self.skipped)}  "
            f"错误={len(self.errors)}"
        )
        for err in self.errors:
            print(f"  ✗ {err}")


# ================================================================
# 空间树挂载板件收集
# ================================================================


def collect_space_panels(root_space: Space | None) -> list[Panel]:
    """
    收集整个空间树中的 Panel
    """
    panels: list[Panel] = []

    def walk(node: Space) -> None:
        for group in getattr(node, "panel_groups", []):
            panels.extend(group.panels)

        for child in node.children:
            walk(child)

    if root_space is not None:
        walk(root_space)

    return panels


# ================================================================
# 包裹规则上下文
# ================================================================

@dataclass
class WrapContext:
    """
    生成单块板件时的上下文，持有包裹规则所需的所有信息。
    避免把大量参数逐个传递给各个规则函数。
    """
    space:        Space
    role:         PanelRole
    wrap_rule:    WrapRule
    parent_space: Optional[Space] = None


# ================================================================
# 核心：单个 Space 生成其骨架板件
# ================================================================

def _generate_for_space(
    space: Space,
    *,
    dirty_only: bool = False,
) -> tuple[PanelGroup, list[str]]:
    """
    为单个 Space 节点生成骨架板件（旁板、顶板、底板、背板）。

    包裹规则决定每块板的尺寸归属：
      - 旁板包顶底：旁板高度 = Space 全高，顶底板宽度 = Space 宽 - 2×旁板厚
      - 顶板包旁板：顶底板宽度 = Space 全宽，旁板高度 = Space 高 - 顶板厚 - 底板厚
    具体规则由 panel_wrap_rules.py 提供，此处只做编排。

    Returns:
        (PanelGroup, errors)
    """
    group  = PanelGroup(space_id=space.id)
    errors: list[str] = []

    if dirty_only and not space.is_dirty:
        return group, errors

    # 从配置读取此 space_type 对应的包裹规则和默认参数
    wrap_rule = get_wrap_rule(space.space_type)
    defaults  = get_panel_defaults(space.space_type)

    # ── 旁板（LEFT / RIGHT）────────────────────────────────
    side_thickness = defaults.side_thickness

    for role, x_pos in (
        (PanelRole.LEFT,  space.x),
        (PanelRole.RIGHT, space.x + space.width - side_thickness),
    ):
        p = Panel(
            name=f"{space.name}_{role.value}",
            role=role,
            orientation=PanelOrientation.VERTICAL_X,
            thickness=side_thickness,
        )
        _apply_side_size(p, space, wrap_rule, defaults)
        p.set_position(
            x=x_pos,
            y=space.y + (defaults.bottom_thickness if wrap_rule.bottom_wraps_sides else 0),
            z=space.z,
        )
        _mark_anchor(p, AnchorType.LEFT if role == PanelRole.LEFT else AnchorType.RIGHT)
        _bind_space(p, space)
        group.add(p)

    # ── 顶板（TOP）────────────────────────────────────────
    top = Panel(
        name=f"{space.name}_top",
        role=PanelRole.TOP,
        orientation=PanelOrientation.HORIZONTAL,
        thickness=defaults.top_thickness,
    )
    _apply_horizontal_size(top, space, wrap_rule, defaults, is_top=True)
    top.set_position(
        x=space.x + (side_thickness if wrap_rule.side_wraps_top else 0),
        y=space.y + space.height - defaults.top_thickness,
        z=space.z,
    )
    _bind_space(top, space)
    _mark_anchor(top, AnchorType.TOP)
    group.add(top)

    # ── 底板（BOTTOM）─────────────────────────────────────
    bottom = Panel(
        name=f"{space.name}_bottom",
        role=PanelRole.BOTTOM,
        orientation=PanelOrientation.HORIZONTAL,
        thickness=defaults.bottom_thickness,
    )
    _apply_horizontal_size(bottom, space, wrap_rule, defaults, is_top=False)
    bottom.set_position(
        x=space.x + (side_thickness if wrap_rule.side_wraps_bottom else 0),
        y=space.y,
        z=space.z,
    )
    _bind_space(bottom, space)
    _mark_anchor(bottom, AnchorType.BOTTOM)
    group.add(bottom)

    # ── 背板（BACK）───────────────────────────────────────
    if defaults.has_back:
        back = Panel(
            name=f"{space.name}_back",
            role=PanelRole.BACK,
            orientation=PanelOrientation.VERTICAL_Z,
            thickness=defaults.back_thickness,
        )
        _apply_back_size(back, space, wrap_rule, defaults)
        back.set_position(
            x=space.x + (side_thickness if wrap_rule.side_wraps_back else 0),
            y=space.y + (defaults.bottom_thickness if wrap_rule.bottom_wraps_back else 0),
            z=space.z,
        )
        _bind_space(back, space)
        _mark_anchor(back, AnchorType.BACK)
        group.add(back)

    # ── 封边规则 ───────────────────────────────────────────
    for panel in group.panels:
        try:
            apply_edge_band_rules(panel, space)
        except Exception as e:
            errors.append(
                f"封边规则应用失败 [{panel.name}]: {e}"
            )

    return group, errors


# ================================================================
# 尺寸分配辅助函数
# ================================================================

def _apply_side_size(
    panel: Panel,
    space: Space,
    wrap: WrapRule,
    defaults,
) -> None:
    """
    计算旁板的 width（深度方向）和 height（高度方向）。

    旁板的"width"在视觉上是深度，"height"受包裹规则影响：
      - 旁板包顶底 → height = space.height（全高）
      - 顶底包旁板 → height = space.height - top_t - bottom_t
    """
    depth = space.depth - (
        defaults.back_thickness if wrap.back_reduces_depth else 0
    )

    if wrap.side_wraps_top and wrap.side_wraps_bottom:
        # 旁板包顶底：旁板高度 = 全高
        height = space.height
    elif wrap.side_wraps_top:
        height = space.height - defaults.bottom_thickness
    elif wrap.side_wraps_bottom:
        height = space.height - defaults.top_thickness
    else:
        # 顶底包旁板：旁板高度扣除顶底板厚
        height = space.height - defaults.top_thickness - defaults.bottom_thickness

    panel.set_size(width=depth, height=height, thickness=defaults.side_thickness)


def _apply_horizontal_size(
    panel: Panel,
    space: Space,
    wrap: WrapRule,
    defaults,
    *,
    is_top: bool,
) -> None:
    """
    计算顶板/底板的 width（X 方向）和 height（深度方向）。

    顶底板宽度受包裹规则影响：
      - 旁板包顶底 → 顶底板宽 = space.width - 2×side_t
      - 顶底包旁板 → 顶底板宽 = space.width（全宽）
    """
    wraps_side = wrap.side_wraps_top if is_top else wrap.side_wraps_bottom

    width = space.width if wraps_side else (
        space.width - 2 * defaults.side_thickness
    )
    depth = space.depth - (
        defaults.back_thickness if wrap.back_reduces_depth else 0
    )

    thickness = defaults.top_thickness if is_top else defaults.bottom_thickness
    panel.set_size(width=width, height=depth, thickness=thickness)


def _apply_back_size(
    panel: Panel,
    space: Space,
    wrap: WrapRule,
    defaults,
) -> None:
    """
    计算背板的 width（X 方向）和 height（Y 方向）。
    背板嵌入旁板槽内，通常比内空略小。
    """
    width = space.width - (
        2 * defaults.side_thickness if wrap.side_wraps_back else 0
    )
    height = space.height - (
        (defaults.top_thickness if wrap.top_wraps_back else 0)
        + (defaults.bottom_thickness if wrap.bottom_wraps_back else 0)
    )
    panel.set_size(width=width, height=height, thickness=defaults.back_thickness)


def _bind_space(panel: Panel, space: Space) -> None:
    """将板件绑定到 Space，写入 space_id 和 space_bounds。"""
    panel.space_id = space.id
    panel.space_bounds = (
        space.x, space.y, space.z,
        space.x + space.width,
        space.y + space.height,
        space.z + space.depth,
    )


def _mark_anchor(panel: Panel, anchor: AnchorType) -> None:
    panel.placement_mode = PlacementMode.ANCHOR_FIXED
    panel.anchor_type = anchor


def _mark_auto(panel: Panel) -> None:
    panel.placement_mode = PlacementMode.AUTO_PLACED
    panel.anchor_type = AnchorType.NONE


# ================================================================
# 中隔板生成（非叶节点的分割面）
# ================================================================

def _generate_dividers(
    space: Space,
    defaults,
) -> tuple[list[Panel], list[str]]:
    """
    为非叶节点生成中隔板（分割面板件）。

    当父 Space 沿 X / Y / Z 轴分段时，子 Space 之间的共享面
    需要生成中隔板或层板（此函数处理非首子节点前的分割面）。

    Returns:
        (panels, errors)
    """
    panels: list[Panel] = []
    errors: list[str]   = []

    if space.is_leaf or not space.children:
        return panels, errors

    direction = space.split_direction
    defaults_root = get_panel_defaults(space.space_type)

    if is_split_along_x(direction):
        # 沿 X：子节点左边界处生成竖向中隔板（法向 X）
        for i, child in enumerate(space.children[1:], start=1):
            divider = Panel(
                name=f"{space.name}_div_{i}",
                role=PanelRole.DIVIDER,
                orientation=PanelOrientation.VERTICAL_X,
                thickness=defaults_root.divider_thickness,
            )
            depth  = space.depth - (
                defaults_root.back_thickness
                if get_wrap_rule(space.space_type).back_reduces_depth else 0
            )
            height = space.height - defaults_root.top_thickness - defaults_root.bottom_thickness
            divider.set_size(
                width=depth,
                height=height,
                thickness=defaults_root.divider_thickness,
            )
            divider.set_position(
                x=child.x - defaults_root.divider_thickness / 2,
                y=space.y + defaults_root.bottom_thickness,
                z=space.z,
            )
            _bind_space(divider, space)
            _mark_auto(divider)
            apply_edge_band_rules(divider, space)
            panels.append(divider)

    elif is_split_along_y(direction):
        # 沿 Y：子节点下边界处生成横向层板（法向 Y）
        for i, child in enumerate(space.children[1:], start=1):
            shelf = Panel(
                name=f"{space.name}_shelf_{i}",
                role=PanelRole.SHELF,
                orientation=PanelOrientation.HORIZONTAL,
                thickness=defaults_root.shelf_thickness,
            )
            width = space.width - 2 * defaults_root.side_thickness
            depth = space.depth - (
                defaults_root.back_thickness
                if get_wrap_rule(space.space_type).back_reduces_depth else 0
            )
            shelf.set_size(
                width=width,
                height=depth,
                thickness=defaults_root.shelf_thickness,
            )
            shelf.set_position(
                x=space.x + defaults_root.side_thickness,
                y=child.y - defaults_root.shelf_thickness / 2,
                z=space.z,
            )
            _bind_space(shelf, space)
            _mark_auto(shelf)
            apply_edge_band_rules(shelf, space)
            panels.append(shelf)

    elif is_split_along_z(direction):
        # 沿 Z：子节点前边界 z 处生成竖向板（法向 Z，板面在 XY）
        for i, child in enumerate(space.children[1:], start=1):
            shelf = Panel(
                name=f"{space.name}_z_shelf_{i}",
                role=PanelRole.SHELF,
                orientation=PanelOrientation.VERTICAL_Z,
                thickness=defaults_root.shelf_thickness,
            )
            width = space.width - 2 * defaults_root.side_thickness
            height = space.height - defaults_root.top_thickness - defaults_root.bottom_thickness
            shelf.set_size(
                width=width,
                height=height,
                thickness=defaults_root.shelf_thickness,
            )
            shelf.set_position(
                x=space.x + defaults_root.side_thickness,
                y=space.y + defaults_root.bottom_thickness,
                z=child.z - defaults_root.shelf_thickness / 2,
            )
            _bind_space(shelf, space)
            _mark_auto(shelf)
            apply_edge_band_rules(shelf, space)
            panels.append(shelf)

    return panels, errors


# ================================================================
# 主入口
# ================================================================

def generate(
    root: Space,
    *,
    dirty_only: bool = False,
    include_dividers: bool = True,
    include_skeleton: bool = False,
) -> GenerateResult:
    """
    从 Space 树生成板件分组结果。

    遍历策略：
      - ``include_skeleton=True``：为各 Space 生成骨架板件（LEFT/RIGHT/TOP/BOTTOM/BACK 等）
      - ``include_dividers=True`` 且 ``include_skeleton=True``：非叶节点再生成中隔板/层板
      - 无论骨架与否：都会把各节点 ``Space.panel_groups`` 中用户挂载的板件并入输出

    ``include_skeleton=False``（默认）时仅输出用户/命令挂载的板件，新建柜子后 3D 只保留
    逻辑空间盒线框，不出现自动 18mm 围壳。

    dirty_only=True 时跳过 CLEAN 节点，供 incremental_solver 调用。

    Args:
        root:               空间树根节点
        dirty_only:         只处理脏节点
        include_dividers:   是否生成中隔板/层板（仅当 ``include_skeleton`` 为真时生效）
        include_skeleton:   是否生成算法骨架围板（默认否，与「命令式加板」产品流一致）

    Returns:
        GenerateResult，调用 .all_panels 获取完整板件列表
    """
    final   = GenerateResult()
    seen_ids: set[str] = set()   # 防止同一 Space 重复生成

    for space in walk_dfs(root, order="pre"):

        if space.id in seen_ids:
            continue
        seen_ids.add(space.id)

        # dirty_only 模式跳过干净节点
        if dirty_only and not space.is_dirty:
            final.skipped.append(space.id)
            continue

        # 跳过纯逻辑分组节点（见 ``_should_skip``；当前枚举无 GROUP 时集合为空）
        if _should_skip(space):
            final.skipped.append(space.id)
            continue

        if include_skeleton:
            # 骨架板件（LEFT/RIGHT/TOP/BOTTOM/BACK 等）
            group, errs = _generate_for_space(space, dirty_only=dirty_only)
            final.errors.extend(errs)
            if group.panels:
                final.groups.append(group)

            # 中隔板 / 层板
            if include_dividers and not space.is_leaf:
                defaults = get_panel_defaults(space.space_type)
                div_panels, div_errs = _generate_dividers(space, defaults)
                final.errors.extend(div_errs)
                if div_panels:
                    # 中隔板归入同一 group
                    existing = final.by_space(space.id)
                    if existing:
                        for dp in div_panels:
                            existing.add(dp)
                    else:
                        g = PanelGroup(space_id=space.id)
                        for dp in div_panels:
                            g.add(dp)
                        final.groups.append(g)

        # 用户挂在 ``Space.panel_groups`` 上的板件（如「左侧板」命令）并入求解输出
        for ug in getattr(space, "panel_groups", []) or []:
            for p in getattr(ug, "panels", []) or []:
                existing = final.by_space(space.id)
                if existing is not None:
                    existing.add(p)
                else:
                    g = PanelGroup(space_id=space.id)
                    g.add(p)
                    final.groups.append(g)

    return final


def generate_incremental(
    root: Space,
    dirty_spaces: Optional[list[Space]] = None,
) -> GenerateResult:
    """
    局部增量生成，只重新生成脏 Space 的板件。
    供 incremental_solver 在 resolve() 之后调用。

    Args:
        root:          空间树根节点
        dirty_spaces:  需要重新生成的 Space 列表
                       None → 自动从树中查找所有脏节点

    Returns:
        GenerateResult，只包含本次重新生成的板件
    """
    if dirty_spaces is None:
        from ..space.tree import find_dirty
        dirty_spaces = find_dirty(root)

    if not dirty_spaces:
        return GenerateResult()

    # 临时标记这些节点为 DIRTY，其余节点保持 CLEAN
    # 让 generate(dirty_only=True) 只处理它们
    _ids = {s.id for s in dirty_spaces}
    for node in walk_dfs(root):
        if node.id in _ids:
            node.dirty_flag = DirtyFlag.DIRTY

    return generate(
        root,
        dirty_only=True,
        include_dividers=True,
        include_skeleton=False,
    )


# ================================================================
# 工具
# ================================================================

def _should_skip(space: Space) -> bool:
    """
    判断此 Space 是否应该跳过板件骨架生成。

    纯逻辑分组节点（如未来的 ``SpaceType.GROUP``）可不生成骨架；
    当前 ``core.space.enums.SpaceType`` 尚未定义 ``GROUP`` / ``VIRTUAL``，
    故用 ``getattr`` 组装集合，避免 ``AttributeError`` 被 ``solve`` 捕获后返回空板件列表。
    """
    skip_candidates = (
        getattr(SpaceType, "GROUP", None),
        getattr(SpaceType, "VIRTUAL", None),
    )
    skip_types = frozenset(t for t in skip_candidates if t is not None)
    return space.space_type in skip_types
