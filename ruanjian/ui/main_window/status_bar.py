# -*- coding: utf-8 -*-
"""状态栏模块

主窗口底部状态栏。显示：
- 左侧：当前操作提示信息
- 中部：鼠标在画布上的坐标（mm）
- 右侧：当前缩放比例、当前单位
"""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QStatusBar


class StatusBar(QStatusBar):
    """主窗口状态栏。

    坐标 / 单位 / 缩放已移入画布底部工具栏（_CanvasBottomBar）。
    此状态栏完全隐藏，接口保留以避免调用方报错。
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setSizeGripEnabled(False)
        self.setMaximumHeight(0)
        self.setVisible(False)

    # ---------------------------------------------------------------- 对外接口
    def set_hint(self, text: str, timeout_ms: int = 0):
        """兼容接口，状态栏隐藏时调用无副作用。"""
        self.showMessage(text, timeout_ms)

    def set_coordinate(self, x: float, y: float): pass
    def set_zoom(self, percent: int): pass
    def set_unit(self, unit: str): pass
