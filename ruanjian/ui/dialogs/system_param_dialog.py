# -*- coding: utf-8 -*-
"""系统参数设置对话框

对应 菜单 → 设置 → 软件系统设置。
左侧分类 Tab：
    1. 界面交互  —— 完整实现
    2. 工艺相关  —— 完整实现
    3. 审图避让  —— 完整实现
    4. 图纸LOGO  —— 完整实现（2x2 图片槽位）

本对话框只做"采集 + 校验"，不直接落盘；
get_config() / set_config() 与 controller 对接，由 core 层持久化。
"""
import os

from PySide6.QtCore import Qt, Signal, QSize
from PySide6.QtGui import QDoubleValidator, QIntValidator, QPixmap, QDragEnterEvent, QDropEvent
from PySide6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QDialog,
    QFileDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMenu,
    QPushButton,
    QStackedWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)


# 主题色（侧栏深底与主窗口侧栏一致；激活/强调色与工具栏一致）
PRIMARY_COLOR = "#2c3e50"
PRIMARY_COLOR_HOVER = "#34495e"
SIDEBAR_BG = "#2c3e50"
ACCENT = "#4dc9e4"
ACCENT_HOVER = "#6fd4ec"
CHECK_BLUE = ACCENT  # 复选框、焦点、主按钮等激活色

# 对话框默认尺寸：相对早期版本整体缩小三分之一（线性尺寸 × 2/3）
_DIALOG_BASE_W = 1280
_DIALOG_BASE_H = 780
_DIALOG_SIZE_SCALE = 2 / 3


# ============================================================ 主对话框
class SystemParamDialog(QDialog):
    """系统参数设置对话框。"""

    WINDOW_TITLE = "系统参数设置"

    # 分类 Tab 定义：(代码键, 显示名)
    CATEGORIES = [
        ("ui_interaction", "界面交互"),
        ("craft_related",  "工艺相关"),
        ("review_avoid",   "审图避让"),
        ("drawing_logo",   "图纸LOGO"),
    ]

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(self.WINDOW_TITLE)
        self.setModal(True)
        self.resize(
            int(round(_DIALOG_BASE_W * _DIALOG_SIZE_SCALE)),
            int(round(_DIALOG_BASE_H * _DIALOG_SIZE_SCALE)),
        )

        # 各页实例缓存
        self.page_ui_interaction: UIInteractionPage = None
        self.page_craft_related:  CraftRelatedPage  = None
        self.page_review_avoid:   ReviewAvoidPage   = None
        self.page_drawing_logo:   DrawingLogoPage   = None

        self._build_ui()
        self._apply_style()

    # ---------------------------------------------------------------- UI
    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        body = QHBoxLayout()
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(0)

        self.side_tab = _CategoryTabBar(self.CATEGORIES, self)
        body.addWidget(self.side_tab)

        self.content_stack = QStackedWidget(self)
        self.content_stack.setObjectName("contentStack")
        self.page_ui_interaction = UIInteractionPage(self)
        self.page_craft_related  = CraftRelatedPage(self)
        self.page_review_avoid   = ReviewAvoidPage(self)
        self.page_drawing_logo   = DrawingLogoPage(self)
        self.content_stack.addWidget(self.page_ui_interaction)
        self.content_stack.addWidget(self.page_craft_related)
        self.content_stack.addWidget(self.page_review_avoid)
        self.content_stack.addWidget(self.page_drawing_logo)
        body.addWidget(self.content_stack, 1)

        root.addLayout(body, 1)

        # 底部分隔线 + 保存按钮
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet("color:#dcdfe6; background:#dcdfe6; max-height:1px;")
        root.addWidget(sep)

        bottom = QHBoxLayout()
        bottom.setContentsMargins(12, 10, 16, 12)
        bottom.addStretch(1)
        self.btn_save = QPushButton("保存设置")
        self.btn_save.setObjectName("saveButton")
        self.btn_save.setFixedSize(140, 40)
        self.btn_save.setCursor(Qt.CursorShape.PointingHandCursor)
        bottom.addWidget(self.btn_save)
        root.addLayout(bottom)

        self.side_tab.tab_changed.connect(self.content_stack.setCurrentIndex)
        self.btn_save.clicked.connect(self.accept)

    # ---------------------------------------------------------------- 样式
    def _apply_style(self):
        self.setStyleSheet(f"""
            QDialog {{
                background-color: #ffffff;
            }}
            QStackedWidget#contentStack {{
                background-color: #ffffff;
            }}
            QLabel {{
                color: #303133;
            }}
            QLineEdit, QTextEdit {{
                border: 1px solid #dcdfe6;
                border-radius: 3px;
                padding: 4px 6px;
                background: #ffffff;
                selection-background-color: {CHECK_BLUE};
            }}
            QLineEdit:focus, QTextEdit:focus {{
                border: 1px solid {CHECK_BLUE};
            }}

            /* —— 复选框：主题蓝 —— */
            QCheckBox {{
                color: #303133;
                spacing: 8px;
                padding: 4px 0;
            }}
            QCheckBox::indicator {{
                width: 18px;
                height: 18px;
                border: 1px solid #c0c4cc;
                border-radius: 2px;
                background: #ffffff;
            }}
            QCheckBox::indicator:hover {{
                border: 1px solid {CHECK_BLUE};
            }}
            QCheckBox::indicator:checked {{
                background: {CHECK_BLUE};
                border: 1px solid {CHECK_BLUE};
                image: none;
            }}

            QPushButton {{
                background-color: #f5f7fa;
                color: #303133;
                border: 1px solid #dcdfe6;
                border-radius: 3px;
                padding: 6px 10px;
            }}
            QPushButton:hover {{
                border-color: {CHECK_BLUE};
                color: {CHECK_BLUE};
            }}

            /* —— 保存按钮：强调色 —— */
            QPushButton#saveButton {{
                background-color: {PRIMARY_COLOR};
                color: #ffffff;
                border: 1px solid {PRIMARY_COLOR};
                border-radius: 3px;
                font-size: 14px;
                font-weight: bold;
            }}
            QPushButton#saveButton:hover {{
                background-color: {PRIMARY_COLOR_HOVER};
                border-color: {PRIMARY_COLOR_HOVER};
            }}
        """)

    # ---------------------------------------------------------------- 对外接口
    def get_config(self) -> dict:
        return {
            "ui_interaction": self.page_ui_interaction.get_data(),
            "craft_related":  self.page_craft_related.get_data(),
            "review_avoid":   self.page_review_avoid.get_data(),
            "drawing_logo":   self.page_drawing_logo.get_data(),
        }

    def set_config(self, cfg: dict):
        if "ui_interaction" in cfg:
            self.page_ui_interaction.set_data(cfg["ui_interaction"])
        if "craft_related" in cfg:
            self.page_craft_related.set_data(cfg["craft_related"])
        if "review_avoid" in cfg:
            self.page_review_avoid.set_data(cfg["review_avoid"])
        if "drawing_logo" in cfg:
            self.page_drawing_logo.set_data(cfg["drawing_logo"])


