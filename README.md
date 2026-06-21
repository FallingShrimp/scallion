# Scallion

Scallion 是一个轻量级剧本描述语言（Script Description Language）解析器，用于将面向视觉小说 / 交互叙事场景的文本剧本转换为结构化 JSON，方便下游游戏引擎或渲染器消费。

## 运行原理

Scallion 采用**词法分析 + 递归下降解析**的两阶段架构：

1. **词法分析（Lexer）**  
   `parser.py` 中的 `tokenize()` 使用正则表达式将源码逐行切分为 `Token` 流。Token 类型包括关键字（`enter`、`talk`、`select` 等）、结构符号（`{`、`}`、`->` 等）、标识符、整数字面量以及自由文本。

2. **语法分析（Parser）**  
   `Parser` 类基于 Token 流进行递归下降解析，生成一棵类型安全的抽象语法树（AST）。AST 节点使用 [Pydantic](https://docs.pydantic.dev/) 定义，位于 `ast_nodes.py`，根节点为 `Script`，其子节点为各类 `Statement`（如 `Enter`、`Talk`、`Select`、`Jump`、`Exit` 等）。

3. **输出**  
   - **JSON**：AST 通过 Pydantic 的 `model_dump_json()` 序列化为 JSON 文件，语句以 `kind` 字段作类型判别，可直接被外部程序读取。  
   - **可视化树**：`Visualizer` 使用 Rich 标签将 AST 渲染为带缩进、颜色和标签标注的树形文本，便于作者在终端快速审阅剧本结构。

## 项目结构

```plain
scallion/
├── index.py              # CLI 入口：读文件 → 解析 → 输出 JSON + 可视化树
├── scallion/
│   ├── __init__.py       # Scallion 主类（parse / parse_file / dump）
│   ├── parser.py         # 词法分析器 + 递归下降解析器
│   ├── ast_nodes.py      # Pydantic AST 节点定义
│   ├── visualizer.py     # AST 终端可视化
│   └── cli/              # 命令行参数解析
│       ├── __init__.py
│       └── structs.py
└── article.txt           # 示例剧本
```

## 安装

本项目依赖 Python 3.10+ 以及 `pydantic`、`rich`。

```bash
pip install pydantic rich
```

## 用法

### 命令行

```bash
python index.py <剧本文件> [-o <输出JSON路径>] [-f <缩进空格数>]
```

示例：

```bash
python index.py article.txt -o article.json -f 2
```

运行后会在终端打印带颜色的 AST 树，并将 JSON 写入 `article.json`。

### 作为库使用

```python
from scallion import Scallion

scallion = Scallion()
script = scallion.parse_file("article.txt")
print(script.model_dump_json(indent=2))
```

## 语法说明

完整的语法规范请参考 [`syntax.md`](syntax.md)。

## 示例输出

以 `article.txt` 为例，终端可视化输出大致如下：

```plain
Script《day start》
│   statements:
│   │   Enter(name='Tera', emotion='a')
│   │   Enter(name='Pico', emotion='b')
│   │   Focus(name='Tera')
│   │   Talk(mode='auto', text='你好Pico，你吃饭了吗？？？')
│   │   Select(variable='eat?')
│   │   │   Pico吃饭了 → 0
│   │   │   Pico没吃饭 → 1
│   │   ...
```

对应的 JSON 则以 `kind` 为判别字段，完整保留标签、文本、跳转映射等语义信息。
