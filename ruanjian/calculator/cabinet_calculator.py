# -*- coding: utf-8 -*-
"""柜体算料总调度器

文件路径：
    calculator/cabinet_calculator.py

职责：
    接收一个柜体设计对象（Cabinet），依次调用各子计算器，
    汇总成一份完整的 BOM（Bill of Materials）返回。

调用示例::

    from calculator.cabinet_calculator import CabinetCalculator

    calc = CabinetCalculator(cabinet)
    bom  = calc.calculate()

    # 传给 UI
    dlg.set_order_data(bom.to_order_data())

    # 导出
    bom.to_excel("output.xlsx")
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List


# ──────────────────────────────────────────────────────────────────────────────
# 数据模型（轻量，正式项目建议移到 bom_engine/models/）
# ──────────────────────────────────────────────────────────────────────────────

@dataclass
class PanelRow:
    """单块板件行。"""
    name:             str   = ""       # 名称，如"左侧板"
    material:         str   = ""       # 材料/型号，如"耕耘农夫"
    spec:             float = 18.0     # 规格/厚度(mm)
    size:             str   = ""       # 原始尺寸，如"600×1000"
    cut_size:         str   = ""       # 开料尺寸，如"598.1×998.2"
    qty:              float = 1.0      # 数量
    process_desc:     str   = ""       # 工艺描述，如"双面贴皮"
    edge_deduction:   str   = ""       # 封边扣减，如"四边-1.9"
    production_type:  str   = ""       # 生产类型，如"数控开料"
    remark:           str   = ""       # 备注说明


@dataclass
class HardwareRow:
    """单条五金件行。"""
    name:     str   = ""        # 名称，如"三合一"
    model:    str   = ""        # 型号
    spec:     str   = ""        # 规格
    qty:      float = 1.0       # 数量


@dataclass
class EdgeRow:
    """封边行。"""
    material:  str   = ""       # 封边材料
    thickness: float = 0.0      # 厚度(mm)，如 1.0 / 0.9
    length:    float = 0.0      # 总长(m)


@dataclass
class BOM:
    """单个产品的完整物料清单。"""
    product_name: str              = ""
    panels:       List[PanelRow]   = field(default_factory=list)
    edges:        List[EdgeRow]    = field(default_factory=list)
    hardware:     List[HardwareRow]= field(default_factory=list)

    # ── 转为 UI 所需的行列表（bom_parse_dialog 格式）─────────────────
    def to_bom_rows(self) -> list[dict]:
        """返回可直接传给 BomParseDialog._load_bom() 的行列表。"""
        rows: list[dict] = []

        for p in self.panels:
            rows.append({
                "name":            p.name,
                "material":        p.material,
                "spec":            p.spec,
                "size":            p.size,
                "cut_size":        p.cut_size,
                "qty":             p.qty,
                "process_desc":    p.process_desc,
                "edge_deduction":  p.edge_deduction,
                "production_type": p.production_type,
                "remark":          p.remark,
            })

        for e in self.edges:
            rows.append({
                "name":            "封边",
                "material":        e.material,
                "spec":            e.thickness,
                "size":            "",
                "cut_size":        "",
                "qty":             round(e.length, 3),
                "process_desc":    "",
                "edge_deduction":  "",
                "production_type": "",
                "remark":          "",
            })

        for h in self.hardware:
            rows.append({
                "name":            h.name,
                "material":        h.model,
                "spec":            h.spec,
                "size":            "",
                "cut_size":        "",
                "qty":             h.qty,
                "process_desc":    "",
                "edge_deduction":  "",
                "production_type": "",
                "remark":          "",
            })

        return rows

    def to_order_data(self, room: str = "房间_0", order_id: str = "") -> dict:
        """转为 BomParseDialog.set_order_data() 接受的格式。"""
        return {
            "order_id": order_id,
            "customer": "",
            "products": [
                {
                    "room": room,
                    "items": [
                        {
                            "name": self.product_name,
                            "size": "",
                            "qty":  1,
                            "bom":  self.to_bom_rows(),
                        }
                    ],
                }
            ],
        }


# ──────────────────────────────────────────────────────────────────────────────
# 子计算器（占位，后续在各自文件里实现）
# ──────────────────────────────────────────────────────────────────────────────

class PanelCalculator:
    """板件计算器。

    TODO: 根据柜体宽高深、板件厚度，计算每块板件的净尺寸和开料尺寸。
    """

    def run(self, cabinet) -> list[PanelRow]:
        """
        Parameters
        ----------
        cabinet : Cabinet
            柜体设计对象（来自 bom_engine/models/cabinet.py）

        Returns
        -------
        list[PanelRow]
        """
        # ── 占位实现，返回空列表 ──────────────────────────────────────
        # 正式实现示例：
        #   w, h, d = cabinet.width, cabinet.height, cabinet.depth
        #   t = cabinet.panel_thickness          # 板厚，默认 18mm
        #   margin = 1.9                         # 封边余量
        #   panels = [
        #       PanelRow("左侧板", cabinet.material, t,
        #                f"{d}×{h}", f"{d-margin}×{h-margin}"),
        #       PanelRow("右侧板", cabinet.material, t,
        #                f"{d}×{h}", f"{d-margin}×{h-margin}"),
        #       ...
        #   ]
        #   return panels
        return []


class HardwareCalculator:
    """五金件计算器。

    TODO: 根据门扇数量、抽屉数量等计算铰链、导轨、拉手等。
    """

    def run(self, cabinet) -> list[HardwareRow]:
        return []


class EdgeCalculator:
    """封边计算器。

    TODO: 遍历所有板件，统计各厚度封边的总长度。
    """

    def run(self, panels: list[PanelRow]) -> list[EdgeRow]:
        return []


# ──────────────────────────────────────────────────────────────────────────────
# 主调度器
# ──────────────────────────────────────────────────────────────────────────────

class CabinetCalculator:
    """柜体算料总调度器。

    Parameters
    ----------
    cabinet : Cabinet
        柜体设计对象。

    Examples
    --------
    >>> calc = CabinetCalculator(cabinet)
    >>> bom  = calc.calculate()
    >>> rows = bom.to_bom_rows()          # 传给物料表
    >>> data = bom.to_order_data()        # 传给 BomParseDialog
    """

    def __init__(self, cabinet):
        self.cabinet          = cabinet
        self._panel_calc      = PanelCalculator()
        self._hardware_calc   = HardwareCalculator()
        self._edge_calc       = EdgeCalculator()

    def calculate(self) -> BOM:
        """执行完整算料流程，返回 BOM。"""

        # 1. 板件计算
        panels = self._panel_calc.run(self.cabinet)

        # 2. 五金件计算
        hardware = self._hardware_calc.run(self.cabinet)

        # 3. 封边计算（依赖板件结果）
        edges = self._edge_calc.run(panels)

        # 4. 汇总
        bom = BOM(
            product_name = getattr(self.cabinet, "name", "未命名柜体"),
            panels       = panels,
            edges        = edges,
            hardware     = hardware,
        )

        return bom


# ==============================================================================
# 物料解析对话框（UI + 算料逻辑合一）
# ==============================================================================
from PySide6.QtCore import Qt, QDate, Signal
from PySide6.QtGui import QFont

from ui.qt_lifecycle import safe_set_font_size
from PySide6.QtWidgets import (
    QDialog, QHBoxLayout, QVBoxLayout, QLabel, QPushButton,
    QToolButton, QMenu, QTabWidget, QTreeWidget, QTreeWidgetItem,
    QTableWidget, QTableWidgetItem, QHeaderView, QCheckBox,
    QDateEdit, QWidget, QSplitter, QAbstractItemView, QStackedWidget,
)

# View3D 3D 预览组件（懒导入，避免无 OpenGL 环境报错）
try:
    from ui.main_window.view_3d import View3D as _View3D
except ImportError:
    _View3D = None

_TOOLBAR_STYLE = """
QWidget#bomToolBar {
    background: #f0f0f0;
    border-bottom: 1px solid #c8c8c8;
}
QPushButton, QToolButton {
    background: #e8e8e8;
    border: 1px solid #b8b8b8;
    border-radius: 3px;
    padding: 4px 10px;
    font-size: 13px;
    color: #222;
    min-height: 26px;
}
QPushButton:hover, QToolButton:hover { background: #d8eaf8; border-color: #7ab0d8; }
QPushButton:pressed, QToolButton:pressed { background: #c0d8f0; }
"""
_TREE_STYLE = """
QTreeWidget { background:#fff; border:1px solid #c8c8c8; font-size:12px; }
QTreeWidget::item:selected { background:#cce5ff; color:#000; }
"""
_TAB_STYLE = """
QTabWidget::pane { border:1px solid #c8c8c8; background:#fff; }
QTabBar::tab {
    background:#e8e8e8; border:1px solid #c8c8c8; border-bottom:none;
    padding:4px 18px; font-size:13px; min-width:60px;
}
QTabBar::tab:selected { background:#fff; border-top:2px solid #4a90d9; font-weight:bold; }
QTabBar::tab:hover:!selected { background:#d8eaf8; }
"""
_TABLE_STYLE = """
QTableWidget { background:#fff; gridline-color:#d0d0d0; font-size:12px; border:none; }
QHeaderView::section {
    background:#f2f2f2; border:1px solid #d0d0d0;
    padding:4px 6px; font-size:12px; font-weight:bold; color:#333;
}
QTableWidget::item:selected { background:#cce5ff; color:#000; }
"""
_BOTTOM_STYLE = """
QWidget#bomBottomBar { background:#f0f0f0; border-top:1px solid #c8c8c8; }
QLabel { font-size:12px; color:#333; }
QDateEdit { background:#fff; border:1px solid #b8b8b8; border-radius:2px;
            padding:2px 4px; font-size:12px; }
"""
_ORDER_ID_STYLE = "color:#d04040; font-size:13px; font-weight:bold;"
_DELETE_BTN_STYLE = """
QPushButton {
    background:#e8e8e8; border:1px solid #b8b8b8; border-radius:3px;
    padding:4px 14px; font-size:13px; color:#222; min-height:26px;
}
QPushButton:hover { background:#fde8e8; border-color:#d04040; color:#d04040; }
"""

_DEMO_DATA = {
    "order_id": "2605006",
    "customer": "",
    "products": [
        {
            "room": "\u623f\u95f4_0",
            "items": [
                {
                    "name": "\u4fa7\u5305\u9876\u5e95(\u6709\u8e22\u811a)",
                    "size": "600*1000*600",
                    "qty": 1,
                    "bom": [
                        {"name": "\u5de6\u4fa7\u677f",  "material": "\u8015\u8012\u519c\u592b", "spec": 18,  "size": "600\u00d71000", "cut_size": "598.1\u00d7998.2", "qty": 1, "process_desc": "\u53cc\u9762\u8d34\u76ae", "edge_deduction": "\u56db\u8fb9-1.9", "production_type": "\u6570\u63a7\u5f00\u6599", "remark": ""},
                        {"name": "\u53f3\u4fa7\u677f",  "material": "\u8015\u8012\u519c\u592b", "spec": 18,  "size": "600\u00d71000", "cut_size": "598.1\u00d7998.2", "qty": 1, "process_desc": "\u53cc\u9762\u8d34\u76ae", "edge_deduction": "\u56db\u8fb9-1.9", "production_type": "\u6570\u63a7\u5f00\u6599", "remark": ""},
                        {"name": "\u9876\u677f",    "material": "\u8015\u8012\u519c\u592b", "spec": 18,  "size": "600\u00d7564",  "cut_size": "598.1\u00d7562.2", "qty": 1, "process_desc": "\u53cc\u9762\u8d34\u76ae", "edge_deduction": "\u56db\u8fb9-1.9", "production_type": "\u6570\u63a7\u5f00\u6599", "remark": ""},
                        {"name": "\u5e95\u677f",    "material": "\u8015\u8012\u519c\u592b", "spec": 18,  "size": "600\u00d7564",  "cut_size": "598.1\u00d7562.2", "qty": 1, "process_desc": "\u53cc\u9762\u8d34\u76ae", "edge_deduction": "\u56db\u8fb9-1.9", "production_type": "\u6570\u63a7\u5f00\u6599", "remark": ""},
                        {"name": "\u5c01\u8fb9",    "material": "\u8015\u8012\u519c\u592b", "spec": 1,   "size": "", "cut_size": "", "qty": 3.13, "process_desc": "", "edge_deduction": "", "production_type": "\u5c01\u8fb9\u673a", "remark": ""},
                        {"name": "\u5c01\u8fb9",    "material": "\u8015\u8012\u519c\u592b", "spec": 0.9, "size": "", "cut_size": "", "qty": 7.93, "process_desc": "", "edge_deduction": "", "production_type": "\u5c01\u8fb9\u673a", "remark": ""},
                        {"name": "\u677f\u6750",    "material": "\u8015\u8012\u519c\u592b", "spec": 18,  "size": "", "cut_size": "", "qty": 1.877, "process_desc": "", "edge_deduction": "", "production_type": "", "remark": ""},
                        {"name": "\u4e09\u5408\u4e00",  "material": "",  "spec": "", "size": "", "cut_size": "", "qty": 12, "process_desc": "", "edge_deduction": "", "production_type": "\u91c7\u8d2d", "remark": ""},
                    ],
                }
            ],
        }
    ],
}


class BomParseDialog(QDialog):
    """订单物料解析对话框。

    用法::
        from calculator.cabinet_calculator import BomParseDialog
        dlg = BomParseDialog(order_data=..., parent=self)
        dlg.exec()
    """

    sig_save        = Signal()
    sig_production  = Signal()
    sig_export_xml  = Signal()
    sig_export_dxf  = Signal()
    sig_optimize    = Signal()
    sig_modify_base = Signal()
    sig_delete      = Signal()

    def __init__(self, order_data=None, parent=None):
        super().__init__(parent)
        self._order_data = order_data or _DEMO_DATA
        self.setWindowTitle("\u8ba2\u5355\u7269\u6599\u89e3\u6790")
        self.resize(1020, 700)
        self._build_ui()
        self._populate_tree()
        self._connect_signals()

    # ── 构建 UI ───────────────────────────────────────────────────
    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        root.addWidget(self._build_toolbar())
        root.addWidget(self._build_body(), stretch=1)
        root.addWidget(self._build_bottom_bar())

    def _build_toolbar(self):
        bar = QWidget()
        bar.setObjectName("bomToolBar")
        bar.setStyleSheet(_TOOLBAR_STYLE)
        bar.setFixedHeight(44)
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(8, 6, 8, 6)
        layout.setSpacing(4)

        self.btn_save       = QPushButton("\u4fdd\u5b58\u8fd4\u56de")
        self.btn_production = QPushButton("\u751f\u4ea7\u89e3\u6790")

        self.btn_export_prod = QToolButton()
        self.btn_export_prod.setText("\u751f\u4ea7\u5bfc\u51fa  \u25bc")
        self.btn_export_prod.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        m1 = QMenu(self)
        m1.addAction("\u5bfc\u51fa\u5168\u90e8")
        m1.addAction("\u5bfc\u51fa\u9009\u4e2d")
        self.btn_export_prod.setMenu(m1)

        self.btn_xml = QPushButton("\u5bfc\u51fa.xml")
        self.btn_dxf = QPushButton("\u5bfc\u51fa.dxf")

        self.btn_print = QToolButton()
        self.btn_print.setText("\u6253\u5370\u6599\u5355  \u25bc")
        self.btn_print.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        m2 = QMenu(self)
        m2.addAction("\u6253\u5370\u5168\u90e8")
        m2.addAction("\u6253\u5370\u9009\u4e2d")
        self.btn_print.setMenu(m2)

        self.btn_user_bom   = QPushButton("\u7528\u6237\u6599\u5355")
        self.btn_optimize   = QPushButton("\u4f18\u5316\u751f\u4ea7")
        self.btn_modify_mat = QPushButton("\u57fa\u6750\u4fee\u6539")

        for w in [
            self.btn_save, self.btn_production, self.btn_export_prod,
            self.btn_xml, self.btn_dxf, self.btn_print,
            self.btn_user_bom, self.btn_optimize, self.btn_modify_mat,
        ]:
            layout.addWidget(w)
        layout.addStretch(1)
        return bar

    def _build_body(self):
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setHandleWidth(4)

        # 左：产品列表
        left = QWidget()
        ll = QVBoxLayout(left)
        ll.setContentsMargins(6, 6, 0, 6)
        ll.setSpacing(4)

        tab_lbl = QLabel("\u4ea7\u54c1\u5217\u8868")
        tab_lbl.setFixedHeight(28)
        tab_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        tab_lbl.setStyleSheet(
            "background:#e0e8f5; border:1px solid #b0c8e8; border-radius:3px;"
            "font-size:13px; font-weight:bold; color:#1a5fa8;"
        )
        ll.addWidget(tab_lbl)

        self.tree = QTreeWidget()
        self.tree.setHeaderHidden(True)
        self.tree.setStyleSheet(_TREE_STYLE)
        self.tree.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        ll.addWidget(self.tree, stretch=1)

        self.btn_audit = QPushButton("\u4ea7\u54c1\u5ba1\u6838\u68c0\u9a8c")
        self.btn_audit.setFixedHeight(32)
        self.btn_audit.setStyleSheet(
            "QPushButton{background:#e8e8e8;border:1px solid #b8b8b8;"
            "border-radius:3px;font-size:13px;color:#222;}"
            "QPushButton:hover{background:#d8eaf8;}"
        )
        ll.addWidget(self.btn_audit)
        splitter.addWidget(left)

        # 右：Tab
        right = QWidget()
        rl = QVBoxLayout(right)
        rl.setContentsMargins(0, 6, 6, 0)
        rl.setSpacing(0)

        info_bar = QWidget()
        il = QHBoxLayout(info_bar)
        il.setContentsMargins(0, 0, 4, 4)
        il.setSpacing(8)
        il.addStretch(1)
        il.addWidget(QLabel("\u5ba2\u6237\u540d\u79f0\uff1a"))
        self.lbl_customer = QLabel(self._order_data.get("customer", ""))
        il.addWidget(self.lbl_customer)
        il.addWidget(QLabel("\u8ba2\u5355\u7f16\u53f7\uff1a"))
        self.lbl_order_id = QLabel(self._order_data.get("order_id", ""))
        self.lbl_order_id.setStyleSheet(_ORDER_ID_STYLE)
        il.addWidget(self.lbl_order_id)
        rl.addWidget(info_bar)

        self.tab_widget = QTabWidget()
        self.tab_widget.setStyleSheet(_TAB_STYLE)
        self.bom_table = self._build_bom_table()
        self.tab_widget.addTab(self.bom_table, "\u7269\u6599\u8868")

        # ── 审核图 Tab：包含"加载 3D 视图"按钮 + View3D ──────────────
        self._review_tab = QWidget()
        review_layout = QVBoxLayout(self._review_tab)
        review_layout.setContentsMargins(0, 0, 0, 0)
        review_layout.setSpacing(0)

        # 顶部操作栏
        review_bar = QWidget()
        review_bar.setFixedHeight(38)
        review_bar.setStyleSheet(
            "background:#f5f7fa; border-bottom:1px solid #d0d0d0;"
        )
        rb_layout = QHBoxLayout(review_bar)
        rb_layout.setContentsMargins(8, 4, 8, 4)
        rb_layout.setSpacing(8)
        self.btn_load_3d = QPushButton("\u52a0\u8f7d 3D \u89c6\u56fe")
        self.btn_load_3d.setFixedWidth(110)
        self.btn_load_3d.setStyleSheet(
            "QPushButton{background:#4a90d9;border:none;border-radius:3px;"
            "padding:4px 12px;font-size:13px;color:#fff;min-height:26px;}"
            "QPushButton:hover{background:#357abd;}"
            "QPushButton:pressed{background:#2a6099;}"
            "QPushButton:disabled{background:#b0c8e8;color:#e8f0fa;}"
        )
        self.lbl_3d_hint = QLabel("\u70b9\u51fb\u6309\u94ae\u52a0\u8f7d\u5f53\u524d\u4ea7\u54c1 3D \u9884\u89c8")
        self.lbl_3d_hint.setStyleSheet("color:#888; font-size:12px;")
        rb_layout.addWidget(self.btn_load_3d)
        rb_layout.addWidget(self.lbl_3d_hint)
        rb_layout.addStretch(1)
        review_layout.addWidget(review_bar)

        # 内容区：QStackedWidget 在"占位页"和"3D 视图页"之间切换
        self._review_stack = QStackedWidget()

        # 页0：占位提示
        placeholder = QLabel("\u6682\u65e0 3D \u6570\u636e\uff0c\u8bf7\u70b9\u51fb\u300a\u52a0\u8f7d 3D \u89c6\u56fe\u300b")
        placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        placeholder.setStyleSheet("color:#aaa; font-size:14px;")
        self._review_stack.addWidget(placeholder)   # index 0

        # 页1：View3D（延迟创建，避免 OpenGL 上下文问题）
        self._view3d: "View3D | None" = None        # index 1（首次点击时插入）

        review_layout.addWidget(self._review_stack, stretch=1)
        self.tab_widget.addTab(self._review_tab, "\u5ba1\u6838\u56fe")
        rl.addWidget(self.tab_widget, stretch=1)
        splitter.addWidget(right)

        splitter.setSizes([300, 700])
        return splitter

    def _build_bom_table(self):
        headers = ["\u5e8f\u53f7", "\u540d\u79f0", "\u6750\u6599/\u578b\u53f7",
                   "\u89c4\u683c/D", "\u5c3a\u5bf8/\u5bbd\u957f", "\u5f00\u6599/\u5bbd\u957f", "\u6570\u91cf",
                   "\u5de5\u827a\u63cf\u8ff0", "\u5c01\u8fb9\u625c\u51cf", "\u751f\u4ea7\u7c7b\u578b", "\u5907\u6ce8\u8bf4\u660e"]
        tbl = QTableWidget(0, len(headers))
        tbl.setHorizontalHeaderLabels(headers)
        tbl.setStyleSheet(_TABLE_STYLE)
        tbl.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        tbl.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        tbl.verticalHeader().setVisible(False)
        for i, w in enumerate([44, 110, 100, 60, 100, 110, 60, 100, 80, 90, 100]):
            tbl.setColumnWidth(i, w)
        tbl.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        return tbl

    def _build_bottom_bar(self):
        bar = QWidget()
        bar.setObjectName("bomBottomBar")
        bar.setFixedHeight(38)
        bar.setStyleSheet(_BOTTOM_STYLE)
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(8, 4, 8, 4)
        layout.setSpacing(6)

        layout.addWidget(QLabel("\u4ea4\u8d27\u65e5\u671f\uff1a"))
        self.date_edit = QDateEdit(QDate.currentDate())
        self.date_edit.setDisplayFormat("yyyy\u5e74 M\u6708d\u65e5")
        self.date_edit.setCalendarPopup(True)
        self.date_edit.setFixedWidth(140)
        layout.addWidget(self.date_edit)
        layout.addSpacing(12)

        self.chk_irregular = QCheckBox("\u5f02\u5f62\u6807\u8bb0")
        self.chk_irregular.setStyleSheet("font-size:12px;")
        dot = QLabel("\u25cf")
        dot.setStyleSheet("color:#d04040; font-size:14px;")
        layout.addWidget(self.chk_irregular)
        layout.addWidget(dot)
        layout.addStretch(1)

        self.btn_delete = QPushButton("\u5220  \u9664")
        self.btn_delete.setFixedWidth(70)
        self.btn_delete.setStyleSheet(_DELETE_BTN_STYLE)
        layout.addWidget(self.btn_delete)
        return bar

    # ── 数据 ──────────────────────────────────────────────────────
    def _populate_tree(self):
        self.tree.clear()
        for room_data in self._order_data.get("products", []):
            room_item = QTreeWidgetItem(["\u25a1 " + room_data.get("room", "\u623f\u95f4")])
            _hdr_font = QFont()
            safe_set_font_size(_hdr_font, 11)
            _hdr_font.setBold(True)
            room_item.setFont(0, _hdr_font)
            self.tree.addTopLevelItem(room_item)
            for prod in room_data.get("items", []):
                label = "\u25a1 {}  /  {}  =  {}".format(
                    prod.get("name", ""), prod.get("size", ""), prod.get("qty", 1)
                )
                prod_item = QTreeWidgetItem([label])
                prod_item.setData(0, Qt.ItemDataRole.UserRole, prod)
                room_item.addChild(prod_item)
            room_item.setExpanded(True)

        root = self.tree.invisibleRootItem()
        if root.childCount() > 0:
            first_room = root.child(0)
            if first_room.childCount() > 0:
                first_prod = first_room.child(0)
                self.tree.setCurrentItem(first_prod)
                self._load_bom(first_prod.data(0, Qt.ItemDataRole.UserRole))

    def _load_bom(self, prod):
        tbl = self.bom_table
        tbl.setRowCount(0)
        for i, row in enumerate(prod.get("bom", [])):
            tbl.insertRow(i)
            for col, val in enumerate([
                str(i + 1),
                row.get("name", ""),
                row.get("material", ""),
                str(row.get("spec", "")),
                row.get("size", ""),
                row.get("cut_size", ""),
                str(row.get("qty", "")),
                row.get("process_desc", ""),
                row.get("edge_deduction", ""),
                row.get("production_type", ""),
                row.get("remark", ""),
            ]):
                item = QTableWidgetItem(val)
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                tbl.setItem(i, col, item)
        tbl.resizeRowsToContents()

    def _connect_signals(self):
        self.tree.currentItemChanged.connect(self._on_tree_changed)
        self.btn_save.clicked.connect(self.sig_save)
        self.btn_production.clicked.connect(self.sig_production)
        self.btn_xml.clicked.connect(self.sig_export_xml)
        self.btn_dxf.clicked.connect(self.sig_export_dxf)
        self.btn_optimize.clicked.connect(self.sig_optimize)
        self.btn_modify_mat.clicked.connect(self.sig_modify_base)
        self.btn_delete.clicked.connect(self.sig_delete)
        self.btn_load_3d.clicked.connect(self._on_load_3d)

    def _on_tree_changed(self, current, _prev):
        if current:
            prod = current.data(0, Qt.ItemDataRole.UserRole)
            if prod:
                self._load_bom(prod)

    def set_order_data(self, order_data):
        self._order_data = order_data
        self.lbl_customer.setText(order_data.get("customer", ""))
        self.lbl_order_id.setText(order_data.get("order_id", ""))
        self._populate_tree()

    # ── 审核图：加载 3D 视图 ───────────────────────────────────────
    def _on_load_3d(self):
        """点击「加载 3D 视图」按钮时调用。

        首次调用时创建 View3D 并插入到 QStackedWidget 的 index 1；
        之后再次点击只刷新相机适配。
        如果 View3D 无法导入（无 OpenGL 环境），显示友好提示。
        """
        if _View3D is None:
            self.lbl_3d_hint.setText(
                "\u5f53\u524d\u73af\u5883\u4e0d\u652f\u6301 OpenGL\uff0c\u65e0\u6cd5\u52a0\u8f7d 3D \u89c6\u56fe"
            )
            self.lbl_3d_hint.setStyleSheet("color:#d04040; font-size:12px;")
            return

        # 首次创建 View3D
        if self._view3d is None:
            self._view3d = _View3D(parent=self._review_stack)
            self._review_stack.addWidget(self._view3d)   # index 1

        # 尝试从当前选中产品中拿 Room 信息（若主窗口有注入则使用，否则传 None）
        room = getattr(self, "_current_room", None)
        self._view3d.set_room(room)

        # 切换到 3D 页
        self._review_stack.setCurrentIndex(1)
        self.btn_load_3d.setEnabled(False)
        self.btn_load_3d.setText("\u5df2\u52a0\u8f7d")
        self.lbl_3d_hint.setText(
            "\u5de6\u952e\u62d6\u52a8\u65cb\u8f6c\u00b7\u53f3\u952e\u5e73\u79fb\u00b7\u6eda\u8f6e\u7f29\u653e\u00b7\u53cc\u51fb\u91cd\u7f6e\u89c6\u89d2"
        )
        self.lbl_3d_hint.setStyleSheet("color:#555; font-size:12px;")

    def set_room(self, room) -> None:
        """主窗口可调用此方法同步房间数据到 3D 视图。

        Args:
            room: space_engine.room.Room 对象
        """
        self._current_room = room
        if self._view3d is not None:
            self._view3d.set_room(room)