# ============================================================ 左侧分类 Tab
class _CategoryTabBar(QWidget):
    """对话框左侧分类切换栏。"""

    tab_changed = Signal(int)

    def __init__(self, categories, parent=None):
        super().__init__(parent)
        self.setObjectName("categoryTabBar")
        self.setFixedWidth(140)

        self._buttons = []
        self._group = QButtonGroup(self)
        self._group.setExclusive(True)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 12, 0, 12)
        layout.setSpacing(0)

        for idx, (_key, label) in enumerate(categories):
            btn = QPushButton(label)
            btn.setCheckable(True)
            btn.setFixedHeight(56)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            self._group.addButton(btn, idx)
            self._buttons.append(btn)
            layout.addWidget(btn)

        layout.addStretch(1)
        self._group.idClicked.connect(self.tab_changed.emit)

        if self._buttons:
            self._buttons[0].setChecked(True)

        self.setStyleSheet(f"""
            QWidget#categoryTabBar {{
                background-color: {SIDEBAR_BG};
            }}
            QPushButton {{
                background-color: {SIDEBAR_BG};
                color: #ffffff;
                border: none;
                font-size: 14px;
                text-align: center;
            }}
            QPushButton:hover {{
                background-color: {PRIMARY_COLOR_HOVER};
            }}
            QPushButton:checked {{
                background-color: {CHECK_BLUE};
                color: #ffffff;
                font-weight: bold;
            }}
            QPushButton:checked:hover {{
                background-color: {ACCENT_HOVER};
            }}
        """)


# ============================================================ 通用工具
def _build_field_row(parent_layout: QVBoxLayout,
                     label_text: str,
                     default: str,
                     suffix: str,
                     validator=None,
                     label_min_width: int = 280,
                     edit_width: int = 100) -> QLineEdit:
    """通用'标签 + 输入框 + 后缀'行。"""
    row = QHBoxLayout()
    row.setSpacing(8)

    lbl = QLabel(label_text)
    lbl.setMinimumWidth(label_min_width)
    lbl.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
    row.addWidget(lbl)

    edit = QLineEdit(default)
    edit.setFixedWidth(edit_width)
    edit.setAlignment(Qt.AlignmentFlag.AlignCenter)
    if validator is not None:
        edit.setValidator(validator)
    row.addWidget(edit)

    lbl_suffix = QLabel(suffix)
    lbl_suffix.setStyleSheet("color:#606266;")
    row.addWidget(lbl_suffix)

    row.addStretch(1)
    parent_layout.addLayout(row)
    return edit


