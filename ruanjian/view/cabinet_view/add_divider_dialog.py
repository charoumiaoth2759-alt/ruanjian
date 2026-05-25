# -*- coding: utf-8 -*-
"""加分割面对话框 —— add_divider_dialog.py

弹出对话框，供用户选择分割面方向（上下 / 左右 / 前后）及定位方式（靠下/靠上/分布），
并可设置"允许跨界碰撞出孔"选项。

使用方式：
    在 cabinet_assembler.py 的 _IconGrid._make_btn 中，对槽位 18（加分割面）的
    icon_clicked 信号连接到此对话框。

    from add_divider_dialog import AddDividerDialog
    dlg = AddDividerDialog(icon_dir=self._icon_dir, parent=self)
    if dlg.exec():
        result = dlg.get_result()
        # result 示例：
        # {'direction': 'ud', 'mode': 'dist', 'value': 0, 'count': 2, 'allow_cross': False}
"""

from __future__ import annotations
import os, sys

from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QIcon, QPixmap, QColor, QPainter, QFont
from PySide6.QtWidgets import (
    QApplication, QButtonGroup, QCheckBox, QComboBox, QDialog,
    QDialogButtonBox, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QRadioButton, QSpinBox, QVBoxLayout, QWidget, QFrame,
)

# ─── 颜色常量（与主程序保持一致）────────────────────────────────────────────

_TITLE_TOP   = "#3d5a6e"
_TITLE_BTM   = "#2c3e50"
_BG          = "#f0f0f0"
_BORD        = "#b0b0b0"
_BLUE        = "#1a6fc4"
_TEXT        = "#222222"
_BTN_BG      = "#e8e8e8"
_BTN_OK_TOP  = "#3d5a6e"
_BTN_OK_BTM  = "#2c3e50"

# ─── 图标路径解析 ─────────────────────────────────────────────────────────────

def _resolve_shiyitu_dir(icon_dir: str) -> str:
    """返回 icons/shiyitu/ 目录，不存在则返回空串。"""
    p = os.path.join(icon_dir, "shiyitu")
    return p if os.path.isdir(p) else ""


