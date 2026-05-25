# -*- coding: utf-8 -*-
"""快捷命令注册设置对话框

对应 菜单 → 设置 → 快捷命令设置。
顶部分类 Tab：
    1. 场景设计模式  —— 完整录入参考图列出的命令（默认 21 条）
    2. 产品设计模式  —— 占位，可后续补充
    3. 产品图块调用  —— 占位
    4. 快捷启动      —— 占位

每行字段：序号 / 软件功能 / 命令代码 / ALT组合 / 备注说明
快捷键规则：
    - 普通快捷命令 = 命令代码 + 空格键
    - ALT 组合     = ALT 键 + 单字符
"""
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QDialog,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPushButton,
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
CHECK_BLUE = "#4dc9e4"


# ============================================================ 数据：默认快捷命令清单
# 场景设计模式 —— 严格按参考图顺序录入（第 21 行参考图被截断，按业务推测命名）
DEFAULT_SCENE_COMMANDS = [
    # (软件功能, 命令代码, ALT组合默认勾选)
    ("添加柜子", "GZ",  False),
    ("添加滑门", "HM",  False),
    ("结构设计", "G",   False),
    ("材料装饰", "ZS",  False),
    ("复制对象", "C",   False),
    ("旋转对象", "XZ",  False),
    ("缩放对象", "SF",  False),
    ("移动对象", "M",   False),
    ("成组操作", "CZ",  False),
    ("隐藏选中", "H",   False),
    ("删除选中", "D",   False),
    ("属性操作", "SX",  False),
    ("隐藏门类", "HH",  False),
    ("客户信息", "KH",  False),
    ("结算报价", "JS",  False),
    ("附加配件", "PJ",  False),
    ("生产拆料", "CL",  False),
    ("渲染图纸", "XR",  False),
    ("CAD输出", "CAD", False),
    ("测量尺寸", "CC",  False),
    ("产品图上传", "SC", False),
]


