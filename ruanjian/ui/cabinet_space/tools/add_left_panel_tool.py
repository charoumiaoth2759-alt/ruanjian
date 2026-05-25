# -*- coding: utf-8 -*-
"""逻辑 Space 左侧面：悬停半透明预览板；左键单击提交加板交互（经 ``CabinetInteractionManager`` 流水线）。"""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import Qt

from core.space.space_face_occupancy import SpaceFace, get_face_occupancy_manager
from core.space.space_models import Space

from ..gl_ray_utils import (
    gl_screen_ray,
    left_panel_slab_meshdata,
    ray_hits_space_left_face,
)
from .base_tool import BaseTool

try:
    from pyqtgraph.opengl import GLMeshItem

    _HAS_PG = True
except ImportError:  # pragma: no cover
    GLMeshItem = None  # type: ignore[misc, assignment]
    _HAS_PG = False


_DEFAULT_THICKNESS_MM = 18.0


def _event_local_xy(event: Any) -> tuple[float, float]:
    pos = event.position() if hasattr(event, "position") else event.localPos()
    return float(pos.x()), float(pos.y())


class AddLeftPanelTool(BaseTool):
    """
    1. 射线命中 Space 左侧面 → ``hover_left``。
    2. ``mouseMove``：持续刷新射线，更新悬停状态（供 ``draw_preview`` 画 ghost）。
    3. 左键在左面 **单击** → 宿主注入的 ``submit_add_left_panel_payload_fn``（载荷含 ``thickness``）
       → ``submit_add_left_panel_interaction`` → CommandFactory → UndoStack → 增量 Scene。
    4. 左侧面未被非 ``LEFT_SIDE`` 的板占用时可派发；多块 ``LEFT_SIDE`` 可叠放。
    """

    def __init__(self) -> None:
        self.hover_left = False
        self.preview_thickness = _DEFAULT_THICKNESS_MM
        self._slab_item: Any = None

    def reset(self, gl: Any | None = None) -> None:
        """退出工具或换根空间时清空状态与 GL 项。"""
        if gl is not None:
            self._remove_gl_items(gl)
        self.hover_left = False
        self.preview_thickness = _DEFAULT_THICKNESS_MM

    def _remove_gl_items(self, gl: Any) -> None:
        it = self._slab_item
        if it is not None:
            try:
                gl.removeItem(it)
            except Exception:
                pass
        self._slab_item = None

    def _update_hover_from_ray(self, gl: Any, space: Space, sx: float, sy: float) -> None:
        ray = gl_screen_ray(gl, sx, sy)
        if ray is None:
            self.hover_left = False
            return
        origin, direction = ray
        hit = ray_hits_space_left_face(space, origin, direction)
        if not hit:
            self.hover_left = False
            return
        fm = get_face_occupancy_manager()
        self.hover_left = not fm.is_face_occupied(space.id, SpaceFace.LEFT)

    def on_mouse_move(self, event: Any, gl: Any, context: dict[str, Any] | None = None) -> bool:
        if context is None or gl is None:
            return False
        space = context.get("space")
        if not isinstance(space, Space):
            return False

        sx, sy = _event_local_xy(event)
        self._update_hover_from_ray(gl, space, sx, sy)
        return False

    def on_mouse_press(self, event: Any, gl: Any, context: dict[str, Any] | None = None) -> bool:
        if context is None or gl is None:
            return False
        if event.button() != Qt.MouseButton.LeftButton:
            return False
        space = context.get("space")
        if not isinstance(space, Space):
            return False

        sx, sy = _event_local_xy(event)
        self._update_hover_from_ray(gl, space, sx, sy)
        if not self.hover_left:
            return False

        fn = context.get("submit_add_left_panel_payload_fn")
        if callable(fn):
            try:
                from core.space.cabinet_ops_lock import ctx_cabinet_ops_locked

                cctx = (context or {}).get("cabinet_lock_ctx")
                if isinstance(cctx, dict) and ctx_cabinet_ops_locked(cctx):
                    return True
                fn({"thickness": float(_DEFAULT_THICKNESS_MM)})
            except Exception:
                pass
        self.preview_thickness = _DEFAULT_THICKNESS_MM
        return True

    def on_mouse_release(self, event: Any, gl: Any, context: dict[str, Any] | None = None) -> bool:
        return False

    def draw_preview(self, gl: Any, context: dict[str, Any] | None = None) -> None:
        if not _HAS_PG or GLMeshItem is None or gl is None:
            return
        if context is None:
            self._remove_gl_items(gl)
            return
        space = context.get("space")
        if not isinstance(space, Space):
            self._remove_gl_items(gl)
            return

        stack = float(context.get("stack_offset_mm", 0.0) or 0.0)

        self._remove_gl_items(gl)

        if not self.hover_left:
            return

        md = left_panel_slab_meshdata(
            space, _DEFAULT_THICKNESS_MM, stack_offset_mm=stack
        )
        if md is None:
            return
        self._slab_item = GLMeshItem(
            meshdata=md,
            smooth=False,
            drawFaces=True,
            drawEdges=False,
            shader="shaded",
            color=(0.25, 0.82, 0.42, 0.42),
        )
        try:
            self._slab_item.setGLOptions("translucent")
        except Exception:
            pass
        gl.addItem(self._slab_item)
