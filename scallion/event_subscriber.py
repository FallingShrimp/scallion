"""程序内部事件订阅-发布机制

与 WebSocket 协议事件 (events.py) 完全区分：
  - events.py   → 跨进程/跨网络的数据包定义 (BaseEvent / ChangedEvent)
  - 本模块      → 同一进程内的回调解耦，不关心数据结构，只管传播

用法::

    from scallion.event_subscriber import EventSubscriber

    article_compiled = EventSubscriber()
    article_compiled.subscribe(lambda result, raw: print("编译完成"))

    # 触发
    article_compiled.emit(json_str, original_text)

    # 等价调用
    article_compiled(json_str, original_text)
"""

from __future__ import annotations

import asyncio
import threading
from collections.abc import Callable
from typing import Any

C = Callable[..., Any]


class EventSubscriber:
    """单个事件的订阅-发布器

    每个实例管理一个逻辑事件，维护一组订阅回调。
    线程安全，支持异步回调。
    """

    __slots__ = ("_callbacks", "_lock", "_loop")

    def __init__(self) -> None:
        self._callbacks: list[C] = []
        self._lock = threading.Lock()

    # ── 订阅 / 取消 ────────────────────────────────

    def subscribe(self, callback: C) -> C:
        """注册回调。返回 callback 自身，方便用作装饰器::

        @article_compiled.subscribe
        def on_compiled(result, raw):
            ...
        """
        with self._lock:
            if callback not in self._callbacks:
                self._callbacks.append(callback)
        return callback

    def unsubscribe(self, callback: C) -> None:
        """取消注册（已取消或不存在的回调静默忽略）"""
        with self._lock:
            try:
                self._callbacks.remove(callback)
            except ValueError:
                pass

    # ── 触发 ───────────────────────────────────────

    def emit(self, *args: Any, **kwargs: Any) -> None:
        """同步触发：依次调用所有订阅回调"""
        with self._lock:
            cbs = list(self._callbacks)
        for cb in cbs:
            try:
                cb(*args, **kwargs)
            except Exception:
                # 静默吃掉异常，避免单个回调崩溃影响其他订阅者
                pass

    async def async_emit(self, *args: Any, **kwargs: Any) -> None:
        """异步触发：并发 await 所有异步/同步回调。同步回调在线程池中执行"""
        with self._lock:
            cbs = list(self._callbacks)

        async def _run(cb: C) -> None:
            try:
                if asyncio.iscoroutinefunction(cb):
                    await cb(*args, **kwargs)
                else:
                    loop = asyncio.get_running_loop()
                    await loop.run_in_executor(None, cb, *args, **kwargs)
            except Exception:
                pass

        await asyncio.gather(*(_run(cb) for cb in cbs), return_exceptions=True)

    # ── 语法糖 ─────────────────────────────────────

    def __call__(self, *args: Any, **kwargs: Any) -> None:
        """article_compiled(data, raw) 等价于 article_compiled.emit(data, raw)"""
        self.emit(*args, **kwargs)

    def __iadd__(self, callback: C) -> EventSubscriber:
        """article_compiled += callback"""
        self.subscribe(callback)
        return self

    def __isub__(self, callback: C) -> EventSubscriber:
        """article_compiled -= callback"""
        self.unsubscribe(callback)
        return self

    def __len__(self) -> int:
        with self._lock:
            return len(self._callbacks)

    def __bool__(self) -> bool:
        return len(self) > 0

    def __repr__(self) -> str:
        return f"<EventSubscriber subscribers={len(self)}>"
