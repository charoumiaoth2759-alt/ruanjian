# -*- coding: utf-8 -*-
"""参数化根空间 3D 预览：pyqtgraph.opengl + 尺寸文字叠加；场景含 Space 盒与挂载板件。"""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

from core.panel.cabinet_space_panel_cmd import left_side_stack_offset_mm
from core.space.space_models import Space
from core.space.cabinet_ops_lock import (
    cabinet_space_constraint_engine,
    ctx_cabinet_ops_locked,
    pick_closest_structural_occupied_leaf_for_ray,
    toggle_cabinet_ops_user_allow,
    unlock_closest_occ_leaf_if_locked,
)
from core.space.space_placement_sync import (
    left_side_preview_board_for_validate,
    refresh_leaf_placement_ui_metadata,
)

from ui.cabinet_design_host import (
    resolve_cabinet_design_view,
)
from ui.interaction import CabinetInteractionSource

from .scene_manager import SceneManager
from .tool_modes import ToolMode
from .tools.add_left_panel_tool import AddLeftPanelTool
from .tools.add_right_panel_tool import AddRightPanelTool
from .tools.base_tool import BaseTool, NullTool

try:
    import pyqtgraph as pg
    from pyqtgraph.opengl import GLViewWidget

    _HAS_PG = True
except ImportError:  # pragma: no cover
    pg = None  # type: ignore
    GLViewWidget = None  # type: ignore
    _HAS_PG = False


if _HAS_PG:

    class _ParamSpaceGLViewWidget(GLViewWidget):
        """将鼠标与 ``paintGL`` 转发给宿主 ``ParamSpaceGLView.current_tool``。"""

        def __init__(self, param_host: "ParamSpaceGLView", **kwargs: Any) -> None:
            super().__init__(**kwargs)
            self._param_host = param_host

        def mouseMoveEvent(self, event) -> None:  # noqa: ANN001
            h = self._param_host
            if h._root is not None:
                tc = h._tool_context()
                consumed = h.current_tool.on_mouse_move(event, self, tc)
                if h.tool_mode in (ToolMode.ADD_LEFT_PANEL, ToolMode.ADD_RIGHT_PANEL):
                    h._refresh_space_box_colors()
                    self.update()
                if consumed:
                    event.accept()
                    return
            super().mouseMoveEvent(event)

        def mousePressEvent(self, event) -> None:  # noqa: ANN001
            h = self._param_host
            if h._root is not None:
                if event.button() == Qt.MouseButton.LeftButton:
                    if not (event.modifiers() & Qt.KeyboardModifier.ControlModifier):
                        if h._try_unlock_occ_at_screen(event):
                            self.update()
                            event.accept()
                            return
                    if (
                        event.modifiers() & Qt.KeyboardModifier.ControlModifier
                        and h._try_toggle_cabinet_occ_at_screen(event)
                    ):
                        self.update()
                        event.accept()
                        return
                tc = h._tool_context()
                if h.current_tool.on_mouse_press(event, self, tc):
                    if h.tool_mode in (ToolMode.ADD_LEFT_PANEL, ToolMode.ADD_RIGHT_PANEL):
                        h._refresh_space_box_colors()
                    self.update()
                    event.accept()
                    return
            super().mousePressEvent(event)

        def mouseReleaseEvent(self, event) -> None:  # noqa: ANN001
            h = self._param_host
            if h._root is not None:
                tc = h._tool_context()
                if h.current_tool.on_mouse_release(event, self, tc):
                    self.update()
                    event.accept()
                    return
            super().mouseReleaseEvent(event)

        def paintGL(self) -> None:
            h = self._param_host
            if h._root is not None:
                h.current_tool.draw_preview(self, h._tool_context())
            super().paintGL()


