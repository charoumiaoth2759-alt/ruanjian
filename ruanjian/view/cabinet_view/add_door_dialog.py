# -*- coding: utf-8 -*-
"""
AddDoorDialog — 添加门板对话框
=====================================
集成方式（cabinet_assembler.py）：
    from add_door_dialog import AddDoorDialog
    self.sig_add_door.connect(self._open_door_dialog)

    def _open_door_dialog(self):
        dlg = AddDoorDialog(icon_dir=self._icon_dir,
                            space_w=564, space_h=1013, space_d=580,
                            parent=self)
        if dlg.exec():
            data = dlg.get_result()   # dict

shiyitu 图片命名规则：
    icons/shiyitu/左开.png   icons/shiyitu/右开.png
    icons/shiyitu/对开.png   （2扇及以上对开用，没有则用代码绘制）
"""
from __future__ import annotations
import os

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPainter, QPen, QPixmap, QBrush
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QDialog, QFrame,
    QGridLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QScrollArea, QSizePolicy,
    QSpinBox, QVBoxLayout, QWidget,
)

# ── 颜色 ──────────────────────────────────────────────────────────────────────
_BG     = "#f0f0f0"
_WHITE  = "#ffffff"
_BORD   = "#999999"
_BORD_L = "#cccccc"
_BLUE   = "#3a6a98"
_TEXT   = "#202020"
_HDR    = "#e0e0e0"
_CELL   = "#f5f5f5"
_ORANGE = "#e8c89a"
_TITBAR = "#2c3e50"

# ── 路径工具 ──────────────────────────────────────────────────────────────────

def _shiyitu_png(icon_dir: str, name: str) -> str:
    """icons/shiyitu/{name}.png，不存在返回空字符串"""
    if not icon_dir:
        return ""
    p = os.path.join(icon_dir, "shiyitu", f"{name}.png")
    return p if os.path.isfile(p) else ""


# ── 代码绘制门板（后备） ──────────────────────────────────────────────────────

