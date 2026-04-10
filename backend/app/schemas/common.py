"""
通用 Schema
"""
from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional, Dict, Any


class ErrorResponse(BaseModel):
    """统一错误响应"""
    error: str
    message: str
    details: Optional[Dict[str, Any]] = None
    timestamp: datetime = Field(default_factory=datetime.now)
    request_id: str
