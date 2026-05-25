# -*- coding: utf-8 -*-
"""
命令返回值规范。

commands 层不得直接 ``publish`` 事件或操作 Qt；通过 ``events`` 描述需由
`CommandDispatcher` 代为投递到 `core.events` 总线的事件规格（纯 dict）。

约定：**禁止静默失败**——跳过、未实现或失败时须在 ``CommandResult.data`` 中标明
（``skipped`` / ``unhandled`` / ``error``），并由 ``CommandDispatcher`` 统一 ``print`` 可见输出。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class CommandResult:
    """单次命令执行结果（供 UI 经 ``CommandDispatcher.dispatch`` 读取）。"""

    success: bool = True
    data: dict[str, Any] = field(default_factory=dict)
    events: list[dict[str, Any]] = field(default_factory=list)


__all__ = ["CommandResult"]
