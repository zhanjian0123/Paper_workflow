"""
记忆相关的 Pydantic 模型
"""
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
from enum import Enum


class MemoryType(str, Enum):
    """记忆类型"""
    USER = "user"
    FEEDBACK = "feedback"
    PROJECT = "project"
    REFERENCE = "reference"


class MemoryEntrySchema(BaseModel):
    """记忆条目"""
    id: str
    memory_type: MemoryType
    name: str
    description: str
    created_at: datetime
    updated_at: datetime
    expires_at: Optional[datetime]
    is_stale: bool
    is_expired: bool
    stale_days: Optional[int] = None
    tags: Optional[List[str]]

    class Config:
        from_attributes = True


class MemoryCreateRequest(BaseModel):
    """创建记忆请求"""
    memory_type: MemoryType
    name: str = Field(..., min_length=1, max_length=200)
    description: str = Field(..., min_length=50, max_length=5000)
    tags: Optional[List[str]] = None
    expires_days: Optional[int] = Field(None, ge=1, le=365)


class MemoryUpdateRequest(BaseModel):
    """更新记忆请求"""
    name: Optional[str] = Field(None, min_length=1, max_length=200)
    description: Optional[str] = Field(None, min_length=50, max_length=5000)
    tags: Optional[List[str]] = None


class MemoryListResponse(BaseModel):
    """记忆列表响应"""
    items: List[MemoryEntrySchema]
    total: int
    by_type: dict[str, int]


class MemoryCleanupResponse(BaseModel):
    """记忆清理响应"""
    total: int
    expired: int
    stale: int
