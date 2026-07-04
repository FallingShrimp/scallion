"""Scallion —— 高效剧本描述语言解析器"""

from .ast_nodes import Script
from .parser import Parser
from .visualizer import Visualizer


class Scallion:
    def parse(self, source: str) -> Script:
        parser = Parser(source)
        return parser.parse()

    def parse_file(self, filepath: str) -> Script:
        with open(filepath, encoding="utf-8") as f:
            return self.parse(f.read())

    def dump(self, source: str, highlight: bool = True) -> str:
        script = self.parse(source)
        viz = Visualizer(script, highlight=highlight)
        return viz.print()
