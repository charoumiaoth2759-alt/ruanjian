# -*- coding: utf-8 -*-
"""通用撤销栈：命令模式下的 ``UndoStack.push`` / ``undo_last``。

约定（柜体与其它编辑场景共用）
--------------------------------
**禁止**在 UI 事件（按钮 ``clicked``、菜单 ``triggered``、3D 拾取等）中直接调用
``space.add_board``、``space.boards.append``、``split_space``、``remove_board`` 等
修改领域模型；UI **只能** 构造实现 ``UndoableCommand`` 的命令对象，再::

    undo_stack.push(cmd)

``push`` 内部 **原子地** 完成 ``command.execute()`` 与入栈，避免出现：

- ``execute`` 成功却未 ``append``；
- 已 ``append`` 却从未 ``execute``；
- UI 在 ``push`` 之外自行 ``execute``（重复执行）。

若 ``execute()`` 返回 ``False``（未改模型 / 用户取消 / 校验失败），**不入栈**，
避免 ``undo`` 误撤销空操作或错误状态。

``UndoStack`` 与 Qt 解耦，仅依赖 ``UndoableCommand`` 协议。

调试：``push`` / ``execute`` / ``undo_last`` 打印 ``[UNDO] push``、``[UNDO] execute``、
``[UNDO] undo``（无冒号后缀）；环境变量 ``ZHIGUI_UNDO_LOG=0`` 可关闭。
"""

from __future__ import annotations

import os
from abc import ABC, abstractmethod
from collections import deque
from typing import Any, Deque, Optional

_UNDO_LOG = os.environ.get("ZHIGUI_UNDO_LOG", "1").strip() not in ("0", "false", "False", "no", "NO")


def _undo_log(tag: str) -> None:
    if _UNDO_LOG:
        print(tag, flush=True)


class UndoableCommand(ABC):
    """可入撤销栈的命令：由 ``UndoStack.push`` 调用 ``execute``，由 ``undo_last`` 调用 ``undo``。"""

    @abstractmethod
    def execute(self) -> bool:
        """执行本命令对应的模型修改；成功且应可撤销时返回 True。"""

    @abstractmethod
    def undo(self) -> None:
        """撤销 ``execute`` 已提交的变更。"""


class UndoStack:
    """后进先出撤销栈；可选 ``maxlen`` 时与 ``collections.deque`` 一致丢弃最旧项。"""

    def __init__(self, maxlen: Optional[int] = None) -> None:
        self._stack: Deque[UndoableCommand] = deque(maxlen=maxlen) if maxlen is not None else deque()

    def push(self, command: UndoableCommand) -> bool:
        """先 ``command.execute()``，**仅当**返回真时 ``append`` 到栈内。"""
        _undo_log("[UNDO] push")
        _undo_log("[UNDO] execute")
        if not command.execute():
            return False
        self._stack.append(command)
        return True

    def undo_last(self) -> bool:
        """弹栈并调用 ``undo()``；栈空时返回 False。"""
        if not self._stack:
            return False
        command = self._stack.pop()
        _undo_log("[UNDO] undo")
        command.undo()
        return True

    def clear(self) -> None:
        self._stack.clear()

    def __len__(self) -> int:
        return len(self._stack)


__all__ = ["UndoableCommand", "UndoStack"]
