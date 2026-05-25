from __future__ import annotations

from typing import Any

from commands.command_factory import CommandFactory
from commands.command_result import CommandResult
from core.constants.enums import PanelRole
from core.space.cabinet_ops_lock import (
    CABINET_OPS_LOCKED_HINT,
    cabinet_command_should_respect_ops_lock,
    ctx_cabinet_ops_locked,
)

from .cabinet_interaction_sources import CabinetInteractionSource
from .interaction_log import log_command, log_mode
from .interaction_mode import InteractionMode

# 提交加板前同步主 3D / 参数空间 ``ToolMode`` 的来源（不改变 Hover 拾取语义）。
_SOURCES_SYNC_ADD_PANEL_TOOL_MODE = frozenset(
    {
        CabinetInteractionSource.UI_COMPONENT_LIBRARY_SLOT,
        CabinetInteractionSource.UI_COMPONENT_LIBRARY_ICON,
        CabinetInteractionSource.MAIN_3D_SHORTCUT,
        CabinetInteractionSource.TOOLBAR,
    }
)


class CabinetInteractionManager:
    """持有一个 ``CabinetDesignView``（或等价宿主），读取其 ``_cmd_dispatcher`` / ``_cabinet_undo_stack``。"""

    def __init__(self, host: Any) -> None:
        self._host = host

    def _apply_interaction_mode_step(self, source: CabinetInteractionSource) -> None:
        """
        流水线第二步：``InteractionMode``。

        - 组件库 / 快捷键 / 工具条：``set_interaction_mode(ADD_PANEL)``（同步 ``ToolMode``）。
        - 主 3D 悬停单击 / 参数空间工具：仅 ``[MODE] ADD_PANEL``，不切换当前工具（保持 SELECT 拾取等逻辑）。
        """
        if source in _SOURCES_SYNC_ADD_PANEL_TOOL_MODE:
            fn = getattr(self._host, "set_interaction_mode", None)
            if callable(fn):
                fn(InteractionMode.ADD_PANEL)
                return
        log_mode("ADD_PANEL")

    def submit_add_left_panel(
        self,
        payload: Any | None = None,
        *,
        source: CabinetInteractionSource,
    ) -> CommandResult:
        """
        唯一交互侧「添加左侧板」入口。

        InteractionMode → CommandFactory.create_add_panel_command
        → UndoStack.push → AddBoardCommand.execute → 增量 Scene。
        """
        host = self._host
        dispatcher = getattr(host, "_cmd_dispatcher", None)
        stack = getattr(host, "_cabinet_undo_stack", None)
        if dispatcher is None:
            return CommandResult(False, {"error": "no dispatcher"}, [])
        if stack is None:
            return CommandResult(False, {"error": "cabinet_undo_pipeline_inactive"}, [])

        ctx = dispatcher.context
        if cabinet_command_should_respect_ops_lock("add_left_panel") and ctx_cabinet_ops_locked(ctx):
            return CommandResult(False, {"error": CABINET_OPS_LOCKED_HINT}, [])

        self._apply_interaction_mode_step(source)
        try:
            cmd = CommandFactory.create_add_panel_command(ctx, payload)
        except (ValueError, RuntimeError) as e:
            return CommandResult(False, {"error": str(e)}, [])
        log_command("AddBoardCommand")
        if stack.push(cmd):
            return cmd.last_result or CommandResult(True, {}, [])
        return cmd.last_result or CommandResult(False, {"error": "command failed"}, [])

    def submit_add_right_panel(
        self,
        payload: Any | None = None,
        *,
        source: CabinetInteractionSource,
    ) -> CommandResult:
        host = self._host
        dispatcher = getattr(host, "_cmd_dispatcher", None)
        stack = getattr(host, "_cabinet_undo_stack", None)
        if dispatcher is None:
            return CommandResult(False, {"error": "no dispatcher"}, [])
        if stack is None:
            return CommandResult(False, {"error": "cabinet_undo_pipeline_inactive"}, [])

        ctx = dispatcher.context
        if cabinet_command_should_respect_ops_lock("add_right_panel") and ctx_cabinet_ops_locked(ctx):
            return CommandResult(False, {"error": CABINET_OPS_LOCKED_HINT}, [])

        self._apply_interaction_mode_step(source)
        try:
            cmd = CommandFactory.create_add_panel_command(ctx, payload, role=PanelRole.RIGHT_SIDE)
        except (ValueError, RuntimeError) as e:
            return CommandResult(False, {"error": str(e)}, [])
        log_command("AddBoardCommand")
        if stack.push(cmd):
            return cmd.last_result or CommandResult(True, {}, [])
        return cmd.last_result or CommandResult(False, {"error": "command failed"}, [])


__all__ = ["CabinetInteractionManager"]

            )

        ctx = dispatcher.context

        if cabinet_command_should_respect_ops_lock(
            "add_left_panel"
        ) and ctx_cabinet_ops_locked(ctx):
            return CommandResult(False, {"error": CABINET_OPS_LOCKED_HINT}, [])

        self._apply_interaction_mode_step(source)
        try:
            cmd = CommandFactory.create_add_panel_command(ctx, payload)
        except (ValueError, RuntimeError) as e:
            return CommandResult(False, {"error": str(e)}, [])
        log_command("AddBoardCommand")
        if stack.push(cmd):
            return cmd.last_result or CommandResult(True, {}, [])
        return cmd.last_result or CommandResult(
            False,
            {"error": "command failed"},
            [],
        )


__all__ = ["CabinetInteractionManager"]
