# -*- coding: utf-8 -*-
"""订单文件管理对话框

对应 菜单 → 订单 → 订单管理 / 新建订单。
布局（按参考图）：
    ┌──────────────────────────────────────────────────────────────┐
    │ [本地订单]                                                    │
    ├─────────────────────────────────────────────┬────────────────┤
    │                                             │ ☑ 文件日期 ___ │
    │  订单列表（多选 + 多列）：                    │ 结束日期 ___   │
    │  ☐ # 订单号 门店 客户 手机 地址               │ 关键字  ___    │
    │     设计师 状态 最后修改                       │ 文件状态 全部▼ │
    │                                             │ [查找订单]     │
    │                                             ├────────────────┤
    │                                             │ 备注/日志区     │
    │                                             │                │
    │                                             ├────────────────┤
    │                                             │ [打开][提交][删]│
    │                                             ├────────────────┤
    │                                             │ 红色提示        │
    └─────────────────────────────────────────────┴────────────────┘

本对话框只负责"采集 + 显示"，订单读取 / 提交 / 删除等业务
由 controller / core 层处理，通过暴露的 action / signal 接入。
"""
from datetime import date

from PySide6.QtCore import Qt, Signal, QDate
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QDateEdit,
    QDialog,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPushButton,
    QTabBar,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)


# 主题色（与主窗口、其它对话框保持一致）
PRIMARY_COLOR = "#2c3e50"
PRIMARY_COLOR_HOVER = "#34495e"
WARN_COLOR = "#e74c3c"
CHECK_BLUE = "#3a8ee6"


# ============================================================ 默认演示数据
# 仅在对话框首次打开时填充，后续由 controller 通过 set_orders() 注入真实数据
DEMO_ORDERS = [
    # (订单号, 门店, 客户, 手机, 地址, 设计师, 状态, 最后修改)
    ("2604004",     "豪莱屋家居", "", "", "",              "", "设计中", "2026/4/29"),
    ("2604005",     "豪莱屋家居", "", "", "",              "", "设计中", "2026/4/18"),
    ("2604006",     "豪莱屋家居", "", "", "",              "", "设计中", "2026/4/15"),
    ("2604007",     "豪莱屋家居", "", "", "",              "", "设计中", "2026/4/25"),
    ("2604007",     "豪莱屋家居", "", "", "凤凰城6-602",    "", "设计中", "2026/4/27"),
    ("HLW0419002",  "豪莱屋家居", "", "", "凤凰城5-1-1102", "", "已拆单", "2026/4/26"),
    ("2604005",     "豪莱屋家居", "", "", "凤凰城6-1201",   "", "设计中", "2026/4/28"),
    ("2605005",     "豪莱屋家居", "", "", "",              "", "设计中", "2026/5/14"),
]


