"""
论文相关的 Pydantic 模型
"""
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime


class PaperSummary(BaseModel):
    """论文摘要 (列表项)"""
    id: str
    paper_id: str  # ArXiv ID 或内部 ID
    title: str
    authors: List[str]
    year: Optional[str]
    source: str
    pdf_available: bool
    workflow_id: str

    class Config:
        from_attributes = True


class PaperDetail(BaseModel):
    """论文详情"""
    paper_id: str
    workflow_id: str
    title: str
    authors: List[str]
    abstract: str
    year: Optional[str]
    source: str
    categories: Optional[List[str]]
    venue: Optional[str]
    citations: Optional[int]
    doi: Optional[str]
    url: str
    pdf_path: Optional[str]
    download_status: str  # pending/downloaded/failed
    created_at: datetime

    class Config:
        from_attributes = True


class PaperFilterRequest(BaseModel):
    """论文过滤请求"""
    workflow_id: Optional[str] = None
    source: Optional[str] = Field(None, pattern="^(arxiv|google)$")
    year_from: Optional[int] = None
    year_to: Optional[int] = None
    search_query: Optional[str] = None


class PaperListResponse(BaseModel):
    """论文列表响应"""
    items: List[PaperSummary]
    total: int
    page: int
    page_size: int
    has_more: bool


class PaperDownloadResponse(BaseModel):
    """论文下载响应"""
    paper_id: str
    file_path: str
    file_size: int
    content_type: str = "application/pdf"


class PaperBatchRequest(BaseModel):
    """论文批量操作请求"""
    paper_ids: List[str] = Field(..., min_length=1)


class PaperBatchDeleteResponse(BaseModel):
    """论文批量删除响应"""
    deleted_count: int
    deleted_file_count: int
