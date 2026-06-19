"""Scallion 剧本描述语言的词法分析器 + 递归下降解析器"""

import re
from typing import List, Optional

from .ast_nodes import (
    Script,
    Enter,
    Focus,
    Unfocus,
    Talk,
    Select,
    Jump,
    LabeledStatement,
    Exit,
    Statement,
)

# ─── 词法分析 ───────────────────────────────────────────

# 标识符：字母/下划线开头，可包含字母数字下划线和 ?
ID_RE = r"[a-zA-Z_]\w*\??"

TOKEN_SPEC = [
    ("ENTER", r"enter\b"),
    ("FOCUS", r"focus\b"),
    ("UNFOCUS", r"unfocus\b"),
    ("TALK", r"talk&"),
    ("SELECT", r"select\b"),
    ("JUMP", r"jump\b"),
    ("EXIT", r"exit\b"),
    ("LABEL", ID_RE + r"#"),  # label#
    ("ARROW", r"->"),
    ("LBRACE", r"\{"),
    ("RBRACE", r"\}"),
    ("COLON", r":"),
    ("OPTION", r"\d+"),  # 数字选项键
    ("ID", ID_RE),  # 标识符（含可选的 ?）
    ("TEXT", r"[^\n]+"),  # 对话文本（剩余行内容）
    ("NEWLINE", r"\n"),
    ("SKIP", r"[ \t]+"),
    ("COMMENT", r"//[^\n]*"),
]

TOKEN_RE = "|".join(f"(?P<{name}>{pattern})" for name, pattern in TOKEN_SPEC)


class Token:
    __slots__ = ("kind", "value", "line", "col")

    def __init__(self, kind: str, value: str, line: int, col: int):
        self.kind = kind
        self.value = value
        self.line = line
        self.col = col

    def __repr__(self):
        return f"Token({self.kind!r}, {self.value!r})"


def tokenize(source: str) -> List[Token]:
    """将源码字符串转为 Token 列表"""
    tokens: List[Token] = []
    line_no = 1
    line_start = 0

    for m in re.finditer(TOKEN_RE, source, re.MULTILINE):
        kind = m.lastgroup
        assert kind is not None
        value = m.group()
        col = m.start() - line_start + 1

        if kind == "NEWLINE":
            # 检查当前行是否已有有意义 token，如果有则插入一个隐式 NEWLINE
            # 但实际解析时我们按行处理更方便
            tokens.append(Token("NEWLINE", "\n", line_no, col))
            line_no += 1
            line_start = m.end()
        elif kind == "SKIP" or kind == "COMMENT":
            continue
        elif kind == "TEXT":
            # TEXT 只在特定上下文使用，但这里先作为回退 token
            tokens.append(Token(kind, value.strip(), line_no, col))
        else:
            tokens.append(Token(kind, value, line_no, col))

    return tokens


# ─── 解析器 ─────────────────────────────────────────────


class ParseError(Exception):
    def __init__(self, msg: str, line: int = 0, col: int = 0):
        super().__init__(f"第{line}行第{col}列: {msg}" if line else msg)


