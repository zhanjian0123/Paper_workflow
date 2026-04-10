"""
上传论文 API 路由 - 支持本地 PDF 上传和解析
"""
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form
from fastapi.responses import JSONResponse
from typing import Optional, List
from pathlib import Path
import uuid
import aiofiles
import asyncio
import json

from backend.app.schemas.paper import (
    PaperSummary,
    PaperDetail,
)
from backend.app.schemas.workflow import (
    WorkflowDetail,
    WorkflowCreateRequest,
)
from backend.app.services.workflow_store import WorkflowStore, WorkflowRecord, PaperRecord
from backend.app.core.deps import get_workflow_store, generate_request_id
from backend.app.core.config import get_settings
from datetime import datetime

router = APIRouter(prefix="/api/upload", tags=["upload"])


@router.post(
    "/papers",
    summary="上传单篇论文 PDF",
)
async def upload_paper(
    file: UploadFile = File(..., description="PDF 文件"),
    title: Optional[str] = Form(None, description="论文标题（可选，不提供则使用文件名）"),
    store: WorkflowStore = Depends(get_workflow_store),
):
    """
    上传本地论文 PDF 文件

    - **file**: PDF 文件
    - **title**: 论文标题（可选，不提供则使用文件名）
    """
    upload_dir = get_settings().upload_dir_path
    upload_dir.mkdir(parents=True, exist_ok=True)

    # 验证文件类型
    if not file.filename.lower().endswith('.pdf'):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only PDF files are supported",
        )

    # 生成唯一 ID
    paper_id = f"uploaded_{uuid.uuid4().hex[:8]}"

    # 保存文件
    file_path = upload_dir / f"{paper_id}.pdf"

    try:
        async with aiofiles.open(str(file_path), "wb") as f:
            content = await file.read()
            await f.write(content)

        # 获取文件大小
        file_size = len(content)

        # 解析 PDF 元数据获取标题（如果未提供）
        paper_title = title
        if not paper_title:
            # 使用文件名（去掉 .pdf 后缀）
            paper_title = Path(file.filename).stem

        # 创建论文记录
        paper_record = PaperRecord(
            paper_id=paper_id,
            workflow_id="uploaded",  # 标记为上传论文
            title=paper_title,
            authors="[]",  # 暂时为空，后续可解析
            abstract="",  # 暂时为空，后续可解析
            year=None,
            source="local_upload",
            pdf_path=str(file_path),
            download_status="downloaded",
            created_at=datetime.now().isoformat(),
        )
        store.add_paper(paper_record)

        return {
            "paper_id": paper_id,
            "title": paper_title,
            "file_path": str(file_path),
            "file_size": file_size,
            "message": "上传成功",
        }

    except Exception as e:
        # 删除失败的文件
        if file_path.exists():
            file_path.unlink()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Upload failed: {str(e)}",
        )


@router.post(
    "/papers/batch",
    summary="批量上传论文 PDF",
)
async def upload_papers_batch(
    files: List[UploadFile] = File(..., description="PDF 文件列表"),
    store: WorkflowStore = Depends(get_workflow_store),
):
    """
    批量上传本地论文 PDF 文件

    - **files**: 多个 PDF 文件
    """
    upload_dir = get_settings().upload_dir_path
    upload_dir.mkdir(parents=True, exist_ok=True)

    results = []
    failed = []

    for file in files:
        if not file.filename.lower().endswith('.pdf'):
            failed.append({"filename": file.filename, "error": "Only PDF files are supported"})
            continue

        paper_id = f"uploaded_{uuid.uuid4().hex[:8]}"
        file_path = upload_dir / f"{paper_id}.pdf"

        try:
            async with aiofiles.open(str(file_path), "wb") as f:
                content = await file.read()
                await f.write(content)

            paper_title = Path(file.filename).stem

            paper_record = PaperRecord(
                paper_id=paper_id,
                workflow_id="uploaded",
                title=paper_title,
                authors="[]",
                abstract="",
                year=None,
                source="local_upload",
                pdf_path=str(file_path),
                download_status="downloaded",
                created_at=datetime.now().isoformat(),
            )
            store.add_paper(paper_record)

            results.append({
                "paper_id": paper_id,
                "title": paper_title,
                "file_path": str(file_path),
            })

        except Exception as e:
            failed.append({"filename": file.filename, "error": str(e)})
            if file_path.exists():
                file_path.unlink()

    return {
        "uploaded": len(results),
        "failed": len(failed),
        "results": results,
        "errors": failed,
    }


