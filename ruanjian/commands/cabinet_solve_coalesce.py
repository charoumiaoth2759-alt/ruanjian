# -*- coding: utf-8 -*-
"""
柜体求解相关：事件合并桶键（与命令 / 总线共用）。

从 ``core.solver`` 迁出，避免 solver 包承担 UI / 总线编排职责。
"""

# Space / Panel / Material 三类高频触发共用，避免同帧重复求解
CABINET_SOLVE_COALESCE_KEY = "cabinet_solver_coalesce_v1"

__all__ = ["CABINET_SOLVE_COALESCE_KEY"]
