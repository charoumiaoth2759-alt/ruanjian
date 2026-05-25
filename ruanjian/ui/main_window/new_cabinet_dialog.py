# -*- coding: utf-8 -*-
"""新建柜子对话框

NewCabinetDialog —— 点击"新建柜子"时弹出，用于输入：
    - 产品名称（下拉预设 + 自定义输入）
    - 总尺寸 W / H / D（mm）

预设名称列表：
    空框架、主卧衣柜、次卧衣柜、榻榻米、酒柜、鞋柜、
    电视柜、橱柜、吊柜、其他

返回数据（confirmed 后可读）：
    dialog.product_name  -> str
    dialog.width         -> int  (mm)
    dialog.height        -> int  (mm)
    dialog.depth         -> int  (mm)

用法：
    from ui.main_window.new_cabinet_dialog import NewCabinetDialog

    dlg = NewCabinetDialog(parent=self)
    if dlg.exec() == NewCabinetDialog.DialogCode.Accepted:
        name  = dlg.product_name
        w, h, d = dlg.width, dlg.height, dlg.depth
"""

from PySide6.QtCore import Qt
from PySide6.QtGui  import QFont, QIntValidator
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout,
    QLabel, QLineEdit, QComboBox, QPushButton,
    QFrame, QSizePolicy,
)


# ── 预设产品名称 ──────────────────────────────────────────────────
_PRESET_NAMES = [
    "空框架",
    "主卧衣柜",
    "次卧衣柜",
    "榻榻米",
    "酒柜",
    "鞋柜",
    "电视柜",
    "橱柜",
    "吊柜",
    "其他",
]

# ── 默认尺寸 (mm) ──────────────────────────────────────────────────
_DEFAULT_W = 2400
_DEFAULT_H = 2200
_DEFAULT_D = 600


