# -*- coding: utf-8 -*-
"""空间 + 板件约束校验（供拾取管线 ``validate`` 阶段使用）。"""

from __future__ import annotations

from typing import Any, Callable

from ..constants.tolerance import DIMENSION_TOLERANCE
from ..panel.panel_bounds import panel_extents_world_xyz, panel_world_aabb
from .constraints import SpaceConstraint
from .space_models import Space


def _panel_world_aabb_inside_space(space: Space, board: Any) -> bool:
    """
    板件世界轴 AABB 是否完全落在当前 ``Space`` 的 AABB 内。

    旁板等 ``VERTICAL_X`` 语义下 ``panel.width`` 沿世界 Z，不得再与 ``space.width`` 直接比较。
    """
    ex, ey, ez = panel_extents_world_xyz(board)
    if ex <= 1e-9 or ey <= 1e-9 or ez <= 1e-9:
        return False
    tol = float(DIMENSION_TOLERANCE)
    px0, px1, py0, py1, pz0, pz1 = panel_world_aabb(board)
    sx0 = float(space.x)
    sy0 = float(space.y)
    sz0 = float(space.z)
    sx1 = sx0 + float(space.width)
    sy1 = sy0 + float(space.height)
    sz1 = sz0 + float(space.depth)
    return (
        px0 >= sx0 - tol
        and py0 >= sy0 - tol
        and pz0 >= sz0 - tol
        and px1 <= sx1 + tol
        and py1 <= sy1 + tol
        and pz1 <= sz1 + tol
    )


class ConstraintEngine:
    """
    对候选 ``Space`` 做约束校验；``board`` 为 ``None`` 时仅校验空间自身边界。
    可注入额外 ``(space, board) -> bool`` 规则。
    """

    def __init__(
        self,
        extra_rules: list[Callable[[Space, Any | None], bool]] | None = None,
    ) -> None:
        self._extra_rules = list(extra_rules or [])

    def validate(self, space: Space, board: Any | None) -> bool:
        if not _space_within_self_constraints(space):
            return False
        if board is not None:
            if not _panel_world_aabb_inside_space(space, board):
                return False
        for rule in self._extra_rules:
            if not rule(space, board):
                return False
        return True


def _space_within_self_constraints(space: Space) -> bool:
    c: SpaceConstraint = space.constraints
    w, h, d = float(space.width), float(space.height), float(space.depth)
    if w < float(c.min_width) or w > float(c.max_width):
        return False
    if h < float(c.min_height) or h > float(c.max_height):
        return False
    if d < float(c.min_depth) or d > float(c.max_depth):
        return False
    return True
