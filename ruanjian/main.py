# -*- coding: utf-8 -*-
"""应用入口"""
import sys
import traceback

from PySide6.QtCore import QTimer
from PySide6.QtGui import QSurfaceFormat
from PySide6.QtWidgets import QApplication

from core.events.event_bus import set_flush_bridge
from ui.main_window import MainWindow
from ui.qt_lifecycle import configure_application_font_and_style


def main():
    print("[1] start main", flush=True)

    print("[2] create QApplication", flush=True)
    fmt = QSurfaceFormat()
    fmt.setDepthBufferSize(24)
    fmt.setStencilBufferSize(8)
    fmt.setSamples(8)  # MSAA
    QSurfaceFormat.setDefaultFormat(fmt)

    app = QApplication(sys.argv)
    # 去抖后的派发由 UI 层注入：此处使用宿主单次调度把 ``work`` 投到主线程（core/events 无 GUI 依赖）
    set_flush_bridge(lambda work: QTimer.singleShot(0, work))
    # Fusion + 显式系统 UI 字号：缓解 Windows 原生样式下 Qt C++ setPointSize(-1) 告警
    configure_application_font_and_style(app)

    app.setApplicationName("智柜")
    app.setApplicationVersion("V2026")

    print("[3] create main window", flush=True)
    window = MainWindow()

    print("[4] show main window", flush=True)
    window.show()

    print("[5] app.exec start", flush=True)
    sys.exit(app.exec())


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print("FATAL ERROR:", e, flush=True)
        traceback.print_exc()
        input("press enter to exit")
