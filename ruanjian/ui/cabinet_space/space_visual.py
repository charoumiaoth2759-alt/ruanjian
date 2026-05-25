# -*- coding: utf-8 -*-
"""Space 的可视化表现：仅依赖 Space 几何，不包含业务规则。"""

from __future__ import annotations

import numpy as np

from core.space.enums import SpaceState as PickSpaceState
from core.space.space_models import Space
from core.space.space_state import infer_space_state, read_ui_placement_for_space_display
from core.space.cabinet_ops_lock import read_cabinet_ops_user_allow
from core.space.space_visual_mapper import space_box_face_edge_rgba

from core.debug_flags import DEBUG_VIEW3D

try:
    from pyqtgraph.opengl import GLMeshItem, GLLinePlotItem
    from pyqtgraph.opengl.MeshData import MeshData

    _HAS_PG = True
except ImportError:  # pragma: no cover
    GLMeshItem = GLLinePlotItem = MeshData = None  # type: ignore
    _HAS_PG = False


def _box_vertices_faces(
    x: float, y: float, z: float, w: float, h: float, d: float
) -> tuple[np.ndarray, np.ndarray]:
    """轴对齐盒：Y 为高度（与 View3D 挤出方向一致），返回 (8,3) 顶点与 (12,3) 三角形索引。"""
    v = np.array(
        [
            [x, y, z],
            [x + w, y, z],
            [x + w, y, z + d],
            [x, y, z + d],
            [x, y + h, z],
            [x + w, y + h, z],
            [x + w, y + h, z + d],
            [x, y + h, z + d],
        ],
        dtype=np.float32,
    )
    # 12 三角形，外法线朝外
    f = np.array(
        [
            [0, 2, 1],
            [0, 3, 2],  # 底 y
            [4, 5, 6],
            [4, 6, 7],  # 顶 y+h
            [0, 1, 5],
            [0, 5, 4],  # 前 z
            [2, 3, 7],
            [2, 7, 6],  # 后 z+d
            [0, 4, 7],
            [0, 7, 3],  # 左 x
            [1, 2, 6],
            [1, 6, 5],  # 右 x+w
        ],
        dtype=np.uint32,
    )
    return v, f


def _box_edge_segments(
    x: float, y: float, z: float, w: float, h: float, d: float
) -> np.ndarray:
    """12 条棱，每段两个点 → (24, 3)。"""
    v = _box_vertices_faces(x, y, z, w, h, d)[0]
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
    pts = []
    for a, b in pairs:
        pts.append(v[a])
        pts.append(v[b])
    return np.array(pts, dtype=np.float32)


def _panel_orientation_name(panel: object) -> str:
    o = getattr(panel, "orientation", None)
    if o is None:
        return ""
    v = getattr(o, "value", None)
    if isinstance(v, str):
        return v
    return str(getattr(o, "name", "") or "")


def draw_space_box(
    gl_view,
    space: Space,
    *,
    face_rgba: tuple[float, float, float, float] | None = None,
    edge_rgba: tuple[float, float, float, float] | None = None,
) -> tuple[object | None, object | None]:
    """
    绘制逻辑空间轴对齐盒（与 ``SpaceVisual`` 默认样式一致）。

    Returns:
        ``(mesh, edges)``；无 pyqtgraph 时为 ``(None, None)``。已 ``addItem`` 到 ``gl_view``。
    """
    if not _HAS_PG:
        return None, None
    fr = face_rgba or SpaceVisual._FACE_RGBA
    er = edge_rgba or SpaceVisual._EDGE_RGBA
    x, y, z = float(space.x), float(space.y), float(space.z)
    w, h, d = float(space.width), float(space.height), float(space.depth)
    verts, faces = _box_vertices_faces(x, y, z, w, h, d)
    md = MeshData(vertexes=verts, faces=faces)
    mesh = GLMeshItem(
        meshdata=md,
        smooth=False,
        drawFaces=True,
        drawEdges=False,
        shader="shaded",
        color=fr,
    )
    edge_pos = _box_edge_segments(x, y, z, w, h, d)
    edges = GLLinePlotItem(
        pos=edge_pos,
        color=er,
        width=1.0,
        mode="lines",
    )
    gl_view.addItem(mesh)
    gl_view.addItem(edges)
    return mesh, edges


