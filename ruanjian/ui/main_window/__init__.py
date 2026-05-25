# -*- coding: utf-8 -*-
"""主窗口模块包

对外只暴露 MainWindow，其余子组件由 main_window.py 内部组装。
"""
from .main_window import MainWindow

__all__ = ["MainWindow"]
