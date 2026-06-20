"""Scallion 剧本描述语言的抽象语法树节点定义"""

from __future__ import annotations

from typing import Annotated, Literal, Union

from pydantic import BaseModel, Field


# ─── 语句基类 ───────────────────────────────────────────


class Statement(BaseModel):
    """所有语句的基类 —— kind 用作 JSON 判别，label 为可选标签"""

    kind: str
    label: str | None = None


# ─── 具体语句 ───────────────────────────────────────────


class Enter(Statement):
    """enter Name:emotion —— 角色声明（冒号后为心情）"""

    kind: Literal["enter"] = "enter"  # type: ignore[assignment]
    name: str
    emotion: str


class Focus(Statement):
    """focus Name —— 聚焦角色（后续 talk 由该角色发言）"""

    kind: Literal["focus"] = "focus"  # type: ignore[assignment]
    name: str


class Unfocus(Statement):
    """unfocus Name —— 取消聚焦"""

    kind: Literal["unfocus"] = "unfocus"  # type: ignore[assignment]
    name: str


class Talk(Statement):
    """
    talk& text  —— 自动推进（动画播完自动进入下一句，配合 select 使用）
    talk  text  —— 等待玩家点击后推进
    """

    kind: Literal["talk"] = "talk"  # type: ignore[assignment]
    text: str
    auto_advance: bool = False  # True = talk& (自动), False = talk (等待点击)


class Select(Statement):
    """select { options } -> variable —— 分支选择"""

    kind: Literal["select"] = "select"  # type: ignore[assignment]
    options: list[str]
    variable: str


class Jump(Statement):
    """
    jump label           —— 无条件跳转（condition=None, mappings={}）
    jump var { 0:l1, 1:l2 } —— 条件跳转
    """

    kind: Literal["jump"] = "jump"  # type: ignore[assignment]
    condition: str | None = None  # 条件变量名；None 表示无条件跳转
    mappings: dict[str, str] = Field(default_factory=dict)  # 值 → 标签


class Title(Statement):
    """*name —— 剧本标题声明，只能出现在文件第一条"""

    kind: Literal["title"] = "title"  # type: ignore[assignment]
    name: str


class Exit(Statement):
    """exit —— 终止"""

    kind: Literal["exit"] = "exit"  # type: ignore[assignment]


# ─── 判别联合类型（排在所有子类之后，供 LabeledStatement 和 Script 使用）───

StatementType = Union[
    Title,
    Enter,
    Focus,
    Unfocus,
    Talk,
    Select,
    Jump,
    Exit,
]


# ─── 顶层节点 ───────────────────────────────────────────


class Script(BaseModel):
    """整个剧本的根节点"""

    statements: list[Annotated[StatementType, Field(discriminator="kind")]] = Field(
        default_factory=list
    )
