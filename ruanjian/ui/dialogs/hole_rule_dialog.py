# -*- coding: utf-8 -*-
"""孔位规则 / 五金设置对话框

对应 菜单 → 设置 → 系统工艺设置 → 孔位规则/五金设置。
布局（按参考图，当前显示"孔位五金"页）：
    ┌─────────────────────────────────────────────────────────────┐
    │ [孔位规则 | 孔位五金]    系统固有：二合一、三合一、四合一... │
    ├──────────────┬──────────────────────────────────────────────┤
    │ 五金类型列表  │                                              │
    │  层板钉       │           参考图片                            │
    │  二合一 *选中*│         （icons/erheyi.png）                  │
    │  三合一       │                                              │
    │  四合一       │         A1=大饼孔径                           │
    │  圆木梢       │         A2=大饼孔深                           │
    ├──────────────┤         A3=...                              │
    │ 属性表        │                                              │
    │  孔径   8     │                                              │
    │  孔深   10    │                                              │
    │  外部孔径 10  │                                              │
    │  ...          │                                              │
    │ [保存应用属性↑]│                                             │
    └──────────────┴──────────────────────────────────────────────┘

本对话框只负责"采集 + 显示"，五金参数的持久化由 controller / core 层处理。
"""
import os

from PySide6.QtCore import Qt, Signal, QSize
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QAbstractItemView,
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QDialog,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QInputDialog,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QRadioButton,
    QSizePolicy,
    QStackedWidget,
    QTabBar,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)


# 主题色（与主窗口、其它对话框保持一致）
PRIMARY_COLOR = "#2c3e50"
PRIMARY_COLOR_HOVER = "#34495e"
WARN_COLOR = "#e74c3c"
SELECTED_BG = "#4dc9e4"   # 列表选中高亮色
SYSTEM_BUILTIN_NAMES = ["二合一", "三合一", "四合一", "圆木梢", "层板钉"]


# ============================================================ 默认数据
# 五金类型清单（按参考图顺序）
DEFAULT_HARDWARE_TYPES = [
    "层板钉", "层板钉A",
    "二合一", "二合一A",
    "三合一", "三合一A",
    "四合一", "四合一A",
    "圆木梢", "圆木梢A",
]

# 每种五金的默认属性（参考图给出了"二合一"的完整默认值，
# 其它先复用同一组缺省，等业务清单确认后再分别填）
DEFAULT_HARDWARE_PROPS = {
    "二合一": {
        "孔径":     "8",
        "孔深":     "10",
        "外部孔径": "10",
        "外部孔深": "12",
        "大饼孔深": "13",
        "大饼孔径": "20",
        "基点Z":    "9",
        "绑定五金": "1|二合一",
    },
}

# 属性表统一行顺序（与参考图一致）
HARDWARE_PROP_KEYS = [
    "孔径", "孔深", "外部孔径", "外部孔深",
    "大饼孔深", "大饼孔径", "基点Z", "绑定五金",
]

# A1~A7 标注说明
A_HINTS = [
    "A1=大饼孔径",
    "A2=大饼孔深",
    "A3=孔深/影响距边破边",
    "A4=孔径/可不设置或为0",
    "A5=基点Z/板厚位置",
    "A6=外部孔径/印到侧板的孔径",
    "A7=外部孔深/印到侧板的孔深",
]


# ============================================================ 孔位规则默认数据

# 默认方案名列表（对应参考图左侧列表）
DEFAULT_HOLE_RULE_SCHEMES = [
    "二合一",
    "常规三合一加木肖",
    "抽屉三合一",
    "铰链只打杯孔",
    "活层",
    "通用门铰",
    "常规三合一",
    "底板三合一",
    "顶板三合一",
]

# 板件类型选项
BOARD_TYPES = ["平板类", "侧立类", "面板背板类", "门板类"]

# 表格列定义
HOLE_RULE_COLUMNS = ["#", "五金类型", "数量", "对齐分布", "板厚位置", "存在条件(尺寸区间)", "前偏", "后偏", "左偏"]

# 五金类型选项（下拉）
HARDWARE_TYPE_OPTIONS = ["二合一", "三合一", "四合一", "圆木梢", "层板钉", "铰链", "抽屉轨道"]

# 对齐分布选项
ALIGN_OPTIONS = ["64:1:64", "32:1:64", "32:1:32", "96:1:96", "自定义"]

# 板厚位置选项
THICKNESS_OPTIONS = ["S/2", "S", "0", "自定义"]

