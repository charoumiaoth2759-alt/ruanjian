# -*- coding: utf-8 -*-
"""柜体参数化视图交互工具基类：仅输入/预览语义，不绑定命令或求解。"""

from __future__ import annotations

from typing import Any


class BaseTool:
    """宿主（如 ``ParamSpaceGLView``）将 GL 与上下文注入；子类实现具体交互。"""

    def on_mouse_move(self, event: Any, gl: Any, context: dict[str, Any] | None = None) -> bool:
        """鼠标移动。返回 True 表示建议宿主吞掉事件（如拖曳中禁用轨道）。"""
        return False

    def on_mouse_press(self, event: Any, gl: Any, context: dict[str, Any] | None = None) -> bool:
        """鼠标按下。"""
        return False

    def on_mouse_release(self, event: Any, gl: Any, context: dict[str, Any] | None = None) -> bool:
        """鼠标松开。"""
        return False

    def draw_preview(self, gl: Any, context: dict[str, Any] | None = None) -> None:
        """在 GL 场景中同步半透明预览几何（由宿主在状态变更后调用）。"""
        pass


class NullTool(BaseTool):
    """无操作工具：选择模式等默认占用，不拦截鼠标、不绘制预览。"""

    pass
