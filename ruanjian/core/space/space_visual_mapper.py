# -*- coding: utf-8 -*-
"""
空间盒 **仅展示用** 颜色映射（不参与业务判断）。

正确数据流（单向）::

    ConstraintEngine.validate / Resolver
        → PlacementState（ALLOWED / BLOCKED / UNKNOWN）
    + infer_space_state(space) → enums.SpaceState（FREE / OCCUPIED / SPLIT）
    + UI 悬停布尔（仅视觉）
        → 本模块映射为 RGBA
        → GL / Qt 绘制

状态与颜色（线性 RGBA 0~1；颜色不参与逻辑）::

    ALLOWED   可放板件     透明青 (135,240,240)，α 153/255；棱线纯青 (0,255,255)
    BLOCKED   不能放       柔和红：面片 (255,80,80)、α 90/255；棱线略深红
    OCCUPIED  已放板件     科技蓝：面片 (70,140,255)、α 60/255；棱线蓝色
    HOVER     鼠标悬停     高亮透明青 (168,255,255)、α 200/255；棱线略深青

❌ 禁止根据颜色反推「能否放置」；业务层不得 ``if color == blue: allow()``。
"""

from __future__ import annotations

from .enums import SpaceState as PickSpaceState
from .space_state import PlacementState

# --- 基准色（线性 RGB 0~1，含 alpha）-----------------------------------------

# ALLOWED：可放板件 → 透明青 (135, 240, 240, 153)
_RGBA_ALLOWED_FACE: tuple[float, float, float, float] = (
    135 / 255.0,
    240 / 255.0,
    240 / 255.0,
    153 / 255.0,
)
_RGBA_ALLOWED_EDGE: tuple[float, float, float, float] = (0.0, 1.0, 1.0, 1.0)

# BLOCKED：不能放 → 柔和红 (255,80,80)，α 90/255；棱线略深红
_RGBA_BLOCKED_FACE: tuple[float, float, float, float] = (
    255 / 255.0,
    80 / 255.0,
    80 / 255.0,
    90 / 255.0,
)
_RGBA_BLOCKED_EDGE: tuple[float, float, float, float] = (
    200 / 255.0,
    45 / 255.0,
    50 / 255.0,
    1.0,
)

# OCCUPIED：已放板件 → 科技蓝 (70,140,255)，α 60/255；棱线蓝色
_RGBA_OCCUPIED_FACE: tuple[float, float, float, float] = (
    70 / 255.0,
    140 / 255.0,
    255 / 255.0,
    60 / 255.0,
)
_RGBA_OCCUPIED_EDGE: tuple[float, float, float, float] = (
    35 / 255.0,
    100 / 255.0,
    230 / 255.0,
    1.0,
)

# SPLIT 父节点（有 children）：弱透明青灰，不参与放置
_RGBA_SPLIT_FACE: tuple[float, float, float, float] = (0.50, 0.78, 0.80, 0.32)
_RGBA_SPLIT_EDGE: tuple[float, float, float, float] = (0.35, 0.70, 0.74, 0.88)

# UNKNOWN + FREE：与 ALLOWED 同色透明青（历史默认）
_RGBA_DEFAULT_FACE: tuple[float, float, float, float] = (
    135 / 255.0,
    240 / 255.0,
    240 / 255.0,
    153 / 255.0,
)
_RGBA_DEFAULT_EDGE: tuple[float, float, float, float] = (0.0, 1.0, 1.0, 1.0)

# HOVER：悬停 → 高亮透明青（略提亮、略提高不透明度）
_RGBA_HOVER_FACE: tuple[float, float, float, float] = (
    168 / 255.0,
    1.0,
    1.0,
    200 / 255.0,
)
_RGBA_HOVER_EDGE: tuple[float, float, float, float] = (0.15, 1.0, 1.0, 1.0)


def space_box_face_edge_rgba(
    pick_state: PickSpaceState,
    placement: PlacementState,
    *,
    hovered: bool = False,
    cabinet_ops_user_allow: bool | None = None,
) -> tuple[tuple[float, float, float, float], tuple[float, float, float, float]]:
    """
    由 **拾取语义结构状态** + **放置决策** + **悬停** 得到空间盒填充色与棱线色。

    优先级（仅影响颜色，非业务）::

        1. 悬停 → 高亮透明青
        2. 结构 SPLIT 父节点 → 弱透明青灰
        3. 结构 OCCUPIED 且未用户解锁 → 科技蓝 (70,140,255)，α 60/255，棱线蓝色
        4. 放置 BLOCKED → 柔和红 (255,80,80)，α 90/255
        5. 放置 ALLOWED → 透明青 (135,240,240,153)
        6. 其它（含 UNKNOWN）→ 与 ALLOWED 相同透明青

    ``cabinet_ops_user_allow``：结构仍为 OCCUPIED 但用户已单击切换为允许编辑时，
    跳过科技蓝，改由放置状态决定颜色（与 ALLOWED 语义一致）。
    """
    if hovered:
        return _RGBA_HOVER_FACE, _RGBA_HOVER_EDGE

    if pick_state is PickSpaceState.SPLIT:
        return _RGBA_SPLIT_FACE, _RGBA_SPLIT_EDGE
    if pick_state is PickSpaceState.OCCUPIED and cabinet_ops_user_allow is not True:
        return _RGBA_OCCUPIED_FACE, _RGBA_OCCUPIED_EDGE
    if placement is PlacementState.BLOCKED:
        return _RGBA_BLOCKED_FACE, _RGBA_BLOCKED_EDGE
    if placement is PlacementState.ALLOWED:
        return _RGBA_ALLOWED_FACE, _RGBA_ALLOWED_EDGE
    return _RGBA_DEFAULT_FACE, _RGBA_DEFAULT_EDGE


__all__ = [
    "space_box_face_edge_rgba",
]
