# -*- coding: utf-8 -*-
"""
纯 Python 事件载体与常用类型名字符串。

说明：
    - ``Event.type`` 为 **str**，``Event.payload`` 恒为 **dict**。
    - ``BuiltinEventTopics`` 为稳定字符串常量；业务可自定义其它 ``type``。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


class BuiltinEventTopics:
    """内置业务事件 ``type`` 字符串（与命令层 ``events[].type`` 对齐）。"""

    SPACE_CHANGED = "SPACE_CHANGED"
    CABINET_CREATED = "CABINET_CREATED"
    PANEL_CHANGED = "PANEL_CHANGED"
    MATERIAL_CHANGED = "MATERIAL_CHANGED"
    SELECTION_CHANGED = "SELECTION_CHANGED"
    SOLVE_COMPLETED = "SOLVE_COMPLETED"


@dataclass(frozen=True)
class Event:
    """
    总线中传递的事件实例（纯数据结构）。

    字段：
        type: 事件类型名（任意 str）
        payload: 附加数据，恒为 dict
        coalesce_key:
            若不为 None，则在同一去抖窗口内、相同 ``coalesce_key`` 的多条事件
            只保留**最后一条**（用于高频 ``publish`` 合并）。
        immediate:
            若为 True，不经过去抖队列，立即同步派发给订阅者。
    """

    type: str
    payload: dict[str, Any] = field(default_factory=dict)
    coalesce_key: str | None = None
    immediate: bool = False

    def merge_bucket(self) -> str:
        """返回队列合并桶键：默认同 ``type``，可被 ``coalesce_key`` 覆盖。"""
        if self.coalesce_key is not None:
            return self.coalesce_key
        return self.type
