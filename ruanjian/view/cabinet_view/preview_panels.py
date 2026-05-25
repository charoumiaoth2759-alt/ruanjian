# -*- coding: utf-8 -*-
"""
两面板联合预览：
  左  CabinetAssembler      (cabinet_assembler.py)
  右  CabinetPropertyPanel  (cabinet_property_panel.py)

架构说明（解耦）：
  本文件仅作独立预览入口，不参与主程序的 CommandDispatcher。
  主程序内业务请走：信号 → commands → core → solver → View3D.refresh。
"""

import sys
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QHBoxLayout, QLabel
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor

from .cabinet_assembler import CabinetAssembler
from .cabinet_property_panel import CabinetPropertyPanel


class PreviewWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("柜体设计面板预览  ·  左: 组件库  |  右: 属性面板")
        self.resize(1100, 820)

        central = QWidget()
        root = QHBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        self.setCentralWidget(central)

        # ── 左面板 ───────────────────────────────────────────────────────────
        self._assembler = CabinetAssembler()
        self._assembler.sig_icon_clicked.connect(
            lambda i, p: print(f"[图标 {i+1:02d}] {p or '(无文件)'}"))
        self._assembler.sig_template_clicked.connect(
            lambda n, p: print(f"[模板] {n}  →  {p}"))
        root.addWidget(self._assembler)

        # ── 中间画布（模拟设计区域）──────────────────────────────────────────
        canvas = QWidget()
        canvas.setStyleSheet("background:#2c3e50;")
        lbl = QLabel("设 计 区 域")
        lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl.setStyleSheet("color:rgba(255,255,255,80);font-size:20px;letter-spacing:6px;")
        lay = QHBoxLayout(canvas)
        lay.addWidget(lbl)
        root.addWidget(canvas, 1)

        # ── 右面板 ───────────────────────────────────────────────────────────
        self._prop_panel = CabinetPropertyPanel()
        self._prop_panel.sig_finish_design.connect(
            lambda: print("[完成柜子设计]"))
        self._prop_panel.sig_add_or_modify.connect(
            lambda: print("[添加 or 修改]"))
        self._prop_panel.sig_save_to_library.connect(
            lambda: print("[存为产品库]"))
        self._prop_panel.sig_tab_changed.connect(
            lambda i: print(f"[Tab 切换] → {['柜体','板件','审图'][i]}"))
        root.addWidget(self._prop_panel)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    win = PreviewWindow()
    win.show()
    sys.exit(app.exec())
