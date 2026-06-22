import asyncio
import os
from pathlib import Path

from scallion import Scallion
from scallion.cli import arguments
from scallion.visualizer import Visualizer
from scallion.watcher import ChangedEvent, WatchClient
from rich.console import Console

scallion = Scallion()
visualizer = Visualizer()
console = Console(highlight=False)


def compile_script(raw: str) -> str:
    """编译回调：解析 → 可视化 → 返回 JSON 字符串"""
    script = scallion.parse(raw)
    return script.model_dump_json(
        indent=arguments.format if arguments.format > 0 else None,
        by_alias=True,
    )


def compile_and_show(raw: str) -> str:
    """编译 + 可视化输出"""
    result = compile_script(raw)
    script = scallion.parse(raw)
    dumper = visualizer.print(script)
    console.print(dumper)
    return result


def compile_file(input_path: str, output_path: str) -> None:
    """编译单个文件并写入 JSON"""
    raw = Path(input_path).read_text(encoding="utf-8")
    script = scallion.parse(raw)
    result = script.model_dump_json(
        indent=arguments.format if arguments.format > 0 else None,
        by_alias=True,
    )

    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(result)

    console.print(f"[bold]{input_path}[/bold] → [dim]{output_path}[/dim]")
    console.print(visualizer.print(script))


def single_file_mode() -> None:
    """单文件编译模式"""
    raw = Path(arguments.filename).read_text(encoding="utf-8")
    result = compile_and_show(raw)

    if arguments.output:
        with open(arguments.output, "w", encoding="utf-8") as f:
            f.write(result)


def workspace_mode() -> None:
    """目录模式：遍历所有 .sdl 文件，保持目录结构输出"""
    input_root = Path(arguments.filename).resolve()
    output_root = Path(arguments.output).resolve()

    sdl_files = sorted(input_root.rglob("*.sdl"))
    if not sdl_files:
        console.print(f"[yellow]警告: {input_root} 下未找到 .sdl 文件[/yellow]")
        return

    for sdl_file in sdl_files:
        rel = sdl_file.relative_to(input_root)
        out_file = output_root / rel.with_suffix(".json")
        compile_file(str(sdl_file), str(out_file))

    count = len(sdl_files)
    console.print(f"\n[green]完成: 编译了 {count} 个文件 → {output_root}[/green]")


async def watch_mode() -> None:
    """watch 模式：启动文件监听 + 可选 WebSocket 服务器

    单文件：监听目标文件变动 → 编译 → 终端输出 + WS 广播
    目录 (workspace)：递归监听 .sdl 变动 → 编译 → 写 JSON + WS 广播
    """
    client = WatchClient(arguments.filename, arguments.port)
    is_ws = arguments.is_workspace
    input_root = Path(arguments.filename).resolve()
    output_root = Path(arguments.output).resolve() if arguments.output else input_root

    @client.on_changed.subscribe
    def handle_changed(filepath: str, raw: str) -> None:
        fp = Path(filepath)
        result = compile_script(raw)
        console.print(f"[bold dim]{filepath}[/bold dim] 已变更，重新编译")
        console.print(visualizer.print(scallion.parse(raw)))

        if is_ws:
            rel = fp.relative_to(input_root)
            out_file = output_root / rel.with_suffix(".json")
            os.makedirs(os.path.dirname(out_file) or ".", exist_ok=True)
            out_file.write_text(result, encoding="utf-8")
            console.print(f"  → [dim]{out_file}[/dim]")

        if arguments.port > 0:
            client.send_event(ChangedEvent(data=result, raw=raw))

    async with client:
        if is_ws:
            # 首次全量编译
            sdl_files = sorted(input_root.rglob("*.sdl"))
            if not sdl_files:
                console.print(f"[yellow]警告: {input_root} 下未找到 .sdl 文件[/yellow]")
            for sdl_file in sdl_files:
                raw = sdl_file.read_text(encoding="utf-8")
                handle_changed(str(sdl_file), raw)
            console.print(
                f"\n[green]监控中: {len(sdl_files)} 个文件 → [dim]{output_root}[/dim]"
                f"{'  ws://localhost:' + str(arguments.port) if arguments.port > 0 else ''}[/green]"
            )
        else:
            # 首次编译
            raw = input_root.read_text(encoding="utf-8")
            handle_changed(str(input_root), raw)
            label = f" → [dim]{arguments.output}[/dim]" if arguments.output else ""
            console.print(
                f"[green]监控中: {input_root}{label}"
                f"{'  ws://localhost:' + str(arguments.port) if arguments.port > 0 else ''}[/green]"
            )

        try:
            await asyncio.Future()
        except asyncio.CancelledError:
            pass


if arguments.watch:
    asyncio.run(watch_mode())
elif arguments.is_workspace:
    workspace_mode()
else:
    single_file_mode()
