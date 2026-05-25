# -*- coding: utf-8 -*-
"""
柜体 UI 与事件总线 / 求解之间的桥接（仅供 view 通过 ``commands`` 包调用）。

说明：
    - ``view/cabinet_view/*`` 不得直接 ``import core.*``；
    - 视图同步（``canvas`` / ``refresh_view``）与总线 ``publish`` 仅在本模块发生；
    - **solver**（``solver.cabinet_solver.solve(space_tree)``）仅返回 ``SolveResult``（含 ``events`` 建议项），
      不触碰 Qt、不 ``publish``；由本模块根据 ``result.events`` 调用 ``publish``。
"""

from __future__ import annotations

from typing import Any, Callable

from .cabinet_solve_coalesce import CABINET_SOLVE_COALESCE_KEY

# ``SOLVE_COMPLETED`` 载荷：为真时才允许主 3D / 参数空间 ``rebuild all panels``。
FULL_PANEL_REBUILD_KEY = "full_panel_rebuild"
CABINET_DIMENSIONS_SPIN_SOURCE = "cabinet_dimensions_spin"

__all__ = [
    "CABINET_DIMENSIONS_SPIN_SOURCE",
    "CABINET_SOLVE_COALESCE_KEY",
    "FULL_PANEL_REBUILD_KEY",
    "get_event_bus_instance",
    "emit_dimension_spins_panel_changed",
    "emit_assembler_selection_changed",
    "register_cabinet_mode_event_subscribers",
    "write_solve_result_to_project_display_cache",
    "run_attach_solver_and_publish",
]


def get_event_bus_instance() -> Any:
    from core.events.event_bus import get_event_bus

    return get_event_bus()


def emit_dimension_spins_panel_changed() -> None:
    """尺寸 Spin 连续拖动：投递 ``PANEL_CHANGED``（与命令链相同的合并键）。"""
    from core.events.event_bus import publish as bus_publish
    from core.events.event_types import BuiltinEventTopics, Event

    bus_publish(
        Event(
            BuiltinEventTopics.PANEL_CHANGED,
            {"source": "cabinet_dimensions_spin"},
            coalesce_key=CABINET_SOLVE_COALESCE_KEY,
        )
    )


def emit_assembler_selection_changed(index: int, path: str) -> None:
    """组件库图标选中：投递 ``SELECTION_CHANGED``。"""
    from core.events.event_bus import publish as bus_publish
    from core.events.event_types import BuiltinEventTopics, Event

    bus_publish(
        Event(
            BuiltinEventTopics.SELECTION_CHANGED,
            {"kind": "assembler", "index": index, "path": path},
        )
    )


def write_solve_result_to_project_display_cache(
    ctx: dict[str, Any], result: Any, *, success: bool | None = None
) -> None:
    """
    将一次 ``SolveResult`` 写入 ``project._cabinet_display_*``，与总线求解链末尾逻辑一致。

    供命令在**已本地调用** ``solve`` 后同步更新缓存；展示由 ``SOLVE_COMPLETED`` 载荷
    （``incremental_*`` 或 ``full_panel_rebuild``）决定，避免误触发全量 rebuild。
    """
    project = ctx.get("project")
    if project is None:
        return
    ok = result.success if success is None else success
    _pl = list(getattr(result, "panel_list", None) or [])
    _pgs = list(getattr(result, "panel_groups", None) or [])
    setattr(
        project,
        "_cabinet_display_panels",
        _pl if (ok or _pl) else [],
    )
    setattr(
        project,
        "_cabinet_display_panel_groups",
        _pgs if (ok or _pgs) else [],
    )


def run_attach_solver_and_publish(ctx: dict[str, Any], attachment_space: Any) -> Any:
    """
    在目标 ``Space`` 上变更挂载板件后：对根 ``solve_cabinet`` 并写入 ``project`` 展示缓存。

    **不**在此处 ``publish`` 总线事件：经 ``CommandDispatcher`` 调用的 handler 应把
    ``SOLVE_COMPLETED`` 放在 ``CommandResult.events``；经 ``UndoStack.push(AddBoardCommand)``
    的路径由 ``AddBoardCommand`` 在 ``execute`` / ``undo`` 末尾自行投递 ``SOLVE_COMPLETED``。
    """
    from core.solver.cabinet_solver import solve_cabinet

    proj = ctx.get("project")
    root_space = getattr(proj, "root_space", None) if proj is not None else None
    if root_space is None:
        root_space = ctx.get("root_space")
    panel_groups = list(getattr(attachment_space, "panel_groups", []) or [])
    result = solve_cabinet(root_space=root_space, panel_groups=panel_groups)
    ctx["last_solve_result"] = result
    write_solve_result_to_project_display_cache(ctx, result)
    return result


