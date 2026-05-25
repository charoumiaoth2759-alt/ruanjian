# -*- coding: utf-8 -*-
"""柜体设计交互模式（纯枚举）。加板经 ``CabinetInteractionManager`` 记录 ``[MODE]``，不直接改模型。"""

from __future__ import annotations

from enum import Enum


class InteractionMode(Enum):
    """与 ``ToolMode`` 对齐的交互语义；由 ``CabinetDesignView.set_interaction_mode`` 同步到视图。"""

    SELECT = "SELECT"
    ADD_PANEL = "ADD_PANEL"


__all__ = ["InteractionMode"]