def _to_int(text: str, default):
    try:
        return int(text.strip())
    except (ValueError, AttributeError):
        return default


def _to_float(text: str, default):
    try:
        return float(text.strip())
    except (ValueError, AttributeError):
        return default


# ============================================================ 界面交互 页
class UIInteractionPage(QWidget):
    """『界面交互』分页 —— 完整对照参考图实现。"""

    SWITCHES = [
        ("enable_complex_db",          "柜柜通数据库，启用复杂参数模式",          True),
        ("enable_memory_accel",        "启用内存加速（个别系统不兼容）",          True),
        ("continuous_add_on_general",  "通用板件设计时，为连续添加模式",          True),
        ("drag_add_on_flat",           "平立面设计时，启用拖画加板模式",          True),
        ("left_list_prefer_online",    "窗口左边栏列表优先启用->在线页",         False),
        ("left_list_default_tree",     "窗口左边栏列表默认启用树形目录",         False),
        ("fast_jump_to_module",        "结构设计快速跳转到选中模块目录",         True),
        ("hide_door_open_dash",        "门板开向示意虚线条，屏蔽不展示",         True),
        ("silent_add_general_board",   "启用通用板件无弹窗静默添加方式",         True),
        ("mouse_pan_left_rotate_right","鼠标交互：左键=平移   右键=旋转",        False),
        ("system_door_three_hole",     "系统门、抽屉加立板默认三方孔连接",       True),
        ("enable_custom_mod_door",     "系统门板、抽面启用自定义MOD门型",        True),
        ("common_part_resident",       "系统常用部件窗口加载后，常驻添加",       True),
        ("hide_new_cabinet_popup",     "屏蔽新建柜子按钮的列表弹窗",            False),
        ("enable_2024_new_mode",       "启用2024以后新版本的设计交互模式",       True),
    ]

    def __init__(self, parent=None):
        super().__init__(parent)
        self._switch_checkboxes: dict[str, QCheckBox] = {}
        self._build_ui()

    def _build_ui(self):
        root = QHBoxLayout(self)
        root.setContentsMargins(20, 18, 20, 18)
        root.setSpacing(30)

        root.addLayout(self._build_left_switches(), 0)
        root.addLayout(self._build_right_properties(), 1)

    def _build_left_switches(self) -> QVBoxLayout:
        col = QVBoxLayout()
        col.setSpacing(2)
        col.setContentsMargins(0, 0, 0, 0)
        for key, text, default in self.SWITCHES:
            chk = QCheckBox(text)
            chk.setChecked(default)
            self._switch_checkboxes[key] = chk
            col.addWidget(chk)
        col.addStretch(1)
        return col

    def _build_right_properties(self) -> QVBoxLayout:
        col = QVBoxLayout()
        col.setContentsMargins(0, 0, 0, 0)
        col.setSpacing(14)

        row_depth = QHBoxLayout()
        row_depth.addWidget(QLabel("设计选择空间时，忽略最小深度 ="))
        self.edit_ignore_min_depth = QLineEdit()
        self.edit_ignore_min_depth.setFixedWidth(180)
        self.edit_ignore_min_depth.setValidator(QIntValidator(0, 999999, self))
        row_depth.addWidget(self.edit_ignore_min_depth)
        row_depth.addWidget(QLabel("mm  大于设定目标值有效返回"))
        row_depth.addStretch(1)
        col.addLayout(row_depth)

        row_bg = QHBoxLayout()
        row_bg.addWidget(QLabel("自定义窗口设计画板背景色 ="))
        self.edit_canvas_bg_color = QLineEdit("#E8E8E8")
        self.edit_canvas_bg_color.setFixedWidth(180)
        row_bg.addWidget(self.edit_canvas_bg_color)
        row_bg.addWidget(QLabel("十六进制颜色编码，如#E8E8E8"))
        row_bg.addStretch(1)
        col.addLayout(row_bg)

        col.addWidget(QLabel("自定义组件属性(如:属性1|属性2|..)↓↓"))
        self.edit_custom_component_props = QTextEdit()
        self.edit_custom_component_props.setFixedHeight(140)
        col.addWidget(self.edit_custom_component_props)

        col.addWidget(QLabel("标记文字的属性(如:属性1|属性2|..)↓↓"))
        self.edit_mark_text_props = QTextEdit()
        self.edit_mark_text_props.setFixedHeight(140)
        col.addWidget(self.edit_mark_text_props)

        row_size = QHBoxLayout()
        row_size.addWidget(QLabel("标记文字字体尺寸 ="))
        self.edit_mark_font_size = QLineEdit()
        self.edit_mark_font_size.setFixedWidth(180)
        self.edit_mark_font_size.setValidator(QIntValidator(1, 999, self))
        row_size.addWidget(self.edit_mark_font_size)
        row_size.addWidget(QLabel("无设置，软件默认30"))
        row_size.addStretch(1)
        col.addLayout(row_size)

        row_color = QHBoxLayout()
        row_color.addWidget(QLabel("标记文字字体颜色 ="))
        self.edit_mark_font_color = QLineEdit()
        self.edit_mark_font_color.setFixedWidth(180)
        row_color.addWidget(self.edit_mark_font_color)
        row_color.addWidget(QLabel("十六进制颜色编码，如#E8E8E8"))
        row_color.addStretch(1)
        col.addLayout(row_color)

        col.addStretch(1)

        row_dpi = QHBoxLayout()
        row_dpi.addStretch(1)
        self.btn_enable_dpi = QPushButton("设置DPI系统增强\n界面错位用，重新运行起效")
        self.btn_enable_dpi.setMinimumSize(180, 56)
        self.btn_cancel_dpi = QPushButton("取消设置DPI\n系统增强")
        self.btn_cancel_dpi.setMinimumSize(140, 56)
        row_dpi.addWidget(self.btn_enable_dpi)
        row_dpi.addWidget(self.btn_cancel_dpi)
        col.addLayout(row_dpi)

        return col

    def get_data(self) -> dict:
        switches = {key: chk.isChecked() for key, chk in self._switch_checkboxes.items()}
        return {
            "switches": switches,
            "ignore_min_depth_mm":      _to_int(self.edit_ignore_min_depth.text(), None),
            "canvas_bg_color":          self.edit_canvas_bg_color.text().strip(),
            "custom_component_props":   self.edit_custom_component_props.toPlainText().strip(),
            "mark_text_props":          self.edit_mark_text_props.toPlainText().strip(),
            "mark_font_size":           _to_int(self.edit_mark_font_size.text(), None),
            "mark_font_color":          self.edit_mark_font_color.text().strip(),
        }

    def set_data(self, data: dict):
        switches = data.get("switches", {})
        for key, chk in self._switch_checkboxes.items():
            if key in switches:
                chk.setChecked(bool(switches[key]))
        if data.get("ignore_min_depth_mm") is not None:
            self.edit_ignore_min_depth.setText(str(data["ignore_min_depth_mm"]))
        if "canvas_bg_color" in data:
            self.edit_canvas_bg_color.setText(data["canvas_bg_color"] or "")
        if "custom_component_props" in data:
            self.edit_custom_component_props.setPlainText(data["custom_component_props"] or "")
        if "mark_text_props" in data:
            self.edit_mark_text_props.setPlainText(data["mark_text_props"] or "")
        if data.get("mark_font_size") is not None:
            self.edit_mark_font_size.setText(str(data["mark_font_size"]))
        if "mark_font_color" in data:
            self.edit_mark_font_color.setText(data["mark_font_color"] or "")


