
# -*- coding: utf-8 -*-
from PySide6.QtCore import Qt
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QFormLayout,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QMainWindow,
    QMenu,
    QMessageBox,
    QPushButton,
    QSplitter,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QToolBar,
    QToolButton,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)


class ProductStructureDialog(QDialog):
    """产品结构设计 / 参数模块编辑器"""

    def __init__(self, parent=None):
        super().__init__(parent)

        self.setWindowTitle("产品结构设计器")
        self.resize(1600, 900)

        self._build_ui()
        self._load_demo_data()

    # =========================================================
    # UI
    # =========================================================
    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(4, 4, 4, 4)
        root.setSpacing(4)

        # =====================================================
        # 顶部工具栏
        # =====================================================
        toolbar = self._build_toolbar()
        root.addWidget(toolbar)

        # =====================================================
        # 中央区域
        # =====================================================
        center_splitter = QSplitter(Qt.Horizontal)

        # 左侧
        left_widget = self._build_left_panel()
        center_splitter.addWidget(left_widget)

        # 中间
        middle_widget = self._build_middle_panel()
        center_splitter.addWidget(middle_widget)

        # 右侧
        right_widget = self._build_right_panel()
        center_splitter.addWidget(right_widget)

        center_splitter.setStretchFactor(0, 1)
        center_splitter.setStretchFactor(1, 4)
        center_splitter.setStretchFactor(2, 1)

        root.addWidget(center_splitter)

        # =====================================================
        # 底部区域
        # =====================================================
        bottom_widget = self._build_bottom_panel()
        root.addWidget(bottom_widget)

    # =========================================================
    # 顶部工具栏
    # =========================================================
    def _build_toolbar(self):
        toolbar = QToolBar()
        toolbar.setMovable(False)
        toolbar.setIconSize(toolbar.iconSize())

        actions = [
            "打开文件",
            "保存文件",
            "另存文件",
            "新建清除",
            "删除对象",
            "添加模块",
            "导入模块",
        ]

        for text in actions:
            action = QAction(text, self)
            toolbar.addAction(action)

        toolbar.addSeparator()

        check = QCheckBox("显示示意框")
        check.setChecked(True)
        toolbar.addWidget(check)

        return toolbar

    # =========================================================
    # 左侧结构树
    # =========================================================
    def _build_left_panel(self):
        panel = QGroupBox("文件结构")

        layout = QVBoxLayout(panel)

        self.tree = QTreeWidget()
        self.tree.setHeaderHidden(True)

        layout.addWidget(self.tree)

        return panel

    # =========================================================
    # 中间区域
    # =========================================================
    def _build_middle_panel(self):
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)

        # =========================================
        # 中间画布
        # =========================================
        preview_frame = QFrame()
        preview_frame.setFrameShape(QFrame.StyledPanel)
        preview_frame.setMinimumHeight(450)
        preview_frame.setStyleSheet(
            """
            QFrame {
                background: #f5f5f5;
                border: 1px solid #cfcfcf;
            }
            """
        )

        preview_layout = QVBoxLayout(preview_frame)

        lbl = QLabel("产品结构预览区域")
        lbl.setAlignment(Qt.AlignCenter)
        lbl.setStyleSheet(
            "font-size:18px;color:#999999;font-weight:bold;"
        )

        preview_layout.addWidget(lbl)

        layout.addWidget(preview_frame)

        return container

    # =========================================================
    # 右侧授权区域
    # =========================================================
    def _build_right_panel(self):
        panel = QGroupBox("授权设置")
        panel.setMaximumWidth(320)

        layout = QVBoxLayout(panel)

        form = QFormLayout()

        self.enable_checkbox = QCheckBox()
        form.addRow("启用授权：", self.enable_checkbox)

        self.version_edit = QLineEdit("2025.11")
        form.addRow("模块版本：", self.version_edit)

        self.contact_edit = QLineEdit()
        form.addRow("联系方式：", self.contact_edit)

        layout.addLayout(form)

        label = QLabel("授权账号&用户组：")
        layout.addWidget(label)

        self.auth_text = QTextEdit()
        layout.addWidget(self.auth_text)

        return panel

    # =========================================================
    # 底部区域
    # =========================================================
    def _build_bottom_panel(self):
        panel = QWidget()
        layout = QHBoxLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)

        # =====================================================
        # 左边参数编辑
        # =====================================================
        left_group = QWidget()
        left_layout = QVBoxLayout(left_group)

        # Tab
        tab = QTabWidget()

        tab.addTab(self._build_property_page(), "模块属性参数")
        tab.addTab(self._build_formula_page(), "模块结构公式")
        tab.addTab(self._build_material_page(), "解析物料测试")

        left_layout.addWidget(tab)

        layout.addWidget(left_group, 4)

        # =====================================================
        # 右边预设参数
        # =====================================================
        preset_group = QGroupBox("预设参数集")
        preset_group.setMaximumWidth(360)

        preset_layout = QVBoxLayout(preset_group)

        self.preset_text = QTextEdit()
        preset_layout.addWidget(self.preset_text)

        btn_layout = QHBoxLayout()

        self.collect_btn = QPushButton("收集当前参数到预设")
        self.clear_btn = QPushButton("清除")

        btn_layout.addWidget(self.collect_btn)
        btn_layout.addWidget(self.clear_btn)

        preset_layout.addLayout(btn_layout)

        layout.addWidget(preset_group, 1)

        return panel

    # =========================================================
    # 属性页
    # =========================================================
    def _build_property_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)

        # =========================================
        # 顶部输入
        # =========================================
        top_layout = QHBoxLayout()

        top_layout.addWidget(QLabel("产品名称："))
        self.product_name_edit = QLineEdit()
        top_layout.addWidget(self.product_name_edit)

        top_layout.addWidget(QLabel("系统类别："))
        self.category_combo = QComboBox()
        self.category_combo.addItems([
            "衣柜",
            "橱柜",
            "酒柜",
            "电视柜",
            "鞋柜",
        ])
        top_layout.addWidget(self.category_combo)

        top_layout.addWidget(QLabel("供货计价："))
        self.supply_combo = QComboBox()
        self.supply_combo.addItems(["展开", "投影"])
        top_layout.addWidget(self.supply_combo)

        top_layout.addWidget(QLabel("销售计价："))
        self.sale_combo = QComboBox()
        self.sale_combo.addItems(["展开", "投影"])
        top_layout.addWidget(self.sale_combo)

        layout.addLayout(top_layout)

        # =========================================
        # 下方双表格
        # =========================================
        table_layout = QHBoxLayout()

        # 左表
        self.spec_table = QTableWidget(0, 7)
        self.spec_table.setHorizontalHeaderLabels([
            "#",
            "型号",
            "W",
            "H",
            "D",
            "销售价",
            "供货价",
        ])

        self.spec_table.horizontalHeader().setStretchLastSection(True)
        self.spec_table.setSelectionBehavior(QAbstractItemView.SelectRows)

        table_layout.addWidget(self.spec_table, 2)

        # 右表
        self.param_table = QTableWidget(0, 2)
        self.param_table.setHorizontalHeaderLabels([
            "名称",
            "选项",
        ])

        self.param_table.horizontalHeader().setStretchLastSection(True)

        table_layout.addWidget(self.param_table, 2)

        layout.addLayout(table_layout)

        # =========================================
        # 按钮
        # =========================================
        btn_layout = QHBoxLayout()

        self.add_spec_btn = QPushButton("添加规格")
        self.del_spec_btn = QPushButton("删除")

        self.add_param_btn = QPushButton("添加参数")
        self.edit_param_btn = QPushButton("修改选中")
        self.del_param_btn = QPushButton("删除选中")

        btn_layout.addWidget(self.add_spec_btn)
        btn_layout.addWidget(self.del_spec_btn)
        btn_layout.addStretch()
        btn_layout.addWidget(self.add_param_btn)
        btn_layout.addWidget(self.edit_param_btn)
        btn_layout.addWidget(self.del_param_btn)

        layout.addLayout(btn_layout)

        return page

    # =========================================================
    # 结构公式页
    # =========================================================
    def _build_formula_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)

        self.formula_edit = QTextEdit()
        self.formula_edit.setPlaceholderText(
            "输入参数公式、柜体逻辑、尺寸约束..."
        )

        layout.addWidget(self.formula_edit)

        return page

    # =========================================================
    # 解析物料测试页
    # =========================================================
    def _build_material_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)

        self.material_test_edit = QTextEdit()
        self.material_test_edit.setPlaceholderText(
            "显示拆单后的板件、五金、封边、孔位数据..."
        )

        layout.addWidget(self.material_test_edit)

        return page

    # =========================================================
    # 测试数据
    # =========================================================
    def _load_demo_data(self):

        root1 = QTreeWidgetItem(["设计实例列表"])
        root2 = QTreeWidgetItem(["参数化模块组"])

        self.tree.addTopLevelItem(root1)
        self.tree.addTopLevelItem(root2)

        demo_specs = [
            ["1", "A01", "1200", "2400", "600", "2999", "2100"],
            ["2", "A02", "1600", "2400", "600", "3999", "3100"],
        ]

        self.spec_table.setRowCount(len(demo_specs))

        for row, data in enumerate(demo_specs):
            for col, text in enumerate(data):
                self.spec_table.setItem(row, col, QTableWidgetItem(text))

        demo_params = [
            ["门板颜色", "暖白 / 奶咖 / 深灰"],
            ["拉手类型", "暗拉手 / 明装拉手"],
            ["柜体板厚", "18mm / 25mm"],
        ]

        self.param_table.setRowCount(len(demo_params))

        for row, data in enumerate(demo_params):
            for col, text in enumerate(data):
                self.param_table.setItem(row, col, QTableWidgetItem(text))


