"""Scallion AST 可视化输出"""

from .ast_nodes import (
    Script,
    Enter,
    Focus,
    Unfocus,
    Talk,
    Play,
    Select,
    DirectJump,
    MappingJump,
    Exit,
    Statement,
)


def print_ast(script: Script) -> str:
    """将 AST 转为带缩进的可读字符串"""
    lines: list[str] = []
    _print_script(script, lines, indent=0)
    return "\n".join(lines)


def _indent(level: int) -> str:
    return "│   " * level


def _print_script(script: Script, lines: list[str], indent: int):
    title_suffix = f"(title={script.title!r})" if script.title else ""
    lines.append(f"{_indent(indent)}Script{title_suffix}")

    # 语句
    if script.statements:
        lines.append(f"{_indent(indent + 1)}statements:")
        for stmt in script.statements:
            _print_stmt(stmt, lines, indent + 2)


def _print_stmt(stmt: Statement, lines: list[str], indent: int):
    prefix = _indent(indent)

    # 有标签时加前缀
    tag = f"{stmt.label}#" if stmt.label is not None else ""

    if isinstance(stmt, Enter):
        lines.append(
            f"{prefix}{tag}Enter(name={stmt.name!r}, emotion={stmt.emotion!r})"
        )

    elif isinstance(stmt, Focus):
        lines.append(f"{prefix}{tag}Focus(name={stmt.name!r})")

    elif isinstance(stmt, Unfocus):
        lines.append(f"{prefix}{tag}Unfocus(name={stmt.name!r})")

    elif isinstance(stmt, Talk):
        mode = "auto" if stmt.await_ else "click"
        lines.append(f"{prefix}{tag}Talk(mode={mode!r}, text={stmt.text!r})")

    elif isinstance(stmt, Play):
        mode = "await" if stmt.await_ else "fire"
        lines.append(f"{prefix}{tag}Play(mode={mode!r}, resource={stmt.resource!r})")

    elif isinstance(stmt, Select):
        lines.append(f"{prefix}{tag}Select(variable={stmt.variable!r}):")
        for i, opt in enumerate(stmt.options):
            lines.append(f"{_indent(indent + 1)}option[{i}] = {opt!r}")

    elif isinstance(stmt, DirectJump):
        lines.append(f"{prefix}{tag}DirectJump(target={stmt.target!r})")

    elif isinstance(stmt, MappingJump):
        lines.append(f"{prefix}{tag}MappingJump(condition={stmt.condition!r}):")
        for key, label in stmt.mappings.items():
            lines.append(f"{_indent(indent + 1)}{key} → {label!r}")

    elif isinstance(stmt, Exit):
        lines.append(f"{prefix}{tag}Exit")

    else:
        lines.append(f"{prefix}{stmt.__class__.__name__}")