# 默认方案数据：{方案名: {配置}}
DEFAULT_SCHEME_DATA = {
    "二合一": {
        "board_types": ["平板类", "侧立类", "面板背板类"],
        "direction": "反面",
        "rows": [
            {"五金类型": "二合一", "数量": "2", "对齐分布": "64:1:64", "板厚位置": "S/2",
             "存在条件(尺寸区间)": "W>250", "前偏": "", "后偏": "", "左偏": ""},
            {"五金类型": "二合一", "数量": "2", "对齐分布": "32:1:64", "板厚位置": "S/2",
             "存在条件(尺寸区间)": "W<=250", "前偏": "", "后偏": "", "左偏": ""},
        ],
    },
}

# ============================================================ 主对话框
class HoleRuleDialog(QDialog):
    """孔位规则 / 五金设置对话框。

    顶部两个 Tab：
        - 孔位规则（占位，后续按需补充）
        - 孔位五金（完整实现）

    暴露信号：
        property_saved(hardware_name: str, props: dict)
            点击"保存应用属性"按钮时发出，由 controller 落盘。
    """

    WINDOW_TITLE = "孔位规则/五金设置"

    property_saved = Signal(str, dict)

    def __init__(self, icon_dir: str = "icons", parent=None):
        super().__init__(parent)
        self.setWindowTitle(self.WINDOW_TITLE)
        self.setModal(True)
        self.resize(1100, 680)

        # 图标资源目录（参考图所在路径）
        self._icon_dir = icon_dir

        # 内存：每种五金的属性缓存 {name: {属性名: 属性值}}
        self._hardware_data: dict[str, dict] = {
            name: dict(DEFAULT_HARDWARE_PROPS.get(name, {})) for name in DEFAULT_HARDWARE_TYPES
        }
        # 当前选中的五金名
        self._current_hardware: str = ""

        self._build_ui()
        self._apply_style()
        self._connect_local_signals()

        # 默认选中"二合一"（与参考图一致）
        self._select_hardware_by_name("二合一")

    # ---------------------------------------------------------------- UI
    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ============ 顶部：Tab + 提示 ============
        top = QWidget()
        top.setObjectName("topBar")
        top_layout = QHBoxLayout(top)
        top_layout.setContentsMargins(8, 4, 12, 0)
        top_layout.setSpacing(8)

        self.tab_bar = QTabBar()
        self.tab_bar.setObjectName("paramTabBar")
        self.tab_bar.setDrawBase(False)
        self.tab_bar.addTab("孔位规则")
        self.tab_bar.addTab("孔位五金")
        self.tab_bar.setCurrentIndex(1)   # 默认显示孔位五金
        top_layout.addWidget(self.tab_bar)

        top_layout.addStretch(1)

        self.lbl_builtin_hint = QLabel("系统固有：" + "、".join(SYSTEM_BUILTIN_NAMES))
        self.lbl_builtin_hint.setStyleSheet("color:#606266; font-size:12px;")
        top_layout.addWidget(self.lbl_builtin_hint)
        root.addWidget(top)

        # ============ 内容堆栈 ============
        self.content_stack = QStackedWidget(self)
        self.page_hole_rule     = HoleRulePage(self)
        self.page_hole_hardware = HoleHardwarePage(self._icon_dir, self)
        self.content_stack.addWidget(self.page_hole_rule)
        self.content_stack.addWidget(self.page_hole_hardware)
        self.content_stack.setCurrentIndex(1)
        root.addWidget(self.content_stack, 1)

        # Tab 切换
        self.tab_bar.currentChanged.connect(self.content_stack.setCurrentIndex)

    # ---------------------------------------------------------------- 样式
    def _apply_style(self):
        self.setStyleSheet(f"""
            QDialog {{ background-color: #ffffff; }}
            QWidget#topBar {{ background: #ffffff; border-bottom: 1px solid #dcdfe6; }}

            /* —— 顶部 Tab —— */
            QTabBar#paramTabBar {{ qproperty-drawBase: 0; background: transparent; }}
            QTabBar#paramTabBar::tab {{
                background: #f5f7fa;
                color: #606266;
                border: 1px solid #dcdfe6;
                border-bottom: none;
                padding: 6px 18px;
                margin-right: 2px;
                min-width: 80px;
            }}
            QTabBar#paramTabBar::tab:hover {{ color: {PRIMARY_COLOR}; }}
            QTabBar#paramTabBar::tab:selected {{
                background: #ffffff;
                color: {PRIMARY_COLOR};
                font-weight: bold;
                border-top: 2px solid {PRIMARY_COLOR};
            }}

            QLabel {{ color: #303133; }}
        """)

    # ---------------------------------------------------------------- 信号
    def _connect_local_signals(self):
        # 五金列表选择 → 切换属性表
        self.page_hole_hardware.hardware_list.currentItemChanged.connect(
            self._on_hardware_changed
        )
        # 属性表的"保存应用属性"按钮
        self.page_hole_hardware.btn_save.clicked.connect(self._on_save_clicked)

    # ---------------- 切换五金 ----------------
    def _on_hardware_changed(self, current: QListWidgetItem, previous: QListWidgetItem):
        # 切换前：先把当前表格数据回写到 _hardware_data
        if previous is not None:
            prev_name = previous.text()
            self._hardware_data[prev_name] = self.page_hole_hardware.get_properties()

        # 切换后：把目标五金的属性加载到表格，并刷新右侧参考图
        if current is None:
            self._current_hardware = ""
            return
        name = current.text()
        self._current_hardware = name
        props = self._hardware_data.get(name, {})
        self.page_hole_hardware.set_properties(props)
        self.page_hole_hardware.preview.load_for_hardware(name)

    def _select_hardware_by_name(self, name: str):
        lst = self.page_hole_hardware.hardware_list
        for i in range(lst.count()):
            if lst.item(i).text() == name:
                lst.setCurrentRow(i)
                return

    # ---------------- 保存 ----------------
    def _on_save_clicked(self):
        if not self._current_hardware:
            return
        props = self.page_hole_hardware.get_properties()
        self._hardware_data[self._current_hardware] = props
        self.property_saved.emit(self._current_hardware, props)

    # ---------------------------------------------------------------- 对外接口
    def get_config(self) -> dict:
        """返回所有五金的属性 + 孔位规则方案。"""
        if self._current_hardware:
            self._hardware_data[self._current_hardware] = self.page_hole_hardware.get_properties()
        return {
            "hardware": dict(self._hardware_data),
            "hole_rules": self.page_hole_rule.get_all_schemes(),
        }

    def set_config(self, cfg: dict):
        """从外部回填全部数据。"""
        hw = cfg.get("hardware", {})
        for name in DEFAULT_HARDWARE_TYPES:
            if name in hw:
                self._hardware_data[name] = dict(hw[name])
        if self._current_hardware:
            self.page_hole_hardware.set_properties(
                self._hardware_data.get(self._current_hardware, {})
            )
        rules = cfg.get("hole_rules", {})
        if rules:
            self.page_hole_rule.set_all_schemes(rules)


