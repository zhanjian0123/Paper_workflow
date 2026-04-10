"""
工作流 API 路由
"""
from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks, Form, Request
from typing import Optional, Any
from datetime import datetime
from pathlib import Path

from backend.app.schemas.workflow import (
    WorkflowCreateRequest,
    WorkflowDetail,
    WorkflowSummary,
    WorkflowListResponse,
    WorkflowCancelRequest,
    WorkflowCancelResponse,
    WorkflowBatchRequest,
    WorkflowBatchDeleteResponse,
    WorkflowStatus,
    WorkflowFromTemplateRequest,
)
from backend.app.schemas.common import ErrorResponse
from backend.app.services.workflow_store import WorkflowStore, WorkflowRecord
from backend.app.services.workflow_runner import WorkflowRunner
from backend.app.core.deps import (
    get_workflow_store,
    get_workflow_runner,
    get_pagination,
    generate_request_id,
)
from backend.app.core.events import get_event_bus
from backend.app.core.config import get_settings

router = APIRouter(prefix="/api/workflows", tags=["workflows"])


@router.post(
    "/batch-delete",
    response_model=WorkflowBatchDeleteResponse,
    summary="批量删除工作流及关联文件",
)
async def batch_delete_workflows(
    request: WorkflowBatchRequest,
    store: WorkflowStore = Depends(get_workflow_store),
    runner: Any = Depends(get_workflow_runner),
):
    """批量删除工作流，并清理关联论文/报告文件和数据库索引"""
    deleted_count = 0
    deleted_paper_file_count = 0
    deleted_report_file_count = 0

    for workflow_id in request.workflow_ids:
        workflow = store.get_workflow(workflow_id)
        if not workflow:
            continue

        if runner.is_running(workflow_id):
            await runner.cancel_workflow(workflow_id)

        papers = store.get_papers_by_workflow(workflow_id, limit=1000)
        for paper in papers:
            if paper.pdf_path:
                pdf_path = Path(paper.pdf_path)
                if pdf_path.exists():
                    pdf_path.unlink()
                    deleted_paper_file_count += 1

        report = store.get_report_by_workflow(workflow_id)
        if report and report.file_path:
            report_path = Path(report.file_path)
            if report_path.exists():
                report_path.unlink()
                deleted_report_file_count += 1

        store.delete_workflow(workflow_id)
        deleted_count += 1

    return WorkflowBatchDeleteResponse(
        deleted_count=deleted_count,
        deleted_paper_file_count=deleted_paper_file_count,
        deleted_report_file_count=deleted_report_file_count,
    )


@router.post(
    "",
    response_model=WorkflowDetail,
    status_code=status.HTTP_201_CREATED,
    summary="创建新工作流",
)
async def create_workflow(
    request: WorkflowCreateRequest,
    background_tasks: BackgroundTasks,
    store: WorkflowStore = Depends(get_workflow_store),
    runner: Any = Depends(get_workflow_runner),
    request_id: str = Depends(generate_request_id),
):
    """
    创建一个新的文献分析工作流

    - **query**: 研究主题（必填）
    - **year_range**: 年份范围，如 "2024-2026" 或 "2025"
    - **max_papers**: 最大论文数量（1-100，默认 10）
    - **source**: 数据源（arxiv/google/both，默认 arxiv）
    """
    settings = get_settings()
    workflow_id = f"wf_{datetime.now().strftime('%Y%m%d%H%M%S')}_{request_id[-8:]}"
    now = datetime.now().isoformat()

    # 创建工作流记录
    workflow = WorkflowRecord(
        id=workflow_id,
        query=request.query,
        year_range=request.year_range,
        max_papers=request.max_papers,
        source=request.source,
        status="pending",
        current_stage=None,
        progress=0,
        message="等待启动",
        papers_found=0,
        result=None,
        error=None,
        created_at=now,
        updated_at=now,
        completed_at=None,
    )

    store.create_workflow(workflow)

    # 立即启动工作流（后台运行）
    async def run_workflow_bg():
        try:
            # 创建适配器实例
            from backend.app.adapters.multi_agent_adapter import MultiAgentAdapter
            adapter = MultiAgentAdapter(
                download_dir=str(settings.download_dir_path),
                max_papers=request.max_papers,
                source=request.source,
                workflow_store=store,  # 传入 workflow_store
            )
            await adapter.initialize()
            try:
                await runner.start_workflow(workflow_id, adapter)
            finally:
                await adapter.shutdown()
        except Exception as e:
            store.update_workflow_status(
                workflow_id,
                status="failed",
                error=str(e),
                message=f"工作流失败：{str(e)}",
            )

    background_tasks.add_task(run_workflow_bg)

    # 返回工作流详情
    return _workflow_to_detail(workflow)


