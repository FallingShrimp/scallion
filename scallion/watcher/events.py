"""WebSocket 事件数据包 —— Pydantic ABC 基类 + ChangedEvent"""

from abc import ABC

from pydantic import BaseModel


class BaseEvent(BaseModel, ABC):
    """所有 WebSocket 事件的抽象基类"""

    event: str


class ChangedEvent(BaseEvent):
    """文件变更事件 —— 监听器检测到文件变化后广播"""

    event: str = "changed"
    data: str  # 编译结果 (JSON)
    raw: str  # 原始文件内容