# ============================================================ 工艺相关 页
class CraftRelatedPage(QWidget):
    """『工艺相关』分页 —— 6 数值 + 2 开关。"""

    SWITCHES = [
        ("force_open_thin_board_hole", "强制开启厚度小于12mm，接受孔位", True),
        ("hinge_pos_by_top_distance",  "门铰链定位描述，按距上计算定位", True),
    ]

    def __init__(self, parent=None):
        super().__init__(parent)
        self._switch_checkboxes: dict[str, QCheckBox] = {}
        self._build_ui()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(60, 30, 60, 30)
        root.setSpacing(14)

        int_validator = lambda: QIntValidator(0, 999999, self)
        def float_validator():
            v = QDoubleValidator(0.0, 999999.0, 3, self)
            v.setNotation(QDoubleValidator.Notation.StandardNotation)
            return v

        self.edit_force_rotate_overwidth = _build_field_row(
            root, "强制旋转超宽板件纹理，超宽 =", "1200",
            "mm  应用于所有板件，默认1210mm", int_validator(),
            label_min_width=260, edit_width=120,
        )
        self.edit_back_slot_depth_margin = _build_field_row(
            root, "背板入槽时，开槽深度余量 =", "0.7",
            "mm  只对孔位模板=入槽 有效", float_validator(),
            label_min_width=260, edit_width=120,
        )
        self.edit_back_slot_width_margin = _build_field_row(
            root, "背板入槽时，开槽宽度余量 =", "1",
            "mm  只对孔位模板=入槽 有效", float_validator(),
            label_min_width=260, edit_width=120,
        )
        self.edit_hole_min_gap_error = _build_field_row(
            root, "孔位碰撞计算时，最小间隙误差 =", "",
            "mm  侧孔有效,必须>0.1，默认4mm", float_validator(),
            label_min_width=260, edit_width=120,
        )
        self.edit_cancel_edge_min_size = _build_field_row(
            root, "板件尺寸小于目标值就取消封边 =", "",
            "mm  某边小于设定值封边=0", int_validator(),
            label_min_width=260, edit_width=120,
        )
        self.edit_straightener_min_height = _build_field_row(
            root, "门板需配拉直器时，最小高度尺寸 =", "1200",
            "无默认值按>=1200mm才配拉直器", int_validator(),
            label_min_width=260, edit_width=120,
        )

        root.addSpacing(6)

        for key, text, default in self.SWITCHES:
            chk = QCheckBox(text)
            chk.setChecked(default)
            self._switch_checkboxes[key] = chk
            row = QHBoxLayout()
            row.addSpacing(40)
            row.addWidget(chk)
            row.addStretch(1)
            root.addLayout(row)

        root.addStretch(1)

    def get_data(self) -> dict:
        return {
            "force_rotate_overwidth_mm":  _to_int(self.edit_force_rotate_overwidth.text(), None),
            "back_slot_depth_margin_mm":  _to_float(self.edit_back_slot_depth_margin.text(), None),
            "back_slot_width_margin_mm":  _to_float(self.edit_back_slot_width_margin.text(), None),
            "hole_min_gap_error_mm":      _to_float(self.edit_hole_min_gap_error.text(), None),
            "cancel_edge_min_size_mm":    _to_int(self.edit_cancel_edge_min_size.text(), None),
            "straightener_min_height_mm": _to_int(self.edit_straightener_min_height.text(), None),
            "switches": {k: c.isChecked() for k, c in self._switch_checkboxes.items()},
        }

    def set_data(self, data: dict):
        mapping = [
            ("force_rotate_overwidth_mm",  self.edit_force_rotate_overwidth),
            ("back_slot_depth_margin_mm",  self.edit_back_slot_depth_margin),
            ("back_slot_width_margin_mm",  self.edit_back_slot_width_margin),
            ("hole_min_gap_error_mm",      self.edit_hole_min_gap_error),
            ("cancel_edge_min_size_mm",    self.edit_cancel_edge_min_size),
            ("straightener_min_height_mm", self.edit_straightener_min_height),
        ]
        for key, edit in mapping:
            if key in data and data[key] is not None:
                edit.setText(str(data[key]))
        switches = data.get("switches", {})
        for key, chk in self._switch_checkboxes.items():
            if key in switches:
                chk.setChecked(bool(switches[key]))


