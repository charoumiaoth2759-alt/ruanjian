# -*- coding: utf-8 -*-
"""可撤销命令层（兼容期已实现分发骨架）。

分层约定见项目根下 ``docs/ARCHITECTURE.md``。摘要：

    UI(Qt) → CommandDispatcher → commands(编排, 无 Qt) → core(领域, 无 Qt)
         → solver(Space→SolveResult) → event_bus(纯 Python) → UI(仅渲染)
"""

from .command_dispatcher import CommandDispatcher
from .command_factory import CommandFactory
from .command_result import CommandResult
from .undo_stack import UndoStack, UndoableCommand

__all__ = [
    "CommandDispatcher",
    "CommandFactory",
    "CommandResult",
    "UndoStack",
    "UndoableCommand",
]
