# -*- coding: utf-8 -*-
"""
从任意 Qt 控件向上解析宿主 ``CabinetDesignView``（MainWindow 挂在 ``_cabinet_design_view``）。

用于主 3D、参数空间预览等 **非** 柜子画布子树内的控件解析
``CabinetDesignView`` / ``CabinetInteractionManager``，
统一走 ``submit_add_left_panel_interaction``（InteractionMode→CommandFactory→UndoStack→增量 Scene），不改变各视图旋转/拾取/着色逻辑。
"""

from __future__ import annotations

from typing import Any

_MAX_PARENT_HOPS = 64


def resolve_cabinet_design_view(start: Any | None) -> Any | None:
    """
    :param start: 一般为 ``QWidget``（如 ``View3D``、``ParamSpaceGLView``）
    :return: 带 ``run_cabinet_dispatch_command`` 的 ``CabinetDesignView`` 实例，或 ``None``
    """
    if start is None:
        return None
    try:
        win = start.window()
    except Exception:
        win = None
    if win is not None:
        cv = getattr(win, "_cabinet_design_view", None)
        if cv is not None:
            return cv
    depth = 0
    cur: Any = start
    while cur is not None and depth < _MAX_PARENT_HOPS:
        cv = getattr(cur, "_cabinet_design_view", None)
        if cv is not None:
            return cv
        try:
            cur = cur.parentWidget()
        except Exception:
            break
        depth += 1
    return None


def resolve_cabinet_interaction_manager(start: Any | None) -> Any | None:
    """返回宿主上的 ``CabinetInteractionManager``，未初始化则 ``None``。"""
    cdv = resolve_cabinet_design_view(start)
    if cdv is None:
        return None
    return getattr(cdv, "cabinet_interaction_manager", None)


__all__ = [
    "resolve_cabinet_design_view",
    "resolve_cabinet_interaction_manager",
]