@router.post(
    "/papers/{paper_id}/parse",
    summary="解析上传的论文",
)
async def parse_uploaded_paper(
    paper_id: str,
    store: WorkflowStore = Depends(get_workflow_store),
):
    """
    解析上传的论文 PDF，提取元数据和摘要

    - **paper_id**: 论文 ID
    """
    paper = store.get_paper(paper_id)

    if not paper:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Paper not found: {paper_id}",
        )

    if not paper.pdf_path or not Path(paper.pdf_path).exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"PDF file not found: {paper.pdf_path}",
        )

    # 解析 PDF
    try:
        from tools.pdf_parser_tool import PDFParserTool
        parser = PDFParserTool()

        # 提取元数据
        metadata_result = await parser.get_metadata(paper.pdf_path)

        # 提取文本（前 5 页，通常包含摘要和引言）
        text_result = await parser.extract_text(
            paper.pdf_path,
            page_range={"start": 0, "end": 5},
        )

        # 从文本中提取摘要（简单启发式：查找 "Abstract" 或 "摘要"）
        abstract = _extract_abstract_from_text(text_result.data.get("full_text", ""))

        # 更新论文记录
        update_data = {}
        if metadata_result.success and metadata_result.data:
            if metadata_result.data.get("title") != "Unknown":
                update_data["title"] = metadata_result.data["title"]
            if metadata_result.data.get("author") != "Unknown":
                update_data["authors"] = json.dumps([metadata_result.data["author"]])

        if abstract:
            update_data["abstract"] = abstract

        # 更新记录
        for key, value in update_data.items():
            setattr(paper, key, value)
        store.update_paper(paper_id, **update_data)

        return {
            "paper_id": paper_id,
            "title": paper.title,
            "authors": paper.authors,
            "abstract": paper.abstract,
            "metadata": metadata_result.data if metadata_result.success else {},
            "pages": text_result.data.get("total_pages", 0) if text_result.success else 0,
        }

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Parse failed: {str(e)}",
        )


@router.post(
    "/papers/{paper_id}/full-parse",
    summary="完整解析上传的论文",
)
async def parse_uploaded_paper_full(
    paper_id: str,
    store: WorkflowStore = Depends(get_workflow_store),
):
    """
    完整解析上传的论文 PDF，提取全部文本内容

    - **paper_id**: 论文 ID
    """
    paper = store.get_paper(paper_id)

    if not paper:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Paper not found: {paper_id}",
        )

    if not paper.pdf_path or not Path(paper.pdf_path).exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"PDF file not found: {paper.pdf_path}",
        )

    try:
        from tools.pdf_parser_tool import PDFParserTool
        parser = PDFParserTool()

        # 提取全部文本
        text_result = await parser.extract_text(paper.pdf_path)

        if not text_result.success:
            raise Exception(text_result.error or "Failed to extract text")

        return {
            "paper_id": paper_id,
            "title": paper.title,
            "full_text": text_result.data.get("full_text", ""),
            "total_pages": text_result.data.get("total_pages", 0),
            "pages": text_result.data.get("texts", []),
        }

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Parse failed: {str(e)}",
        )


