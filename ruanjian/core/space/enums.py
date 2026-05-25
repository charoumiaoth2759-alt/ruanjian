# -*- coding: utf-8 -*-
"""
空间树相关枚举。

``SplitDirection`` 的**规范语义**为世界坐标轴上的子空间划分：

- ``SPLIT_X``：沿 X 轴分段（子节点 ``width`` / ``x`` 变化）
- ``SPLIT_Y``：沿 Y 轴分段（子节点 ``height`` / ``y`` 变化）
- ``SPLIT_Z``：沿 Z 轴分段（子节点 ``depth`` / ``z`` 变化）

历史名 ``HORIZONTAL`` / ``VERTICAL`` / ``DEPTH`` 仍保留在枚举中以便反序列化
与旧数据兼容，但**已废弃**，新代码不得再写入；请使用 ``SPLIT_*``。
其中 ``VERTICAL`` 曾混用于「X 向左右切」与「Y 向上下堆叠」，已拆清为
``SPLIT_X`` 与 ``SPLIT_Y``。
"""

from __future__ import annotations

from enum import Enum


class SpaceType(Enum):

    ROOT = "root"

    NORMAL = "normal"

    DRAWER = "drawer"

    HANGING = "hanging"

    SHELF = "shelf"

    DOOR = "door"


class SpaceState(Enum):
    """空间在拾取 / 放置语义下的离散状态（不得仅用 ``is_leaf`` 推断）。"""

    FREE = "free"           # 可参与放置决策的终端容积
    OCCUPIED = "occupied"   # 已挂载板件或标记占用
    SPLIT = "split"         # 已产生子节点，容积被细分


class SplitDirection(Enum):
    """子节点沿哪一世界轴紧排切分（规范值 + 废弃别名）。"""

    NONE = "none"

    SPLIT_X = "split_x"
    SPLIT_Y = "split_y"
    SPLIT_Z = "split_z"

    # --- deprecated: 保留值以兼容旧持久化 / 旧调用，新代码请改用 SPLIT_* ---
    HORIZONTAL = "horizontal"  # deprecated → 语义同 SPLIT_X
    VERTICAL = "vertical"  # deprecated → 语义同 SPLIT_Y（勿再表示 X 向切分）
    DEPTH = "depth"  # deprecated → 语义同 SPLIT_Z


def is_split_along_x(d: SplitDirection) -> bool:
    """是否为沿 X 轴切分（含废弃别名 ``HORIZONTAL``）。"""
    return d is SplitDirection.SPLIT_X or d is SplitDirection.HORIZONTAL


def is_split_along_y(d: SplitDirection) -> bool:
    """是否为沿 Y 轴切分（含废弃别名 ``VERTICAL``）。"""
    return d is SplitDirection.SPLIT_Y or d is SplitDirection.VERTICAL


def is_split_along_z(d: SplitDirection) -> bool:
    """是否为沿 Z 轴切分（含废弃别名 ``DEPTH``）。"""
    return d is SplitDirection.SPLIT_Z or d is SplitDirection.DEPTH


__all__ = [
    "SpaceType",
    "SpaceState",
    "SplitDirection",
    "is_split_along_x",
    "is_split_along_y",
    "is_split_along_z",
]