def _draw_single(direction: str, w: int, h: int) -> QPixmap:
    """单扇：左开 或 右开"""
    pix = QPixmap(w, h)
    pix.fill(QColor(_ORANGE))
    p = QPainter(pix)
    p.setRenderHint(QPainter.RenderHint.Antialiasing, False)
    p.setPen(QPen(QColor("#8B5E3C"), 1))
    p.drawRect(1, 1, w - 2, h - 2)
    p.setPen(QPen(QColor("#A07040"), 1, Qt.PenStyle.DashLine))
    p.drawLine(2, 2, w - 2, h - 2)
    p.drawLine(w - 2, 2, 2, h - 2)
    hinge_left = (direction == "左开")
    hx = 3 if hinge_left else w - 4
    p.setPen(QPen(QColor("#555"), 2, Qt.PenStyle.SolidLine))
    for yy in [h // 4, h // 2, 3 * h // 4]:
        p.drawLine(hx, yy - 4, hx, yy + 4)
    hx2 = w - 8 if hinge_left else 8
    p.setPen(QPen(QColor("#707070"), 1))
    p.setBrush(QBrush(QColor("#888")))
    p.drawRect(hx2 - 1, h // 2 - 8, 3, 16)
    p.end()
    return pix


def _draw_multi(count: int, directions: list[str], w: int, h: int) -> QPixmap:
    """多扇拼接绘制"""
    pix = QPixmap(w, h)
    pix.fill(QColor(_ORANGE))
    p = QPainter(pix)
    p.setRenderHint(QPainter.RenderHint.Antialiasing, False)
    dw = (w - 2) / count
    for i in range(count):
        x = int(1 + i * dw)
        sw = int(dw)
        direction = directions[i] if i < len(directions) else "左开"
        # fill
        p.fillRect(x, 1, sw, h - 2, QColor(_ORANGE))
        # X
        p.setPen(QPen(QColor("#A07040"), 1, Qt.PenStyle.DashLine))
        p.drawLine(x, 1, x + sw, h - 1)
        p.drawLine(x + sw, 1, x, h - 1)
        # hinge
        hinge_left = (direction == "左开")
        hx = x + 2 if hinge_left else x + sw - 2
        p.setPen(QPen(QColor("#555"), 2, Qt.PenStyle.SolidLine))
        for yy in [h // 4, h // 2, 3 * h // 4]:
            p.drawLine(hx, yy - 4, hx, yy + 4)
        # handle
        hx2 = x + sw - 7 if hinge_left else x + 7
        p.setPen(QPen(QColor("#707070"), 1))
        p.setBrush(QBrush(QColor("#888")))
        p.drawRect(hx2 - 1, h // 2 - 8, 3, 16)
        # divider
        p.setPen(QPen(QColor("#8B5E3C"), 1, Qt.PenStyle.SolidLine))
        p.setBrush(QBrush(Qt.BrushStyle.NoBrush))
        p.drawRect(x, 1, sw, h - 2)
    # outer frame
    p.setPen(QPen(QColor("#555"), 2))
    p.drawRect(0, 0, w - 1, h - 1)
    p.end()
    return pix


def _preview_pixmap(icon_dir: str, count: int,
                    directions: list[str], w: int, h: int) -> QPixmap:
    """
    左上预览图：
      count==1 → 用 左开.png / 右开.png
      count>=2 → 用 对开.png（若有），否则代码绘制多扇
    """
    if count == 1:
        name = directions[0] if directions else "左开"
        path = _shiyitu_png(icon_dir, name)
        if path:
            raw = QPixmap(path)
            if not raw.isNull():
                return raw.scaled(w, h, Qt.AspectRatioMode.IgnoreAspectRatio,
                                  Qt.TransformationMode.SmoothTransformation)
        return _draw_single(name, w, h)
    else:
        path = _shiyitu_png(icon_dir, "对开")
        if path:
            raw = QPixmap(path)
            if not raw.isNull():
                return raw.scaled(w, h, Qt.AspectRatioMode.IgnoreAspectRatio,
                                  Qt.TransformationMode.SmoothTransformation)
        return _draw_multi(count, directions, w, h)


def _cell_pixmap(icon_dir: str, direction: str, w: int, h: int) -> QPixmap:
    """底部表格单格示意图：优先 shiyitu/左开.png 等，fallback 代码绘制"""
    path = _shiyitu_png(icon_dir, direction)
    if path:
        raw = QPixmap(path)
        if not raw.isNull():
            return raw.scaled(w, h, Qt.AspectRatioMode.IgnoreAspectRatio,
                              Qt.TransformationMode.SmoothTransformation)
    return _draw_single(direction, w, h)


# ── 小部件工厂 ────────────────────────────────────────────────────────────────

def _hline() -> QFrame:
    f = QFrame()
    f.setFrameShape(QFrame.Shape.HLine)
    f.setStyleSheet(f"color:{_BORD};")
    f.setFixedHeight(1)
    return f


def _combo(options: list[str], current: str = "", w: int = 0) -> QComboBox:
    cb = QComboBox()
    cb.addItems(options)
    if current in options:
        cb.setCurrentText(current)
    cb.setFixedHeight(14)
    if w:
        cb.setFixedWidth(w)
    cb.setStyleSheet(
        f"QComboBox{{border:1px solid {_BORD};background:white;"
        f"font-size:11px;padding:0 2px;}}"
        f"QComboBox::drop-down{{width:9px;}}"
    )
    return cb


def _lineedit(val: str = "", fixed_w: int = 0) -> QLineEdit:
    le = QLineEdit(val)
    le.setFixedHeight(14)
    if fixed_w:
        le.setFixedWidth(fixed_w)
    le.setStyleSheet(
        f"QLineEdit{{border:1px solid {_BORD};background:white;"
        f"font-size:11px;padding:0 3px;}}"
    )
    return le


def _pushbtn(text: str, w: int = 0, h: int = 14) -> QPushButton:
    b = QPushButton(text)
    b.setFixedHeight(h)
    if w:
        b.setFixedWidth(w)
    b.setStyleSheet(
        f"QPushButton{{border:1px solid {_BORD};background:{_HDR};"
        f"font-size:11px;padding:0 6px;}}"
        f"QPushButton:hover{{background:#d0d8e8;}}"
        f"QPushButton:pressed{{background:#b8c8dc;}}"
    )
    return b


def _row_label(text: str, w: int = 37) -> QLabel:
    lbl = QLabel(text)
    lbl.setFixedWidth(w)
    lbl.setFixedHeight(15)
    lbl.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
    lbl.setStyleSheet(
        f"font-size:11px;color:{_TEXT};background:{_HDR};"
        f"border:1px solid {_BORD_L};padding:0 3px;"
    )
    return lbl


def _cell_label(text: str) -> QLabel:
    lbl = QLabel(text)
    lbl.setFixedHeight(15)
    lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
    lbl.setStyleSheet(
        f"font-size:11px;color:{_TEXT};background:white;"
        f"border:1px solid {_BORD_L};"
    )
    return lbl


# ── 标题栏 ────────────────────────────────────────────────────────────────────

class _TitleBar(QWidget):
    def __init__(self, title: str, space_w, space_h, space_d, dlg, parent=None):
        super().__init__(parent)
        self.setFixedHeight(28)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setStyleSheet(f"_TitleBar {{ background-color: {_TITBAR}; }}")
        hl = QHBoxLayout(self)
        hl.setContentsMargins(6, 0, 4, 0)
        hl.setSpacing(10)

        t = QLabel(title)
        t.setStyleSheet("color:white;font-size:12px;font-weight:bold;background:transparent;")
        hl.addWidget(t)

        info = QLabel(f"空间  W  {space_w}    H  {space_h}    D  {space_d}")
        info.setStyleSheet("color:#d0e4f8;font-size:11px;background:transparent;")
        hl.addWidget(info, 1)

        x = QPushButton("×")
        x.setFixedSize(12, 12)
        x.setStyleSheet(
            "QPushButton{background:#c0392b;color:white;border:none;font-size:13px;}"
            "QPushButton:hover{background:#e74c3c;}"
        )
        x.clicked.connect(dlg.reject)
        hl.addWidget(x)


# ── 拉手定位九宫格 ────────────────────────────────────────────────────────────

_GRID_DEF = [
    # num, tick_top, tick_bot, tick_left, tick_right, selected
    (3, True,  False, False, False, False),
    (6, True,  True,  False, False, False),
    (3, True,  False, False, False, False),
    (2, False, False, True,  False, False),
    (5, False, True,  False, False, True ),
    (2, False, False, False, True,  False),
    (1, False, True,  False, False, False),
    (4, False, True,  False, False, False),
    (1, False, True,  False, False, False),
]


class _HandleCell(QWidget):
    def __init__(self, num, tt, tb, tl, tr, sel, parent=None):
        super().__init__(parent)
        self._sel = sel
        self._ticks = (tt, tb, tl, tr)
        self.setFixedSize(27, 23)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self._update_bg()
        lbl = QLabel(str(num), self)
        lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl.setGeometry(0, 0, 27, 23)
        lbl.setStyleSheet("font-size:12px;font-weight:bold;background:transparent;border:none;")

    def _update_bg(self):
        if self._sel:
            self.setStyleSheet("background:#d8e8f8;border:2px solid #6699cc;")
        else:
            self.setStyleSheet(f"background:white;border:1px solid {_BORD};")

    def paintEvent(self, ev):
        super().paintEvent(ev)
        p = QPainter(self)
        p.setPen(QPen(QColor("#888"), 1))
        W, H = self.width(), self.height()
        tt, tb, tl, tr = self._ticks
        mx, my = W // 2, H // 2
        if tt: p.drawLine(mx - 4, 2, mx + 4, 2)
        if tb: p.drawLine(mx - 4, H - 2, mx + 4, H - 2)
        if tl: p.drawLine(2, my - 4, 2, my + 4)
        if tr: p.drawLine(W - 2, my - 4, W - 2, my + 4)
        p.end()

    def mousePressEvent(self, ev):
        self._sel = not self._sel
        self._update_bg()
        self.update()


class _HandleGrid(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        g = QGridLayout(self)
        g.setContentsMargins(2, 2, 2, 2)
        g.setSpacing(2)
        for i, (num, tt, tb, tl, tr, sel) in enumerate(_GRID_DEF):
            g.addWidget(_HandleCell(num, tt, tb, tl, tr, sel), i // 3, i % 3)


# ── 门板预览（左上区域）────────────────────────────────────────────────────────

class _PreviewLabel(QLabel):
    """固定尺寸的门板预览图标签"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(87, 73)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setStyleSheet(f"border:1px solid {_BORD};background:{_ORANGE};")

    def update_image(self, icon_dir: str, count: int, directions: list[str]):
        pm = _preview_pixmap(icon_dir, count, directions, 128, 108)
        self.setPixmap(pm)


# ── 底部门扇明细区（核心：行+列布局，参考图2样式）─────────────────────────────

_ATTR_ROWS = [
    "门宽预计", "分布比例", "门板朝向", "示意图例",
    "门型编号", "拉手位置", "铰链类型", "封边厚度", "图元变换", "门板分段",
]

_ROW_LABEL_W   = 39   # 行标签宽
_COL_MIN_W     = 60   # 每扇列最小宽度
_DIAG_H        = 47   # 示意图例行高
_NORMAL_ROW_H  = 15   # 普通行高


def _hinge_default(col: int, count: int) -> str:
    if count == 1:
        return "不盖"
    if col == 0 or col == count - 1:
        return "全盖"
    return "半盖"


def _directions_default(count: int) -> list[str]:
    if count == 1:
        return ["左开"]
    return ["左开" if i % 2 == 0 else "右开" for i in range(count)]


class _DoorDetailArea(QWidget):
    """
    底部门扇明细区：
      - 左列：行标签（固定宽度）
      - 右侧：每扇门一列，动态宽度
      - 门扇数量变化时整体重建
    """

    def __init__(self, icon_dir: str, count: int = 1, parent=None):
        super().__init__(parent)
        self._icon_dir = icon_dir
        self._count = count
        self._directions: list[str] = _directions_default(count)
        self._layout = QGridLayout(self)
        self._layout.setContentsMargins(4, 4, 4, 4)
        self._layout.setSpacing(0)
        self._rebuild()

    # ── 公开 API ──────────────────────────────────────────────────────────────

    def set_count(self, count: int):
        count = max(1, min(count, 12))
        if count != self._count:
            self._count = count
            self._directions = _directions_default(count)
            self._rebuild()

    def get_directions(self) -> list[str]:
        return list(self._directions)

    def get_data(self) -> list[dict]:
        result = []
        for col in range(self._count):
            d: dict = {}
            for row_i, row_name in enumerate(_ATTR_ROWS):
                if row_name == "示意图例":
                    continue
                w = self._layout.itemAtPosition(row_i, col + 1)
                if w and w.widget():
                    ww = w.widget()
                    if isinstance(ww, QComboBox):
                        d[row_name] = ww.currentText()
                    elif isinstance(ww, QLineEdit):
                        d[row_name] = ww.text()
                    else:
                        d[row_name] = ww.text() if hasattr(ww, "text") else ""
                else:
                    d[row_name] = ""
            result.append(d)
        return result

    # ── 内部 ──────────────────────────────────────────────────────────────────

    def _clear(self):
        while self._layout.count():
            item = self._layout.takeAt(0)
            if item and item.widget():
                item.widget().deleteLater()

    def _rebuild(self):
        self._clear()
        g = self._layout
        g.setColumnMinimumWidth(0, _ROW_LABEL_W)

        # 列宽
        for col in range(self._count):
            g.setColumnMinimumWidth(col + 1, _COL_MIN_W)
            g.setColumnStretch(col + 1, 1)

        for row_i, row_name in enumerate(_ATTR_ROWS):
            # 行标签
            lbl = _row_label(row_name, _ROW_LABEL_W)
            if row_name == "示意图例":
                lbl.setFixedHeight(_DIAG_H)
            g.addWidget(lbl, row_i, 0)

            for col in range(self._count):
                direction = self._directions[col]
                cell = self._make_cell(row_name, col, direction)
                g.addWidget(cell, row_i, col + 1)

        # 行高
        for row_i, row_name in enumerate(_ATTR_ROWS):
            if row_name == "示意图例":
                g.setRowMinimumHeight(row_i, _DIAG_H)
            else:
                g.setRowMinimumHeight(row_i, _NORMAL_ROW_H)

    def _make_cell(self, row_name: str, col: int, direction: str) -> QWidget:
        count = self._count

        if row_name == "门宽预计":
            le = _lineedit("120")
            le.setFixedHeight(_NORMAL_ROW_H)
            le.setStyleSheet(
                f"QLineEdit{{border:1px solid {_BORD_L};background:white;"
                f"font-size:11px;padding:0 3px;text-align:center;}}"
            )
            return le

        elif row_name == "分布比例":
            le = _lineedit("1")
            le.setFixedHeight(_NORMAL_ROW_H)
            le.setStyleSheet(
                f"QLineEdit{{border:1px solid {_BORD_L};background:white;"
                f"font-size:11px;padding:0 3px;text-align:center;}}"
            )
            return le

        elif row_name == "门板朝向":
            cb = _combo(["左开", "右开"], direction)
            cb.setFixedHeight(_NORMAL_ROW_H)
            cb.setStyleSheet(
                f"QComboBox{{border:1px solid {_BORD_L};background:white;"
                f"font-size:11px;padding:0 2px;}}"
                f"QComboBox::drop-down{{width:9px;}}"
            )
            cb.currentTextChanged.connect(
                lambda txt, c=col: self._on_dir_changed(c, txt)
            )
            return cb

        elif row_name == "示意图例":
            lbl = QLabel()
            lbl.setFixedHeight(_DIAG_H)
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lbl.setStyleSheet(
                f"border:1px solid {_BORD_L};background:{_ORANGE};"
            )
            pm = _cell_pixmap(self._icon_dir, direction, _COL_MIN_W - 4, _DIAG_H - 4)
            lbl.setPixmap(pm)
            return lbl

        elif row_name == "铰链类型":
            hinge = _hinge_default(col, count)
            cb = _combo(["全盖", "半盖", "不盖"], hinge)
            cb.setFixedHeight(_NORMAL_ROW_H)
            cb.setStyleSheet(
                f"QComboBox{{border:1px solid {_BORD_L};background:white;"
                f"font-size:11px;padding:0 2px;}}"
                f"QComboBox::drop-down{{width:9px;}}"
            )
            return cb

        elif row_name == "拉手位置":
            lbl = _cell_label("2")
            return lbl

        elif row_name == "封边厚度":
            lbl = _cell_label("G")
            return lbl

        elif row_name in ("门型编号", "图元变换", "门板分段"):
            le = _lineedit("")
            le.setFixedHeight(_NORMAL_ROW_H)
            le.setStyleSheet(
                f"QLineEdit{{border:1px solid {_BORD_L};background:white;"
                f"font-size:11px;padding:0 3px;}}"
            )
            return le

        else:
            return _cell_label("")

    def _on_dir_changed(self, col: int, direction: str):
        """门板朝向变化 → 更新该列示意图"""
        if col < len(self._directions):
            self._directions[col] = direction
        # 示意图在 "示意图例" 行
        row_i = _ATTR_ROWS.index("示意图例")
        item = self._layout.itemAtPosition(row_i, col + 1)
        if item and item.widget():
            lbl = item.widget()
            pm = _cell_pixmap(self._icon_dir, direction,
                              max(60, _COL_MIN_W - 4), _DIAG_H - 4)
            lbl.setPixmap(pm)


# ── 主对话框 ──────────────────────────────────────────────────────────────────

class AddDoorDialog(QDialog):
    """
    添加门板对话框，严格对照参考图布局。

    Parameters
    ----------
    icon_dir  : str   icons/ 目录，内含 shiyitu/ 子目录
    space_w/h/d : int 标题栏空间尺寸
    """

    def __init__(self, icon_dir: str = "", space_w=564, space_h=1013,
                 space_d=580, parent=None):
        super().__init__(parent)
        self._icon_dir = icon_dir
        self._result: dict = {}

        self.setWindowFlags(Qt.WindowType.Dialog | Qt.WindowType.FramelessWindowHint)
        self.setFixedSize(580, 453)
        self.setStyleSheet(f"QDialog{{background:{_BG};border:1px solid #888;}}")

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ── 标题栏 ──────────────────────────────────────────────────────────
        self._title_bar = _TitleBar("添加门板", space_w, space_h, space_d, self)
        root.addWidget(self._title_bar)

        # ── 上半：三列 ───────────────────────────────────────────────────────
        top = QHBoxLayout()
        top.setContentsMargins(6, 6, 6, 4)
        top.setSpacing(8)
        top.addWidget(self._build_left(), 0)
        top.addWidget(self._build_middle(), 1)
        top.addWidget(self._build_right(), 0)
        root.addLayout(top)

        root.addWidget(_hline())

        # ── 下半：可滚动的门扇明细 ───────────────────────────────────────────
        self._detail = _DoorDetailArea(icon_dir, count=1)

        scroll = QScrollArea()
        scroll.setWidget(self._detail)
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll.setStyleSheet(
            "QScrollArea{border:none;background:#fafafa;}"
            "QScrollBar:vertical{background:#f0f2f5;width:6px;}"
            "QScrollBar::handle:vertical{background:#c0c4cc;border-radius:3px;}"
            "QScrollBar:horizontal{background:#f0f2f5;height:6px;}"
            "QScrollBar::handle:horizontal{background:#c0c4cc;border-radius:3px;}"
        )
        root.addWidget(scroll, 1)

        root.addWidget(_hline())

        # ── 底部按钮栏 ───────────────────────────────────────────────────────
        root.addWidget(self._build_footer())

        # 初始化预览
        self._sync_preview()

    # ── 左侧：四周尺寸外盖 / 门缝值 ─────────────────────────────────────────

    def _build_left(self) -> QWidget:
        w = QWidget()
        w.setFixedWidth(197)
        vl = QVBoxLayout(w)
        vl.setContentsMargins(0, 0, 0, 0)
        vl.setSpacing(4)

        sec = QLabel("四周尺寸外盖 / 门缝值")
        sec.setStyleSheet(
            f"font-size:11px;color:{_TEXT};border-bottom:1px solid {_BORD_L};padding-bottom:2px;"
        )
        vl.addWidget(sec)

        gb = QWidget()
        gb.setStyleSheet(f"background:#fafafa;border:1px solid {_BORD};")
        gl = QVBoxLayout(gb)
        gl.setContentsMargins(4, 6, 4, 6)
        gl.setSpacing(4)

        # 顶部下拉（居中）
        top_row = QHBoxLayout()
        top_row.addStretch(1)
        self._cb_top_cover = _combo(["全盖","半盖","不盖"], "全盖", 39)
        self._cb_top_gap   = _combo(["半缝","全缝","无缝"], "半缝", 58)
        top_row.addWidget(self._cb_top_cover)
        top_row.addWidget(self._cb_top_gap)
        top_row.addStretch(1)
        gl.addLayout(top_row)

        # 中间：左下拉 | 预览图 | 右下拉
        mid = QHBoxLayout()
        mid.setSpacing(4)

        lv = QVBoxLayout()
        lv.setSpacing(4)
        self._cb_left_cover = _combo(["全盖","半盖","不盖"], "全盖", 58)
        self._cb_left_gap   = _combo(["半缝","全缝","无缝"], "半缝", 58)
        lv.addWidget(self._cb_left_cover)
        lv.addWidget(self._cb_left_gap)
        lv.addStretch()
        mid.addLayout(lv)

        self._preview = _PreviewLabel()
        mid.addWidget(self._preview, 1)

        rv = QVBoxLayout()
        rv.setSpacing(4)
        self._cb_right_cover = _combo(["全盖","半盖","不盖"], "全盖", 58)
        self._cb_right_gap   = _combo(["半缝","全缝","无缝"], "半缝", 58)
        rv.addWidget(self._cb_right_cover)
        rv.addWidget(self._cb_right_gap)
        rv.addStretch()
        mid.addLayout(rv)

        gl.addLayout(mid)

        # 底部下拉（居中）
        bot_row = QHBoxLayout()
        bot_row.addStretch(1)
        self._cb_bot_cover = _combo(["全盖","半盖","不盖"], "全盖", 58)
        self._cb_bot_gap   = _combo(["半缝","全缝","无缝"], "半缝", 58)
        bot_row.addWidget(self._cb_bot_cover)
        bot_row.addWidget(self._cb_bot_gap)
        bot_row.addStretch(1)
        gl.addLayout(bot_row)

        vl.addWidget(gb)

        # 快捷按钮行
        qb = QHBoxLayout()
        qb.setSpacing(3)
        for lbl in ["全盖","半盖","不盖","全缝","半缝","无缝"]:
            b = _pushbtn(lbl)
            b.clicked.connect(lambda _, l=lbl: self._quick(l))
            qb.addWidget(b)
        vl.addLayout(qb)

        return w

    # ── 中间：通用属性 ───────────────────────────────────────────────────────

    def _build_middle(self) -> QWidget:
        w = QWidget()
        vl = QVBoxLayout(w)
        vl.setContentsMargins(0, 0, 0, 0)
        vl.setSpacing(4)

        sec = QLabel("通用属性")
        sec.setStyleSheet(
            f"font-size:11px;color:{_TEXT};border-bottom:1px solid {_BORD_L};padding-bottom:2px;"
        )
        vl.addWidget(sec)

        gb = QWidget()
        gb.setStyleSheet(f"background:#fafafa;border:1px solid {_BORD};")
        gl = QGridLayout(gb)
        gl.setContentsMargins(8, 8, 8, 8)
        gl.setSpacing(6)
        gl.setColumnStretch(1, 1)

        def lbl(t):
            l = QLabel(t)
            l.setStyleSheet(f"font-size:11px;color:{_TEXT};background:transparent;")
            l.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            return l

        # 门扇数量
        self._spin = QSpinBox()
        self._spin.setRange(1, 12)
        self._spin.setValue(1)
        self._spin.setFixedHeight(15)
        self._spin.setFixedWidth(53)
        self._spin.setStyleSheet(
            f"QSpinBox{{border:1px solid {_BORD};background:white;"
            f"font-size:11px;padding:0 3px;}}"
        )
        self._spin.valueChanged.connect(self._on_count)
        gl.addWidget(lbl("门扇数量"), 0, 0)
        gl.addWidget(self._spin, 0, 1, 1, 2)

        # 门扇厚度
        self._le_thick = _lineedit("K", 53)
        gl.addWidget(lbl("门扇厚度"), 1, 0)
        gl.addWidget(self._le_thick, 1, 1, 1, 2)

        # 门型编号
        self._le_type = _lineedit("")
        gl.addWidget(lbl("门型编号"), 2, 0)
        gl.addWidget(self._le_type, 2, 1)
        b1 = _pushbtn("选择", 27)
        gl.addWidget(b1, 2, 2)

        # 拉手型号
        self._cb_handle = _combo([], "")
        gl.addWidget(lbl("拉手型号"), 3, 0)
        gl.addWidget(self._cb_handle, 3, 1)
        b2 = _pushbtn("选择", 40)
        gl.addWidget(b2, 3, 2)

        # 孔位模板
        self._cb_hole = _combo(["铰链只打杯孔","铰链打全孔","无孔"], "铰链只打杯孔")
        gl.addWidget(lbl("孔位模板"), 4, 0)
        gl.addWidget(self._cb_hole, 4, 1, 1, 2)

        # 自定义MOD
        mod_btn = _pushbtn("选择自定义MOD门型", h=16)
        mod_btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        gl.addWidget(mod_btn, 5, 0, 1, 3)

        vl.addWidget(gb)
        vl.addStretch(1)
        return w

    # ── 右侧：拉手定位 + 附加属性 ───────────────────────────────────────────

    def _build_right(self) -> QWidget:
        w = QWidget()
        w.setFixedWidth(147)
        vl = QVBoxLayout(w)
        vl.setContentsMargins(0, 0, 0, 0)
        vl.setSpacing(4)

        # 拉手/定位位置
        s1 = QLabel("拉手/定位位置")
        s1.setStyleSheet(
            f"font-size:11px;color:{_TEXT};border-bottom:1px solid {_BORD_L};padding-bottom:2px;"
        )
        vl.addWidget(s1)

        hg = QWidget()
        hg.setStyleSheet(f"border:1px solid {_BORD};background:#fafafa;")
        hgl = QVBoxLayout(hg)
        hgl.setContentsMargins(4, 4, 4, 4)
        hgl.addWidget(_HandleGrid())
        vl.addWidget(hg)

        # 附加属性
        s2 = QLabel("附加属性")
        s2.setStyleSheet(
            f"font-size:11px;color:{_TEXT};border-bottom:1px solid {_BORD_L};padding-bottom:2px;"
        )
        vl.addWidget(s2)

        av = QWidget()
        av.setStyleSheet(f"border:1px solid {_BORD};background:#fafafa;")
        al = QVBoxLayout(av)
        al.setContentsMargins(0, 0, 0, 0)
        al.setSpacing(0)

        # 表头
        hdr_w = QWidget()
        hdr_w.setStyleSheet(f"background:{_HDR};border-bottom:1px solid {_BORD_L};")
        hdr_w.setFixedHeight(15)
        hdr_hl = QHBoxLayout(hdr_w)
        hdr_hl.setContentsMargins(6, 0, 6, 0)
        la = QLabel("附加属性")
        la.setStyleSheet(f"font-size:11px;font-weight:bold;color:{_TEXT};background:transparent;")
        lv2 = QLabel("属性值")
        lv2.setStyleSheet(f"font-size:11px;font-weight:bold;color:{_TEXT};background:transparent;")
        lv2.setAlignment(Qt.AlignmentFlag.AlignCenter)
        hdr_hl.addWidget(la, 1)
        hdr_hl.addWidget(lv2)
        al.addWidget(hdr_w)

        self._attr_cbs: dict[str, QCheckBox] = {}
        for name in ["添加立板","添加背板","纹理翻转","二次归方",
                     "配拉直器","配反弹器","拉手旋转","免拉手延伸"]:
            row = QWidget()
            row.setFixedHeight(15)
            row.setStyleSheet(
                "QWidget{background:white;border-bottom:1px solid #e0e0e0;}"
                "QWidget:hover{background:#eef2f8;}"
            )
            rl = QHBoxLayout(row)
            rl.setContentsMargins(6, 0, 6, 0)
            ll = QLabel(name)
            ll.setStyleSheet(f"font-size:11px;color:{_TEXT};background:transparent;")
            cb = QCheckBox()
            cb.setStyleSheet(
                f"QCheckBox::indicator{{width:8px;height:8px;"
                f"border:1px solid {_BORD};background:white;}}"
                f"QCheckBox::indicator:checked{{background:{_BLUE};border-color:{_BLUE};}}"
            )
            rl.addWidget(ll, 1)
            rl.addWidget(cb)
            self._attr_cbs[name] = cb
            al.addWidget(row)

        vl.addWidget(av)
        vl.addStretch(1)
        return w

    # ── 底部按钮栏 ───────────────────────────────────────────────────────────

    def _build_footer(self) -> QWidget:
        w = QWidget()
        w.setFixedHeight(24)
        w.setStyleSheet(f"background:{_HDR};")
        hl = QHBoxLayout(w)
        hl.setContentsMargins(8, 4, 8, 4)

        self._chk_flat = QCheckBox("添加为榄槅米平躺门")
        self._chk_flat.setStyleSheet(
            f"QCheckBox{{font-size:11px;color:{_TEXT};}}"
            f"QCheckBox::indicator{{width:9px;height:9px;"
            f"border:1px solid {_BORD};background:white;}}"
            f"QCheckBox::indicator:checked{{background:{_BLUE};border-color:{_BLUE};}}"
        )
        hl.addWidget(self._chk_flat, 1)

        ok_btn = _pushbtn("添加 OR 修改", w=67, h=17)
        ok_btn.setStyleSheet(
            f"QPushButton{{border:1px solid {_BORD};background:#e0e0e0;"
            f"font-size:12px;font-weight:bold;}}"
            f"QPushButton:hover{{background:#d0e0f0;}}"
            f"QPushButton:pressed{{background:#b0c8dc;}}"
        )
        ok_btn.clicked.connect(self._on_add)
        hl.addWidget(ok_btn)
        return w

    # ── 逻辑 ────────────────────────────────────────────────────────────────

    def _on_count(self, count: int):
        self._detail.set_count(count)
        self._sync_preview()

    def _sync_preview(self):
        count = self._spin.value()
        dirs = self._detail.get_directions()
        self._preview.update_image(self._icon_dir, count, dirs)

    def _quick(self, label: str):
        cover_opts = {"全盖","半盖","不盖"}
        gap_opts   = {"全缝","半缝","无缝"}
        if label in cover_opts:
            for cb in [self._cb_top_cover, self._cb_bot_cover,
                       self._cb_left_cover, self._cb_right_cover]:
                cb.setCurrentText(label)
        if label in gap_opts:
            for cb in [self._cb_top_gap, self._cb_bot_gap,
                       self._cb_left_gap, self._cb_right_gap]:
                cb.setCurrentText(label)

    def _on_add(self):
        self._result = {
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
            "count":       self._spin.value(),
            "thickness":   self._le_thick.text(),
            "type_code":   self._le_type.text(),
            "hole_tpl":    self._cb_hole.currentText(),
            "flat_door":   self._chk_flat.isChecked(),
            "attributes":  {k: v.isChecked() for k, v in self._attr_cbs.items()},
            "doors":       self._detail.get_data(),
        }
        self.accept()

    def get_result(self) -> dict:
        return self._result

    # ── 拖动无边框窗口 ───────────────────────────────────────────────────────

    def mousePressEvent(self, ev):
        if ev.button() == Qt.MouseButton.LeftButton and \
                ev.position().y() < self._title_bar.height():
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
    win.resize(173, 53)
    btn = QPushButton("打开「添加门板」", win)
    btn.setGeometry(13, 13, 147, 27)

    def _open():
        dlg = AddDoorDialog(icon_dir=icon_dir,
                            space_w=435, space_h=750, space_d=332, parent=win)
        if dlg.exec():
            import json
            print(json.dumps(dlg.get_result(), ensure_ascii=False, indent=2))

    btn.clicked.connect(_open)
    win.show()
    sys.exit(app.exec())