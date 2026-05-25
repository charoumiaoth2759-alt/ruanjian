from __future__ import annotations
from enum import Enum, auto


class DirtyFlag(Enum):
    """
    节点脏标记三态。

    CLEAN       —— 已求解，数据可信，渲染层可直接读取
    DIRTY       —— 数据已过期，等待 incremental_solver 处理
    PROPAGATING —— dirty_tracker 正在向下游传播标记中，
                   防止传播过程中被其他事件误判为 CLEAN
    """
    CLEAN       = auto()
    DIRTY       = auto()
    PROPAGATING = auto()