@router.post(
    "/from-local-papers",
    response_model=WorkflowDetail,
    status_code=status.HTTP_201_CREATED,
    summary="从本地论文创建工作流并启动",
)
async def create_workflow_from_local_papers(
    request: Request,
    background_tasks: BackgroundTasks,
    store: WorkflowStore = Depends(get_workflow_store),
    runner: Any = Depends(get_workflow_runner),
    request_id: str = Depends(generate_request_id),
):
    """
    从本地上传的论文创建工作流并启动（跳过搜索阶段）

    - **paper_ids**: 论文 ID 列表
    - **query**: 研究主题
    """
    form_data = await request.form()
    paper_ids = form_data.getlist("paper_ids") or form_data.getlist("paper_ids[]")
    query = str(form_data.get("query") or "").strip()

    if not paper_ids:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="paper_ids is required",
        )

    if not query:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="query is required",
        )

    settings = get_settings()
    workflow_id = f"wf_{datetime.now().strftime('%Y%m%d%H%M%S')}_{request_id[-8:]}"
    now = datetime.now().isoformat()

    # 创建工作流记录
    workflow = WorkflowRecord(
        id=workflow_id,
        query=query,
        rewritten_query=query,
        year_range=None,
        max_papers=len(paper_ids),
        source="local_upload",
        status="pending",
        current_stage=None,
        progress=0,
        message="等待启动",
        papers_found=len(paper_ids),
        result=None,
        error=None,
        created_at=now,
        updated_at=now,
        completed_at=None,
    )

    store.create_workflow(workflow)

    # 立即启动工作流（后台运行）
    async def run_workflow_bg():
        try:
            from backend.app.adapters.multi_agent_adapter import MultiAgentAdapter
            adapter = MultiAgentAdapter(
                download_dir=str(settings.download_dir_path),
                max_papers=len(paper_ids),
                source="local_upload",
                workflow_store=store,
            )
            await adapter.initialize()
            try:
                await runner.start_workflow_with_local_papers(
                    workflow_id,
                    adapter,
                    paper_ids,
                )
            finally:
                await adapter.shutdown()
        except Exception as e:
            store.update_workflow_status(
                workflow_id,
                status="failed",
                error=str(e),
                message=f"工作流失败：{str(e)}",
            )

    background_tasks.add_task(run_workflow_bg)

    # 返回工作流详情
    return _workflow_to_detail(workflow)


@router.get(
    "",
    response_model=WorkflowListResponse,
    summary="获取工作流列表",
)
async def list_workflows(
    status_filter: Optional[WorkflowStatus] = None,
    pagination: dict = Depends(get_pagination),
    store: WorkflowStore = Depends(get_workflow_store),
):
    """
    获取工作流列表（分页）

    - **status_filter**: 按状态过滤（可选）
    - **page**: 页码（默认 1）
    - **page_size**: 每页数量（默认 20，最大 100）
    """
    status_str = status_filter.value if status_filter else None

    workflows = store.get_workflows(
        status=status_str,
        limit=pagination["page_size"],
        offset=pagination["offset"],
    )

    total = store.get_workflows_count(status=status_str)

    items = [_workflow_to_summary(wf) for wf in workflows]

    return WorkflowListResponse(
        items=items,
        total=total,
        page=pagination["page"],
        page_size=pagination["page_size"],
        has_more=pagination["offset"] + len(workflows) < total,
    )


@router.get(
    "/{workflow_id}",
    response_model=WorkflowDetail,
    summary="获取工作流详情",
    responses={
        404: {"model": ErrorResponse, "description": "工作流不存在"},
    },
)
async def get_workflow(
    workflow_id: str,
    store: WorkflowStore = Depends(get_workflow_store),
):
    """获取指定工作流的详细信息"""
    workflow = store.get_workflow(workflow_id)

    if not workflow:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Workflow not found: {workflow_id}",
        )

    return _workflow_to_detail(workflow)


