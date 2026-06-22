"""Scallion 文件监听 + WebSocket 广播客户端

WatchClient 完全独立于 Parser，只负责：
  1. 使用 watchdog 监听指定文件的变动
  2. 变动时通过 on_changed (EventSubscriber) 广播原始文本
  3. 若有 port，启动 WebSocket 服务器可供广播 BaseEvent 数据包
"""

from __future__ import annotations

import asyncio
from pathlib import Path

import websockets
from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer
from websockets.asyncio.server import Server, ServerConnection

from scallion.event_subscriber import EventSubscriber
from .events import BaseEvent


# ─── watchdog 事件处理器（内部类）───────────────────────


class _FileChangeHandler(FileSystemEventHandler):
    """将 watchdog 原生事件转发给 WatchClient"""

    def __init__(self, client: WatchClient) -> None:
        super().__init__()
        self._client = client

    def on_modified(self, event: object) -> None:
        # 只响应目标文件本身的修改
        src = getattr(event, "src_path", "")
        if Path(src).resolve() == self._client._target_file:
            self._client._on_file_changed()


# ─── WatchClient ────────────────────────────────────────


class WatchClient:
    """文件监听 + 可选 WebSocket 广播客户端

    用法::

        client = WatchClient("article.txt", port=9000)

        @client.on_changed.subscribe
        def handle(raw: str) -> None:
            result = compile(raw)
            client.send_event(ChangedEvent(data=result, raw=raw))

        async with client:
            ...  # 阻塞直到外部取消
    """

    def __init__(self, filename: str, port: int = 0) -> None:
        self._target_file = Path(filename).resolve()
        self.port = port

        self._observer = Observer()
        self._server: Server | None = None
        self._clients: set[ServerConnection] = set()
        self._loop: asyncio.AbstractEventLoop | None = None

        self.on_changed = EventSubscriber()
        """文件变更时触发，回调参数 `(raw: str)`

        用法::

            @client.on_changed.subscribe
            def handle_change(raw: str) -> None:
                result = compile(raw)
                client.send_event(ChangedEvent(data=result, raw=raw))
        """

    # ── 事件广播（公开 API）────────────────────────

    async def broadcast(self, event: BaseEvent) -> None:
        """异步广播事件给所有已连接的 WebSocket 客户端"""
        if not self._clients:
            return
        payload = event.model_dump_json(by_alias=True)
        await asyncio.gather(
            *(ws.send(payload) for ws in self._clients),
            return_exceptions=True,
        )

    def send_event(self, event: BaseEvent) -> None:
        """线程安全的事件发送（供 watchdog 回调等非异步上下文调用）"""
        if self._loop is not None:
            asyncio.run_coroutine_threadsafe(self._broadcast(event), self._loop)

    # ── 内部：文件变更回调 ────────────────────────

    def _on_file_changed(self) -> None:
        """watchdog 通知文件已修改 —— 读取原始文本并通过 on_changed 广播"""
        try:
            raw = self._target_file.read_text(encoding="utf-8")
        except OSError:
            return
        self.on_changed.emit(raw)

    async def _broadcast(self, event: BaseEvent) -> None:
        """内部广播实现"""
        if not self._clients:
            return
        payload = event.model_dump_json(by_alias=True)
        await asyncio.gather(
            *(ws.send(payload) for ws in self._clients),
            return_exceptions=True,
        )

    # ── WebSocket 连接管理 ─────────────────────────

    async def _ws_handler(self, websocket: ServerConnection) -> None:
        self._clients.add(websocket)
        try:
            async for _ in websocket:
                pass  # 保持连接直到客户端断开
        finally:
            self._clients.discard(websocket)

    # ── 生命周期 ──────────────────────────────────

    async def start(self) -> None:
        """启动文件监听与 WebSocket 服务器（若有 port）"""
        self._loop = asyncio.get_running_loop()

        if self.port > 0:
            self._server = await websockets.serve(
                self._ws_handler, "localhost", self.port
            )

        handler = _FileChangeHandler(self)
        watch_dir = str(self._target_file.parent)
        self._observer.schedule(handler, watch_dir, recursive=False)
        self._observer.start()

    async def stop(self) -> None:
        """停止文件监听与 WebSocket 服务器"""
        self._observer.stop()
        self._observer.join()

        if self._server is not None:
            self._server.close()
            await self._server.wait_closed()

    async def __aenter__(self) -> WatchClient:
        await self.start()
        return self

    async def __aexit__(self, *args: object) -> None:
        await self.stop()