# ============================================================ 审图避让 页
class ReviewAvoidPage(QWidget):
    """『审图避让』分页 —— 4 开关 + 3 + 7 数值。"""

    SWITCHES = [
        ("auto_orthographic_camera",   "审图模式下自动启用正投相机",  True),
        ("auto_avoid_door_hinge",      "开启自动避让_门板铰链",       True),
        ("auto_avoid_cabinet_slot",    "开启自动避让_柜体孔槽",       True),
        ("block_avoid_through_hole",   "屏蔽自动避让_对穿孔位",       True),
    ]

    def __init__(self, parent=None):
        super().__init__(parent)
        self._switch_checkboxes: dict[str, QCheckBox] = {}
        self._build_ui()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(40, 24, 40, 24)
        root.setSpacing(10)

        for key, text, default in self.SWITCHES:
            chk = QCheckBox(text)
            chk.setChecked(default)
            self._switch_checkboxes[key] = chk
            row = QHBoxLayout()
            row.addSpacing(200)
            row.addWidget(chk)
            row.addStretch(1)
            root.addLayout(row)

        root.addSpacing(6)

        int_validator = lambda: QIntValidator(0, 999999, self)
        def float_validator():
            v = QDoubleValidator(0.0, 999999.0, 3, self)
            v.setNotation(QDoubleValidator.Notation.StandardNotation)
            return v

        self.edit_cabinet_hole_avoid_offset = _build_field_row(
            root, "不合理柜体孔位避让自动偏移 =", "30",
            "mm  只对外碰孔位有效，默认16mm", int_validator(),
            label_min_width=280, edit_width=100,
        )
        self.edit_hinge_hole_avoid_offset = _build_field_row(
            root, "不合理铰链孔位避让自动偏移 =", "32",
            "mm  只对门板门铰有效，默认32mm", int_validator(),
            label_min_width=280, edit_width=100,
        )
        self.edit_through_hole_center_tolerance = _build_field_row(
            root, "对穿孔判断孔位圆心重合误差 =", "",
            "mm  只对正反对称孔有效，默认0.5mm", float_validator(),
            label_min_width=280, edit_width=100,
        )

        root.addSpacing(4)
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet("border: none; border-top: 1px dashed #c0c4cc;")
        sep.setFixedHeight(2)
        root.addWidget(sep)
        root.addSpacing(4)

        self.edit_review_material_opacity = _build_field_row(
            root, "审图模式下材质透明时的透明度 =", "0.2",
            "有效数值必须在0.1~0.9之间", float_validator(),
            label_min_width=280, edit_width=100,
        )
        self.edit_min_board_thickness_for_edge = _build_field_row(
            root, "审图自动检验封边，检测最小板厚 =", "5",
            "不填或无默认值按>9mm检测", int_validator(),
            label_min_width=280, edit_width=100,
        )
        self.edit_hinge_collide_depth = _build_field_row(
            root, "审图自动检验，铰链碰撞检测深度 =", "80",
            "不填或无默认值按80mm检测", int_validator(),
            label_min_width=280, edit_width=100,
        )
        self.edit_hinge_collide_height = _build_field_row(
            root, "审图自动检验，铰链碰撞检测高度 =", "70",
            "不填或无默认值按70mm检测", int_validator(),
            label_min_width=280, edit_width=100,
        )
        self.edit_board_overwidth_threshold = _build_field_row(
            root, "审图自动检验，检测板件超宽尺寸 >", "1210",
            "不填或无默认值按1210mm检测", int_validator(),
            label_min_width=280, edit_width=100,
        )
        self.edit_board_overlength_threshold = _build_field_row(
            root, "审图自动检验，检测板件超长尺寸 >", "2420",
            "不填或无默认值按2420mm检测", int_validator(),
            label_min_width=280, edit_width=100,
        )
        self.edit_door_hinge_diameter_threshold = _build_field_row(
            root, "审图自动检验，检测识别门铰孔径 >", "",
            "必须>30mm,默认按30mm检测", int_validator(),
            label_min_width=280, edit_width=100,
        )

        root.addStretch(1)

    def get_data(self) -> dict:
        return {
            "switches": {k: c.isChecked() for k, c in self._switch_checkboxes.items()},
            "cabinet_hole_avoid_offset_mm":     _to_int(self.edit_cabinet_hole_avoid_offset.text(), None),
            "hinge_hole_avoid_offset_mm":       _to_int(self.edit_hinge_hole_avoid_offset.text(), None),
            "through_hole_center_tolerance_mm": _to_float(self.edit_through_hole_center_tolerance.text(), None),
            "review_material_opacity":          _to_float(self.edit_review_material_opacity.text(), None),
            "min_board_thickness_for_edge_mm":  _to_int(self.edit_min_board_thickness_for_edge.text(), None),
            "hinge_collide_depth_mm":           _to_int(self.edit_hinge_collide_depth.text(), None),
            "hinge_collide_height_mm":          _to_int(self.edit_hinge_collide_height.text(), None),
            "board_overwidth_threshold_mm":     _to_int(self.edit_board_overwidth_threshold.text(), None),
            "board_overlength_threshold_mm":    _to_int(self.edit_board_overlength_threshold.text(), None),
            "door_hinge_diameter_threshold_mm": _to_int(self.edit_door_hinge_diameter_threshold.text(), None),
        }

    def set_data(self, data: dict):
        switches = data.get("switches", {})
        for key, chk in self._switch_checkboxes.items():
            if key in switches:
                chk.setChecked(bool(switches[key]))
        mapping = [
            ("cabinet_hole_avoid_offset_mm",     self.edit_cabinet_hole_avoid_offset),
            ("hinge_hole_avoid_offset_mm",       self.edit_hinge_hole_avoid_offset),
            ("through_hole_center_tolerance_mm", self.edit_through_hole_center_tolerance),
            ("review_material_opacity",          self.edit_review_material_opacity),
            ("min_board_thickness_for_edge_mm",  self.edit_min_board_thickness_for_edge),
            ("hinge_collide_depth_mm",           self.edit_hinge_collide_depth),
            ("hinge_collide_height_mm",          self.edit_hinge_collide_height),
            ("board_overwidth_threshold_mm",     self.edit_board_overwidth_threshold),
            ("board_overlength_threshold_mm",    self.edit_board_overlength_threshold),
            ("door_hinge_diameter_threshold_mm", self.edit_door_hinge_diameter_threshold),
        ]
        for key, edit in mapping:
            if key in data and data[key] is not None:
                edit.setText(str(data[key]))


