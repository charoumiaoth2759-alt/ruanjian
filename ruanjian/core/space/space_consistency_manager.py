# -*- coding: utf-8 -*-
"""
根空间尺寸变化后的唯一一致性入口：校验板件、标记状态、重绑 ``space_id``、重定位。

禁止删除板件或清空 ``boards`` / ``panel_groups`` 内列表；禁止清空 ``Space.children``。
"""

from __future__ import annotations

from typing import Any, TYPE_CHECKING

from ..dirty.dirty_flags import DirtyFlag
from ..constants.enums import PlacementMode
from ..panel.anchor_placement import apply_mixed_placements, placement_mode_effective
from ..panel.panel_models import Panel, PanelGroup
from .constraint_engine import ConstraintEngine
from .placement_state import (
    BLOCKED,
    INVALID,
    NEEDS_RELAYOUT,
    PLACED,
    UNPLACED,
    set_placement_state,
)
from .space_face_occupancy import get_face_occupancy_manager
from .space_resolver import SpaceResolver
from .tree import walk_dfs

if TYPE_CHECKING:
    from .space_models import Space


def _collect_panels_unique(root: "Space") -> list[Panel]:
    """树上全部 ``Panel``（``panel_groups`` + 各节点 ``panels``），按 ``id`` 去重。"""
    seen: set[str] = set()
    out: list[Panel] = []

    def add(p: Panel) -> None:
        k = str(getattr(p, "id", "") or id(p))
        if k in seen:
            return
        seen.add(k)
        out.append(p)

    for node in walk_dfs(root):
        for grp in getattr(node, "panel_groups", None) or []:
            for p in getattr(grp, "panels", None) or []:
                if isinstance(p, Panel):
                    add(p)
        for p in getattr(node, "panels", None) or []:
            if isinstance(p, Panel):
                add(p)
    return out


def _detach_panel_from_tree(root: "Space", panel: Panel) -> None:
    """从各 ``PanelGroup`` / ``Space.panels`` 中移除引用（不销毁 ``Panel`` 对象）。"""
    for node in walk_dfs(root):
        for grp in list(getattr(node, "panel_groups", None) or []):
            pls = getattr(grp, "panels", None)
            if pls and panel in pls:
                pls.remove(panel)
        flat = getattr(node, "panels", None)
        if flat and panel in flat:
            flat.remove(panel)
        # 去掉已无板件的组，避免空壳占位
        groups = getattr(node, "panel_groups", None)
        if groups:
            node.panel_groups = [g for g in groups if len(getattr(g, "panels", []) or []) > 0]


def _ensure_panel_group(space: "Space") -> PanelGroup:
    sid = space.id
    for g in getattr(space, "panel_groups", None) or []:
        if getattr(g, "space_id", None) == sid:
            return g
    if not hasattr(space, "panel_groups") or space.panel_groups is None:
        space.panel_groups = []
    g = PanelGroup(space_id=sid)
    space.panel_groups.append(g)
    return g


def _attach_panel_to_space(space: "Space", panel: Panel) -> None:
    """将板件挂到目标 ``Space`` 的 ``panel_groups``（``PanelGroup.add`` 同步 ``space_id``）。"""
    grp = _ensure_panel_group(space)
    if panel not in grp.panels:
        grp.add(panel)


