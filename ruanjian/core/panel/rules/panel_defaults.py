# -*- coding: utf-8 -*-
"""
板件默认厚度与背板开关等参数。

本模块为目录重构后补齐的**默认参数入口**。
"""

from __future__ import annotations

from dataclasses import dataclass

from core.space.enums import SpaceType


@dataclass(frozen=True)
class PanelDefaults:
    side_thickness: float = 18.0
    top_thickness: float = 18.0
    bottom_thickness: float = 18.0
    back_thickness: float = 9.0
    has_back: bool = True
    divider_thickness: float = 18.0
    shelf_thickness: float = 18.0


_DEFAULT = PanelDefaults()


def get_panel_defaults(_space_type: SpaceType) -> PanelDefaults:
    """按空间类型返回默认板厚等（当前为统一默认，保持 API 稳定）。"""
    return _DEFAULT


__all__ = ["PanelDefaults", "get_panel_defaults"]
