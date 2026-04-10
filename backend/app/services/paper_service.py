"""
论文服务 - 论文数据管理

功能：
- 论文列表查询
- 论文详情
- PDF 下载
"""
from typing import List, Dict, Any, Optional
from pathlib import Path
import aiofiles
from backend.app.services.workflow_store import WorkflowStore, PaperRecord


class PaperService:
    """论文服务"""

    def __init__(self, workflow_store: WorkflowStore):
        self.workflow_store = workflow_store

    def list_papers(
        self,
        workflow_id: Optional[str] = None,
        source: Optional[str] = None,
        search: Optional[str] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> Dict[str, Any]:
        """
        获取论文列表（支持过滤和分页）

        Args:
            workflow_id: 工作流 ID 过滤
            source: 数据源过滤 (arxiv/google)
            search: 标题搜索关键词
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
        all_papers = self.workflow_store.list_papers(
            workflow_id=workflow_id,
            source=source,
            search=search,
        )

        # 分页
        total = len(all_papers)
        total_pages = (total + page_size - 1) // page_size
        start = (page - 1) * page_size
        end = start + page_size
        items = all_papers[start:end]

        return {
            "items": [self._paper_to_dict(p) for p in items],
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": total_pages,
        }

    def get_paper(self, paper_id: str) -> Optional[Dict[str, Any]]:
        """获取论文详情"""
        paper = self.workflow_store.get_paper(paper_id)
        if not paper:
            return None
        return self._paper_to_dict(paper)

    async def download_pdf(self, paper_id: str) -> Optional[bytes]:
        """
        下载论文 PDF

        Args:
            paper_id: 论文 ID

        Returns:
            PDF 二进制数据，如果论文不存在或 PDF 不存在则返回 None
        """
        paper = self.workflow_store.get_paper(paper_id)
        if not paper or not paper.pdf_path:
            return None

        pdf_path = Path(paper.pdf_path)
        if not pdf_path.exists():
            return None

        async with aiofiles.open(pdf_path, "rb") as f:
            return await f.read()

    def _paper_to_dict(self, paper: PaperRecord) -> Dict[str, Any]:
        """转换 PaperRecord 为字典"""
        import json

        data = {
            "paper_id": paper.paper_id,
            "workflow_id": paper.workflow_id,
            "title": paper.title,
            "abstract": paper.abstract,
            "year": paper.year,
            "source": paper.source,
            "pdf_available": bool(paper.pdf_path and Path(paper.pdf_path).exists()),
            "download_status": paper.download_status,
            "created_at": paper.created_at,
        }

        # 解析作者列表
        try:
            data["authors"] = json.loads(paper.authors) if paper.authors else []
        except (json.JSONDecodeError, TypeError):
            data["authors"] = []

        return data
