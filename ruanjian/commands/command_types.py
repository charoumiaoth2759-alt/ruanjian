# -*- coding: utf-8 -*-
"""commands 层共享类型别名（无 Qt）。"""

from __future__ import annotations

from typing import Any, Callable

from .command_result import CommandResult

CommandHandler = Callable[[dict[str, Any], Any], CommandResult | None]

__all__ = ["CommandHandler", "CommandResult"]
