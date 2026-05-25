# -*- coding: utf-8 -*-
"""
柜体可撤销命令工厂（commands 层，无 Qt）。

职责：构造 ``UndoableCommand`` 实例；**不** ``execute``、**不** ``UndoStack.push``。
左侧板：入栈前 ``build_left_side_panel``，再 ``AddBoardCommand(target_space, panel, ctx)``。
门 / 抽屉：仍为 ``DispatchCabinetEditCommand`` 快照撤销（与对话框确认路径一致）。
"""

from __future__ import annotations

from typing import Any

from commands.cabinet.add_board_command import AddBoardCommand
from commands.cabinet_edit_command import (
    CabinetEditEnvironment,
    DispatchCabinetEditCommand,
)
from core.panel.cabinet_space_panel_cmd import build_left_side_panel
from core.space.space_models import Space


def _thickness_mm(payload: Any) -> float:
    if not isinstance(payload, dict):
        return 18.0
    raw = payload.get("thickness")
    if raw is None:
        return 18.0
    try:
        t = float(raw)
    except (TypeError, ValueError):
        return 18.0
    return max(6.0, min(t, 80.0))


def resolve_attachment_space(ctx: dict[str, Any]) -> Space | None:
    """与 ``handle_add_left_panel`` / 原 ``AddBoardCommand`` 一致：``current_space`` → ``root_space``。"""
    sel_mgr = ctx.get("selection")
    if sel_mgr:
        space = getattr(sel_mgr, "current_space", None)
        if isinstance(space, Space):
            return space
    rs = ctx.get("root_space")
    if isinstance(rs, Space):
        return rs
    return None


class CommandFactory:
    """可撤销柜体编辑命令的统一创建入口。"""

    @staticmethod
    def create_add_panel_command(
        ctx: dict[str, Any], payload: Any | None = None
    ) -> AddBoardCommand:
        """
        添加左侧板：解析目标空间 → ``build_left_side_panel`` → ``AddBoardCommand(space, panel, ctx)``。

        禁止在 UI / InteractionManager 中直接 ``AddBoardCommand(...)``。
        """
        space = resolve_attachment_space(ctx)
        if space is None:
            raise ValueError("no target space for add panel")
        panel = build_left_side_panel(space, thickness=_thickness_mm(payload))
        return AddBoardCommand(space, panel, ctx)

    @staticmethod
    def create_add_left_panel_command(
        ctx: dict[str, Any], payload: Any | None = None
    ) -> AddBoardCommand:
        """与 ``create_add_panel_command`` 相同（兼容旧调用名）。"""
        return CommandFactory.create_add_panel_command(ctx, payload)

    @staticmethod
    def create_add_door_command(
        env: CabinetEditEnvironment,
        payload: Any | None = None,
    ) -> DispatchCabinetEditCommand:
        """开门：经 Dispatcher ``add_door``，撤销为项目快照还原。"""
        return DispatchCabinetEditCommand(env, "add_door", payload)

    @staticmethod
    def create_add_drawer_command(
        env: CabinetEditEnvironment,
        payload: Any | None = None,
    ) -> DispatchCabinetEditCommand:
        """抽屉：经 Dispatcher ``add_drawer``，撤销为项目快照还原。"""
        return DispatchCabinetEditCommand(env, "add_drawer", payload)


__all__ = ["CommandFactory", "resolve_attachment_space"]