class SpaceConsistencyManager:
    """
    空间一致性管理器：``root`` 外形尺寸变化后的板件与占用语义统一处理。

    调用方应传入当前树上全部待处理板件（通常 ``_collect_panels_unique(root)``）。
    """

    def __init__(
        self,
        constraint_engine: ConstraintEngine | None = None,
        *,
        face_manager: Any | None = None,
    ) -> None:
        self.constraint_engine = constraint_engine or ConstraintEngine()
        self._faces = face_manager or get_face_occupancy_manager()
        self._resolver = SpaceResolver(self.constraint_engine, self._faces)

    def on_root_resized(self, root: "Space", boards: list[Any]) -> None:
        """
        根 ``Space`` 的 ``width`` / ``height`` / ``depth`` 已更新后调用。

        ``boards`` 为当前应参与一致性处理的板件列表；不得清空该列表，
        本方法也不会从列表中删除元素。
        """
        panels: list[Panel] = [p for p in boards if isinstance(p, Panel)]
        if not panels:
            panels = _collect_panels_unique(root)

        self._mark_tree_dirty(root)
        invalid = self._validate_boards(root, panels)
        self._handle_invalid_boards(invalid)
        self._reflow_boards(root, panels)
        self._faces.rebuild_from_root(root)

    def _mark_tree_dirty(self, root: "Space") -> None:
        root.dirty_flag = DirtyFlag.DIRTY

    def _validate_boards(self, root: "Space", boards: list[Panel]) -> list[Panel]:
        space_map = {s.id: s for s in walk_dfs(root)}
        invalid: list[Panel] = []
        for board in boards:
            if not self._is_board_still_valid(space_map, board):
                invalid.append(board)
        return invalid

    def _is_board_still_valid(self, space_map: dict[str, "Space"], board: Panel) -> bool:
        sid = getattr(board, "space_id", None)
        space = space_map.get(sid or "")
        if space is None:
            return False
        # 锚定板：只要宿主节点仍在树上即视为「仍有效」，尺寸不足不触发迁出/删除
        if placement_mode_effective(board) == PlacementMode.ANCHOR_FIXED:
            return True
        if not self.constraint_engine.validate(space, board):
            return False
        return True

    def _handle_invalid_boards(self, invalid_boards: list[Panel]) -> None:
        for board in invalid_boards:
            if placement_mode_effective(board) == PlacementMode.ANCHOR_FIXED:
                set_placement_state(board, BLOCKED)
            else:
                set_placement_state(board, INVALID)

    def _reflow_boards(self, root: "Space", boards: list[Panel]) -> None:
        self._reset_space_occupancy_flags(root)

        for board in boards:
            space_map = {s.id: s for s in walk_dfs(root)}
            sid = getattr(board, "space_id", None)
            host = space_map.get(sid or "")
            is_anchor = placement_mode_effective(board) == PlacementMode.ANCHOR_FIXED

            if is_anchor:
                if host is not None:
                    ok = self.constraint_engine.validate(host, board)
                    set_placement_state(board, PLACED if ok else BLOCKED)
                    board.dirty_flag = DirtyFlag.DIRTY
                    continue
                # 宿主 id 已不在树上：换挂目标，但绝不卸载锚定板
                best = self._resolver.pick_best_space(root, board)
                if best is not None:
                    _detach_panel_from_tree(root, board)
                    _attach_panel_to_space(best, board)
                    ok = self.constraint_engine.validate(best, board)
                else:
                    ok = False
                set_placement_state(board, PLACED if ok else BLOCKED)
                board.dirty_flag = DirtyFlag.DIRTY
                continue

            if host is not None and self.constraint_engine.validate(host, board):
                set_placement_state(board, PLACED)
                board.dirty_flag = DirtyFlag.DIRTY
                continue

            set_placement_state(board, NEEDS_RELAYOUT)
            best = self._resolver.pick_best_space(root, board)
            if best is None:
                set_placement_state(board, UNPLACED)
                _detach_panel_from_tree(root, board)
                board.space_id = None
                continue

            _detach_panel_from_tree(root, board)
            _attach_panel_to_space(best, board)
            set_placement_state(board, PLACED)
            board.dirty_flag = DirtyFlag.DIRTY

        space_map = {s.id: s for s in walk_dfs(root)}
        apply_mixed_placements(space_map, boards)
        self._sync_occupancy_from_panels(root)

    def _reset_space_occupancy_flags(self, root: "Space") -> None:
        for node in walk_dfs(root):
            if hasattr(node, "is_occupied"):
                setattr(node, "is_occupied", False)

    def _sync_occupancy_from_panels(self, root: "Space") -> None:
        """按当前挂载的板件组更新 ``is_occupied``（供 ``infer_space_state``）。"""
        for node in walk_dfs(root):
            flat = getattr(node, "panels", None) or []
            groups = getattr(node, "panel_groups", None) or []
            n_group_panels = sum(len(getattr(g, "panels", []) or []) for g in groups)
            has = bool(flat) or n_group_panels > 0
            setattr(node, "is_occupied", has)


def collect_panels_from_space_tree(root: "Space") -> list[Panel]:
    """供命令层在根尺寸变化后收集树上全部板件，交给 ``on_root_resized``。"""
    return _collect_panels_unique(root)
