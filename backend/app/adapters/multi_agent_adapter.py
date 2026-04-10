"""
多 Agent 适配器 - 封装现有 WorkflowEngine 和 Agent 代码

功能：
- 适配现有的 WorkflowEngine 接口
- 添加事件回调支持
- 统一返回格式
- 支持取消检查
"""
import asyncio
from typing import Dict, Any, Optional, Callable, List
from pathlib import Path
import sys
import json
import ast
from datetime import datetime

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from core.workflow_engine import WorkflowEngine
from memory.task_memory import TaskMemory
from core.skill_loader import SkillLoader


class MultiAgentAdapter:
    """
    多 Agent 适配器

    将现有的 WorkflowEngine 适配为事件驱动的接口，
    支持进度回调和取消检查。

    使用示例:
        adapter = MultiAgentAdapter()
        await adapter.initialize()

        result = await adapter.run_search(
            query="transformer",
            year_range="2024-2026",
            max_papers=10,
            workflow_id="wf_xxx",
            on_progress=callback_func,
        )
    """

    def __init__(
        self,
        download_dir: str = "output/papers",
        max_papers: int = 10,
        source: str = "arxiv",
        workflow_store: Optional[Any] = None,
    ):
        self.download_dir = download_dir
        self.max_papers = max_papers
        self.source = source
        self.workflow_store = workflow_store

        # 核心组件（延迟初始化）
        self.system: Optional[Any] = None
        self.agents: Dict[str, Any] = {}
        self.task_memory = TaskMemory()
        self.skill_loader = SkillLoader()

        # 工作流引擎缓存（按配置）
        self._workflow_engines: Dict[str, WorkflowEngine] = {}

        # 阶段数据缓存（用于跨阶段传递）
        self._stage_data: Dict[str, Any] = {}

    async def initialize(self) -> None:
        """初始化系统组件"""
        from main import MultiAgentSystem

        # 创建 MultiAgentSystem
        self.system = MultiAgentSystem()
        await self.system.initialize()
        self.agents = self.system.agents

        print("[MultiAgentAdapter] 初始化完成")

    async def shutdown(self) -> None:
        """关闭系统"""
        if self.system:
            await self.system.shutdown()
        print("[MultiAgentAdapter] 已关闭")

    @staticmethod
    def _parse_authors(authors_value: Any) -> List[str]:
        """兼容 JSON、Python 列表字符串和单个作者字符串。"""
        if not authors_value:
            return []

        if isinstance(authors_value, list):
            return [str(item) for item in authors_value if item]

        if isinstance(authors_value, str):
            raw = authors_value.strip()
            if not raw:
                return []

            try:
                parsed = json.loads(raw)
            except json.JSONDecodeError:
                try:
                    parsed = ast.literal_eval(raw)
                except (ValueError, SyntaxError):
                    parsed = raw

            if isinstance(parsed, list):
                return [str(item) for item in parsed if item]
            if isinstance(parsed, str):
                return [parsed] if parsed else []

        return [str(authors_value)]

    async def load_local_papers(
        self,
        paper_ids: List[str],
        workflow_id: str,
        on_progress: Optional[Callable] = None,
    ) -> Dict[str, Any]:
        """
        从本地文件加载论文（跳过搜索阶段）

        Args:
            paper_ids: 论文 ID 列表
            workflow_id: 工作流 ID
            on_progress: 进度回调函数

        Returns:
            {"papers": [...], "count": N}
        """
        try:
            if not self.workflow_store:
                raise ValueError("workflow_store not initialized")

            total = len(paper_ids)
            papers = []

            for i, paper_id in enumerate(paper_ids):
                if on_progress:
                    progress = int(((i + 1) / total) * 100)
                    on_progress(workflow_id, "search", progress, f"加载论文 {i+1}/{total}...")

                # 从数据库获取论文记录
                paper_record = self.workflow_store.get_paper(paper_id)
                if not paper_record:
                    continue

                # 解析 PDF 获取摘要（如果需要）
                if not paper_record.abstract and paper_record.pdf_path:
                    abstract = await self._extract_abstract_from_pdf(paper_record.pdf_path)
                    if abstract:
                        self.workflow_store.update_paper(paper_id, abstract=abstract)
                        paper_record.abstract = abstract

                paper = {
                    "arxiv_id": paper_record.paper_id,
                    "title": paper_record.title,
                    "authors": self._parse_authors(paper_record.authors),
                    "summary": paper_record.abstract or "",
                    "published": paper_record.year or "",
                    "published_year": paper_record.year,
                    "source": paper_record.source,
                    "pdf_path": paper_record.pdf_path,
                    "is_local": True,  # 标记为本地论文
                }
                papers.append(paper)

            # 缓存论文
            self._stage_data[f"{workflow_id}_papers"] = papers

            # 更新工作流状态
            self.workflow_store.update_workflow_status(
                workflow_id,
                status="running",
                papers_found=len(papers),
                message=f"已加载 {len(papers)} 篇本地论文",
            )

            if on_progress:
                on_progress(
                    workflow_id, "search", 100,
                    f"加载完成，共 {len(papers)} 篇论文",
                    {"papers_found": len(papers)},
                )

            return {"papers": papers, "count": len(papers)}

        except Exception as e:
            if on_progress:
                on_progress(workflow_id, "search", 0, f"加载失败：{str(e)}")
            raise

    async def _extract_abstract_from_pdf(self, pdf_path: str) -> str:
        """从 PDF 提取摘要"""
        try:
            from tools.pdf_parser_tool import PDFParserTool
            parser = PDFParserTool()

            # 提取前 5 页
            result = await parser.extract_text(
                pdf_path,
                page_range={"start": 0, "end": 5},
            )

            if not result.success:
                return ""

            full_text = result.data.get("full_text", "")

            # 提取摘要
            return self._extract_abstract_from_text(full_text)

        except Exception as e:
            print(f"[MultiAgentAdapter] PDF 摘要提取失败：{e}")
            return ""

    def _extract_abstract_from_text(self, full_text: str) -> str:
        """从全文中提取摘要（简单启发式）"""
        lines = full_text.split('\n')
        abstract_lines = []
        in_abstract = False

        for line in lines:
            line_lower = line.lower().strip()

            # 检测摘要开始
            if 'abstract' in line_lower or '摘要' in line_lower:
                in_abstract = True
                if ':' in line:
                    line = line.split(':', 1)[1]
                continue

            # 检测摘要结束
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

    def _get_workflow_engine(
        self,
        max_papers: int,
        source: str,
        download_dir: str,
    ) -> WorkflowEngine:
        """获取或创建工作流引擎实例"""
        key = f"{max_papers}_{source}_{download_dir}"

        if key not in self._workflow_engines:
            self._workflow_engines[key] = WorkflowEngine(
                search_agent=self.agents["search"],
                analyst_agent=self.agents["analyst"],
                writer_agent=self.agents["writer"],
                reviewer_agent=self.agents["reviewer"],
                editor_agent=self.agents["editor"],
                task_memory=self.task_memory,
                skill_loader=self.skill_loader,
                download_dir=download_dir,
                max_papers=max_papers,
                source=source,
            )

        return self._workflow_engines[key]

    # ========== 阶段执行方法 ==========

    async def run_search(
        self,
        query: str,
        year_range: Optional[str],
        max_papers: int,
        source: str,
        download_dir: str,
        workflow_id: str,
        on_progress: Optional[Callable] = None,
    ) -> Dict[str, Any]:
        """
        运行搜索阶段

        Args:
            query: 研究主题
            year_range: 年份范围
            max_papers: 最大论文数量
            source: 数据源
            download_dir: 下载目录
            workflow_id: 工作流 ID
            on_progress: 进度回调函数 (stage, progress, message, data)

        Returns:
            {"papers": [...], "count": N}
        """
        # 获取工作流引擎
        engine = self._get_workflow_engine(max_papers, source, download_dir)

        # 执行搜索
        try:
            # 进度 0% - 开始
            if on_progress:
                on_progress(workflow_id, "search", 0, "正在连接 ArXiv API...")
                await asyncio.sleep(0.1)  # 让 UI 有机会渲染

            # 调用 Search Agent 并传入进度回调
            search_result = await engine._run_search(
                query,
                year_range,
                on_progress=lambda stage, progress, message, data=None: on_progress(workflow_id, stage, progress, message, data) if on_progress else None
            )

            papers = search_result.get("papers", [])
            count = len(papers)

            # 保存论文到 workflow_store
            if self.workflow_store and papers:
                from backend.app.services.workflow_store import PaperRecord
                for paper in papers:
                    paper_record = PaperRecord(
                        paper_id=paper.get("arxiv_id", f"paper_{count}"),
                        workflow_id=workflow_id,
                        title=paper.get("title", "Unknown"),
                        authors=json.dumps(paper.get("authors", []), ensure_ascii=False),
                        abstract=paper.get("summary", ""),
                        year=paper.get("published_year") or (paper.get("published", "")[:4] if paper.get("published") else None),
                        source=paper.get("source", "arxiv"),
                        pdf_path=paper.get("pdf_path"),
                        download_status="downloaded" if paper.get("pdf_path") else "pending",
                        created_at=datetime.now().isoformat(),
                    )
                    self.workflow_store.add_paper(paper_record)

                # 更新工作流的 papers_found
                self.workflow_store.update_workflow_status(
                    workflow_id,
                    status="running",
                    papers_found=count,
                )

            # 缓存论文用于跨阶段传递
            self._stage_data[f"{workflow_id}_papers"] = papers

            # 进度 100% - 完成
            if on_progress:
                on_progress(
                    workflow_id, "search", 100,
                    f"搜索完成，找到 {count} 篇论文",
                    {"papers_found": count},
                )

            return {"papers": papers, "count": count}

        except Exception as e:
            if on_progress:
                on_progress(workflow_id, "search", 0, f"搜索失败：{str(e)}")
            raise

    async def run_analyst(
        self,
        workflow_id: str,
        on_progress: Optional[Callable] = None,
    ) -> Dict[str, Any]:
        """
        运行分析阶段

        Args:
            workflow_id: 工作流 ID
            on_progress: 进度回调函数

        Returns:
            {"analysis": [...], "count": N}
        """
        try:
            if on_progress:
                on_progress(workflow_id, "analyst", 0, "开始分析论文...")

            # 优先从缓存获取论文
            papers = self._stage_data.get(f"{workflow_id}_papers")

            # 如果缓存没有，从 workflow_store 读取
            if not papers and self.workflow_store:
                paper_records = self.workflow_store.get_papers_by_workflow(workflow_id, limit=100)
                papers = []
                for pr in paper_records:
                    paper = {
                        "arxiv_id": pr.paper_id,
                        "title": pr.title,
                        "authors": self._parse_authors(pr.authors),
                        "summary": pr.abstract,
                        "published": pr.year,
                        "published_year": pr.year,
                        "source": pr.source,
                        "pdf_path": pr.pdf_path,
                    }
                    papers.append(paper)
                # 缓存到内存
                self._stage_data[f"{workflow_id}_papers"] = papers

            if not papers:
                raise ValueError("没有找到待分析的论文")

            # 逐个分析论文
            analysis_results = []
            total = len(papers)

            for i, paper in enumerate(papers):
                if on_progress:
                    progress = int((i / total) * 100)
                    on_progress(
                        workflow_id, "analyst", progress,
                        f"正在分析第 {i+1}/{total} 篇论文...",
                        {"current_paper": i + 1, "total": total},
                    )

                # 调用 Analyst Agent
                analysis = await self._analyze_paper(paper)
                analysis_results.append(analysis)

            # 缓存分析结果
            self._stage_data[f"{workflow_id}_analysis"] = analysis_results

            if on_progress:
                on_progress(
                    workflow_id, "analyst", 100,
                    f"完成 {len(analysis_results)} 篇论文分析",
                    {"analysis_count": len(analysis_results)},
                )

            return {"analysis": analysis_results, "count": len(analysis_results)}

        except Exception as e:
            if on_progress:
                on_progress(workflow_id, "analyst", 0, f"分析失败：{str(e)}")
            raise

    async def run_writer(
        self,
        workflow_id: str,
        on_progress: Optional[Callable] = None,
    ) -> Dict[str, Any]:
        """
        运行写作阶段

        Args:
            workflow_id: 工作流 ID
            on_progress: 进度回调函数

        Returns:
            {"draft": str}
        """
        try:
            if on_progress:
                on_progress(workflow_id, "writer", 0, "开始撰写报告...")

            # 优先从缓存获取分析结果
            analysis = self._stage_data.get(f"{workflow_id}_analysis")

            # 如果缓存没有，从 workflow_store 读取（TODO: 需要实现分析结果存储）
            if not analysis:
                # 临时方案：使用占位分析结果
                papers = self._stage_data.get(f"{workflow_id}_papers")
                if not papers and self.workflow_store:
                    paper_records = self.workflow_store.get_papers_by_workflow(workflow_id, limit=100)
                    papers = []
                    for pr in paper_records:
                        paper = {
                            "arxiv_id": pr.paper_id,
                            "title": pr.title,
                            "authors": self._parse_authors(pr.authors),
                            "summary": pr.abstract,
                            "published": pr.year,
                            "published_year": pr.year,
                            "source": pr.source,
                            "pdf_path": pr.pdf_path,
                        }
                        papers.append(paper)

                if papers:
                    # 创建占位分析结果
                    analysis = []
                    for paper in papers:
                        analysis.append({
                            "title": paper.get("title", "Unknown"),
                            "authors": paper.get("authors", []),
                            "arxiv_id": paper.get("arxiv_id", ""),
                            "summary": paper.get("summary", ""),
                            "research_question": "待分析",
                            "methodology": "待分析",
                            "key_contributions": ["待分析"],
                            "innovations": ["待分析"],
                            "limitations": ["待分析"],
                        })
                    # 缓存分析结果
                    self._stage_data[f"{workflow_id}_analysis"] = analysis

            if not analysis:
                raise ValueError("没有找到待写作的分析结果")

            # 获取原始论文数据
            papers = self._stage_data.get(f"{workflow_id}_papers")
            if not papers and self.workflow_store:
                paper_records = self.workflow_store.get_papers_by_workflow(workflow_id, limit=100)
                papers = []
                for pr in paper_records:
                    paper = {
                        "arxiv_id": pr.paper_id,
                        "title": pr.title,
                        "authors": self._parse_authors(pr.authors),
                        "summary": pr.abstract,
                        "published": pr.year,
                        "published_year": pr.year,
                        "source": pr.source,
                        "pdf_path": pr.pdf_path,
                    }
                    papers.append(paper)

            # 调用 Writer Agent
            writer_result = await self.agents["writer"].run_once({
                "analysis": analysis,
                "original_papers": papers or [],
            })

            draft = writer_result.get("draft", "")

            # 缓存草稿
            self._stage_data[f"{workflow_id}_draft"] = draft

            if on_progress:
                on_progress(
                    workflow_id, "writer", 100,
                    "报告草稿完成",
                    {"word_count": len(draft.split())},
                )

            return {"draft": draft}

        except Exception as e:
            if on_progress:
                on_progress(workflow_id, "writer", 0, f"写作失败：{str(e)}")
            raise

    async def run_reviewer(
        self,
        workflow_id: str,
        on_progress: Optional[Callable] = None,
    ) -> Dict[str, Any]:
        """
        运行审核阶段

        Args:
            workflow_id: 工作流 ID
            on_progress: 进度回调函数

        Returns:
            {"review": [...]}
        """
        try:
            if on_progress:
                on_progress(workflow_id, "reviewer", 0, "开始审核报告...")

            # 优先从缓存获取草稿
            draft = self._stage_data.get(f"{workflow_id}_draft")

            if not draft:
                # 尝试从分析结果生成简易草稿
                analysis = self._stage_data.get(f"{workflow_id}_analysis")
                if analysis:
                    draft = "# 分析报告\n\n"
                    for i, a in enumerate(analysis, 1):
                        draft += f"## {i}. {a.get('title', 'Unknown')}\n\n"
                        draft += f"**摘要**: {a.get('summary', 'N/A')}\n\n"
                    self._stage_data[f"{workflow_id}_draft"] = draft
                else:
                    raise ValueError("没有找到待审核的草稿")

            # 调用 Reviewer Agent
            review_result = await self.agents["reviewer"].run_once({
                "draft": draft,
            })

            review = review_result.get("review", [])

            # 缓存审核结果
            self._stage_data[f"{workflow_id}_review"] = review

            if on_progress:
                on_progress(
                    workflow_id, "reviewer", 100,
                    "报告审核完成",
                    {"review_count": len(review)},
                )

            return {"review": review}

        except Exception as e:
            if on_progress:
                on_progress(workflow_id, "reviewer", 0, f"审核失败：{str(e)}")
            raise

    async def run_editor(
        self,
        workflow_id: str,
        on_progress: Optional[Callable] = None,
    ) -> Dict[str, Any]:
        """
        运行编辑阶段

        Args:
            workflow_id: 工作流 ID
            on_progress: 进度回调函数

        Returns:
            {"final_report": str}
        """
        try:
            if on_progress:
                on_progress(workflow_id, "editor", 0, "开始编辑最终报告...")

            # 优先从缓存获取草稿和审核意见
            draft = self._stage_data.get(f"{workflow_id}_draft")
            review = self._stage_data.get(f"{workflow_id}_review")

            if not draft:
                raise ValueError("没有找到草稿")

            # 调用 Editor Agent
            editor_result = await self.agents["editor"].run_once({
                "draft": draft,
                "review": review or [],
            })

            final_report = editor_result.get("final_report", "")

            if on_progress:
                on_progress(
                    workflow_id, "editor", 100,
                    "最终报告完成",
                    {"word_count": len(final_report.split())},
                )

            return {"final_report": final_report}

        except Exception as e:
            if on_progress:
                on_progress(workflow_id, "editor", 0, f"编辑失败：{str(e)}")
            raise

    # ========== 辅助方法 ==========

    async def _analyze_paper(self, paper: Dict[str, Any]) -> Dict[str, Any]:
        """分析单篇论文"""
        # 调用 Analyst Agent
        result = await self.agents["analyst"].run_once({
            "papers": [paper],
        })
        analysis = result.get("analysis", [])
        return analysis[0] if analysis else self._create_placeholder_analysis(paper)

    def _create_placeholder_analysis(self, paper: Dict[str, Any]) -> Dict[str, Any]:
        """创建占位分析结果"""
        return {
            "title": paper.get("title", "Unknown"),
            "authors": paper.get("authors", []),
            "arxiv_id": paper.get("arxiv_id", ""),
            "summary": paper.get("summary", ""),
            "published": paper.get("published", ""),
            "published_year": paper.get("published_year", ""),
            "venue": paper.get("venue", ""),
            "citations": paper.get("citations", 0),
            "url": paper.get("url", ""),
            "categories": paper.get("categories", []),
            "doi": paper.get("doi", ""),
            "pdf_path": paper.get("pdf_path", ""),
            "source": paper.get("source", "unknown"),
            "research_question": "待分析",
            "methodology": "待分析",
            "key_contributions": ["待分析"],
            "innovations": ["待分析"],
            "limitations": ["待分析"],
        }

    # ========== 临时数据存储（简化实现） ==========
    # TODO: 改为从 workflow_store 读取

    def _get_recent_papers(self) -> List[Dict[str, Any]]:
        """获取最近的论文列表"""
        # 简化实现：从最近的搜索结果获取
        # 实际实现需要从 workflow_store 读取
        return []

    def _get_recent_analysis(self) -> List[Dict[str, Any]]:
        """获取最近的分析结果"""
        return []

    def _get_recent_draft(self) -> str:
        """获取最近的草稿"""
        return ""

    def _get_recent_review(self) -> List[Dict[str, Any]]:
        """获取最近的审核意见"""
        return []

    def set_stage_data(
        self,
        workflow_id: str,
        stage: str,
        data: Any,
    ) -> None:
        """设置阶段数据（用于跨阶段传递）"""
        # TODO: 实现到 workflow_store
        pass

    def get_stage_data(
        self,
        workflow_id: str,
        stage: str,
    ) -> Optional[Any]:
        """获取阶段数据"""
        # TODO: 实现从 workflow_store 读取
        return None
