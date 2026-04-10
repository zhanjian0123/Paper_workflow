"""
事件总线 - 用于工作流事件的发布/订阅

支持：
- 按 workflow_id 订阅
- 异步事件分发
- 多个订阅者
"""
import asyncio
from typing import Dict, Set, Callable, Any, Optional
from datetime import datetime
import json

# 事件类型
EVENT_STAGE_STARTED = "stage_started"
EVENT_STAGE_PROGRESS = "stage_progress"
EVENT_STAGE_COMPLETED = "stage_completed"
EVENT_STAGE_FAILED = "stage_failed"
EVENT_WORKFLOW_COMPLETED = "workflow_completed"
EVENT_WORKFLOW_FAILED = "workflow_failed"
EVENT_WORKFLOW_CANCELLED = "workflow_cancelled"
EVENT_HEARTBEAT = "heartbeat"


class Event:
    """事件对象"""

    def __init__(
        self,
        event_type: str,
        workflow_id: str,
        data: Optional[Dict[str, Any]] = None,
    ):
        self.event_type = event_type
        self.workflow_id = workflow_id
        self.data = data or {}
        self.timestamp = datetime.now()

    def to_dict(self) -> dict:
        return {
            "event_type": self.event_type,
            "workflow_id": self.workflow_id,
            "data": self.data,
            "timestamp": self.timestamp.isoformat(),
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False)


class EventBus:
    """
    事件总线

    使用示例:
        bus = EventBus()

        # 订阅某个 workflow 的事件
        async def handler(event: Event):
            print(f"收到事件：{event.event_type}")

        bus.subscribe("workflow_123", handler)

        # 发布事件
        await bus.publish(Event(EVENT_STAGE_STARTED, "workflow_123", {"stage": "search"}))

        # 取消订阅
        bus.unsubscribe("workflow_123", handler)
    """

    def __init__(self):
        # workflow_id -> set of callbacks
        self._subscribers: Dict[str, Set[Callable]] = {}
        self._lock = asyncio.Lock()

    def subscribe(self, workflow_id: str, callback: Callable) -> None:
        """订阅某个 workflow 的事件"""
        if workflow_id not in self._subscribers:
            self._subscribers[workflow_id] = set()
        self._subscribers[workflow_id].add(callback)

    def unsubscribe(self, workflow_id: str, callback: Callable) -> None:
        """取消订阅"""
        if workflow_id in self._subscribers:
            self._subscribers[workflow_id].discard(callback)
            if not self._subscribers[workflow_id]:
                del self._subscribers[workflow_id]

    async def publish(self, event: Event) -> None:
        """发布事件给所有订阅者"""
        async with self._lock:
            subscribers = self._subscribers.get(event.workflow_id, set()).copy()

        if subscribers:
            # 异步分发给所有订阅者
            tasks = []
            for callback in subscribers:
                try:
                    if asyncio.iscoroutinefunction(callback):
                        tasks.append(callback(event))
                    else:
                        tasks.append(asyncio.get_event_loop().run_in_executor(None, callback, event))
                except Exception as e:
                    print(f"[EventBus] 订阅者调用失败：{e}")

            if tasks:
                # 并发执行所有回调
                results = await asyncio.gather(*tasks, return_exceptions=True)
                for i, result in enumerate(results):
                    if isinstance(result, Exception):
                        print(f"[EventBus] 回调执行失败：{result}")

    def get_subscriber_count(self, workflow_id: str) -> int:
        """获取某个 workflow 的订阅者数量"""
        return len(self._subscribers.get(workflow_id, set()))

    def get_all_workflow_ids(self) -> list:
        """获取所有有订阅者的 workflow ID"""
        return list(self._subscribers.keys())


# 全局事件总线实例
_event_bus: Optional[EventBus] = None


def get_event_bus() -> EventBus:
    """获取全局事件总线实例"""
    global _event_bus
    if _event_bus is None:
        _event_bus = EventBus()
    return _event_bus


def set_event_bus(bus: EventBus) -> None:
    """设置全局事件总线实例"""
    global _event_bus
    _event_bus = bus
