# -*- coding: utf-8 -*-
"""
Qt 信号与字体相关的生命周期小工具。

用途：
    - 统一「安全断开」信号，避免未连接时 `RuntimeWarning: Failed to disconnect`。
    - 统一「安全字号」，避免 `QFont::setPointSize: Point size <= 0` 等告警。

字体规则（必读）：
    Qt 默认 / 样式解析后的 `QFont.pointSize()` 可能为 **-1 或 0**（未指定点大小）。
    **禁止**把 `pointSize()` 的返回值直接传给 `setPointSize()`，例如：
    `font.setPointSize(font.pointSize() - 1)`、`font.setPointSize(widget.font().pointSize())`。
    应使用本模块的 `effective_font_point_size()` / `safe_set_font_size*()` /
    `repair_font_point_size_if_needed()`（应用启动时对 `QApplication.font()` 调用）。
    整应用启动请优先 `configure_application_font_and_style(app)`（Fusion + 系统 UI 字体）。
"""

from __future__ import annotations

import math
import warnings
from typing import Any

from PySide6.QtGui import QFont

# 当 `QFont.pointSize()` 无效（<=0，常见为 -1）时采用的默认点大小
DEFAULT_EFFECTIVE_POINT_SIZE = 10


def effective_font_point_size(
    font: QFont, default: int = DEFAULT_EFFECTIVE_POINT_SIZE
) -> int:
    """
    从 `font` 读取「可用的」整数点大小。

    Qt 在仅像素或样式指定字号时，`pointSize()` 常为 -1；不可直接传给 `setPointSize`。
    若 `pointSize` 无效但 `pixelSize` 有效，则按 96dpi 近似换算为点大小。
    """
    try:
        ps = int(font.pointSize())
    except (TypeError, ValueError):
        ps = -1
    if ps > 0:
        return ps
    try:
        px = int(font.pixelSize())
    except (TypeError, ValueError):
        px = -1
    if px > 0:
        return max(1, int(round(px * 72.0 / 96.0)))
    return int(default)


def repair_font_point_size_if_needed(font: QFont) -> None:
    """
    原地修复：当 `pointSize() <= 0` 时写入合法点大小（避免 Qt 内部 / 继承字体带 -1）。

    说明：启动日志里 `QFont::setPointSize(-1)` 常来自 **Qt C++ 样式引擎**，
    Python 侧 monkey patch `QFont.setPointSize` 抓不到栈；通过规范应用默认字体可消除多数情况。
    """
    if font.pointSize() > 0:
        return
    px = font.pixelSize()
    if px > 0:
        safe_set_font_size(font, max(1, int(round(px * 72.0 / 96.0))))
    else:
        safe_set_font_size(font, DEFAULT_EFFECTIVE_POINT_SIZE)


def configure_application_font_and_style(app: Any) -> None:
    """
    启动时统一：Fusion 样式 + 显式应用默认字体。

    Windows 原生样式（windowsvista）下，QSS 仅 `font-size: px` 与继承字体合并时，
    Qt 可能在 C++ 路径调用 `setPointSize(-1)` 并打印告警；Fusion + 全新 QFont 可显著减少此类问题。

    若需恢复系统原生样式，可设置环境变量 ``ZHIGUI_USE_NATIVE_STYLE=1``。
    """
    import os

    if os.environ.get("ZHIGUI_USE_NATIVE_STYLE", "").lower() not in (
        "1",
        "true",
        "yes",
    ):
        try:
            from PySide6.QtWidgets import QStyleFactory

            _st = QStyleFactory.create("Fusion")
            if _st is not None:
                app.setStyle(_st)
        except Exception:
            pass

    try:
        from PySide6.QtGui import QFontDatabase

        base = QFontDatabase.systemFont(QFontDatabase.SystemFont.GeneralFont)
    except Exception:
        base = app.font()

    pt = effective_font_point_size(base)
    fam = (base.family() or "").strip()
    if not fam:
        _fams = base.families()
        fam = (_fams[0] if _fams else "") or "Segoe UI"

    ui_font = QFont(fam)
    safe_set_font_size(ui_font, pt)
    app.setFont(ui_font)

    try:
        from PySide6.QtWidgets import QToolTip

        QToolTip.setFont(ui_font)
    except Exception:
        pass


def safe_disconnect(signal: Any, slot: Any | None = None) -> None:
    """
    安全断开 Qt 信号连接。

    在未连接、槽已销毁、或重复断开时静默返回。
    同时抑制 PySide 在失败断开时可能发出的 RuntimeWarning。
    """
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        try:
            if slot is None:
                signal.disconnect()
            else:
                signal.disconnect(slot)
        except (RuntimeError, TypeError):
            pass


def safe_set_font_size(font: QFont, size: float | int) -> None:
    """
    设置字体整数点大小，保证 >= 1。

    说明：Qt 对 `setPointSize(0)` 或负值会告警，动态 UI（缩放、计算字号）下
    应始终通过本函数写入点大小。
    """
    try:
        v = float(size)
    except (TypeError, ValueError):
        v = float(DEFAULT_EFFECTIVE_POINT_SIZE)
    if not math.isfinite(v) or v <= 0.0:
        v = float(DEFAULT_EFFECTIVE_POINT_SIZE)
    font.setPointSize(max(1, int(v)))


def safe_set_font_size_from_reference(
    font: QFont, reference: QFont, delta: int = 0
) -> None:
    """
    以 `reference` 的有效点大小为基准，加减 `delta` 后写入 `font`。

    替代错误写法::
        size = ref.pointSize()
        font.setPointSize(size - 1)  # size 可能为 -1 → 告警
    """
    base = effective_font_point_size(reference)
    safe_set_font_size(font, base + int(delta))


def safe_set_font_point_size_f(font: QFont, size: float) -> None:
    """
    设置浮点点大小，保证至少 1.0（与 `setPointSizeF` 配合的逻辑坐标场景）。
    """
    try:
        v = float(size)
    except (TypeError, ValueError):
        v = float(DEFAULT_EFFECTIVE_POINT_SIZE)
    if not math.isfinite(v) or v <= 0.0:
        v = float(DEFAULT_EFFECTIVE_POINT_SIZE)
    font.setPointSizeF(max(1.0, v))
