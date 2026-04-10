"""
记忆 API 路由
"""
from fastapi import APIRouter, Depends, HTTPException, status
from typing import Optional

from backend.app.schemas.memory import (
    MemoryType,
    MemoryEntrySchema,
    MemoryCreateRequest,
    MemoryUpdateRequest,
    MemoryListResponse,
    MemoryCleanupResponse,
)
from backend.app.services.memory_service import MemoryService
from backend.app.core.deps import get_pagination

router = APIRouter(prefix="/api/memory", tags=["memory"])

# 全局 MemoryService 实例
_memory_service: Optional[MemoryService] = None


def get_memory_service() -> MemoryService:
    """获取 MemoryService 实例"""
    global _memory_service
    if _memory_service is None:
        _memory_service = MemoryService()
    return _memory_service


@router.get(
    "",
    response_model=MemoryListResponse,
    summary="获取记忆列表",
)
async def list_memories(
    type_filter: Optional[MemoryType] = None,
    search: Optional[str] = None,
    exclude_expired: bool = True,
    exclude_stale: bool = False,
    pagination: dict = Depends(get_pagination),
    memory_service: MemoryService = Depends(get_memory_service),
):
    """
    获取记忆列表

    - **type_filter**: 按类型过滤（user/feedback/project/reference）
    - **search**: 搜索关键词
    - **exclude_expired**: 排除过期记忆（默认 true）
    - **exclude_stale**: 排除过时记忆（默认 false）
    """
    memory_type = type_filter.value if type_filter else None

    entries = memory_service.get(
        memory_type=memory_type,
        query=search,
        exclude_expired=exclude_expired,
        exclude_stale=exclude_stale,
    )

    # 计算按类型统计
    by_type = {
        "user": len([e for e in entries if e.memory_type == "user"]),
        "feedback": len([e for e in entries if e.memory_type == "feedback"]),
        "project": len([e for e in entries if e.memory_type == "project"]),
        "reference": len([e for e in entries if e.memory_type == "reference"]),
    }

    # 分页
    start = pagination["offset"]
    end = start + pagination["page_size"]
    paginated_entries = entries[start:end]

    items = [_entry_to_schema(entry) for entry in paginated_entries]

    return MemoryListResponse(
        items=items,
        total=len(entries),
        by_type=by_type,
    )


@router.post(
    "",
    response_model=MemoryEntrySchema,
    status_code=status.HTTP_201_CREATED,
    summary="保存新记忆",
)
async def create_memory(
    request: MemoryCreateRequest,
    memory_service: MemoryService = Depends(get_memory_service),
):
    """
    保存一条新的长期记忆

    - **memory_type**: 记忆类型（user/feedback/project/reference）
    - **name**: 简短标题（1-200 字符）
    - **description**: 详细描述（50-5000 字符）
    - **tags**: 标签列表（可选）
    - **expires_days**: 过期天数（1-365，可选）
    """
    from datetime import timedelta, datetime

    # 内容校验
    if memory_service._contains_sensitive_info(request.name + request.description):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="记忆内容包含敏感信息",
        )

    if memory_service._is_code_structure_info(request.description):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="不能保存纯代码结构信息",
        )

    # 计算过期时间
    expires_at = None
    if request.expires_days:
        expires_at = datetime.now() + timedelta(days=request.expires_days)

    # 保存记忆
    entry = memory_service.save(
        memory_type=request.memory_type,
        name=request.name,
        description=request.description,
        tags=request.tags,
        expires_days=request.expires_days,
    )

    if not entry:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="记忆保存失败",
        )

    return _entry_to_schema(entry)


@router.delete(
    "/{memory_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="删除记忆",
)
async def delete_memory(
    memory_id: str,
    memory_service: MemoryService = Depends(get_memory_service),
):
    """删除指定的记忆"""
    success = memory_service.delete(memory_id)

    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Memory not found: {memory_id}",
        )


@router.post(
    "/cleanup",
    response_model=MemoryCleanupResponse,
    summary="清理过期/过时记忆",
)
async def cleanup_memories(
    memory_service: MemoryService = Depends(get_memory_service),
):
    """清理过期和过时的记忆"""
    stats = memory_service.cleanup()

    return MemoryCleanupResponse(
        total=stats["total"],
        expired=stats["expired"],
        stale=stats["stale"],
    )


# ========== 辅助函数 ==========

def _entry_to_schema(entry) -> MemoryEntrySchema:
    """转换为 Schema 对象"""
    return MemoryEntrySchema(
        id=entry.id,
        memory_type=entry.memory_type,
        name=entry.name,
        description=entry.description,
        created_at=entry.created_at,
        updated_at=entry.updated_at,
        expires_at=entry.expires_at,
        is_stale=entry.is_stale(),
        is_expired=entry.is_expired(),
        stale_days=entry.stale_days(),
        tags=entry.tags,
    )
