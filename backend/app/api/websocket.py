"""
WebSocket 管理器 - 管理工作流事件的 WebSocket 订阅

功能：
- 连接管理
- 按 workflow_id 订阅
- 心跳/超时处理
- 断线清理
"""
import asyncio
import json
from typing import Dict, Set, Optional
from fastapi import WebSocket, WebSocketDisconnect, WebSocketException
from datetime import datetime, timedelta

from backend.app.core.events import Event, EVENT_HEARTBEAT
from backend.app.core.config import get_settings


class ConnectionManager:
    """
    WebSocket 连接管理器

    使用示例:
        manager = ConnectionManager()

        # 接受连接
        await manager.connect(websocket, workflow_id)

        # 发送事件
        await manager.broadcast_to_workflow(workflow_id, event)

        # 断开连接
        await manager.disconnect(websocket, workflow_id)
    """

    def __init__(self):
        # workflow_id -> set of websockets
        self._workflow_subscribers: Dict[str, Set[WebSocket]] = {}
        # websocket -> workflow_id
        self._websocket_to_workflow: Dict[WebSocket, str] = {}
        # 心跳配置
        settings = get_settings()
        self.ping_interval = settings.websocket_ping_interval
        self.timeout = timedelta(seconds=settings.websocket_timeout)

    async def connect(
        self,
        websocket: WebSocket,
        workflow_id: str,
    ) -> None:
        """接受 WebSocket 连接并订阅 workflow"""
        await websocket.accept()

        if workflow_id not in self._workflow_subscribers:
            self._workflow_subscribers[workflow_id] = set()

        self._workflow_subscribers[workflow_id].add(websocket)
        self._websocket_to_workflow[websocket] = workflow_id

        # 发送欢迎消息
        await self._send_message(
            websocket,
            {
                "type": "connected",
                "workflow_id": workflow_id,
                "timestamp": datetime.now().isoformat(),
            },
        )

    async def disconnect(
        self,
        websocket: WebSocket,
        workflow_id: Optional[str] = None,
    ) -> None:
        """断开 WebSocket 连接"""
        if workflow_id is None:
            workflow_id = self._websocket_to_workflow.get(websocket)

        if workflow_id:
            if workflow_id in self._workflow_subscribers:
                self._workflow_subscribers[workflow_id].discard(websocket)

                if not self._workflow_subscribers[workflow_id]:
                    del self._workflow_subscribers[workflow_id]

            if websocket in self._websocket_to_workflow:
                del self._websocket_to_workflow[websocket]

    async def broadcast_to_workflow(
        self,
        workflow_id: str,
        event: Event,
    ) -> None:
        """向订阅某个 workflow 的所有客户端广播事件"""
        if workflow_id not in self._workflow_subscribers:
            return

        message = event.to_dict()

        # 并发发送给所有订阅者
        tasks = []
        for websocket in self._workflow_subscribers[workflow_id].copy():
            tasks.append(self._safe_send(websocket, message))

        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

    async def send_to_client(
        self,
        websocket: WebSocket,
        event: Event,
    ) -> None:
        """向特定客户端发送事件"""
        await self._safe_send(websocket, event.to_dict())

    async def _safe_send(
        self,
        websocket: WebSocket,
        message: dict,
    ) -> bool:
        """安全发送消息（失败时自动断开）"""
        try:
            await websocket.send_json(message)
            return True
        except Exception as e:
            # 发送失败，断开连接
            await self.disconnect(websocket)
            return False

    async def _send_message(
        self,
        websocket: WebSocket,
        message: dict,
    ) -> None:
        """发送消息"""
        await websocket.send_json(message)

    def get_subscriber_count(self, workflow_id: str) -> int:
        """获取某个 workflow 的订阅者数量"""
        return len(self._workflow_subscribers.get(workflow_id, set()))

    def get_all_workflow_ids(self) -> list:
        """获取所有有订阅者的 workflow ID"""
        return list(self._workflow_subscribers.keys())

    async def start_heartbeat(
        self,
        websocket: WebSocket,
        workflow_id: str,
    ) -> None:
        """启动心跳"""
        try:
            while True:
                await asyncio.sleep(self.ping_interval)
                await self._send_message(
                    websocket,
                    {
                        "type": EVENT_HEARTBEAT,
                        "timestamp": datetime.now().isoformat(),
                    },
                )
        except Exception:
            # 心跳失败，断开连接
            await self.disconnect(websocket, workflow_id)


# 全局连接管理器实例
_connection_manager: Optional[ConnectionManager] = None


def get_connection_manager() -> ConnectionManager:
    """获取全局 ConnectionManager 实例"""
    global _connection_manager
    if _connection_manager is None:
        _connection_manager = ConnectionManager()
    return _connection_manager


# WebSocket 路由辅助函数
async def websocket_handler(
    websocket: WebSocket,
    workflow_id: str,
    event_bus,
):
    """
    WebSocket 连接处理器

    订阅 workflow 事件并推送给客户端
    """
    manager = get_connection_manager()
    subscription = None

    # 连接
    await manager.connect(websocket, workflow_id)

    async def forward_event(event: Event) -> None:
        """将事件总线中的事件转发给当前连接"""
        await manager.send_to_client(websocket, event)

    subscription = forward_event
    event_bus.subscribe(workflow_id, subscription)

    # 启动心跳
    heartbeat_task = asyncio.create_task(
        manager.start_heartbeat(websocket, workflow_id)
    )

    try:
        while True:
            # 接收客户端消息（保持连接）
            try:
                data = await websocket.receive_text()
                # 可选：处理客户端消息
            except WebSocketDisconnect:
                break
            except asyncio.TimeoutError:
                # 超时，继续等待
                continue

    except Exception as e:
        # 异常处理
        pass

    finally:
        if subscription is not None:
            event_bus.unsubscribe(workflow_id, subscription)

        # 清理
        heartbeat_task.cancel()
        try:
            await heartbeat_task
        except asyncio.CancelledError:
            pass

        await manager.disconnect(websocket, workflow_id)
