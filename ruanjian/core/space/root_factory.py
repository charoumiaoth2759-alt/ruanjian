# -*- coding: utf-8 -*-
"""根柜体逻辑空间：仅根据尺寸与名称构造 ``Space`` 数据（无 I/O、无宿主 UI）。"""

from __future__ import annotations

from .enums import SpaceType
from .space_face_occupancy import get_face_occupancy_manager
from .space_models import Space


def make_root_cabinet_space(
    name: str, width: float, height: float, depth: float
) -> Space:
    """由柜体外形尺寸生成根 ``Space`` 节点（纯数据）。"""
    get_face_occupancy_manager().reset()
    return Space(
        name=name or "Root Cabinet",
        space_type=SpaceType.ROOT,
        x=0.0,
        y=0.0,
        z=0.0,
        width=float(width),
        height=float(height),
        depth=float(depth),
    )
