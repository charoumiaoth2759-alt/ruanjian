# -*- coding: utf-8 -*-
"""
封边规则应用（暴露面 / 封边条规格）。

本模块为目录重构后补齐的**入口占位**：不修改传入 `Panel` 的已有字段，
以便在缺少完整规则库时仍能完成 import 与调用链。
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from core.panel.panel_models import Panel
    from core.space.space_models import Space


def apply_edge_band_rules(panel: "Panel", space: "Space") -> None:
    """按空间与板件角色应用封边规则（当前无操作，保持签名稳定）。"""
    del panel, space


def get_edge_band_thickness() -> float:
    """占位：返回典型封边条厚度参考值（mm）。"""
    return 0.8


__all__ = ["apply_edge_band_rules", "get_edge_band_thickness"]
