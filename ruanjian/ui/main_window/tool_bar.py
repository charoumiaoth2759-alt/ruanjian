# -*- coding: utf-8 -*-
"""工具栏模块

仅包含左侧垂直 Tab 栏：
- SideTabBar —— 左侧垂直 Tab 栏，切换"画户型 / 画柜子 / 材质 / 模型 / 场景树"
                这是拆单软件的核心导航，配合左侧资源面板使用。
"""
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QWidget, QVBoxLayout, QPushButton, QButtonGroup


# ============================================================ 左侧垂直 Tab 栏
class SideTabBar(QWidget):
    """左侧垂直 Tab 切换栏。

    对应参考图中"画户型 / 画柜子 / 材质 / 模型 / 场景树"五个垂直标签。
    点击后通过 tab_changed 信号通知主窗口切换左侧资源面板内容。
    """

    # 信号：当前激活的 Tab 索引发生变化
    tab_changed = Signal(int)

    # Tab 定义（索引、名称、用途说明）
    TABS = [
        ("画户型",   "绘制房间布局、墙体、门窗"),
        ("画柜子",   "放置和编辑柜体"),
        ("材质",     "选择板材、封边、五金材质"),
        ("模型",     "导入 3D 模型库"),
        ("场景树",   "查看当前项目的所有对象层级"),
        ("智能设计", "AI 自动布局 / 智能推荐 / 一键生成"),
    ]

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("sideTabBar")
        self.setFixedWidth(34)   # 原 28px，增加五分之一（≈+6px → 34px）

        self._buttons = []
        self._group = QButtonGroup(self)
        self._group.setExclusive(True)

        self._build_ui()
        self._apply_style()

        # 默认激活第一个 Tab
        if self._buttons:
            self._buttons[0].setChecked(True)

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        for idx, (name, tooltip) in enumerate(self.TABS):
            btn = QPushButton(self._to_vertical_text(name))
            btn.setCheckable(True)
            btn.setToolTip(tooltip)
            btn.setFixedHeight(120)  # 原 80px，增加四分之二（+50% → 120px）
            btn.setCursor(Qt.CursorShape.PointingHandCursor)

            self._group.addButton(btn, idx)
            self._buttons.append(btn)
            layout.addWidget(btn)

        layout.addStretch(1)

        # 连接信号
        self._group.idClicked.connect(self.tab_changed.emit)

    @staticmethod
    def _to_vertical_text(text: str) -> str:
        """把横向文字转成竖排显示（用换行符模拟）。"""
        return "\n".join(text)

    def _apply_style(self):
        """深色栏 + 激活态 #4dc9e4。"""
        self.setStyleSheet("""
            QWidget#sideTabBar {
                background-color: #2c3e50;
            }
            QPushButton {
                background-color: #2c3e50;
                color: #ffffff;
                border: none;
                font-size: 12px;
                padding: 6px 0;
            }
            QPushButton:hover {
                background-color: #34495e;
            }
            QPushButton:checked {
                background-color: #4dc9e4;
                color: #2c3e50;
                font-weight: bold;
            }
            QPushButton:checked:hover {
                background-color: #6fd4ec;
            }
        """)

    def current_index(self) -> int:
        """返回当前激活的 Tab 索引。"""
        return self._group.checkedId()

    def set_current_index(self, index: int):
        """切换到指定 Tab。"""
        if 0 <= index < len(self._buttons):
            self._buttons[index].setChecked(True)
            self.tab_changed.emit(index)
