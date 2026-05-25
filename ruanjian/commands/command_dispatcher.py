# -*- coding: utf-8 -*-
"""
命令分发器：UI → ``dispatch(...)`` → 已注册 handler → ``CommandResult``
→ 由本模块将 ``result.events`` 转为 ``core.events`` 投递。

说明：
    - commands 子模块只返回 ``CommandResult``，不直接 ``publish``、不 import Qt。
    - 默认在 handler 执行后追加一条 ``SPACE_CHANGED``（与旧行为一致），
      除非 ``result.data.get("suppress_default_space_changed")`` 为真，
      或 ``result.events`` 已包含 ``SPACE_CHANGED``。
    - **禁止静默失败**：handler 返回 ``success=False`` 时
      在 ``dispatch`` 内统一 ``print`` 到 stdout，便于排查。
    - ``success=True`` 且 ``data.skipped`` / ``data.unhandled`` 的诊断行由
      ``core.debug_flags.DEBUG_VIEW3D`` 控制（正常模式不刷屏）。
"""

from __future__ import annotations

from typing import Any

from core.debug_flags import DEBUG_VIEW3D
from core.events.event_bus import publish as bus_publish
from core.events.event_types import Event
from .cabinet_solve_coalesce import CABINET_SOLVE_COALESCE_KEY

from . import opening_commands
from . import panel_commands
from . import split_commands
from . import ui_commands
from .command_result import CommandResult
from .command_types import CommandHandler


def _announce_command_outcome(command_name: str, result: CommandResult) -> None:
    """
    约定：命令不得静默跳过或失败。

    对 ``success=False`` 打印一行到 stdout；``skipped`` / ``unhandled`` 仅在
    ``DEBUG_VIEW3D`` 为真时打印。
    """
    data = result.data if isinstance(result.data, dict) else {}
    if not result.success:
        print(f"[Command] {command_name} FAILED:", data.get("error", data))
        return
    if data.get("skipped"):
        if DEBUG_VIEW3D:
            print(f"[Command] {command_name} skipped:", data.get("reason", data))
        return
    if data.get("unhandled"):
        if DEBUG_VIEW3D:
            print(f"[Command] {command_name} UNHANDLED (no handler registered)")


def _merge_command_payload(payload: Any, kwargs: dict[str, Any]) -> Any:
    """
    合并 `payload` 与 `**kwargs`，供 `dispatch(command, **kwargs)` 兼容旧 `dispatch(name, obj)`。

    规则：
        - 无 kwargs：原样返回 payload；
        - payload 为 dict：与 kwargs 浅合并（kwargs 覆盖同名键）；
        - payload 为 None：若 kwargs 非空则返回 kwargs，否则 None；
        - 其他类型且带 kwargs：包成 {"_legacy_payload": payload, **kwargs}。
    """
    if not kwargs:
        return payload
    if isinstance(payload, dict):
        merged: dict[str, Any] = {**payload, **kwargs}
        return merged
    if payload is None:
        return kwargs if kwargs else None
    return {"_legacy_payload": payload, **kwargs}


def _dict_to_event(spec: dict[str, Any]) -> Event:
    name = spec.get("type")
    if not isinstance(name, str):
        raise TypeError("event spec requires str 'type'")
    raw_pl = spec.get("payload")
    if raw_pl is None:
        payload: dict[str, Any] = {}
    elif isinstance(raw_pl, dict):
        payload = dict(raw_pl)
    else:
        payload = {"_payload": raw_pl}
    return Event(
        name,
        payload,
        coalesce_key=spec.get("coalesce_key") if isinstance(spec.get("coalesce_key"), str) else None,
        immediate=bool(spec.get("immediate", False)),
    )


def _default_space_changed_event(command_name: str) -> dict[str, Any]:
    return {
        "type": "SPACE_CHANGED",
        "payload": {"command": command_name},
        "coalesce_key": CABINET_SOLVE_COALESCE_KEY,
    }


class CommandDispatcher:
    """根据 command_name 调用已注册处理函数，投递 ``CommandResult.events``。"""

    def __init__(self, context: dict[str, Any] | None = None) -> None:
        self._context: dict[str, Any] = dict(context) if context else {}
        self._handlers: dict[str, CommandHandler] = {}
        self._handlers.update(panel_commands.register_handlers())
        self._handlers.update(ui_commands.register_handlers())
        self._handlers.update(opening_commands.register_handlers())
        self._handlers.update(split_commands.register_handlers())

    @property
    def context(self) -> dict[str, Any]:
        """供事件总线 `get_ctx()` 读取当前命令上下文（只读引用，勿替换整个 dict）。"""
        return self._context

    def dispatch(
        self, command_name: str, payload: Any | None = None, **kwargs: Any
    ) -> CommandResult:
        """
        执行命令并返回 ``CommandResult``；将 ``events`` 中规格依次 ``publish`` 到总线。

        兼容：
            - `dispatch(name, payload_obj)` 旧式第二位置参数；
            - `dispatch(name, **kwargs)` 新式关键字参数（与 payload dict 合并）。
        """
        if not command_name:
            res = CommandResult(True, {"skipped": True, "reason": "empty_command"}, [])
            _announce_command_outcome("<empty>", res)
            return res

        merged = _merge_command_payload(payload, kwargs)
        fn = self._handlers.get(command_name)

        result: CommandResult
        if fn is not None:
            raw = fn(self._context, merged)
            if not isinstance(raw, CommandResult):
                if DEBUG_VIEW3D:
                    print(
                        f"[Command] {command_name} WARN: handler did not return CommandResult; "
                        "coerced to success",
                    )
            result = raw if isinstance(raw, CommandResult) else CommandResult(True, {}, [])
        else:
            result = CommandResult(True, {"unhandled": True}, [])

        _announce_command_outcome(command_name, result)

        events = list(result.events)
        if not result.data.get("suppress_default_space_changed"):
            if not any(
                isinstance(e, dict) and e.get("type") == "SPACE_CHANGED" for e in events
            ):
                events.append(_default_space_changed_event(command_name))

        for spec in events:
            bus_publish(_dict_to_event(spec))

        return CommandResult(
            result.success,
            {**result.data, "command": command_name},
            events,
        )
