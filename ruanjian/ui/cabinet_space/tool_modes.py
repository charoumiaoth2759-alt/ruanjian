# -*- coding: utf-8 -*-
"""柜体设计工具模式（纯枚举，不依赖 Qt）。"""

from __future__ import annotations

from enum import Enum


class ToolMode(Enum):
    """当前激活的柜体设计交互工具。"""

    SELECT = "select"
    ADD_LEFT_PANEL = "add_left_panel"
    ADD_RIGHT_PANEL = "add_right_panel"


__all__ = ["ToolMode"]
