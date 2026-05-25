# -*- coding: utf-8 -*-
"""
AddDrawerDialog — 添加抽屉组对话框
=====================================
集成方式（cabinet_assembler.py）：

    from add_drawer_dialog import AddDrawerDialog
    self.sig_add_drawer.connect(self._open_drawer_dialog)

    def _open_drawer_dialog(self):
        dlg = AddDrawerDialog(
            icon_dir=self._icon_dir,
            space_w=564, space_h=1013, space_d=580,
            parent=self
        )
        if dlg.exec():
            data = dlg.get_result()

shiyitu 图片命名规则（icons/shiyitu/）：
    四周外盖/门缝中央示意：优先 抽面A.png
    式样模板卡片：优先 抽面A.png，否则按类型名 png
    底部网格可选 抽屉单列.png

界面分区（与参考图四宫格一致）：
    左上：外盖/门缝、层距、行列与拉手
    右上：抽屉式样模板
    左下：属性名 / 属性值
    右下：宽→、分布与抽屉示意网格
"""
from __future__ import annotations
import os

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QPainter, QPen, QPixmap, QBrush
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QDialog, QFrame,
    QGridLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QScrollArea, QSizePolicy,
    QSpinBox, QVBoxLayout, QWidget,
)

# ── 颜色 ──────────────────────────────────────────────────────────────────────
_BG      = "#f0f0f0"
_BORD    = "#aaaaaa"
_BORD_L  = "#cccccc"
_BORD_D  = "#888888"
_BLUE    = "#1a6fc4"
_TEXT    = "#202020"
_HDR     = "#e0e0e0"
_ORANGE  = "#e8c49a"
_TITBAR  = "#2c3e50"          # ← 标题栏纯色 #2c3e50
_SEL_BG  = "#cce0ff"
_SEL_BD  = "#3a7ac8"

# 对话框外框尺寸（与历史版本一致，勿随意改动）
_DLG_W   = 580
_DLG_H   = 427

# 控件尺寸（适配 580×427）
_CB_H    = 18
_BTN_H   = 18
_FONT    = "10px"
_TITLE_H = 28

# 式样模板 / 中央预览：优先 icons/shiyitu/抽面A.png
_DRAWER_FACE_ICON = "抽面A"

# 左下角属性表默认行（与参考图一致，可编辑）
_DEFAULT_DRAWER_PROPS: list[tuple[str, str]] = [
    ("抽底上移", "18.0"),
    ("抽屉类型", "四方抽"),
    ("抽底厚度", "薄底"),
    ("单侧滑轨厚度", "13.0"),
    ("拉条宽", "0.0"),
]


# ── 路径工具 ──────────────────────────────────────────────────────────────────

def _sty_path(icon_dir: str, name: str) -> str:
    if not icon_dir:
        return ""
    p = os.path.join(icon_dir, "shiyitu", f"{name}.png")
    return p if os.path.isfile(p) else ""


def _load_pm(icon_dir: str, name: str, w: int, h: int) -> QPixmap | None:
    p = _sty_path(icon_dir, name)
    if p:
        raw = QPixmap(p)
        if not raw.isNull():
            return raw.scaled(w, h, Qt.AspectRatioMode.IgnoreAspectRatio,
                              Qt.TransformationMode.SmoothTransformation)
    return None


