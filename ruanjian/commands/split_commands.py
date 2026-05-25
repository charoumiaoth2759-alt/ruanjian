# -*- coding: utf-8 -*-
"""
空间分割命令占位。

后续与 core.space.splitter 等衔接后，在此注册 split_vertical 等命令名；
处理函数须返回 ``CommandResult``，不得依赖 Qt。
"""

from __future__ import annotations

from .command_types import CommandHandler


def register_handlers() -> dict[str, CommandHandler]:
    """兼容期无处理器。"""
    return {}
