# -*- coding: utf-8 -*-
"""
应用级事件总线（标准库：threading 去抖 + 合并队列）。

API：
    - ``EventBus.subscribe(event_type, handler) -> unsub``：按事件类型字符串订阅。
    - ``EventBus.publish(event)``：投递事件；``immediate`` 为真时同步派发，否则去抖后派发。

可选钩子 ``set_flush_bridge``：在去抖定时器线程上完成合并后，将「派发批次」交给宿主
（例如由 **UI 层** 把回调投递到主线程）；未设置时在当前线程直接派发。
"""

from __future__ import annotations

import threading
from collections import defaultdict
from typing import Any, Callable

from .event_queue import CoalescingEventQueue
from .event_types import Event

EventHandler = Callable[[Event], Any]

_DEFAULT_DEBOUNCE_MS = 48

_flush_bridge: Callable[[Callable[[], None]], None] = lambda work: work()


def set_flush_bridge(fn: Callable[[Callable[[], None]], None] | None) -> None:
    """
    设置「冲刷后派发」的桥接函数。

    ``fn(work)`` 收到无参 ``work`` 时应安排其尽快执行（典型用法由 **UI 入口**
    注入宿主工具包的单次调度，**本模块不** import 任何 GUI 框架）。

    传入 ``None`` 表示在触发去抖的线程上直接执行 ``work()``。
    """
    global _flush_bridge
    if fn is None:
        _flush_bridge = lambda work: work()
    else:
        _flush_bridge = fn


# 兼容旧名（仍指向同一钩子，新代码请用 ``set_flush_bridge``）
set_event_thread_marshal = set_flush_bridge


class EventBus:
    """
    纯 Python 事件总线：不绑定任何宿主 GUI 框架的类型或信号机制。

    - ``subscribe(event_type, handler)``：仅派发 ``event.type == event_type`` 的回调。
    - ``publish``：去抖合并或立即派发。
    """

    def __init__(self, debounce_ms: int = _DEFAULT_DEBOUNCE_MS) -> None:
        self._debounce_ms = max(8, int(debounce_ms))
        self._queue = CoalescingEventQueue()
        self._by_type: dict[str, list[EventHandler]] = defaultdict(list)
        self._lock = threading.Lock()
        self._timer: threading.Timer | None = None

    def subscribe(self, event_type: str, handler: EventHandler) -> Callable[[], None]:
        """订阅 ``event_type``；返回 ``unsub()`` 可取消订阅。"""
        if not isinstance(event_type, str):
            raise TypeError("event_type must be str")
        self._by_type[event_type].append(handler)

        def unsub() -> None:
            lst = self._by_type.get(event_type)
            if not lst:
                return
            try:
                lst.remove(handler)
            except ValueError:
                pass

        return unsub

    def publish(self, event: Event) -> None:
        """投递事件：``immediate`` 为真则立即派发；否则入队并重启去抖定时器。"""
        if event.immediate:
            self._deliver(event)
            return
        with self._lock:
            self._queue.enqueue(event)
            if self._timer is not None:
                self._timer.cancel()
                self._timer = None
            self._timer = threading.Timer(
                self._debounce_ms / 1000.0,
                self._timer_fire,
            )
            self._timer.daemon = True
            self._timer.start()

    def _timer_fire(self) -> None:
        def work() -> None:
            with self._lock:
                self._timer = None
                events = self._queue.drain()
            for ev in events:
                self._deliver(ev)

        _flush_bridge(work)

    def _deliver(self, event: Event) -> None:
        for h in list(self._by_type.get(event.type, [])):
            try:
                h(event)
            except Exception:
                continue


_bus_singleton: EventBus | None = None
_bus_lock = threading.Lock()


def get_event_bus() -> EventBus:
    """获取（或创建）默认总线实例。"""
    global _bus_singleton
    with _bus_lock:
        if _bus_singleton is None:
            _bus_singleton = EventBus()
        return _bus_singleton


def publish(event: Event) -> None:
    """向默认总线 ``publish``。"""
    get_event_bus().publish(event)
