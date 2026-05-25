# -*- coding: utf-8 -*-
"""
柜体设计：对 `Space` 树的兼容层编辑操作。

原则：
    - 不在这里创建 `Panel` 对象；板件由 ``core.panel.panel_generator.generate`` 从树生成。
    - 尽量调用既有 ``core.space.splitter`` 的 `split_vertical`（写 `SPLIT_X`）/
      `split_horizontal`（写 `SPLIT_Z`）/ `split_stack_y`（写 `SPLIT_Y`）。
    - 若树状态不适合再分割（已有子节点等），**静默跳过**，保证旧交互不崩。
"""

from __future__ import annotations

from typing import Any


def _root_space(ctx: dict[str, Any]) -> Any:
    project = ctx.get("project")
    if project is None:
        return None
    return getattr(project, "root_space", None)


def apply_vertical_split_default(ctx: dict[str, Any], payload: Any = None) -> bool:
    """
    在根节点上做「左右」垂直分割（示意：左侧窄条 + 其余空间）。

    映射语义：组件库「左侧板」意图 → 先切分空间，再由 generator 出板件。
    payload 可为 dict，含键 `left_width`（mm，可选）。
    """
    _ = payload
    root = _root_space(ctx)
    if root is None or getattr(root, "width", 0) <= 1:
        return False
    if len(getattr(root, "children", [])) > 0:
        return False
    from ..space.splitter import split_vertical

    lw = 100.0
    if isinstance(payload, dict) and payload.get("left_width") is not None:
        try:
            lw = float(payload["left_width"])
        except (TypeError, ValueError):
            lw = 100.0
    lw = max(18.0, min(lw, root.width - 18.0))
    rw = max(root.width - lw, 1.0)
    split_vertical(root, [lw, rw])
    return True


def apply_vertical_split_right_strip(ctx: dict[str, Any], payload: Any = None) -> bool:
    """根节点左右分割：右侧窄条（示意「右侧板」前置空间划分）。"""
    _ = payload
    root = _root_space(ctx)
    if root is None or getattr(root, "width", 0) <= 1:
        return False
    if len(getattr(root, "children", [])) > 0:
        return False
    from ..space.splitter import split_vertical

    rw = 100.0
    lw = max(root.width - rw, 1.0)
    split_vertical(root, [lw, rw])
    return True


def apply_top_strip_split(ctx: dict[str, Any], payload: Any = None) -> bool:
    """
    在根节点上沿高度 Y 做「下主空间 + 上窄条」分割（示意顶板前置空间）。

    与 `split_stack_y` 配合；根已有子节点时跳过。
    """
    _ = payload
    root = _root_space(ctx)
    if root is None or getattr(root, "height", 0) <= 1:
        return False
    if len(getattr(root, "children", [])) > 0:
        return False
    from ..space.splitter import split_stack_y

    th = 100.0
    if isinstance(payload, dict) and payload.get("top_height") is not None:
        try:
            th = float(payload["top_height"])
        except (TypeError, ValueError):
            th = 100.0
    th = max(18.0, min(th, root.height - 18.0))
    bh = max(root.height - th, 1.0)
    split_stack_y(root, [bh, th])
    return True


def apply_horizontal_split_default(ctx: dict[str, Any], payload: Any = None) -> bool:
    """
    在根节点上沿 Z（深度）方向分段（`split_horizontal` → ``SplitDirection.SPLIT_Z``）。

    用于「底板」等命令的**占位**空间划分；若根已有子节点则跳过。
    """
    _ = payload
    root = _root_space(ctx)
    if root is None or getattr(root, "depth", 0) <= 1:
        return False
    if len(getattr(root, "children", [])) > 0:
        return False
    from ..space.splitter import split_horizontal

    front = min(120.0, root.depth * 0.25)
    back = max(root.depth - front, 1.0)
    split_horizontal(root, [front, back])
    return True


def apply_noop_tree_change(ctx: dict[str, Any], payload: Any = None) -> bool:
    """不改变树结构（背板/门/抽屉等命令的兼容占位）。"""
    _ = (ctx, payload)
    return True