# ============================================================ 孔位五金 页
class HoleHardwarePage(QWidget):
    """『孔位五金』分页。

    布局：
        左边 260px ：五金列表 + 属性表 + 保存按钮
        右边自适应 ：参考图片预览（含 A1~A7 文字说明）
    """

    LEFT_WIDTH = 260

    def __init__(self, icon_dir: str, parent=None):
        super().__init__(parent)
        self._icon_dir = icon_dir
        self._build_ui()

    def _build_ui(self):
        root = QHBoxLayout(self)
        root.setContentsMargins(6, 6, 6, 6)
        root.setSpacing(6)

        # 左：列表 + 属性表 + 保存
        left = QWidget()
        left.setFixedWidth(self.LEFT_WIDTH)
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(0)

        # 五金列表
        self.hardware_list = QListWidget()
        self.hardware_list.setObjectName("hardwareList")
        for name in DEFAULT_HARDWARE_TYPES:
            self.hardware_list.addItem(QListWidgetItem(name))
        self.hardware_list.setFixedHeight(260)
        left_layout.addWidget(self.hardware_list)

        # 属性表
        self.prop_table = QTableWidget(len(HARDWARE_PROP_KEYS), 2)
        self.prop_table.setObjectName("propTable")
        self.prop_table.setHorizontalHeaderLabels(["属性名", "属性值"])
        self.prop_table.verticalHeader().setVisible(False)
        self.prop_table.setShowGrid(True)
        self.prop_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.prop_table.setEditTriggers(
            QAbstractItemView.EditTrigger.DoubleClicked
            | QAbstractItemView.EditTrigger.SelectedClicked
            | QAbstractItemView.EditTrigger.EditKeyPressed
        )
        # 第一列只读 = 属性名，第二列可编辑
        for r, key in enumerate(HARDWARE_PROP_KEYS):
            name_item = QTableWidgetItem(key)
            name_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            name_item.setFlags(name_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.prop_table.setItem(r, 0, name_item)
            value_item = QTableWidgetItem("")
            value_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.prop_table.setItem(r, 1, value_item)
        # 列宽
        self.prop_table.setColumnWidth(0, 90)
        self.prop_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        left_layout.addWidget(self.prop_table, 1)

        # 保存按钮
        self.btn_save = QPushButton("保存应用属性 ↑")
        self.btn_save.setObjectName("primaryButton")
        self.btn_save.setFixedHeight(36)
        self.btn_save.setCursor(Qt.CursorShape.PointingHandCursor)
        left_layout.addWidget(self.btn_save)

        root.addWidget(left)

        # 右：图片预览
        self.preview = _HardwarePreview(self._icon_dir, self)
        root.addWidget(self.preview, 1)

        # 样式
        self.setStyleSheet(f"""
            QListWidget#hardwareList {{
                background: #ffffff;
                border: 1px solid #dcdfe6;
                border-radius: 0;
                outline: none;
                font-size: 13px;
            }}
            QListWidget#hardwareList::item {{
                padding: 4px 8px;
                color: #303133;
            }}
            QListWidget#hardwareList::item:hover {{
                background: #ecf5ff;
                color: {PRIMARY_COLOR};
            }}
            QListWidget#hardwareList::item:selected {{
                background: {SELECTED_BG};
                color: #ffffff;
            }}

            QTableWidget#propTable {{
                background: #ffffff;
                gridline-color: #e4e7ed;
                border: 1px solid #dcdfe6;
                border-top: none;
                selection-background-color: #4dc9e4;
                selection-color: #303133;
                font-size: 12px;
            }}
            QHeaderView::section {{
                background-color: #f5f7fa;
                color: #303133;
                padding: 4px;
                border: none;
                border-right: 1px solid #e4e7ed;
                border-bottom: 1px solid #dcdfe6;
                font-weight: bold;
            }}

            QPushButton#primaryButton {{
                background-color: {PRIMARY_COLOR};
                color: #ffffff;
                border: 1px solid {PRIMARY_COLOR};
                border-radius: 0;
                font-size: 13px;
            }}
            QPushButton#primaryButton:hover {{
                background-color: {PRIMARY_COLOR_HOVER};
                border-color: {PRIMARY_COLOR_HOVER};
            }}
            QPushButton#primaryButton:disabled {{
                background: #c0c4cc;
                border-color: #c0c4cc;
            }}
        """)

    # ---------------- 属性读写 ----------------
    def get_properties(self) -> dict:
        result = {}
        for r, key in enumerate(HARDWARE_PROP_KEYS):
            item = self.prop_table.item(r, 1)
            result[key] = item.text() if item else ""
        return result

    def set_properties(self, props: dict):
        for r, key in enumerate(HARDWARE_PROP_KEYS):
            item = self.prop_table.item(r, 1)
            if item is not None:
                item.setText(str(props.get(key, "")))


# ============================================================ 右侧图片预览
class _HardwarePreview(QWidget):
    """右侧五金参考图预览。

    上半部分：实物图 / 示意图（按当前五金加载对应 icon）
    中部：A1~A7 标注说明文字
    底部：尺寸标注图（同一张图的另一区域，本实现统一显示 erheyi.png）
    """

    HARDWARE_ICONS = {
        "二合一":   "erheyi.png",
        "二合一A":  "erheyi.png",
        "三合一":   "sanheyi.png",
        "三合一A":  "sanheyi.png",
        "四合一":   "siheyi.png",
        "四合一A":  "siheyi.png",
        "圆木梢":   "yuanmushao.png",
        "圆木梢A":  "yuanmushao.png",
        "层板钉":   "cengbanding.png",
        "层板钉A":  "cengbanding.png",
    }

    def __init__(self, icon_dir: str, parent=None):
        super().__init__(parent)
        self._icon_dir = icon_dir
        self._current_pixmap: QPixmap | None = None
        self._build_ui()
        self.load_for_hardware("二合一")  # 默认

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        # 图片显示区
        self.lbl_image = QLabel()
        self.lbl_image.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_image.setMinimumHeight(420)
        self.lbl_image.setStyleSheet(
            "QLabel { background: #faf6f0; border: 1px solid #dcdfe6; }"
        )
        layout.addWidget(self.lbl_image, 1)

        # A1~A7 说明文字
        hints_frame = QFrame()
        hints_frame.setStyleSheet(
            "QFrame { background: transparent; border: none; }"
        )
        hints_layout = QVBoxLayout(hints_frame)
        hints_layout.setContentsMargins(8, 4, 8, 4)
        hints_layout.setSpacing(2)
        for text in A_HINTS:
            lbl = QLabel(text)
            lbl.setStyleSheet("color:#303133; font-size:13px;")
            hints_layout.addWidget(lbl)
        layout.addWidget(hints_frame)

    # ---------------- 加载图片 ----------------
    def load_for_hardware(self, name: str):
        """根据五金名加载对应 icon。"""
        fname = self.HARDWARE_ICONS.get(name, "erheyi.png")
        path = os.path.join(self._icon_dir, fname)

        pix = QPixmap(path) if os.path.isfile(path) else QPixmap()
        if pix.isNull():
            # 找不到图：显示占位文字
            self._current_pixmap = None
            self.lbl_image.setPixmap(QPixmap())
            self.lbl_image.setText(
                f"未找到参考图：{path}\n请把 {fname} 放到该路径下。"
            )
            self.lbl_image.setStyleSheet(
                "QLabel { background:#faf6f0; border:1px solid #dcdfe6;"
                " color:#909399; font-size:13px; }"
            )
            return

        self._current_pixmap = pix
        self.lbl_image.setStyleSheet(
            "QLabel { background: #faf6f0; border: 1px solid #dcdfe6; }"
        )
        self._render_scaled()

    def resizeEvent(self, e):
        super().resizeEvent(e)
        if self._current_pixmap is not None:
            self._render_scaled()

    def _render_scaled(self):
        if self._current_pixmap is None:
            return
        target = QSize(
            self.lbl_image.width() - 16,
            self.lbl_image.height() - 16,
        )
        if target.width() <= 0 or target.height() <= 0:
            return
        scaled = self._current_pixmap.scaled(
            target,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        self.lbl_image.setPixmap(scaled)


# ============================================================ 孔位规则 页
class HoleRulePage(QWidget):
    """『孔位规则』分页 —— 完整实现参考图样式。

    布局：
        顶部工具栏：增加方案 | 删除方案 | 命名方案 | 导出方案 | 导入方案
        左侧（固定宽）：方案列表
        右侧（自适应）：
            方案配置区（标题 + 板件类型复选 + 孔位方向单选 + 可编辑表格 + 底部操作栏）
    """

    SCHEME_LIST_W = 160
    COL_WIDTHS    = [30, 100, 50, 90, 70, 140, 50, 50, 50]

    # 样式
    _STYLE = f"""
        QGroupBox {{
            font-size: 13px;
            font-weight: bold;
            color: #303133;
            border: 1px solid #dcdfe6;
            border-radius: 3px;
            margin-top: 6px;
            padding-top: 4px;
        }}
        QGroupBox::title {{
            subcontrol-origin: margin;
            left: 8px;
            padding: 0 4px;
        }}
        QListWidget#schemeList {{
            background: #ffffff;
            border: 1px solid #dcdfe6;
            font-size: 13px;
            outline: none;
        }}
        QListWidget#schemeList::item {{
            padding: 5px 8px;
            color: #303133;
        }}
        QListWidget#schemeList::item:hover   {{ background: #ecf5ff; }}
        QListWidget#schemeList::item:selected {{
            background: {SELECTED_BG};
            color: #ffffff;
        }}
        QTableWidget {{
            background: #ffffff;
            gridline-color: #e4e7ed;
            border: 1px solid #dcdfe6;
            selection-background-color: #4dc9e4;
            selection-color: #303133;
            font-size: 12px;
        }}
        QHeaderView::section {{
            background-color: #f5f7fa;
            color: #303133;
            padding: 4px 2px;
            border: none;
            border-right: 1px solid #e4e7ed;
            border-bottom: 1px solid #dcdfe6;
            font-weight: bold;
            font-size: 12px;
        }}
        QPushButton.toolBtn {{
            background: #ffffff;
            border: 1px solid #dcdfe6;
            border-radius: 3px;
            color: #303133;
            font-size: 12px;
            padding: 3px 10px;
            min-height: 26px;
        }}
        QPushButton.toolBtn:hover   {{ background: #ecf5ff; border-color: #409eff; color: #409eff; }}
        QPushButton.toolBtn:pressed {{ background: #d9ecff; }}
        QPushButton#saveSchemeBtn {{
            background-color: {PRIMARY_COLOR};
            color: #ffffff;
            border: 1px solid {PRIMARY_COLOR};
            border-radius: 3px;
            font-size: 13px;
            padding: 4px 16px;
            min-height: 28px;
        }}
        QPushButton#saveSchemeBtn:hover {{
            background-color: {PRIMARY_COLOR_HOVER};
        }}
        QLabel#warnLabel {{
            color: #e74c3c;
            font-size: 12px;
        }}
        QCheckBox, QRadioButton {{
            font-size: 12px;
            color: #303133;
        }}
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        # 数据：{方案名: {"board_types": [...], "direction": "正面"/"反面", "rows": [...]}}
        self._schemes: dict = {}
        for name in DEFAULT_HOLE_RULE_SCHEMES:
            self._schemes[name] = dict(DEFAULT_SCHEME_DATA.get(name, {
                "board_types": ["平板类", "侧立类", "面板背板类"],
                "direction": "反面",
                "rows": [],
            }))
        self._current_scheme: str = ""
        self._build_ui()
        self.setStyleSheet(self._STYLE)
        # 默认选第一项
        if self.scheme_list.count() > 0:
            self.scheme_list.setCurrentRow(0)

    # ─────────────────────────────── UI
    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ── 顶部工具栏 ─────────────────────────────────────────
        toolbar = QWidget()
        toolbar.setStyleSheet(
            "QWidget { background: #f5f7fa; border-bottom: 1px solid #dcdfe6; }"
        )
        tb_layout = QHBoxLayout(toolbar)
        tb_layout.setContentsMargins(8, 4, 8, 4)
        tb_layout.setSpacing(4)

        self.btn_add_scheme    = self._make_tool_btn("增加方案")
        self.btn_del_scheme    = self._make_tool_btn("删除方案")
        self.btn_rename_scheme = self._make_tool_btn("命名方案")
        self.btn_export_scheme = self._make_tool_btn("导出方案")
        self.btn_import_scheme = self._make_tool_btn("导入方案")

        for btn in [self.btn_add_scheme, self.btn_del_scheme,
                    self.btn_rename_scheme, self.btn_export_scheme,
                    self.btn_import_scheme]:
            tb_layout.addWidget(btn)
        tb_layout.addStretch(1)
        root.addWidget(toolbar)

        # ── 主体（左：方案列表，右：配置区）──────────────────────
        body = QWidget()
        body_layout = QHBoxLayout(body)
        body_layout.setContentsMargins(6, 6, 6, 6)
        body_layout.setSpacing(6)

        # 左：方案列表
        self.scheme_list = QListWidget()
        self.scheme_list.setObjectName("schemeList")
        self.scheme_list.setFixedWidth(self.SCHEME_LIST_W)
        for name in DEFAULT_HOLE_RULE_SCHEMES:
            self.scheme_list.addItem(QListWidgetItem(name))
        body_layout.addWidget(self.scheme_list)

        # 右：配置区
        right = QGroupBox("方案配置")
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(8, 8, 8, 6)
        right_layout.setSpacing(6)

        # ── 板件类型 + 孔位方向 ────────────────────────────────
        options_row = QHBoxLayout()
        options_row.setSpacing(16)

        # 板件类型复选
        board_label = QLabel("应用到板件类型：")
        board_label.setStyleSheet("font-size:12px; color:#303133;")
        options_row.addWidget(board_label)

        self._board_checks: dict[str, QCheckBox] = {}
        for bt in BOARD_TYPES:
            cb = QCheckBox(bt)
            self._board_checks[bt] = cb
            options_row.addWidget(cb)

        options_row.addStretch(1)

        # 孔位方向单选
        dir_label = QLabel("默认的孔位方向：")
        dir_label.setStyleSheet("font-size:12px; color:#303133;")
        options_row.addWidget(dir_label)

        self._dir_group = QButtonGroup(self)
        self._dir_group.setExclusive(True)
        self.rb_front = QRadioButton("正面")
        self.rb_back  = QRadioButton("反面")
        self.rb_back.setChecked(True)
        self._dir_group.addButton(self.rb_front, 0)
        self._dir_group.addButton(self.rb_back,  1)
        options_row.addWidget(self.rb_front)
        options_row.addWidget(self.rb_back)

        right_layout.addLayout(options_row)

        # ── 规则表格 ───────────────────────────────────────────
        self.rule_table = QTableWidget(0, len(HOLE_RULE_COLUMNS))
        self.rule_table.setHorizontalHeaderLabels(HOLE_RULE_COLUMNS)
        self.rule_table.verticalHeader().setVisible(False)
        self.rule_table.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows
        )
        self.rule_table.setEditTriggers(
            QAbstractItemView.EditTrigger.DoubleClicked
            | QAbstractItemView.EditTrigger.SelectedClicked
            | QAbstractItemView.EditTrigger.EditKeyPressed
        )
        # 列宽
        for i, w in enumerate(self.COL_WIDTHS):
            self.rule_table.setColumnWidth(i, w)
        self.rule_table.horizontalHeader().setStretchLastSection(False)
        self.rule_table.horizontalHeader().setSectionResizeMode(
            5, QHeaderView.ResizeMode.Stretch
        )
        right_layout.addWidget(self.rule_table, 1)

        # ── 底部操作栏 ─────────────────────────────────────────
        bottom_bar = QWidget()
        bb_layout = QHBoxLayout(bottom_bar)
        bb_layout.setContentsMargins(0, 0, 0, 0)
        bb_layout.setSpacing(6)

        self.btn_del_row  = self._make_tool_btn("删除行")
        self.btn_add_row  = self._make_tool_btn("添加行")
        bb_layout.addWidget(self.btn_del_row)
        bb_layout.addWidget(self.btn_add_row)

        self.lbl_warn = QLabel(
            "★注意：当孔位五金为KW模板时，板厚位置由KW模板设置决定！！"
        )
        self.lbl_warn.setObjectName("warnLabel")
        bb_layout.addWidget(self.lbl_warn, 1)

        self.btn_save_scheme = QPushButton("✓ 保存方案配置")
        self.btn_save_scheme.setObjectName("saveSchemeBtn")
        self.btn_save_scheme.setCursor(Qt.CursorShape.PointingHandCursor)
        bb_layout.addWidget(self.btn_save_scheme)

        right_layout.addWidget(bottom_bar)
        body_layout.addWidget(right, 1)
        root.addWidget(body, 1)

        # ── 信号连接 ───────────────────────────────────────────
        self.scheme_list.currentItemChanged.connect(self._on_scheme_changed)
        self.btn_add_row.clicked.connect(self._add_row)
        self.btn_del_row.clicked.connect(self._del_row)
        self.btn_save_scheme.clicked.connect(self._save_current_scheme)
        self.btn_add_scheme.clicked.connect(self._add_scheme)
        self.btn_del_scheme.clicked.connect(self._del_scheme)
        self.btn_rename_scheme.clicked.connect(self._rename_scheme)

    def _make_tool_btn(self, text: str) -> QPushButton:
        btn = QPushButton(text)
        btn.setProperty("class", "toolBtn")
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        return btn

    # ─────────────────────────────── 方案切换
    def _on_scheme_changed(self, current: QListWidgetItem, previous: QListWidgetItem):
        # 回写旧方案
        if previous is not None:
            self._write_back(previous.text())
        # 加载新方案
        if current is None:
            self._current_scheme = ""
            self._load_scheme({})
            return
        self._current_scheme = current.text()
        self._load_scheme(self._schemes.get(self._current_scheme, {}))

    def _load_scheme(self, data: dict):
        """把方案数据渲染到右侧控件。"""
        # 板件类型
        board_types = data.get("board_types", [])
        for bt, cb in self._board_checks.items():
            cb.setChecked(bt in board_types)

        # 方向
        direction = data.get("direction", "反面")
        if direction == "正面":
            self.rb_front.setChecked(True)
        else:
            self.rb_back.setChecked(True)

        # 表格
        rows = data.get("rows", [])
        self.rule_table.setRowCount(0)
        for row_data in rows:
            self._append_row(row_data)

    def _write_back(self, scheme_name: str):
        """把当前 UI 状态写回 _schemes。"""
        if not scheme_name:
            return
        self._schemes[scheme_name] = {
            "board_types": [bt for bt, cb in self._board_checks.items() if cb.isChecked()],
            "direction": "正面" if self.rb_front.isChecked() else "反面",
            "rows": self._read_rows(),
        }

    def _read_rows(self) -> list:
        rows = []
        for r in range(self.rule_table.rowCount()):
            row_data = {}
            for c, col_name in enumerate(HOLE_RULE_COLUMNS[1:], 1):  # skip #
                widget = self.rule_table.cellWidget(r, c)
                if isinstance(widget, QComboBox):
                    row_data[col_name] = widget.currentText()
                else:
                    item = self.rule_table.item(r, c)
                    row_data[col_name] = item.text() if item else ""
            rows.append(row_data)
        return rows

    # ─────────────────────────────── 表格行操作
    def _append_row(self, data: dict = None):
        if data is None:
            data = {}
        r = self.rule_table.rowCount()
        self.rule_table.insertRow(r)
        self.rule_table.setRowHeight(r, 26)

        # 列0：序号（只读）
        idx_item = QTableWidgetItem(str(r + 1))
        idx_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        idx_item.setFlags(idx_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
        self.rule_table.setItem(r, 0, idx_item)

        # 列1：五金类型 → 下拉
        combo_hw = QComboBox()
        combo_hw.addItems(HARDWARE_TYPE_OPTIONS)
        val_hw = data.get("五金类型", "二合一")
        idx_hw = combo_hw.findText(val_hw)
        if idx_hw >= 0:
            combo_hw.setCurrentIndex(idx_hw)
        self.rule_table.setCellWidget(r, 1, combo_hw)

        # 列2：数量 → 可编辑
        qty_item = QTableWidgetItem(data.get("数量", "2"))
        qty_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        self.rule_table.setItem(r, 2, qty_item)

        # 列3：对齐分布 → 下拉
        combo_align = QComboBox()
        combo_align.addItems(ALIGN_OPTIONS)
        combo_align.setEditable(True)
        val_align = data.get("对齐分布", "64:1:64")
        combo_align.setCurrentText(val_align)
        self.rule_table.setCellWidget(r, 3, combo_align)

        # 列4：板厚位置 → 下拉
        combo_thick = QComboBox()
        combo_thick.addItems(THICKNESS_OPTIONS)
        combo_thick.setEditable(True)
        val_thick = data.get("板厚位置", "S/2")
        combo_thick.setCurrentText(val_thick)
        self.rule_table.setCellWidget(r, 4, combo_thick)

        # 列5：存在条件（可编辑文本）
        cond_item = QTableWidgetItem(data.get("存在条件(尺寸区间)", ""))
        self.rule_table.setItem(r, 5, cond_item)

        # 列6~8：前偏、后偏、左偏（可编辑）
        for col_idx, key in [(6, "前偏"), (7, "后偏"), (8, "左偏")]:
            item = QTableWidgetItem(data.get(key, ""))
            item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.rule_table.setItem(r, col_idx, item)

    def _add_row(self):
        self._append_row()
        self._refresh_row_numbers()

    def _del_row(self):
        rows = sorted(set(idx.row() for idx in self.rule_table.selectedIndexes()), reverse=True)
        if not rows:
            if self.rule_table.rowCount() > 0:
                rows = [self.rule_table.rowCount() - 1]
        for r in rows:
            self.rule_table.removeRow(r)
        self._refresh_row_numbers()

    def _refresh_row_numbers(self):
        for r in range(self.rule_table.rowCount()):
            item = self.rule_table.item(r, 0)
            if item:
                item.setText(str(r + 1))

    # ─────────────────────────────── 方案管理
    def _save_current_scheme(self):
        if self._current_scheme:
            self._write_back(self._current_scheme)
            QMessageBox.information(self, "保存成功",
                                    f"方案「{self._current_scheme}」已保存。")

    def _add_scheme(self):
        name, ok = QInputDialog.getText(self, "增加方案", "请输入新方案名称：")
        if ok and name.strip():
            name = name.strip()
            if name in self._schemes:
                QMessageBox.warning(self, "名称重复", f"方案「{name}」已存在。")
                return
            self._schemes[name] = {
                "board_types": ["平板类", "侧立类", "面板背板类"],
                "direction": "反面",
                "rows": [],
            }
            self.scheme_list.addItem(QListWidgetItem(name))
            self.scheme_list.setCurrentRow(self.scheme_list.count() - 1)

    def _del_scheme(self):
        item = self.scheme_list.currentItem()
        if item is None:
            return
        name = item.text()
        reply = QMessageBox.question(
            self, "删除方案", f"确定删除方案「{name}」？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            self._schemes.pop(name, None)
            row = self.scheme_list.currentRow()
            self.scheme_list.takeItem(row)

    def _rename_scheme(self):
        item = self.scheme_list.currentItem()
        if item is None:
            return
        old_name = item.text()
        new_name, ok = QInputDialog.getText(self, "命名方案", "请输入新名称：",
                                            text=old_name)
        if ok and new_name.strip() and new_name.strip() != old_name:
            new_name = new_name.strip()
            if new_name in self._schemes:
                QMessageBox.warning(self, "名称重复", f"方案「{new_name}」已存在。")
                return
            data = self._schemes.pop(old_name, {})
            self._schemes[new_name] = data
            item.setText(new_name)
            self._current_scheme = new_name

    # ─────────────────────────────── 对外接口
    def get_all_schemes(self) -> dict:
        """返回所有方案数据（含当前未保存的）。"""
        if self._current_scheme:
            self._write_back(self._current_scheme)
        return {k: dict(v) for k, v in self._schemes.items()}

    def set_all_schemes(self, data: dict):
        """从外部回填所有方案。"""
        self._schemes = {k: dict(v) for k, v in data.items()}
        self.scheme_list.clear()
        for name in self._schemes:
            self.scheme_list.addItem(QListWidgetItem(name))
        if self.scheme_list.count() > 0:
            self.scheme_list.setCurrentRow(0)


# ============================================================ 占位页
class _PlaceholderPage(QWidget):
    """其它暂未实现的分页。"""

    def __init__(self, title: str, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(30, 30, 30, 30)
        lbl = QLabel(f"『{title}』分类内容待补充")
        lbl.setStyleSheet("color:#909399; font-size:14px;")
        lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(lbl)
        layout.addStretch(1)
