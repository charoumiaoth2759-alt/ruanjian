# -*- coding: utf-8 -*-
"""图元参数化编辑器对话框

对应 菜单 → 设置 → 异形图元设置。
整体布局（按参考图）：
    ┌────────────────────────────────────────────────────────────────┐
    │  顶部工具栏：新建图元 / 打开图元 / 保存图元 / 从CAD抓取        │
    │              / 参数化 / 刷新视图 / 升级旧版                     │
    ├──────────────────────────────┬─────────────────────────────────┤
    │                              │ 演示尺寸 W___ L___  尺寸限制...  │
    │                              │ 宫格设置 横 2  纵 2  高度...     │
    │                              ├─────────────────────────────────┤
    │                              │ [ 路径对象 | 附加变量 ]          │
    │   预览画布（灰色背景）        │ 表格：# 类型 刀具or直径 雕刻深度  │
    │                              │       加工速度 主轴转速 加工方向 │
    │                              ├─────────────────────────────────┤
    │                              │ 红色注意提示                    │
    │                              ├─────────────────────────────────┤
    │                              │ 表格：# 类型 坐标公式_X _Y _Z   │
    └──────────────────────────────┴─────────────────────────────────┘

本对话框只负责"采集与编辑"，参数化解析 / CAD 抓取等由 core 层处理。
"""
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QAction, QColor, QPainter, QPen
from PySide6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QFrame,
    QGraphicsScene,
    QGraphicsView,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QStackedWidget,
    QTabBar,
    QTableWidget,
    QTableWidgetItem,
    QToolBar,
    QVBoxLayout,
    QWidget,
)


# 主题色（与主窗口、其他对话框保持一致）
PRIMARY_COLOR = "#2c3e50"
PRIMARY_COLOR_HOVER = "#34495e"
WARN_COLOR = "#e74c3c"
CHECK_BLUE = "#3a8ee6"


# ============================================================ 主对话框
class IrregularElementDialog(QDialog):
    """图元参数化编辑器对话框。"""

    WINDOW_TITLE = "图元参数化编辑器  2025.11203"

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(self.WINDOW_TITLE)
        self.setModal(True)
        self.resize(1280, 780)

        self._build_ui()
        self._apply_style()

    # ---------------------------------------------------------------- UI
    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # 顶部工具栏
        self.tool_bar = self._build_tool_bar()
        root.addWidget(self.tool_bar)

        # 主体：左画布 + 右参数面板
        body = QHBoxLayout()
        body.setContentsMargins(6, 6, 6, 6)
        body.setSpacing(6)

        self.canvas = ElementPreviewCanvas(self)
        body.addWidget(self.canvas, 5)

        self.param_panel = ParamPanel(self)
        body.addWidget(self.param_panel, 6)

        root.addLayout(body, 1)

    # ---------------- 顶部工具栏 ----------------
    def _build_tool_bar(self) -> QToolBar:
        bar = QToolBar(self)
        bar.setObjectName("topToolBar")
        bar.setMovable(False)
        bar.setIconSize(bar.iconSize())
        bar.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextOnly)

        self.action_new       = QAction("📄  新建图元", self)
        self.action_open      = QAction("📁  打开图元", self)
        self.action_save      = QAction("💾  保存图元", self)
        self.action_cad_grab  = QAction("✂️  从CAD抓取", self)
        self.action_parametric = QAction("➡️  参数化", self)
        self.action_refresh   = QAction("🔄  刷新视图", self)
        self.action_upgrade   = QAction("⬆️  升级旧版", self)

        for act in (
            self.action_new, self.action_open, self.action_save,
            self.action_cad_grab, self.action_parametric,
            self.action_refresh, self.action_upgrade,
        ):
            bar.addAction(act)
            bar.addSeparator()
        return bar

    # ---------------------------------------------------------------- 样式
    def _apply_style(self):
        self.setStyleSheet(f"""
            QDialog {{
                background-color: #f5f7fa;
            }}

            /* —— 顶部工具栏 —— */
            QToolBar#topToolBar {{
                background: #ffffff;
                border: none;
                border-bottom: 1px solid #dcdfe6;
                padding: 4px 6px;
                spacing: 4px;
            }}
            QToolBar#topToolBar QToolButton {{
                background: transparent;
                color: #303133;
                border: 1px solid transparent;
                border-radius: 3px;
                padding: 4px 10px;
                font-size: 13px;
            }}
            QToolBar#topToolBar QToolButton:hover {{
                background: #ecf0f5;
                border-color: {PRIMARY_COLOR};
                color: {PRIMARY_COLOR};
            }}
            QToolBar#topToolBar QToolButton:pressed {{
                background: {PRIMARY_COLOR};
                color: #ffffff;
            }}
            QToolBar::separator {{
                background: transparent;
                width: 1px;
                margin: 4px 2px;
            }}

            /* —— 公共控件 —— */
            QLabel {{ color: #303133; }}
            QLineEdit {{
                border: 1px solid #c0c4cc;
                border-radius: 2px;
                padding: 2px 4px;
                background: #ffffff;
                selection-background-color: {PRIMARY_COLOR};
            }}
            QLineEdit:focus {{
                border: 1px solid {PRIMARY_COLOR};
            }}
        """)