def _should_full_panel_rebuild(trigger_ev: Any, solve_result: Any) -> bool:
    """
    仅下列情况允许 ``rebuild all panels``：

    - 柜体尺寸变化（``PANEL_CHANGED`` 且 ``source=cabinet_dimensions_spin``）
    - 根布局重算（``SolveResult.new_space_tree``）
    - 全量求解（``SPACE_CHANGED`` 触发的 ``solve(root)`` 链）
    """
    from core.events.event_types import BuiltinEventTopics

    if solve_result is not None and getattr(solve_result, "new_space_tree", None) is not None:
        return True
    pl = getattr(trigger_ev, "payload", None)
    if not isinstance(pl, dict):
        pl = {}
    if pl.get("source") == CABINET_DIMENSIONS_SPIN_SOURCE:
        return True
    if pl.get(FULL_PANEL_REBUILD_KEY):
        return True
    topic = getattr(trigger_ev, "type", None)
    if topic == BuiltinEventTopics.SPACE_CHANGED:
        return True
    return False


def _apply_incremental_panel_display(
    ctx: dict[str, Any],
    add_panels: list[Any] | None,
    remove_panel_ids: list[str] | None,
) -> None:
    """``AddBoardCommand`` 等：仅追加/移除板件 GL，不触发全量 ``rebuild panels``。"""
    canvas = ctx.get("canvas")
    project = ctx.get("project")
    root = getattr(project, "root_space", None) if project is not None else None

    view = getattr(canvas, "_3d_view", None) if canvas is not None else None
    if view is not None:
        rm = [str(x) for x in (remove_panel_ids or []) if x]
        if rm and hasattr(view, "remove_display_panels_by_ids"):
            view.remove_display_panels_by_ids(rm)
        add = list(add_panels or [])
        if add and hasattr(view, "append_display_panels"):
            view.append_display_panels(add)

    if canvas is None or project is None or root is None:
        return
    mw = canvas.window()
    if mw is None:
        return
    from ui.cabinet_space.param_space_gl_view import ParamSpaceGLView

    rm = [str(x) for x in (remove_panel_ids or []) if x]
    add = list(add_panels or [])
    for pv in mw.findChildren(ParamSpaceGLView):
        r = getattr(pv, "_root", None)
        if r is None or id(r) != id(root):
            continue
        if rm:
            fn_rm = getattr(pv, "remove_panel_visuals_by_ids", None)
            if callable(fn_rm):
                fn_rm(rm)
        if add:
            fn_add = getattr(pv, "append_panel_visuals", None)
            if callable(fn_add):
                fn_add(add)
        if rm or add:
            fn_refresh = getattr(pv, "_refresh_space_box_colors", None)
            if callable(fn_refresh):
                fn_refresh()
            fn_sync = getattr(pv, "_sync_add_left_preview", None)
            if callable(fn_sync):
                fn_sync()
            gl = getattr(pv, "_gl", None)
            if gl is not None:
                gl.update()


def _full_rebuild_param_space_panel_views(ctx: dict[str, Any]) -> None:
    """参数空间：全量 ``rebuild_panels``（仅 ``full_panel_rebuild`` 路径）。"""
    canvas = ctx.get("canvas")
    project = ctx.get("project")
    if canvas is None or project is None:
        return
    root = getattr(project, "root_space", None)
    groups = getattr(project, "_cabinet_display_panel_groups", None)
    mw = canvas.window()
    if mw is None:
        return
    from ui.cabinet_space.param_space_gl_view import ParamSpaceGLView

    pgs = list(groups) if groups else None
    for pv in mw.findChildren(ParamSpaceGLView):
        r = getattr(pv, "_root", None)
        if r is None or root is None or id(r) != id(root):
            continue
        fn = getattr(pv, "apply_full_panel_rebuild_display", None)
        if callable(fn):
            fn(pgs)


