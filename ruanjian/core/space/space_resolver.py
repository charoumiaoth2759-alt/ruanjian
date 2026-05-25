# -*- coding: utf-8 -*-
"""
为板件在整棵 ``Space`` 树中挑选可放置叶节点（与 ``ConstraintEngine`` 配合）。

不修改 ``Space`` 结构；仅返回候选 ``Space`` 供一致性管理器绑定 ``space_id``。
"""

from __future__ import annotations

from typing import Any, TYPE_CHECKING

from .tree import iter_leaves, walk_dfs

if TYPE_CHECKING:
    from .constraint_engine import ConstraintEngine
    from .space_face_occupancy import FaceOccupancyManager
    from .space_models import Space


class SpaceResolver:
    """叶级空间解析：在合法叶节点中择优（优先保留原宿主、否则最小容积近似）。"""

    def __init__(
        self,
        constraint_engine: "ConstraintEngine",
        face_manager: "FaceOccupancyManager | None" = None,
    ) -> None:
        from .space_face_occupancy import get_face_occupancy_manager

        self._engine = constraint_engine
        self._faces = face_manager or get_face_occupancy_manager()

    def pick_best_space(self, root: "Space", panel: Any) -> "Space | None":
        """
        返回可放置 ``panel`` 的叶 ``Space``；若无则 ``None``。

        策略：
        - **锚定板**（``ANCHOR_FIXED``）：不因几何/约束剔除；优先保留 ``space_id`` 宿主；
          若宿主丢失，在 **该锚定面对应的叶** 中选 ``FaceOccupancyManager`` 仍空闲者；
          若该面在所有叶上均已占用则退回第一个叶（由上层标 ``BLOCKED``）。
        - 自动布局板：``space_id`` 仍合法且约束通过 → 保留；否则在叶节点中筛选约束通过者。
        """
        if root is None:
            return None

        from ..constants.enums import PlacementMode
        from ..panel.anchor_placement import placement_mode_effective
        from .space_face_occupancy import space_face_for_anchor_panel

        if placement_mode_effective(panel) == PlacementMode.ANCHOR_FIXED:
            smap = {s.id: s for s in walk_dfs(root)}
            sid = getattr(panel, "space_id", None)
            if sid and sid in smap:
                return smap[sid]
            needed = space_face_for_anchor_panel(panel)
            leaves = list(iter_leaves(root))
            if needed:
                free = [
                    L
                    for L in leaves
                    if not self._faces.is_face_occupied(str(L.id), needed)
                ]
                if free:
                    return min(free, key=_space_volume)
            if leaves:
                return leaves[0]
            return root

        preferred_id = getattr(panel, "space_id", None)
        if preferred_id:
            for leaf in iter_leaves(root):
                if leaf.id == preferred_id and self._engine.validate(leaf, panel):
                    return leaf

        candidates: list[Space] = [
            leaf for leaf in iter_leaves(root) if self._engine.validate(leaf, panel)
        ]
        if not candidates:
            return None
        vol_p = _panel_volume_hint(panel)
        feasible = [c for c in candidates if _space_volume(c) + 1e-6 >= vol_p]
        pool = feasible if feasible else candidates
        return min(pool, key=_space_volume)


def _space_volume(space: Any) -> float:
    return float(space.width) * float(space.height) * float(space.depth)


def _panel_volume_hint(panel: Any) -> float:
    sx = float(getattr(panel, "size_x", 0.0) or 0.0)
    sy = float(getattr(panel, "size_y", 0.0) or 0.0)
    sz = float(getattr(panel, "size_z", 0.0) or 0.0)
    if sx > 1e-6 and sy > 1e-6 and sz > 1e-6:
        return sx * sy * sz
    w = float(getattr(panel, "width", 0.0) or 0.0)
    h = float(getattr(panel, "height", 0.0) or 0.0)
    t = float(getattr(panel, "thickness", 0.0) or 0.0)
    return max(w * h * t, 1.0)
