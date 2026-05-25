# -*- coding: utf-8 -*-
"""基础配置对话框

对应 菜单 → 设置 → 用户基础设置。
功能区域：
    1. 门店配置  —— 品牌名称 / 门店名称 / 联系电话 / 传真号码 / 门店地址 / 公司名称 / 品牌文化
    2. 订单号规则设置 —— 标识字符 + 年份号 + 月份号 + 日份号 + 流水编号
    3. 产品数据库（适用旧版） —— 启用 + 数据库文件路径

本对话框只负责"采集 + 校验"，不直接读写磁盘/数据库；
确认后通过 get_config() 把数据返回给调用方，由 controller / core 层落盘。
"""
from datetime import datetime

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)


# 与主窗口侧栏一致的深蓝色；激活/强调色与系统设置、侧栏工具栏一致
PRIMARY_COLOR = "#2c3e50"
PRIMARY_COLOR_HOVER = "#34495e"
ACCENT = "#4dc9e4"
WARN_COLOR = "#e74c3c"


# ============================================================ 主对话框
class BasicConfigDialog(QDialog):
    """用户基础设置对话框。"""

    WINDOW_TITLE = "基础配置"

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(self.WINDOW_TITLE)
        self.setModal(True)
        self.resize(720, 640)

        self._build_ui()
        self._apply_style()
        self._update_order_preview()  # 初始化效果示例

    # ---------------------------------------------------------------- UI
    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(10)

        root.addWidget(self._build_store_group())
        root.addWidget(self._build_order_rule_group())
        root.addWidget(self._build_product_db_group())

        root.addStretch(1)
        root.addLayout(self._build_bottom_bar())

    # ---------------- 门店配置 ----------------
    def _build_store_group(self) -> QGroupBox:
        group = QGroupBox("门店配置")

        grid = QGridLayout(group)
        grid.setContentsMargins(12, 18, 12, 12)
        grid.setHorizontalSpacing(10)
        grid.setVerticalSpacing(10)

        # 第 1 行：品牌名称 | 门店名称
        self.edit_brand_name = QLineEdit()
        self.edit_store_name = QLineEdit()
        grid.addWidget(QLabel("品牌名称："), 0, 0)
        grid.addWidget(self.edit_brand_name, 0, 1)
        grid.addWidget(QLabel("门店名称："), 0, 2)
        grid.addWidget(self.edit_store_name, 0, 3)

        # 第 2 行：联系电话 | 传真号码
        self.edit_contact_phone = QLineEdit()
        self.edit_fax_number = QLineEdit()
        grid.addWidget(QLabel("联系电话："), 1, 0)
        grid.addWidget(self.edit_contact_phone, 1, 1)
        grid.addWidget(QLabel("传真号码："), 1, 2)
        grid.addWidget(self.edit_fax_number, 1, 3)

        # 第 3 行：门店地址（占满）
        self.edit_store_address = QLineEdit()
        grid.addWidget(QLabel("门店地址："), 2, 0)
        grid.addWidget(self.edit_store_address, 2, 1, 1, 3)

        # 第 4 行：公司名称（占满）
        self.edit_company_name = QLineEdit()
        grid.addWidget(QLabel("公司名称："), 3, 0)
        grid.addWidget(self.edit_company_name, 3, 1, 1, 3)

        # 第 5 行：品牌文化（占满）
        self.edit_brand_culture = QLineEdit()
        grid.addWidget(QLabel("品牌文化："), 4, 0)
        grid.addWidget(self.edit_brand_culture, 4, 1, 1, 3)

        # 列宽：两列输入框等宽
        grid.setColumnStretch(1, 1)
        grid.setColumnStretch(3, 1)
        return group

    # ---------------- 订单号规则 ----------------
    def _build_order_rule_group(self) -> QGroupBox:
        group = QGroupBox("订单号规则设置")

        outer = QVBoxLayout(group)
        outer.setContentsMargins(12, 18, 12, 12)
        outer.setSpacing(10)

        # 规则行：标识字符 + [√]年份号 + [√]月份号 + [ ]日份号 + 流水编号
        row = QHBoxLayout()
        row.setSpacing(8)

        row.addWidget(QLabel("标识字符"))

        self.edit_order_prefix = QLineEdit()
        self.edit_order_prefix.setFixedWidth(120)
        row.addWidget(self.edit_order_prefix)

        row.addWidget(QLabel("+"))
        self.chk_year = QCheckBox("年份号")
        self.chk_year.setChecked(True)
        row.addWidget(self.chk_year)

        row.addWidget(QLabel("+"))
        self.chk_month = QCheckBox("月份号")
        self.chk_month.setChecked(True)
        row.addWidget(self.chk_month)

        row.addWidget(QLabel("+"))
        self.chk_day = QCheckBox("日份号")
        self.chk_day.setChecked(False)
        row.addWidget(self.chk_day)

        row.addWidget(QLabel("+"))
        row.addWidget(QLabel("流水编号"))

        row.addStretch(1)
        outer.addLayout(row)

        # 效果示例
        preview_row = QHBoxLayout()
        preview_row.addWidget(QLabel("效果示例："))
        self.lbl_order_preview = QLabel("2605001")
        self.lbl_order_preview.setStyleSheet("color: #606266;")
        preview_row.addWidget(self.lbl_order_preview)
        preview_row.addStretch(1)
        outer.addLayout(preview_row)

        # 监听变化，实时刷新示例
        self.edit_order_prefix.textChanged.connect(self._update_order_preview)
        self.chk_year.toggled.connect(self._update_order_preview)
        self.chk_month.toggled.connect(self._update_order_preview)
        self.chk_day.toggled.connect(self._update_order_preview)
        return group

    # ---------------- 产品数据库 ----------------
    def _build_product_db_group(self) -> QGroupBox:
        group = QGroupBox("产品数据库（适用旧版）")

        outer = QVBoxLayout(group)
        outer.setContentsMargins(12, 18, 12, 12)
        outer.setSpacing(8)

        row = QHBoxLayout()
        row.setSpacing(8)

        self.chk_enable_db = QCheckBox("启用")
        row.addWidget(self.chk_enable_db)

        row.addWidget(QLabel("数据库文件："))

        self.edit_db_path = QLineEdit()
        row.addWidget(self.edit_db_path, 1)

        self.btn_browse_db = QPushButton("...")
        self.btn_browse_db.setFixedWidth(32)
        self.btn_browse_db.clicked.connect(self._on_browse_db_clicked)
        row.addWidget(self.btn_browse_db)

        outer.addLayout(row)

        # 启用状态联动
        self.chk_enable_db.toggled.connect(self.edit_db_path.setEnabled)
        self.chk_enable_db.toggled.connect(self.btn_browse_db.setEnabled)
        self.edit_db_path.setEnabled(False)
        self.btn_browse_db.setEnabled(False)
        return group

    # ---------------- 底部按钮区 ----------------
    def _build_bottom_bar(self) -> QHBoxLayout:
        bar = QHBoxLayout()
        bar.setContentsMargins(0, 0, 0, 0)
        bar.setSpacing(10)

        self.lbl_warning = QLabel("注：产品库文件改变，必须重新运行软件生效！")
        self.lbl_warning.setStyleSheet(f"color: {WARN_COLOR};")
        bar.addWidget(self.lbl_warning)

        bar.addStretch(1)

        self.btn_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel,
            parent=self,
        )
        self.btn_ok = self.btn_box.button(QDialogButtonBox.StandardButton.Ok)
        self.btn_cancel = self.btn_box.button(QDialogButtonBox.StandardButton.Cancel)
        self.btn_ok.setText("确 定")
        self.btn_cancel.setText("取 消")
        self.btn_ok.setObjectName("primaryButton")
        self.btn_cancel.setObjectName("defaultButton")
        self.btn_ok.setFixedSize(96, 32)
        self.btn_cancel.setFixedSize(96, 32)
        self.btn_box.accepted.connect(self.accept)
        self.btn_box.rejected.connect(self.reject)
        bar.addWidget(self.btn_box)
        return bar

    # ---------------------------------------------------------------- 样式
    def _apply_style(self):
        """复选框、输入框焦点/选区与次要按钮悬停使用激活色 #4dc9e4；确定为主色 #2c3e50。"""
        self.setStyleSheet(f"""
            QDialog {{
                background-color: #ffffff;
            }}
            QGroupBox {{
                font-weight: bold;
                color: #303133;
                border: 1px solid #dcdfe6;
                border-radius: 4px;
                margin-top: 10px;
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                subcontrol-position: top left;
                left: 10px;
                padding: 0 6px;
                background-color: #ffffff;
            }}
            QLabel {{
                color: #303133;
            }}
            QLineEdit {{
                border: 1px solid #dcdfe6;
                border-radius: 3px;
                padding: 4px 6px;
                background: #ffffff;
                selection-background-color: {ACCENT};
            }}
            QLineEdit:focus {{
                border: 1px solid {ACCENT};
            }}
            QLineEdit:disabled {{
                background: #f5f7fa;
                color: #c0c4cc;
            }}

            /* —— 复选框：激活色 —— */
            QCheckBox {{
                color: #303133;
                spacing: 6px;
            }}
            QCheckBox::indicator {{
                width: 16px;
                height: 16px;
                border: 1px solid #c0c4cc;
                border-radius: 2px;
                background: #ffffff;
            }}
            QCheckBox::indicator:hover {{
                border: 1px solid {ACCENT};
            }}
            QCheckBox::indicator:checked {{
                background: {ACCENT};
                border: 1px solid {ACCENT};
                image: none;
            }}
            QCheckBox::indicator:disabled {{
                background: #f5f7fa;
                border: 1px solid #e4e7ed;
            }}

            /* —— 按钮 —— */
            QPushButton#primaryButton {{
                background-color: {PRIMARY_COLOR};
                color: #ffffff;
                border: 1px solid {PRIMARY_COLOR};
                border-radius: 3px;
            }}
            QPushButton#primaryButton:hover {{
                background-color: {PRIMARY_COLOR_HOVER};
                border-color: {PRIMARY_COLOR_HOVER};
            }}
            QPushButton#defaultButton {{
                background-color: #ffffff;
                color: #303133;
                border: 1px solid #dcdfe6;
                border-radius: 3px;
            }}
            QPushButton#defaultButton:hover {{
                border-color: {ACCENT};
                color: {ACCENT};
            }}
            /* "..." 浏览按钮 */
            QPushButton {{
                background-color: #ffffff;
                border: 1px solid #dcdfe6;
                border-radius: 3px;
                padding: 4px 8px;
            }}
            QPushButton:hover {{
                border-color: {ACCENT};
                color: {ACCENT};
            }}
            QPushButton:disabled {{
                background: #f5f7fa;
                color: #c0c4cc;
                border-color: #e4e7ed;
            }}
        """)

    # ---------------------------------------------------------------- 槽函数
    def _update_order_preview(self):
        """根据当前规则刷新效果示例。"""
        now = datetime.now()
        parts = []
        if self.edit_order_prefix.text().strip():
            parts.append(self.edit_order_prefix.text().strip())
        if self.chk_year.isChecked():
            parts.append(f"{now.year % 100:02d}")
        if self.chk_month.isChecked():
            parts.append(f"{now.month:02d}")
        if self.chk_day.isChecked():
            parts.append(f"{now.day:02d}")
        parts.append("001")  # 流水号占位
        self.lbl_order_preview.setText("".join(parts))

    def _on_browse_db_clicked(self):
        """打开文件选择对话框，选择产品库文件。"""
        path, _ = QFileDialog.getOpenFileName(
            self,
            "选择产品数据库文件",
            self.edit_db_path.text() or "",
            "数据库文件 (*.db *.mdb *.sqlite);;所有文件 (*.*)",
        )
        if path:
            self.edit_db_path.setText(path)

    # ---------------------------------------------------------------- 对外接口
    def get_config(self) -> dict:
        """返回当前对话框中的所有配置项，供 controller 落盘使用。"""
        return {
            "store": {
                "brand_name":     self.edit_brand_name.text().strip(),
                "store_name":     self.edit_store_name.text().strip(),
                "contact_phone":  self.edit_contact_phone.text().strip(),
                "fax_number":     self.edit_fax_number.text().strip(),
                "store_address":  self.edit_store_address.text().strip(),
                "company_name":   self.edit_company_name.text().strip(),
                "brand_culture":  self.edit_brand_culture.text().strip(),
            },
            "order_rule": {
                "prefix":      self.edit_order_prefix.text().strip(),
                "with_year":   self.chk_year.isChecked(),
                "with_month":  self.chk_month.isChecked(),
                "with_day":    self.chk_day.isChecked(),
            },
            "product_db": {
                "enabled": self.chk_enable_db.isChecked(),
                "path":    self.edit_db_path.text().strip(),
            },
        }

    def set_config(self, cfg: dict):
        """把已有配置回填到对话框。cfg 结构同 get_config()。"""
        store = cfg.get("store", {})
        self.edit_brand_name.setText(store.get("brand_name", ""))
        self.edit_store_name.setText(store.get("store_name", ""))
        self.edit_contact_phone.setText(store.get("contact_phone", ""))
        self.edit_fax_number.setText(store.get("fax_number", ""))
        self.edit_store_address.setText(store.get("store_address", ""))
        self.edit_company_name.setText(store.get("company_name", ""))
        self.edit_brand_culture.setText(store.get("brand_culture", ""))

        rule = cfg.get("order_rule", {})
        self.edit_order_prefix.setText(rule.get("prefix", ""))
        self.chk_year.setChecked(rule.get("with_year", True))
        self.chk_month.setChecked(rule.get("with_month", True))
        self.chk_day.setChecked(rule.get("with_day", False))

        db = cfg.get("product_db", {})
        self.chk_enable_db.setChecked(db.get("enabled", False))
        self.edit_db_path.setText(db.get("path", ""))

        self._update_order_preview()
