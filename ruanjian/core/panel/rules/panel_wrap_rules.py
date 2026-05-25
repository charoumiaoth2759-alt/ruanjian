# -*- coding: utf-8 -*-
"""
板件包裹关系（旁/顶/底/背互相扣尺）。

本模块为目录重构后补齐的**规则数据入口**，供 `panel_generator` / `panel_placement` 引用。
"""

from __future__ import annotations

from dataclasses import dataclass

from core.space.enums import SpaceType


@dataclass(frozen=True)
class WrapRule:
    """描述一组布尔包裹关系（与 `panel_generator` 中字段名一致）。"""

    back_reduces_depth: bool = True
    bottom_wraps_sides: bool = False
    side_wraps_top: bool = True
    side_wraps_bottom: bool = True
    side_wraps_back: bool = True
    top_wraps_back: bool = False
    bottom_wraps_back: bool = False


_DEFAULT = WrapRule()


def get_wrap_rule(_space_type: SpaceType) -> WrapRule:
    """按空间类型返回包裹规则（当前为统一默认，保持 API 稳定）。"""
    return _DEFAULT


__all__ = ["WrapRule", "get_wrap_rule"]
