"""Scallion —— 高效剧本描述语言解析器"""

from .parser import Parser, ParseError, tokenize
from .ast_nodes import (
    Script, Enter, Focus, Unfocus, Talk,
    Select, Jump, LabeledStatement, Exit, Statement,
)
from .visualizer import print_ast


class Scallion:
    """Scallion 主入口 —— 解析剧本描述并输出 AST"""

    @staticmethod
    def parse(source: str) -> Script:
        """解析源码字符串，返回 AST"""
        parser = Parser(source)
        return parser.parse()

    @staticmethod
    def parse_file(filepath: str) -> Script:
        """从文件解析，返回 AST"""
        with open(filepath, 'r', encoding='utf-8') as f:
            return Scallion.parse(f.read())

    @staticmethod
    def dump(source: str) -> str:
        """解析并返回 AST 的可视化字符串"""
        script = Scallion.parse(source)
        return print_ast(script)
