# -*- coding: utf-8 -*-
"""
添加侧板（当前实现：左侧板 ``LEFT_SIDE``）的可撤销命令。

- 构造：``AddBoardCommand(target_space, created_panel, ctx)`` —— **禁止**无参或仅 ``ctx`` 构造；
  ``created_panel`` 由 ``CommandFactory`` 经 ``build_left_side_panel`` 在入栈前创建。
- ``execute``：``mount_left_side_panel`` → 求解 → ``SOLVE_COMPLETED``。
- ``undo``：``detach_left_side_panel`` 同一 ``Panel`` 引用（禁止 ``deepcopy``）。
"""

from __future__ import annotations

from typing import Any

from commands.cabinet_event_bridge import run_attach_solver_and_publish
from commands.command_result import CommandResult
from core.events.event_bus import publish as bus_publish
from core.events.event_types import BuiltinEventTopics, Event
from core.panel.cabinet_space_panel_cmd import (
    detach_right_side_panel,
    detach_left_side_panel,
    mount_right_side_panel,
    mount_left_side_panel,
)
from core.panel.panel_models import Panel
from core.constants.enums import PanelRole
from core.space.space_models import Space

from .base_command import BaseCommand


def _publish_solve_completed_incremental_add(panel: Panel) -> None:
    bus_publish(
        Event(
            BuiltinEventTopics.SOLVE_COMPLETED,
            {"incremental_add_panels": [panel]},
            immediate=True,
        )
    )


def _publish_solve_completed_incremental_remove(panel_id: str) -> None:
    bus_publish(
        Event(
            BuiltinEventTopics.SOLVE_COMPLETED,
            {"incremental_remove_panel_ids": [str(panel_id)]},
            immediate=True,
        )
    )


def _panel_mounted_on_space(panel: Panel, space: Space) -> bool:
    groups = getattr(space, "panel_groups", None) or []
    for g in groups:
        pls = getattr(g, "panels", None) or []
        if panel in pls:
            return True
    return False


class AddBoardCommand(BaseCommand):
    """
    在目标 ``Space`` 上挂载已构造的左侧板；撤销时卸下 **同一** ``Panel`` 实例。
    """

    def __init__(
        self,
        target_space: Space,
        created_panel: Panel,
        ctx: dict[str, Any],
    ) -> None:
        if not isinstance(target_space, Space):
            raise TypeError("AddBoardCommand requires a Space target_space")
        if not isinstance(created_panel, Panel):
            raise TypeError("AddBoardCommand requires a Panel created_panel")
        self._ctx = ctx
        self._space = target_space
        self._panel = created_panel
        self.last_result: CommandResult | None = None

    def __repr__(self) -> str:
        sid = getattr(self._space, "id", None)
        pid = getattr(self._panel, "id", None)
        return f"<AddBoardCommand space={sid!r} panel={pid!r}>"

    def execute(self) -> bool:
        space = self._space
        panel = self._panel
        try:
            from core.space.cabinet_ops_lock import (
                reset_cabinet_ops_visual_to_locked_after_left_panel_added,
            )

            if not _panel_mounted_on_space(panel, space):
                if panel.role == PanelRole.RIGHT_SIDE:
                    mount_right_side_panel(space, panel)
                else:
                    mount_left_side_panel(space, panel)
            reset_cabinet_ops_visual_to_locked_after_left_panel_added(space)
            run_attach_solver_and_publish(self._ctx, space)
            _publish_solve_completed_incremental_add(panel)
        except Exception as e:
            self.last_result = CommandResult(
                False, {"handler": "AddBoardCommand", "error": str(e)}, []
            )
            return False
        self.last_result = CommandResult(
            True,
            {"handler": "AddBoardCommand", "suppress_default_space_changed": True},
            [],
        )
        return True

    def undo(self) -> None:
        if self._panel is None or self._space is None:
            return
        if self._panel.role == PanelRole.RIGHT_SIDE:
            detach_right_side_panel(self._panel, self._space)
        else:
            detach_left_side_panel(self._panel, self._space)
        run_attach_solver_and_publish(self._ctx, self._space)
        _publish_solve_completed_incremental_remove(self._panel.id)


__all__ = ["AddBoardCommand"]
