# -*- coding: utf-8 -*-
"""管理所有 `SpaceVisual` 与 GL 视图项的挂载/卸载（逻辑空间盒 + 该 Space 下板件）。"""

from __future__ import annotations

from typing import TYPE_CHECKING

from core.space.space_models import Space
from core.space.tree import walk_dfs

from .space_visual import SpaceVisual, is_pyqtgraph_gl_available

if TYPE_CHECKING:
    pass


def _collect_panel_groups_from_tree(root: Space) -> list:
    """遍历整棵树，收集各节点 ``panel_groups``（保持大致 DFS 顺序）。"""
    out: list = []
    for node in walk_dfs(root):
        for g in getattr(node, "panel_groups", None) or []:
            out.append(g)
    return out


def collect_panel_groups_from_tree(root: Space | None) -> list:
    """供 UI 增量刷新：与 ``_collect_panel_groups_from_tree`` 相同，``root`` 为 ``None`` 时返回空列表。"""
    if root is None:
        return []
    return _collect_panel_groups_from_tree(root)


class SceneManager:
    """管理 `SpaceVisual` 集合；不持有 `Space` 业务逻辑。"""

    def __init__(self, gl_view):
        self._gl_view = gl_view
        self._visuals: dict[str, SpaceVisual] = {}
        # 由 ``rebuild_panels`` 挂载的求解板件 GL 项（与 ``SpaceVisual`` 逻辑盒分离）
        self.panel_items: list[tuple[object, object]] = []
        self.panel_wireframe_items: list[object] = []
        self._panel_mesh_by_id: dict[str, tuple[object, object | None]] = {}

    def _clear_solver_panel_items(self) -> None:
        for mesh, edges in self.panel_items:
            if mesh is not None:
                try:
                    self._gl_view.removeItem(mesh)
                except Exception:
                    pass
            if edges is not None:
                try:
                    self._gl_view.removeItem(edges)
                except Exception:
                    pass
        self.panel_items.clear()
        self._panel_mesh_by_id.clear()
        for wf in self.panel_wireframe_items:
            if wf is not None:
                try:
                    self._gl_view.removeItem(wf)
                except Exception:
                    pass
        self.panel_wireframe_items.clear()
        # ``panel_visual.rebuild_panels`` 也会往 ``_rebuild_panel_mesh_items`` 挂 mesh，须 remove 再清列表
        prev = getattr(self._gl_view, "_rebuild_panel_mesh_items", None) or []
        for item in list(prev):
            try:
                self._gl_view.removeItem(item)
            except Exception:
                pass
        self._gl_view._rebuild_panel_mesh_items = []

    def rebuild_panels(self, panel_groups) -> None:
        """
        将 ``panel_groups`` 中的板件画入当前 GL 视图（pyqtgraph：``addItem``；非 VTK ``addActor``）。

        内部流程：

        1. **清除**上一轮由本方法挂载的板件 mesh/edges（``_clear_solver_panel_items``）。
        2. **遍历**所有 ``PanelGroup`` 及其 ``panels``。
        3. 按 ``PanelOrientation`` 将 ``width/height/thickness`` 展开为轴对齐盒，**生成**三角网格
           （``panel_visual.build_panel_mesh``；``VERTICAL_X`` 时 ``Δx=thickness, Δy=height, Δz=width``）。
        4. **挂载**：``gl_view.addItem`` 面片与棱线，并记入 ``panel_items`` 供下次刷新卸下。

        不改动 ``SpaceVisual`` 逻辑空间盒；无 pyqtgraph GL 时直接返回。
        """
        if not is_pyqtgraph_gl_available():
            return
        self._clear_solver_panel_items()
        from .panel_visual import rebuild_panels as _rebuild_panels_gl

        self.panel_items = list(
            _rebuild_panels_gl(self._gl_view, panel_groups or [])
        )
        self._panel_mesh_by_id.clear()
        idx = 0
        for group in panel_groups or []:
            for panel in getattr(group, "panels", []) or []:
                if idx >= len(self.panel_items):
                    break
                pid = str(getattr(panel, "id", "") or "")
                if pid:
                    self._panel_mesh_by_id[pid] = self.panel_items[idx]
                idx += 1

    def append_panel(self, panel: object) -> bool:
        """增量挂载单块板件 GL；已存在同 ``id`` 时跳过。"""
        if not is_pyqtgraph_gl_available():
            return False
        pid = str(getattr(panel, "id", "") or "")
        if not pid or pid in self._panel_mesh_by_id:
            return False
        from .panel_visual import append_panel_mesh

        item = append_panel_mesh(self._gl_view, panel)
        if item is None:
            return False
        self._panel_mesh_by_id[pid] = item
        self.panel_items.append(item)
        return True

    def remove_panel_by_id(self, panel_id: str) -> bool:
        """增量卸下一块板件 GL（``AddBoardCommand.undo`` 等）。"""
        pid = str(panel_id or "")
        if not pid:
            return False
        item = self._panel_mesh_by_id.pop(pid, None)
        if item is None:
            return False
        mesh, edges = item
        if mesh is not None:
            try:
                self._gl_view.removeItem(mesh)
            except Exception:
                pass
        if edges is not None:
            try:
                self._gl_view.removeItem(edges)
            except Exception:
                pass
        try:
            self.panel_items.remove(item)
        except ValueError:
            pass
        prev = getattr(self._gl_view, "_rebuild_panel_mesh_items", None) or []
        gl_items = [m for m in prev if m is not mesh]
        self._gl_view._rebuild_panel_mesh_items = gl_items
        return True

    def rebuild_spaces(self, spaces) -> None:
        """
        用当前 ``Space`` 列表重绑逻辑空间盒（仅 ``SpaceVisual``，不清理 ``rebuild_panels`` 挂载项）。

        ``spaces`` 可为 ``Space`` 可迭代序列（通常与 ``SolveResult.spaces`` 一致）。
        """
        if not is_pyqtgraph_gl_available():
            return
        for vis in list(self._visuals.values()):
            vis.detach(self._gl_view)
        self._visuals.clear()
        for s in spaces or []:
            if s is None:
                continue
            self.add_space(s)

    def add_space(self, space: Space) -> SpaceVisual | None:
        if not is_pyqtgraph_gl_available():
            return None
        self.clear()
        if space is None:
            return None
        first: SpaceVisual | None = None
        for node in walk_dfs(space):
            vis = SpaceVisual(node)
            vis.attach(self._gl_view)
            self._visuals[node.id] = vis
            if first is None:
                first = vis
        self.rebuild_panels(_collect_panel_groups_from_tree(space))
        return first

    def refresh_space_box_styles(self, *, hovered_space_ids: set[str] | None = None) -> None:
        """按 metadata / 悬停刷新所有已挂载空间盒颜色（不重画板件）。"""
        if not is_pyqtgraph_gl_available():
            return
        hs = hovered_space_ids or set()
        for sid, vis in self._visuals.items():
            vis.set_hover_highlight(sid in hs)
            vis.refresh_box_style(self._gl_view)

    def remove_space(self, space: Space) -> None:
        vis = self._visuals.pop(space.id, None)
        if vis is not None:
            vis.detach(self._gl_view)

    def clear(self) -> None:
        self._clear_solver_panel_items()
        for vis in list(self._visuals.values()):
            vis.detach(self._gl_view)
        self._visuals.clear()
