# -*- coding: utf-8 -*-
"""
开口（门洞/窗洞等）命令占位。

后续与 core.opening 衔接后，在此注册 add_window_opening 等命令名；
处理函数须返回 ``CommandResult``，不得依赖 Qt。
"""

from __future__ import annotations

from .command_types import CommandHandler


def register_handlers() -> dict[str, CommandHandler]:
    """兼容期无处理器。"""
    return {}
