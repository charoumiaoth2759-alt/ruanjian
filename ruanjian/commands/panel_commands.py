# -*- coding: utf-8 -*-
"""
板件相关命令：经 ``core.panel`` 修改 Space / 挂载板件，不直接 import Qt。

``handle_add_left_panel``：仅 **程序化** ``CommandDispatcher.dispatch("add_left_panel")`` 兼容；
有 ``ctx["cabinet_interaction_manager"]`` 时委托统一链路，否则 ``CommandFactory`` + 单次 ``execute``。

**用户交互**（UI / 快捷键 / 悬停拾取 / 参数空间工具）必须经
``CabinetDesignView`` → ``CabinetInteractionManager.submit_add_left_panel``，禁止直连本 handler。
"""

from __future__ import annotations

from typing import Any

from core.debug_flags import DEBUG_VIEW3D
from core.events.event_types import BuiltinEventTopics
from core.panel import cabinet_panel_tree_cmd as _pcmd

from .command_result import CommandResult
from .command_types import CommandHandler


def _invoke(cmd_label: str, fn, ctx: dict[str, Any], payload: Any) -> CommandResult:
    try:
        fn(ctx, payload)
        return CommandResult(True, {"handler": cmd_label}, [])
    except Exception as e:
        return CommandResult(False, {"handler": cmd_label, "error": str(e)}, [])


def handle_add_left_panel(ctx: dict[str, Any], payload: Any = None) -> CommandResult:
    """程序化入口：优先走 InteractionManager → CommandFactory → UndoStack。"""
    if DEBUG_VIEW3D:
        print("[Command] handle_add_left_panel ENTER (programmatic)")

    mgr = ctx.get("cabinet_interaction_manager")
    if mgr is not None:
        from ui.interaction.cabinet_interaction_sources import CabinetInteractionSource

        return mgr.submit_add_left_panel(
            payload,
            source=CabinetInteractionSource.INTERNAL_LEGACY_DISPATCH,
        )

    stack = ctx.get("cabinet_undo_stack")
    from commands.command_factory import CommandFactory

    try:
        cmd = CommandFactory.create_add_panel_command(ctx, payload)
    except (ValueError, RuntimeError) as e:
        return CommandResult(
            False,
            {"handler": "handle_add_left_panel", "error": str(e)},
            [],
        )

    if stack is not None:
        if stack.push(cmd):
            return cmd.last_result or CommandResult(
                True,
                {
                    "handler": "handle_add_left_panel",
                    "suppress_default_space_changed": True,
                },
                [],
            )
        return cmd.last_result or CommandResult(
            False,
            {"handler": "handle_add_left_panel", "error": "command failed"},
            [],
        )

    if cmd.execute():
        return CommandResult(
            True,
            {
                "handler": "handle_add_left_panel",
                "suppress_default_space_changed": True,
            },
            [],
        )
    return cmd.last_result or CommandResult(
        False,
        {"handler": "handle_add_left_panel", "error": "command failed"},
        [],
    )


def add_right_panel(ctx: dict[str, Any], payload: Any = None) -> CommandResult:
    mgr = ctx.get("cabinet_interaction_manager")
    if mgr is not None:
        from ui.interaction.cabinet_interaction_sources import CabinetInteractionSource

        return mgr.submit_add_right_panel(
            payload,
            source=CabinetInteractionSource.INTERNAL_LEGACY_DISPATCH,
        )
    return _invoke("add_right_panel", _pcmd.add_right_panel, ctx, payload)


def add_top_panel(ctx: dict[str, Any], payload: Any = None) -> CommandResult:
    return _invoke("add_top_panel", _pcmd.add_top_panel, ctx, payload)


def add_bottom_panel(ctx: dict[str, Any], payload: Any = None) -> CommandResult:
    return _invoke("add_bottom_panel", _pcmd.add_bottom_panel, ctx, payload)


def add_back_panel(ctx: dict[str, Any], payload: Any = None) -> CommandResult:
    return _invoke("add_back_panel", _pcmd.add_back_panel, ctx, payload)


def add_door(ctx: dict[str, Any], payload: Any = None) -> CommandResult:
    return _invoke("add_door", _pcmd.add_door, ctx, payload)


def add_drawer(ctx: dict[str, Any], payload: Any = None) -> CommandResult:
    return _invoke("add_drawer", _pcmd.add_drawer, ctx, payload)


def apply_add_or_modify(ctx: dict[str, Any], payload: Any = None) -> CommandResult:
    return _invoke("apply_add_or_modify", _pcmd.apply_add_or_modify, ctx, payload)


def save_to_library(ctx: dict[str, Any], payload: Any = None) -> CommandResult:
    return _invoke("save_to_library", _pcmd.save_to_library, ctx, payload)


def finish_cabinet_design(ctx: dict[str, Any], payload: Any = None) -> CommandResult:
    return _invoke("finish_cabinet_design", _pcmd.finish_cabinet_design, ctx, payload)


def register_handlers() -> dict[str, CommandHandler]:
    """注册 command_name → 处理函数。"""
    return {
        "add_left_panel": handle_add_left_panel,
        "add_right_panel": add_right_panel,
        "add_top_panel": add_top_panel,
        "add_bottom_panel": add_bottom_panel,
        "add_back_panel": add_back_panel,
        "add_door": add_door,
        "add_drawer": add_drawer,
        "apply_add_or_modify": apply_add_or_modify,
        "save_to_library": save_to_library,
        "finish_cabinet_design": finish_cabinet_design,
    }