# ============================================================ 图纸LOGO 页
class DrawingLogoPage(QWidget):
    """『图纸LOGO』分页 —— 2x2 图片上传槽位。

    四个槽位（key, 标题, 推荐尺寸说明）：
        - pdf_logo  PDF产品图-LOGO   200*200
        - pdf_cover PDF产品图-封面    自适应
        - pdf_footer PDF产品图-底页   自适应
        - render_watermark 效果图-水印 200*80
    """

    SLOTS = [
        ("pdf_logo",        "PDF产品图-LOGO",   "200*200", 0, 0),
        ("pdf_cover",       "PDF产品图-封面",   None,      0, 1),
        ("pdf_footer",      "PDF产品图-底页",   None,      1, 0),
        ("render_watermark","效果图-水印",      "200*80",  1, 1),
    ]

    def __init__(self, parent=None):
        super().__init__(parent)
        self._slot_widgets: dict[str, "ImageSlotWidget"] = {}
        self._build_ui()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(40, 24, 40, 24)
        root.setSpacing(0)

        grid = QGridLayout()
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setHorizontalSpacing(28)
        grid.setVerticalSpacing(20)

        for key, title, size_hint, row, col in self.SLOTS:
            if key.startswith("pdf_"):
                slot = ImageSlotWidget(
                    title,
                    size_hint,
                    parent=self,
                    header_bg=PRIMARY_COLOR,
                    preview_bg=PRIMARY_COLOR,
                    preview_border=PRIMARY_COLOR,
                    preview_placeholder="#d4d8de",
                    preview_hover_border=PRIMARY_COLOR_HOVER,
                    preview_hover_text="#ecf0f1",
                )
            else:
                slot = ImageSlotWidget(title, size_hint, parent=self)
            self._slot_widgets[key] = slot
            grid.addWidget(slot, row, col)

        # 列宽均分
        grid.setColumnStretch(0, 1)
        grid.setColumnStretch(1, 1)
        grid.setRowStretch(0, 1)
        grid.setRowStretch(1, 1)

        root.addLayout(grid, 1)

    # ---------------- 数据接口 ----------------
    def get_data(self) -> dict:
        """返回各槽位选定的本地图片路径。"""
        return {key: w.image_path for key, w in self._slot_widgets.items()}

    def set_data(self, data: dict):
        """根据已有路径回填图片预览。"""
        for key, widget in self._slot_widgets.items():
            if key in data and data[key]:
                widget.set_image(data[key])
            else:
                widget.clear_image()


