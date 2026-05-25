# -*- coding: utf-8 -*-
"""GL 视图像素射线与逻辑 Space 侧面拾取（无命令 / 无业务，仅几何）。"""

from __future__ import annotations

import numpy as np
from PySide6.QtGui import QVector3D, QVector4D

try:
    from pyqtgraph.opengl.MeshData import MeshData as _MeshData

    _HAS_PG = True
except ImportError:  # pragma: no cover
    _MeshData = None  # type: ignore[misc, assignment]
    _HAS_PG = False

from core.space.space_models import Space


def gl_screen_ray(gl, sx: float, sy: float) -> tuple[QVector3D, QVector3D] | None:
    """从 GL 视图像素坐标得到世界空间射线 ``(origin, unit_direction)``。"""
    vp = gl.getViewport()
    m_proj = gl.projectionMatrix(vp, vp)
    m_mv = gl.viewMatrix()
    mvp = m_proj * m_mv
    inv, ok = mvp.inverted()
    if not ok:
        return None
    w = max(gl.width(), 1)
    h = max(gl.height(), 1)
    nx = 2.0 * float(sx) / w - 1.0
    ny = 1.0 - 2.0 * float(sy) / h

    def _un(zc: float) -> QVector3D | None:
        v = inv * QVector4D(nx, ny, zc, 1.0)
        ww = v.w()
        if abs(ww) < 1e-9:
            return None
        return QVector3D(v.x() / ww, v.y() / ww, v.z() / ww)

    pn = _un(-1.0)
    pf = _un(1.0)
    if pn is None or pf is None:
        return None
    rd = pf - pn
    ln = rd.length()
    if ln < 1e-9:
        return None
    return pn, QVector3D(rd.x() / ln, rd.y() / ln, rd.z() / ln)


def ray_hits_space_left_face(
    space: Space,
    origin: QVector3D,
    direction: QVector3D,
    *,
    margin_mm: float = 120.0,
) -> bool:
    """射线是否与逻辑空间 **左侧面**（``x = space.x`` 的 YZ 矩形，带容差）相交。"""
    px = float(space.x)
    dx = direction.x()
    if abs(dx) < 1e-6:
        return False
    t = (px - origin.x()) / dx
    if t < 0.0 or t > 1.0e7:
        return False
    pt = origin + direction * t
    py, pz = pt.y(), pt.z()
    y0, y1 = float(space.y), float(space.y + space.height)
    z0, z1 = float(space.z), float(space.z + space.depth)
    return (y0 - margin_mm <= py <= y1 + margin_mm) and (z0 - margin_mm <= pz <= z1 + margin_mm)


def ray_hits_space_right_face(
    space: Space,
    origin: QVector3D,
    direction: QVector3D,
    *,
    margin_mm: float = 120.0,
) -> bool:
    """射线是否与逻辑空间 **右侧面**（``x = space.x + width`` 的 YZ 矩形，带容差）相交。"""
    px = float(space.x + space.width)
    dx = direction.x()
    if abs(dx) < 1e-6:
        return False
    t = (px - origin.x()) / dx
    if t < 0.0 or t > 1.0e7:
        return False
    pt = origin + direction * t
    py, pz = pt.y(), pt.z()
    y0, y1 = float(space.y), float(space.y + space.height)
    z0, z1 = float(space.z), float(space.z + space.depth)
    return (y0 - margin_mm <= py <= y1 + margin_mm) and (z0 - margin_mm <= pz <= z1 + margin_mm)


def left_face_quad_meshdata(space: Space, offset_mm: float = 1.5):
    """左侧面 YZ 矩形（沿 +X 微偏移，减轻与逻辑盒 z-fight）。"""
    if not _HAS_PG or _MeshData is None:
        return None
    x = float(space.x) + offset_mm
    y0, y1 = float(space.y), float(space.y + space.height)
    z0, z1 = float(space.z), float(space.z + space.depth)
    verts = np.array(
        [
            [x, y0, z0],
            [x, y1, z0],
            [x, y1, z1],
            [x, y0, z1],
        ],
        dtype=np.float32,
    )
    faces = np.array([[0, 1, 2], [0, 2, 3]], dtype=np.uint32)
    return _MeshData(vertexes=verts, faces=faces)


def left_panel_slab_meshdata(
    space: Space,
    thickness_mm: float,
    stack_offset_mm: float = 0.0,
):
    """沿 +X 的左侧板实体盒预览（``x0 = space.x + stack``，厚度 ``thickness_mm``）。"""
    if not _HAS_PG or _MeshData is None:
        return None
    t = max(float(thickness_mm), 0.01)
    x0 = float(space.x) + float(stack_offset_mm)
    x1 = x0 + t
    y0, y1 = float(space.y), float(space.y + space.height)
    z0, z1 = float(space.z), float(space.z + space.depth)
    verts = np.array(
        [
            [x0, y0, z0],
            [x1, y0, z0],
            [x1, y1, z0],
            [x0, y1, z0],
            [x0, y0, z1],
            [x1, y0, z1],
            [x1, y1, z1],
            [x0, y1, z1],
        ],
        dtype=np.float32,
    )
    faces = np.array(
        [
            [0, 1, 2],
            [0, 2, 3],
            [4, 6, 5],
            [4, 7, 6],
            [0, 4, 5],
            [0, 5, 1],
            [2, 6, 7],
            [2, 7, 3],
            [0, 3, 7],
            [0, 7, 4],
            [1, 5, 6],
            [1, 6, 2],
        ],
        dtype=np.uint32,
    )
    return _MeshData(vertexes=verts, faces=faces)


def right_panel_slab_meshdata(
    space: Space,
    thickness_mm: float,
    stack_offset_mm: float = 0.0,
):
    """沿 -X 的右侧板实体盒预览（``x1 = right - stack``，厚度 ``thickness_mm``）。"""
    if not _HAS_PG or _MeshData is None:
        return None
    t = max(float(thickness_mm), 0.01)
    x1 = float(space.x + space.width) - float(stack_offset_mm)
    x0 = x1 - t
    y0, y1 = float(space.y), float(space.y + space.height)
    z0, z1 = float(space.z), float(space.z + space.depth)
    verts = np.array(
        [
            [x0, y0, z0],
            [x1, y0, z0],
            [x1, y1, z0],
            [x0, y1, z0],
            [x0, y0, z1],
            [x1, y0, z1],
            [x1, y1, z1],
            [x0, y1, z1],
        ],
        dtype=np.float32,
    )
    faces = np.array(
        [
            [0, 1, 2],
            [0, 2, 3],
            [4, 6, 5],
            [4, 7, 6],
            [0, 4, 5],
            [0, 5, 1],
            [2, 6, 7],
            [2, 7, 3],
            [0, 3, 7],
            [0, 7, 4],
            [1, 5, 6],
            [1, 6, 2],
        ],
        dtype=np.uint32,
    )
    return _MeshData(vertexes=verts, faces=faces)
