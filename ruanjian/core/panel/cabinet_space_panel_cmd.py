# -*- coding: utf-8 -*-
"""
将板件挂到 ``Space`` 的实现（纯数据，无 UI）。

- ``Space.panel_groups``：按组挂载（如 ``add_left_side_panel``）
- ``Space.panels``：扁平挂载（兼容旧路径）

由 ``commands.panel_commands`` / ``cabinet_panel_tree_cmd`` 调用。
"""

from __future__ import annotations

from typing import Any

from ..constants.enums import AnchorType, PanelRole, PlacementMode
from ..debug_flags import DEBUG_VIEW3D
from ..space.constraint_engine import ConstraintEngine
from ..space.space_face_occupancy import SpaceFace, get_face_occupancy_manager
from ..space.space_models import Space

from .panel_calculator import calculate_left_side_panel
from .panel_models import Panel, PanelGroup
from .panel_placement import left_side_stack_offset_x, place_left_side_panel

_fit_engine = ConstraintEngine()


def left_side_stack_offset_mm(space: Space) -> float:
    """已有左侧板沿 +X 堆叠的累计厚度（毫米）；供 GL 预览与落点与数据层一致。"""
    return left_side_stack_offset_x(space)


def _target_space(ctx: dict[str, Any]) -> Space | None:
    selection = ctx.get("selection")
    if selection is not None:
        s = getattr(selection, "active_space", None)
        if isinstance(s, Space):
            return s
    root = ctx.get("root_space")
    if isinstance(root, Space):
        return root
    project = ctx.get("project")
    if project is not None:
        rs = getattr(project, "root_space", None)
        if isinstance(rs, Space):
            return rs
    return None


def build_left_side_panel(space: Space, thickness: float = 18.0) -> Panel:
    """
    构造一块左侧板实例（算尺、落位、校验），**尚未**写入 ``panel_groups`` / 面占用。

    供 ``CommandFactory`` 在 ``UndoStack.push`` 之前绑定 ``AddBoardCommand(target_space, panel)``；
    实际挂载由 ``mount_left_side_panel`` 在 ``execute`` 内完成。
    """
    t = max(6.0, min(float(thickness), 80.0))
    panel = Panel(
        name="左侧板",
        role=PanelRole.LEFT_SIDE,
        placement_mode=PlacementMode.ANCHOR_FIXED,
        anchor_type=AnchorType.LEFT,
    )
    calculate_left_side_panel(panel, space, thickness=t)
    fm = get_face_occupancy_manager()
    if not fm.can_place(space.id, SpaceFace.LEFT, panel):
        raise RuntimeError("该空间左侧面已占用板件，无法重复添加左侧板。")
    panel.space_id = space.id
    place_left_side_panel(panel, space)
    if not _fit_engine.validate(space, panel):
        raise RuntimeError("板件超出当前空间盒子尺寸，无法添加左侧板。")
    return panel


def mount_left_side_panel(space: Space, panel: Panel) -> None:
    """将 ``build_left_side_panel`` 产出的 **同一** ``Panel`` 挂入 ``space.panel_groups`` 并登记面占用。"""
    fm = get_face_occupancy_manager()
    if not hasattr(space, "panel_groups") or space.panel_groups is None:
        space.panel_groups = []
    for g in space.panel_groups:
        pls = getattr(g, "panels", None) or []
        if panel in pls:
            return
    group = PanelGroup(space_id=space.id)
    group.add(panel)
    space.panel_groups.append(group)
    if not fm.occupy(space.id, SpaceFace.LEFT, panel):
        group.panels.remove(panel)
        space.panel_groups.remove(group)
        raise RuntimeError("左侧面占用登记失败（内部状态不一致）。")


