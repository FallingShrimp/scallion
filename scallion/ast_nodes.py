"""Scallion 剧本描述语言的抽象语法树节点定义"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional


# ─── 顶层节点 ───────────────────────────────────────────


@dataclass
class Script:
    """整个剧本的根节点"""

    statements: List["Statement"]


# ─── 语句基类 ───────────────────────────────────────────


class Statement:
    """所有语句的基类"""

    pass


@dataclass
class Enter(Statement):
    """enter Name:emotion —— 角色声明（冒号后为心情）"""

    name: str
    emotion: str


@dataclass
class Focus(Statement):
    """focus Name —— 聚焦角色（后续 talk 由该角色发言）"""

    name: str


@dataclass
class Unfocus(Statement):
    """unfocus Name —— 取消聚焦"""

    name: str


@dataclass
class Talk(Statement):
    """
    talk& text  —— 自动推进（动画播完自动进入下一句，配合 select 使用）
    talk  text  —— 等待玩家点击后推进
    """

    text: str
    auto_advance: bool = False  # True = talk& (自动), False = talk (等待点击)


@dataclass
class Select(Statement):
    """select { options } -> variable —— 分支选择"""

    options: List[str]
    variable: str


@dataclass
class Jump(Statement):
    """
    jump label           —— 无条件跳转（condition=None, mappings={}）
    jump var { 0:l1, 1:l2 } —— 条件跳转
    """

    condition: Optional[str] = None  # 条件变量名；None 表示无条件跳转
    mappings: Dict[str, str] = field(default_factory=dict)  # 值 → 标签


@dataclass
class LabeledStatement(Statement):
    """label#action —— 带标签的语句"""

    label: str
    statement: Statement


@dataclass
class Exit(Statement):
    """exit —— 终止"""

    pass