# ============================================================ 图片槽位控件
class ImageSlotWidget(QWidget):
    """单个图片上传槽位。

    结构：
        ┌────────────────────────────┐
        │   标题（灰色横条）          │
        │   推荐尺寸（可选）          │
        ├────────────────────────────┤
        │                            │
        │     图片预览区域             │
        │  （点击/拖入可上传 / 替换）  │
        │                            │
        └────────────────────────────┘
    支持：左键点击选择文件 / 拖放图片 / 右键菜单替换或清空。
    """

    image_changed = Signal(str)  # 选定新图片时发出，参数为绝对路径

    def __init__(
        self,
        title: str,
        size_hint: str = None,
        parent=None,
        *,
        header_bg: str | None = None,
        preview_bg: str | None = None,
        preview_border: str | None = None,
        preview_placeholder: str | None = None,
        preview_hover_border: str | None = None,
        preview_hover_text: str | None = None,
    ):
        super().__init__(parent)
        self._image_path: str = ""
        self._header_bg = header_bg if header_bg is not None else CHECK_BLUE
        self._preview_bg = preview_bg if preview_bg is not None else "#ffffff"
        self._preview_border = preview_border if preview_border is not None else CHECK_BLUE
        self._preview_placeholder = preview_placeholder if preview_placeholder is not None else "#c0c4cc"
        self._preview_hover_border = (
            preview_hover_border if preview_hover_border is not None else ACCENT_HOVER
        )
        self._preview_hover_text = preview_hover_text if preview_hover_text is not None else CHECK_BLUE
        self._build_ui(title, size_hint)
        self.setAcceptDrops(True)

    # ---------------- UI ----------------
    def _build_ui(self, title: str, size_hint: str):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # 标题栏（灰色横条）
        self.header = QWidget()
        self.header.setObjectName("slotHeader")
        self.header.setFixedHeight(46 if size_hint else 32)
        header_layout = QVBoxLayout(self.header)
        header_layout.setContentsMargins(8, 4, 8, 4)
        header_layout.setSpacing(2)

        lbl_title = QLabel(title)
        lbl_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl_title.setStyleSheet("color:#ffffff; font-size:13px; font-weight:bold;")
        header_layout.addWidget(lbl_title)

        if size_hint:
            lbl_size = QLabel(size_hint)
            lbl_size.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lbl_size.setStyleSheet("color:#d4d8de; font-size:12px;")
            header_layout.addWidget(lbl_size)

        layout.addWidget(self.header)

        # 预览区
        self.preview = _ImagePreviewLabel(
            self,
            bg=self._preview_bg,
            border=self._preview_border,
            hover_border=self._preview_hover_border,
            hover_text=self._preview_hover_text,
            placeholder=self._preview_placeholder,
        )
        self.preview.setMinimumHeight(220)
        self.preview.clicked.connect(self._pick_image)
        layout.addWidget(self.preview, 1)

        hb = self._header_bg
        self.setStyleSheet(f"""
            QWidget#slotHeader {{
                background: {hb};
                border: 1px solid {hb};
            }}
        """)

    # ---------------- 文件选择 ----------------
    def _pick_image(self):
        path, _ = QFileDialog.getOpenFileName(
            self,
            "选择图片",
            self._image_path or "",
            "图片文件 (*.png *.jpg *.jpeg *.bmp *.gif *.webp);;所有文件 (*.*)",
        )
        if path:
            self.set_image(path)

    # ---------------- 对外接口 ----------------
    @property
    def image_path(self) -> str:
        return self._image_path

    def set_image(self, path: str):
        """设置并预览图片。"""
        if not path or not os.path.isfile(path):
            self.clear_image()
            return
        pix = QPixmap(path)
        if pix.isNull():
            self.clear_image()
            return
        self._image_path = path
        self.preview.set_pixmap(pix)
        self.image_changed.emit(path)

    def clear_image(self):
        self._image_path = ""
        self.preview.clear_pixmap()

    # ---------------- 拖放 ----------------
    def dragEnterEvent(self, e: QDragEnterEvent):
        if e.mimeData().hasUrls():
            for url in e.mimeData().urls():
                if url.toLocalFile().lower().endswith(IMAGE_EXTENSIONS):
                    e.acceptProposedAction()
                    return
        e.ignore()

    def dropEvent(self, e: QDropEvent):
        for url in e.mimeData().urls():
            path = url.toLocalFile()
            if path.lower().endswith(IMAGE_EXTENSIONS):
                self.set_image(path)
                e.acceptProposedAction()
                return

    # ---------------- 右键菜单 ----------------
    def contextMenuEvent(self, e):
        menu = QMenu(self)
        act_choose  = menu.addAction("选择图片...")
        act_clear   = menu.addAction("清空")
        act_clear.setEnabled(bool(self._image_path))

        chosen = menu.exec(e.globalPos())
        if chosen is act_choose:
            self._pick_image()
        elif chosen is act_clear:
            self.clear_image()