class ParamSpaceGLView(QWidget):
    """含 `GLViewWidget` 的柜体逻辑空间预览；无 pyqtgraph 时降级为提示。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._root: Space | None = None
        self._scene: SceneManager | None = None
        self._gl: QWidget | None = None
        self.tool_mode: ToolMode = ToolMode.SELECT
        self._null_tool = NullTool()
        self._add_left_panel_tool = AddLeftPanelTool()
        self._add_right_panel_tool = AddRightPanelTool()
        self.current_tool: BaseTool = self._null_tool
        self._command_dispatcher: Any = None

        root_lay = QVBoxLayout(self)
        root_lay.setContentsMargins(0, 0, 0, 0)
        root_lay.setSpacing(0)

        if _HAS_PG:
            self._gl = _ParamSpaceGLViewWidget(self)
            self._gl.setBackgroundColor((0.92, 0.95, 0.99, 1.0))
            self._gl.setMouseTracking(True)
            self._gl.opts["distance"] = 5200
            self._scene = SceneManager(self._gl)
            root_lay.addWidget(self._gl, 1)
        else:
            tip = QLabel(
                "未安装 pyqtgraph，无法显示参数化空间 3D 预览。\n"
                "请执行：pip install pyqtgraph"
            )
            tip.setAlignment(Qt.AlignmentFlag.AlignCenter)
            tip.setWordWrap(True)
            tip.setStyleSheet(
                "color:#606266; font-size:13px; padding:24px; background:#f5f7fa;"
            )
            root_lay.addWidget(tip, 1)
            self._gl = None

        self._dim_lbl = QLabel("")
        self._dim_lbl.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self._dim_lbl.setStyleSheet(
            "QLabel {"
            "  background: rgba(255,255,255,0.88);"
            "  color: #303133;"
            "  font-size: 13px;"
            "  font-weight: bold;"
            "  padding: 6px 10px;"
            "  border: 1px solid #dcdfe6;"
            "  border-radius: 4px;"
            "}"
        )
        self._dim_lbl.setParent(self)
        self._dim_lbl.raise_()
        self._dim_lbl.move(12, 12)

    def _try_unlock_occ_at_screen(self, event) -> bool:
        """锁定态 OCC 叶：普通单击盒体解锁为 ALLOWED 配色。"""
        if not _HAS_PG or self._gl is None or self._root is None:
            return False
        from .gl_ray_utils import gl_screen_ray

        pos = event.position() if hasattr(event, "position") else event.localPos()
        sx, sy = float(pos.x()), float(pos.y())
        ray = gl_screen_ray(self._gl, sx, sy)
        if ray is None:
            return False
        origin, direction = ray
        leaf = unlock_closest_occ_leaf_if_locked(
            self._root,
            (origin.x(), origin.y(), origin.z()),
            (direction.x(), direction.y(), direction.z()),
        )
        if leaf is None:
            return False
        self._refresh_space_box_colors()
        return True

    def _try_toggle_cabinet_occ_at_screen(self, event) -> bool:
        """Ctrl+单击：命中 OCCUPIED 叶 AABB 时切换允许编辑。"""
        if not _HAS_PG or self._gl is None or self._root is None:
            return False
        from .gl_ray_utils import gl_screen_ray

        pos = event.position() if hasattr(event, "position") else event.localPos()
        sx, sy = float(pos.x()), float(pos.y())
        ray = gl_screen_ray(self._gl, sx, sy)
        if ray is None:
            return False
        origin, direction = ray
        leaf = pick_closest_structural_occupied_leaf_for_ray(
            self._root,
            (origin.x(), origin.y(), origin.z()),
            (direction.x(), direction.y(), direction.z()),
        )
        if leaf is None:
            return False
        toggle_cabinet_ops_user_allow(leaf)
        self._refresh_space_box_colors()
        return True

    def _tool_context(self) -> dict[str, Any]:
        ctx: dict[str, Any] = {
            "space": self._root,
            "stack_offset_mm": 0.0,
        }
        if self._root is not None:
            ctx["stack_offset_mm"] = float(left_side_stack_offset_mm(self._root))

        d = self._resolved_command_dispatcher()
        ctx["cabinet_lock_ctx"] = getattr(d, "context", None) if d is not None else None

        def _submit_add_left(payload: dict[str, Any]) -> None:
            cdv = resolve_cabinet_design_view(self)
            if cdv is None:
                return
            try:
                cctx = ctx.get("cabinet_lock_ctx")
                if isinstance(cctx, dict) and ctx_cabinet_ops_locked(cctx):
                    return
                fn = getattr(cdv, "submit_add_left_panel_interaction", None)
                if not callable(fn):
                    return
                fn(payload, source=CabinetInteractionSource.PARAM_SPACE_TOOL)
            except Exception:
                pass

        ctx["submit_add_left_panel_payload_fn"] = _submit_add_left

        def _submit_add_right(payload: dict[str, Any]) -> None:
            cdv = resolve_cabinet_design_view(self)
            if cdv is None:
                return
            try:
                cctx = ctx.get("cabinet_lock_ctx")
                if isinstance(cctx, dict) and ctx_cabinet_ops_locked(cctx):
                    return
                fn = getattr(cdv, "submit_add_right_panel_interaction", None)
                if not callable(fn):
                    return
                fn(payload, source=CabinetInteractionSource.PARAM_SPACE_TOOL)
            except Exception:
                pass

        ctx["submit_add_right_panel_payload_fn"] = _submit_add_right
        return ctx

    def _sync_space_placement_ui_metadata(self) -> None:
        """业务结果写入 ``Space.metadata``；颜色仅由 ``space_visual_mapper`` 读取。"""
        if self._root is None:
            return
        if self.tool_mode == ToolMode.ADD_LEFT_PANEL:
            refresh_leaf_placement_ui_metadata(
                self._root,
                engine=cabinet_space_constraint_engine(),
                board_for_space=lambda sp: left_side_preview_board_for_validate(
                    sp, thickness=float(self._add_left_panel_tool.preview_thickness)
                ),
            )
        else:
            refresh_leaf_placement_ui_metadata(self._root, board_for_space=None)

    def _refresh_space_box_colors(self) -> None:
        """同步放置元数据并按悬停刷新各 ``SpaceVisual`` 盒颜色。"""
        if self._scene is None or self._gl is None or self._root is None:
            return
        self._sync_space_placement_ui_metadata()
        hovered: set[str] = set()
        if self.tool_mode == ToolMode.ADD_LEFT_PANEL and self._add_left_panel_tool.hover_left:
            hovered.add(self._root.id)
        if self.tool_mode == ToolMode.ADD_RIGHT_PANEL and self._add_right_panel_tool.hover_right:
            hovered.add(self._root.id)
        self._scene.refresh_space_box_styles(hovered_space_ids=hovered)
        self._gl.update()

    def _sync_add_left_preview(self) -> None:
        if not _HAS_PG or self._gl is None or self._root is None:
            return
        self.current_tool.draw_preview(self._gl, self._tool_context())
        self._gl.update()

    def set_command_dispatcher(self, dispatcher: Any) -> None:
        """显式注入 ``CommandDispatcher``（可选；未设置时尝试从父窗口链解析）。"""
        self._command_dispatcher = dispatcher

    def _resolved_command_dispatcher(self) -> Any:
        if self._command_dispatcher is not None:
            return self._command_dispatcher
        cv = resolve_cabinet_design_view(self)
        if cv is not None:
            d = getattr(cv, "_cmd_dispatcher", None)
            if d is not None and hasattr(d, "dispatch"):
                return d
        return None

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._dim_lbl.move(12, 12)

    def set_root_space(self, space: Space) -> None:
        """绑定根空间并刷新 GL 与尺寸文案。"""
        if self._gl is not None:
            self._add_left_panel_tool.reset(self._gl)
            self._add_right_panel_tool.reset(self._gl)
        self._root = space
        w, h, d = space.width, space.height, space.depth
        self._dim_lbl.setText(
            f"{space.name or 'Root'}   {w:.0f} × {h:.0f} × {d:.0f}  mm"
        )
        self._dim_lbl.adjustSize()

        if self._scene is not None and self._gl is not None:
            self._scene.clear()
            self._sync_space_placement_ui_metadata()
            self._scene.add_space(space)
            self._frame_camera(space)
        self._sync_add_left_preview()

    def rebuild_scene(self, solve_result) -> None:
        """
        仅按求解结果刷新板件 GL（``solve_result.panel_groups``），不重绑根 ``Space``。

        典型：``SOLVE_COMPLETED`` 后由宿主传入 ``SolveResult``。
        """
        if self._scene is None:
            return
        pgs = getattr(solve_result, "panel_groups", None) if solve_result is not None else None
        self._scene.rebuild_panels(pgs or [])
        self._sync_add_left_preview()

    def apply_full_panel_rebuild_display(self, panel_groups: list | None = None) -> None:
        """
        全量 ``rebuild_panels``：仅柜体尺寸 / 根布局 / Full Solve 路径。

        不调用 ``set_root_space`` / ``_frame_camera``，保持相机与工具模式不变。
        """
        if self._scene is None or self._gl is None or self._root is None:
            return
        from .scene_manager import collect_panel_groups_from_tree

        pgs = (
            list(panel_groups)
            if panel_groups is not None
            else collect_panel_groups_from_tree(self._root)
        )
        self._scene.rebuild_panels(pgs)
        self._refresh_space_box_colors()
        self._sync_add_left_preview()
        self._gl.update()

    def apply_incremental_solve_display(self, panel_groups: list | None = None) -> None:
        """已废弃语义：等同 ``apply_full_panel_rebuild_display``（勿在加板路径调用）。"""
        self.apply_full_panel_rebuild_display(panel_groups)

    def append_panel_visuals(self, panels: list) -> None:
        """增量挂载板件 mesh（不 ``rebuild_panels``）。"""
        if self._scene is None or self._gl is None:
            return
        for panel in panels or []:
            self._scene.append_panel(panel)

    def remove_panel_visuals_by_ids(self, panel_ids: list[str]) -> None:
        if self._scene is None:
            return
        for pid in panel_ids or []:
            self._scene.remove_panel_by_id(str(pid))

    def refresh_scene(self, solve_result=None) -> None:
        """
        重画当前根 ``Space`` 的逻辑盒 + 挂载板件；若提供 ``solve_result`` 再叠加
        ``solve_result.panel_groups``（经 ``SceneManager.rebuild_panels``）。
        """
        if self._root is None:
            return
        if self._scene is not None and self._gl is not None:
            self._add_left_panel_tool.reset(self._gl)
            self._add_right_panel_tool.reset(self._gl)
            self._scene.clear()
            self._sync_space_placement_ui_metadata()
            self._scene.add_space(self._root)
            self._frame_camera(self._root)
            if solve_result is not None:
                pgs = getattr(solve_result, "panel_groups", None)
                self._scene.rebuild_panels(pgs or [])
            else:
                self._scene.rebuild_panels(getattr(self._root, "panel_groups", []) or [])
        self._sync_add_left_preview()

    def clear_scene(self) -> None:
        if self._scene is not None:
            self._scene.clear()
        if self._gl is not None:
            self._add_left_panel_tool.reset(self._gl)
            self._add_right_panel_tool.reset(self._gl)
        self._root = None
        self._dim_lbl.setText("")

    def scene_manager(self):
        """内部 ``SceneManager``（供命令链 ``ctx["scene_manager"]`` 刷新 GL 场景）。"""
        return self._scene

    def set_tool_mode(self, mode: ToolMode) -> None:
        """切换柜体设计工具状态；不派发命令、不触发 ``dispatch``。"""
        prev = self.tool_mode
        self.tool_mode = mode

        if prev in (ToolMode.ADD_LEFT_PANEL, ToolMode.ADD_RIGHT_PANEL) and mode not in (ToolMode.ADD_LEFT_PANEL, ToolMode.ADD_RIGHT_PANEL):
            if self._gl is not None:
                self._add_left_panel_tool.reset(self._gl)
                self._add_right_panel_tool.reset(self._gl)
        elif mode == ToolMode.ADD_LEFT_PANEL and prev != ToolMode.ADD_LEFT_PANEL:
            if self._gl is not None:
                self._add_left_panel_tool.reset(self._gl)
        elif mode == ToolMode.ADD_RIGHT_PANEL and prev != ToolMode.ADD_RIGHT_PANEL:
            if self._gl is not None:
                self._add_right_panel_tool.reset(self._gl)

        if mode == ToolMode.ADD_LEFT_PANEL:
            self.current_tool = self._add_left_panel_tool
        elif mode == ToolMode.ADD_RIGHT_PANEL:
            self.current_tool = self._add_right_panel_tool
        else:
            self.current_tool = self._null_tool

        if self._gl is not None:
            self._gl.update()

        if self._scene is not None and self._root is not None:
            self._refresh_space_box_colors()

    def _frame_camera(self, space: Space) -> None:
        if not _HAS_PG or self._gl is None:
            return
        x, y, z = space.x, space.y, space.z
        w, h, d = space.width, space.height, space.depth
        cx = x + w * 0.5
        cy = y + h * 0.5
        cz = z + d * 0.5
        self._gl.opts["center"] = pg.Vector(cx, cy, cz)
        span = max(float(w), float(h), float(d), 1.0)
        dist = span * 2.4
        self._gl.opts["distance"] = dist
        elev = 22.0
        azim = 42.0
        self._gl.setCameraPosition(distance=dist, elevation=elev, azimuth=azim)
