"""Scallion 剧本描述语言 —— 词法分析器 + 递归下降解析器"""

import re

from .ast_nodes import (
    DirectJump,
    Enter,
    Exit,
    Focus,
    MappingJump,
    Play,
    Script,
    Select,
    Statement,
    Talk,
    Unfocus,
)

# ─── 标识符定义（唯一常量，扩展只需改此处）─────────────

ID_RE = r"[a-zA-Z_]\w*\??"

# ─── Token 定义 ────────────────────────────────────────
# 顺序敏感：关键字优先于 ID，结构符优先于 TEXT

TOKEN_SPEC: list[tuple[str, str]] = [
    # 关键字
    ("ENTER", r"enter\b"),
    ("FOCUS", r"focus\b"),
    ("UNFOCUS", r"unfocus\b"),
    ("PLAY_AWAIT", r"play&"),
    ("PLAY_NOWAIT", r"play\b"),
    ("TALK_AUTO", r"talk&"),
    ("TALK_CLICK", r"talk\b"),
    ("SELECT", r"select\b"),
    ("JUMP", r"jump\b"),
    ("EXIT", r"exit\b"),
    # 结构符号
    ("STAR", r"\*"),
    ("LBRACE", r"\{"),
    ("RBRACE", r"\}"),
    ("ARROW", r"->"),
    ("COLON", r":"),
    ("HASH", r"#"),
    # 字面量
    ("INTEGER", r"\d+"),
    ("ID", ID_RE),
    # 自由文本（非空白开头直到行尾）
    # 空白 / 注释
    ("NEWLINE", r"\n"),
    ("SKIP", r"[ \t]+"),
    ("COMMENT", r"//[^\n]*"),
    ("TEXT", r"[^\s][^\n]*"),
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


# ─── 词法分析 ───────────────────────────────────────────


def tokenize(source: str) -> list[Token]:
    """将源码字符串转为 Token 列表，滤除 SKIP 和 COMMENT"""
    tokens: list[Token] = []
    line_no = 1
    line_start = 0

    for m in re.finditer(TOKEN_RE, source, re.MULTILINE):
        kind = m.lastgroup
        assert kind is not None
        value = m.group()
        col = m.start() - line_start + 1

        if kind == "NEWLINE":
            tokens.append(Token("NEWLINE", "\n", line_no, col))
            line_no += 1
            line_start = m.end()
        elif kind in ("SKIP", "COMMENT"):
            continue
        else:
            if kind == "TEXT" and "//" in value:
                value = value.split("//", 1)[0].rstrip()
                if not value:
                    continue
            tokens.append(Token(kind, value, line_no, col))

    # 确保末尾有 NEWLINE，简化解析器
    if not tokens or tokens[-1].kind != "NEWLINE":
        tokens.append(Token("NEWLINE", "\n", line_no, 1))

    return tokens


# ─── 解析器 ─────────────────────────────────────────────


class ParseError(Exception):
    def __init__(self, msg: str, token: Token | None = None):
        if token:
            super().__init__(
                f"第{token.line}行第{token.col}列: {msg}\n  当前 token: {token}"
            )
        else:
            super().__init__(msg)


class Parser:
    """递归下降解析器 —— 基于 Token 流"""

    def __init__(self, source: str):
        self.tokens: list[Token] = tokenize(source)
        self.pos: int = 0

    # ── Token 工具 ───────────────────────────────────

    @property
    def current(self) -> Token:
        return self.tokens[self.pos]

    def advance(self) -> Token:
        tok = self.current
        self.pos += 1
        return tok

    def peek(self, offset: int = 0) -> Token:
        idx = self.pos + offset
        if idx < len(self.tokens):
            return self.tokens[idx]
        # 返回哨兵 NEWLINE，避免 None 判断
        return Token("NEWLINE", "\n", 0, 0)

    def check(self, *kinds: str) -> bool:
        return self.current.kind in kinds

    def consume(self, kind: str, label: str = "") -> Token:
        """消费一个期望类型的 token，否则报错"""
        tok = self.current
        if tok.kind != kind:
            expected = label or kind
            raise ParseError(f"期望 {expected}，实际为 {tok}", tok)
        return self.advance()

    def skip_newlines(self) -> None:
        """跳过空白行"""
        while self.pos < len(self.tokens) and self.check("NEWLINE"):
            self.advance()

    # ── 顶层解析 ─────────────────────────────────────

    def parse(self) -> Script:
        """Script → Title? Statement*"""
        title: str | None = None
        statements: list[Statement] = []

        if len(self.tokens) == 0:
            return Script(title=None, statements=[])
        self.skip_newlines()
        if self.pos < len(self.tokens) and self.check("STAR"):
            title = self.parse_title()

        while self.pos < len(self.tokens):
            self.skip_newlines()
            if self.pos >= len(self.tokens):
                break
            stmt = self.parse_statement()
            if stmt is not None:
                statements.append(stmt)

        return Script(title=title, statements=statements)  # type: ignore[arg-type]

    def parse_title(self) -> str:
        """STAR TEXT* NEWLINE → 返回标题字符串"""
        self.consume("STAR")
        parts: list[str] = []
        while not self.check("NEWLINE"):
            parts.append(self.advance().value)
        self.consume("NEWLINE")
        return " ".join(parts)

    def parse_enter(self) -> Enter:
        """enter ID : ID NEWLINE"""
        self.consume("ENTER")
        name = self.consume("ID", "角色名").value
        self.consume("COLON")
        emotion = self.consume("ID", "心情").value
        self.consume("NEWLINE")
        return Enter(name=name, emotion=emotion)

    # ── 语句解析 ─────────────────────────────────────

    def parse_statement(self) -> Statement | None:
        """
        Statement → [ID HASH] Action
        """
        if self.check("ID") and self.peek(1).kind == "HASH":
            # label#action
            label = self.advance().value
            self.consume("HASH")
            stmt: Statement
            if self.check("NEWLINE"):
                # label# 后面没有内容，视为 exit
                self.advance()
                stmt = Exit()
            else:
                stmt = self.parse_action()
            stmt.label = label
            return stmt

        return self.parse_action()

    def parse_action(self) -> Statement:
        """
        Action → enter ID : ID NEWLINE
               | focus ID NEWLINE
               | unfocus ID NEWLINE
               | TALK_AUTO TEXT NEWLINE
               | TALK_CLICK TEXT NEWLINE
               | select LBRACE NEWLINE TEXT* RBRACE ARROW ID NEWLINE
               | jump ID ( LBRACE ... )? NEWLINE
               | exit NEWLINE
        """
        tok = self.current

        if tok.kind == "ENTER":
            return self.parse_enter()

        elif tok.kind == "FOCUS":
            self.advance()
            name = self.consume("ID", "角色名").value
            self.consume("NEWLINE")
            return Focus(name=name)

        elif tok.kind == "UNFOCUS":
            self.advance()
            name = self.consume("ID", "角色名").value
            self.consume("NEWLINE")
            return Unfocus(name=name)

        elif tok.kind in ("TALK_AUTO", "TALK_CLICK"):
            auto = tok.kind == "TALK_AUTO"
            self.advance()
            # 收集直到行尾的全部 token 作为对话文本
            parts: list[str] = []
            while not self.check("NEWLINE"):
                parts.append(self.advance().value)
            text = "".join(parts)
            self.consume("NEWLINE")
            return Talk.model_validate({"text": text, "await": not auto})

        elif tok.kind in ("PLAY_AWAIT", "PLAY_NOWAIT"):
            is_await = tok.kind == "PLAY_AWAIT"
            self.advance()
            res_parts: list[str] = []
            while not self.check("NEWLINE"):
                res_parts.append(self.advance().value)
            resource = "".join(res_parts)
            self.consume("NEWLINE")
            return Play.model_validate({"resource": resource, "await": is_await})

        elif tok.kind == "SELECT":
            return self.parse_select()

        elif tok.kind == "JUMP":
            return self.parse_jump()

        elif tok.kind == "EXIT":
            self.advance()
            self.consume("NEWLINE")
            return Exit()

        else:
            raise ParseError(f"无法识别的语句，当前 token: {tok}", tok)

    # ── select 语句 ──────────────────────────────────

    def parse_select(self) -> Select:
        """
        select LBRACE NEWLINE
            (行内全部 token 拼接为选项) NEWLINE
            ...
        RBRACE ARROW ID NEWLINE
        """
        self.consume("SELECT")
        self.consume("LBRACE")
        self.consume("NEWLINE")

        options: list[str] = []
        while not self.check("RBRACE"):
            # 收集一行上的全部 token 作为选项文本
            parts: list[str] = []
            while not self.check("NEWLINE"):
                parts.append(self.advance().value)
            self.consume("NEWLINE")
            options.append("".join(parts))

        self.consume("RBRACE")
        self.consume("ARROW")
        variable = self.consume("ID", "变量名").value
        self.consume("NEWLINE")

        return Select(options=options, variable=variable)

    # ── jump 语句 ────────────────────────────────────

    def parse_jump(self) -> DirectJump | MappingJump:
        """
        jump ID NEWLINE                           → DirectJump
        jump ID LBRACE NEWLINE
            INTEGER COLON ID NEWLINE
            INTEGER COLON ID NEWLINE
        RBRACE NEWLINE                            → MappingJump
        """
        self.consume("JUMP")
        target = self.consume("ID", "跳转目标或条件变量").value

        if self.check("NEWLINE"):
            # 无条件跳转
            self.advance()
            return DirectJump(target=target)

        # 条件跳转
        self.consume("LBRACE")
        self.consume("NEWLINE")

        mappings: dict[str, str] = {}
        while self.check("INTEGER"):
            key = self.advance().value
            self.consume("COLON")
            label = self.consume("ID", "跳转标签").value
            mappings[key] = label
            self.consume("NEWLINE")

        self.consume("RBRACE")
        self.consume("NEWLINE")

        return MappingJump(condition=target, mappings=mappings)
