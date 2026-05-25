# -*- coding: utf-8 -*-
"""
将 **ConstraintEngine.validate** 的结果同步到 ``Space.metadata``，供 UI 映射颜色。

本模块属于 **业务 / 状态桥接**（写入决策），不包含任何颜色常量。
颜色请使用 ``space_visual_mapper.space_box_face_edge_rgba``。
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from .constraint_engine import ConstraintEngine
from .space_models import Space
from .space_state import PlacementState, write_ui_placement_for_space_display
from .tree import iter_leaves, walk_dfs


def left_side_preview_board_for_validate(space: Space, *, thickness: float = 18.0) -> Any:
    """
    构造一块与「添加左侧板」同尺度的临时板，仅用于 ``validate``，不加入 ``panel_groups``。
    """
    from ..constants.enums import AnchorType, PanelOrientation, PanelRole, PlacementMode
    from ..panel.panel_calculator import calculate_left_side_panel
    from ..panel.panel_models import Panel
    from ..panel.panel_placement import place_left_side_panel

    t = max(6.0, min(float(thickness), 80.0))
    p = Panel(
        name="_preview_left_side",
        role=PanelRole.LEFT_SIDE,
        orientation=PanelOrientation.VERTICAL_X,
        placement_mode=PlacementMode.ANCHOR_FIXED,
        anchor_type=AnchorType.LEFT,
    )
    calculate_left_side_panel(p, space, thickness=t)
    place_left_side_panel(p, space)
    return p


def refresh_leaf_placement_ui_metadata(
    root: Space | None,
    *,
    engine: ConstraintEngine | None = None,
    board_for_space: Callable[[Space], Any | None] | None = None,
) -> None:
    """
    遍历 ``root`` 上所有 **叶** ``Space``：

    - 先将树上所有节点（含非叶）的 UI 放置标记清为 ``UNKNOWN``（去掉 metadata 键）。
    - 若 ``board_for_space`` 为 ``None``：结束（UI 显示回默认逻辑）。
    - 否则对每个叶节点 ``sp``：``board = board_for_space(sp)``；若 ``board`` 为 ``None`` 则
      ``UNKNOWN``；否则 ``validate(sp, board)`` → ``ALLOWED`` / ``BLOCKED``。
    """
    if root is None:
        return

    eng = engine or ConstraintEngine()

    for node in walk_dfs(root):
        write_ui_placement_for_space_display(node, PlacementState.UNKNOWN)

    if board_for_space is None:
        return

    for leaf in iter_leaves(root):
        board = board_for_space(leaf)
        if board is None:
            write_ui_placement_for_space_display(leaf, PlacementState.UNKNOWN)
            continue
        ok = eng.validate(leaf, board)
        write_ui_placement_for_space_display(
            leaf, PlacementState.ALLOWED if ok else PlacementState.BLOCKED
        )


__all__ = [
    "left_side_preview_board_for_validate",
    "refresh_leaf_placement_ui_metadata",
]
