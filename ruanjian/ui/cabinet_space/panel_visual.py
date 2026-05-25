# -*- coding: utf-8 -*-
"""板件几何 → OpenGL 用三角网格（与业务规则解耦，仅按朝向展开 AABB）。"""

from __future__ import annotations

import numpy as np

from core.panel.panel_bounds import (
    panel_extents_world_xyz as _extents_xyz,
    resolve_panel_orientation as _resolve_orientation,
)

from core.debug_flags import DEBUG_VIEW3D

try:
    from pyqtgraph.opengl import GLMeshItem
    from pyqtgraph.opengl.MeshData import MeshData

    _HAS_PG = True
except ImportError:  # pragma: no cover
    GLMeshItem = None  # type: ignore[misc, assignment]
    MeshData = None  # type: ignore[misc, assignment]
    _HAS_PG = False


def _axis_aligned_box_vertices_faces(
    x: float, y: float, z: float, ex: float, ey: float, ez: float
) -> tuple[np.ndarray, np.ndarray]:
    """
    轴对齐盒：最小角 ``(x,y,z)``，沿 X/Y/Z 正方向延伸 ``ex, ey, ez``。
    返回 ``(8,3)`` 顶点与 ``(12,3)`` 三角形索引（与 ``space_visual._box_vertices_faces`` 一致）。
    """
    v = np.array(
        [
            [x, y, z],
            [x + ex, y, z],
            [x + ex, y, z + ez],
            [x, y, z + ez],
            [x, y + ey, z],
            [x + ex, y + ey, z],
            [x + ex, y + ey, z + ez],
            [x, y + ey, z + ez],
        ],
        dtype=np.float32,
    )
    f = np.array(
        [
            [0, 2, 1],
            [0, 3, 2],
            [4, 5, 6],
            [4, 6, 7],
            [0, 1, 5],
            [0, 5, 4],
            [2, 3, 7],
            [2, 7, 6],
            [0, 4, 7],
            [0, 7, 3],
            [1, 2, 6],
            [1, 6, 5],
        ],
        dtype=np.uint32,
    )
    return v, f


def _axis_aligned_box_edge_segments(
    x: float, y: float, z: float, ex: float, ey: float, ez: float
) -> np.ndarray:
    """12 条棱 → ``(24, 3)`` float32，与 ``space_visual._box_edge_segments`` 语义一致。"""
    v = _axis_aligned_box_vertices_faces(x, y, z, ex, ey, ez)[0]
    pairs = [
        (0, 1),
        (1, 2),
        (2, 3),
        (3, 0),
        (4, 5),
        (5, 6),
        (6, 7),
        (7, 4),
        (0, 4),
        (1, 5),
        (2, 6),
        (3, 7),
    ]
    pts: list[np.ndarray] = []
    for a, b in pairs:
        pts.append(v[a])
        pts.append(v[b])
    return np.array(pts, dtype=np.float32)


def build_panel_mesh(panel: object) -> "MeshData | tuple[np.ndarray, np.ndarray]":
    """
    根据 ``panel`` 的位姿与朝向生成轴对齐盒 ``MeshData``（**12 个三角面** 的封闭盒）。

    顶点 + 面索引与 ``space_visual._box_vertices_faces`` 一致；``faces`` 形状 ``(12, 3)``。
    例：左侧板 ``(x,y,z)=(0,0,0)``，``thickness=18, height=2200, width=600``
    → 网格尺寸沿轴 ``Δx=18, Δy=2200, Δz=600``。

    Parameters
    ----------
    panel :
        使用 ``x,y,z``、``width,height,thickness``、``orientation``。

    Returns
    -------
    pyqtgraph.opengl.MeshData.MeshData
        若已安装 pyqtgraph；否则在未安装时返回 ``(vertexes, faces)`` 二元组 ``ndarray``。
    """
    x = float(panel.x)
    y = float(panel.y)
    z = float(panel.z)
    ex, ey, ez = _extents_xyz(panel)
    verts, faces = _axis_aligned_box_vertices_faces(x, y, z, ex, ey, ez)
    if not _HAS_PG or MeshData is None:
        return verts, faces
    return MeshData(vertexes=verts, faces=faces)


