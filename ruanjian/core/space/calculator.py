from __future__ import annotations

from typing import Any

from .constraint_engine import ConstraintEngine
from .enums import SpaceState
from .space_models import Space
from .space_state import infer_space_state
from .tree import iter_leaves


# ==========================================================
# 1. 净可用尺寸（geometry）
# ==========================================================

def get_usable_width(
    space: Space,
    left_thickness: float,
    right_thickness: float,
) -> float:
    """
    扣除左右板厚后的内部净宽。

    示例：
        w = get_usable_width(space, left_thickness=18, right_thickness=18)
    """
    return space.width - left_thickness - right_thickness


def get_usable_height(
    space: Space,
    top_thickness: float,
    bottom_thickness: float,
) -> float:
    """扣除上下板厚后的内部净高。"""
    return space.height - top_thickness - bottom_thickness


def get_usable_depth(
    space: Space,
    back_thickness: float,
) -> float:
    """扣除背板厚度后的内部净深。"""
    return space.depth - back_thickness


# ==========================================================
# 2. SpaceState 查询
# ==========================================================

def get_free_leaf_spaces(root: Space) -> list[Space]:
    """
    返回树中所有 ``SpaceState.FREE`` 的叶节点（候选容积）。

    使用 ``infer_space_state``，**不**以 ``is_leaf`` 为唯一条件。
    """
    result: list[Space] = []
    for node in iter_leaves(root):
        if infer_space_state(node) is SpaceState.FREE:
            result.append(node)
    return result


def get_used_spaces(root: Space) -> list[Space]:
    """返回树中所有 ``SpaceState.OCCUPIED`` 的叶节点。"""
    result: list[Space] = []
    for node in iter_leaves(root):
        if infer_space_state(node) is SpaceState.OCCUPIED:
            result.append(node)
    return result


def get_space_utilization(root: Space) -> float:
    """
    返回 0.0–1.0 的空间利用率：used_volume / total_volume。

    - 分母为零时返回 0.0，避免 ZeroDivisionError。
    - volume = width × height × depth（三轴均存在时）；
      若模型只有二轴，则退化为面积比。

    示例：
        ratio = get_space_utilization(cabinet_root)
        print(f"利用率 {ratio:.1%}")
    """
    def volume(node: Space) -> float:
        w = getattr(node, "width", 0.0) or 0.0
        h = getattr(node, "height", 0.0) or 0.0
        d = getattr(node, "depth", 1.0) or 1.0  # 无深度字段时退化为面积
        return w * h * d

    used_vol = sum(volume(n) for n in get_used_spaces(root))
    total_vol = sum(volume(n) for n in iter_leaves(root))

    if total_vol == 0.0:
        return 0.0
    return used_vol / total_vol


# ==========================================================
# 3. Constraint-aware 放置检查
# ==========================================================

def can_place(
    space: Space,
    board: Any,
    constraint_engine: ConstraintEngine,
) -> bool:
    """
    判断 board 能否放入 space，同时满足 ConstraintEngine 中的所有约束。

    检查顺序（短路求值，越早失败越快）：
        1. ``infer_space_state(space)`` 必须为 ``SpaceState.FREE``
        2. board 尺寸不超过 space 的物理边界
        3. 经 constraint_engine 校验所有注册规则均通过

    参数：
        space             目标空间节点
        board             待放置的板件节点
        constraint_engine 已初始化的约束引擎实例

    返回：
        True  → 可以放置
        False → 任意条件不满足

    示例：
        if can_place(target_space, new_board, engine):
            placer.place(target_space, new_board)
    """
    # 1. 状态必须为 FREE（综合子节点 / 占用 / 板件，不单看 is_leaf）
    if infer_space_state(space) is not SpaceState.FREE:
        return False

    # 2. 物理尺寸检查
    board_w = getattr(board, "width", 0.0)
    board_h = getattr(board, "height", 0.0)
    board_d = getattr(board, "depth", 0.0)

    if board_w > space.width:
        return False
    if board_h > space.height:
        return False
    if board_d > space.depth:
        return False

    # 3. 约束引擎校验
    return constraint_engine.validate(space, board)