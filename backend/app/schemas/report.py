"""
报告相关的 Pydantic 模型
"""
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime


class ReportSummary(BaseModel):
    """报告摘要 (列表项)"""
    report_id: str
    workflow_id: str
    title: str  # 取报告第一行
    word_count: int
    paper_count: int
    created_at: datetime

    class Config:
        from_attributes = True


class ReportDetail(BaseModel):
    """报告详情"""
    report_id: str
    workflow_id: str
    content_markdown: str
    file_path: Optional[str]
    word_count: int
    paper_count: int
    created_at: datetime

    class Config:
        from_attributes = True


class ReportDownloadResponse(BaseModel):
    """报告下载响应"""
    report_id: str
    file_path: str
    file_size: int
    content_type: str  # text/markdown | application/pdf


class ReportBatchRequest(BaseModel):
    """报告批量操作请求"""
    report_ids: List[str] = Field(..., min_length=1)


class ReportBatchDeleteResponse(BaseModel):
    """报告批量删除响应"""
    deleted_count: int
    deleted_file_count: int
