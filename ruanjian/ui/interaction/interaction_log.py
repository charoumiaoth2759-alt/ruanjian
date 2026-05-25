# -*- coding: utf-8 -*-
"""柜体交互 / 命令 / 撤销的统一控制台日志前缀（无 Qt）。"""

from __future__ import annotations

import os

_ENABLED = os.environ.get("ZHIGUI_INTERACTION_LOG", "1").strip() not in (
    "0",
    "false",
    "False",
    "no",
    "NO",
)


def log_mode(mode: str) -> None:
    """例如 ``[MODE] ADD_PANEL``。"""
    if _ENABLED:
        print(f"[MODE] {mode}", flush=True)


def log_command(command_name: str) -> None:
    """例如 ``[COMMAND] AddBoardCommand``。"""
    if _ENABLED:
        print(f"[COMMAND] {command_name}", flush=True)


def log_view3d_add_panel_visual() -> None:
    """``AddBoardCommand`` 增量刷新主 3D 板件（非全量 rebuild）。"""
    if _ENABLED:
        print("[View3D] add panel visual", flush=True)


def log_view3d_remove_panel_visual() -> None:
    if _ENABLED:
        print("[View3D] remove panel visual", flush=True)


__all__ = [
    "log_command",
    "log_mode",
    "log_view3d_add_panel_visual",
    "log_view3d_remove_panel_visual",
]