def rebuild_panels(
    gl_view,
    panel_groups,
    *,
    face_rgba: tuple[float, float, float, float] | None = None,
) -> list[tuple[object, object | None]]:
    """
    遍历 ``panel_groups`` → 各 ``group.panels``，用 ``build_panel_mesh`` 生成盒网格并加入 ``gl_view``。

    Parameters
    ----------
    gl_view :
        ``pyqtgraph.opengl.GLViewWidget``（或其它支持 ``addItem`` 的 GL 视图）。
    panel_groups :
        可迭代 ``PanelGroup`` 序列（如 ``space.panel_groups``）。

    Returns
    -------
    list[tuple[GLMeshItem, None]]
        每项为 ``(mesh, None)``：实体由 ``MeshData`` 的 12 三角面 + ``GLMeshItem.drawEdges`` 画棱；
        第二元占位与 ``SceneManager`` 卸下逻辑兼容。
    """
    if not _HAS_PG or MeshData is None or GLMeshItem is None:
        return []

    # rebuild：先卸下本 gl_view 上由上一轮 ``rebuild_panels`` 挂载的 mesh（防漏清叠加）
    prev_items = getattr(gl_view, "_rebuild_panel_mesh_items", None) or []
    for item in prev_items:
        try:
            gl_view.removeItem(item)
        except Exception:
            pass
    gl_view._rebuild_panel_mesh_items = []

    groups = list(panel_groups or [])
    total_panels = sum(len(getattr(g, "panels", []) or []) for g in groups)
    if DEBUG_VIEW3D:
        print("[ParamSpaceGL] rebuild panels =", total_panels)

    fr = face_rgba or (
        205 / 255.0,
        170 / 255.0,
        120 / 255.0,
        1.0,
    )
    edge_rgba = (0.0, 0.0, 0.0, 1.0)

    out: list[tuple[object, object | None]] = []
    for group in groups:
        for panel in getattr(group, "panels", []) or []:
            md = build_panel_mesh(panel)
            if isinstance(md, tuple):
                verts, faces = md
                md = MeshData(vertexes=verts, faces=faces)

            mesh = GLMeshItem(
                meshdata=md,
                smooth=False,
                drawFaces=True,
                drawEdges=True,
                edgeColor=edge_rgba,
                shader="shaded",
                color=fr,
            )
            gl_view.addItem(mesh)
            out.append((mesh, None))

    gl_view._rebuild_panel_mesh_items = [t[0] for t in out if t[0] is not None]

    return out


def append_panel_mesh(
    gl_view,
    panel: object,
    *,
    face_rgba: tuple[float, float, float, float] | None = None,
) -> tuple[object, object | None] | None:
    """
    向 ``gl_view`` **增量**挂载单块板件 mesh（不卸下已有项）。

    Returns
    -------
    (mesh, None) 或 ``None``（无 pyqtgraph / 构建失败）。
    """
    if not _HAS_PG or MeshData is None or GLMeshItem is None:
        return None
    fr = face_rgba or (
        205 / 255.0,
        170 / 255.0,
        120 / 255.0,
        1.0,
    )
    edge_rgba = (0.0, 0.0, 0.0, 1.0)
    md = build_panel_mesh(panel)
    if isinstance(md, tuple):
        verts, faces = md
        md = MeshData(vertexes=verts, faces=faces)
    mesh = GLMeshItem(
        meshdata=md,
        smooth=False,
        drawFaces=True,
        drawEdges=True,
        edgeColor=edge_rgba,
        shader="shaded",
        color=fr,
    )
    gl_view.addItem(mesh)
    prev = getattr(gl_view, "_rebuild_panel_mesh_items", None) or []
    gl_view._rebuild_panel_mesh_items = list(prev) + [mesh]
    return (mesh, None)


__all__ = ["append_panel_mesh", "build_panel_mesh", "rebuild_panels"]