def _load_pm_fit(icon_dir: str, name: str, w: int, h: int) -> QPixmap | None:
    """等比缩放，留白由 QLabel 居中。"""
    p = _sty_path(icon_dir, name)
    if p:
        raw = QPixmap(p)
        if not raw.isNull():
            return raw.scaled(
                w,
                h,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
    return None


def _load_drawer_style_thumb(
    icon_dir: str, w: int, h: int, type_name: str = ""
) -> QPixmap | None:
    """式样区图标：优先抽面A.png，否则按类型名加载对应 png。"""
    pm = _load_pm_fit(icon_dir, _DRAWER_FACE_ICON, w, h)
    if pm is not None:
        return pm
    if type_name:
        return _load_pm_fit(icon_dir, type_name, w, h)
    return None

# ── 代码绘制 ──────────────────────────────────────────────────────────────────

def _draw_drawer_cell(w: int, h: int) -> QPixmap:
    pix = QPixmap(w, h)
    pix.fill(QColor(_ORANGE))
    p = QPainter(pix)
    p.setPen(QPen(QColor("#8B5E3C"), 1))
    p.drawRect(0, 0, w - 1, h - 1)
    p.setPen(QPen(QColor("#555"), 2))
    p.drawLine(w // 4, h // 2, 3 * w // 4, h // 2)
    p.end()
    return pix


def _draw_drawer_grid(rows: int, cols: int, cw: int = 48, ch: int = 24) -> QPixmap:
    pad = 2
    tw = cols * cw + (cols - 1) * pad + 4
    th = rows * ch + (rows - 1) * pad + 4
    pix = QPixmap(tw, th)
    pix.fill(QColor(_BG))
    p = QPainter(pix)
    for r in range(rows):
        for c in range(cols):
            x = 2 + c * (cw + pad)
            y = 2 + r * (ch + pad)
            p.fillRect(x, y, cw, ch, QColor(_ORANGE))
            p.setPen(QPen(QColor("#8B5E3C"), 1))
            p.drawRect(x, y, cw - 1, ch - 1)
            p.setPen(QPen(QColor("#555"), 2))
            p.drawLine(x + cw // 4, y + ch // 2, x + 3 * cw // 4, y + ch // 2)
    p.end()
    return pix


def _draw_spacing_diagram(w: int, h: int) -> QPixmap:
    """层距示意：三个抽屉块 + 橙色标注线"""
    pix = QPixmap(w, h)
    pix.fill(QColor("#e0e0e0"))
    p = QPainter(pix)
    p.setPen(QPen(QColor(_BORD_D), 1))
    p.drawRect(0, 0, w - 1, h - 1)
    bh = (h - 8) // 4          # 单个抽屉块高度
    gap = (h - 3 * bh) // 4    # 间距
    colors = [_ORANGE, "#6baed6", _ORANGE]   # 中间蓝=层距示意
    for i in range(3):
        y = gap + i * (bh + gap)
        p.fillRect(4, y, w - 8, bh, QColor(colors[i]))
        p.setPen(QPen(QColor("#8B5E3C"), 1))
        p.drawRect(4, y, w - 9, bh - 1)
        p.setPen(QPen(QColor("#555"), 1))
        p.drawLine(4 + (w - 8) // 4, y + bh // 2, 4 + 3 * (w - 8) // 4, y + bh // 2)
    # 上口/层距/下口 标注（右侧小箭头）
    ax = w - 3
    p.setPen(QPen(QColor("#e86020"), 1))
    p.drawLine(ax, 0, ax, gap)                          # 上口
    p.drawLine(ax - 2, gap // 2, ax + 2, gap // 2)
    y1 = gap + bh; y2 = y1 + gap
    p.drawLine(ax, y1, ax, y2)                          # 层距
    p.drawLine(ax - 2, (y1 + y2) // 2, ax + 2, (y1 + y2) // 2)
    y3 = 2 * (gap + bh) + gap; y4 = h
    p.drawLine(ax, y3, ax, y4)                          # 下口
    p.drawLine(ax - 2, (y3 + y4) // 2, ax + 2, (y3 + y4) // 2)
    p.end()
    return pix


def _draw_box_diagram(w: int, h: int) -> QPixmap:
    """抽盒距示意：顶板 + 抽屉 + 底板"""
    pix = QPixmap(w, h)
    pix.fill(QColor("#e0e0e0"))
    p = QPainter(pix)
    p.setPen(QPen(QColor(_BORD_D), 1))
    p.drawRect(0, 0, w - 1, h - 1)
    # 顶板
    p.fillRect(2, 2, w - 4, 6, QColor("#c8c8a0"))
    p.setPen(QPen(QColor("#888"), 1))
    p.drawRect(2, 2, w - 5, 5)
    # 抽屉
    mid_y = (h - 14) // 2
    p.fillRect(2, mid_y, w - 4, h - mid_y - 10, QColor(_ORANGE))
    p.setPen(QPen(QColor("#8B5E3C"), 1))
    p.drawRect(2, mid_y, w - 5, h - mid_y - 11)
    p.setPen(QPen(QColor("#555"), 1))
    p.drawLine(w // 4, mid_y + (h - mid_y - 10) // 2,
               3 * w // 4, mid_y + (h - mid_y - 10) // 2)
    # 底板
    p.fillRect(2, h - 8, w - 4, 6, QColor("#c8c8a0"))
    p.setPen(QPen(QColor("#888"), 1))
    p.drawRect(2, h - 8, w - 5, 5)
    # 标注线
    ax = w - 3
    p.setPen(QPen(QColor("#e86020"), 1))
    p.drawLine(ax, 8, ax, mid_y)
    p.drawLine(ax - 2, (8 + mid_y) // 2, ax + 2, (8 + mid_y) // 2)
    p.drawLine(ax, h - mid_y + 4, ax, h - 8)
    p.drawLine(ax - 2, (h - mid_y + 4 + h - 8) // 2,
               ax + 2, (h - mid_y + 4 + h - 8) // 2)
    p.end()
    return pix


# ── 标题栏 ────────────────────────────────────────────────────────────────────

class _TitleBar(QWidget):
    def __init__(self, title: str, space_w, space_h, space_d, dlg, parent=None):
        super().__init__(parent)
        self.setFixedHeight(_TITLE_H)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        # 标题栏底色 #2c3e50，用类名选择器防止颜色渗透子控件
        self.setStyleSheet(f"_TitleBar {{ background-color: {_TITBAR}; }}")
        hl = QHBoxLayout(self)
        hl.setContentsMargins(6, 0, 4, 0)
        hl.setSpacing(8)

        t = QLabel(title)
        t.setStyleSheet(
            "color:white;font-size:11px;font-weight:bold;background:transparent;"
        )
        hl.addWidget(t)

        info = QLabel(f"W:  {space_w}   H:  {space_h}   D:  {space_d}")
        info.setStyleSheet("color:#c8d8e8;font-size:10px;background:transparent;")
        hl.addWidget(info, 0)

        hl.addStretch(1)

        tpl = QLabel("抽屉式样模板：↓↓↓")
        tpl.setStyleSheet("color:#b8ccde;font-size:10px;background:transparent;")
        hl.addWidget(tpl)

        x = QPushButton("×")
        x.setFixedSize(16, 16)
        x.setStyleSheet(
            "QPushButton{background:#c0392b;color:white;border:none;font-size:12px;"
            "border-radius:2px;}"
            "QPushButton:hover{background:#e74c3c;}"
        )
        x.clicked.connect(dlg.reject)
        hl.addWidget(x)


# ── 控件工厂（尺寸与参考布局一致）──────────────────────────────────────────

_CB_SS = (
    f"QComboBox{{border:1px solid {_BORD};background:white;"
    f"font-size:{_FONT};padding:0 2px;height:{_CB_H}px;}}"
    f"QComboBox::drop-down{{width:12px;}}"
)
_LE_SS = (
    f"QLineEdit{{border:1px solid {_BORD};background:white;"
    f"font-size:{_FONT};padding:0 2px;height:{_CB_H}px;}}"
)
_SB_SS = (
    f"QSpinBox{{border:1px solid {_BORD};background:white;"
    f"font-size:{_FONT};padding:0 2px;height:{_CB_H}px;}}"
)
_BTN_SS = (
    f"QPushButton{{border:1px solid {_BORD};background:{_HDR};"
    f"font-size:{_FONT};padding:0 4px;height:{_BTN_H}px;}}"
    f"QPushButton:hover{{background:#d0d8e8;}}"
    f"QPushButton:pressed{{background:#b8c8dc;}}"
)


def _combo(opts: list[str], cur: str = "", w: int = 0) -> QComboBox:
    cb = QComboBox()
    cb.addItems(opts)
    if cur in opts:
        cb.setCurrentText(cur)
    cb.setFixedHeight(_CB_H)
    if w:
        cb.setFixedWidth(w)
    cb.setStyleSheet(_CB_SS)
    return cb


def _spinbox(val: int, lo: int = 1, hi: int = 20, w: int = 60) -> QSpinBox:
    sb = QSpinBox()
    sb.setRange(lo, hi)
    sb.setValue(val)
    sb.setFixedHeight(_CB_H)
    sb.setFixedWidth(w)
    sb.setStyleSheet(_SB_SS)
    return sb


def _lineedit(val: str = "", w: int = 0) -> QLineEdit:
    le = QLineEdit(val)
    le.setFixedHeight(_CB_H)
    if w:
        le.setFixedWidth(w)
    le.setStyleSheet(_LE_SS)
    return le


def _btn(text: str, w: int = 0, h: int = _BTN_H) -> QPushButton:
    b = QPushButton(text)
    b.setFixedHeight(h)
    if w:
        b.setFixedWidth(w)
    b.setStyleSheet(_BTN_SS)
    return b


def _lbl(text: str, w: int = 0, bold: bool = False) -> QLabel:
    l = QLabel(text)
    l.setFixedHeight(_CB_H)
    if w:
        l.setFixedWidth(w)
    weight = "font-weight:bold;" if bold else ""
    l.setStyleSheet(f"font-size:{_FONT};color:{_TEXT};background:transparent;{weight}")
    l.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
    return l


def _hline() -> QFrame:
    f = QFrame()
    f.setFrameShape(QFrame.Shape.HLine)
    f.setStyleSheet(f"color:{_BORD_L};")
    f.setFixedHeight(1)
    return f


def _vline() -> QFrame:
    f = QFrame()
    f.setFrameShape(QFrame.Shape.VLine)
    f.setStyleSheet(f"color:{_BORD_L};")
    f.setFixedWidth(1)
    return f


# ── 拉手定位九宫格 ─────────────────────────────────────────────────────────────

_GRID9 = [
    (3, True,  False, False, False, False),
    (6, True,  True,  False, False, False),
    (3, True,  False, False, False, False),
    (2, False, False, True,  False, False),
    (5, False, True,  False, False, True),
    (2, False, False, False, True,  False),
    (1, False, True,  False, False, False),
    (4, False, True,  False, False, False),
    (1, False, True,  False, False, False),
]


class _HCell(QWidget):
    def __init__(self, num, tt, tb, tl, tr, sel, parent=None):
        super().__init__(parent)
        self._sel   = sel
        self._ticks = (tt, tb, tl, tr)
        self.setFixedSize(26, 22)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self._repaint()
        lb = QLabel(str(num), self)
        lb.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lb.setGeometry(0, 0, 26, 22)
        lb.setStyleSheet("font-size:9px;font-weight:bold;background:transparent;border:none;")

    def _repaint(self):
        if self._sel:
            self.setStyleSheet(f"background:{_SEL_BG};border:2px solid {_SEL_BD};")
        else:
            self.setStyleSheet(f"background:white;border:1px solid {_BORD};")

    def paintEvent(self, ev):
        super().paintEvent(ev)
        p = QPainter(self)
        p.setPen(QPen(QColor("#888"), 1))
        W, H = self.width(), self.height()
        mx, my = W // 2, H // 2
        tt, tb, tl, tr = self._ticks
        if tt: p.drawLine(mx - 3, 2, mx + 3, 2)
        if tb: p.drawLine(mx - 3, H - 2, mx + 3, H - 2)
        if tl: p.drawLine(2, my - 3, 2, my + 3)
        if tr: p.drawLine(W - 2, my - 3, W - 2, my + 3)
        p.end()

    def mousePressEvent(self, ev):
        self._sel = not self._sel
        self._repaint()
        self.update()


class _HandleGrid(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        g = QGridLayout(self)
        g.setContentsMargins(1, 1, 1, 1)
        g.setSpacing(1)
        for i, args in enumerate(_GRID9):
            g.addWidget(_HCell(*args), i // 3, i % 3)


# ── 抽屉式样卡片 ──────────────────────────────────────────────────────────────

_DRAWER_TYPES = ["A抽屉", "假抽面", "多宝格1", "多宝格2", "带轮子抽屉", "托底抽屉"]


class _DrawerCard(QWidget):
    selected = Signal(str)

    def __init__(self, icon_dir: str, name: str, parent=None):
        super().__init__(parent)
        self._name  = name
        self._is_sel = False
        self.setFixedSize(74, 66)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._upd_style()

        vl = QVBoxLayout(self)
        vl.setContentsMargins(2, 2, 2, 2)
        vl.setSpacing(1)

        self._img = QLabel()
        self._img.setFixedSize(70, 48)
        self._img.setAlignment(Qt.AlignmentFlag.AlignCenter)

        pm = _load_drawer_style_thumb(icon_dir, 66, 44, name)
        if pm:
            self._img.setPixmap(pm)
            self._img.setStyleSheet(
                f"background:#f8f8f8;border:1px solid {_BORD_L};border-radius:2px;"
            )
        else:
            self._img.setText(name)
            self._img.setStyleSheet(
                f"background:{_ORANGE};border:1px solid {_BORD_L};font-size:9px;"
                f"color:{_TEXT};border-radius:2px;"
            )
        vl.addWidget(self._img)

        lb = QLabel(name)
        lb.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lb.setStyleSheet(f"font-size:9px;color:{_TEXT};background:transparent;border:none;")
        vl.addWidget(lb)

    def _upd_style(self):
        if self._is_sel:
            self.setStyleSheet(
                f"background:{_SEL_BG};border:2px solid {_SEL_BD};border-radius:2px;"
            )
        else:
            self.setStyleSheet(
                f"background:#f5f5f5;border:1px solid {_BORD_L};border-radius:2px;"
            )

    def set_selected(self, v: bool):
        self._is_sel = v
        self._upd_style()

    def mousePressEvent(self, ev):
        if ev.button() == Qt.MouseButton.LeftButton:
            self.selected.emit(self._name)

    def enterEvent(self, ev):
        if not self._is_sel:
            self.setStyleSheet(
                f"background:#e8f0fb;border:1px solid {_SEL_BD};border-radius:2px;"
            )

    def leaveEvent(self, ev):
        self._upd_style()


# ── 底部宽/分布/示意图网格 ────────────────────────────────────────────────────

_LBL_W      = 34
_COL_MIN_W  = 50
_HDR_ROW_H  = 18
_DATA_ROW_H = 17
_DIAG_ROW_H = 30


class _BottomGrid(QWidget):
    def __init__(
        self,
        icon_dir: str,
        rows: int = 3,
        cols: int = 4,
        width_hint_first_col: str = "",
        parent=None,
    ):
        super().__init__(parent)
        self._icon_dir = icon_dir
        self._rows = rows
        self._cols = cols
        self._width_hint = (width_hint_first_col or "").strip()
        self._g = QGridLayout(self)
        self._g.setContentsMargins(2, 2, 2, 2)
        self._g.setSpacing(0)
        self.setStyleSheet(f"background:{_BG};")
        self._rebuild()

    def set_rows_cols(self, rows: int, cols: int):
        if rows != self._rows or cols != self._cols:
            self._rows = max(1, rows)
            self._cols = max(1, cols)
            self._rebuild()

    def get_widths(self) -> list[str]:
        result = []
        for c in range(self._cols):
            it = self._g.itemAtPosition(0, c + 1)
            if it and it.widget() and hasattr(it.widget(), "text"):
                result.append(it.widget().text())
        return result

    def get_ratios(self) -> list[str]:
        result = []
        for c in range(self._cols):
            it = self._g.itemAtPosition(1, c + 1)
            if it and it.widget() and hasattr(it.widget(), "text"):
                result.append(it.widget().text())
        return result

    def _clear(self):
        while self._g.count():
            item = self._g.takeAt(0)
            if item and item.widget():
                item.widget().deleteLater()

    def _mk_hdr(self, text: str) -> QLabel:
        l = QLabel(text)
        l.setFixedHeight(_HDR_ROW_H)
        l.setAlignment(Qt.AlignmentFlag.AlignCenter)
        l.setStyleSheet(
            f"font-size:{_FONT};color:{_TEXT};background:{_HDR};"
            f"border:1px solid {_BORD_L};font-weight:bold;"
        )
        return l

    def _mk_input(self, val: str) -> QLineEdit:
        le = QLineEdit(val)
        le.setFixedHeight(_DATA_ROW_H)
        le.setAlignment(Qt.AlignmentFlag.AlignCenter)
        le.setStyleSheet(
            f"QLineEdit{{border:1px solid {_BORD_L};background:white;"
            f"font-size:{_FONT};padding:0;text-align:center;}}"
        )
        return le

    def _mk_row_lbl(self, text: str) -> QLabel:
        l = QLabel(text)
        l.setFixedWidth(_LBL_W)
        l.setFixedHeight(_DIAG_ROW_H)
        l.setAlignment(Qt.AlignmentFlag.AlignCenter)
        l.setStyleSheet(
            f"font-size:{_FONT};color:{_TEXT};background:{_HDR};"
            f"border:1px solid {_BORD_L};font-weight:bold;"
        )
        return l

    def _mk_drawer_cell(self) -> QLabel:
        lb = QLabel()
        lb.setFixedHeight(_DIAG_ROW_H)
        lb.setAlignment(Qt.AlignmentFlag.AlignCenter)
        pm = _load_pm(self._icon_dir, "抽屉单列", 46, _DIAG_ROW_H - 4)
        if not pm:
            pm = _draw_drawer_cell(46, _DIAG_ROW_H - 4)
        lb.setPixmap(pm)
        lb.setStyleSheet(f"background:{_ORANGE};border:1px solid {_BORD_L};")
        return lb

    def _rebuild(self):
        self._clear()
        g = self._g
        rows, cols = self._rows, self._cols

        g.setColumnMinimumWidth(0, _LBL_W)
        for c in range(cols):
            g.setColumnMinimumWidth(c + 1, _COL_MIN_W)
            g.setColumnStretch(c + 1, 1)

        # 行0：宽→（与参考图箭头方向一致）
        g.addWidget(self._mk_hdr("宽→"), 0, 0)
        for c in range(cols):
            winit = "141"
            if c == 0 and self._width_hint:
                winit = self._width_hint
            g.addWidget(self._mk_input(winit), 0, c + 1)
        g.setRowMinimumHeight(0, _HDR_ROW_H)

        # 行1：分布
        g.addWidget(self._mk_hdr("分布"), 1, 0)
        for c in range(cols):
            g.addWidget(self._mk_input("1"), 1, c + 1)
        g.setRowMinimumHeight(1, _DATA_ROW_H)

        # 行2+：每行抽屉
        for r in range(rows):
            ri = r + 2
            g.addWidget(self._mk_row_lbl(str(r + 1)), ri, 0)
            for c in range(cols):
                g.addWidget(self._mk_drawer_cell(), ri, c + 1)
            g.setRowMinimumHeight(ri, _DIAG_ROW_H)


# ── 主对话框 ──────────────────────────────────────────────────────────────────

class AddDrawerDialog(QDialog):
    """添加抽屉组：四宫格（左上设置 / 右上式样 / 左下属性 / 右下宽→与分布）；标题栏 #2c3e50。"""

    def __init__(self, icon_dir: str = "",
                 space_w: int = 564, space_h: int = 1013, space_d: int = 580,
                 parent=None):
        super().__init__(parent)
        self._icon_dir  = icon_dir
        self._result    = {}
        self._sel_type  = "A抽屉"

        self.setWindowFlags(Qt.WindowType.Dialog | Qt.WindowType.FramelessWindowHint)
        self.setFixedSize(_DLG_W, _DLG_H)
        self.setStyleSheet(f"QDialog{{background:{_BG};border:1px solid #666;}}")

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ── 标题栏 ──────────────────────────────────────────────────────────
        self._titlebar = _TitleBar("添加抽屉组", space_w, space_h, space_d, self)
        root.addWidget(self._titlebar)

        # ── 上半主体（左内容区 | 竖分隔 | 右式样区） ────────────────────────
        body = QHBoxLayout()
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(0)

        left_w = self._build_left()
        left_w.setFixedWidth(360)
        body.addWidget(left_w)
        body.addWidget(_vline())
        body.addWidget(self._build_right(), 1)

        root.addLayout(body, 0)
        root.addWidget(_hline())

        # ── 下半：四宫格之「左下属性 | 右下宽→/分布」─────────────────────────
        bottom_split = QWidget()
        bsl = QHBoxLayout(bottom_split)
        bsl.setContentsMargins(0, 0, 0, 0)
        bsl.setSpacing(0)
        bsl.addWidget(self._build_property_region())
        bsl.addWidget(_vline())
        self._bottom = _BottomGrid(
            icon_dir,
            rows=self._spin_rows.value(),
            cols=self._spin_cols.value(),
            width_hint_first_col=str(space_w),
        )
        scroll = QScrollArea()
        scroll.setWidget(self._bottom)
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll.setStyleSheet(
            f"QScrollArea{{border:none;background:#fafafa;}}"
            f"QScrollBar:vertical{{background:#f0f2f5;width:4px;}}"
            f"QScrollBar::handle:vertical{{background:#c0c4cc;border-radius:2px;}}"
            f"QScrollBar:horizontal{{background:#f0f2f5;height:4px;}}"
            f"QScrollBar::handle:horizontal{{background:#c0c4cc;border-radius:2px;}}"
        )
        bsl.addWidget(scroll, 1)
        root.addWidget(bottom_split, 1)

        root.addWidget(_hline())
        root.addWidget(self._build_footer())

    # ─────────────────────────────────────────────────────────────────────────
    # 左侧：三列（四周外盖 | 层距+抽盒距 | 行列+拉手）
    # ─────────────────────────────────────────────────────────────────────────

    def _build_left(self) -> QWidget:
        w = QWidget()
        w.setStyleSheet(f"background:{_BG};")
        hl = QHBoxLayout(w)
        hl.setContentsMargins(4, 4, 4, 3)
        hl.setSpacing(5)

        hl.addWidget(self._build_cover_panel())
        hl.addWidget(_vline())
        hl.addWidget(self._build_spacing_panel())
        hl.addWidget(_vline())
        hl.addWidget(self._build_options_panel(), 1)
        return w

    # ── 四周尺寸外盖 / 门缝值（严格对照参考图1）────────────────────────────

    def _build_cover_panel(self) -> QWidget:
        """
        参考图1 精确布局：
          ┌────────────────────────────┐
          │ 四周尺寸外盖 / 门缝值 标题  │
          │   [不盖▼] [半缝▼]   ← 顶  │
          │ [不盖▼]  ┌─────┐  [不盖▼] │
          │ [半缝▼]  │预览图│  [半缝▼] │
          │          └─────┘          │
          │   [不盖▼] [半缝▼]   ← 底  │
          │全盖 半盖 不盖 全缝 半缝 无缝│
          └────────────────────────────┘
        """
        w = QWidget()
        w.setFixedWidth(148)
        vl = QVBoxLayout(w)
        vl.setContentsMargins(0, 0, 0, 0)
        vl.setSpacing(3)

        # 标题
        sec = QLabel("四周尺寸外盖 / 门缝值")
        sec.setStyleSheet(
            f"font-size:{_FONT};color:{_TEXT};"
            f"border-bottom:1px solid {_BORD_L};padding-bottom:2px;"
        )
        vl.addWidget(sec)

        gb = QWidget()
        gb.setStyleSheet(f"background:#fafafa;border:1px solid {_BORD};")
        inner = QVBoxLayout(gb)
        inner.setContentsMargins(3, 4, 3, 4)
        inner.setSpacing(3)

        # ── 顶部：[不盖▼][半缝▼] 居中 ──
        top_row = QHBoxLayout()
        top_row.setSpacing(2)
        top_row.addStretch(1)
        self._cb_top_cover = _combo(["不盖","全盖","半盖"], "不盖", 46)
        self._cb_top_gap   = _combo(["半缝","全缝","无缝"], "半缝", 46)
        top_row.addWidget(self._cb_top_cover)
        top_row.addWidget(self._cb_top_gap)
        top_row.addStretch(1)
        inner.addLayout(top_row)

        # ── 中间：左侧2下拉 | 预览图 | 右侧2下拉 ──
        mid = QHBoxLayout()
        mid.setSpacing(3)
        mid.setContentsMargins(0, 0, 0, 0)

        # 左侧：外盖下拉 在上，缝值下拉 在下（竖排）
        lv = QVBoxLayout()
        lv.setSpacing(3)
        lv.setContentsMargins(0, 0, 0, 0)
        self._cb_left_cover = _combo(["不盖","全盖","半盖"], "不盖", 46)
        self._cb_left_gap   = _combo(["半缝","全缝","无缝"], "半缝", 46)
        lv.addWidget(self._cb_left_cover)
        lv.addWidget(self._cb_left_gap)
        lv.addStretch()
        mid.addLayout(lv)

        # 中央：外盖/门缝示意区 — 优先加载 shiyitu/抽面A.png
        self._preview_lbl = QLabel()
        self._preview_lbl.setFixedSize(42, 38)
        self._preview_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._preview_lbl.setStyleSheet(
            f"border:1px solid {_BORD};background:{_ORANGE};"
        )
        self._refresh_preview_img()
        mid.addWidget(self._preview_lbl)

        # 右侧：外盖下拉 在上，缝值下拉 在下（竖排）
        rv = QVBoxLayout()
        rv.setSpacing(3)
        rv.setContentsMargins(0, 0, 0, 0)
        self._cb_right_cover = _combo(["不盖","全盖","半盖"], "不盖", 46)
        self._cb_right_gap   = _combo(["半缝","全缝","无缝"], "半缝", 46)
        rv.addWidget(self._cb_right_cover)
        rv.addWidget(self._cb_right_gap)
        rv.addStretch()
        mid.addLayout(rv)

        inner.addLayout(mid)

        # ── 底部：[不盖▼][半缝▼] 居中 ──
        bot_row = QHBoxLayout()
        bot_row.setSpacing(2)
        bot_row.addStretch(1)
        self._cb_bot_cover = _combo(["不盖","全盖","半盖"], "不盖", 46)
        self._cb_bot_gap   = _combo(["半缝","全缝","无缝"], "半缝", 46)
        bot_row.addWidget(self._cb_bot_cover)
        bot_row.addWidget(self._cb_bot_gap)
        bot_row.addStretch(1)
        inner.addLayout(bot_row)

        vl.addWidget(gb)

        # 快捷按钮（6个，紧凑排列）
        qb = QHBoxLayout()
        qb.setSpacing(2)
        qb.setContentsMargins(0, 1, 0, 0)
        for lbl_text in ["全盖","半盖","不盖","全缝","半缝","无缝"]:
            b = QPushButton(lbl_text)
            b.setMinimumHeight(17)
            b.setSizePolicy(
                QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
            )
            b.setStyleSheet(
                f"QPushButton{{border:1px solid {_BORD};background:{_HDR};"
                f"font-size:9px;padding:0;}}"
                f"QPushButton:hover{{background:#d0d8e8;}}"
                f"QPushButton:pressed{{background:#b8c8dc;}}"
            )
            b.clicked.connect(lambda _, l=lbl_text: self._quick_cover(l))
            qb.addWidget(b)
        vl.addLayout(qb)
        return w

    # ── 层距 + 抽盒距 ────────────────────────────────────────────────────────

    def _build_spacing_panel(self) -> QWidget:
        w = QWidget()
        w.setFixedWidth(108)
        vl = QVBoxLayout(w)
        vl.setContentsMargins(0, 0, 0, 0)
        vl.setSpacing(3)

        # ── 层距（上口/中间/下口）──────────────────────────────────────────
        sp_wrap = QWidget()
        sp_wrap.setStyleSheet(f"background:#fafafa;border:1px solid {_BORD};")
        sl = QGridLayout(sp_wrap)
        sl.setContentsMargins(3, 4, 2, 4)
        sl.setSpacing(2)
        sl.setColumnStretch(1, 1)

        def row_lbl(t):
            l = QLabel(t)
            l.setFixedHeight(_CB_H)
            l.setStyleSheet(
                f"font-size:{_FONT};color:{_TEXT};background:transparent;"
            )
            l.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
            return l

        def tag_lbl(t, color="#e86020"):
            l = QLabel(t)
            l.setFixedHeight(_CB_H)
            l.setStyleSheet(
                f"font-size:9px;color:{color};background:transparent;"
            )
            l.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
            return l

        # 示意图（跨3行）
        sp_diag = QLabel()
        sp_diag.setFixedSize(30, 54)
        sp_diag.setAlignment(Qt.AlignmentFlag.AlignCenter)
        pm = _load_pm(self._icon_dir, "层距示意", 28, 52)
        if not pm:
            pm = _draw_spacing_diagram(28, 52)
        sp_diag.setPixmap(pm)
        sp_diag.setStyleSheet(f"border:1px solid {_BORD_L};background:#e8e8e8;")
        sl.addWidget(sp_diag, 0, 3, 3, 1)

        sl.addWidget(row_lbl("上口留空"), 0, 0)
        self._le_top_gap = _lineedit("0", 28)
        sl.addWidget(self._le_top_gap, 0, 1)
        sl.addWidget(tag_lbl("上口"), 0, 2)

        sl.addWidget(row_lbl("中间层距"), 1, 0)
        self._le_mid_gap = _lineedit("0", 28)
        sl.addWidget(self._le_mid_gap, 1, 1)
        sl.addWidget(tag_lbl("层距"), 1, 2)

        sl.addWidget(row_lbl("下口留空"), 2, 0)
        self._le_bot_gap = _lineedit("0", 28)
        sl.addWidget(self._le_bot_gap, 2, 1)
        sl.addWidget(tag_lbl("下口"), 2, 2)

        vl.addWidget(sp_wrap)

        # ── 抽盒距上/下 ────────────────────────────────────────────────────
        bx_wrap = QWidget()
        bx_wrap.setStyleSheet(f"background:#fafafa;border:1px solid {_BORD};")
        bl = QGridLayout(bx_wrap)
        bl.setContentsMargins(3, 4, 2, 4)
        bl.setSpacing(2)
        bl.setColumnStretch(1, 1)

        bx_diag = QLabel()
        bx_diag.setFixedSize(30, 36)
        bx_diag.setAlignment(Qt.AlignmentFlag.AlignCenter)
        pm2 = _load_pm(self._icon_dir, "抽盒距示意", 28, 34)
        if not pm2:
            pm2 = _draw_box_diagram(28, 34)
        bx_diag.setPixmap(pm2)
        bx_diag.setStyleSheet(f"border:1px solid {_BORD_L};background:#e8e8e8;")
        bl.addWidget(bx_diag, 0, 3, 2, 1)

        bl.addWidget(row_lbl("抽盒距上"), 0, 0)
        self._le_box_top = _lineedit("10", 28)
        bl.addWidget(self._le_box_top, 0, 1)
        bl.addWidget(tag_lbl("距上"), 0, 2)

        bl.addWidget(row_lbl("抽盒距下"), 1, 0)
        self._le_box_bot = _lineedit("20", 28)
        bl.addWidget(self._le_box_bot, 1, 1)
        bl.addWidget(tag_lbl("距下"), 1, 2)

        vl.addWidget(bx_wrap)
        vl.addStretch(1)
        return w

    # ── 行列数 + 拉手配置 ────────────────────────────────────────────────────

    def _build_options_panel(self) -> QWidget:
        w = QWidget()
        vl = QVBoxLayout(w)
        vl.setContentsMargins(0, 0, 0, 0)
        vl.setSpacing(3)

        # ── 行列数 + 门型 ──────────────────────────────────────────────────
        rc = QWidget()
        rc.setStyleSheet(f"background:#fafafa;border:1px solid {_BORD};")
        rl = QGridLayout(rc)
        rl.setContentsMargins(4, 4, 4, 4)
        rl.setSpacing(3)
        rl.setColumnStretch(1, 1)

        def rl_lbl(t):
            l = QLabel(t)
            l.setFixedHeight(_CB_H)
            l.setStyleSheet(
                f"font-size:{_FONT};color:{_TEXT};background:transparent;"
            )
            return l

        rl.addWidget(rl_lbl("抽屉行数"), 0, 0)
        self._spin_rows = _spinbox(1, 1, 20, 55)
        self._spin_rows.valueChanged.connect(self._on_grid_change)
        rl.addWidget(self._spin_rows, 0, 1)

        rl.addWidget(rl_lbl("抽屉列数"), 1, 0)
        self._spin_cols = _spinbox(1, 1, 12, 55)
        self._spin_cols.valueChanged.connect(self._on_grid_change)
        rl.addWidget(self._spin_cols, 1, 1)

        rl.addWidget(rl_lbl("门型编号"), 2, 0)
        r2 = QHBoxLayout()
        r2.setSpacing(2)
        self._le_type = _lineedit("")
        r2.addWidget(self._le_type, 1)
        r2.addWidget(_btn("选择", 30, _BTN_H))
        rl.addLayout(r2, 2, 1)

        mod_btn = _btn("选择自定义MOD抽面", h=_BTN_H)
        mod_btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        rl.addWidget(mod_btn, 3, 0, 1, 2)

        vl.addWidget(rc)

        # ── 拉手配置 ──────────────────────────────────────────────────────
        hc = QWidget()
        hc.setStyleSheet(f"background:#fafafa;border:1px solid {_BORD};")
        hl2 = QGridLayout(hc)
        hl2.setContentsMargins(4, 4, 4, 4)
        hl2.setSpacing(3)
        hl2.setColumnStretch(1, 1)

        hl2.addWidget(rl_lbl("拉手型号"), 0, 0)
        r_h = QHBoxLayout()
        r_h.setSpacing(2)
        self._cb_handle = _combo([], "", 0)
        r_h.addWidget(self._cb_handle, 1)
        r_h.addWidget(_btn("选择", 30, _BTN_H))
        hl2.addLayout(r_h, 0, 1)

        hl2.addWidget(rl_lbl("拉手位置"), 1, 0)
        self._cb_handle_pos = _combo(["1","2","3","4","5","6","7","8","9"], "5", 50)
        hl2.addWidget(self._cb_handle_pos, 1, 1)

        hl2.addWidget(rl_lbl("免拉手延伸"), 2, 0)
        self._cb_no_handle = _combo(["无","有"], "无", 50)
        hl2.addWidget(self._cb_no_handle, 2, 1)

        self._chk_rotate = QCheckBox("拉手旋转安装")
        self._chk_rotate.setChecked(True)
        self._chk_rotate.setStyleSheet(
            f"QCheckBox{{font-size:{_FONT};color:{_TEXT};}}"
            f"QCheckBox::indicator{{width:11px;height:11px;"
            f"border:1px solid {_BORD};background:white;}}"
            f"QCheckBox::indicator:checked{{background:{_BLUE};border-color:{_BLUE};}}"
        )
        hl2.addWidget(self._chk_rotate, 3, 0, 1, 2)

        vl.addWidget(hc)
        vl.addStretch(1)
        return w

    def _build_property_region(self) -> QWidget:
        """左下角：属性名 / 属性值（四宫格之一，与参考图一致）。"""
        wrap = QWidget()
        wrap.setFixedWidth(218)
        wrap.setStyleSheet(f"background:{_BG};")
        vl = QVBoxLayout(wrap)
        vl.setContentsMargins(1, 1, 1, 1)
        vl.setSpacing(0)

        ah = QWidget()
        ah.setFixedHeight(_HDR_ROW_H)
        ah.setStyleSheet(f"background:{_HDR};border:1px solid {_BORD_L};")
        ahl = QHBoxLayout(ah)
        ahl.setContentsMargins(3, 0, 3, 0)
        la = QLabel("属性名")
        la.setStyleSheet(
            f"font-size:{_FONT};font-weight:bold;color:{_TEXT};background:transparent;"
        )
        lv = QLabel("属性值")
        lv.setStyleSheet(
            f"font-size:{_FONT};font-weight:bold;color:{_TEXT};background:transparent;"
        )
        lv.setAlignment(Qt.AlignmentFlag.AlignCenter)
        ahl.addWidget(la, 1)
        ahl.addWidget(lv, 1)
        vl.addWidget(ah)

        body = QWidget()
        gl = QGridLayout(body)
        gl.setContentsMargins(0, 0, 0, 0)
        gl.setSpacing(0)
        gl.setColumnStretch(1, 1)

        self._prop_edits = {}
        for row, (pk, val) in enumerate(_DEFAULT_DRAWER_PROPS):
            nk = QLabel(pk)
            nk.setFixedHeight(_DATA_ROW_H + 1)
            nk.setStyleSheet(
                f"font-size:{_FONT};color:{_TEXT};background:white;"
                f"border:1px solid {_BORD_L};padding-left:3px;"
            )
            nk.setAlignment(
                Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
            )
            gl.addWidget(nk, row, 0)
            le = QLineEdit(val)
            le.setFixedHeight(_DATA_ROW_H + 1)
            le.setAlignment(Qt.AlignmentFlag.AlignCenter)
            le.setStyleSheet(
                f"QLineEdit{{border:1px solid {_BORD_L};background:white;"
                f"font-size:{_FONT};padding:0 2px;}}"
            )
            gl.addWidget(le, row, 1)
            self._prop_edits[pk] = le

        sc = QScrollArea()
        sc.setWidget(body)
        sc.setWidgetResizable(True)
        sc.setFrameShape(QFrame.Shape.NoFrame)
        sc.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        sc.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        sc.setStyleSheet(
            "QScrollArea{border:none;background:transparent;}"
            "QScrollBar:vertical{background:#f0f2f5;width:4px;}"
            "QScrollBar::handle:vertical{background:#c0c4cc;border-radius:2px;}"
        )
        vl.addWidget(sc, 1)
        return wrap

    # ── 右侧：仅抽屉式样模板（四宫格之右上）─────────────────────────────────────

    def _build_right(self) -> QWidget:
        w = QWidget()
        vl = QVBoxLayout(w)
        vl.setContentsMargins(4, 4, 4, 3)
        vl.setSpacing(3)

        # 式样卡片（2 列 × 3 行，可滚动）
        tpl_grid = QWidget()
        tpl_grid.setStyleSheet(f"background:{_BG};")
        tg = QGridLayout(tpl_grid)
        tg.setContentsMargins(1, 1, 1, 1)
        tg.setSpacing(3)
        tg.setColumnStretch(0, 1)
        tg.setColumnStretch(1, 1)

        self._type_cards: dict[str, _DrawerCard] = {}
        for i, name in enumerate(_DRAWER_TYPES):
            card = _DrawerCard(self._icon_dir, name)
            card.selected.connect(self._on_type_selected)
            tg.addWidget(card, i // 2, i % 2)
            self._type_cards[name] = card
        self._type_cards["A抽屉"].set_selected(True)

        sc = QScrollArea()
        sc.setWidget(tpl_grid)
        sc.setWidgetResizable(True)
        sc.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        sc.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        sc.setStyleSheet(
            f"QScrollArea{{border:1px solid {_BORD_L};background:{_BG};}}"
            f"QScrollBar:vertical{{background:#f0f2f5;width:4px;}}"
            f"QScrollBar::handle:vertical{{background:#c0c4cc;border-radius:2px;}}"
        )
        vl.addWidget(sc, 1)

        return w

    # ── 底部按钮 ─────────────────────────────────────────────────────────────

    def _build_footer(self) -> QWidget:
        w = QWidget()
        w.setFixedHeight(28)
        w.setStyleSheet(f"background:{_HDR};")
        hl = QHBoxLayout(w)
        hl.setContentsMargins(6, 3, 6, 3)
        hl.setSpacing(6)
        hl.addStretch(1)

        b1 = _btn("应用到选中", w=72, h=22)
        b1.clicked.connect(lambda: self._on_apply(False))
        hl.addWidget(b1)

        b2 = _btn("应用到所有", w=72, h=22)
        b2.setStyleSheet(
            f"QPushButton{{border:1px solid {_BORD};background:#c8daf0;"
            f"font-size:{_FONT};font-weight:bold;padding:0 4px;}}"
            f"QPushButton:hover{{background:#b0cae8;}}"
            f"QPushButton:pressed{{background:#98b8dc;}}"
        )
        b2.clicked.connect(lambda: self._on_apply(True))
        hl.addWidget(b2)
        return w

    # ── 逻辑 ─────────────────────────────────────────────────────────────────

    def _on_type_selected(self, name: str):
        self._sel_type = name
        for n, card in self._type_cards.items():
            card.set_selected(n == name)

    def _on_grid_change(self):
        rows = self._spin_rows.value()
        cols = self._spin_cols.value()
        self._bottom.set_rows_cols(rows, cols)
        self._refresh_preview_img()

    def _refresh_preview_img(self):
        r = getattr(self._spin_rows if hasattr(self, "_spin_rows") else None, "value", lambda: 2)()
        c = getattr(self._spin_cols if hasattr(self, "_spin_cols") else None, "value", lambda: 2)()
        lbl = getattr(self, "_preview_lbl", None)
        if not lbl:
            return
        iw = max(16, lbl.width() - 4)
        ih = max(14, lbl.height() - 4)
        pm = _load_pm_fit(self._icon_dir, _DRAWER_FACE_ICON, iw, ih)
        if pm is None:
            pm = _load_pm(self._icon_dir, "抽屉预览", iw, ih)
        if pm is None:
            pm = _draw_drawer_grid(min(r, 3), min(c, 3), 12, 8)
            if not pm.isNull():
                pm = pm.scaled(iw, ih, Qt.AspectRatioMode.KeepAspectRatio,
                               Qt.TransformationMode.SmoothTransformation)
        if pm and not pm.isNull():
            lbl.setPixmap(pm)
            lbl.setStyleSheet(
                f"border:1px solid {_BORD};background:#f8f8f8;"
            )
        else:
            lbl.clear()
            lbl.setStyleSheet(
                f"border:1px solid {_BORD};background:{_ORANGE};"
            )

    def _quick_cover(self, label: str):
        cover = {"全盖","半盖","不盖"}
        gap   = {"全缝","半缝","无缝"}
        if label in cover:
            for cb in [self._cb_top_cover, self._cb_bot_cover,
                       self._cb_left_cover, self._cb_right_cover]:
                cb.setCurrentText(label)
        if label in gap:
            for cb in [self._cb_top_gap, self._cb_bot_gap,
                       self._cb_left_gap, self._cb_right_gap]:
                cb.setCurrentText(label)

    def _on_apply(self, to_all: bool):
        self._result = {
            "drawer_type":  self._sel_type,
            "cover": {
                "top":   self._cb_top_cover.currentText(),
                "bot":   self._cb_bot_cover.currentText(),
                "left":  self._cb_left_cover.currentText(),
                "right": self._cb_right_cover.currentText(),
            },
            "gap": {
                "top":   self._cb_top_gap.currentText(),
                "bot":   self._cb_bot_gap.currentText(),
                "left":  self._cb_left_gap.currentText(),
                "right": self._cb_right_gap.currentText(),
            },
            "rows":          self._spin_rows.value(),
            "cols":          self._spin_cols.value(),
            "type_code":     self._le_type.text(),
            "handle_pos":    self._cb_handle_pos.currentText(),
            "no_handle_ext": self._cb_no_handle.currentText(),
            "handle_rotate": self._chk_rotate.isChecked(),
            "top_gap":       self._le_top_gap.text(),
            "mid_gap":       self._le_mid_gap.text(),
            "bot_gap":       self._le_bot_gap.text(),
            "box_top":       self._le_box_top.text(),
            "box_bot":       self._le_box_bot.text(),
            "col_widths":    self._bottom.get_widths(),
            "col_ratios":    self._bottom.get_ratios(),
            "props":         {k: w.text() for k, w in self._prop_edits.items()},
            "apply_to_all":  to_all,
        }
        self.accept()

    def get_result(self) -> dict:
        return self._result

    # ── 无边框拖动 ───────────────────────────────────────────────────────────

    def mousePressEvent(self, ev):
        if (ev.button() == Qt.MouseButton.LeftButton
                and ev.position().y() < self._titlebar.height()):
            self._drag = ev.globalPosition().toPoint() - self.frameGeometry().topLeft()
        else:
            self._drag = None
        super().mousePressEvent(ev)

    def mouseMoveEvent(self, ev):
        if getattr(self, "_drag", None) and ev.buttons() & Qt.MouseButton.LeftButton:
            self.move(ev.globalPosition().toPoint() - self._drag)
        else:
            super().mouseMoveEvent(ev)

    def mouseReleaseEvent(self, ev):
        self._drag = None
        super().mouseReleaseEvent(ev)


# ── 独立运行预览 ──────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys
    from PySide6.QtWidgets import QApplication, QMainWindow

    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    icon_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "icons")

    win = QMainWindow()
    win.setWindowTitle("测试入口")
    win.resize(240, 70)
    btn = QPushButton("打开「添加抽屉组」", win)
    btn.setGeometry(10, 10, 220, 40)

    def _open():
        dlg = AddDrawerDialog(icon_dir=icon_dir,
                              space_w=564, space_h=1013, space_d=580,
                              parent=win)
        if dlg.exec():
            import json
            print(json.dumps(dlg.get_result(), ensure_ascii=False, indent=2))
        else:
            print("取消")

    btn.clicked.connect(_open)
    win.show()
    sys.exit(app.exec())