# -*- coding: utf-8 -*-
"""柜体设计：可撤销编辑命令（命令模式）。

所有进入撤销栈的模型修改均实现 ``execute`` / ``undo``，由
``commands.undo_stack.UndoStack``（``push`` 内先 ``execute`` 再入栈）统一调度；
UI 侧通过 ``CabinetEditEnvironment`` 注入快照与 ``CommandDispatcher.dispatch``，
避免命令类依赖具体 Qt 控件。

**禁止**在 UI 事件中直接调用 ``space.add_board``、``boards.append``、
``split_space``、``remove_board`` 等；模型变更只能发生在 ``UndoableCommand.execute`` /
``undo``（或经 ``CommandDispatcher`` 的 handler）内。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from commands.command_result import CommandResult
from commands.undo_stack import UndoableCommand


@dataclass
class CabinetModelSnapshot:
    """柜体项目可恢复快照（根空间深拷贝 + 外形尺寸）。"""

    root_space: object | None
    cabinet_width: float
    cabinet_height: float
    cabinet_depth: float
    name: str


class CabinetEditEnvironment:
    """注入快照、派发与同步回调，供具体 ``CabinetEditCommand`` 使用。"""

    def __init__(
        self,
        *,
        capture_snapshot: Callable[[], CabinetModelSnapshot],
        apply_snapshot: Callable[[CabinetModelSnapshot], None],
        dispatch: Callable[[str, Any | None], CommandResult],
        is_undo_restoring: Callable[[], bool],
        get_project: Callable[[], Any],
        sync_after_total_size_changed: Callable[[], None],
    ) -> None:
        self._capture = capture_snapshot
        self._apply = apply_snapshot
        self._dispatch = dispatch
        self._is_restoring = is_undo_restoring
        self._get_project = get_project
        self._sync_total = sync_after_total_size_changed

    def capture_snapshot(self) -> CabinetModelSnapshot:
        return self._capture()

    def apply_snapshot(self, snap: CabinetModelSnapshot) -> None:
        self._apply(snap)

    def dispatch(self, command_name: str, payload: Any | None = None) -> CommandResult:
        return self._dispatch(command_name, payload)

    def is_undo_restoring(self) -> bool:
        return self._is_restoring()

    def get_project(self) -> Any:
        return self._get_project()

    def sync_after_total_size_changed(self) -> None:
        self._sync_total()


class CabinetEditCommand(UndoableCommand):
    """柜体模型修改命令：语义化别名，与 ``UndoableCommand`` 相同。"""


class DispatchCabinetEditCommand(CabinetEditCommand):
    """通过 ``CommandDispatcher`` 执行的一条命名命令；撤销时恢复执行前整包快照。"""

    def __init__(
        self,
        env: CabinetEditEnvironment,
        command_name: str,
        payload: Any | None = None,
    ) -> None:
        self._env = env
        self._command_name = command_name
        self._payload = payload
        self._before = env.capture_snapshot()
        self.last_dispatch_result: CommandResult | None = None

    def __repr__(self) -> str:
        return f"<DispatchCabinetEditCommand {self._command_name!r}>"

    def execute(self) -> bool:
        if self._env.is_undo_restoring():
            self.last_dispatch_result = CommandResult(False, {"skipped": True}, [])
            return False
        result = self._env.dispatch(self._command_name, self._payload)
        self.last_dispatch_result = result
        return bool(result.success)

    def undo(self) -> None:
        self._env.apply_snapshot(self._before)


class ChangeCabinetProjectDimsCommand(CabinetEditCommand):
    """总尺寸 / 名称：``execute`` 写入 ``project`` 并同步根空间；``undo`` 恢复快照。"""

    def __init__(
        self,
        env: CabinetEditEnvironment,
        before: CabinetModelSnapshot,
        *,
        name: str,
        cabinet_width: float,
        cabinet_height: float,
        cabinet_depth: float,
    ) -> None:
        self._env = env
        self._before = before
        self._name = name
        self._cabinet_width = cabinet_width
        self._cabinet_height = cabinet_height
        self._cabinet_depth = cabinet_depth

    def execute(self) -> bool:
        if self._env.is_undo_restoring():
            return False
        proj = self._env.get_project()
        if proj is None:
            return False
        if hasattr(proj, "name"):
            setattr(proj, "name", self._name)
        if hasattr(proj, "cabinet_width"):
            setattr(proj, "cabinet_width", self._cabinet_width)
        if hasattr(proj, "cabinet_height"):
            setattr(proj, "cabinet_height", self._cabinet_height)
        if hasattr(proj, "cabinet_depth"):
            setattr(proj, "cabinet_depth", self._cabinet_depth)
        self._env.sync_after_total_size_changed()
        return True

    def undo(self) -> None:
        self._env.apply_snapshot(self._before)


__all__ = [
    "CabinetEditCommand",
    "CabinetEditEnvironment",
    "CabinetModelSnapshot",
    "ChangeCabinetProjectDimsCommand",
    "DispatchCabinetEditCommand",
]
