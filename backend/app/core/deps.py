"""
依赖注入
"""
from fastapi import Depends, HTTPException, status, Request
from typing import Optional, Any
import uuid

from backend.app.core.config import get_settings, Settings
from backend.app.services.workflow_store import WorkflowStore
from backend.app.core.events import EventBus, get_event_bus


# WorkflowRunner 依赖
_runner: Optional[Any] = None

# MultiAgentAdapter 依赖
_adapter: Optional[Any] = None

# WorkflowStore 依赖
_db_store: Optional[WorkflowStore] = None


def get_workflow_store() -> WorkflowStore:
    """获取 WorkflowStore 实例"""
    global _db_store
    if _db_store is None:
        settings = get_settings()
        _db_store = WorkflowStore(db_path=settings.workflow_store_db_path)
    return _db_store


def get_workflow_runner() -> Any:
    """获取 WorkflowRunner 实例（单例）"""
    global _runner
    if _runner is None:
        from backend.app.services.workflow_runner import WorkflowRunner
        settings = get_settings()
        _runner = WorkflowRunner(
            workflow_store=get_workflow_store(),
            event_bus=get_event_bus(),
            download_dir=str(settings.download_dir_path),
        )
    return _runner


async def get_multi_agent_adapter() -> Any:
    """获取 MultiAgentAdapter 实例（单例）"""
    global _adapter
    if _adapter is None:
        from backend.app.adapters.multi_agent_adapter import MultiAgentAdapter
        settings = get_settings()
        _adapter = MultiAgentAdapter(
            download_dir=str(settings.download_dir_path),
            max_papers=10,
            source="arxiv",
        )
        await _adapter.initialize()
    return _adapter


# 分页参数
def get_pagination(
    page: int = 1,
    page_size: int = 20,
) -> dict:
    """获取分页参数"""
    settings = get_settings()

    if page < 1:
        page = 1
    if page_size < 1:
        page_size = 1
    if page_size > settings.max_page_size:
        page_size = settings.max_page_size

    offset = (page - 1) * page_size
    return {"page": page, "page_size": page_size, "offset": offset}


# Request ID 生成
async def generate_request_id(request: Request) -> str:
    """生成请求 ID"""
    return f"req_{uuid.uuid4().hex[:16]}"


# 错误响应
def create_error_response(
    error: str,
    message: str,
    details: Optional[dict] = None,
    request_id: Optional[str] = None,
) -> dict:
    """创建错误响应"""
    from datetime import datetime

    return {
        "error": error,
        "message": message,
        "details": details or {},
        "timestamp": datetime.now().isoformat(),
        "request_id": request_id or "unknown",
    }


def not_found_error(resource: str, resource_id: str) -> HTTPException:
    """创建 404 错误"""
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=f"{resource} not found: {resource_id}",
    )


def bad_request_error(message: str) -> HTTPException:
    """创建 400 错误"""
    return HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail=message,
    )


def conflict_error(message: str) -> HTTPException:
    """创建 409 错误"""
    return HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail=message,
    )
