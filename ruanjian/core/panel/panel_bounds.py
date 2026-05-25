# -*- coding: utf-8 -*-
"""
板件朝向 → 世界轴 AABB / 盒尺寸 ``(Δx,Δy,Δz)``。

若 ``panel.size_x / size_y / size_z`` 三者均 > 0，则直接作为世界轴上的盒尺寸（与 ``panel.x,y,z`` 最小角
配合），**不再**按 ``orientation`` 映射 ``width/height/thickness``。

否则回退到由 ``width / height / thickness`` 与 ``PanelOrientation`` 推导（厚度方向语义如下）：

- ``VERTICAL_X``：板面在 **YZ**，**thickness 沿 +X** → ``Δx=thickness``。
- ``VERTICAL_Z``：板面在 **XY**，**thickness 沿 +Z** → ``Δz=thickness``。
- ``HORIZONTAL``：板面在 **XZ**，**thickness 沿 +Y** → ``Δy=thickness``。

供 ``view_3d``、``panel_visual``、``panel_topology`` 等共用，避免 UI / core 各写一套。
"""

from __future__ import annotations

from typing import Any

from ..constants.enums import PanelOrientation


def resolve_panel_orientation(panel: Any) -> PanelOrientation:
    """解析 ``panel.orientation``（枚举 / 字符串 / 带 ``.value`` 的包装）。"""
    o = getattr(panel, "orientation", None)
    if isinstance(o, PanelOrientation):
        return o

    def _from_str(s: str) -> PanelOrientation | None:
        s = s.strip()
        if not s:
            return None
        if s in PanelOrientation.__members__:
            return PanelOrientation[s]
        try:
            return PanelOrientation(s)
        except ValueError:
            pass
        try:
            return PanelOrientation(s.lower())
        except ValueError:
            return None

    if isinstance(o, str):
        r = _from_str(o)
        if r is not None:
            return r
    v = getattr(o, "value", None)
    if isinstance(v, str):
        r = _from_str(v)
        if r is not None:
            return r
    return PanelOrientation.VERTICAL_X


def panel_extents_world_xyz(panel: Any) -> tuple[float, float, float]:
    """
    世界轴盒尺寸 ``(Δx, Δy, Δz)``。

    若 ``size_x/size_y/size_z`` 均已给定（>0），则直接返回该三元组。
    否则将 ``width / height / thickness`` 按 ``orientation`` 映射到世界轴。

    与 ``panel_placement._check_bounds``、``panel_topology._panel_bbox`` 一致。
    """
    sx = float(getattr(panel, "size_x", 0.0) or 0.0)
    sy = float(getattr(panel, "size_y", 0.0) or 0.0)
    sz = float(getattr(panel, "size_z", 0.0) or 0.0)
    if sx > 1e-9 and sy > 1e-9 and sz > 1e-9:
        return sx, sy, sz

    pw = float(getattr(panel, "width", 0.0))
    ph = float(getattr(panel, "height", 0.0))
    pt = float(getattr(panel, "thickness", 0.0))
    orient = resolve_panel_orientation(panel)

    if orient == PanelOrientation.VERTICAL_X:
        return pt, ph, pw
    if orient == PanelOrientation.HORIZONTAL:
        return pw, pt, ph
    if orient == PanelOrientation.VERTICAL_Z:
        return pw, ph, pt
    # 未知朝向：与领域默认 ``VERTICAL_X`` 一致，避免把厚度误放到 Z
    return pt, ph, pw


def panel_world_aabb_at(
    panel: Any,
    x: float,
    y: float,
    z: float,
) -> tuple[float, float, float, float, float, float]:
    """角点 ``(x,y,z)`` + 板件尺寸/朝向 → ``(x0,x1,y0,y1,z0,z1)``。"""
    ex, ey, ez = panel_extents_world_xyz(panel)
    return x, x + ex, y, y + ey, z, z + ez


def panel_world_aabb(panel: Any) -> tuple[float, float, float, float, float, float]:
    """``panel.x/y/z`` 为最小角时的世界轴对齐包围盒。"""
    x = float(getattr(panel, "x", 0.0))
    y = float(getattr(panel, "y", 0.0))
    z = float(getattr(panel, "z", 0.0))
    return panel_world_aabb_at(panel, x, y, z)


__all__ = [
    "resolve_panel_orientation",
    "panel_extents_world_xyz",
    "panel_world_aabb_at",
    "panel_world_aabb",
]