class _ImagePreviewLabel(QLabel):
    """图片预览 Label：保持宽高比缩放显示，无图时显示提示文字。"""

    clicked = Signal()
    PLACEHOLDER_TEXT = "点击或拖入图片"

    def __init__(
        self,
        parent=None,
        *,
        bg: str = "#ffffff",
        border: str | None = None,
        hover_border: str | None = None,
        hover_text: str | None = None,
        placeholder: str = "#c0c4cc",
    ):
        super().__init__(parent)
        self._pixmap: QPixmap = None
        bd = border if border is not None else CHECK_BLUE
        hb = hover_border if hover_border is not None else ACCENT_HOVER
        ht = hover_text if hover_text is not None else CHECK_BLUE
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setStyleSheet(f"""
            QLabel {{
                background: {bg};
                border: 1px solid {bd};
                border-top: none;
                color: {placeholder};
                font-size: 13px;
            }}
            QLabel:hover {{
                border-color: {hb};
                color: {ht};
            }}
        """)
        self.setText(self.PLACEHOLDER_TEXT)

    def set_pixmap(self, pix: QPixmap):
        self._pixmap = pix
        self._render_scaled()

    def clear_pixmap(self):
        self._pixmap = None
        self.clear()
        self.setText(self.PLACEHOLDER_TEXT)

    def resizeEvent(self, e):
        super().resizeEvent(e)
        if self._pixmap is not None:
            self._render_scaled()

    def _render_scaled(self):
        if self._pixmap is None:
            return
        target = QSize(self.width() - 16, self.height() - 16)
        if target.width() <= 0 or target.height() <= 0:
            return
        scaled = self._pixmap.scaled(
            target,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        self.setPixmap(scaled)

    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(e)