class Parser:
    """递归下降解析器 —— 按行解析"""

    def __init__(self, source: str):
        # 预处理：去除空行和纯注释行，保留有意义行，去掉行尾空白
        self.lines: List[str] = []
        self.line_numbers: List[int] = []  # 原始行号映射
        for i, raw in enumerate(source.splitlines(), 1):
            line = raw.strip()
            if line and not line.startswith("//"):
                self.lines.append(line)
                self.line_numbers.append(i)

        self.pos: int = 0

    # ── 工具方法 ──────────────────────────────────────

    @property
    def current_line(self) -> Optional[str]:
        return self.lines[self.pos] if self.pos < len(self.lines) else None

    @property
    def current_ln(self) -> int:
        if self.pos < len(self.lines):
            return self.line_numbers[self.pos]
        return 0

    def advance(self) -> Optional[str]:
        line = self.current_line
        self.pos += 1
        return line

    def peek(self, offset: int = 0) -> Optional[str]:
        idx = self.pos + offset
        return self.lines[idx] if 0 <= idx < len(self.lines) else None

    def is_at_end(self) -> bool:
        return self.pos >= len(self.lines)

    def error(self, msg: str) -> ParseError:
        return ParseError(msg, self.current_ln)

    # ── 顶层解析 ─────────────────────────────────────

    def parse(self) -> Script:
        """Script → Enter* Statement*"""
        enters: List[Enter] = []
        statements: List[Statement] = []

        # 先解析所有 enter 声明（集中在开头）
        while not self.is_at_end():
            line = self.current_line
            assert line is not None
            if not line.startswith("enter "):
                break
            enters.append(self.parse_enter())

        # 解析剩余语句
        while not self.is_at_end():
            stmt = self.parse_statement()
            if stmt is not None:
                statements.append(stmt)

        return Script(enters=enters, statements=statements)

    def parse_enter(self) -> Enter:
        """enter Name:emotion"""
        line = self.advance()
        assert line is not None
        # 去掉 'enter ' 前缀
        rest = line[6:].strip()
        # 用最后一个冒号分割（名称中可能有冒号，但这里名称是简单标识符）
        if ":" not in rest:
            raise self.error(f"enter 语句缺少冒号: {line}")
        name, emotion = rest.rsplit(":", 1)
        name = name.strip()
        emotion = emotion.strip()
        if not name:
            raise self.error("enter 语句缺少角色名")
        if not emotion:
            raise self.error("enter 语句缺少心情")
        return Enter(name=name, emotion=emotion)

    # ── 语句解析 ─────────────────────────────────────

    def parse_statement(self) -> Optional[Statement]:
        """解析一条语句，可能带有标签前缀"""
        if self.is_at_end():
            return None

        line = self.current_line
        assert line is not None

        # 检查 label# 前缀
        label_match = re.match(r"^([a-zA-Z_]\w*\??)#(.*)", line)
        if label_match:
            self.advance()  # 消费该行
            label = label_match.group(1)
            rest = label_match.group(2).strip()
            if not rest:
                # label# 后面没有内容，看作标签值为空
                return LabeledStatement(
                    label=label,
                    statement=Exit(),
                )
            # 解析标签后面的语句
            inner = self.parse_inline_stmt(rest)
            return LabeledStatement(label=label, statement=inner)

        # 直接语句
        line = self.advance()
        assert line is not None
        return self.parse_inline_stmt(line)

    def parse_inline_stmt(self, line: str) -> Statement:
        """从单行文本解析语句"""
        line = line.strip()

        if line.startswith("focus "):
            name = line[6:].strip()
            if not name:
                raise self.error("focus 语句缺少角色名")
            return Focus(name=name)

        elif line.startswith("unfocus "):
            name = line[8:].strip()
            if not name:
                raise self.error("unfocus 语句缺少角色名")
            return Unfocus(name=name)

        elif line.startswith("talk&") or line.startswith("talk "):
            # talk& → auto_advance=True（动画播完自动推进）
            # talk  → auto_advance=False（等待玩家点击）
            auto = line.startswith("talk&")
            idx = 5 if auto else 4
            text = line[idx:].strip()
            return Talk(text=text, auto_advance=auto)

        elif line.startswith("select "):
            return self.parse_select(line)

        elif line.startswith("jump "):
            return self.parse_jump(line)

        elif line == "exit":
            return Exit()

        else:
            raise self.error(f"无法识别的语句: {line}")

    def parse_select(self, line: str) -> Select:
        """
        select {
            option1
            option2
        } -> variable
        """
        # 收集所有相关行（可能是多行）
        block_lines = [line]
        # 如果在同一行没有找到 '} ->'，则继续读行
        if "} ->" not in line:
            while not self.is_at_end():
                nxt = self.advance()
                assert nxt is not None
                block_lines.append(nxt)
                if "} ->" in nxt:
                    break

        full = "\n".join(block_lines)

        # 提取选项块
        block_match = re.search(r"\{(.+?)\}", full, re.DOTALL)
        if not block_match:
            raise self.error("select 语句缺少 { }")

        options_text = block_match.group(1).strip()
        options = [opt.strip() for opt in options_text.splitlines() if opt.strip()]

        # 提取变量名
        arrow_match = re.search(r"->\s*(\w+)", full)
        if not arrow_match:
            raise self.error("select 语句缺少 -> variable")
        variable = arrow_match.group(1)

        return Select(options=options, variable=variable)

    def parse_jump(self, line: str) -> Jump:
        """
        jump label                → 无条件跳转
        jump var { 0:label, ... } → 条件跳转
        """
        rest = line[5:].strip()  # 去掉 'jump '

        # 无条件跳转：jump label
        if "{" not in rest:
            return Jump(condition=None, mappings={rest: rest})

        # 条件跳转：jump var { 0:l1, 1:l2 }
        cond_match = re.match(r"^([a-zA-Z_]\w*\??)\s*\{", rest)
        if not cond_match:
            raise self.error(f"jump 语句格式错误: {line}")

        condition = cond_match.group(1)

        # 提取 { } 中的映射
        block_lines = [rest]
        if "}" not in rest:
            while not self.is_at_end():
                nxt = self.advance()
                assert nxt is not None
                block_lines.append(nxt)
                if "}" in nxt:
                    break

        full = "\n".join(block_lines)
        block_match = re.search(r"\{(.+?)\}", full, re.DOTALL)
        if not block_match:
            raise self.error("jump 语句缺少 { }")

        mappings_text = block_match.group(1).strip()
        mappings: dict[str, str] = {}
        for entry in mappings_text.splitlines():
            entry = entry.strip()
            if not entry:
                continue
            if ":" not in entry:
                raise self.error(f"jump 映射格式错误: {entry}")
            key, val = entry.split(":", 1)
            mappings[key.strip()] = val.strip()

        return Jump(condition=condition, mappings=mappings)
