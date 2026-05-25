# -*- coding: utf-8 -*-
"""
与 UI 触发相关、但不依赖 Qt 控件的命令（经 Dispatcher 走统一命令流）。

说明：
    - **唯一**允许写入 ``project.root_space`` 的入口：``SET_ROOT_SPACE``（及别名
      ``cabinet_total_size_updated``）。UI 不得 ``setattr(project, "root_space", ...)``。
    - ``material_changed``：不写 Space 树；由 Dispatcher 追加 ``SPACE_CHANGED`` 触发求解链。
"""

from __future__ import annotations

from typing import Any

from core.dirty.dirty_flags import DirtyFlag
from core.events.event_types import BuiltinEventTopics
from core.space.placement_state import BLOCKED, set_placement_state
from core.space.root_factory import make_root_cabinet_space
from core.space.space_consistency_manager import (
    SpaceConsistencyManager,
    collect_panels_from_space_tree,
)
from core.space.space_models import Space

from .cabinet_solve_coalesce import CABINET_SOLVE_COALESCE_KEY
from .command_result import CommandResult
from .command_types import CommandHandler

# 柜体总尺寸任一边小于该值（mm）时，树上板件统一标为 BLOCKED，3D 以红色提示（仅尺寸语义，不改其它逻辑）
_MIN_CABINET_OUTLINE_MM = 100.0


def material_changed(ctx: dict[str, Any], payload: Any = None) -> CommandResult:
    """材料菜单点击：不写 Space 树。"""
    _ = (ctx, payload)
    return CommandResult(True, {"handler": "material_changed"}, [])


def _apply_root_dimensions_in_place(root: Space, name: str, w: float, h: float, d: float) -> None:
    """仅更新根节点外形尺寸与名称，保留 ``id`` / ``children`` / ``panel_groups`` 子树。"""
    name = (name or "").strip()
    if name:
        root.name = name
    root.width = float(w)
    root.height = float(h)
    root.depth = float(d)
    root.dirty_flag = DirtyFlag.DIRTY


def _set_root_space_from_project(ctx: dict[str, Any], handler_name: str) -> CommandResult:
    """
    根据 ``project`` 上的柜体宽高深更新 ``project.root_space``。

    若已有根 ``Space``（无父节点），则**就地改尺寸**并走 ``SpaceConsistencyManager``；
    否则新建根节点。不在此处清空子树或板件列表。

    返回一条 **immediate** 的 ``SPACE_CHANGED``，避免首帧去抖延迟；并抑制 Dispatcher
    默认追加的第二条 ``SPACE_CHANGED``。
    """
    project = ctx.get("project")
    if project is None:
        return CommandResult(False, {"handler": handler_name, "error": "no project"}, [])
    w = float(getattr(project, "cabinet_width", 2400))
    h = float(getattr(project, "cabinet_height", 2200))
    d = float(getattr(project, "cabinet_depth", 600))
    nm = getattr(project, "name", None) or ""

    existing = getattr(project, "root_space", None)
    if isinstance(existing, Space) and existing.parent is None:
        _apply_root_dimensions_in_place(existing, nm, w, h, d)
        root = existing
    else:
        root = make_root_cabinet_space(nm, w, h, d)

    try:
        setattr(project, "root_space", root)
    except Exception as e:
        return CommandResult(False, {"handler": handler_name, "error": str(e)}, [])

    boards = collect_panels_from_space_tree(root)
    SpaceConsistencyManager().on_root_resized(root, boards)

    if w < _MIN_CABINET_OUTLINE_MM or h < _MIN_CABINET_OUTLINE_MM or d < _MIN_CABINET_OUTLINE_MM:
        for p in collect_panels_from_space_tree(root):
            set_placement_state(p, BLOCKED)

    return CommandResult(
        True,
        {
            "handler": handler_name,
            "root_space_id": getattr(root, "id", None),
            "suppress_default_space_changed": True,
        },
        [
            # 须先于 SPACE_CHANGED：后者会同步触发 solve → SOLVE_COMPLETED，
            # 若 CABINET_CREATED 在后则会用旧 root 覆盖 View3D。
            {
                "type": BuiltinEventTopics.CABINET_CREATED,
                "payload": {"space": root},
                "immediate": True,
            },
            {
                "type": BuiltinEventTopics.SPACE_CHANGED,
                "payload": {"command": handler_name},
                "coalesce_key": CABINET_SOLVE_COALESCE_KEY,
                "immediate": True,
            },
        ],
    )


def set_root_space(ctx: dict[str, Any], payload: Any = None) -> CommandResult:
    """写入 ``project.root_space`` 的规范命令名（UI 应仅 ``dispatch("SET_ROOT_SPACE")``）。"""
    _ = payload
    return _set_root_space_from_project(ctx, "SET_ROOT_SPACE")


def cabinet_total_size_updated(ctx: dict[str, Any], payload: Any = None) -> CommandResult:
    """总尺寸对话框已写回 ``project`` 尺寸字段后：与 ``SET_ROOT_SPACE`` 同逻辑（兼容旧命令名）。"""
    _ = payload
    return _set_root_space_from_project(ctx, "cabinet_total_size_updated")


def register_handlers() -> dict[str, CommandHandler]:
    """注册 UI 语义命令。"""
    return {
        "SET_ROOT_SPACE": set_root_space,
        "material_changed": material_changed,
        "cabinet_total_size_updated": cabinet_total_size_updated,
    }
