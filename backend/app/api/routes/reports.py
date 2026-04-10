"""
报告 API 路由
"""
from fastapi import APIRouter, Depends, HTTPException, status
from starlette.background import BackgroundTask
from typing import Optional
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED
import tempfile

from backend.app.schemas.report import (
    ReportSummary,
    ReportDetail,
    ReportDownloadResponse,
    ReportBatchRequest,
    ReportBatchDeleteResponse,
)
from backend.app.services.workflow_store import WorkflowStore
from backend.app.core.deps import get_workflow_store, get_pagination

router = APIRouter(prefix="/api/reports", tags=["reports"])


@router.get(
    "",
    summary="获取报告列表",
)
async def list_reports(
    pagination: dict = Depends(get_pagination),
    store: WorkflowStore = Depends(get_workflow_store),
):
    """获取所有报告列表"""
    reports = store.get_all_reports(
        limit=pagination["page_size"],
        offset=pagination["offset"],
    )

    total = store.get_reports_count()

    items = [_report_to_summary(report) for report in reports]

    return {
        "items": items,
        "total": total,
        "page": pagination["page"],
        "page_size": pagination["page_size"],
    }


@router.post(
    "/batch-download",
    summary="批量下载报告（ZIP）",
)
async def batch_download_reports(
    request: ReportBatchRequest,
    store: WorkflowStore = Depends(get_workflow_store),
):
    """批量下载报告，返回 ZIP 压缩包"""
    from fastapi.responses import FileResponse

    reports = [store.get_report(report_id) for report_id in request.report_ids]
    valid_reports = [report for report in reports if report]

    if not valid_reports:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No reports found for selected ids",
        )

    with tempfile.NamedTemporaryFile(prefix="reports_", suffix=".zip", delete=False) as tmp:
        zip_path = Path(tmp.name)

    with ZipFile(zip_path, "w", ZIP_DEFLATED) as zip_file:
        for report in valid_reports:
            filename = f"reports/{report.report_id}.md"
            if report.file_path and Path(report.file_path).exists():
                zip_file.write(Path(report.file_path), arcname=filename)
            else:
                zip_file.writestr(filename, report.content_markdown or "")

    return FileResponse(
        path=str(zip_path),
        media_type="application/zip",
        filename="reports_bundle.zip",
        background=BackgroundTask(zip_path.unlink, missing_ok=True),
    )


@router.post(
    "/batch-delete",
    response_model=ReportBatchDeleteResponse,
    summary="批量删除报告记录和文件",
)
async def batch_delete_reports(
    request: ReportBatchRequest,
    store: WorkflowStore = Depends(get_workflow_store),
):
    """批量删除报告记录，并尝试删除对应文件"""
    reports = [store.get_report(report_id) for report_id in request.report_ids]
    deleted_file_count = 0
    existing_ids = []

    for report in reports:
        if not report:
            continue
        existing_ids.append(report.report_id)
        if report.file_path:
            report_path = Path(report.file_path)
            if report_path.exists():
                report_path.unlink()
                deleted_file_count += 1

    deleted_count = store.delete_reports(existing_ids)

    return ReportBatchDeleteResponse(
        deleted_count=deleted_count,
        deleted_file_count=deleted_file_count,
    )


@router.get(
    "/{report_id}",
    response_model=ReportDetail,
    summary="获取报告详情",
)
async def get_report(
    report_id: str,
    store: WorkflowStore = Depends(get_workflow_store),
):
    """获取指定报告的详细内容"""
    report = store.get_report(report_id)

    if not report:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Report not found: {report_id}",
        )

    return _report_to_detail(report)


@router.get(
    "/{report_id}/download",
    summary="下载报告文件",
)
async def download_report(
    report_id: str,
    format: str = "markdown",
    store: WorkflowStore = Depends(get_workflow_store),
):
    """下载报告文件（Markdown 或 PDF）"""
    report = store.get_report(report_id)

    if not report:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Report not found: {report_id}",
        )

    from fastapi.responses import FileResponse, Response

    if format.lower() == "markdown" or format.lower() == "md":
        # 返回 Markdown 内容
        return Response(
            content=report.content_markdown,
            media_type="text/markdown",
            headers={
                "Content-Disposition": f'attachment; filename="report_{report_id}.md"',
            },
        )

    elif format.lower() == "pdf":
        # 如果存储了 PDF 文件路径，返回 PDF
        if report.file_path and report.file_path.endswith(".pdf"):
            pdf_path = Path(report.file_path)
            if pdf_path.exists():
                return FileResponse(
                    path=str(pdf_path),
                    media_type="application/pdf",
                    filename=f"report_{report_id}.pdf",
                )

        # TODO: 动态生成 PDF
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="PDF version not available",
        )

    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid format. Use 'markdown' or 'pdf'.",
        )


@router.get(
    "/workflow/{workflow_id}",
    response_model=ReportDetail,
    summary="根据工作流 ID 获取报告",
)
async def get_report_by_workflow(
    workflow_id: str,
    store: WorkflowStore = Depends(get_workflow_store),
):
    """根据工作流 ID 获取报告"""
    report = store.get_report_by_workflow(workflow_id)

    if not report:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Report not found for workflow: {workflow_id}",
        )

    return _report_to_detail(report)


# ========== 辅助函数 ==========

def _report_to_summary(report) -> ReportSummary:
    """转换为摘要对象"""
    # 提取标题（第一行）
    title = report.content_markdown.split("\n")[0].lstrip("# ").strip()

    return ReportSummary(
        report_id=report.report_id,
        workflow_id=report.workflow_id,
        title=title,
        word_count=report.word_count,
        paper_count=0,  # TODO: 从 workflow 获取
        created_at=report.created_at,
    )


def _report_to_detail(report) -> ReportDetail:
    """转换为详情对象"""
    return ReportDetail(
        report_id=report.report_id,
        workflow_id=report.workflow_id,
        content_markdown=report.content_markdown,
        file_path=report.file_path,
        word_count=report.word_count,
        paper_count=0,  # TODO: 从 workflow 获取
        created_at=report.created_at,
    )