# ============================================================ 主对话框
class ShortcutCommandDialog(QDialog):
    """快捷命令注册设置对话框。"""

    WINDOW_TITLE = "快捷命令注册设置"

    CATEGORIES = [
        ("scene_design",   "场景设计模式", DEFAULT_SCENE_COMMANDS),
        ("product_design", "产品设计模式", []),
        ("product_block",  "产品图块调用", []),
        ("quick_launch",   "快捷启动",     []),
    ]

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(self.WINDOW_TITLE)
        self.setModal(True)
        self.resize(820, 760)

        # 各分类页面引用 {key: ShortcutTablePage}
        self.pages: dict[str, "ShortcutTablePage"] = {}

        self._build_ui()
        self._apply_style()

    # ---------------------------------------------------------------- UI
    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(6)

        # 顶部 Tab
        self.tab_bar = QTabBar()
        self.tab_bar.setObjectName("topTabBar")
        self.tab_bar.setDrawBase(False)
        for _key, label, _data in self.CATEGORIES:
            self.tab_bar.addTab(label)
        root.addWidget(self.tab_bar)

        # 内容堆栈
        self.stack = QStackedWidget()
        for key, _label, data in self.CATEGORIES:
            page = ShortcutTablePage(data, self)
            self.pages[key] = page
            self.stack.addWidget(page)
        root.addWidget(self.stack, 1)

        self.tab_bar.currentChanged.connect(self.stack.setCurrentIndex)

        # 底部说明 + 保存按钮
        root.addLayout(self._build_bottom_bar())

    def _build_bottom_bar(self) -> QHBoxLayout:
        bar = QHBoxLayout()
        bar.setContentsMargins(8, 6, 8, 4)
        bar.setSpacing(12)

        # 注意说明（两行）
        note_box = QVBoxLayout()
        note_box.setSpacing(2)
        self.lbl_note_1 = QLabel("注意说明：1、快捷命令 = 命令代码 + 空格键")
        self.lbl_note_2 = QLabel("              2、快捷键方式 = ALT 键 + 单字符")
        for lbl in (self.lbl_note_1, self.lbl_note_2):
            lbl.setStyleSheet(f"color: {WARN_COLOR}; font-size: 13px;")
        note_box.addWidget(self.lbl_note_1)
        note_box.addWidget(self.lbl_note_2)
        bar.addLayout(note_box)

        bar.addStretch(1)

        self.btn_save = QPushButton("保存设置")
        self.btn_save.setObjectName("saveButton")
        self.btn_save.setFixedSize(140, 56)
        self.btn_save.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_save.clicked.connect(self.accept)
        bar.addWidget(self.btn_save)
        return bar

    # ---------------------------------------------------------------- 样式
    def _apply_style(self):
        self.setStyleSheet(f"""
            QDialog {{ background-color: #ffffff; }}

            /* —— 顶部 Tab —— */
            QTabBar#topTabBar {{
                qproperty-drawBase: 0;
                background: transparent;
            }}
            QTabBar#topTabBar::tab {{
                background: #f5f7fa;
                color: #606266;
                border: 1px solid #dcdfe6;
                border-bottom: none;
                padding: 8px 18px;
                margin-right: 2px;
                min-width: 110px;
            }}
            QTabBar#topTabBar::tab:hover {{
                color: {PRIMARY_COLOR};
            }}
            QTabBar#topTabBar::tab:selected {{
                background: #ffffff;
                color: {PRIMARY_COLOR};
                font-weight: bold;
                border-top: 2px solid {PRIMARY_COLOR};
            }}

            /* —— 表格 —— */
            QTableWidget {{
                background: #ffffff;
                gridline-color: #e4e7ed;
                border: 1px solid #dcdfe6;
                selection-background-color: #ecf5ff;
                selection-color: #303133;
                font-size: 13px;
            }}
            QTableWidget::item {{
                padding: 4px 6px;
            }}
            QHeaderView::section {{
                background-color: #f5f7fa;
                color: #303133;
                padding: 6px 4px;
                border: none;
                border-right: 1px solid #e4e7ed;
                border-bottom: 1px solid #dcdfe6;
                font-weight: bold;
            }}

            /* —— 输入框 —— */
            QLineEdit {{
                border: 1px solid transparent;
                padding: 2px 4px;
                background: transparent;
            }}
            QLineEdit:focus {{
                border: 1px solid {PRIMARY_COLOR};
                background: #ffffff;
            }}

            QLabel {{ color: #303133; }}

            /* —— 保存按钮：主色调 —— */
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
        """返回所有分类的快捷命令配置。"""
        return {key: self.pages[key].get_rows() for key, _l, _d in self.CATEGORIES}

    def set_config(self, cfg: dict):
        """把已有快捷命令回填到表格。"""
        for key, _label, _data in self.CATEGORIES:
            if key in cfg:
                self.pages[key].set_rows(cfg[key])


# ============================================================ 单页：命令表
class ShortcutTablePage(QWidget):
    """单个分类下的快捷命令表。

    列：序号(#) | 软件功能 | 命令代码 | ALT组合(checkbox) | 备注说明
    """

    COL_INDEX     = 0
    COL_FUNCTION  = 1
    COL_CODE      = 2
    COL_ALT       = 3
    COL_REMARK    = 4

    HEADERS = ["#", "软件功能", "命令代码", "ALT组合", "备注说明"]

    def __init__(self, rows: list[tuple], parent=None):
        super().__init__(parent)
        self._build_ui()
        self.set_rows([
            {"function": fn, "code": code, "alt": alt, "remark": ""}
            for fn, code, alt in rows
        ])

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.table = QTableWidget(0, len(self.HEADERS), self)
        self.table.setHorizontalHeaderLabels(self.HEADERS)
        self.table.verticalHeader().setVisible(False)
        self.table.setShowGrid(True)
        self.table.setAlternatingRowColors(False)
        self.table.setEditTriggers(
            QTableWidget.EditTrigger.DoubleClicked
            | QTableWidget.EditTrigger.SelectedClicked
            | QTableWidget.EditTrigger.EditKeyPressed
        )
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)

        # 列宽策略
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(self.COL_INDEX,    QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(self.COL_FUNCTION, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(self.COL_CODE,     QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(self.COL_ALT,      QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(self.COL_REMARK,   QHeaderView.ResizeMode.Stretch)
        self.table.setColumnWidth(self.COL_INDEX,    60)
        self.table.setColumnWidth(self.COL_FUNCTION, 180)
        self.table.setColumnWidth(self.COL_CODE,     120)
        self.table.setColumnWidth(self.COL_ALT,      90)

        layout.addWidget(self.table)

    # ---------------------------------------------------------------- 数据接口
    def set_rows(self, rows: list[dict]):
        """rows: [{function, code, alt, remark}, ...]"""
        self.table.setRowCount(len(rows))
        for r, row in enumerate(rows):
            self._set_index_cell(r)
            self._set_text_cell(r, self.COL_FUNCTION, row.get("function", ""))
            self._set_text_cell(r, self.COL_CODE,     row.get("code", ""), align_center=True)
            self._set_alt_cell(r,  bool(row.get("alt", False)))
            self._set_text_cell(r, self.COL_REMARK,   row.get("remark", ""))

    def get_rows(self) -> list[dict]:
        """从表格收集所有行数据。"""
        result = []
        for r in range(self.table.rowCount()):
            result.append({
                "function": self._get_text(r, self.COL_FUNCTION),
                "code":     self._get_text(r, self.COL_CODE),
                "alt":      self._get_alt(r),
                "remark":   self._get_text(r, self.COL_REMARK),
            })
        return result

    # ---------------------------------------------------------------- 单元格构造
    def _set_index_cell(self, row: int):
        """序号列：不可编辑，居中。"""
        item = QTableWidgetItem(str(row + 1))
        item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
        item.setForeground(QColor("#606266"))
        self.table.setItem(row, self.COL_INDEX, item)

    def _set_text_cell(self, row: int, col: int, text: str, align_center: bool = False):
        item = QTableWidgetItem(text or "")
        if align_center:
            item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        self.table.setItem(row, col, item)

    def _set_alt_cell(self, row: int, checked: bool):
        """ALT 组合列：放一个居中的复选框。"""
        from PySide6.QtWidgets import QCheckBox  # 局部导入避免顶部杂乱
        container = QWidget()
        h = QHBoxLayout(container)
        h.setContentsMargins(0, 0, 0, 0)
        chk = QCheckBox()
        chk.setChecked(checked)
        chk.setStyleSheet(f"""
            QCheckBox::indicator {{
                width: 16px; height: 16px;
                border: 1px solid #c0c4cc;
                border-radius: 2px;
                background: #ffffff;
            }}
            QCheckBox::indicator:hover {{ border: 1px solid {CHECK_BLUE}; }}
            QCheckBox::indicator:checked {{
                background: {CHECK_BLUE};
                border: 1px solid {CHECK_BLUE};
            }}
        """)
        h.addStretch(1)
        h.addWidget(chk)
        h.addStretch(1)
        # 把复选框引用挂在容器上，便于 _get_alt 读取
        container.checkbox = chk
        self.table.setCellWidget(row, self.COL_ALT, container)

    def _get_text(self, row: int, col: int) -> str:
        item = self.table.item(row, col)
        return item.text().strip() if item else ""

    def _get_alt(self, row: int) -> bool:
        widget = self.table.cellWidget(row, self.COL_ALT)
        if widget and hasattr(widget, "checkbox"):
            return widget.checkbox.isChecked()
        return False
