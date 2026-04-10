"""
报告服务 - 报告数据管理

功能：
- 报告列表查询
- 报告详情
- 报告下载（Markdown/PDF）
"""
from typing import List, Dict, Any, Optional
from pathlib import Path
import aiofiles
from backend.app.services.workflow_store import WorkflowStore, ReportRecord


class ReportService:
    """报告服务"""

    def __init__(self, workflow_store: WorkflowStore):
        self.workflow_store = workflow_store

    def list_reports(
        self,
        workflow_id: Optional[str] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> Dict[str, Any]:
        """
        获取报告列表（支持过滤和分页）

        Args:
            workflow_id: 工作流 ID 过滤
            page: 页码
            page_size: 每页数量

        Returns:
            {
                "items": [...],
                "total": 100,
                "page": 1,
                "page_size": 20,
                "total_pages": 5
            }
        """
        all_reports = self.workflow_store.list_reports(workflow_id=workflow_id)

        # 分页
        total = len(all_reports)
        total_pages = (total + page_size - 1) // page_size
        start = (page - 1) * page_size
        end = start + page_size
        items = all_reports[start:end]

        return {
            "items": [self._report_to_dict(r) for r in items],
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": total_pages,
        }

    def get_report(self, report_id: str) -> Optional[Dict[str, Any]]:
        """获取报告详情"""
        report = self.workflow_store.get_report(report_id)
        if not report:
            return None
        return self._report_to_dict(report)

    def get_report_by_workflow(self, workflow_id: str) -> Optional[Dict[str, Any]]:
        """根据工作流 ID 获取报告"""
        reports = self.workflow_store.list_reports(workflow_id=workflow_id)
        if reports:
            return self._report_to_dict(reports[0])
        return None

    async def download_report(
        self,
        report_id: str,
        format: str = "markdown",
    ) -> Optional[tuple]:
        """
        下载报告

        Args:
            report_id: 报告 ID
            format: 下载格式 (markdown/pdf)

        Returns:
            (content, filename, content_type) 元组，如果报告不存在则返回 None
        """
        report = self.workflow_store.get_report(report_id)
        if not report:
            return None

        if format == "markdown":
            filename = f"report_{report_id}.md"
            content_type = "text/markdown"
            if report.file_path and Path(report.file_path).exists():
                async with aiofiles.open(report.file_path, "r", encoding="utf-8") as f:
                    content = await f.read()
            else:
                content = report.content_markdown
            return (content, filename, content_type)

        elif format == "pdf":
            # 目前不支持 PDF 导出
            return None

        return None

    def _report_to_dict(self, report: ReportRecord) -> Dict[str, Any]:
        """转换 ReportRecord 为字典"""
        return {
            "report_id": report.report_id,
            "workflow_id": report.workflow_id,
            "title": self._extract_title(report.content_markdown),
            "word_count": report.word_count,
            "paper_count": self._count_papers(report.content_markdown),
            "created_at": report.created_at,
            "content_markdown": report.content_markdown,
            "file_path": report.file_path,
        }

    def _extract_title(self, markdown_content: str) -> str:
        """从 Markdown 内容提取标题"""
        if not markdown_content:
            return ""
        lines = markdown_content.split("\n")
        for line in lines:
            if line.startswith("# "):
                return line[2:].strip()
        return "无标题报告"

    def _count_papers(self, markdown_content: str) -> int:
        """从 Markdown 内容计算引用的论文数量"""
        if not markdown_content:
            return 0
        # 简单统计：计算包含 "arxiv" 或 "doi" 的行数
        count = 0
        for line in markdown_content.split("\n"):
            line_lower = line.lower()
            if "arxiv" in line_lower or "doi:" in line_lower:
                count += 1
        return count
