# -*- coding: utf-8 -*-
"""
板件相关命令在 `core/panel` 侧的聚合入口。

说明：
    - 满足「`commands.panel_commands` 只依赖 `core/panel`」的目录边界；
    - 树分割类操作由 ``core.cabinet.cabinet_space_actions`` 实现；
    - ``add_left_panel`` 等在 ``Space.panel_groups`` / ``Space.panels`` 上挂载板件，见 ``cabinet_space_panel_cmd``。
"""

from __future__ import annotations

from typing import Any

from core.cabinet import cabinet_space_actions as _ops


def add_left_panel(ctx: dict[str, Any], payload: Any = None) -> None:
    """左侧板：在目标 ``Space.panels`` 追加板件（非树分割）。"""
    from .cabinet_space_panel_cmd import add_left_panel as _attach_left

    _attach_left(ctx, payload)


def add_right_panel(ctx: dict[str, Any], payload: Any = None) -> None:
    """右侧板意图：根节点沿 X 垂直分割（右窄条）。"""
    _ops.apply_vertical_split_right_strip(ctx, payload)


def add_top_panel(ctx: dict[str, Any], payload: Any = None) -> None:
    """顶板意图：根节点沿 Y 高度分割（上窄条 + 下主空间）。"""
    _ops.apply_top_strip_split(ctx, payload)


def add_bottom_panel(ctx: dict[str, Any], payload: Any = None) -> None:
    """底板意图：根节点沿深度方向水平分割（兼容既有 splitter 语义）。"""
    _ops.apply_horizontal_split_default(ctx, payload)


def add_back_panel(ctx: dict[str, Any], payload: Any = None) -> None:
    """背板意图：兼容期不改变树结构。"""
    _ops.apply_noop_tree_change(ctx, payload)


def add_door(ctx: dict[str, Any], payload: Any = None) -> None:
    """开门意图：占位。"""
    _ops.apply_noop_tree_change(ctx, payload)


def add_drawer(ctx: dict[str, Any], payload: Any = None) -> None:
    """抽屉意图：占位。"""
    _ops.apply_noop_tree_change(ctx, payload)


def apply_add_or_modify(ctx: dict[str, Any], payload: Any = None) -> None:
    """属性「添加 or 修改」：兼容期不改变树。"""
    _ops.apply_noop_tree_change(ctx, payload)


def save_to_library(ctx: dict[str, Any], payload: Any = None) -> None:
    """存为产品库：树不变。"""
    _ops.apply_noop_tree_change(ctx, payload)


def finish_cabinet_design(ctx: dict[str, Any], payload: Any = None) -> None:
    """完成设计：树不变。"""
    _ops.apply_noop_tree_change(ctx, payload)
