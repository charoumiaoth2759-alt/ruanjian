# -*- coding: utf-8 -*-
"""2D 画户型视图模块

View2D —— 带参考网格的 QGraphicsView，用于"画户型"模式。

参考网格在 **FloorPlanScene.drawBackground** 中绘制。

重要（Qt 6）：若 QGraphicsView 设置了非 NoBrush 的 backgroundBrush，则 QGraphicsView::drawBackground
只会 fillRect，**不会**再调用 scene.drawBackground()，场景里画格子的代码永远不会执行。
因此视图必须用 NoBrush，由场景负责铺底色与网格。

视觉约定：
    - 画板：浅灰底 #ebeef2，大格轻微棋盘纹 #e4e9ef
    - 细网格：scene 步长自适应（基准 20），线色 #8e9bab
    - 大网格：每 5 细格，线色 #5c6b7a
    - 原点轴线 + 刻度标注

交互：
    - 滚轮：以鼠标为锚点缩放（网格密度自适应）
    - 空格 / 中键：拖拽平移
    - set_tool("wall_straight")：启用直墙绘制模式

直墙绘制（仿专业 CAD 软件）：
    - 左键第一点  → 固定起点
    - 移动鼠标   → 正交引线（水平/垂直虚线）辅助对齐；定点后实时预览（带厚度半透明墙体 + 尺寸标注）
    - 房间闭合后 → 正交引线关闭，直至再次左键开始新轮廓
    - Shift 按住 → 角度锁定 0°/45°/90°
    - 左键后续点 → 提交墙段，终点自动成为下一段起点（连续绘制）
    - 双击       → 提交并结束
    - 右键       → 结束当前直墙操作并弹出上下文浮动工具条
    - Esc        → 取消绘制并退出连续绘制（不弹出工具条）

矩形墙（与直墙相同的点击节奏，画的是轴对齐矩形）：
    - 左键第一点 → 矩形一角（网格吸附）
    - 移动鼠标   → 实时预览四面墙 + 内部区域 + 宽高标注
    - 左键第二点 → 提交矩形（对角逐点，网格 / 端点吸附）
    - 双击       → 按当前鼠标位置提交（若有效）并结束工具内状态
    - 右键       → 取消当前矩形操作并弹出上下文浮动工具条
    - Esc        → 取消当前矩形操作
"""

import math
from pathlib import Path

from PySide6.QtCore import QEvent, Qt, QPointF, QRectF, QSizeF, QTimer
from PySide6.QtGui import (
    QAction, QBrush, QColor, QFont, QMouseEvent,
    QPainter, QPainterPath, QPen, QPalette, QPolygonF,
    QPixmap, QTransform,
)
from PySide6.QtWidgets import (
    QFrame, QGraphicsItem, QGraphicsLineItem, QGraphicsPathItem, QGraphicsPolygonItem,
    QGraphicsScene, QGraphicsSimpleTextItem, QGraphicsView,
    QFrame, QHBoxLayout, QPushButton, QWidget,
)

from ui.qt_lifecycle import safe_set_font_point_size_f, safe_set_font_size


def _diban_pixmap_path() -> Path:
    return Path(__file__).resolve().parents[2] / "icons" / "diban.jpg"


_diban_pm_cache: QPixmap | None | str = "unset"  # "unset" | None 失败 | QPixmap


def _get_diban_pixmap() -> QPixmap | None:
    """加载主程序 icons/diban.jpg；失败返回 None（地板走程序生成的木纹）。"""
    global _diban_pm_cache
    if _diban_pm_cache != "unset":
        return _diban_pm_cache if isinstance(_diban_pm_cache, QPixmap) else None
    pm = QPixmap(str(_diban_pixmap_path()))
    if pm.isNull():
        _diban_pm_cache = None
        return None
    _diban_pm_cache = pm
    return pm


# ═══════════════════════════════════════════════════ WallItem
class WallItem(QGraphicsPathItem):
    """已提交的直墙图元 — 使用 QPainterPath 实现 MiterJoin 直角接缝。

    单段墙体为矩形多边形；相邻墙体共享端点，由场景层合并时自动形成直角外轮廓。
    """

    FILL_COLOR  = QColor("#c8cdd8")   # 墙体主色（略深灰，接近参考图）
    OUTER_COLOR = QColor("#8090a8")   # 外边线

    def __init__(self, x1, y1, x2, y2, thickness=120.0, parent=None):
        super().__init__(parent)
        self.x1, self.y1 = x1, y1
        self.x2, self.y2 = x2, y2
        self.thickness = thickness
        self.wall_id: str | None = None
        self._rebuild()
        self.setZValue(10)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, False)

    def _rebuild(self):
        pts = _wall_poly(self.x1, self.y1, self.x2, self.y2, self.thickness)
        path = QPainterPath()
        path.moveTo(QPointF(*pts[0]))
        for p in pts[1:]:
            path.lineTo(QPointF(*p))
        path.closeSubpath()

        # 在两端各加一个正方形填充块，覆盖相邻墙体的斜切缝隙，形成直角接缝
        h = self.thickness / 2.0
        for cx, cy in ((self.x1, self.y1), (self.x2, self.y2)):
            sq = QPainterPath()
            sq.addRect(QRectF(cx - h, cy - h, self.thickness, self.thickness))
            path = path.united(sq)

        self.setPath(path)
        pen = QPen(self.OUTER_COLOR)
        pen.setWidthF(1.0)
        pen.setCosmetic(True)
        pen.setJoinStyle(Qt.PenJoinStyle.MiterJoin)
        pen.setCapStyle(Qt.PenCapStyle.SquareCap)
        self.setPen(pen)
        self.setBrush(QBrush(self.FILL_COLOR))

    def paint(self, painter, option, widget=None):
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)
        # 填充主色
        painter.fillPath(self.path(), QBrush(self.FILL_COLOR))
        # 边线（直角 miter）
        pen = QPen(self.OUTER_COLOR)
        pen.setWidthF(1.2)
        pen.setCosmetic(True)
        pen.setJoinStyle(Qt.PenJoinStyle.MiterJoin)
        pen.setCapStyle(Qt.PenCapStyle.FlatCap)
        # 选中时高亮 (PySide6 StateFlag is an enum, use isSelected())
        if self.isSelected():
            pen.setColor(QColor("#4dc9e4"))
            pen.setWidthF(2.0)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawPath(self.path())
        painter.restore()