def create_panel_mesh(
    panel: object,
    *,
    face_rgba: tuple[float, float, float, float] | None = None,
) -> tuple[object | None, object | None]:
    """
    为板件创建 GL 网格（**未** ``addItem``）。

    仅 ``orientation == VERTICAL_X`` 时返回实体；否则 ``(None, None)``。

    使用 ``MeshData`` 的 **12 三角面** 封闭盒；``GLMeshItem`` 开启 ``drawEdges=True``、
    ``edgeColor=(0,0,0,1)``。第二返回值为 ``None``（棱由 mesh 绘制）。
    """
    if not _HAS_PG:
        return None, None
    if _panel_orientation_name(panel).lower() != "vertical_x":
        return None, None

    if DEBUG_VIEW3D:
        print(
            "[Render] draw panel",
            panel.name,
            panel.position,
            panel.size,
        )

    fr = face_rgba or (
        205 / 255.0,
        170 / 255.0,
        120 / 255.0,
        1.0,
    )

    x = float(getattr(panel, "x", 0.0))
    y = float(getattr(panel, "y", 0.0))
    z = float(getattr(panel, "z", 0.0))
    # VERTICAL_X：板面 YZ、厚沿 X → _box_vertices_faces 的 (w,h,d) = (Δx,Δy,Δz)
    w = float(getattr(panel, "thickness", 0.0))  # Δx
    h = float(getattr(panel, "height", 0.0))      # Δy
    d = float(getattr(panel, "width", 0.0))     # Δz（旁板「板宽」沿 Z）

    verts, faces = _box_vertices_faces(x, y, z, w, h, d)
    md = MeshData(vertexes=verts, faces=faces)
    mesh = GLMeshItem(
        meshdata=md,
        smooth=False,
        drawFaces=True,
        drawEdges=True,
        edgeColor=(0.0, 0.0, 0.0, 1.0),
        shader="shaded",
        color=fr,
    )
    return mesh, None


def draw_panel(
    gl_view,
    panel: object,
    *,
    face_rgba: tuple[float, float, float, float] | None = None,
) -> tuple[object | None, object | None]:
    """
    绘制板件轴对齐盒（``create_panel_mesh`` + 挂载到 ``gl_view``）。

    **VERTICAL_X**：板面在 **YZ**，板厚沿 **X**；盒尺寸
    ``(Δx,Δy,Δz)=(thickness,height,width)``，最小角 ``(panel.x, panel.y, panel.z)``。

    颜色默认木板色 ``(205, 170, 120)`` RGB。
    """
    mesh, edges = create_panel_mesh(panel, face_rgba=face_rgba)
    if mesh is None:
        return None, None
    x = float(getattr(panel, "x", 0.0))
    y = float(getattr(panel, "y", 0.0))
    z = float(getattr(panel, "z", 0.0))
    w = float(getattr(panel, "thickness", 0.0))
    h = float(getattr(panel, "height", 0.0))
    d = float(getattr(panel, "width", 0.0))
    verts, _ = _box_vertices_faces(x, y, z, w, h, d)
    if DEBUG_VIEW3D:
        print(
            "[View3D] box verts =",
            verts.shape,
            panel.role,
        )
    gl_view.addItem(mesh)
    if edges is not None:
        gl_view.addItem(edges)
    return mesh, edges


