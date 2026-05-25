# -*- coding: utf-8 -*-
"""柜体编辑命令基类。"""

from __future__ import annotations

from commands.undo_stack import UndoableCommand


class BaseCommand(UndoableCommand):
    """与 ``commands.undo_stack.UndoStack.push`` 配合的柜体编辑命令基类。"""