# ============================================================ 左侧预览画布
class ElementPreviewCanvas(QGraphicsView):
    """图元预览画布。

    暂提供灰色背景的占位实现。参数化解析完成后，会把折线 / 圆弧 /
    标注等绘制到 scene 里；CAD 抓取的几何也会回写到此画布。
    """

    BG_COLOR = QColor("#9a9a9a")  # 参考图灰色调

    def __init__(self, parent=None):
        scene = QGraphicsScene()
        scene.setSceneRect(-5000, -5000, 10000, 10000)
        super().__init__(scene, parent)

        self.setBackgroundBrush(self.BG_COLOR)
        self.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setFrameShape(QFrame.Shape.Box)
        self.setStyleSheet("QGraphicsView { border: 1px solid #909399; }")


# ============================================================ 右侧参数面板
class ParamPanel(QWidget):
    """右侧参数面板。

    结构：
        1. 顶部尺寸/宫格输入区
        2. 切换 Tab（路径对象 / 附加变量）
        3. 上半表（路径对象表）
        4. 红色注意说明
        5. 下半表（坐标公式表）
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._build_ui()

    # ---------------- UI ----------------
    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(6)

        root.addWidget(self._build_size_box())
        root.addWidget(self._build_main_tab())
        root.addWidget(self._build_path_object_table(), 1)
        root.addWidget(self._build_warning_label())
        root.addWidget(self._build_coord_formula_table(), 1)

    # ---------------- 1. 尺寸 / 宫格输入区 ----------------
    def _build_size_box(self) -> QFrame:
        box = QFrame()
        box.setObjectName("sizeBox")
        layout = QHBoxLayout(box)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(8)

        # —— 左列：演示尺寸 + 宫格设置 ——
        left_col = QVBoxLayout()
        left_col.setSpacing(6)

        # 演示尺寸
        row_demo = QHBoxLayout()
        row_demo.setSpacing(6)
        row_demo.addWidget(QLabel("演示尺寸: W"))
        self.edit_demo_w = QLineEdit()
        self.edit_demo_w.setFixedWidth(80)
        row_demo.addWidget(self.edit_demo_w)
        row_demo.addWidget(QLabel("L"))
        self.edit_demo_l = QLineEdit()
        self.edit_demo_l.setFixedWidth(80)
        row_demo.addWidget(self.edit_demo_l)
        row_demo.addStretch(1)
        left_col.addLayout(row_demo)

        # 宫格设置
        row_grid = QHBoxLayout()
        row_grid.setSpacing(6)
        row_grid.addWidget(QLabel("宫格设置: 横"))
        self.edit_grid_x = QLineEdit("2")
        self.edit_grid_x.setFixedWidth(80)
        self.edit_grid_x.setAlignment(Qt.AlignmentFlag.AlignCenter)
        row_grid.addWidget(self.edit_grid_x)
        row_grid.addWidget(QLabel("纵"))
        self.edit_grid_y = QLineEdit("2")
        self.edit_grid_y.setFixedWidth(80)
        self.edit_grid_y.setAlignment(Qt.AlignmentFlag.AlignCenter)
        row_grid.addWidget(self.edit_grid_y)
        row_grid.addStretch(1)
        left_col.addLayout(row_grid)

        layout.addLayout(left_col)

        # —— 右列：尺寸限制（宽度 / 高度）——
        right_col = QVBoxLayout()
        right_col.setSpacing(6)

        # 宽度
        row_w = QHBoxLayout()
        row_w.setSpacing(6)
        row_w.addWidget(QLabel("尺寸限制: 宽度/W"))
        self.edit_limit_w_min = QLineEdit()
        self.edit_limit_w_min.setFixedWidth(90)
        row_w.addWidget(self.edit_limit_w_min)
        row_w.addWidget(QLabel("至"))
        self.edit_limit_w_max = QLineEdit()
        self.edit_limit_w_max.setFixedWidth(90)
        row_w.addWidget(self.edit_limit_w_max)
        row_w.addStretch(1)
        right_col.addLayout(row_w)

        # 高度
        row_h = QHBoxLayout()
        row_h.setSpacing(6)
        # 用空白占位使"高度/L"与"宽度/W"左对齐
        lbl_h = QLabel("           高度/L")
        row_h.addWidget(lbl_h)
        self.edit_limit_h_min = QLineEdit()
        self.edit_limit_h_min.setFixedWidth(90)
        row_h.addWidget(self.edit_limit_h_min)
        row_h.addWidget(QLabel("至"))
        self.edit_limit_h_max = QLineEdit()
        self.edit_limit_h_max.setFixedWidth(90)
        row_h.addWidget(self.edit_limit_h_max)
        row_h.addStretch(1)
        right_col.addLayout(row_h)

        layout.addLayout(right_col)

        box.setStyleSheet(f"""
            QFrame#sizeBox {{
                background: #ffffff;
                border: 1px solid #dcdfe6;
                border-radius: 2px;
            }}
        """)
        return box

    # ---------------- 2. Tab：路径对象 / 附加变量 ----------------
    def _build_main_tab(self) -> QWidget:
        wrap = QWidget()
        wrap_layout = QHBoxLayout(wrap)
        wrap_layout.setContentsMargins(0, 0, 0, 0)
        wrap_layout.setSpacing(0)

        self.tab_bar = QTabBar()
        self.tab_bar.setObjectName("paramTabBar")
        self.tab_bar.setDrawBase(False)
        self.tab_bar.addTab("路径对象")
        self.tab_bar.addTab("附加变量")
        wrap_layout.addWidget(self.tab_bar)
        wrap_layout.addStretch(1)

        # Tab 样式
        self.tab_bar.setStyleSheet(f"""
            QTabBar#paramTabBar {{
                qproperty-drawBase: 0;
                background: transparent;
            }}
            QTabBar#paramTabBar::tab {{
                background: #f5f7fa;
                color: #606266;
                border: 1px solid #dcdfe6;
                border-bottom: none;
                padding: 6px 18px;
                margin-right: 2px;
                min-width: 70px;
            }}
            QTabBar#paramTabBar::tab:hover {{
                color: {PRIMARY_COLOR};
            }}
            QTabBar#paramTabBar::tab:selected {{
                background: #ffffff;
                color: {PRIMARY_COLOR};
                font-weight: bold;
                border-top: 2px solid {PRIMARY_COLOR};
            }}
        """)
        return wrap

    # ---------------- 3. 路径对象表 ----------------
    def _build_path_object_table(self) -> QTableWidget:
        headers = ["#", "类型", "刀具or直径", "雕刻深度",
                   "加工速度", "主轴转速", "加工方向", "反"]
        self.table_path = self._make_table(headers, row_count=0)
        # 列宽
        self.table_path.setColumnWidth(0, 36)
        self.table_path.setColumnWidth(1, 70)
        self.table_path.setColumnWidth(2, 100)
        self.table_path.setColumnWidth(3, 80)
        self.table_path.setColumnWidth(4, 80)
        self.table_path.setColumnWidth(5, 80)
        self.table_path.setColumnWidth(6, 80)
        self.table_path.setColumnWidth(7, 40)
        return self.table_path

    # ---------------- 4. 红色注意说明 ----------------
    def _build_warning_label(self) -> QLabel:
        self.lbl_warning = QLabel(
            "注意：为适应不同机器参数，非专用刀具，建议《刀具or直径》设置直径数值更为合理！"
        )
        self.lbl_warning.setStyleSheet(f"color:{WARN_COLOR}; font-size:12px; padding:2px 4px;")
        self.lbl_warning.setAlignment(Qt.AlignmentFlag.AlignCenter)
        return self.lbl_warning

    # ---------------- 5. 坐标公式表 ----------------
    def _build_coord_formula_table(self) -> QTableWidget:
        headers = ["#", "类型", "坐标公式_X", "坐标公式_Y", "坐标公式_Z"]
        self.table_coord = self._make_table(headers, row_count=0)
        self.table_coord.setColumnWidth(0, 36)
        self.table_coord.setColumnWidth(1, 70)
        header = self.table_coord.horizontalHeader()
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)
        return self.table_coord

    # ---------------- 工具：创建统一样式的表格 ----------------
    def _make_table(self, headers: list[str], row_count: int) -> QTableWidget:
        table = QTableWidget(row_count, len(headers))
        table.setHorizontalHeaderLabels(headers)
        table.verticalHeader().setVisible(False)
        table.setShowGrid(True)
        table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        table.setEditTriggers(
            QAbstractItemView.EditTrigger.DoubleClicked
            | QAbstractItemView.EditTrigger.SelectedClicked
            | QAbstractItemView.EditTrigger.EditKeyPressed
        )
        table.setAlternatingRowColors(False)
        table.setStyleSheet(f"""
            QTableWidget {{
                background: #ffffff;
                gridline-color: #e4e7ed;
                border: 1px solid #dcdfe6;
                selection-background-color: #ecf5ff;
                selection-color: #303133;
                font-size: 12px;
            }}
            QHeaderView::section {{
                background-color: #f5f7fa;
                color: #303133;
                padding: 4px 4px;
                border: none;
                border-right: 1px solid #e4e7ed;
                border-bottom: 1px solid #dcdfe6;
                font-weight: bold;
            }}
        """)
        return table

    # ---------------------------------------------------------------- 对外接口
    def get_data(self) -> dict:
        """收集本面板的全部数据。"""
        return {
            "demo_size": {
                "w": _to_float(self.edit_demo_w.text(), None),
                "l": _to_float(self.edit_demo_l.text(), None),
            },
            "grid_size": {
                "x": _to_int(self.edit_grid_x.text(), None),
                "y": _to_int(self.edit_grid_y.text(), None),
            },
            "limit_w": [
                _to_float(self.edit_limit_w_min.text(), None),
                _to_float(self.edit_limit_w_max.text(), None),
            ],
            "limit_h": [
                _to_float(self.edit_limit_h_min.text(), None),
                _to_float(self.edit_limit_h_max.text(), None),
            ],
            "path_objects":   self._read_table(self.table_path),
            "coord_formulas": self._read_table(self.table_coord),
        }

    def set_data(self, data: dict):
        demo = data.get("demo_size", {})
        if demo.get("w") is not None: self.edit_demo_w.setText(str(demo["w"]))
        if demo.get("l") is not None: self.edit_demo_l.setText(str(demo["l"]))

        grid = data.get("grid_size", {})
        if grid.get("x") is not None: self.edit_grid_x.setText(str(grid["x"]))
        if grid.get("y") is not None: self.edit_grid_y.setText(str(grid["y"]))

        lw = data.get("limit_w", [])
        if len(lw) >= 1 and lw[0] is not None: self.edit_limit_w_min.setText(str(lw[0]))
        if len(lw) >= 2 and lw[1] is not None: self.edit_limit_w_max.setText(str(lw[1]))

        lh = data.get("limit_h", [])
        if len(lh) >= 1 and lh[0] is not None: self.edit_limit_h_min.setText(str(lh[0]))
        if len(lh) >= 2 and lh[1] is not None: self.edit_limit_h_max.setText(str(lh[1]))

        self._write_table(self.table_path,  data.get("path_objects",   []))
        self._write_table(self.table_coord, data.get("coord_formulas", []))

    # ---------------- 表格读写 ----------------
    @staticmethod
    def _read_table(table: QTableWidget) -> list[list[str]]:
        rows = []
        for r in range(table.rowCount()):
            row = []
            for c in range(table.columnCount()):
                item = table.item(r, c)
                row.append(item.text() if item else "")
            rows.append(row)
        return rows

    @staticmethod
    def _write_table(table: QTableWidget, rows: list[list[str]]):
        table.setRowCount(len(rows))
        for r, row in enumerate(rows):
            for c, value in enumerate(row):
                if c >= table.columnCount():
                    break
                item = QTableWidgetItem(str(value) if value is not None else "")
                if c == 0:
                    item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                    item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                table.setItem(r, c, item)


# ============================================================ 工具函数
def _to_int(text: str, default):
    try:
        return int(str(text).strip())
    except (ValueError, AttributeError, TypeError):
        return default


def _to_float(text: str, default):
    try:
        return float(str(text).strip())
    except (ValueError, AttributeError, TypeError):
        return default
