# -*- coding: utf-8 -*-
"""
空间拾取：可评分的决策管线（候选 → 几何 → 约束 → 得分 → 唯一 ``Space``）。

UI 层只提供世界射线或世界点坐标；不得在此写 Qt / OpenGL。
"""

from __future__ import annotations

import math
from typing import Any

from .constraint_engine import ConstraintEngine
from .enums import SpaceState
from .space_metrics import SpaceMetrics
from .space_models import Space
from .space_state import infer_space_state
from .tree import iter_leaves

from ..panel.panel_placement import left_side_stack_offset_x


def _leaf_eligible_for_panel_pick(sp: Space) -> bool:
    """
    左面 / 点选叠板：已挂板件的叶节点为 ``OCCUPIED``，但仍需能再次拾取（如多块左侧板）。

    排除 ``SPLIT``（非叶）；``iter_leaves`` 通常不会产出 ``SPLIT``，此处防御性判断。
    """
    st = infer_space_state(sp)
    return st in (SpaceState.FREE, SpaceState.OCCUPIED)


def world_point_in_space_aabb(
    space: Space, wx: float, wy: float, wz: float, *, eps: float = 1e-6
) -> bool:
    """世界坐标点是否落在 ``space`` 轴对齐包围盒内（含边界）。"""
    x0, y0, z0 = float(space.x), float(space.y), float(space.z)
    x1 = x0 + float(space.width)
    y1 = y0 + float(space.height)
    z1 = z0 + float(space.depth)
    return (
        (x0 - eps <= wx <= x1 + eps)
        and (y0 - eps <= wy <= y1 + eps)
        and (z0 - eps <= wz <= z1 + eps)
    )


def ray_intersect_left_stack_outer_face_mm(
    space: Space,
    ox: float,
    oy: float,
    oz: float,
    dx: float,
    dy: float,
    dz: float,
    *,
    margin_mm: float = 120.0,
) -> float | None:
    """
    射线与「当前左侧板堆叠后的外左 YZ 面」相交。

    平面 ``x = space.x + left_side_stack_offset_x(space)``，与下一块左侧板落位面一致；
    叠板后仍可从该面拾取 / 悬停（绿色 ghost）。
    """
    px = float(space.x) + float(left_side_stack_offset_x(space))
    if abs(dx) < 1e-9:
        return None
    t = (px - ox) / dx
    if t < 0.0 or t > 1.0e7:
        return None
    py = oy + dy * t
    pz = oz + dz * t
    y0, y1 = float(space.y), float(space.y + space.height)
    z0, z1 = float(space.z), float(space.z + space.depth)
    m = float(margin_mm)
    if (y0 - m <= py <= y1 + m) and (z0 - m <= pz <= z1 + m):
        return float(t)
    return None


def ray_intersect_space_left_face_mm(
    space: Space,
    ox: float,
    oy: float,
    oz: float,
    dx: float,
    dy: float,
    dz: float,
    *,
    margin_mm: float = 120.0,
) -> float | None:
    """
    射线与 ``space`` 左侧面 ``x = space.x`` 的 YZ 矩形（带 margin）相交时返回参数 ``t``（mm 意义下沿方向长度），否则 ``None``。
    """
    px = float(space.x)
    if abs(dx) < 1e-9:
        return None
    t = (px - ox) / dx
    if t < 0.0 or t > 1.0e7:
        return None
    py = oy + dy * t
    pz = oz + dz * t
    y0, y1 = float(space.y), float(space.y + space.height)
    z0, z1 = float(space.z), float(space.z + space.depth)
    m = float(margin_mm)
    if (y0 - m <= py <= y1 + m) and (z0 - m <= pz <= z1 + m):
        return float(t)
    return None


class SpacePicker:
    """空间拾取：单结果 ``Space | None``。"""

    @staticmethod
    def pick_leaf_for_left_face_ray(
        root: Space,
        origin: tuple[float, float, float],
        direction: tuple[float, float, float],
        *,
        constraint_engine: ConstraintEngine,
        board_context: Any | None = None,
        margin_mm: float = 120.0,
    ) -> Space | None:
        """
        以左侧面射线拾取 **单一** 叶节点空间。

        阶段：``iter_leaves`` → ``SpaceState``（可叠板的 ``FREE``/``OCCUPIED`` 叶）→ 左面几何 → ``validate`` → 得分 → 最优。
        """
        ox, oy, oz = (float(origin[0]), float(origin[1]), float(origin[2]))
        dx, dy, dz = (float(direction[0]), float(direction[1]), float(direction[2]))
        ln = math.sqrt(dx * dx + dy * dy + dz * dz)
        if ln < 1e-12:
            return None
        dx, dy, dz = dx / ln, dy / ln, dz / ln

        # 1) candidate gathering
        candidates = tuple(iter_leaves(root))

        # 2) geometry + 3) constraint + 4) scoring（合并遍历，短路约束失败）
        best: Space | None = None
        best_score = float("-inf")

        for sp in candidates:
            if not _leaf_eligible_for_panel_pick(sp):
                continue
            t_hit = ray_intersect_left_stack_outer_face_mm(
                sp, ox, oy, oz, dx, dy, dz, margin_mm=margin_mm
            )
            if t_hit is None:
                continue
            if not constraint_engine.validate(sp, board_context):
                continue
            vol = float(sp.width) * float(sp.height) * float(sp.depth)
            score = SpaceMetrics.score_left_face_ray(sp, t_hit, vol)
            if score > best_score:
                best_score = score
                best = sp

        return best

    @staticmethod
    def pick_leaf_for_world_point(
        root: Space,
        wx: float,
        wy: float,
        wz: float,
        *,
        constraint_engine: ConstraintEngine,
        board_context: Any | None = None,
    ) -> Space | None:
        """
        以世界点落在 AABB 内拾取 **单一** 叶节点（用于 UI 点选 / 屏幕反投影点）。

        阶段：``iter_leaves`` → ``SpaceState``（``FREE``/已挂板 ``OCCUPIED`` 仍可点）→ 点入盒 → ``validate`` → 得分 → 最优。
        """
        wx, wy, wz = float(wx), float(wy), float(wz)
        candidates = tuple(iter_leaves(root))
        best: Space | None = None
        best_score = float("-inf")

        for sp in candidates:
            if not _leaf_eligible_for_panel_pick(sp):
                continue
            if not world_point_in_space_aabb(sp, wx, wy, wz):
                continue
            if not constraint_engine.validate(sp, board_context):
                continue
            score = SpaceMetrics.score_world_point(sp, wx, wy, wz)
            if score > best_score:
                best_score = score
                best = sp

        return best
