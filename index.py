import asyncio

from scallion import Scallion
from scallion.cli import arguments
from scallion.visualizer import Visualizer
from scallion.watcher import ChangedEvent, WatchClient
from rich.console import Console

scallion = Scallion()
visualizer = Visualizer()
console = Console(highlight=False)


def compile_script(raw: str) -> str:
    """编译回调：解析 → 可视化 → 写 JSON → 返回编译结果"""
    script = scallion.parse(raw)
    result = script.model_dump_json(
        indent=arguments.format if arguments.format > 0 else None,
        by_alias=True,
    )

    if arguments.output:
        with open(arguments.output, "w", encoding="utf-8") as f:
            f.write(result)

    dumper = visualizer.print(script)
    console.print(dumper)
    return result


async def watch_mode() -> None:
    """watch 模式：启动文件监听 + 可选 WebSocket 服务器"""
    client = WatchClient(arguments.filename, arguments.port)

    @client.on_changed.subscribe
    def handle_changed(raw: str) -> None:
        """文件变更 → 编译 → WebSocket 广播"""
        result = compile_script(raw)
        if arguments.port > 0:
            client.send_event(ChangedEvent(data=result, raw=raw))

    async with client:
        # 首次编译 + 广播
        raw = open(arguments.filename, "r", encoding="utf-8").read()
        handle_changed(raw)

        # 阻塞直到用户中断
        try:
            await asyncio.Future()
        except asyncio.CancelledError:
            pass


if arguments.watch:
    asyncio.run(watch_mode())
else:
    raw = open(arguments.filename, "r", encoding="utf-8").read()
    compile_script(raw)
