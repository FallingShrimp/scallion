"""Scallion 文件监听 + WebSocket 广播客户端

WatchClient 完全独立于 Parser，只负责：
  1. 使用 watchdog 监听文件或目录的变动
  2. 变动时通过 on_changed (EventSubscriber) 广播 (filepath, raw)
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
        src = Path(getattr(event, "src_path", "")).resolve()

        if self._client._is_workspace:
            # 目录模式：只响应 .sdl 文件
            if src.suffix == ".sdl":
                self._client._changed_file = src
                self._client._on_file_changed()
        else:
            # 单文件模式：只响应目标文件
            if src == self._client._target_path:
                self._client._changed_file = src
                self._client._on_file_changed()


# ─── WatchClient ────────────────────────────────────────


class WatchClient:
    """文件/目录监听 + 可选 WebSocket 广播客户端

    用法::

        # 单文件
        client = WatchClient("article.sdl", port=9000)

        # 目录 (workspace)
        client = WatchClient("scripts/", port=9000)

        @client.on_changed.subscribe
        def handle(filepath: str, raw: str) -> None:
            result = compile(raw)
            client.send_event(ChangedEvent(data=result, raw=raw))
    """

    def __init__(self, path: str, port: int = 0) -> None:
        _p = Path(path).resolve()
        self._is_workspace = _p.is_dir()
        self._target_path = _p
        self.port = port

        self._observer = Observer()
        self._server: Server | None = None
        self._clients: set[ServerConnection] = set()
        self._loop: asyncio.AbstractEventLoop | None = None
        self._changed_file: Path | None = None

        self.on_changed = EventSubscriber()
        """文件变更时触发，回调参数 `(filepath: str, raw: str)`

        用法::

            @client.on_changed.subscribe
            def handle_change(filepath: str, raw: str) -> None:
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
        """watchdog 通知文件已修改 —— 读取并通过 on_changed 广播"""
        fp = self._changed_file
        if fp is None:
            return
        try:
            raw = fp.read_text(encoding="utf-8")
        except OSError:
            return
        self.on_changed.emit(str(fp), raw)

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
                pass
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
        if self._is_workspace:
            watch_dir = str(self._target_path)
            self._observer.schedule(handler, watch_dir, recursive=True)
        else:
            watch_dir = str(self._target_path.parent)
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
