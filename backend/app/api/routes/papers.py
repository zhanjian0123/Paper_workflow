"""
论文 API 路由
"""
from fastapi import APIRouter, Depends, HTTPException, status
from starlette.background import BackgroundTask
from typing import Optional
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED
import tempfile

from backend.app.schemas.paper import (
    PaperSummary,
    PaperDetail,
    PaperListResponse,
    PaperBatchRequest,
    PaperBatchDeleteResponse,
)
from backend.app.services.workflow_store import WorkflowStore
from backend.app.core.deps import get_workflow_store, get_pagination

router = APIRouter(prefix="/api/papers", tags=["papers"])


@router.get(
    "",
    response_model=PaperListResponse,
    summary="获取论文列表",
)
async def list_papers(
    workflow_id: Optional[str] = None,
    source: Optional[str] = None,
    year_from: Optional[int] = None,
    year_to: Optional[int] = None,
    search: Optional[str] = None,
    pagination: dict = Depends(get_pagination),
    store: WorkflowStore = Depends(get_workflow_store),
):
    """
    获取论文列表（支持过滤和分页）

    - **workflow_id**: 按工作流 ID 过滤
    - **source**: 按数据源过滤（arxiv/google）
    - **year_from**: 起始年份
    - **year_to**: 结束年份
    - **search**: 标题搜索关键词
    """
    papers = store.get_all_papers(
        workflow_id=workflow_id,
        source=source,
        year_from=year_from,
        year_to=year_to,
        search_query=search,
        limit=pagination["page_size"],
        offset=pagination["offset"],
    )

    total = store.get_papers_count(
        workflow_id=workflow_id,
        source=source,
    )

    items = [_paper_to_summary(paper) for paper in papers]

    return PaperListResponse(
        items=items,
        total=total,
        page=pagination["page"],
        page_size=pagination["page_size"],
        has_more=pagination["offset"] + len(papers) < total,
    )


@router.post(
    "/batch-download",
    summary="批量下载论文 PDF（ZIP）",
)
async def batch_download_papers(
    request: PaperBatchRequest,
    store: WorkflowStore = Depends(get_workflow_store),
):
    """批量下载论文 PDF，返回 ZIP 压缩包"""
    from fastapi.responses import FileResponse

    papers = [store.get_paper(paper_id) for paper_id in request.paper_ids]
    existing_files = []

    for paper in papers:
        if not paper or not paper.pdf_path:
            continue
        pdf_path = Path(paper.pdf_path)
        if pdf_path.exists():
            existing_files.append((paper.paper_id, pdf_path))

    if not existing_files:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No downloadable PDF files found for selected papers",
        )

    with tempfile.NamedTemporaryFile(prefix="papers_", suffix=".zip", delete=False) as tmp:
        zip_path = Path(tmp.name)

    with ZipFile(zip_path, "w", ZIP_DEFLATED) as zip_file:
        for paper_id, pdf_path in existing_files:
            zip_file.write(pdf_path, arcname=f"papers/{paper_id}.pdf")

    return FileResponse(
        path=str(zip_path),
        media_type="application/zip",
        filename="papers_bundle.zip",
        background=BackgroundTask(zip_path.unlink, missing_ok=True),
    )


@router.post(
    "/batch-delete",
    response_model=PaperBatchDeleteResponse,
    summary="批量删除论文记录和文件",
)
async def batch_delete_papers(
    request: PaperBatchRequest,
    store: WorkflowStore = Depends(get_workflow_store),
):
    """批量删除论文记录，并尝试删除对应 PDF 文件"""
    papers = [store.get_paper(paper_id) for paper_id in request.paper_ids]
    deleted_file_count = 0
    existing_ids = []

    for paper in papers:
        if not paper:
            continue
        existing_ids.append(paper.paper_id)
        if paper.pdf_path:
            pdf_path = Path(paper.pdf_path)
            if pdf_path.exists():
                pdf_path.unlink()
                deleted_file_count += 1

    deleted_count = store.delete_papers(existing_ids)

    return PaperBatchDeleteResponse(
        deleted_count=deleted_count,
        deleted_file_count=deleted_file_count,
    )


@router.get(
    "/{paper_id}",
    response_model=PaperDetail,
    summary="获取论文详情",
)
async def get_paper(
    paper_id: str,
    store: WorkflowStore = Depends(get_workflow_store),
):
    """获取指定论文的详细信息"""
    paper = store.get_paper(paper_id)

    if not paper:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Paper not found: {paper_id}",
        )

    return _paper_to_detail(paper)


@router.get(
    "/{paper_id}/pdf",
    summary="下载论文 PDF",
)
async def download_paper_pdf(
    paper_id: str,
    store: WorkflowStore = Depends(get_workflow_store),
):
    """下载论文的 PDF 文件"""
    paper = store.get_paper(paper_id)

    if not paper:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Paper not found: {paper_id}",
        )

    if not paper.pdf_path:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"PDF not available for paper: {paper_id}",
        )

    from fastapi.responses import FileResponse

    pdf_path = Path(paper.pdf_path)

    if not pdf_path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"PDF file not found: {paper.pdf_path}",
        )

    return FileResponse(
        path=str(pdf_path),
        media_type="application/pdf",
        filename=f"{paper_id}.pdf",
    )


# ========== 辅助函数 ==========

def _paper_to_summary(paper) -> PaperSummary:
    """转换为摘要对象"""
    pdf_exists = bool(paper.pdf_path and Path(paper.pdf_path).exists())
    return PaperSummary(
        id=paper.paper_id,
        paper_id=paper.paper_id,
        title=paper.title,
        authors=[],  # TODO: 解析 JSON authors
        year=paper.year,
        source=paper.source,
        pdf_available=pdf_exists,
        workflow_id=paper.workflow_id,
    )


def _paper_to_detail(paper) -> PaperDetail:
    """转换为详情对象"""
    return PaperDetail(
        paper_id=paper.paper_id,
        workflow_id=paper.workflow_id,
        title=paper.title,
        authors=[],  # TODO: 解析 JSON authors
        abstract=paper.abstract,
        year=paper.year,
        source=paper.source,
        categories=None,
        venue=None,
        citations=None,
        doi=None,
        url="",
        pdf_path=paper.pdf_path,
        download_status=paper.download_status,
        created_at=paper.created_at,
    )
