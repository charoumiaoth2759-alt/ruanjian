# -*- coding: utf-8 -*-
"""
板件生成门面（从 Space 树到板件列表）。

说明：
    实际算法在既有模块 `panel_generator.py` 的 `generate()` 中实现；
    本文件仅提供**稳定对外入口**，供 ``core.solver.solve`` 与命令链调用，
    避免业务层直接依赖内部文件名变更。
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .panel_generator import GenerateResult
    from ..space.space_models import Space


def generate_panels_from_space_tree(root: "Space") -> "GenerateResult":
    """
    从整棵 Space 树根节点生成板件分组结果。

    Returns:
        GenerateResult：含 groups / errors；板件展平用 `.all_panels`。

    兼容：
        若 `panel_generator` 因依赖缺失无法导入，返回空结果，不抛异常打断 UI。
    """
    try:
        from .panel_generator import generate
    except Exception:  # pragma: no cover — 兼容残缺依赖环境
        from dataclasses import dataclass, field

        @dataclass
        class _EmptyGenerateResult:
            """空生成结果占位。"""

            groups: list = field(default_factory=list)
            errors: list = field(default_factory=list)
            skipped: list = field(default_factory=list)

            @property
            def all_panels(self) -> list:
                return []

            @property
            def ok(self) -> bool:
                return True

        return _EmptyGenerateResult()

    return generate(root, dirty_only=False, include_dividers=True, include_skeleton=False)
