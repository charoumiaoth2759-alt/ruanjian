# -*- coding: utf-8 -*-
"""
锚点贴边 vs 自动布局：与 ``panel_placement.place`` 使用同一套空间坐标与包裹规则。

``LEFT_SIDE`` 多块堆叠时，板件已在 ``panel_groups`` 内，**不能**再用
``left_side_stack_offset_x``（会把自身厚度算进偏移）；改由本模块按序累加厚度重贴左缘。
"""

from __future__ import annotations

from typing import Any

from ..constants.enums import AnchorType, PanelRole, PlacementMode
from ..dirty.dirty_flags import DirtyFlag
from ..space.space_models import Space
from .panel_bounds import panel_extents_world_xyz
from .panel_models import Panel
from .panel_placement import place
from .rules.panel_defaults import get_panel_defaults
from .rules.panel_wrap_rules import get_wrap_rule

_AUTO_ROLES: frozenset[PanelRole] = frozenset(
    {
        PanelRole.SHELF,
        PanelRole.DIVIDER,
        PanelRole.DOOR_LEFT,
        PanelRole.DOOR_RIGHT,
        PanelRole.DOOR_DOUBLE,
        PanelRole.DRAWER_FRONT,
        PanelRole.UNKNOWN,
    }
)


def placement_mode_effective(panel: Panel) -> PlacementMode:
    """未显式设置时：围合骨架类默认锚定，层板/中隔板/门扇等默认自动布局。"""
    m = getattr(panel, "placement_mode", None)
    if isinstance(m, PlacementMode):
        return m
    role = getattr(panel, "role", PanelRole.UNKNOWN)
    if role in _AUTO_ROLES:
        return PlacementMode.AUTO_PLACED
    return PlacementMode.ANCHOR_FIXED


def anchor_type_effective(panel: Panel) -> AnchorType:
    """未显式设置时：由 ``role`` 推断锚边（与 ``panel_placement`` 语义一致）。"""
    a = getattr(panel, "anchor_type", None)
    if isinstance(a, AnchorType) and a != AnchorType.NONE:
        return a
    role = getattr(panel, "role", PanelRole.UNKNOWN)
    if role in (PanelRole.LEFT, PanelRole.LEFT_SIDE):
        return AnchorType.LEFT
    if role in (PanelRole.RIGHT, PanelRole.RIGHT_SIDE):
        return AnchorType.RIGHT
    if role == PanelRole.TOP:
        return AnchorType.TOP
    if role == PanelRole.BOTTOM:
        return AnchorType.BOTTOM
    if role == PanelRole.BACK:
        return AnchorType.BACK
    return AnchorType.NONE


def _role_eq(panel: Any, role: PanelRole) -> bool:
    r = getattr(panel, "role", None)
    if r == role:
        return True
    v = getattr(r, "value", None)
    return v == role.value


def place_left_side_stack_on_space(space: Space, panels: list[Panel]) -> None:
    """
    同一 ``Space`` 上全部 ``LEFT_SIDE``：按当前 ``x`` 排序后从左缘累加厚度重贴，
    与 ``add_left_side_panel`` 在「尚未入组」时调用 ``place_left_side_panel`` 的几何效果一致。
    """
    sides = [p for p in panels if _role_eq(p, PanelRole.LEFT_SIDE)]
    if not sides:
        return
    sides.sort(key=lambda p: (float(getattr(p, "x", 0.0)), float(getattr(p, "z", 0.0)), float(getattr(p, "y", 0.0))))
    defaults = get_panel_defaults(space.space_type)
    wrap = get_wrap_rule(space.space_type)
    y = float(space.y) + (
        0.0 if wrap.side_wraps_bottom else float(defaults.bottom_thickness)
    )
    z = float(space.z)
    off = 0.0
    sx = float(space.x)
    for p in sides:
        p.set_position(sx + off, y, z)
        off += float(getattr(p, "thickness", 18.0))
        p.dirty_flag = DirtyFlag.DIRTY


def _apply_edge_anchor(panel: Panel, space: Space, anchor: AnchorType) -> None:
    """
    按锚边写回最小角 ``(x,y,z)``（不删板件、不用比例位移）。

    与 ``panel_placement._calc_position`` 的围合语义对齐；``TOP`` 为贴 **顶**（大 ``y``），
    ``FRONT`` 为贴 **前**（大 ``z``）。
    """
    dx, dy, dz = panel_extents_world_xyz(panel)
    sx0, sy0, sz0 = float(space.x), float(space.y), float(space.z)
    sw, sh, sd = float(space.width), float(space.height), float(space.depth)

    if anchor == AnchorType.LEFT:
        panel.set_position(sx0, panel.y, panel.z)
        return
    if anchor == AnchorType.RIGHT:
        panel.set_position(sx0 + sw - dx, panel.y, panel.z)
        return
    if anchor == AnchorType.BOTTOM:
        panel.set_position(panel.x, sy0, panel.z)
        return
    if anchor == AnchorType.TOP:
        panel.set_position(panel.x, sy0 + sh - dy, panel.z)
        return
    if anchor == AnchorType.BACK:
        panel.set_position(panel.x, panel.y, sz0)
        return
    if anchor == AnchorType.FRONT:
        panel.set_position(panel.x, panel.y, sz0 + sd - dz)
        return


def apply_anchor_panel(panel: Panel, space: Space) -> None:
    """
    锚定板件：只做贴空间边界校正。

    对 ``LEFT`` / ``RIGHT`` / ``TOP`` / ``BOTTOM`` / ``BACK`` 等标准围合角色，
    调用 ``place()`` 以复用包裹规则与朝向写入；其它角色按 ``anchor_type`` 用 AABB 贴边。
    """
    mode = placement_mode_effective(panel)
    if mode != PlacementMode.ANCHOR_FIXED:
        return

    anchor = anchor_type_effective(panel)
    if panel.role in (
        PanelRole.LEFT,
        PanelRole.RIGHT,
        PanelRole.TOP,
        PanelRole.BOTTOM,
        PanelRole.BACK,
    ):
        place(panel, space, apply_to_panel=True)
        return

    if anchor != AnchorType.NONE:
        _apply_edge_anchor(panel, space, anchor)
        panel.dirty_flag = DirtyFlag.DIRTY
        return

    place(panel, space, apply_to_panel=True)


def apply_mixed_placements(space_map: dict[str, Space], boards: list[Panel]) -> None:
    """
    按 Space 分组：先重排 ``LEFT_SIDE`` 堆叠，再处理其余 ``ANCHOR_FIXED``，最后 ``AUTO_PLACED``。

    不整表 ``place_all``，避免把锚定板当作普通列表统一重算导致 X 漂移。
    """
    by_space: dict[str, list[Panel]] = {}
    for b in boards:
        sid = getattr(b, "space_id", None)
        if not sid or sid not in space_map:
            continue
        by_space.setdefault(sid, []).append(b)

    for sid, plist in by_space.items():
        space = space_map[sid]

        left_sides = [
            p
            for p in plist
            if placement_mode_effective(p) == PlacementMode.ANCHOR_FIXED
            and _role_eq(p, PanelRole.LEFT_SIDE)
        ]
        if left_sides:
            place_left_side_stack_on_space(space, left_sides)

        for p in plist:
            if placement_mode_effective(p) != PlacementMode.ANCHOR_FIXED:
                continue
            if _role_eq(p, PanelRole.LEFT_SIDE):
                continue
            apply_anchor_panel(p, space)

        for p in plist:
            if placement_mode_effective(p) != PlacementMode.AUTO_PLACED:
                continue
            place(p, space, apply_to_panel=True)
