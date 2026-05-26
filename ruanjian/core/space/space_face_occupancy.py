# -*- coding: utf-8 -*-
"""
空间六个面的占用管理（按 ``space_id`` × ``SpaceFace``，与 ``Panel`` 解耦 UI）。

- 同一面默认只允许一块 **非叠放** 锚定板；**左侧板（``LEFT_SIDE``）** 可在同一 ``LEFT`` 面多块叠放。
- 根尺寸 / 一致性流程末尾调用 ``rebuild_from_root``：``reset`` 后按树上挂载重新登记。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Dict, Tuple

_face_manager_singleton: FaceOccupancyManager | None = None


class SpaceFace(Enum):
    LEFT = auto()
    RIGHT = auto()
    TOP = auto()
    BOTTOM = auto()
    FRONT = auto()
    BACK = auto()


class FaceState(Enum):
    FREE = auto()
    OCCUPIED = auto()
    SPLIT = auto()


@dataclass
class FaceOccupancy:
    state: FaceState = FaceState.FREE
    boards: list[Any] = field(default_factory=list)

    def is_free(self) -> bool:
        return self.state == FaceState.FREE and len(self.boards) == 0

    def occupy(self, board: Any) -> None:
        self.state = FaceState.OCCUPIED
        self.boards.append(board)

    def clear(self) -> None:
        self.state = FaceState.FREE
        self.boards.clear()


def _is_left_side_panel(board: Any) -> bool:
    from ..constants.enums import PanelRole

    r = getattr(board, "role", None)
    if r == PanelRole.LEFT_SIDE:
        return True
    return getattr(r, "value", None) == PanelRole.LEFT_SIDE.value


def _is_right_side_panel(board: Any) -> bool:
    from ..constants.enums import PanelRole

    r = getattr(board, "role", None)
    if r == PanelRole.RIGHT_SIDE:
        return True
    return getattr(r, "value", None) == PanelRole.RIGHT_SIDE.value


def _slot_left_face_only_left_side_stack(slot: FaceOccupancy) -> bool:
    """左面槽内若仅有 ``LEFT_SIDE`` 叠板，则仍允许再叠一块。"""
    if slot.is_free():
        return True
    for b in slot.boards:
        if not _is_left_side_panel(b):
            return False
    return True


def _slot_right_face_only_right_side_stack(slot: FaceOccupancy) -> bool:
    """右面槽内若仅有 ``RIGHT_SIDE`` 叠板，则仍允许再叠一块。"""
    if slot.is_free():
        return True
    for b in slot.boards:
        if not _is_right_side_panel(b):
            return False
    return True


def get_face_occupancy_manager() -> FaceOccupancyManager:
    global _face_manager_singleton
    if _face_manager_singleton is None:
        _face_manager_singleton = FaceOccupancyManager()
    return _face_manager_singleton


def reset_face_occupancy_manager() -> None:
    """测试或切换工程时可清空单例。"""
    global _face_manager_singleton
    _face_manager_singleton = None


def space_face_for_anchor_panel(panel: Any) -> SpaceFace | None:
    """由 ``anchor_type``（或 role 推断）得到 ``SpaceFace``。"""
    from ..constants.enums import AnchorType
    from ..panel.anchor_placement import anchor_type_effective

    at = anchor_type_effective(panel)
    m = {
        AnchorType.LEFT: SpaceFace.LEFT,
        AnchorType.RIGHT: SpaceFace.RIGHT,
        AnchorType.TOP: SpaceFace.TOP,
        AnchorType.BOTTOM: SpaceFace.BOTTOM,
        AnchorType.FRONT: SpaceFace.FRONT,
        AnchorType.BACK: SpaceFace.BACK,
    }
    return m.get(at)


class FaceOccupancyManager:
    """
    ``(space_id, SpaceFace)`` → 占用槽。

    锚定板挂载前 ``can_place``；成功后 ``occupy``；``rebuild_from_root`` 与树对齐。
    """

    def __init__(self) -> None:
        self._slots: Dict[Tuple[str, SpaceFace], FaceOccupancy] = {}

    def _slot(self, space_id: str, face: SpaceFace) -> FaceOccupancy:
        key = (space_id, face)
        if key not in self._slots:
            self._slots[key] = FaceOccupancy()
        return self._slots[key]

    def can_place(self, space_id: str, face: SpaceFace, board: Any) -> bool:
        slot = self._slot(space_id, face)
        if face == SpaceFace.LEFT and _is_left_side_panel(board):
            return slot.is_free() or _slot_left_face_only_left_side_stack(slot)
        if face == SpaceFace.RIGHT and _is_right_side_panel(board):
            return slot.is_free() or _slot_right_face_only_right_side_stack(slot)
        return slot.is_free()

    def occupy(self, space_id: str, face: SpaceFace, board: Any) -> bool:
        if not self.can_place(space_id, face, board):
            return False
        self._slot(space_id, face).occupy(board)
        setattr(board, "bound_space_face", face)
        md = getattr(board, "metadata", None)
        if not isinstance(md, dict):
            md = {}
            setattr(board, "metadata", md)
        md["space_face"] = face.name
        return True

    def release(self, space_id: str, face: SpaceFace, board: Any) -> None:
        slot = self._slot(space_id, face)
        if board in slot.boards:
            slot.boards.remove(board)
        if len(slot.boards) == 0:
            slot.state = FaceState.FREE
        if board is not None:
            md = getattr(board, "metadata", None)
            if isinstance(md, dict):
                md.pop("space_face", None)
            if hasattr(board, "bound_space_face"):
                try:
                    delattr(board, "bound_space_face")
                except Exception:
                    pass

    def release_for_panel(self, board: Any) -> None:
        sid = getattr(board, "space_id", None)
        if not sid:
            return
        face = getattr(board, "bound_space_face", None)
        if face is None:
            md = getattr(board, "metadata", None)
            if isinstance(md, dict) and md.get("space_face"):
                name = str(md["space_face"]).upper()
                try:
                    face = SpaceFace[name]
                except KeyError:
                    face = space_face_for_anchor_panel(board)
        if isinstance(face, SpaceFace):
            self.release(str(sid), face, board)

    def is_face_occupied(self, space_id: str, face: SpaceFace) -> bool:
        slot = self._slot(space_id, face)
        if slot.is_free():
            return False
        if face == SpaceFace.LEFT:
            return not _slot_left_face_only_left_side_stack(slot)
        if face == SpaceFace.RIGHT:
            return not _slot_right_face_only_right_side_stack(slot)
        return True

    def reset(self) -> None:
        self._slots.clear()

    def force_occupy(self, space_id: str, face: SpaceFace, board: Any) -> None:
        slot = self._slot(space_id, face)
        slot.clear()
        slot.occupy(board)
        setattr(board, "bound_space_face", face)
        md = getattr(board, "metadata", None)
        if not isinstance(md, dict):
            md = {}
            setattr(board, "metadata", md)
        md["space_face"] = face.name

    def _try_register_anchor_panel(self, panel: Any, fallback_space_id: str) -> None:
        from ..constants.enums import PlacementMode
        from ..panel.anchor_placement import placement_mode_effective
        from ..panel.panel_models import Panel

        if not isinstance(panel, Panel):
            return
        if placement_mode_effective(panel) != PlacementMode.ANCHOR_FIXED:
            return
        face = space_face_for_anchor_panel(panel)
        if face is None:
            return
        psid = str(getattr(panel, "space_id", None) or fallback_space_id)
        slot = self._slot(psid, face)
        if face == SpaceFace.LEFT and _is_left_side_panel(panel):
            if panel in slot.boards:
                return
            slot.occupy(panel)
            setattr(panel, "bound_space_face", face)
            md = getattr(panel, "metadata", None)
            if not isinstance(md, dict):
                md = {}
                setattr(panel, "metadata", md)
            md["space_face"] = face.name
            return
        if face == SpaceFace.RIGHT and _is_right_side_panel(panel):
            if panel in slot.boards:
                return
            slot.occupy(panel)
            setattr(panel, "bound_space_face", face)
            md = getattr(panel, "metadata", None)
            if not isinstance(md, dict):
                md = {}
                setattr(panel, "metadata", md)
            md["space_face"] = face.name
            return
        if not slot.is_free():
            return
        self.force_occupy(psid, face, panel)

    def rebuild_from_root(self, root: Any) -> None:
        """``reset`` 后按 DFS 扫描 ``panel_groups`` / ``panels`` 重建占用。"""
        from .tree import walk_dfs

        self.reset()
        if root is None:
            return
        for node in walk_dfs(root):
            sid = str(node.id)
            for grp in getattr(node, "panel_groups", None) or []:
                for p in getattr(grp, "panels", None) or []:
                    self._try_register_anchor_panel(p, sid)
            for p in getattr(node, "panels", None) or []:
                self._try_register_anchor_panel(p, sid)
