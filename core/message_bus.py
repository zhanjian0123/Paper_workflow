"""
消息总线 - 基于 asyncio.Queue 的 Agent 间通信
"""

import asyncio
from typing import Any, Optional
from dataclasses import dataclass, field
from datetime import datetime
import uuid


@dataclass
class Message:
    """Agent 间传递的消息"""

    source: str  # 发送者 Agent 名称
    target: str  # 接收者 Agent 名称
    content: Any  # 消息内容
    message_type: str = "task"  # 消息类型：task/result/request/error
    priority: int = 0  # 优先级，数字越大优先级越高
    timestamp: datetime = field(default_factory=datetime.now)
    message_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    in_reply_to: Optional[str] = None  # 回复的消息 ID

    def to_dict(self) -> dict:
        return {
            "source": self.source,
            "target": self.target,
            "content": self.content,
            "message_type": self.message_type,
            "priority": self.priority,
            "timestamp": self.timestamp.isoformat(),
            "message_id": self.message_id,
            "in_reply_to": self.in_reply_to,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Message":
        data["timestamp"] = datetime.fromisoformat(data["timestamp"])
        return cls(**data)


class MessageBus:
    """
    消息总线 - 管理 Agent 间的异步通信
    支持发布/订阅模式和点对点消息
    """

    def __init__(self):
        self._queues: dict[str, asyncio.Queue] = {}  # 每个 Agent 一个队列
        self._subscribers: dict[str, list[str]] = {}  # topic -> [agent_names]
        self._running = False

    def register_agent(self, agent_name: str) -> None:
        """注册 Agent，为其创建消息队列"""
        if agent_name not in self._queues:
            self._queues[agent_name] = asyncio.PriorityQueue()

    def unregister_agent(self, agent_name: str) -> None:
        """注销 Agent"""
        if agent_name in self._queues:
            del self._queues[agent_name]
        # 也从订阅者中移除
        for topic in list(self._subscribers.keys()):
            if agent_name in self._subscribers[topic]:
                self._subscribers[topic].remove(agent_name)

    def subscribe(self, topic: str, agent_name: str) -> None:
        """订阅某个主题"""
        if topic not in self._subscribers:
            self._subscribers[topic] = []
        if agent_name not in self._subscribers[topic]:
            self._subscribers[topic].append(agent_name)

    def unsubscribe(self, topic: str, agent_name: str) -> None:
        """取消订阅"""
        if topic in self._subscribers and agent_name in self._subscribers[topic]:
            self._subscribers[topic].remove(agent_name)

    async def send(self, message: Message) -> None:
        """发送消息给特定 Agent"""
        if message.target not in self._queues:
            raise ValueError(f"Unknown agent: {message.target}")
        # 使用负优先级确保高优先级先被处理
        await self._queues[message.target].put((-message.priority, message))

    async def broadcast(self, topic: str, content: Any, source: str = "system") -> None:
        """广播消息给订阅某个主题的所有 Agent"""
        if topic not in self._subscribers:
            return

        for agent_name in self._subscribers[topic]:
            message = Message(
                source=source,
                target=agent_name,
                content=content,
                message_type="broadcast",
            )
            await self.send(message)

    async def receive(self, agent_name: str, timeout: Optional[float] = None) -> Message:
        """
        接收消息
        timeout: 超时时间（秒），None 表示无限等待
        """
        if agent_name not in self._queues:
            raise ValueError(f"Unknown agent: {agent_name}")

        try:
            if timeout is not None:
                priority, message = await asyncio.wait_for(
                    self._queues[agent_name].get(), timeout=timeout
                )
            else:
                priority, message = await self._queues[agent_name].get()
            return message
        except asyncio.TimeoutError:
            raise

    async def receive_nowait(self, agent_name: str) -> Optional[Message]:
        """非阻塞接收消息"""
        if agent_name not in self._queues:
            raise ValueError(f"Unknown agent: {agent_name}")

        try:
            priority, message = self._queues[agent_name].get_nowait()
            return message
        except asyncio.QueueEmpty:
            return None

    def queue_size(self, agent_name: str) -> int:
        """获取 Agent 消息队列大小"""
        if agent_name not in self._queues:
            return 0
        return self._queues[agent_name].qsize()

    async def start(self) -> None:
        """启动消息总线"""
        self._running = True

    async def stop(self) -> None:
        """停止消息总线"""
        self._running = False
        # 清空所有队列
        for queue in self._queues.values():
            while not queue.empty():
                try:
                    queue.get_nowait()
                except asyncio.QueueEmpty:
                    break
