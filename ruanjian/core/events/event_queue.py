# -*- coding: utf-8 -*-
"""
事件合并队列（coalesce / 去抖前的暂存）。

职责：
    - 在单次「冲刷」周期内，按 `Event.merge_bucket()` 合并多条事件，只保留同桶中**最后一条**。
    - 仅依赖标准库，便于单元测试与非 GUI 环境复用。
"""

from __future__ import annotations

from collections import OrderedDict
from typing import Iterator

from .event_types import Event


class CoalescingEventQueue:
    """
    合并队列：先入后覆盖（同 merge_bucket 只保留最新 Event）。

    说明：
        与外层 `EventBus` 的去抖定时器配合：拖动 60fps 连续 publish 时，
        在定时器触发前桶内始终只有一条最新事件，从而求解只跑一次。
    """

    def __init__(self) -> None:
        # 有序字典：保证 drain 时按「最后插入顺序」或稳定顺序输出
        self._pending: "OrderedDict[str, Event]" = OrderedDict()

    def enqueue(self, event: Event) -> None:
        """入队：同桶键覆盖旧事件。"""
        key = event.merge_bucket()
        if key in self._pending:
            del self._pending[key]
        self._pending[key] = event

    def __len__(self) -> int:
        return len(self._pending)

    def drain(self) -> list[Event]:
        """取出当前所有待处理事件并清空队列。"""
        out = list(self._pending.values())
        self._pending.clear()
        return out

    def peek_buckets(self) -> Iterator[str]:
        """调试：查看当前待处理桶键（不改变队列）。"""
        yield from self._pending.keys()