class NewCabinetDialog(QDialog):
    """新建柜子 —— 产品名称 / 总尺寸输入对话框。

    色调与主窗口一致：
        标题条  #2c3e50（蓝）
        背景    #ffffff
        输入框  #ffffff  边框 #d0d5dd
        确定按钮 #2c3e50  取消按钮 #f4f6f8
    """

    # ── 样式常量 ──────────────────────────────────────────────────
    _TITLE_STYLE = """
        QLabel {
            background: #2c3e50;
            color: #ffffff;
            font-size: 13px;
            font-weight: bold;
            padding: 8px 14px;
        }
    """
    _SECTION_LABEL_STYLE = """
        QLabel {
            color: #303133;
            font-size: 13px;
            font-weight: bold;
        }
    """
    _FIELD_LABEL_STYLE = """
        QLabel {
            color: #606266;
            font-size: 13px;
        }
    """
    _COMBO_STYLE = """
        QComboBox {
            background: #ffffff;
            border: 1px solid #d0d5dd;
            border-radius: 4px;
            color: #303133;
            font-size: 13px;
            padding: 0 8px;
            height: 30px;
            min-width: 180px;
        }
        QComboBox:hover  { border-color: #4a6580; }
        QComboBox:focus  { border-color: #4a6580; }
        QComboBox::drop-down {
            border: none;
            width: 24px;
        }
        QComboBox::down-arrow {
            width: 10px; height: 10px;
        }
        QComboBox QAbstractItemView {
            background: #ffffff;
            border: 1px solid #d0d5dd;
            selection-background-color: #d8e4f0;
            selection-color: #2c3e50;
            font-size: 13px;
            outline: none;
        }
    """
    _INPUT_STYLE = """
        QLineEdit {
            background: #ffffff;
            border: 1px solid #d0d5dd;
            border-radius: 4px;
            color: #303133;
            font-size: 13px;
            padding: 0 8px;
            height: 30px;
        }
        QLineEdit:hover  { border-color: #4a6580; }
        QLineEdit:focus  { border-color: #4a6580; }
    """
    _BTN_OK = """
        QPushButton {
            background: #2c3e50;
            border: none;
            border-radius: 4px;
            color: #ffffff;
            font-size: 13px;
            font-weight: bold;
            padding: 0 24px;
            height: 32px;
            min-width: 72px;
        }
        QPushButton:hover   { background: #1a2b3c; }
        QPushButton:pressed { background: #0f1e2d; }
    """
    _BTN_CANCEL = """
        QPushButton {
            background: #f4f6f8;
            border: 1px solid #d0d5dd;
            border-radius: 4px;
            color: #606266;
            font-size: 13px;
            padding: 0 24px;
            height: 32px;
            min-width: 72px;
        }
        QPushButton:hover   { background: #e8f0fe; border-color: #4a6580; color: #303133; }
        QPushButton:pressed { background: #d6e8ff; }
    """
    _SEPARATOR_STYLE = "background: #e4e7ed;"
    _DIM_UNIT_STYLE  = "color: #909399; font-size: 12px;"

    def __init__(self, parent=None,
                 default_name: str = "空框架",
                 default_w: int = _DEFAULT_W,
                 default_h: int = _DEFAULT_H,
                 default_d: int = _DEFAULT_D):
        super().__init__(parent)
        self.setWindowTitle("新建柜子")
        self.setWindowFlags(
            Qt.WindowType.Dialog |
            Qt.WindowType.FramelessWindowHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setStyleSheet("QDialog { background: #ffffff; border: 1px solid #d0d5dd; border-radius: 6px; }")
        self.setFixedWidth(420)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Minimum)

        # ── 返回值 ────────────────────────────────────────────────
        self.product_name:   str = default_name
        self.cabinet_width:  int = default_w
        self.cabinet_height: int = default_h
        self.cabinet_depth:  int = default_d

        self._build_ui(default_name, default_w, default_h, default_d)

        # 支持拖动（无边框时）
        self._drag_pos = None

    # ──────────────────────────────────────────── UI 构建
    def _build_ui(self, def_name, def_w, def_h, def_d):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ── 标题条 ────────────────────────────────────────────────
        title_lbl = QLabel("产品名称/总尺寸：")
        title_lbl.setStyleSheet(self._TITLE_STYLE)
        title_lbl.setFixedHeight(36)
        root.addWidget(title_lbl)

        # ── 内容区 ────────────────────────────────────────────────
        content = QFrame()
        content.setStyleSheet("QFrame { background: #ffffff; }")
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(24, 20, 24, 16)
        content_layout.setSpacing(16)

        # ── 产品名称行 ────────────────────────────────────────────
        name_row = QHBoxLayout()
        name_row.setSpacing(10)

        name_lbl = QLabel("产品名称")
        name_lbl.setStyleSheet(self._FIELD_LABEL_STYLE)
        name_lbl.setFixedWidth(60)
        name_row.addWidget(name_lbl)

        self._name_combo = QComboBox()
        self._name_combo.setEditable(True)
        self._name_combo.setStyleSheet(self._COMBO_STYLE)
        self._name_combo.addItems(_PRESET_NAMES)
        # 定位到默认名
        idx = self._name_combo.findText(def_name)
        if idx >= 0:
            self._name_combo.setCurrentIndex(idx)
        else:
            self._name_combo.setCurrentText(def_name)
        name_row.addWidget(self._name_combo, 1)

        content_layout.addLayout(name_row)

        # ── 分隔线 ────────────────────────────────────────────────
        sep1 = QFrame()
        sep1.setFrameShape(QFrame.Shape.HLine)
        sep1.setFixedHeight(1)
        sep1.setStyleSheet(self._SEPARATOR_STYLE)
        content_layout.addWidget(sep1)

        # ── 总尺寸行 ──────────────────────────────────────────────
        dim_row = QHBoxLayout()
        dim_row.setSpacing(8)

        dim_lbl = QLabel("总尺寸")
        dim_lbl.setStyleSheet(self._FIELD_LABEL_STYLE)
        dim_lbl.setFixedWidth(60)
        dim_row.addWidget(dim_lbl)

        int_validator = QIntValidator(1, 99999, self)

        for attr, prefix, default in (
            ("_input_w", "W", def_w),
            ("_input_h", "H", def_h),
            ("_input_d", "D", def_d),
        ):
            lbl = QLabel(prefix)
            lbl.setStyleSheet("color: #606266; font-size: 12px; font-weight: bold;")
            lbl.setFixedWidth(14)
            dim_row.addWidget(lbl)

            inp = QLineEdit(str(default))
            inp.setValidator(int_validator)
            inp.setStyleSheet(self._INPUT_STYLE)
            inp.setFixedWidth(72)
            inp.setAlignment(Qt.AlignmentFlag.AlignCenter)
            setattr(self, attr, inp)
            dim_row.addWidget(inp)

        dim_row.addStretch(1)
        content_layout.addLayout(dim_row)

        # ── 分隔线 ────────────────────────────────────────────────
        sep2 = QFrame()
        sep2.setFrameShape(QFrame.Shape.HLine)
        sep2.setFixedHeight(1)
        sep2.setStyleSheet(self._SEPARATOR_STYLE)
        content_layout.addWidget(sep2)

        # ── 按钮行 ────────────────────────────────────────────────
        btn_row = QHBoxLayout()
        btn_row.setSpacing(12)
        btn_row.addStretch(1)

        btn_ok = QPushButton("确  定")
        btn_ok.setStyleSheet(self._BTN_OK)
        btn_ok.setDefault(True)
        btn_ok.clicked.connect(self._on_accept)
        btn_row.addWidget(btn_ok)

        btn_cancel = QPushButton("取  消")
        btn_cancel.setStyleSheet(self._BTN_CANCEL)
        btn_cancel.clicked.connect(self.reject)
        btn_row.addWidget(btn_cancel)

        content_layout.addLayout(btn_row)

        root.addWidget(content)

    # ──────────────────────────────────────────── 槽
    def _on_accept(self):
        """读取输入值，校验非空后接受对话框。"""
        name = self._name_combo.currentText().strip()
        if not name:
            name = "空框架"

        try:
            w = int(self._input_w.text())
        except ValueError:
            w = _DEFAULT_W
        try:
            h = int(self._input_h.text())
        except ValueError:
            h = _DEFAULT_H
        try:
            d = int(self._input_d.text())
        except ValueError:
            d = _DEFAULT_D

        # 最小值保护
        w = max(w, 1)
        h = max(h, 1)
        d = max(d, 1)

        self.product_name   = name
        self.cabinet_width  = w
        self.cabinet_height = h
        self.cabinet_depth  = d

        self.accept()

    # ──────────────────────────────────────────── 无边框拖动支持
    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._drag_pos is not None and event.buttons() == Qt.MouseButton.LeftButton:
            self.move(event.globalPosition().toPoint() - self._drag_pos)
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        self._drag_pos = None
        super().mouseReleaseEvent(event)