# ============================================================ 主对话框
class OrderManagerDialog(QDialog):
    """订单文件管理对话框。

    对外暴露的信号（业务层连接）：
        search_requested(filters: dict)
        open_requested(order_ids: list[str])
        submit_requested(order_ids: list[str])
        delete_requested(order_ids: list[str])
    """

    WINDOW_TITLE = "订单文件管理"

    search_requested = Signal(dict)
    open_requested   = Signal(list)
    submit_requested = Signal(list)
    delete_requested = Signal(list)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(self.WINDOW_TITLE)
        self.setModal(True)
        self.resize(1080, 680)

        self._build_ui()
        self._apply_style()
        self._connect_local_signals()

        # 默认填充演示数据，方便预览
        self.set_orders(DEMO_ORDERS)

    # ---------------------------------------------------------------- UI
    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # 顶部 Tab（仅"本地订单"，后续可扩展"云端订单"等）
        self.tab_bar = QTabBar()
        self.tab_bar.setObjectName("topTabBar")
        self.tab_bar.setDrawBase(False)
        self.tab_bar.addTab("本地订单")
        root.addWidget(self.tab_bar)

        body = QHBoxLayout()
        body.setContentsMargins(8, 8, 8, 8)
        body.setSpacing(8)

        # 左：订单表格
        body.addWidget(self._build_order_table(), 5)
        # 右：筛选 + 操作 + 提示
        body.addWidget(self._build_side_panel(), 0)

        root.addLayout(body, 1)

    # ---------------- 左侧订单表 ----------------
    def _build_order_table(self) -> QTableWidget:
        headers = ["", "序号", "订单号", "门店", "客户", "手机",
                   "地址", "设计师", "状态", "最后修改"]

        self.table = QTableWidget(0, len(headers), self)
        self.table.setHorizontalHeaderLabels(headers)
        self.table.verticalHeader().setVisible(False)
        self.table.setShowGrid(True)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setAlternatingRowColors(False)

        # 列宽
        self.table.setColumnWidth(0, 36)   # checkbox
        self.table.setColumnWidth(1, 50)   # 序号
        self.table.setColumnWidth(2, 110)  # 订单号
        self.table.setColumnWidth(3, 110)  # 门店
        self.table.setColumnWidth(4, 70)   # 客户
        self.table.setColumnWidth(5, 90)   # 手机
        self.table.setColumnWidth(7, 70)   # 设计师
        self.table.setColumnWidth(8, 70)   # 状态
        self.table.setColumnWidth(9, 90)   # 最后修改
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(6, QHeaderView.ResizeMode.Stretch)  # 地址列拉伸
        return self.table

    # ---------------- 右侧侧栏 ----------------
    def _build_side_panel(self) -> QWidget:
        side = QWidget()
        side.setFixedWidth(280)
        layout = QVBoxLayout(side)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(8)

        layout.addWidget(self._build_filter_box())

        # 备注 / 日志区
        self.edit_remark = QTextEdit()
        self.edit_remark.setPlaceholderText("订单备注 / 日志...")
        self.edit_remark.setFixedHeight(160)
        layout.addWidget(self.edit_remark)

        # 操作按钮组
        layout.addLayout(self._build_action_buttons())

        layout.addStretch(1)

        # 红色提示
        self.lbl_warning = QLabel("1、提交下单或同步云端只能是自己的订单")
        self.lbl_warning.setStyleSheet(f"color:{WARN_COLOR}; font-size:12px;")
        self.lbl_warning.setWordWrap(True)
        layout.addWidget(self.lbl_warning)

        return side

    # ---------------- 右侧 - 筛选区 ----------------
    def _build_filter_box(self) -> QFrame:
        box = QFrame()
        box.setObjectName("filterBox")
        f = QVBoxLayout(box)
        f.setContentsMargins(10, 10, 10, 12)
        f.setSpacing(8)

        today = QDate(date.today().year, date.today().month, date.today().day)

        # 文件日期
        row_start = QHBoxLayout()
        self.chk_enable_date = QCheckBox("文件日期")
        self.chk_enable_date.setChecked(True)
        row_start.addWidget(self.chk_enable_date)
        self.edit_date_start = QDateEdit(today.addDays(-30))
        self.edit_date_start.setDisplayFormat("yyyy年 M月d日")
        self.edit_date_start.setCalendarPopup(True)
        self.edit_date_start.setFixedWidth(140)
        row_start.addWidget(self.edit_date_start)
        f.addLayout(row_start)

        # 结束日期
        row_end = QHBoxLayout()
        lbl_end = QLabel("结束日期")
        lbl_end.setFixedWidth(70)
        row_end.addWidget(lbl_end)
        self.edit_date_end = QDateEdit(today)
        self.edit_date_end.setDisplayFormat("yyyy年 M月d日")
        self.edit_date_end.setCalendarPopup(True)
        self.edit_date_end.setFixedWidth(140)
        row_end.addWidget(self.edit_date_end)
        f.addLayout(row_end)

        # 关键字
        row_keyword = QHBoxLayout()
        lbl_kw = QLabel("关键字")
        lbl_kw.setFixedWidth(70)
        row_keyword.addWidget(lbl_kw)
        self.edit_keyword = QLineEdit()
        self.edit_keyword.setFixedWidth(140)
        row_keyword.addWidget(self.edit_keyword)
        f.addLayout(row_keyword)

        # 文件状态
        row_status = QHBoxLayout()
        lbl_st = QLabel("文件状态")
        lbl_st.setFixedWidth(70)
        row_status.addWidget(lbl_st)
        self.combo_status = QComboBox()
        self.combo_status.addItems(["全部", "设计中", "已拆单", "已下单", "已完成", "已取消"])
        self.combo_status.setFixedWidth(140)
        row_status.addWidget(self.combo_status)
        f.addLayout(row_status)

        # 查找按钮
        self.btn_search = QPushButton("查找订单")
        self.btn_search.setObjectName("primaryButton")
        self.btn_search.setFixedHeight(36)
        self.btn_search.setCursor(Qt.CursorShape.PointingHandCursor)
        f.addWidget(self.btn_search)

        # 启用/禁用日期联动
        self.chk_enable_date.toggled.connect(self.edit_date_start.setEnabled)
        self.chk_enable_date.toggled.connect(self.edit_date_end.setEnabled)
        return box

    # ---------------- 右侧 - 操作按钮 ----------------
    def _build_action_buttons(self) -> QHBoxLayout:
        row = QHBoxLayout()
        row.setSpacing(6)

        self.btn_open   = QPushButton("打开订单")
        self.btn_submit = QPushButton("提交下单")
        self.btn_delete = QPushButton("删除订单")
        for btn in (self.btn_open, self.btn_submit, self.btn_delete):
            btn.setFixedHeight(34)
            btn.setObjectName("actionButton")
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            row.addWidget(btn, 1)
        return row

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
                padding: 6px 18px;
                margin-right: 2px;
                min-width: 90px;
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

            /* —— 订单表 —— */
            QTableWidget {{
                background: #ffffff;
                gridline-color: #e4e7ed;
                border: 1px solid #dcdfe6;
                selection-background-color: #ecf5ff;
                selection-color: #303133;
                font-size: 13px;
            }}
            QTableWidget::item {{ padding: 4px 6px; }}
            QHeaderView::section {{
                background-color: #f5f7fa;
                color: #303133;
                padding: 6px 4px;
                border: none;
                border-right: 1px solid #e4e7ed;
                border-bottom: 1px solid #dcdfe6;
                font-weight: bold;
            }}

            /* —— 筛选框 —— */
            QFrame#filterBox {{
                background: #ffffff;
                border: 1px solid #dcdfe6;
                border-radius: 3px;
            }}
            QLineEdit, QComboBox, QDateEdit, QTextEdit {{
                border: 1px solid #dcdfe6;
                border-radius: 3px;
                padding: 3px 6px;
                background: #ffffff;
                selection-background-color: {PRIMARY_COLOR};
            }}
            QLineEdit:focus, QComboBox:focus, QDateEdit:focus, QTextEdit:focus {{
                border: 1px solid {PRIMARY_COLOR};
            }}
            QDateEdit:disabled {{
                background: #f5f7fa;
                color: #c0c4cc;
            }}
            QComboBox::drop-down {{
                border: none;
                width: 20px;
            }}
            QLabel {{ color: #303133; }}

            /* —— 复选框 —— */
            QCheckBox {{ color: #303133; spacing: 6px; }}
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

            /* —— 主按钮 (查找订单) —— */
            QPushButton#primaryButton {{
                background-color: {PRIMARY_COLOR};
                color: #ffffff;
                border: 1px solid {PRIMARY_COLOR};
                border-radius: 3px;
                font-size: 14px;
                font-weight: bold;
            }}
            QPushButton#primaryButton:hover {{
                background-color: {PRIMARY_COLOR_HOVER};
                border-color: {PRIMARY_COLOR_HOVER};
            }}

            /* —— 操作按钮 —— */
            QPushButton#actionButton {{
                background-color: #ffffff;
                color: #303133;
                border: 1px solid #dcdfe6;
                border-radius: 3px;
            }}
            QPushButton#actionButton:hover {{
                background-color: {PRIMARY_COLOR};
                color: #ffffff;
                border-color: {PRIMARY_COLOR};
            }}
            QPushButton#actionButton:pressed {{
                background-color: {PRIMARY_COLOR_HOVER};
                border-color: {PRIMARY_COLOR_HOVER};
            }}
        """)

    # ---------------------------------------------------------------- 信号
    def _connect_local_signals(self):
        self.btn_search.clicked.connect(self._on_search)
        self.btn_open.clicked.connect(self._on_open)
        self.btn_submit.clicked.connect(self._on_submit)
        self.btn_delete.clicked.connect(self._on_delete)
        # 双击行 = 打开订单
        self.table.cellDoubleClicked.connect(lambda r, c: self._on_open())

    # ---------------- 操作处理 ----------------
    def _on_search(self):
        self.search_requested.emit(self.get_filters())

    def _on_open(self):
        ids = self.get_selected_order_ids()
        if not ids:
            self.lbl_warning.setText("请先勾选要打开的订单！")
            self.lbl_warning.setStyleSheet(f"color:{WARN_COLOR}; font-size:12px;")
            return
        self.open_requested.emit(ids)

    def _on_submit(self):
        ids = self.get_selected_order_ids()
        if not ids:
            self.lbl_warning.setText("请先勾选要提交的订单！")
            return
        self.submit_requested.emit(ids)

    def _on_delete(self):
        ids = self.get_selected_order_ids()
        if not ids:
            self.lbl_warning.setText("请先勾选要删除的订单！")
            return
        # 删除前从表格里移除（业务层确认成功后由 controller 调用 set_orders 刷新）
        self.delete_requested.emit(ids)
        self._remove_rows_by_order_ids(ids)

    # ---------------------------------------------------------------- 对外接口
    def set_orders(self, orders: list[tuple]):
        """填充订单列表。

        orders: [(订单号, 门店, 客户, 手机, 地址, 设计师, 状态, 最后修改), ...]
        """
        self.table.setRowCount(len(orders))
        for r, row in enumerate(orders):
            # 第 0 列：复选框
            self._set_check_cell(r, 0)
            # 第 1 列：序号（只读，居中）
            self._set_text(r, 1, str(r + 1), center=True, readonly=True)
            # 第 2 ~ 9 列：业务字段（订单号, 门店, 客户, 手机, 地址, 设计师, 状态, 最后修改）
            for offset, value in enumerate(row):
                self._set_text(r, 2 + offset, value, readonly=True)

    def get_selected_order_ids(self) -> list[str]:
        """返回所有"勾选了复选框"的订单号列表。"""
        ids = []
        for r in range(self.table.rowCount()):
            chk = self._row_checkbox(r)
            if chk is not None and chk.isChecked():
                item = self.table.item(r, 2)
                if item:
                    ids.append(item.text())
        return ids

    def get_filters(self) -> dict:
        """收集当前筛选条件。"""
        return {
            "use_date":   self.chk_enable_date.isChecked(),
            "date_start": self.edit_date_start.date().toString("yyyy-MM-dd"),
            "date_end":   self.edit_date_end.date().toString("yyyy-MM-dd"),
            "keyword":    self.edit_keyword.text().strip(),
            "status":     self.combo_status.currentText(),
        }

    # ---------------------------------------------------------------- 单元格构造
    def _set_check_cell(self, row: int, col: int):
        container = QWidget()
        h = QHBoxLayout(container)
        h.setContentsMargins(0, 0, 0, 0)
        chk = QCheckBox()
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
        container.checkbox = chk
        self.table.setCellWidget(row, col, container)

    def _set_text(self, row: int, col: int, text: str,
                  center: bool = False, readonly: bool = False):
        item = QTableWidgetItem(str(text) if text is not None else "")
        if center:
            item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        if readonly:
            item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
        self.table.setItem(row, col, item)

    def _row_checkbox(self, row: int) -> QCheckBox | None:
        widget = self.table.cellWidget(row, 0)
        if widget is None:
            return None
        return getattr(widget, "checkbox", None)

    def _remove_rows_by_order_ids(self, order_ids: list[str]):
        """从表格中移除指定订单号的行。"""
        for r in range(self.table.rowCount() - 1, -1, -1):
            item = self.table.item(r, 2)
            if item and item.text() in order_ids:
                self.table.removeRow(r)
        # 重排序号列
        for r in range(self.table.rowCount()):
            seq = self.table.item(r, 1)
            if seq:
                seq.setText(str(r + 1))
