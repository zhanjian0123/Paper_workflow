"""
工作流引擎 - 顺序执行多 Agent 协作

支持：
- 事件回调（进度推送）
- 取消令牌
- 状态持久化
"""

import asyncio
from typing import Any, Optional, Dict, List, Callable, Awaitable
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.llm_client import LLMClient
from memory.task_memory import TaskMemory, Task
from core.skill_loader import SkillLoader
import uuid
from datetime import datetime


# 阶段进度权重
STAGE_WEIGHTS = {
    "search": 25,
    "analyst": 25,
    "writer": 25,
    "reviewer": 15,
    "editor": 10,
}


class WorkflowContext:
    """工作流上下文（用于取消和进度追踪）"""

    def __init__(self, workflow_id: str):
        self.workflow_id = workflow_id
        self.cancel_requested = False
        self.current_stage: Optional[str] = None
        self.stage_progress: Dict[str, int] = {stage: 0 for stage in STAGE_WEIGHTS.keys()}
        self.papers_found: int = 0
        self.result: Optional[Dict[str, Any]] = None
        self.error: Optional[str] = None
        self.cancel_reason: Optional[str] = None

        # asyncio.Event 用于异步取消检查
        self._cancel_event = asyncio.Event()

    def request_cancel(self, reason: str = "用户请求取消") -> None:
        """请求取消工作流"""
        self.cancel_requested = True
        self.cancel_reason = reason
        self._cancel_event.set()  # 触发取消事件

    def is_cancelled(self) -> bool:
        """检查是否已请求取消"""
        return self._cancel_event.is_set()

    def get_overall_progress(self) -> int:
        """计算总体进度"""
        total = 0
        for stage, weight in STAGE_WEIGHTS.items():
            stage_prog = self.stage_progress.get(stage, 0)
            total += (stage_prog / 100) * weight
        return int(total)