@router.post(
    "/{workflow_id}/cancel",
    response_model=WorkflowCancelResponse,
    summary="取消工作流",
    responses={
        404: {"model": ErrorResponse, "description": "工作流不存在"},
        400: {"model": ErrorResponse, "description": "工作流已完成/失败"},
    },
)
async def cancel_workflow(
    workflow_id: str,
    request: Optional[WorkflowCancelRequest] = None,
    store: WorkflowStore = Depends(get_workflow_store),
    runner: Any = Depends(get_workflow_runner),
):
    """
    取消运行中的工作流

    - **reason**: 取消原因（可选）
    - **graceful**: 是否优雅关闭，等待当前操作完成（可选，默认 false）
    - **graceful_timeout**: 优雅关闭超时时间（可选，默认 30 秒）
    """
    workflow = store.get_workflow(workflow_id)

    if not workflow:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Workflow not found: {workflow_id}",
        )

    if workflow.status in ("completed", "failed", "cancelled"):
        return WorkflowCancelResponse(
            workflow_id=workflow_id,
            status="already_completed",
            message=f"工作流已完成，无法取消（当前状态：{workflow.status}）",
        )

    # 调用 WorkflowRunner.cancel_workflow() 真正取消运行中的任务
    cancelled = await runner.cancel_workflow(
        workflow_id,
        reason=request.reason if request else None,
        graceful=request.graceful if request else False,
        graceful_timeout=request.graceful_timeout if request else 30.0,
    )

    if cancelled:
        return WorkflowCancelResponse(
            workflow_id=workflow_id,
            status="cancelled",
            message="工作流已取消",
        )
    else:
        # 如果 runner 返回 False，说明工作流已经完成/失败/取消
        updated_workflow = store.get_workflow(workflow_id)
        return WorkflowCancelResponse(
            workflow_id=workflow_id,
            status=updated_workflow.status if updated_workflow else "unknown",
            message=f"工作流无法取消（当前状态：{updated_workflow.status if updated_workflow else 'unknown'}）",
        )


@router.get(
    "/{workflow_id}/papers",
    summary="获取工作流的论文列表",
)
async def get_workflow_papers(
    workflow_id: str,
    pagination: dict = Depends(get_pagination),
    store: WorkflowStore = Depends(get_workflow_store),
):
    """获取指定工作流的论文列表"""
    workflow = store.get_workflow(workflow_id)

    if not workflow:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Workflow not found: {workflow_id}",
        )

    papers = store.get_papers_by_workflow(
        workflow_id,
        limit=pagination["page_size"],
        offset=pagination["offset"],
    )

    total = len(papers)  # TODO: 使用 count 方法

    return {
        "items": papers,
        "total": total,
        "page": pagination["page"],
        "page_size": pagination["page_size"],
    }


@router.get(
    "/{workflow_id}/events",
    summary="获取工作流事件日志",
)
async def get_workflow_events(
    workflow_id: str,
    store: WorkflowStore = Depends(get_workflow_store),
):
    """获取指定工作流的事件日志，按时间正序返回。"""
    workflow = store.get_workflow(workflow_id)

    if not workflow:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Workflow not found: {workflow_id}",
        )

    events = store.get_events(workflow_id, limit=500)
    items = [
        {
            "id": event.id,
            "event_type": event.event_type,
            "stage": event.stage,
            "status": event.status,
            "progress": event.progress,
            "message": event.message,
            "data": event.data,
            "timestamp": event.timestamp,
        }
        for event in reversed(events)
    ]

    return {
        "items": items,
        "total": len(items),
    }


@router.get(
    "/{workflow_id}/report",
    summary="获取工作流的最终报告",
)
async def get_workflow_report(
    workflow_id: str,
    store: WorkflowStore = Depends(get_workflow_store),
):
    """获取指定工作流的最终报告"""
    workflow = store.get_workflow(workflow_id)

    if not workflow:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Workflow not found: {workflow_id}",
        )

    report = store.get_report_by_workflow(workflow_id)

    if not report:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Report not found for workflow: {workflow_id}",
        )

    return {
        "report_id": report.report_id,
        "workflow_id": report.workflow_id,
        "title": report.content_markdown.split("\n")[0].lstrip("# ").strip() if report.content_markdown else "无标题报告",
        "content_markdown": report.content_markdown,
        "word_count": report.word_count,
        "created_at": report.created_at,
    }


# ========== 辅助函数 ==========

def _workflow_to_summary(workflow: WorkflowRecord) -> WorkflowSummary:
    """转换为摘要对象"""
    return WorkflowSummary(
        id=workflow.id,
        query=workflow.query,
        year_range=workflow.year_range,
        source=workflow.source,
        status=WorkflowStatus(workflow.status),
        current_stage=workflow.current_stage,
        progress=workflow.progress,
        papers_found=workflow.papers_found,
        created_at=datetime.fromisoformat(workflow.created_at),
        completed_at=(
            datetime.fromisoformat(workflow.completed_at)
            if workflow.completed_at else None
        ),
    )


def _workflow_to_detail(workflow: WorkflowRecord) -> WorkflowDetail:
    """转换为详情对象"""
    # 获取阶段状态（从事件日志）
    stages = []  # TODO: 从事件构建阶段状态

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