def _iter_space_panels_unique(space: Space):
    """合并 ``Space.panels`` 与 ``panel_groups`` 内板件，按 ``id`` 去重。"""
    seen: set[str] = set()
    for p in getattr(space, "panels", []) or []:
        pid = getattr(p, "id", None)
        key = str(pid) if pid is not None else str(id(p))
        if key in seen:
            continue
        seen.add(key)
        yield p
    for g in getattr(space, "panel_groups", []) or []:
        for p in getattr(g, "panels", []) or []:
            pid = getattr(p, "id", None)
            key = str(pid) if pid is not None else str(id(p))
            if key in seen:
                continue
            seen.add(key)
            yield p


class SpaceVisual:
    """将单个 `Space` 转为 pyqtgraph GLMeshItem + GLLinePlotItem（非数据源）。"""

    # 与 View3D 逻辑空间盒一致：QColor(135,240,240,153) 约 60% 透明；棱线 QColor(0,255,255)
    _FACE_RGBA = (135 / 255.0, 240 / 255.0, 240 / 255.0, 153 / 255.0)
    _EDGE_RGBA = (0.0, 1.0, 1.0, 1.0)

    def __init__(self, space: Space):
        self.space = space
        self._mesh: object | None = None
        self._edges: object | None = None
        self._panel_items: list[tuple[object | None, object | None]] = []
        self._hover_highlight: bool = False

    def set_hover_highlight(self, value: bool) -> None:
        """仅视觉：悬停高亮；不参与能否放置判断。"""
        self._hover_highlight = bool(value)

    def _mapper_face_edge(self) -> tuple[tuple[float, float, float, float], tuple[float, float, float, float]]:
        pick = infer_space_state(self.space)
        placement = read_ui_placement_for_space_display(self.space)
        cab_allow = (
            read_cabinet_ops_user_allow(self.space)
            if pick is PickSpaceState.OCCUPIED
            else None
        )
        return space_box_face_edge_rgba(
            pick,
            placement,
            hovered=self._hover_highlight,
            cabinet_ops_user_allow=cab_allow,
        )

    def refresh_box_style(self, gl_view) -> None:
        """按当前 ``Space`` 拾取语义 + metadata 放置决策 + 悬停，重画逻辑盒颜色。"""
        if not _HAS_PG:
            return
        if self._mesh is not None:
            try:
                gl_view.removeItem(self._mesh)
            except Exception:
                pass
            self._mesh = None
        if self._edges is not None:
            try:
                gl_view.removeItem(self._edges)
            except Exception:
                pass
            self._edges = None
        fr, er = self._mapper_face_edge()
        self._mesh, self._edges = draw_space_box(gl_view, self.space, face_rgba=fr, edge_rgba=er)

    def attach(self, gl_view) -> None:
        if not _HAS_PG:
            return
        fr, er = self._mapper_face_edge()
        self._mesh, self._edges = draw_space_box(gl_view, self.space, face_rgba=fr, edge_rgba=er)
        self._clear_panel_gl_items(gl_view)
        # 板件网格统一由 ``SceneManager.rebuild_panels`` 挂载，避免与求解路径双画叠加

    def _clear_panel_gl_items(self, gl_view) -> None:
        """卸下本 ``SpaceVisual`` 曾挂载的板件 mesh（若曾单独画过）。"""
        for pm, pe in self._panel_items:
            if pm is not None:
                try:
                    gl_view.removeItem(pm)
                except Exception:
                    pass
            if pe is not None:
                try:
                    gl_view.removeItem(pe)
                except Exception:
                    pass
        self._panel_items.clear()

    def detach(self, gl_view) -> None:
        self._clear_panel_gl_items(gl_view)
        if self._mesh is not None:
            try:
                gl_view.removeItem(self._mesh)
            except Exception:
                pass
            self._mesh = None
        if self._edges is not None:
            try:
                gl_view.removeItem(self._edges)
            except Exception:
                pass
            self._edges = None


def is_pyqtgraph_gl_available() -> bool:
    return _HAS_PG