def _full_rebuild_panels_in_views(ctx: dict[str, Any]) -> None:
    """从 project 全量重建板件展示（仅柜体尺寸 / 根布局 / Full Solve）。"""
    project = ctx.get("project")
    canvas = ctx.get("canvas")
    panels = getattr(project, "_cabinet_display_panels", None) if project is not None else None
    groups = getattr(project, "_cabinet_display_panel_groups", None) if project is not None else None
    view = getattr(canvas, "_3d_view", None) if canvas is not None else None
    root = getattr(project, "root_space", None) if project is not None else None
    if view is not None and hasattr(view, "set_cabinet_space"):
        if root is None:
            view.set_cabinet_space(None)
        else:
            view.set_cabinet_space(root, refit_camera=False)
    if view is not None and hasattr(view, "set_display_panel_groups"):
        view.set_display_panel_groups(list(groups) if groups else [])
    if view is not None and hasattr(view, "rebuild_all_display_panels"):
        view.rebuild_all_display_panels(list(panels) if panels else [])
    elif view is not None and hasattr(view, "set_display_panels"):
        view.set_display_panels(list(panels) if panels else [], full_rebuild=True)
    _full_rebuild_param_space_panel_views(ctx)


def _refresh_view_from_ctx(ctx: dict[str, Any]) -> None:
    """调用上下文中 ``refresh_view`` 闭包（commands 层编排，非 solver）。"""
    refresh = ctx.get("refresh_view")
    if callable(refresh):
        refresh()


def register_cabinet_mode_event_subscribers(
    bus: Any,
    get_ctx: Callable[[], dict[str, Any] | None],
    prop_panel: Any | None = None,
) -> list[Callable[[], None]]:
    """
    为柜体设计模式注册事件订阅；返回一组 ``unsub()``，供 ``exit()`` 时调用。

    参数：
        bus: ``core.events.event_bus.EventBus`` 实例（使用 Any 避免循环类型导入）。
        get_ctx: 返回当前 CommandDispatcher 上下文的回调。
        prop_panel: 右侧 ``CabinetPropertyPanel``，用于 ``SELECTION_CHANGED``。
    """
    from core.events.event_bus import publish as bus_publish
    from core.events.event_types import BuiltinEventTopics, Event

    from solver.cabinet_solver import solve

    unsubs: list[Callable[[], None]] = []

    def _on_solve_trigger(trigger_ev: Any) -> None:
        ctx = get_ctx()
        if not ctx:
            return
        project = ctx.get("project")
        root = getattr(project, "root_space", None) if project is not None else None
        result = solve(root)
        if project is not None:
            _pl = list(result.panel_list)
            _pgs = list(getattr(result, "panel_groups", []) or [])
            # 求解失败时若仍有可展示板件（例如仅来自 Space.panels），仍写入供 3D 刷新
            setattr(
                project,
                "_cabinet_display_panels",
                _pl if (result.success or _pl) else [],
            )
            setattr(
                project,
                "_cabinet_display_panel_groups",
                _pgs if (result.success or _pgs) else [],
            )
        if result.new_space_tree is not None and project is not None:
            setattr(project, "root_space", result.new_space_tree)
        full_rebuild = _should_full_panel_rebuild(trigger_ev, result)
        for ev in result.events:
            pl: dict[str, Any] = {}
            if ev == BuiltinEventTopics.SOLVE_COMPLETED:
                pl = {
                    "ctx": ctx,
                    FULL_PANEL_REBUILD_KEY: full_rebuild,
                }
            bus_publish(Event(ev, pl, immediate=True))

    def _on_solve_completed(ev: Any) -> None:
        ctx = get_ctx()
        if not ctx:
            return
        payload = getattr(ev, "payload", None)
        if not isinstance(payload, dict):
            payload = {}
        add_panels = payload.get("incremental_add_panels")
        remove_ids = payload.get("incremental_remove_panel_ids")
        if add_panels or remove_ids:
            _apply_incremental_panel_display(ctx, add_panels, remove_ids)
            _refresh_view_from_ctx(ctx)
            return
        if payload.get(FULL_PANEL_REBUILD_KEY):
            _full_rebuild_panels_in_views(ctx)
        _refresh_view_from_ctx(ctx)

    def _on_selection_changed(ev: Any) -> None:
        if prop_panel is None:
            return
        fn = getattr(prop_panel, "apply_selection_from_event", None)
        if callable(fn):
            fn(ev)

    unsubs.append(bus.subscribe(BuiltinEventTopics.SPACE_CHANGED, _on_solve_trigger))
    unsubs.append(bus.subscribe(BuiltinEventTopics.PANEL_CHANGED, _on_solve_trigger))
    unsubs.append(bus.subscribe(BuiltinEventTopics.MATERIAL_CHANGED, _on_solve_trigger))
    unsubs.append(bus.subscribe(BuiltinEventTopics.SOLVE_COMPLETED, _on_solve_completed))
    unsubs.append(bus.subscribe(BuiltinEventTopics.SELECTION_CHANGED, _on_selection_changed))

    return unsubs
