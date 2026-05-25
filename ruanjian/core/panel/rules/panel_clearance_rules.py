# -*- coding: utf-8 -*-
"""
门板 / 抽屉前板等「开口板件」的安装缝隙。

本模块为目录重构后补齐的**入口占位**：结构板件默认四向 0 缝。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.constants.enums import PanelRole

if TYPE_CHECKING:
    from core.space.space_models import Space


@dataclass(frozen=True)
class Clearance:
    left: float = 0.0
    right: float = 0.0
    top: float = 0.0
    bottom: float = 0.0


_DOOR_LIKE = frozenset(
    {
        PanelRole.DOOR_LEFT,
        PanelRole.DOOR_RIGHT,
        PanelRole.DOOR_DOUBLE,
        PanelRole.DRAWER_FRONT,
    },
)


def get_clearance(role: PanelRole, _space: "Space") -> Clearance:
    """按板件角色返回四向安装缝（mm）；门/抽屉类给对称小缝，其余为 0。"""
    if role in _DOOR_LIKE:
        g = 2.0
        return Clearance(left=g, right=g, top=g, bottom=g)
    return Clearance()


__all__ = ["Clearance", "get_clearance"]
