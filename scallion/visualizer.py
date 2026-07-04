"""Scallion AST 可视化输出"""

from rich.text import Text

from .ast_nodes import (
    DirectJump,
    Enter,
    Exit,
    Focus,
    MappingJump,
    Play,
    Script,
    Select,
    Talk,
    Unfocus,
)


class Visualizer:
    def __init__(self, script: Script | None = None, highlight: bool = True) -> None:
        self.script = script
        self.highlight = highlight
        self.lines: list[str] = []
        self.prefix = ""
        self.tag: str | None = None

    def print(self, script: Script | None = None) -> str:
        if script is not None:
            self.script = script
        if self.script is None:
            raise ValueError("No script node given.")
        self.lines.clear()
        self.add_line("[white]", use_prefix=False, use_tag=False)
        self.parse_lines()
        self.add_line("[/white]", use_prefix=False, use_tag=False)
        text = Text("\n".join(self.lines))
        return text.markup if self.highlight else text.plain

    def prefix_indent(self, level: int) -> str:
        return "│   " * level

    def parse_lines(self):
        if self.script is None:
            return
        self.add_line(
            f"[green]Script[/green]{f'《[bold]{self.script.title}[/bold]》' if self.script.title else ''}",
            use_tag=False,
            use_prefix=False,
        )
        if self.script.statements:
            self.add_line(
                "[blue bold]statements[/blue bold]:",
                use_tag=False,
                prefix_override=self.prefix_indent(1),
            )
            for stmt in self.script.statements:
                self.prefix = self.prefix_indent(2)
                self.tag = stmt.label
                if isinstance(stmt, Enter):
                    self.add_statement(
                        "Enter",
                        {
                            "name": stmt.name,
                            "emotion": stmt.emotion,
                        },
                    )
                elif isinstance(stmt, Focus):
                    self.add_statement("Focus", {"name": stmt.name})
                elif isinstance(stmt, Unfocus):
                    self.add_statement("Unfocus", {"name": stmt.name})
                elif isinstance(stmt, Talk):
                    mode = "auto" if stmt.await_ else "click"
                    self.add_statement("Talk", {"mode": mode, "text": stmt.text})
                elif isinstance(stmt, Play):
                    mode = "await" if stmt.await_ else "fire"
                    self.add_statement(
                        "Play",
                        {
                            "mode": mode,
                            "resource": stmt.resource,
                        },
                    )
                elif isinstance(stmt, Select):
                    self.add_statement("Select", {"variable": stmt.variable})
                    for i, opt in enumerate(stmt.options):
                        self.add_line(
                            f"[bold]{opt}[/bold] → [blue]{i}[/blue]",
                            use_tag=False,
                            prefix_override=self.prefix_indent(3),
                        )
                elif isinstance(stmt, DirectJump):
                    self.add_statement("DirectJump", {"target": stmt.target})
                elif isinstance(stmt, MappingJump):
                    self.add_statement("MappingJump", {"condition": stmt.condition})
                    for key, label in stmt.mappings.items():
                        self.add_line(
                            f"[blue]{key}[/blue] → [magenta]{label}[/magenta]",
                            use_tag=False,
                            prefix_override=self.prefix_indent(3),
                        )
                elif isinstance(stmt, Exit):
                    self.add_statement("Exit", {})
                else:
                    self.add_line(stmt.__class__.__name__)

    def add_line(
        self,
        data: str,
        use_prefix: bool = True,
        use_tag: bool = True,
        prefix_override: str | None = None,
    ):
        p = (
            prefix_override
            if prefix_override is not None
            else (self.prefix if use_prefix else "")
        )
        t = f"[magenta]\\[{self.tag}][/magenta] " if use_tag and self.tag else ""
        self.lines.append(f"{p}{t}{data}")

    def add_statement(self, name: str, args: dict[str, str]):
        params = ", ".join(
            f"[blue]{key}[/blue]=[bold]{args[key]!r}[/bold]" for key in args
        )
        self.add_line(f"[green]{name}[/green]({params})")