class WorkflowEngine:
    """
    工作流引擎 - 按顺序执行 6 个 Agent
    1. Search → 2. Analyst → 3. Writer → 4. Reviewer → 5. Editor
    """

    def __init__(
        self,
        search_agent,
        analyst_agent,
        writer_agent,
        reviewer_agent,
        editor_agent,
        task_memory: Optional[TaskMemory] = None,
        skill_loader: Optional[SkillLoader] = None,
        download_dir: str = "output/papers",
        max_papers: int = 10,
        source: str = "arxiv",
        workflow_id: Optional[str] = None,
        on_progress: Optional[Callable[[str, str, int, str, Optional[Dict]], None]] = None,
    ):
        self.search = search_agent
        self.analyst = analyst_agent
        self.writer = writer_agent
        self.reviewer = reviewer_agent
        self.editor = editor_agent
        self.task_memory = task_memory
        self.skill_loader = skill_loader
        self.download_dir = download_dir
        self.max_papers = max_papers
        self.source = source  # arxiv, google_scholar, or both
        self.workflow_id = workflow_id or str(uuid.uuid4())
        self.on_progress = on_progress  # 进度回调：(workflow_id, stage, progress, message, data)
        self._main_task_id: Optional[str] = None
        self._results: Dict[str, Any] = {}
        self._context: Optional[WorkflowContext] = None

    async def run(self, user_request: str, year_range: Optional[str] = None) -> Dict[str, Any]:
        """执行完整工作流"""
        # 创建工作流上下文
        self._context = WorkflowContext(self.workflow_id)

        print(f"\n{'='*60}")
        print(f"开始工作流：{user_request}")
        if year_range:
            print(f"年份范围：{year_range}")
        print(f"论文下载目录：{self.download_dir}")
        print(f"最大论文数量：{self.max_papers}")
        print(f"数据源：{self.source}")
        print(f"工作流 ID: {self.workflow_id}")
        print(f"{'='*60}\n")

        # 创建主任务
        self._main_task_id = str(uuid.uuid4())
        if self.task_memory:
            task = Task(
                task_id=self._main_task_id,
                title=f"处理：{user_request[:50]}...",
                description=user_request,
                status="in_progress",
                priority=5,
            )
            self.task_memory.create_task(task)

        try:
            # Step 1: Search
            print(f"\n[Step 1/5] 🔍 文献搜索...")
            if self.on_progress:
                self.on_progress(self.workflow_id, "search", 0, "开始搜索论文...", None)

            search_result = await self._run_search(user_request, year_range)
            papers = search_result.get("papers", [])

            if self.on_progress:
                self.on_progress(self.workflow_id, "search", 100, f"找到 {len(papers)} 篇论文", {"papers_found": len(papers)})

            if not papers:
                # 搜索结果为空，生成空报告
                warning = search_result.get("warning", "未找到相关论文")
                print(f"[搜索] {warning}，生成空报告")

                return {
                    "status": "completed",
                    "task_id": self._main_task_id,
                    "papers": [],
                    "analysis": [],
                    "draft": f"# 文献分析报告\n\n## 概述\n\n**未找到相关论文**\n\n{warning}\n\n建议：\n1. 尝试其他关键词\n2. 扩大年份范围\n3. 检查 ArXiv API 可用性\n\n---\n*本报告由 Multi-Agent 文献工作流系统自动生成*",
                    "review": [],
                    "final_report": f"# 文献分析报告\n\n## 概述\n\n**未找到相关论文**\n\n{warning}\n\n建议：\n1. 尝试其他关键词\n2. 扩大年份范围\n3. 检查 ArXiv API 可用性\n\n---\n*本报告由 Multi-Agent 文献工作流系统自动生成*",
                }

            print(f"[搜索] 找到 {len(papers)} 篇论文")
            self._context.papers_found = len(papers)

            # 检查取消
            if self._context.is_cancelled():
                raise asyncio.CancelledError()

            # Step 2: Analyst
            print(f"\n[Step 2/5] 📊 文献分析...")
            if self.on_progress:
                self.on_progress(self.workflow_id, "analyst", 0, "开始分析论文...", None)

            analysis_result = await self._run_analyst(papers)

            if self.on_progress:
                self.on_progress(self.workflow_id, "analyst", 100, "分析完成", None)

            # 检查取消
            if self._context.is_cancelled():
                raise asyncio.CancelledError()

            # Step 3: Writer - 传递原始论文数据和分析结果
            print(f"\n[Step 3/5] ✍️  报告撰写...")
            if self.on_progress:
                self.on_progress(self.workflow_id, "writer", 0, "开始撰写报告...", None)

            analysis = analysis_result.get("analysis", [])
            draft_result = await self._run_writer(analysis, papers)  # 传递原始论文数据

            if self.on_progress:
                self.on_progress(self.workflow_id, "writer", 100, "报告草稿完成", None)

            # 检查取消
            if self._context.is_cancelled():
                raise asyncio.CancelledError()

            # Step 4: Reviewer
            print(f"\n[Step 4/5] 🔎 质量审核...")
            if self.on_progress:
                self.on_progress(self.workflow_id, "reviewer", 0, "开始审核报告...", None)

            draft = draft_result.get("draft", "")
            review_result = await self._run_reviewer(draft)

            if self.on_progress:
                self.on_progress(self.workflow_id, "reviewer", 100, "审核完成", None)

            # 检查取消
            if self._context.is_cancelled():
                raise asyncio.CancelledError()

            # Step 5: Editor
            print(f"\n[Step 5/5] 📝 最终编辑...")
            if self.on_progress:
                self.on_progress(self.workflow_id, "editor", 0, "开始编辑最终报告...", None)

            review = review_result.get("review", [])
            final_result = await self._run_editor(draft, review)

            if self.on_progress:
                self.on_progress(self.workflow_id, "editor", 100, "最终报告完成", None)

            # 完成
            if self.task_memory:
                self.task_memory.mark_completed(
                    self._main_task_id,
                    {"final_report": final_result.get("final_report", "")}
                )

            print(f"\n{'='*60}")
            print("✅ 工作流完成!")
            print(f"{'='*60}\n")

            return {
                "status": "completed",
                "task_id": self._main_task_id,
                "papers": papers,
                "analysis": analysis,
                "draft": draft,
                "review": review,
                "final_report": final_result.get("final_report", ""),
            }

        except asyncio.CancelledError:
            # 工作流被取消
            reason = self._context.cancel_reason if self._context else "未知原因"
            print(f"\n❌ 工作流已取消：{reason}")
            if self.task_memory:
                self.task_memory.mark_failed(self._main_task_id, f"工作流被取消：{reason}")
            if self.on_progress:
                self.on_progress(self.workflow_id, "cancelled", 0, f"工作流已取消：{reason}", None)
            raise

        except Exception as e:
            # 工作流失败
            print(f"\n❌ 工作流错误：{e}")
            if self.task_memory:
                self.task_memory.mark_failed(self._main_task_id, str(e))
            if self.on_progress:
                self.on_progress(self.workflow_id, "failed", self._context.get_overall_progress() if self._context else 0, f"工作流失败：{str(e)}", None)
            raise

    async def _run_search(self, query: str, year_range: Optional[str] = None, on_progress: Optional[Callable] = None) -> Dict[str, Any]:
        """运行搜索 Agent"""
        task_id = str(uuid.uuid4())

        # 如果传入了进度回调，创建一个临时的 Search Agent 包装器
        if on_progress:
            # 进度 10% - 正在搜索
            on_progress("search", 10, "正在搜索论文...")
            await asyncio.sleep(0.1)

        result = await self.search.run_once({
            "task_id": task_id,
            "query": query,
            "description": query,
            "year_range": year_range,
            "download_dir": self.download_dir,
            "max_papers": self.max_papers,
            "source": self.source,
            "workflow_id": self.workflow_id,
            "on_progress": on_progress,
        })

        if on_progress:
            # 进度 50% - 搜索完成，开始下载
            if result.get("papers"):
                on_progress("search", 50, f"搜索完成，找到 {len(result['papers'])} 篇论文，开始下载...")
            await asyncio.sleep(0.1)

        if self.task_memory and result.get("papers"):
            self.task_memory.mark_completed(task_id, result)

        return result

    async def _run_analyst(self, papers: List[Dict]) -> Dict[str, Any]:
        """运行分析 Agent"""
        task_id = str(uuid.uuid4())
        result = await self.analyst.run_once({
            "task_id": task_id,
            "papers": papers,
        })

        if self.task_memory and result.get("analysis"):
            self.task_memory.mark_completed(task_id, result)

        return result

    async def _run_writer(self, analysis: List[Dict], original_papers: List[Dict]) -> Dict[str, Any]:
        """运行写作 Agent"""
        task_id = str(uuid.uuid4())
        result = await self.writer.run_once({
            "task_id": task_id,
            "analysis": analysis,
            "original_papers": original_papers,  # 传递原始论文数据
        })

        if self.task_memory and result.get("draft"):
            self.task_memory.mark_completed(task_id, result)

        return result

    async def _run_reviewer(self, draft: str) -> Dict[str, Any]:
        """运行审核 Agent"""
        task_id = str(uuid.uuid4())
        result = await self.reviewer.run_once({
            "task_id": task_id,
            "draft": draft,
        })

        if self.task_memory and result.get("review"):
            self.task_memory.mark_completed(task_id, result)

        return result

    async def _run_editor(self, draft: str, review: List[Dict]) -> Dict[str, Any]:
        """运行编辑 Agent"""
        task_id = str(uuid.uuid4())
        result = await self.editor.run_once({
            "task_id": task_id,
            "draft": draft,
            "review": review,
        })

        if self.task_memory and result.get("final_report"):
            self.task_memory.mark_completed(task_id, result)

        return result
