# 超级大葱编译器

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
├── index.py              # CLI 入口：普通编译 / watch 模式
├── scallion/
│   ├── __init__.py       # Scallion 主类（parse / parse_file / dump）
│   ├── parser.py         # 词法分析器 + 递归下降解析器
│   ├── ast_nodes.py      # Pydantic AST 节点定义
│   ├── visualizer.py     # AST 终端可视化
│   ├── event_subscriber.py # 进程内事件订阅-发布
│   ├── watcher/          # 文件监听 + WebSocket 广播
│   │   ├── __init__.py
│   │   ├── client.py     # WatchClient 类
│   │   └── events.py     # WebSocket 事件数据包 (BaseEvent / ChangedEvent)
│   └── cli/              # 命令行参数解析
│       ├── __init__.py
│       └── structs.py
└── article.txt           # 示例剧本
```

## 安装

本项目依赖 Python 3.10+ 以及 `pydantic`、`rich`、`watchdog`、`websockets`。

```bash
pip install pydantic rich watchdog websockets
```

或一键安装：

```bash
pip install -r requirements.txt
```

## 用法

### 命令行

```bash
python index.py <剧本文件> [-o <输出JSON路径>] [-f <缩进空格数>] [-w] [-p <端口号>]
```

| 选项 | 说明 |
|------|------|
| `-o, --output` | 输出的 JSON 文件路径 |
| `-f, --format` | JSON 缩进空格数，`0` 为紧凑输出 |
| `-w, --watch` | 开启文件监听模式，源文件修改后自动重新编译 |
| `-p, --port` | WebSocket 服务器端口，需配合 `-w` 使用 |

#### 普通模式

```bash
python index.py article.txt -o article.json -f 2
```

运行后会在终端打印带颜色的 AST 树，并将 JSON 写入 `article.json`。

#### Watch 模式

```bash
# 仅监听 + 编译
python index.py article.txt -w -o article.json -f 2

# 监听 + 编译 + WebSocket 广播（端口 9000）
python index.py article.txt -w -p 9000 -o article.json -f 2
```

开启 `-w` 后，程序会持续运行。每次保存 `article.txt` 时自动重新编译并在终端输出新的 AST 树。按 `Ctrl+C` 退出。

### 作为库使用

#### 基础解析

```python
from scallion import Scallion

scallion = Scallion()
script = scallion.parse_file("article.txt")
print(script.model_dump_json(indent=2))
```

#### Watch 模式（编程方式）

通过 `WatchClient` 类可以在自己的脚本中实现文件监听 + WebSocket 广播：

```python
import asyncio
from scallion import Scallion
from scallion.watcher import ChangedEvent, WatchClient

scallion = Scallion()

def compile_callback(raw: str) -> str:
    """编译回调：原始文本 → 编译结果 JSON 字符串"""
    script = scallion.parse(raw)
    return script.model_dump_json(indent=2)

async def main():
    client = WatchClient("article.txt", port=9000)
    client.set_compile_callback(compile_callback)

    async with client:
        # 首次编译并广播
        raw = open("article.txt", encoding="utf-8").read()
        result = compile_callback(raw)
        await client.broadcast(ChangedEvent(data=result, raw=raw))

        # 阻塞，文件变更时自动触发回调并广播
        await asyncio.Future()

asyncio.run(main())
```

## WebSocket 事件

`WatchClient` 启动 WebSocket 服务器后，所有连接的客户端会在文件变更时收到 JSON 事件。

### 事件格式

```json
{
    "event": "changed",
    "data": "{...编译后的 AST JSON...}",
    "raw": "*day start\nenter Tera:a\n..."
}
```

| 字段 | 说明 |
|------|------|
| `event` | 事件类型标识，当前为 `"changed"` |
| `data` | 编译结果 — Pydantic `model_dump_json()` 输出的 AST JSON 字符串 |
| `raw` | 原始剧本文件内容 |

### 事件模型

事件系统基于 Pydantic 抽象基类设计，方便扩展：

```python
class BaseEvent(BaseModel, ABC):  # 所有事件的抽象基类
    event: str

class ChangedEvent(BaseEvent):    # 文件变更事件
    event: str = "changed"
    data: str   # 编译结果
    raw: str    # 原始内容
```

后续可通过继承 `BaseEvent` 添加新事件类型（如 `CompileErrorEvent`、`ConnectionEvent` 等），扩展时无需修改 `WatchClient.broadcast()` 的签名。

### WebSocket 客户端示例（JavaScript）

```js
const ws = new WebSocket("ws://localhost:9000");

ws.onmessage = (msg) => {
    const evt = JSON.parse(msg.data);
    console.log(`事件: ${evt.event}`);
    console.log(`编译结果:`, JSON.parse(evt.data));
    console.log(`原始内容:`, evt.raw);
};
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