def _load_pixmap(icon_dir: str, filename: str, size: int) -> QPixmap:
    """从 icons/shiyitu/<filename> 加载图片，失败则生成占位图。"""
    shiyitu = _resolve_shiyitu_dir(icon_dir)
    path = os.path.join(shiyitu, filename) if shiyitu else ""
    if path and os.path.isfile(path):
        pix = QPixmap(path)
        if not pix.isNull():
            return pix.scaled(
                size, size,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
    # ── 占位图：灰底 + 文字 ──
    pix = QPixmap(size, size)
    pix.fill(QColor("#d0d0d0"))
    painter = QPainter(pix)
    painter.setPen(QColor("#666666"))
    font = QFont()
    font.setPixelSize(max(9, size // 5))
    painter.setFont(font)
    label = os.path.splitext(filename)[0]          # 去掉 .png 后缀
    painter.drawText(pix.rect(), Qt.AlignmentFlag.AlignCenter, label)
    painter.end()
    return pix


# ─── 自定义标题栏 ─────────────────────────────────────────────────────────────

class _TitleBar(QWidget):
    """深色渐变标题栏（#3d5a6e → #2c3e50），带标题文字与关闭按钮。"""

    def __init__(self, title: str, parent: QDialog):
        super().__init__(parent)
        self._dialog = parent
        self.setFixedHeight(28)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setStyleSheet(
            f"background: qlineargradient(x1:0,y1:0,x2:0,y2:1,"
            f"stop:0 {_TITLE_TOP}, stop:1 {_TITLE_BTM});"
        )

        lay = QHBoxLayout(self)
        lay.setContentsMargins(10, 0, 4, 0)
        lay.setSpacing(0)

        lbl = QLabel(title)
        lbl.setStyleSheet("color:#ffffff;font-size:13px;font-weight:bold;background:transparent;")
        lay.addWidget(lbl)
        lay.addStretch(1)

        close_btn = QPushButton("✕")
        close_btn.setFixedSize(20, 20)
        close_btn.setStyleSheet(
            "QPushButton{background:#c0392b;border:1px solid #8e2019;border-radius:2px;"
            "color:#ffffff;font-size:11px;}"
            "QPushButton:hover{background:#e74c3c;}"
        )
        close_btn.clicked.connect(parent.reject)
        lay.addWidget(close_btn)


# ─── 视图切换按钮（上下 / 左右 / 前后）──────────────────────────────────────

class _ViewTabBar(QWidget):
    """三个图片+文字切换按钮，互斥选中。"""

    # 方向 id → (图片文件名, 显示文字)
    _TABS = [
        ("ud", "上下.png", "上下"),
        ("lr", "左右.png", "左右"),
        ("fb", "前后.png", "前后"),
    ]
    _IMG_SIZE = 48   # 图片显示尺寸（px）

    def __init__(self, icon_dir: str, parent=None):
        super().__init__(parent)
        self._icon_dir = icon_dir
        self._buttons: dict[str, QPushButton] = {}
        self._current = "ud"

        lay = QHBoxLayout(self)
        lay.setContentsMargins(6, 4, 6, 0)
        lay.setSpacing(4)

        grp = QButtonGroup(self)
        grp.setExclusive(True)

        for did, fname, label in self._TABS:
            btn = QPushButton()
            btn.setCheckable(True)
            btn.setFixedSize(self._IMG_SIZE + 16, self._IMG_SIZE + 20)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)

            pix = _load_pixmap(icon_dir, fname, self._IMG_SIZE)
            btn.setIcon(QIcon(pix))
            btn.setIconSize(QSize(self._IMG_SIZE, self._IMG_SIZE))
            btn.setText(label)

            # 图标在上、文字在下
            btn.setToolButtonStyle if False else None
            btn.setStyleSheet(
                "QPushButton{"
                f"  background:{_BG};"
                "  border:1px solid #aaaaaa;"
                "  border-bottom:none;"
                "  border-radius:3px 3px 0 0;"
                "  font-size:12px;"
                f"  color:{_TEXT};"
                "  padding-top:2px;"
                "}"
                "QPushButton:checked{"
                "  background:#ffffff;"
                "  border:1px solid #888888;"
                "  border-bottom:2px solid #ffffff;"
                "  font-weight:bold;"
                f"  color:{_TITLE_BTM};"
                "}"
                "QPushButton:hover:!checked{"
                "  background:#e0e8f0;"
                "}"
            )

            # 因 QPushButton 不原生支持图标在上文字在下，
            # 用竖向布局内嵌 QLabel 代替
            inner = QWidget(btn)
            inner.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
            vl = QVBoxLayout(inner)
            vl.setContentsMargins(0, 4, 0, 4)
            vl.setSpacing(2)
            vl.setAlignment(Qt.AlignmentFlag.AlignCenter)

            img_lbl = QLabel()
            img_lbl.setPixmap(pix)
            img_lbl.setFixedSize(self._IMG_SIZE, self._IMG_SIZE)
            img_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            img_lbl.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
            vl.addWidget(img_lbl, 0, Qt.AlignmentFlag.AlignCenter)

            txt_lbl = QLabel(label)
            txt_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            txt_lbl.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
            txt_lbl.setStyleSheet(f"font-size:12px;color:{_TEXT};background:transparent;")
            vl.addWidget(txt_lbl, 0, Qt.AlignmentFlag.AlignCenter)

            inner.setGeometry(0, 0, btn.width(), btn.height())
            btn.resizeEvent = lambda e, w=inner, b=btn: w.setGeometry(0, 0, b.width(), b.height())

            # 隐藏 QPushButton 自身的图标与文字（用内嵌 QLabel 代替）
            btn.setIcon(QIcon())
            btn.setText("")

            grp.addButton(btn)
            lay.addWidget(btn)
            self._buttons[did] = btn

            btn.toggled.connect(lambda checked, d=did: self._on_toggled(d, checked))

        self._buttons["ud"].setChecked(True)
        lay.addStretch(1)

    def _on_toggled(self, did: str, checked: bool):
        if checked:
            self._current = did

    def current(self) -> str:
        return self._current


# ─── 分隔线 ──────────────────────────────────────────────────────────────────

class _HLine(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFrameShape(QFrame.Shape.HLine)
        self.setFrameShadow(QFrame.Shadow.Sunken)
        self.setFixedHeight(1)
        self.setStyleSheet(f"color:{_BORD};")


# ─── 主对话框 ─────────────────────────────────────────────────────────────────

class AddDividerDialog(QDialog):
    """加分割面对话框。

    参数
    ----
    icon_dir : str
        主程序 icons 目录路径（用于加载 shiyitu/上下.png 等图片）。
    parent : QWidget, optional
        父窗口。

    调用示例
    --------
    dlg = AddDividerDialog(icon_dir=self._icon_dir, parent=self)
    if dlg.exec():
        result = dlg.get_result()
    """

    def __init__(self, icon_dir: str = "", parent=None):
        super().__init__(parent)
        self._icon_dir = icon_dir or ""

        # ── 窗口基础属性 ──
        self.setWindowTitle("加分割面")
        self.setWindowFlags(
            Qt.WindowType.Dialog
            | Qt.WindowType.FramelessWindowHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setStyleSheet(
            f"AddDividerDialog{{background:{_BG};"
            f"border:1px solid {_BORD};}}"
        )
        self.setFixedWidth(400)

        self._build_ui()
        self._connect_signals()

    # ── UI 构建 ───────────────────────────────────────────────────────────────

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # 标题栏
        self._title_bar = _TitleBar("加分割面", self)
        root.addWidget(self._title_bar)

        # 视图选项卡（图片按钮）
        self._tab_bar = _ViewTabBar(self._icon_dir, self)
        root.addWidget(self._tab_bar)

        # 选项卡下边框线
        root.addWidget(_HLine())

        # ── 主内容区 ──
        content = QWidget()
        content.setStyleSheet(f"background:{_BG};")
        cl = QVBoxLayout(content)
        cl.setContentsMargins(14, 10, 14, 8)
        cl.setSpacing(0)

        # 单选按钮组
        radio_grp = QButtonGroup(self)
        radio_grp.setExclusive(True)
        self._radio_grp = radio_grp

        # ── 靠下行 ──
        row_bottom = QHBoxLayout()
        row_bottom.setSpacing(8)
        self._rb_near_a = QRadioButton("靠下")   # 方向变更时动态改文字
        self._rb_near_a.setStyleSheet(self._radio_ss())
        radio_grp.addButton(self._rb_near_a, 0)
        self._spin_a = self._make_spin()
        self._spin_a.setEnabled(False)
        row_bottom.addWidget(self._rb_near_a)
        row_bottom.addWidget(self._spin_a)
        row_bottom.addStretch(1)
        cl.addLayout(row_bottom)
        cl.addSpacing(6)

        # ── 靠上行 ──
        row_top = QHBoxLayout()
        row_top.setSpacing(8)
        self._rb_near_b = QRadioButton("靠上")
        self._rb_near_b.setStyleSheet(self._radio_ss())
        radio_grp.addButton(self._rb_near_b, 1)
        self._spin_b = self._make_spin()
        self._spin_b.setEnabled(False)
        row_top.addWidget(self._rb_near_b)
        row_top.addWidget(self._spin_b)
        row_top.addStretch(1)
        cl.addLayout(row_top)
        cl.addSpacing(6)

        # ── 分布行 ──
        row_dist = QHBoxLayout()
        row_dist.setSpacing(8)
        self._rb_dist = QRadioButton("分布")
        self._rb_dist.setStyleSheet(self._radio_ss())
        self._rb_dist.setChecked(True)
        radio_grp.addButton(self._rb_dist, 2)

        self._combo_dist = QComboBox()
        for i in range(1, 9):
            self._combo_dist.addItem(str(i))
        self._combo_dist.setCurrentIndex(0)
        self._combo_dist.setFixedWidth(56)
        self._combo_dist.setStyleSheet(self._combo_ss())

        self._lbl_ratio = QLabel("1:1")
        self._lbl_ratio.setStyleSheet(
            f"font-size:12px;color:{_TEXT};background:transparent;"
        )

        self._lbl_hint = QLabel("（前>后，左>右，下>上）")
        self._lbl_hint.setStyleSheet(
            "font-size:11px;color:#777777;background:transparent;"
        )

        row_dist.addWidget(self._rb_dist)
        row_dist.addWidget(self._combo_dist)
        row_dist.addWidget(self._lbl_ratio)
        row_dist.addWidget(self._lbl_hint)
        row_dist.addStretch(1)
        cl.addLayout(row_dist)
        cl.addSpacing(10)

        # 分割线
        cl.addWidget(_HLine())
        cl.addSpacing(6)

        # ── 允许跨界碰撞出孔 ──
        self._cb_cross = QCheckBox("允许跨界碰撞出孔")
        self._cb_cross.setStyleSheet(
            f"QCheckBox{{font-size:12px;color:{_TEXT};spacing:5px;}}"
            f"QCheckBox::indicator{{width:13px;height:13px;"
            f"border:1px solid {_BORD};border-radius:2px;background:#ffffff;}}"
            f"QCheckBox::indicator:checked{{background:{_BLUE};border-color:{_BLUE};}}"
        )
        cl.addWidget(self._cb_cross)

        root.addWidget(content)

        # ── 按钮行 ──
        root.addWidget(_HLine())
        btn_row = QWidget()
        btn_row.setStyleSheet(f"background:#e0e0e0;")
        bl = QHBoxLayout(btn_row)
        bl.setContentsMargins(10, 7, 10, 8)
        bl.setSpacing(8)
        bl.addStretch(1)

        self._btn_ok = QPushButton("确  定")
        self._btn_ok.setFixedSize(72, 26)
        self._btn_ok.setStyleSheet(
            f"QPushButton{{background:qlineargradient(x1:0,y1:0,x2:0,y2:1,"
            f"stop:0 {_BTN_OK_TOP},stop:1 {_BTN_OK_BTM});"
            f"color:#ffffff;border:1px solid #1a2d3e;border-radius:2px;font-size:13px;}}"
            f"QPushButton:hover{{background:qlineargradient(x1:0,y1:0,x2:0,y2:1,"
            f"stop:0 #4a6278,stop:1 #354f62);}}"
            f"QPushButton:pressed{{background:{_BTN_OK_BTM};}}"
        )
        self._btn_ok.clicked.connect(self.accept)
        bl.addWidget(self._btn_ok)

        self._btn_cancel = QPushButton("取  消")
        self._btn_cancel.setFixedSize(72, 26)
        self._btn_cancel.setStyleSheet(
            f"QPushButton{{background:qlineargradient(x1:0,y1:0,x2:0,y2:1,"
            f"stop:0 #f5f5f5,stop:1 #e0e0e0);"
            f"color:{_TEXT};border:1px solid #aaaaaa;border-radius:2px;font-size:13px;}}"
            f"QPushButton:hover{{background:#d8d8d8;}}"
            f"QPushButton:pressed{{background:#c8c8c8;}}"
        )
        self._btn_cancel.clicked.connect(self.reject)
        bl.addWidget(self._btn_cancel)

        root.addWidget(btn_row)

    # ── 信号连接 ──────────────────────────────────────────────────────────────

    def _connect_signals(self):
        # 单选按钮切换 → 启用/禁用输入框
        self._radio_grp.idToggled.connect(self._on_radio_toggled)

        # 分布数量改变 → 更新比例标签
        self._combo_dist.currentIndexChanged.connect(self._update_ratio_label)

        # 视图选项卡切换 → 更新文字提示
        for did, btn in self._tab_bar._buttons.items():
            btn.toggled.connect(lambda checked, d=did: self._on_tab_changed(d) if checked else None)

    def _on_radio_toggled(self, btn_id: int, checked: bool):
        if not checked:
            return
        self._spin_a.setEnabled(btn_id == 0)
        self._spin_b.setEnabled(btn_id == 1)
        self._combo_dist.setEnabled(btn_id == 2)

    def _on_tab_changed(self, did: str):
        _DIR_LABELS = {
            "ud": ("靠下",  "靠上",  "（前>后，左>右，下>上）"),
            "lr": ("靠左",  "靠右",  "（前>后，下>上，左>右）"),
            "fb": ("靠前",  "靠后",  "（左>右，下>上，前>后）"),
        }
        a, b, hint = _DIR_LABELS.get(did, ("靠下", "靠上", ""))
        self._rb_near_a.setText(a)
        self._rb_near_b.setText(b)
        self._lbl_hint.setText(hint)

    def _update_ratio_label(self):
        n = self._combo_dist.currentIndex() + 1   # 1~8
        self._lbl_ratio.setText(":".join(["1"] * (n + 1)))

    # ── 样式辅助 ──────────────────────────────────────────────────────────────

    @staticmethod
    def _radio_ss() -> str:
        return (
            f"QRadioButton{{font-size:12px;color:{_TEXT};spacing:5px;}}"
            f"QRadioButton::indicator{{width:13px;height:13px;}}"
        )

    @staticmethod
    def _combo_ss() -> str:
        return (
            "QComboBox{font-size:12px;border:1px solid #aaaaaa;"
            "border-radius:1px;padding:1px 4px;background:#ffffff;}"
            "QComboBox:focus{border-color:#2c3e50;}"
            "QComboBox::drop-down{border:none;width:16px;}"
        )

    @staticmethod
    def _make_spin() -> QSpinBox:
        sp = QSpinBox()
        sp.setRange(0, 99999)
        sp.setValue(0)
        sp.setFixedWidth(64)
        sp.setFixedHeight(24)
        sp.setAlignment(Qt.AlignmentFlag.AlignRight)
        sp.setStyleSheet(
            "QSpinBox{font-size:12px;border:1px solid #aaaaaa;"
            "border-radius:1px;padding:0 4px;background:#ffffff;}"
            "QSpinBox:disabled{background:#e8e8e8;color:#999999;}"
            "QSpinBox:focus{border-color:#2c3e50;}"
            "QSpinBox::up-button,QSpinBox::down-button{width:14px;}"
        )
        return sp

    # ── 拖动标题栏移动窗口 ────────────────────────────────────────────────────

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            child = self.childAt(event.position().toPoint())
            # 只在标题栏区域响应拖拽
            if self._title_bar.geometry().contains(event.position().toPoint()):
                self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
                event.accept()
            else:
                self._drag_pos = None

    def mouseMoveEvent(self, event):
        if hasattr(self, "_drag_pos") and self._drag_pos and \
                event.buttons() == Qt.MouseButton.LeftButton:
            self.move(event.globalPosition().toPoint() - self._drag_pos)
            event.accept()

    def mouseReleaseEvent(self, event):
        self._drag_pos = None

    # ── 公开结果接口 ──────────────────────────────────────────────────────────

    def get_result(self) -> dict:
        """返回用户配置字典：

        Keys
        ----
        direction : str
            方向：``'ud'``（上下）/ ``'lr'``（左右）/ ``'fb'``（前后）。
        mode : str
            定位模式：``'near_a'``（靠下/靠左/靠前）/ ``'near_b'``（靠上/靠右/靠后）/ ``'dist'``（分布）。
        value : int
            靠某侧模式下的偏移量（mm）；分布模式下为 0。
        count : int
            分布模式下的分割面数量；靠某侧模式下为 0。
        allow_cross : bool
            是否允许跨界碰撞出孔。
        """
        btn_id = self._radio_grp.checkedId()
        if btn_id == 0:
            mode = "near_a"
            value = self._spin_a.value()
            count = 0
        elif btn_id == 1:
            mode = "near_b"
            value = self._spin_b.value()
            count = 0
        else:
            mode = "dist"
            value = 0
            count = self._combo_dist.currentIndex() + 1

        return {
            "direction":   self._tab_bar.current(),
            "mode":        mode,
            "value":       value,
            "count":       count,
            "allow_cross": self._cb_cross.isChecked(),
        }


# ─── 独立预览 ─────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle("Fusion")

    icon_dir = ""
    # 尝试自动定位项目 icons 目录
    here = os.path.dirname(os.path.abspath(__file__))
    for _ in range(8):
        candidate = os.path.join(here, "icons")
        if os.path.isdir(candidate):
            icon_dir = candidate
            break
        here = os.path.dirname(here)

    dlg = AddDividerDialog(icon_dir=icon_dir)
    if dlg.exec():
        print("[加分割面] 确定：", dlg.get_result())
    else:
        print("[加分割面] 取消")

    sys.exit(0)
