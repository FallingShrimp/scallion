"""Scallion AST 可视化输出"""

from .ast_nodes import (
    Script, Enter, Focus, Unfocus, Talk,
    Select, Jump, LabeledStatement, Exit, Statement,
)


def print_ast(script: Script) -> str:
    """将 AST 转为带缩进的可读字符串"""
    lines: list[str] = []
    _print_script(script, lines, indent=0)
    return '\n'.join(lines)


def _indent(level: int) -> str:
    return '│   ' * level


def _print_script(script: Script, lines: list[str], indent: int):
    lines.append(f'{_indent(indent)}Script')

    # 角色声明
    if script.enters:
        lines.append(f'{_indent(indent + 1)}enters:')
        for e in script.enters:
            lines.append(
                f'{_indent(indent + 2)}Enter(name={e.name!r}, label={e.label!r})'
            )

    # 语句
    if script.statements:
        lines.append(f'{_indent(indent + 1)}statements:')
        for stmt in script.statements:
            _print_stmt(stmt, lines, indent + 2)


def _print_stmt(stmt: Statement, lines: list[str], indent: int):
    prefix = _indent(indent)

    if isinstance(stmt, LabeledStatement):
        lines.append(f'{prefix}LabeledStatement(label={stmt.label!r}):')
        _print_stmt(stmt.statement, lines, indent + 1)

    elif isinstance(stmt, Focus):
        lines.append(f'{prefix}Focus(name={stmt.name!r})')

    elif isinstance(stmt, Unfocus):
        lines.append(f'{prefix}Unfocus(name={stmt.name!r})')

    elif isinstance(stmt, Talk):
        mode = 'auto' if stmt.auto_advance else 'click'
        lines.append(f'{prefix}Talk(mode={mode!r}, text={stmt.text!r})')

    elif isinstance(stmt, Select):
        lines.append(f'{prefix}Select(variable={stmt.variable!r}):')
        for i, opt in enumerate(stmt.options):
            lines.append(f'{_indent(indent + 1)}option[{i}] = {opt!r}')

    elif isinstance(stmt, Jump):
        if stmt.condition is not None:
            lines.append(f'{prefix}Jump(condition={stmt.condition!r}):')
            for key, label in stmt.mappings.items():
                lines.append(f'{_indent(indent + 1)}{key} → {label!r}')
        else:
            # 无条件跳转
            target = next(iter(stmt.mappings), '?')
            lines.append(f'{prefix}Jump(target={target!r})')

    elif isinstance(stmt, Exit):
        lines.append(f'{prefix}Exit')

    else:
        lines.append(f'{prefix}{stmt.__class__.__name__}')