def build_right_side_panel(space: Space, thickness: float = 18.0) -> Panel:
    """构造一块右侧板实例（算尺、落位、校验），**尚未**写入 ``panel_groups`` / 面占用。"""
    t = max(6.0, min(float(thickness), 80.0))
    panel = Panel(
        name="右侧板",
        role=PanelRole.RIGHT_SIDE,
        placement_mode=PlacementMode.ANCHOR_FIXED,
        anchor_type=AnchorType.RIGHT,
    )
    calculate_left_side_panel(panel, space, thickness=t)
    fm = get_face_occupancy_manager()
    if not fm.can_place(space.id, SpaceFace.RIGHT, panel):
        raise RuntimeError("该空间右侧面已占用板件，无法重复添加右侧板。")
    panel.space_id = space.id
    panel.set_position(
        x=float(space.x) + float(space.width) - t,
        y=float(space.y),
        z=float(space.z),
    )
    if not _fit_engine.validate(space, panel):
        raise RuntimeError("板件超出当前空间盒子尺寸，无法添加右侧板。")
    return panel


def mount_right_side_panel(space: Space, panel: Panel) -> None:
    """将 ``build_right_side_panel`` 产出的 ``Panel`` 挂入 ``space.panel_groups`` 并登记面占用。"""
    fm = get_face_occupancy_manager()
    if not hasattr(space, "panel_groups") or space.panel_groups is None:
        space.panel_groups = []
    for g in space.panel_groups:
        pls = getattr(g, "panels", None) or []
        if panel in pls:
            return
    group = PanelGroup(space_id=space.id)
    group.add(panel)
    space.panel_groups.append(group)
    if not fm.occupy(space.id, SpaceFace.RIGHT, panel):
        group.panels.remove(panel)
        space.panel_groups.remove(group)
        raise RuntimeError("右侧面占用登记失败（内部状态不一致）。")


def detach_right_side_panel(panel: Panel, space: Space) -> None:
    """从 ``space`` 上卸下右侧板并释放右侧面占用。"""
    fm = get_face_occupancy_manager()
    fm.release_for_panel(panel)
    if not hasattr(space, "panel_groups") or space.panel_groups is None:
        return
    groups = space.panel_groups
    for g in list(groups):
        pls = getattr(g, "panels", None) or []
        if panel in pls:
            pls.remove(panel)
            if len(pls) == 0 and g in groups:
                groups.remove(g)
            break


def add_left_side_panel(space: Space, thickness: float = 18.0) -> Panel:
    """
    给 Space 添加左侧板（构建 + 挂载一步完成）。

    交互撤销路径请用 ``build_left_side_panel`` + ``mount_left_side_panel`` + ``AddBoardCommand``。
    """
    if DEBUG_VIEW3D:
        print("[Core] add_left_side_panel ENTER")
    panel = build_left_side_panel(space, thickness=thickness)
    mount_left_side_panel(space, panel)
    if DEBUG_VIEW3D:
        print("[Core] add_left_side_panel DONE")
    return panel


def detach_left_side_panel(panel: Panel, space: Space) -> None:
    """
    从 ``space`` 上卸下 ``add_left_side_panel`` 挂载的同一块 ``Panel`` 实例（禁止 ``deepcopy`` 后删除）。

    释放面占用，并从 ``panel_groups`` 中移除所在组（组空则删组）。
    """
    fm = get_face_occupancy_manager()
    fm.release_for_panel(panel)
    if not hasattr(space, "panel_groups") or space.panel_groups is None:
        return
    groups = space.panel_groups
    for g in list(groups):
        pls = getattr(g, "panels", None) or []
        if panel in pls:
            pls.remove(panel)
            if len(pls) == 0 and g in groups:
                groups.remove(g)
            break


def add_left_panel(ctx: dict[str, Any], payload: Any = None) -> None:
    """在当前选中（或根）Space 上追加一块左侧竖板。"""
    space = _target_space(ctx)
    if space is None:
        raise RuntimeError(
            "add_left_panel: no target Space (selection / root_space / project.root_space)"
        )

    t = 18.0
    if isinstance(payload, dict):
        raw = payload.get("thickness")
        if raw is not None:
            try:
                t = float(raw)
            except (TypeError, ValueError):
                t = 18.0
    t = max(6.0, min(t, 80.0))

    add_left_side_panel(space, thickness=t)
    if DEBUG_VIEW3D:
        print(f"[Panel] add left panel -> {space.name}")