@router.post(
    "/create-workflow",
    summary="从上传的论文创建工作流",
    response_model=WorkflowDetail,
)
async def create_workflow_from_uploaded_papers(
    paper_ids: List[str] = Form(..., description="论文 ID 列表"),
    query: str = Form(..., description="研究主题"),
    year_range: Optional[str] = Form(None, description="年份范围"),
    max_papers: int = Form(default=10, ge=1, le=100, description="最大论文数量"),
    skip_search: bool = Form(default=True, description="是否跳过搜索阶段"),
    store: WorkflowStore = Depends(get_workflow_store),
    request_id: str = Depends(generate_request_id),
):
    """
    从上传的论文创建工作流，可跳过搜索阶段直接进行分析

    - **paper_ids**: 要分析的论文 ID 列表
    - **query**: 研究主题
    - **year_range**: 年份范围（可选）
    - **max_papers**: 最大论文数量
    - **skip_search**: 是否跳过搜索阶段（默认 true）
    """
    # 验证论文是否存在
    papers = []
    for paper_id in paper_ids:
        paper = store.get_paper(paper_id)
        if not paper:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Paper not found: {paper_id}",
            )
        papers.append(paper)

    # 创建工作流
    workflow_id = f"wf_{datetime.now().strftime('%Y%m%d%H%M%S')}_{request_id[-8:]}"
    now = datetime.now().isoformat()

    workflow = WorkflowRecord(
        id=workflow_id,
        query=query,
        year_range=year_range,
        max_papers=len(papers),
        source="local_upload",
        status="pending",
        current_stage=None,
        progress=0,
        message=f"已加载 {len(papers)} 篇本地论文",
        papers_found=len(papers),
        result=None,
        error=None,
        created_at=now,
        updated_at=now,
        completed_at=None,
    )

    store.create_workflow(workflow)

    # 将论文关联到工作流
    for paper in papers:
        store.update_paper(
            paper.paper_id,
            workflow_id=workflow_id,
        )

    # 返回工作流详情
    return _workflow_to_detail(workflow)


# ========== 辅助函数 ==========

def _extract_abstract_from_text(full_text: str) -> str:
    """从全文中提取摘要（简单启发式）"""
    lines = full_text.split('\n')
    abstract_lines = []
    in_abstract = False

    for line in lines:
        line_lower = line.lower().strip()

        # 检测摘要开始
        if 'abstract' in line_lower or '摘要' in line_lower:
            in_abstract = True
            # 去掉 "Abstract" 或 "摘要" 标记
            if ':' in line:
                line = line.split(':', 1)[1]
            continue

        # 检测摘要结束（通常是空行或新章节）
        if in_abstract:
            if line.strip() == '' and abstract_lines:
                break
            if line_lower.startswith('1 introduction') or line_lower.startswith('1.') or \
               line_lower.startswith('一、') or line_lower.startswith('引言'):
                break
            abstract_lines.append(line)

    if abstract_lines:
        return '\n'.join(abstract_lines).strip()

    # 如果没有找到摘要，返回前 500 字
    return full_text[:500].strip() if full_text else ""


def _workflow_to_detail(workflow: WorkflowRecord) -> WorkflowDetail:
    """转换为详情对象"""
    from backend.app.schemas.workflow import WorkflowStatus, WorkflowStageStatus

    stages = []

    return WorkflowDetail(
        id=workflow.id,
        query=workflow.query,
        rewritten_query=workflow.rewritten_query,
        year_range=workflow.year_range,
        max_papers=workflow.max_papers,
        source=workflow.source,
        status=WorkflowStatus(workflow.status),
        current_stage=workflow.current_stage,
        stages=stages,
        progress=workflow.progress,
        message=workflow.message,
        papers_found=workflow.papers_found,
        result=workflow.result,
        error=workflow.error,
        created_at=datetime.fromisoformat(workflow.created_at),
        updated_at=datetime.fromisoformat(workflow.updated_at),
        completed_at=(
            datetime.fromisoformat(workflow.completed_at)
            if workflow.completed_at else None
        ),
    )