# === FloorItem: closed room floor fill with diban.jpg + teal border + dimensions ===
class FloorItem(QGraphicsPathItem):
    """闭合房间地板：icons/diban.jpg 贴图（若缺失则程序木纹）+ 青色内边框 + 内侧尺寸标注 + 房间名/面积标签。"""

    FLOOR_BG    = QColor(220, 195, 155, 220)   # 暖木色底
    FLOOR_DARK  = QColor(190, 165, 120, 180)   # 深色木条
    FLOOR_LIGHT = QColor(235, 215, 175, 160)   # 浅色木条
    BORDER_CLR  = QColor("#4dc9e4")             # 青色内边框（参考图）
    DIM_CLR     = QColor("#3a5070")             # 尺寸标注色
    LABEL_CLR   = QColor("#3a5070")             # 房间名/面积色

    BOARD_H    = 60    # 木板条高度（scene mm）
    BOARD_GAP  = 3     # 木板条间缝（scene mm）

    def __init__(self, points: list, room_name: str = "未命名", parent=None):
        super().__init__(parent)
        self._points = list(points)
        self._room_name = room_name
        path = QPainterPath()
        if points:
            path.moveTo(QPointF(*points[0]))
            for p in points[1:]:
                path.lineTo(QPointF(*p))
            path.closeSubpath()
        self.setPath(path)
        self.setZValue(2)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)
        # 无边线/填充（全由 paint 手绘）
        self.setPen(QPen(Qt.PenStyle.NoPen))
        self.setBrush(Qt.BrushStyle.NoBrush)

    def _area_m2(self) -> float:
        """计算多边形面积（m²），使用 Shoelace 公式，scene单位=mm。"""
        pts = self._points
        n = len(pts)
        area = 0.0
        for i in range(n):
            x1, y1 = pts[i]
            x2, y2 = pts[(i + 1) % n]
            area += x1 * y2 - x2 * y1
        return abs(area) / 2.0 / 1_000_000  # mm² → m²

    def paint(self, painter, option, widget=None):
        painter.save()
        painter.setClipPath(self.path())
        br = self.path().boundingRect()

        pm = _get_diban_pixmap()
        if pm is not None and not pm.isNull():
            brush = QBrush(pm)
            tw, th = float(pm.width()), float(pm.height())
            tile_w, tile_h = 1000.0, 1000.0
            tr = QTransform()
            tr.scale(tile_w / max(tw, 1.0), tile_h / max(th, 1.0))
            brush.setTransform(tr)
            painter.fillPath(self.path(), brush)
        else:
            # ── 1. 木纹底色 ──────────────────────────────────────────
            painter.fillPath(self.path(), QBrush(self.FLOOR_BG))

            # ── 2. 木板条纹（仿实木地板，交错短条）────────────────────
            import random as _rnd
            rng = _rnd.Random(42)
            row = 0
            y = br.top() - (int(br.top()) % (self.BOARD_H + self.BOARD_GAP))
            while y <= br.bottom():
                offset = (row % 2) * 300
                x = br.left() - (int(br.left()) % 600) + offset - 600
                board_w_base = 550
                while x <= br.right():
                    bw = board_w_base + rng.randint(-40, 40)
                    bh = self.BOARD_H - self.BOARD_GAP
                    rect = QRectF(x, y, bw, bh)
                    c = rng.randint(0, 1)
                    col = self.FLOOR_DARK if c else self.FLOOR_LIGHT
                    painter.fillRect(rect, QBrush(col))
                    x += bw + rng.randint(2, 6)
                y += self.BOARD_H + self.BOARD_GAP
                row += 1

        # ── 3. 青色内边框 ─────────────────────────────────────────
        border_pen = QPen(self.BORDER_CLR)
        border_pen.setWidthF(2.0)
        border_pen.setCosmetic(True)
        border_pen.setJoinStyle(Qt.PenJoinStyle.MiterJoin)
        painter.setClipping(False)
        painter.setPen(border_pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawPath(self.path())

        # ── 获取场景→屏幕缩放比，用于计算文字在场景中的合适大小 ──
        # painter.worldTransform() 包含视图变换，m11 是 X 缩放
        sc_x = abs(painter.worldTransform().m11())
        if sc_x < 1e-6:
            sc_x = 1.0
        # 目标：文字在屏幕上约 13px 高 → 场景坐标 = 13/sc_x
        txt_h = max(13.0 / sc_x, 1.0)

        # ── 4. 内部各边尺寸标注 ───────────────────────────────────
        pts = self._points
        n = len(pts)
        dim_pen = QPen(self.DIM_CLR)
        dim_pen.setWidthF(1.0)
        dim_pen.setCosmetic(True)
        # 字体用 pointSizeF = txt_h（场景单位），不用 painter.scale
        dim_font = QFont("Consolas")
        safe_set_font_point_size_f(dim_font, max(txt_h * 0.75, 1.0))
        painter.setFont(dim_font)
        painter.setPen(dim_pen)

        for i in range(n):
            x1, y1 = pts[i]
            x2, y2 = pts[(i + 1) % n]
            seg_len = math.hypot(x2 - x1, y2 - y1)
            if seg_len < txt_h * 4:   # 太短就不标注
                continue
            mx, my = (x1 + x2) / 2, (y1 + y2) / 2
            dx, dy = x2 - x1, y2 - y1
            # 法线方向（向内偏移）
            nx_u, ny_u = -dy / seg_len, dx / seg_len
            off = txt_h * 1.8
            tx, ty = mx + nx_u * off, my + ny_u * off

            angle = math.degrees(math.atan2(dy, dx))
            if angle > 90 or angle < -90:
                angle += 180

            text = f"{seg_len:.0f}"
            painter.save()
            painter.translate(tx, ty)
            painter.rotate(angle)
            # 水平居中：向左偏移文字宽度的一半
            fm = painter.fontMetrics()
            tw = fm.horizontalAdvance(text)
            painter.drawText(QPointF(-tw / 2, txt_h * 0.35), text)
            painter.restore()

        # ── 5. 房间名 + 面积居中标注 ──────────────────────────────
        lbl_font = QFont("Arial")
        safe_set_font_point_size_f(lbl_font, max(txt_h * 1.0, 1.0))
        lbl_font.setBold(True)
        painter.setFont(lbl_font)
        lbl_pen = QPen(self.LABEL_CLR)
        lbl_pen.setWidthF(1.0)
        painter.setPen(lbl_pen)

        area = self._area_m2()
        cx = br.center().x()
        cy = br.center().y()
        line_gap = txt_h * 1.6
        for row_i, text in enumerate([self._room_name, f"{area:.2f}m²"]):
            fm = painter.fontMetrics()
            tw = fm.horizontalAdvance(text)
            ty_off = cy + (row_i - 0.5) * line_gap
            painter.drawText(QPointF(cx - tw / 2, ty_off), text)

        painter.restore()

def _wall_poly(x1, y1, x2, y2, thickness):
    """返回以中心线为轴、两侧各偏移 thickness/2 的四边形顶点列表。"""
    dx, dy = x2 - x1, y2 - y1
    L = math.hypot(dx, dy)
    if L < 1e-6:
        return [(x1, y1)] * 4
    nx, ny = -dy / L, dx / L       # 法线（左侧）
    h = thickness / 2.0
    ox, oy = nx * h, ny * h
    return [
        (x1 + ox, y1 + oy), (x2 + ox, y2 + oy),
        (x2 - ox, y2 - oy), (x1 - ox, y1 - oy),
    ]


# ═══════════════════════════════════════════════════ View2D
class View2D(QGraphicsView):
    """带多级参考网格的 2D 画户型视图。"""

    # ── 网格参数 ──────────────────────────────────────────────────
    MINOR_SIZE   = 20
    MAJOR_FACTOR = 5
    MAJOR_SIZE   = MINOR_SIZE * MAJOR_FACTOR   # 100

    # ── 颜色（参考制图软件：浅蓝灰底 + 清晰蓝灰参考网格线）────────────────
    BG_COLOR     = QColor("#dde2ec")   # 画板浅蓝灰底（匹配参考图）
    BG_STRIPE    = QColor("#d6dce8")   # 大格棋盘另一色（极弱对比）
    MINOR_COLOR  = QColor("#8895ae")   # 细网格蓝灰色
    MAJOR_COLOR  = QColor("#4a5a78")   # 大网格深蓝灰
    AXIS_COLOR   = QColor("#4a5a78")   # 原点轴线
    LABEL_COLOR  = QColor("#5a6a88")   # 刻度文字

    # ── 缩放限制 ──────────────────────────────────────────────────
    ZOOM_MIN    = 0.012
    ZOOM_MAX    = 1500.0
    ZOOM_STEP   = 1.15

    # 自适应网格阈值：
    #   _GRID_MIN_PX：细格像素小于此值时换大一级
    #   _GRID_MAX_PX：细格像素大于此值时换小一级（放大限制，避免格太密）
    _GRID_MIN_PX = 10
    _GRID_MAX_PX = 80

    # ── 墙体绘制参数 ──────────────────────────────────────────────
    WALL_THICKNESS = 120          # 默认墙厚（scene 单位 = mm）
    WALL_SNAP      = 20           # 吸附格 = MINOR_SIZE

    _PRV_FILL   = QColor(74, 144, 217, 50)    # 预览墙体填充
    _PRV_STROKE = QColor(74, 144, 217, 210)   # 预览墙体边线 / 标注
    _PRV_DASH   = QColor(74, 144, 217, 140)   # 中心虚线

    def __init__(self, scene: QGraphicsScene, parent=None):
        super().__init__(scene, parent)

        # 工具状态必须在首帧 viewport 事件前就绪（viewport().setAutoFillBackground 等会触发 viewportEvent）
        self._tool: str = "none"  # "none" | "wall_straight" | "wall_rect"
        self._wall_start = None
        self._first_wall_pt = None
        self._session_walls = []
        self._committed_pts = []
        self._preview_items = []
        self._shift_lock = False
        self._mouse_scene = QPointF(0, 0)
        self._snap_to_pt = None
        self._ALIGN_SNAP_PX = 16
        self._CLOSE_SNAP_PX = 20
        self._suppress_cursor_ortho_after_close = False
        self._rect_start: QPointF | None = None

        # 矩形墙绘制状态
        self.draw_mode = ""
        self.is_drawing_rect = False

        self.rect_start_pos = None
        self.rect_end_pos = None

        # 墙数据
        self.walls = []
        self.wall_list = []
        self.temp_rect_items = []

        # Qt 6：视图 backgroundBrush 若为实色，C++ 的 QGraphicsView::drawBackground 只会 fillRect，
        # 不会调用 scene.drawBackground()，网格必须在场景里画 → 此处必须为 NoBrush。
        self.setBackgroundBrush(QBrush(Qt.BrushStyle.NoBrush))

        # !! 关键：禁用 viewport 自动填充，否则会覆盖 drawBackground 绘制的网格
        self.setAutoFillBackground(False)
        self.viewport().setAutoFillBackground(False)

        # FullViewportUpdate：滚动/缩放时强制重绘整个视口（保证网格正确刷新）
        self.setViewportUpdateMode(QGraphicsView.ViewportUpdateMode.FullViewportUpdate)

        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setRenderHints(
            QPainter.RenderHint.Antialiasing |
            QPainter.RenderHint.TextAntialiasing
        )
        self.setDragMode(QGraphicsView.DragMode.RubberBandDrag)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setMouseTracking(True)
        self.viewport().setMouseTracking(True)

        # 禁用背景缓存，保证 drawBackground 每次参与绘制
        self.setCacheMode(QGraphicsView.CacheModeFlag.CacheNone)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

        # 场景范围
        scene.setSceneRect(-50_000, -50_000, 100_000, 100_000)

        # 状态
        self._zoom          = 1.0
        self._space_pressed = False
        self._label_font = QFont("Consolas")
        safe_set_font_size(self._label_font, 8)
        self._camera_initialized = False

    def drawBackground(self, painter: QPainter, rect: QRectF) -> None:
        """显式把背景绘制交给 scene（不依赖 C++ 里 backgroundBrush==NoBrush 的分支）。

        部分 PySide6 / 样式组合下，仅靠 NoBrush 仍可能走不到场景背景；由视图转发最稳。
        """
        sc = self.scene()
        if sc is not None:
            sc.drawBackground(painter, rect)

    def paintEvent(self, event):
        super().paintEvent(event)
        painter = QPainter(self.viewport())
        if self.draw_mode == "rect_wall" and self.is_drawing_rect:
            if self.rect_start_pos is not None and self.rect_end_pos is not None:
                vp1 = self.mapFromScene(self.rect_start_pos)
                vp2 = self.mapFromScene(self.rect_end_pos)
                x1 = vp1.x()
                y1 = vp1.y()
                x2 = vp2.x()
                y2 = vp2.y()
                rect = QRectF(
                    min(x1, x2),
                    min(y1, y2),
                    abs(x2 - x1),
                    abs(y2 - y1),
                )
                painter.setPen(QPen(Qt.GlobalColor.red, 2))
                painter.drawRect(rect)
        painter.end()

    def _reset_viewport_camera(self):
        """首屏用 fitInView 框住一块包含原点的场景区域，避免 centerOn 后视口尺寸异常时只见纯色。"""
        self.resetTransform()
        self._zoom = 1.0
        # 约 20m×15m 的制图区（scene 单位 mm），KeepAspectRatio 适配任意窗口比例
        # 加大范围使默认网格格子更大、稀疏，与参考图一致（每大格约 1m）
        self.fitInView(
            QRectF(-10000, -7500, 20000, 15000),
            Qt.AspectRatioMode.KeepAspectRatio,
        )
        sx = abs(self.transform().m11())
        self._zoom = sx if sx > 1e-8 else 1.0
        self.viewport().update()

    def showEvent(self, event):
        super().showEvent(event)
        if not self._camera_initialized and self.width() > 20 and self.height() > 20:
            self._reset_viewport_camera()
            self._camera_initialized = True
        self.viewport().update()   # Windows 首帧强制重绘网格
        # 布局晚一帧才稳定时补一次对准原点，避免整屏落在“无格线”的空白带
        QTimer.singleShot(0, self._deferred_viewport_refresh)

    def _deferred_viewport_refresh(self):
        if not self.isVisible():
            return
        if self.width() > 20 and self.height() > 20:
            if not self._camera_initialized:
                self._reset_viewport_camera()
                self._camera_initialized = True
            else:
                self.viewport().update()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if not self._camera_initialized and self.width() > 50 and self.height() > 50:
            self._reset_viewport_camera()
            self._camera_initialized = True
        self.viewport().update()

    def _mouse_event_to_scene(self, event) -> QPointF:
        """将视口坐标转为场景坐标。

        PySide6 的 QGraphicsView.mapToScene 无 QPointF 重载，须用整型 x,y。
        """
        p = event.position()
        return self.mapToScene(int(round(p.x())), int(round(p.y())))

    def create_wall(self, start, end):
        wall = {
            "start": start,
            "end": end,
            "thickness": 120,
            "height": 2800,
        }

        self.wall_list.append(wall)

        x1, y1 = start[0], start[1]
        x2, y2 = end[0], end[1]
        self.add_wall_line(x1, y1, x2, y2)
        self.update()

    # ─────────────────────────────────── 工具接口
    def set_tool(self, tool: str) -> None:
        """切换工具。tool: 'none' | 'wall_straight' | 'wall_rect'"""
        self._end_draw()
        self._tool = tool
        if tool != "wall_rect":
            self.draw_mode = ""
            self.is_drawing_rect = False
        if tool in ("wall_straight", "wall_rect"):
            self.setDragMode(QGraphicsView.DragMode.NoDrag)
            self.setCursor(Qt.CursorShape.CrossCursor)
        else:
            self.setDragMode(QGraphicsView.DragMode.RubberBandDrag)
            self.setCursor(Qt.CursorShape.ArrowCursor)

    def on_rect_wall_clicked(self):
        self.draw_mode = "rect_wall"
        self.is_drawing_rect = False
        print("矩形墙模式")

    def _end_draw(self, *, after_polygon_close: bool = False):
        """结束连续绘制，清理预览，重置本次绘制会话。"""
        self._wall_start    = None
        self._first_wall_pt = None
        self._session_walls = []
        self._snap_to_pt    = None
        self._rect_start    = None
        self._clear_preview()
        sc = self.scene()
        if sc is not None:
            for it in self.temp_rect_items:
                if it.scene() is sc:
                    sc.removeItem(it)
        self.temp_rect_items.clear()
        self._suppress_cursor_ortho_after_close = bool(after_polygon_close)

    def _clear_preview(self):
        sc = self.scene()
        if sc is None:
            self._preview_items.clear()
            return
        for item in self._preview_items:
            if item.scene() is sc:
                sc.removeItem(item)
        self._preview_items.clear()

    # ─────────────────────────────────── 吸附 & 角度锁
    def _snap(self, p: QPointF) -> QPointF:
        g = self.WALL_SNAP
        return QPointF(round(p.x() / g) * g, round(p.y() / g) * g)

    def _lock_angle(self, start: QPointF, raw: QPointF) -> QPointF:
        """Shift 模式：将 raw 锁定到距 start 最近的 90° 正交方向（水平或垂直）。"""
        dx, dy = raw.x() - start.x(), raw.y() - start.y()
        # 只允许 0°/90°/180°/270°：选择 |dx| 和 |dy| 中较大的轴
        if abs(dx) >= abs(dy):
            # 水平方向
            return QPointF(raw.x(), start.y())
        else:
            # 垂直方向
            return QPointF(start.x(), raw.y())

    def _align_snap_radius(self) -> float:
        """以当前缩放换算对齐吸附半径（场景单位）。"""
        inv = 1.0 / max(self.transform().m11(), 1e-6)
        return self._ALIGN_SNAP_PX * inv

    def _close_snap_radius(self) -> float:
        inv = 1.0 / max(self.transform().m11(), 1e-6)
        return self._CLOSE_SNAP_PX * inv

    def _find_snap_point(self, p: QPointF) -> QPointF | None:
        """在已提交端点中找到最近的对齐点，若在半径内返回该点，否则返回 None。"""
        r = self._align_snap_radius()
        best_d = r
        best_pt = None
        for (cx, cy) in self._committed_pts:
            d = math.hypot(p.x() - cx, p.y() - cy)
            if d < best_d:
                best_d = d
                best_pt = QPointF(cx, cy)
        # 也检查当前绘制的第一点（用于闭合）
        if self._first_wall_pt is not None:
            fp = self._first_wall_pt
            d = math.hypot(p.x() - fp.x(), p.y() - fp.y())
            if d < self._close_snap_radius():
                best_pt = fp
        return best_pt

    def _effective_end(self, raw: QPointF) -> QPointF:
        """返回经过角度锁 + 端点对齐 + 网格吸附处理后的终点。"""
        p = raw
        if self._shift_lock and self._wall_start is not None:
            p = self._lock_angle(self._wall_start, p)
        # 优先：端点对齐吸附（比网格吸附更精确）
        snap_pt = self._find_snap_point(p)
        if snap_pt is not None:
            self._snap_to_pt = snap_pt
            return snap_pt
        self._snap_to_pt = None
        return self._snap(p)

    def _rect_opposite_corner(self, raw: QPointF) -> QPointF:
        """矩形墙第二点：端点吸附 + 网格吸附（无 Shift 角度锁，避免对角退化成线段）。"""
        p = raw
        snap_pt = self._find_snap_point(p)
        if snap_pt is not None:
            self._snap_to_pt = snap_pt
            return snap_pt
        self._snap_to_pt = None
        return self._snap(p)

    def _ortho_guide_extent(self) -> float:
        sc = self.scene()
        if sc is None:
            return 200_000.0
        r = sc.sceneRect()
        return max(r.width(), r.height()) * 2.0

    def _append_ortho_guide_cross(self, sc: QGraphicsScene, cx: float, cy: float) -> None:
        """在 (cx, cy) 处追加一组正交无限长虚线（场景坐标）。青绿色虚线，参考图样式。"""
        extent = self._ortho_guide_extent()
        guide_pen = QPen(QColor(62, 207, 160, 180))   # 青绿 #3ecfa0
        guide_pen.setCosmetic(True)
        guide_pen.setStyle(Qt.PenStyle.DashLine)
        guide_pen.setDashPattern([6, 4])
        guide_pen.setWidthF(1.2)
        gh = sc.addLine(cx - extent, cy, cx + extent, cy, guide_pen)
        gv = sc.addLine(cx, cy - extent, cx, cy + extent, guide_pen)
        gh.setZValue(5)
        gv.setZValue(5)
        self._preview_items.extend((gh, gv))

    def _preview_cursor_ortho_guides_only(self, scene_pos: QPointF) -> None:
        """直墙工具下尚未点起点：仅绘制过光标（经端点/网格吸附）的正交引线。"""
        self._clear_preview()
        sc = self.scene()
        if sc is None:
            return
        p = self._effective_end(scene_pos)
        self._append_ortho_guide_cross(sc, p.x(), p.y())

    # ─────────────────────────────────── 预览绘制
    def _rebuild_preview(self, end_raw: QPointF):
        """清除旧预览，在 scene 里重建预览图元。包含：
        - 正交引线（过当前吸附终点 + 本段起点，水平/垂直虚线）
        - 端点对齐吸附指示（绿色高亮圆圈 + 对齐虚线）
        - 带厚度墙体预览多边形 + 尺寸标注
        - 闭合预览（接近起点时提示闭合）
        """
        self._clear_preview()
        sc = self.scene()
        if sc is None or self._wall_start is None:
            return

        s = self._wall_start
        e = self._effective_end(end_raw)
        dx, dy = e.x() - s.x(), e.y() - s.y()
        length = math.hypot(dx, dy)
        inv = 1.0 / max(self.transform().m11(), 1e-6)

        # ─── 1. 正交引线（终点 + 起点）──────────────────────────────
        self._append_ortho_guide_cross(sc, e.x(), e.y())
        self._append_ortho_guide_cross(sc, s.x(), s.y())

        # ─── 2. 端点对齐指示 ──────────────────────────────────────
        if self._snap_to_pt is not None:
            sp = self._snap_to_pt
            snap_r = 10 * inv
            is_close = (self._first_wall_pt is not None and
                        abs(sp.x() - self._first_wall_pt.x()) < 1 and
                        abs(sp.y() - self._first_wall_pt.y()) < 1)
            align_color = QColor(0, 200, 100, 230) if is_close else QColor(255, 165, 0, 220)
            align_pen = QPen(align_color)
            align_pen.setCosmetic(True)
            align_pen.setWidthF(2.0)
            # 高亮圆圈
            circle = sc.addEllipse(sp.x()-snap_r, sp.y()-snap_r,
                                   snap_r*2, snap_r*2, align_pen,
                                   QBrush(QColor(align_color.red(),
                                                 align_color.green(),
                                                 align_color.blue(), 40)))
            circle.setZValue(97)
            self._preview_items.append(circle)
            # 对齐延伸虚线（从当前墙段起点到对齐点的连线）
            if is_close:
                close_pen = QPen(QColor(0, 200, 100, 180))
                close_pen.setCosmetic(True)
                close_pen.setStyle(Qt.PenStyle.DashLine)
                cl_line = sc.addLine(s.x(), s.y(), sp.x(), sp.y(), close_pen)
                cl_line.setZValue(6)
                self._preview_items.append(cl_line)

        # ─── 3. 鼠标位置：* 星号标记 ──────────────────────────────
        arm = 7 * inv
        star_pen = QPen(QColor(62, 207, 160, 230))   # 青绿色
        star_pen.setWidthF(1.5)
        star_pen.setCosmetic(True)
        # 三条线组成 * 号：水平、垂直、斜45°两条
        for angle_deg in (0, 90, 45, 135):
            ar = math.radians(angle_deg)
            cx2, cy2 = arm * math.cos(ar), arm * math.sin(ar)
            self._preview_items.append(
                sc.addLine(e.x()-cx2, e.y()-cy2, e.x()+cx2, e.y()+cy2, star_pen)
            )
        for it in self._preview_items[-4:]:
            it.setZValue(96)

        if length < 1:
            return

        # ─── 4. 墙体预览（带厚度多边形）──────────────────────────
        pts = _wall_poly(s.x(), s.y(), e.x(), e.y(), self.WALL_THICKNESS)
        poly = sc.addPolygon(
            QPolygonF([QPointF(x, y) for x, y in pts]),
            QPen(self._PRV_STROKE, 1.0, Qt.PenStyle.SolidLine,
                 Qt.PenCapStyle.FlatCap, Qt.PenJoinStyle.MiterJoin),
            QBrush(self._PRV_FILL),
        )
        poly.pen().setCosmetic(True)
        poly.setZValue(90)
        self._preview_items.append(poly)

        # ─── 5. 中心虚线 ──────────────────────────────────────────
        dash_pen = QPen(self._PRV_DASH)
        dash_pen.setCosmetic(True)
        dash_pen.setStyle(Qt.PenStyle.DashLine)
        cl = sc.addLine(s.x(), s.y(), e.x(), e.y(), dash_pen)
        cl.setZValue(92)
        self._preview_items.append(cl)

        # ─── 6. 起点：空心小圆圈 ──────────────────────────────────
        r = 5 * inv
        dot_pen = QPen(QColor(62, 207, 160, 220))
        dot_pen.setWidthF(1.5)
        dot_pen.setCosmetic(True)
        dot = sc.addEllipse(
            s.x()-r, s.y()-r, r*2, r*2,
            dot_pen, QBrush(Qt.BrushStyle.NoBrush),   # 空心
        )
        dot.setZValue(93)
        self._preview_items.append(dot)

        # ─── 7. 尺寸标注 ──────────────────────────────────────────
        self._draw_dim(sc, s, e, length, dx, dy, inv)

        # ─── 8. Shift 矩形模式：显示待补全的矩形虚线框 ───────────────
        if self._shift_lock and self._first_wall_pt is not None:
            fp = self._first_wall_pt
            # 矩形由起点 fp 和当前终点 e 确定对角
            rect_pts = [
                QPointF(fp.x(), fp.y()),
                QPointF(e.x(),  fp.y()),
                QPointF(e.x(),  e.y()),
                QPointF(fp.x(), e.y()),
                QPointF(fp.x(), fp.y()),   # 闭合
            ]
            rect_pen = QPen(QColor(62, 207, 160, 100))
            rect_pen.setCosmetic(True)
            rect_pen.setStyle(Qt.PenStyle.DashLine)
            rect_pen.setDashPattern([5, 4])
            rect_pen.setWidthF(1.0)
            for i in range(4):
                ln = sc.addLine(
                    rect_pts[i].x(), rect_pts[i].y(),
                    rect_pts[i+1].x(), rect_pts[i+1].y(),
                    rect_pen,
                )
                ln.setZValue(7)
                self._preview_items.append(ln)
            # 对角顶点小圆圈提示
            cr = 4 * inv
            for pt in (rect_pts[1], rect_pts[3]):
                corner_pen = QPen(QColor(62, 207, 160, 160))
                corner_pen.setCosmetic(True)
                corner_pen.setWidthF(1.2)
                circ = sc.addEllipse(
                    pt.x()-cr, pt.y()-cr, cr*2, cr*2,
                    corner_pen, QBrush(Qt.BrushStyle.NoBrush),
                )
                circ.setZValue(8)
                self._preview_items.append(circ)

    def _draw_dim(self, sc, s, e, length, dx, dy, inv):
        """尺寸标注：蓝色填充矩形 + 白色数字 + 独立 mm 标签（参考图样式）。"""
        L = length

        # ── 标注位置：鼠标（终点 e）旁边，水平偏右 ──────────────────
        # 参考图中标注框紧贴鼠标右侧
        pad_x = 16 * inv     # 标注框距鼠标的偏移
        pad_y = -8 * inv

        font_h = max(min(11.0 * inv, 40.0), 0.10)

        # ── 数值文字（白色） ─────────────────────────────────────────
        num_text = f"{length:.0f}"
        num_item = sc.addSimpleText(num_text)
        num_font = QFont("Consolas")
        num_font.setBold(True)
        safe_set_font_size(num_font, 10)
        num_item.setFont(num_font)
        num_item.setScale(font_h)
        num_item.setBrush(QBrush(QColor(255, 255, 255, 255)))

        num_br   = num_item.boundingRect()
        num_w    = num_br.width()  * font_h
        num_h    = num_br.height() * font_h
        box_pad  = 3 * inv

        # ── 蓝底矩形 ────────────────────────────────────────────────
        box_w = num_w + box_pad * 2
        box_h = num_h + box_pad * 1.2
        box_x = e.x() + pad_x
        box_y = e.y() + pad_y - box_h * 0.5

        box = sc.addRect(
            QRectF(box_x, box_y, box_w, box_h),
            QPen(QColor(40, 100, 200, 180), 0),
            QBrush(QColor(40, 110, 220, 230)),
        )
        box.setZValue(94)
        self._preview_items.append(box)

        # 数字居中放入蓝框
        num_item.setPos(box_x + box_pad, box_y + box_pad * 0.6)
        num_item.setZValue(95)
        self._preview_items.append(num_item)

        # ── mm 单位标签（灰色，紧跟蓝框右侧）───────────────────────
        mm_item = sc.addSimpleText("mm")
        mm_font = QFont("Arial")
        safe_set_font_size(mm_font, 9)
        mm_item.setFont(mm_font)
        mm_scale = font_h * 0.85
        mm_item.setScale(mm_scale)
        mm_item.setBrush(QBrush(QColor(80, 100, 130, 200)))
        mm_item.setPos(box_x + box_w + 3 * inv, box_y + box_pad * 0.6)
        mm_item.setZValue(95)
        self._preview_items.append(mm_item)

    def add_wall_line(self, x1: float, y1: float, x2: float, y2: float) -> bool:
        """添加一段直墙：WallItem + Room + 对齐端点（直墙工具与矩形墙共用）。"""
        sc = self.scene()
        if sc is None:
            return False
        if math.hypot(x2 - x1, y2 - y1) < 2:
            return False

        item = WallItem(x1, y1, x2, y2, self.WALL_THICKNESS)
        sc.addItem(item)

        room = sc.property("room")
        if room is not None:
            sw = room.add_wall(x1, y1, x2, y2, self.WALL_THICKNESS)
            item.wall_id = sw.wall_id

        for pt in ((x1, y1), (x2, y2)):
            if pt not in self._committed_pts:
                self._committed_pts.append(pt)
        return True

    # ─────────────────────────────────── 提交墙体
    def _commit_wall(self, end_raw: QPointF):
        """固化一段墙体到 scene 和 Room 数据模型，并继续连续绘制。
        - 记录端点到对齐辅助列表
        - 检测是否闭合：终点接近本次绘制第一个起点时自动填充地板
        - Shift 模式：强制正交，闭合时自动补全矩形
        """
        sc = self.scene()
        if sc is None or self._wall_start is None:
            return

        s = self._wall_start
        e = self._effective_end(end_raw)

        # ── Shift 矩形模式：尝试闭合时自动补全矩形 ─────────────────
        # 条件：shift 按住 + 已有 ≥1 段墙 + 终点接近第一个起点
        if (self._shift_lock
                and self._first_wall_pt is not None
                and len(self._session_walls) >= 1):
            fp = self._first_wall_pt
            close_r = self._CLOSE_SNAP_PX * 2 / max(self.transform().m11(), 1e-6)
            if math.hypot(e.x() - fp.x(), e.y() - fp.y()) < close_r:
                self._commit_rect_close(sc, s, fp)
                return

        if math.hypot(e.x()-s.x(), e.y()-s.y()) < 2:
            return   # 过短忽略（几乎重合才丢弃）

        self._clear_preview()

        if not self.add_wall_line(s.x(), s.y(), e.x(), e.y()):
            return

        # 本次绘制会话记录
        self._session_walls.append((s.x(), s.y(), e.x(), e.y()))
        if self._first_wall_pt is None:
            self._first_wall_pt = QPointF(s.x(), s.y())

        # ── 闭合检测（普通模式）──────────────────────────────────────
        fp = self._first_wall_pt
        if fp is not None and math.hypot(e.x()-fp.x(), e.y()-fp.y()) < self._CLOSE_SNAP_PX * 2 / max(self.transform().m11(), 1e-6):
            self._fill_floor(sc)
            self._end_draw(after_polygon_close=True)
            return

        # 连续绘制：终点成为下一段起点
        self._wall_start = e
        self._snap_to_pt = None
        self._rebuild_preview(e)

    def _commit_rect_close(self, sc: QGraphicsScene, cur_end: QPointF, first_pt: QPointF):
        """Shift 矩形模式下闭合：
        根据已绘制的墙段和起点，自动补全剩余边使房间成为矩形。
        策略：取起点和当前终点（cur_end）为矩形的对角点，
        补出两条正交边后闭合。
        """
        s = self._wall_start
        fp = first_pt

        # 当前终点对齐到起点的正交方向
        e = self._effective_end(self._mouse_scene)

        # 已有墙段的包围盒角点：用第一段起点和当前点构成矩形
        # 矩形四角：fp, (e.x, fp.y), e, (fp.x, e.y)
        corners = [
            QPointF(fp.x(), fp.y()),
            QPointF(e.x(),  fp.y()),
            QPointF(e.x(),  e.y()),
            QPointF(fp.x(), e.y()),
        ]

        # 找出已有墙段走过的最后一个点（连续路径的尾）
        # 从已有 session_walls 提取完整路径
        path_pts: list[QPointF] = []
        if self._session_walls:
            x1, y1, _, _ = self._session_walls[0]
            path_pts.append(QPointF(x1, y1))
            for (_, _, x2, y2) in self._session_walls:
                path_pts.append(QPointF(x2, y2))
        path_pts.append(s)  # 当前段起点

        # 把路径末端对齐到矩形顶点
        # 找矩形中与当前 s 最近的顶点作为"刚画到的角"
        last = path_pts[-1]
        nearest_corner_idx = min(range(4), key=lambda i: math.hypot(
            corners[i].x() - last.x(), corners[i].y() - last.y()))

        # 补充缺少的边，按矩形顺序绘制剩余段回到 corners[0]（= fp）
        # 从 nearest_corner_idx+1 开始，回到 0
        pts_to_add: list[QPointF] = []
        idx = nearest_corner_idx
        while True:
            idx = (idx + 1) % 4
            pts_to_add.append(corners[idx])
            if idx == 0:
                break

        cur = last
        all_walls: list[tuple] = []
        for pt in pts_to_add:
            if math.hypot(pt.x()-cur.x(), pt.y()-cur.y()) > 2:
                if self.add_wall_line(cur.x(), cur.y(), pt.x(), pt.y()):
                    all_walls.append((cur.x(), cur.y(), pt.x(), pt.y()))
            cur = pt

        self._session_walls.extend(all_walls)
        self._fill_floor(sc)
        self._end_draw(after_polygon_close=True)

    def _fill_floor(self, sc: QGraphicsScene):
        """根据本次绘制的墙体中心线端点列表，填充闭合多边形地板。"""
        if len(self._session_walls) < 2:
            return
        pts = []
        for (x1, y1, x2, y2) in self._session_walls:
            if not pts:
                pts.append((x1, y1))
            pts.append((x2, y2))
        if len(pts) < 3:
            return
        if math.hypot(pts[-1][0]-pts[0][0], pts[-1][1]-pts[0][1]) < 5:
            pts = pts[:-1]
        room = sc.property("room")
        room_name = getattr(room, "name", "未命名") if room else "未命名"
        floor = FloorItem(pts, room_name=room_name)
        sc.addItem(floor)

    # ─────────────────────────────────── 矩形墙工具
    def _rebuild_rect_preview(self, end_raw: QPointF):
        """矩形墙工具：实时预览矩形框 + 宽高尺寸标注。"""
        self._clear_preview()
        sc = self.scene()
        if sc is None or self._rect_start is None:
            return

        s = self._rect_start
        e = self._rect_opposite_corner(end_raw)
        inv = 1.0 / max(self.transform().m11(), 1e-6)

        x1, y1 = s.x(), s.y()
        x2, y2 = e.x(), e.y()
        if abs(x2 - x1) < 2 and abs(y2 - y1) < 2:
            # 刚按下尚未拉开：仍画起点，避免误以为无响应
            r = 5 * inv
            dot_pen = QPen(QColor(62, 207, 160, 220))
            dot_pen.setWidthF(1.5)
            dot_pen.setCosmetic(True)
            dot = sc.addEllipse(x1 - r, y1 - r, r * 2, r * 2, dot_pen, QBrush(Qt.BrushStyle.NoBrush))
            dot.setZValue(93)
            self._preview_items.append(dot)
            return

        w = abs(x2 - x1)
        h = abs(y2 - y1)

        # ── 矩形预览：4面墙的带厚度多边形 ──────────────────────────
        corners = [
            (min(x1,x2), min(y1,y2)),
            (max(x1,x2), min(y1,y2)),
            (max(x1,x2), max(y1,y2)),
            (min(x1,x2), max(y1,y2)),
        ]
        wall_fill  = QColor(74, 144, 217, 55)
        wall_stroke = QColor(74, 144, 217, 200)
        for i in range(4):
            ax, ay = corners[i]
            bx, by = corners[(i+1) % 4]
            pts = _wall_poly(ax, ay, bx, by, self.WALL_THICKNESS)
            poly = sc.addPolygon(
                QPolygonF([QPointF(px, py) for px, py in pts]),
                QPen(wall_stroke, 1.0, Qt.PenStyle.SolidLine,
                     Qt.PenCapStyle.FlatCap, Qt.PenJoinStyle.MiterJoin),
                QBrush(wall_fill),
            )
            poly.pen().setCosmetic(True)
            poly.setZValue(90)
            self._preview_items.append(poly)

        # ── 内部填充（浅蓝半透明）────────────────────────────────
        inner = sc.addRect(
            QRectF(min(x1,x2), min(y1,y2), w, h),
            QPen(Qt.PenStyle.NoPen),
            QBrush(QColor(74, 144, 217, 18)),
        )
        inner.setZValue(89)
        self._preview_items.append(inner)

        # ── 起点小圆圈 ────────────────────────────────────────────
        r = 5 * inv
        dot_pen = QPen(QColor(62, 207, 160, 220))
        dot_pen.setWidthF(1.5)
        dot_pen.setCosmetic(True)
        dot = sc.addEllipse(x1-r, y1-r, r*2, r*2, dot_pen, QBrush(Qt.BrushStyle.NoBrush))
        dot.setZValue(93)
        self._preview_items.append(dot)

        # ── 终点 + 字标记 ──────────────────────────────────────────
        arm = 6 * inv
        star_pen = QPen(QColor(62, 207, 160, 220))
        star_pen.setWidthF(1.5)
        star_pen.setCosmetic(True)
        for adeg in (0, 90):
            ar = math.radians(adeg)
            self._preview_items.append(sc.addLine(
                e.x()-arm*math.cos(ar), e.y()-arm*math.sin(ar),
                e.x()+arm*math.cos(ar), e.y()+arm*math.sin(ar), star_pen))
        for it in self._preview_items[-2:]:
            it.setZValue(96)

        # ── 宽度标注（上方）──────────────────────────────────────
        self._draw_rect_dim(sc, inv,
            QPointF((x1+x2)/2, min(y1,y2)),   # 中点
            w, horizontal=True)

        # ── 高度标注（左侧，竖排）────────────────────────────────
        self._draw_rect_dim(sc, inv,
            QPointF(min(x1,x2), (y1+y2)/2),   # 中点
            h, horizontal=False)

    def _draw_rect_dim(
        self,
        sc,
        inv,
        mid: QPointF,
        value: float,
        horizontal: bool,
        items_dest: list | None = None,
    ):
        """在 mid 处绘制蓝框白字尺寸标注，horizontal 决定文字是否旋转。"""
        bucket = self._preview_items if items_dest is None else items_dest
        font_h = max(min(11.0 * inv, 40.0), 0.10)
        num_text = f"{value:.0f}"

        num_item = sc.addSimpleText(num_text)
        num_font = QFont("Consolas")
        num_font.setBold(True)
        safe_set_font_size(num_font, 10)
        num_item.setFont(num_font)
        num_item.setScale(font_h)
        num_item.setBrush(QBrush(QColor(255, 255, 255)))

        br   = num_item.boundingRect()
        nw   = br.width() * font_h
        nh   = br.height() * font_h
        pad  = 3 * inv
        bw   = nw + pad * 2
        bh   = nh + pad * 1.2

        # 蓝框位置：水平标注在中点上方，垂直标注在中点左侧
        if horizontal:
            box_x = mid.x() - bw / 2
            box_y = mid.y() - bh - 6 * inv
        else:
            box_x = mid.x() - bw - 6 * inv
            box_y = mid.y() - bh / 2

        box = sc.addRect(
            QRectF(box_x, box_y, bw, bh),
            QPen(Qt.PenStyle.NoPen),
            QBrush(QColor(40, 110, 220, 230)),
        )
        box.setZValue(94)
        bucket.append(box)

        num_item.setPos(box_x + pad, box_y + pad * 0.6)
        if not horizontal:
            # 竖向尺寸旋转 -90°，绕左上角旋转后平移
            num_item.setRotation(-90)
            num_item.setPos(box_x + pad * 0.6, box_y + bh - pad)
        num_item.setZValue(95)
        bucket.append(num_item)

        # mm 单位
        mm_item = sc.addSimpleText("mm")
        mm_font = QFont("Arial")
        safe_set_font_size(mm_font, 9)
        mm_item.setFont(mm_font)
        mm_item.setScale(font_h * 0.85)
        mm_item.setBrush(QBrush(QColor(80, 100, 130, 200)))
        if horizontal:
            mm_item.setPos(box_x + bw + 3 * inv, box_y + pad * 0.6)
        else:
            mm_item.setPos(box_x + bw + 3 * inv, box_y + pad * 0.6)
        mm_item.setZValue(95)
        bucket.append(mm_item)

    def _commit_rect_wall(self, end_raw: QPointF):
        """矩形墙工具：第二点左键提交 4 面墙 + 地板。"""
        sc = self.scene()
        if sc is None or self._rect_start is None:
            return

        s = self._rect_start
        e = self._rect_opposite_corner(end_raw)

        x1, y1 = s.x(), s.y()
        x2, y2 = e.x(), e.y()
        if abs(x2 - x1) < 2 or abs(y2 - y1) < 2:
            return

        self._clear_preview()
        corners = [
            (min(x1,x2), min(y1,y2)),
            (max(x1,x2), min(y1,y2)),
            (max(x1,x2), max(y1,y2)),
            (min(x1,x2), max(y1,y2)),
        ]

        room = sc.property("room")
        for i in range(4):
            ax, ay = corners[i]
            bx, by = corners[(i+1) % 4]
            self.add_wall_line(ax, ay, bx, by)

        # 填充地板：矩形4个顶点
        floor_pts = list(corners)
        room_name = getattr(room, "name", "未命名") if room else "未命名"
        floor = FloorItem(floor_pts, room_name=room_name)
        sc.addItem(floor)

        self._rect_start = None

    def notify_room_walls_changed(self) -> None:
        """Room 与 2D 场景已同步修改（如删除墙）后，通知工作区刷新 3D。"""
        stack = self.parent()
        if stack is None:
            return
        canvas = stack.parent()
        if canvas is not None and hasattr(canvas, "refresh_3d_room_display"):
            canvas.refresh_3d_room_display()

    # ─────────────────────────────────── 交互事件
    def wheelEvent(self, event):
        delta = event.angleDelta().y()
        if delta == 0:
            return
        f = self.ZOOM_STEP if delta > 0 else 1.0 / self.ZOOM_STEP
        new_zoom = self._zoom * f
        if self.ZOOM_MIN <= new_zoom <= self.ZOOM_MAX:
            self.scale(f, f)
            self._zoom = new_zoom
            self.viewport().update()

    def keyPressEvent(self, event):
        k = event.key()
        if k == Qt.Key.Key_Escape:
            self._end_draw()
        elif k == Qt.Key.Key_Shift:
            self._shift_lock = True
            if self._wall_start is not None:
                self._rebuild_preview(self._mouse_scene)
        elif k == Qt.Key.Key_Space and not event.isAutoRepeat():
            self._space_pressed = True
            self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        else:
            super().keyPressEvent(event)

    def keyReleaseEvent(self, event):
        k = event.key()
        if k == Qt.Key.Key_Shift:
            self._shift_lock = False
            if self._wall_start is not None:
                self._rebuild_preview(self._mouse_scene)
        elif k == Qt.Key.Key_Space and not event.isAutoRepeat():
            self._space_pressed = False
            self.setDragMode(
                QGraphicsView.DragMode.RubberBandDrag
                if self._tool == "none"
                else QGraphicsView.DragMode.NoDrag
            )
        else:
            super().keyReleaseEvent(event)

    def viewportEvent(self, event):
        return super().viewportEvent(event)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.MiddleButton:
            self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
            fake = QMouseEvent(
                event.type(), event.position(), event.globalPosition(),
                Qt.MouseButton.LeftButton, Qt.MouseButton.LeftButton,
                event.modifiers(),
            )
            super().mousePressEvent(fake)
            return

        if self.draw_mode == "rect_wall" and event.button() == Qt.MouseButton.LeftButton:
            scene_pos = self.mapToScene(event.pos())
            self.rect_start_pos = scene_pos
            self.rect_end_pos = scene_pos
            self.is_drawing_rect = True
            self.update()
            return

        if self._tool == "wall_straight":
            raw = self._mouse_event_to_scene(event)
            if event.button() == Qt.MouseButton.LeftButton:
                if self._wall_start is None:
                    self._suppress_cursor_ortho_after_close = False
                    self._wall_start = self._snap(raw)
                    self._rebuild_preview(raw)
                else:
                    self._commit_wall(raw)
            elif event.button() == Qt.MouseButton.RightButton:
                self._end_draw()
                self._show_context_toolbar(event)
            return

        if self._tool == "wall_rect":
            raw = self._mouse_event_to_scene(event)
            if event.button() == Qt.MouseButton.LeftButton:
                if self._rect_start is None:
                    self._suppress_cursor_ortho_after_close = False
                    self._rect_start = self._snap(raw)
                    self._rebuild_rect_preview(raw)
                else:
                    self._commit_rect_wall(raw)
            elif event.button() == Qt.MouseButton.RightButton:
                self._end_draw()
                self._show_context_toolbar(event)
            return

        if event.button() == Qt.MouseButton.RightButton:
            # 右键：弹出上下文工具条
            self._show_context_toolbar(event)
            return

        super().mousePressEvent(event)

    def _show_context_toolbar(self, event):
        """在右键点击位置弹出浮动工具条（QFrame 直接显示在 viewport 上）。"""
        sc = self.scene()
        if sc is None:
            return
        scene_pos = self._mouse_event_to_scene(event)
        selected = sc.selectedItems()
        if not selected:
            for it in sc.items(scene_pos):
                if isinstance(it, (WallItem, FloorItem)):
                    it.setSelected(True)
                    selected = [it]
                    break

        # 关闭旧工具条
        old_bar = getattr(self, "_ctx_bar", None)
        if old_bar is not None:
            try:
                old_bar.close()
            except Exception:
                pass
        self._ctx_bar = None

        # 创建新工具条（直接挂在 viewport 上，不用 exec）
        bar = _ContextToolBar(selected, self, parent=self.viewport())
        bar.adjustSize()
        vp_pos = event.position().toPoint()
        bw, bh = bar.width(), bar.height()
        vw, vh = self.viewport().width(), self.viewport().height()
        x = min(vp_pos.x(), max(0, vw - bw - 4))
        y = max(vp_pos.y() - bh - 8, 4)
        bar.move(x, y)
        bar.show()
        bar.raise_()
        self._ctx_bar = bar

    def mouseDoubleClickEvent(self, event):
        if self._tool == "wall_straight":
            if event.button() == Qt.MouseButton.LeftButton:
                raw = self._mouse_event_to_scene(event)
                if self._wall_start is not None:
                    self._commit_wall(raw)
                self._end_draw()
            return
        if self._tool == "wall_rect":
            if event.button() == Qt.MouseButton.LeftButton:
                raw = self._mouse_event_to_scene(event)
                if self._rect_start is not None:
                    self._commit_rect_wall(raw)
                self._end_draw()
            return
        super().mouseDoubleClickEvent(event)

    def mouseMoveEvent(self, event):
        raw = self._mouse_event_to_scene(event)
        self._mouse_scene = raw

        if self.draw_mode == "rect_wall" and self.is_drawing_rect:
            scene_pos = self.mapToScene(event.pos())
            self.rect_end_pos = scene_pos

            sc = self.scene()
            if sc is None or self.rect_start_pos is None:
                return

            for item in self.temp_rect_items:
                sc.removeItem(item)
            self.temp_rect_items.clear()

            x1 = self.rect_start_pos.x()
            y1 = self.rect_start_pos.y()

            x2 = self.rect_end_pos.x()
            y2 = self.rect_end_pos.y()

            p1 = QPointF(x1, y1)
            p2 = QPointF(x2, y1)
            p3 = QPointF(x2, y2)
            p4 = QPointF(x1, y2)

            lines = [
                (p1, p2),
                (p2, p3),
                (p3, p4),
                (p4, p1),
            ]

            for a, b in lines:
                item = QGraphicsLineItem(
                    a.x(), a.y(),
                    b.x(), b.y(),
                )
                item.setPen(QPen(Qt.GlobalColor.red, 2))
                sc.addItem(item)
                self.temp_rect_items.append(item)

            w = abs(x2 - x1)
            h = abs(y2 - y1)
            inv = 1.0 / max(self.transform().m11(), 1e-6)
            self._draw_rect_dim(
                sc, inv,
                QPointF((x1 + x2) / 2, min(y1, y2)),
                w,
                horizontal=True,
                items_dest=self.temp_rect_items,
            )
            self._draw_rect_dim(
                sc, inv,
                QPointF(min(x1, x2), (y1 + y2) / 2),
                h,
                horizontal=False,
                items_dest=self.temp_rect_items,
            )

            return

        if self._tool == "wall_straight":
            if self._wall_start is not None:
                self._rebuild_preview(raw)
                return
            if not self._suppress_cursor_ortho_after_close:
                self._preview_cursor_ortho_guides_only(raw)
                return
        elif self._tool == "wall_rect":
            if self._rect_start is not None:
                self._rebuild_rect_preview(raw)
                return
            if not self._suppress_cursor_ortho_after_close:
                self._preview_cursor_ortho_guides_only(raw)
                return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.MiddleButton:
            if not self._space_pressed:
                self.setDragMode(
                    QGraphicsView.DragMode.RubberBandDrag
                    if self._tool == "none"
                    else QGraphicsView.DragMode.NoDrag
                )
        elif event.button() == Qt.MouseButton.LeftButton:
            if self.draw_mode == "rect_wall" and self.is_drawing_rect:
                self.is_drawing_rect = False

                start = self.rect_start_pos
                end = self.rect_end_pos

                x1 = start.x()
                y1 = start.y()

                x2 = end.x()
                y2 = end.y()

                corners = [
                    (min(x1, x2), min(y1, y2)),
                    (max(x1, x2), min(y1, y2)),
                    (max(x1, x2), max(y1, y2)),
                    (min(x1, x2), max(y1, y2)),
                ]
                if abs(corners[2][0] - corners[0][0]) < 2 or abs(corners[2][1] - corners[0][1]) < 2:
                    sc = self.scene()
                    if sc is not None:
                        for item in self.temp_rect_items:
                            sc.removeItem(item)
                    self.temp_rect_items.clear()
                    return

                for i in range(4):
                    a = corners[i]
                    b = corners[(i + 1) % 4]
                    self.create_wall(a, b)

                for i in range(4):
                    ax, ay = corners[i]
                    bx, by = corners[(i + 1) % 4]
                    self._session_walls.append((ax, ay, bx, by))

                sc = self.scene()
                if sc is not None:
                    self._fill_floor(sc)

                # 清理预览
                if sc is not None:
                    for item in self.temp_rect_items:
                        sc.removeItem(item)

                self.temp_rect_items.clear()

                self._end_draw(after_polygon_close=True)

                print("矩形墙创建完成")

                return
            super().mouseReleaseEvent(event)
        else:
            super().mouseReleaseEvent(event)


# ═══════════════════════════════════════════════════ 场景层参考网格
def _adaptive_grid_for_scale(scale: float) -> tuple[int, int]:
    """根据视图水平缩放比返回 (minor, major) scene 步长。"""
    if abs(scale) < 1e-8:
        scale = 1.0
    minor = View2D.MINOR_SIZE
    major = View2D.MAJOR_SIZE
    while minor * scale < View2D._GRID_MIN_PX:
        minor *= View2D.MAJOR_FACTOR
        major *= View2D.MAJOR_FACTOR
    while minor * scale > View2D._GRID_MAX_PX and minor > View2D.MINOR_SIZE:
        minor //= View2D.MAJOR_FACTOR
        major //= View2D.MAJOR_FACTOR
    if minor >= major:
        major = minor * View2D.MAJOR_FACTOR
    return int(minor), int(major)


def _draw_grid_labels(painter: QPainter, rect: QRectF, major: int) -> None:
    _lf = QFont("Consolas")
    safe_set_font_size(_lf, 8)
    painter.setFont(_lf)
    pen = QPen(View2D.LABEL_COLOR)
    pen.setCosmetic(True)
    painter.setPen(pen)
    step = major * 5
    off = 3
    x = int(rect.left()) - (int(rect.left()) % step)
    while x <= rect.right():
        if x != 0:
            painter.drawText(QPointF(x + off, -off), str(x))
        x += step
    y = int(rect.top()) - (int(rect.top()) % step)
    while y <= rect.bottom():
        if y != 0:
            painter.drawText(QPointF(off, y - off), str(y))
        y += step


def paint_reference_grid(painter: QPainter, rect: QRectF, scale: float) -> None:
    """在场景坐标中绘制画板底色 + 棋盘纹 + 参考网格与刻度。"""
    minor, major = _adaptive_grid_for_scale(scale)
    bg = View2D.BG_COLOR
    strp = View2D.BG_STRIPE

    painter.fillRect(rect, bg)

    l = int(rect.left()) - (int(rect.left()) % minor) - minor
    t = int(rect.top()) - (int(rect.top()) % minor) - minor
    r = int(rect.right()) + minor
    b = int(rect.bottom()) + minor

    ix = l - (l % major)
    while ix < r:
        iy = t - (t % major)
        while iy < b:
            cell = QRectF(ix, iy, major, major)
            if cell.intersects(rect):
                stripe = ((ix // major) + (iy // major)) & 1
                painter.fillRect(
                    cell.intersected(rect),
                    strp if stripe else bg,
                )
            iy += major
        ix += major

    pen = QPen(View2D.MINOR_COLOR)
    pen.setCosmetic(True)
    pen.setWidthF(1.25)
    painter.setPen(pen)
    x = l
    while x <= r:
        if x % major != 0:
            painter.drawLine(x, t, x, b)
        x += minor
    y = t
    while y <= b:
        if y % major != 0:
            painter.drawLine(l, y, r, y)
        y += minor

    pen = QPen(View2D.MAJOR_COLOR)
    pen.setCosmetic(True)
    pen.setWidthF(1.35)
    painter.setPen(pen)
    x = l - (l % major)
    while x <= r:
        painter.drawLine(x, t, x, b)
        x += major
    y = t - (t % major)
    while y <= b:
        painter.drawLine(l, y, r, y)
        y += major

    pen = QPen(View2D.AXIS_COLOR)
    pen.setCosmetic(True)
    pen.setWidthF(1.5)
    painter.setPen(pen)
    painter.drawLine(0, t, 0, b)
    painter.drawLine(l, 0, r, 0)

    _draw_grid_labels(painter, rect, major)


class FloorPlanScene(QGraphicsScene):
    """画户型专用场景：墙体图元、room 属性，以及 drawBackground 中的参考网格。

    与 View2D 配合：视图 backgroundBrush 必须为 NoBrush，Qt 才会把背景绘制交给本方法。
    """

    def drawBackground(self, painter: QPainter, rect: QRectF):
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)
        try:
            scale = 1.0
            for view in self.views():
                s = view.transform().m11()
                if abs(s) > 1e-8:
                    scale = abs(s)
                    break
            paint_reference_grid(painter, rect, scale)
        finally:
            painter.restore()



# ═══════════════════════════════════════════════════ 右键浮动工具条
class _ContextToolBar(QFrame):
    """右键弹出的浮动工具条（QFrame 直接挂在 viewport 上，无 QMenu 渲染问题）。

    参考图2：深色圆角卡片，6个图标按钮，hover 变青色，删除红色。
    """

    _BTN_NORMAL = """
        QPushButton {
            background: #2e3a50;
            border: none;
            border-radius: 5px;
            color: #c8d8f0;
            font-size: 15px;
            min-width:  36px; max-width:  36px;
            min-height: 36px; max-height: 36px;
        }
        QPushButton:hover   { background: #4dc9e4; color: #ffffff; }
        QPushButton:pressed { background: #2aa8c4; color: #ffffff; }
    """
    _BTN_DANGER = """
        QPushButton {
            background: #5a2020;
            border: none;
            border-radius: 5px;
            color: #f0a0a0;
            font-size: 15px;
            min-width:  36px; max-width:  36px;
            min-height: 36px; max-height: 36px;
        }
        QPushButton:hover   { background: #c83232; color: #ffffff; }
        QPushButton:pressed { background: #9a2020; color: #ffffff; }
    """

    _TOOLS = [
        ("⊞", "复制",     "_act_copy",       False),
        ("✛", "移动",     "_act_move",       False),
        ("⇔", "对齐",     "_act_align",      False),
        ("⊘", "可见性",   "_act_visibility", False),
        ("🔒", "锁定", "_act_lock",       False),
        ("🗑", "删除", "_act_delete",     True),
    ]

    def __init__(self, items: list, view: "View2D", parent=None):
        super().__init__(parent)
        self._items = items
        self._view  = view

        self.setStyleSheet("""
            QFrame {
                background: #252d3d;
                border: 1px solid #3a4a60;
                border-radius: 8px;
            }
        """)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(3)

        for icon, tip, slot_name, danger in self._TOOLS:
            btn = QPushButton(icon)
            btn.setToolTip(tip)
            btn.setStyleSheet(self._BTN_DANGER if danger else self._BTN_NORMAL)
            btn.setFlat(True)
            slot = getattr(self, slot_name)
            btn.clicked.connect(self._wrap(slot))
            layout.addWidget(btn)

        self.adjustSize()
        if parent is not None:
            parent.installEventFilter(self)

    def _wrap(self, fn):
        def _cb(checked=False):
            fn()
            self.close()
        return _cb

    def eventFilter(self, obj, event):
        if event.type() in (QEvent.Type.MouseButtonPress, QEvent.Type.MouseButtonDblClick):
            pos = event.position().toPoint()
            if not self.geometry().contains(pos):
                self.close()
        return False

    # ── 工具槽 ─────────────────────────────────────────────────
    def _act_copy(self):
        sc = self._view.scene()
        if sc is None:
            return
        new_items = []
        for item in self._items:
            if isinstance(item, WallItem):
                ni = WallItem(item.x1 + 120, item.y1 + 120,
                              item.x2 + 120, item.y2 + 120,
                              item.thickness)
                sc.addItem(ni)
                new_items.append(ni)
        for it in self._items:
            it.setSelected(False)
        for ni in new_items:
            ni.setSelected(True)

    def _act_move(self):
        for item in self._items:
            item.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, True)
        self._view.setDragMode(QGraphicsView.DragMode.NoDrag)

    def _act_align(self):
        walls = [i for i in self._items if isinstance(i, WallItem)]
        if len(walls) < 2:
            return
        ref = walls[0]
        for w in walls[1:]:
            if abs(ref.y1 - ref.y2) < abs(ref.x1 - ref.x2):
                w.setPos(w.pos().x(), w.pos().y() + ref.y1 - w.y1)
            else:
                w.setPos(w.pos().x() + ref.x1 - w.x1, w.pos().y())
        if self._view.scene():
            self._view.scene().update()

    def _act_visibility(self):
        for item in self._items:
            item.setVisible(not item.isVisible())
        if self._view.scene():
            self._view.scene().update()

    def _act_lock(self):
        for item in self._items:
            is_sel = bool(item.flags() & QGraphicsItem.GraphicsItemFlag.ItemIsSelectable)
            item.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, not is_sel)
            item.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, False)
        if self._view.scene():
            self._view.scene().update()

    def _act_delete(self):
        sc = self._view.scene()
        if sc is None:
            return
        room = sc.property("room")
        for item in list(self._items):
            if isinstance(item, WallItem) and room is not None:
                wid = getattr(item, "wall_id", None)
                if isinstance(wid, str) and wid:
                    room.remove_wall(wid)
                else:
                    room.remove_wall_by_segment(item.x1, item.y1, item.x2, item.y2)
            if item.scene() is sc:
                sc.removeItem(item)
        self._view.notify_room_walls_changed()
