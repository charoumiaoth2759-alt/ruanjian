# -*- coding: utf-8 -*-
"""
柜体板件相关业务流（兼容期：与 ``commands.panel_commands`` 并行）。

说明：
    - 本模块**不**创建 ``Panel`` 实例，仅委托 ``core.panel.cabinet_panel_tree_cmd``
      修改 ``Space`` 树等**领域数据**。
    - **不进行**视图渲染、不访问画布、不触发任何宿主 UI 行为；展示与刷新由
      ``commands`` / 应用层在求解与事件之后编排。
"""

from __future__ import annotations

from typing import Any

from core.panel import cabinet_panel_tree_cmd as _pcmd


def _project_from_ctx(ctx: dict[str, Any]) -> Any:
    """从命令上下文中取当前柜体项目（可能为 SimpleNamespace）。"""
    return ctx.get("project")


# ---------------------------------------------------------------------------
# 各语义命令对应的业务入口（委托 ``core.panel`` 聚合命令，与 panel_commands 对齐）
# ---------------------------------------------------------------------------


def stage_add_left_panel(ctx: dict[str, Any], payload: Any = None) -> None:
    """左侧板意图。"""
    _pcmd.add_left_panel(ctx, payload)


def stage_add_right_panel(ctx: dict[str, Any], payload: Any = None) -> None:
    """右侧板意图。"""
    _pcmd.add_right_panel(ctx, payload)


def stage_add_top_panel(ctx: dict[str, Any], payload: Any = None) -> None:
    """顶板意图。"""
    _pcmd.add_top_panel(ctx, payload)


def stage_add_bottom_panel(ctx: dict[str, Any], payload: Any = None) -> None:
    """底板意图。"""
    _pcmd.add_bottom_panel(ctx, payload)


def stage_add_back_panel(ctx: dict[str, Any], payload: Any = None) -> None:
    """背板。"""
    _pcmd.add_back_panel(ctx, payload)


def stage_add_door(ctx: dict[str, Any], payload: Any = None) -> None:
    """开门占位。"""
    _pcmd.add_door(ctx, payload)


def stage_add_drawer(ctx: dict[str, Any], payload: Any = None) -> None:
    """抽屉占位。"""
    _pcmd.add_drawer(ctx, payload)


def stage_apply_add_or_modify(ctx: dict[str, Any], payload: Any = None) -> None:
    """属性面板「添加 or 修改」对应的数据侧入口。"""
    _pcmd.apply_add_or_modify(ctx, payload)


def stage_save_to_library(ctx: dict[str, Any], payload: Any = None) -> None:
    """存为产品库。"""
    _ = (_project_from_ctx(ctx), payload)
    _pcmd.save_to_library(ctx, payload)


def stage_finish_cabinet_design(ctx: dict[str, Any], payload: Any = None) -> None:
    """完成柜子设计。"""
    _pcmd.finish_cabinet_design(ctx, payload)
