"""Scallion 剧本模拟播放器 —— 纯事件驱动，与平台解耦

设计原则：
  - Scallion 只负责：解析剧本 → 控制运行时状态 → 发布事件 / 接收输入
  - 文本输出、UI 渲染等由外部订阅事件自行实现
  - 通过 EventSubscriber 发布事件，通过 async 机制等待外部输入

用法示例::

    from scallion import Scallion, SimulatePlayer

    scallion = Scallion()
    player = SimulatePlayer()

    @player.on_talk.subscribe
    def handle_talk(text, speaker, emotion, auto_advance):
        print(f"{speaker}: {text}")
        if not auto_advance:
            input("按回车继续...")
            player.advance()

    @player.on_select.subscribe
    def handle_select(options, variable):
        choice = int(input(f"请选择 0~{len(options)-1}: "))
        player.choose(choice)

    @player.on_end.subscribe
    def handle_end():
        print("剧终")

    script = scallion.parse(source)
    asyncio.run(player.play(script))
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from typing import Any

from .ast_nodes import Script, Statement
from .event_subscriber import EventSubscriber


class PlayerState:
    """播放器内部运行时状态（外部不应直接访问）"""

    __slots__ = (
        "index",
        "focused",
        "characters",
        "variables",
        "running",
        "_advance_event",
        "_pending_choice",
    )

    def __init__(self) -> None:
        self.index: int = 0
        self.focused: str | None = None
        self.characters: dict[str, str] = {}  # name → emotion
        self.variables: dict[str, str] = {}  # select 变量值
        self.running: bool = False
        self._advance_event: asyncio.Event = asyncio.Event()
        self._pending_choice: int | None = None

    def reset(self) -> None:
        self.index = 0
        self.focused = None
        self.characters.clear()
        self.variables.clear()
        self.running = False
        self._advance_event.clear()
        self._pending_choice = None


class SimulatePlayer:
    """剧本模拟播放器

    事件（EventSubscriber 实例，外部通过 .subscribe 注册回调）:
      - on_start(title)          剧本开始
      - on_enter(name, emotion)  角色登场
      - on_focus(name)           镜头聚焦
      - on_unfocus(name)         取消聚焦
      - on_talk(text, speaker, emotion, auto_advance)  对话
      - on_play(resource, auto_advance)                播放资源
      - on_select(options, variable)                   选择分支
      - on_end()                剧本结束
      - on_error(message)       错误发生

    外部输入方法:
      - advance()     推进（用于 talk 等待点击 / play& 等待播完）
      - choose(index)  选择选项
      - stop()         强制停止
    """

    # ── 事件发布器 ──────────────────────────────────

    on_start: EventSubscriber  # (title: str)
    on_enter: EventSubscriber  # (name: str, emotion: str)
    on_focus: EventSubscriber  # (name: str)
    on_unfocus: EventSubscriber  # (name: str)
    on_talk: (
        EventSubscriber  # (text: str, speaker: str, emotion: str, auto_advance: bool)
    )
    on_play: EventSubscriber  # (resource: str, auto_advance: bool)
    on_select: EventSubscriber  # (options: list[str], variable: str)
    on_end: EventSubscriber  # ()
    on_error: EventSubscriber  # (message: str)

    def __init__(self) -> None:
        self.on_start = EventSubscriber()
        self.on_enter = EventSubscriber()
        self.on_focus = EventSubscriber()
        self.on_unfocus = EventSubscriber()
        self.on_talk = EventSubscriber()
        self.on_play = EventSubscriber()
        self.on_select = EventSubscriber()
        self.on_end = EventSubscriber()
        self.on_error = EventSubscriber()

        self._state = PlayerState()
        self._label_map: dict[str, int] = {}

    # ── 外部输入 ────────────────────────────────────

    def advance(self) -> None:
        """推进剧情（talk / play& 等待时调用）"""
        self._state._advance_event.set()

    def choose(self, index: int) -> None:
        """选择一个选项（on_select 触发后调用）"""
        self._state._pending_choice = index
        self._state._advance_event.set()

    def stop(self) -> None:
        """强制停止播放"""
        self._state.running = False
        self._state._advance_event.set()  # 唤醒可能正在等待的 play()

    # ── 播放入口 ────────────────────────────────────

    async def play(self, script: Script) -> None:
        """从 Script 节点开始播放剧本"""
        self._state.reset()
        self._state.running = True

        # 构建 label → index 映射
        self._label_map.clear()
        for idx, stmt in enumerate(script.statements):
            if stmt.label:
                self._label_map[stmt.label] = idx

        title = script.title or "未命名剧本"
        self.on_start(title)

        try:
            await self._run_loop(script)
        except Exception as e:
            self.on_error(str(e))
        finally:
            self._state.running = False

    # ── 内部运行循环 ────────────────────────────────

    async def _run_loop(self, script: Script) -> None:
        statements = script.statements
        st = self._state

        while st.running and st.index < len(statements):
            stmt = statements[st.index]
            handler = self._HANDLERS.get(stmt.kind)
            if handler is None:
                st.index += 1
                continue
            await handler(self, stmt, st)

        if st.running:
            self.on_end()

    # ── 各语句处理器 ────────────────────────────────

    async def _handle_enter(self, stmt: Statement, st: PlayerState) -> None:
        from .ast_nodes import Enter

        assert isinstance(stmt, Enter)
        st.characters[stmt.name] = stmt.emotion
        self.on_enter(stmt.name, stmt.emotion)
        st.index += 1

    async def _handle_focus(self, stmt: Statement, st: PlayerState) -> None:
        from .ast_nodes import Focus

        assert isinstance(stmt, Focus)
        st.focused = stmt.name
        self.on_focus(stmt.name)
        st.index += 1

    async def _handle_unfocus(self, stmt: Statement, st: PlayerState) -> None:
        from .ast_nodes import Unfocus

        assert isinstance(stmt, Unfocus)
        if st.focused == stmt.name:
            st.focused = None
        self.on_unfocus(stmt.name)
        st.index += 1

    async def _handle_talk(self, stmt: Statement, st: PlayerState) -> None:
        from .ast_nodes import Talk

        assert isinstance(stmt, Talk)
        speaker = st.focused or "???"
        emotion = st.characters.get(speaker, "normal")
        self.on_talk(stmt.text, speaker, emotion, stmt.await_)
        st.index += 1

        if not stmt.await_:
            # talk（无 &）→ 等待外部 advance()
            await self._wait_advance()

    async def _handle_play(self, stmt: Statement, st: PlayerState) -> None:
        from .ast_nodes import Play

        assert isinstance(stmt, Play)
        self.on_play(stmt.resource, stmt.await_)
        st.index += 1
        # 模拟运行不等待，直接继续

    async def _handle_select(self, stmt: Statement, st: PlayerState) -> None:
        from .ast_nodes import Select

        assert isinstance(stmt, Select)
        self.on_select(stmt.options, stmt.variable)

        # 等待外部 choose()
        await self._wait_choice()
        if not st.running:
            return

        choice = st._pending_choice
        if choice is not None and 0 <= choice < len(stmt.options):
            st.variables[stmt.variable] = str(choice)
        st._pending_choice = None
        st.index += 1

    async def _handle_direct_jump(self, stmt: Statement, st: PlayerState) -> None:
        from .ast_nodes import DirectJump

        assert isinstance(stmt, DirectJump)
        target_idx = self._label_map.get(stmt.target)
        if target_idx is not None:
            st.index = target_idx
        else:
            self.on_error(f"跳转目标 #{stmt.target} 未找到")
            st.running = False

    async def _handle_mapping_jump(self, stmt: Statement, st: PlayerState) -> None:
        from .ast_nodes import MappingJump

        assert isinstance(stmt, MappingJump)
        var_value = st.variables.get(stmt.condition, "0")
        target_label = stmt.mappings.get(var_value)
        if target_label and target_label in self._label_map:
            st.index = self._label_map[target_label]
        elif stmt.mappings:
            # 兜底走第一条
            first_label = list(stmt.mappings.values())[0]
            if first_label in self._label_map:
                st.index = self._label_map[first_label]
            else:
                self.on_error("条件跳转无匹配分支")
                st.running = False
        else:
            self.on_error("条件跳转无匹配分支")
            st.running = False

    async def _handle_exit(self, stmt: Statement, st: PlayerState) -> None:
        st.running = False
        self.on_end()

    # ── 内部等待机制 ────────────────────────────────

    async def _wait_advance(self) -> None:
        """等待外部调用 advance() 或 stop()"""
        st = self._state
        st._advance_event.clear()
        await st._advance_event.wait()

    async def _wait_choice(self) -> None:
        """等待外部调用 choose() 或 stop()"""
        st = self._state
        st._advance_event.clear()
        await st._advance_event.wait()

    # ── 处理器路由表 ────────────────────────────────

    _HANDLERS: dict[str, Callable[..., Any]] = {
        "enter": _handle_enter,
        "focus": _handle_focus,
        "unfocus": _handle_unfocus,
        "talk": _handle_talk,
        "play": _handle_play,
        "select": _handle_select,
        "direct_jump": _handle_direct_jump,
        "mapping_jump": _handle_mapping_jump,
        "exit": _handle_exit,
    }
