# -*- coding: utf-8 -*-
"""加板交互来源标识（打点 / 溯源）；不参与业务分支逻辑。"""

from __future__ import annotations

from enum import Enum


class CabinetInteractionSource(str, Enum):
    """经由 ``CabinetInteractionManager`` 的统一加板流水线入口归因。"""

    UI_COMPONENT_LIBRARY_SLOT = "ui_component_library_slot"
    UI_COMPONENT_LIBRARY_ICON = "ui_component_library_icon"
    MAIN_3D_HOVER_CLICK = "main_3d_hover_click"
    MAIN_3D_SHORTCUT = "main_3d_shortcut"
    PARAM_SPACE_TOOL = "param_space_tool"
    TOOLBAR = "toolbar"
    INTERNAL_LEGACY_DISPATCH = "internal_legacy_dispatch"


__all__ = ["CabinetInteractionSource"]
