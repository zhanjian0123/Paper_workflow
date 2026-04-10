"""
工作流运行器 - 事件驱动的工作流执行引擎

功能：
- 启动/取消工作流
- 事件驱动的阶段执行
- 实时进度推送
- 状态持久化
- 取消令牌支持
"""
import asyncio
from typing import Dict, Any, Optional, Callable, Awaitable
from datetime import datetime
import uuid
import sys
import json
from pathlib import Path

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from backend.app.core.events import (
    EventBus,
    Event,
    EVENT_STAGE_STARTED,
    EVENT_STAGE_PROGRESS,
    EVENT_STAGE_COMPLETED,
    EVENT_STAGE_FAILED,
    EVENT_WORKFLOW_COMPLETED,
    EVENT_WORKFLOW_FAILED,
    EVENT_WORKFLOW_CANCELLED,
    get_event_bus,
)
from backend.app.services.workflow_store import (
    WorkflowStore,
    WorkflowRecord,
    WorkflowEventRecord,
    PaperRecord,
    ReportRecord,
)


# 阶段进度权重
STAGE_WEIGHTS = {
    "search": 25,
    "analyst": 25,
    "writer": 25,
    "reviewer": 15,
    "editor": 10,
}

# 阶段顺序
STAGE_ORDER = ["search", "analyst", "writer", "reviewer", "editor"]


class WorkflowContext:
    """
    工作流上下文

    支持：
    - asyncio.Event 取消信号
    - 超时控制
    - 取消原因记录
    - 优雅关闭标志
    """

    def __init__(self, workflow_id: str, timeout_seconds: Optional[int] = None):
        self.workflow_id = workflow_id
        self.cancel_requested = False
        self.current_stage: Optional[str] = None
        self.stage_progress: Dict[str, int] = {stage: 0 for stage in STAGE_ORDER}
        self.papers_found: int = 0
        self.result: Optional[Dict[str, Any]] = None
        self.error: Optional[str] = None
        self.cancel_reason: Optional[str] = None
        self.is_graceful_shutdown = False

        # asyncio.Event 用于异步取消检查
        self._cancel_event = asyncio.Event()

        # 超时控制
        self.timeout_seconds = timeout_seconds
        self.start_time: Optional[datetime] = None
        self._timeout_task: Optional[asyncio.Task] = None

    async def request_cancel(self, reason: str = "用户请求取消", graceful: bool = False) -> None:
        """
        请求取消工作流

        Args:
            reason: 取消原因
            graceful: 是否优雅关闭（等待当前操作完成）
        """
        self.cancel_requested = True
        self.cancel_reason = reason
        self.is_graceful_shutdown = graceful
        self._cancel_event.set()  # 触发取消事件

    def is_cancelled(self) -> bool:
        """检查是否已请求取消"""
        return self._cancel_event.is_set()

    async def wait_for_cancel(self, timeout: Optional[float] = None) -> bool:
        """
        等待取消请求

        Args:
            timeout: 等待超时时间（秒）

        Returns:
            True 如果收到取消请求，False 如果超时
        """
        try:
            await asyncio.wait_for(self._cancel_event.wait(), timeout=timeout)
            return True
        except asyncio.TimeoutError:
            return False

    def check_timeout(self) -> bool:
        """
        检查是否超时

        Returns:
            True 如果已超时
        """
        if not self.timeout_seconds or not self.start_time:
            return False

        elapsed = (datetime.now() - self.start_time).total_seconds()
        return elapsed > self.timeout_seconds

    async def start_timeout_monitor(self) -> None:
        """启动超时监控任务"""
        if not self.timeout_seconds:
            return

        self.start_time = datetime.now()

        async def timeout_checker():
            while True:
                await asyncio.sleep(1)
                if self.check_timeout():
                    await self.request_cancel(reason=f"工作流超时（{self.timeout_seconds}秒）")
                    break
                if self.is_cancelled():
                    break

        self._timeout_task = asyncio.create_task(timeout_checker())

    async def stop_timeout_monitor(self) -> None:
        """停止超时监控任务"""
        if self._timeout_task:
            self._timeout_task.cancel()
            try:
                await self._timeout_task
            except asyncio.CancelledError:
                pass

    def get_overall_progress(self) -> int:
        """计算总体进度"""
        total = 0
        for stage, weight in STAGE_WEIGHTS.items():
            stage_prog = self.stage_progress.get(stage, 0)
            total += (stage_prog / 100) * weight
        return int(total)

    async def cleanup(self) -> None:
        """清理上下文资源"""
        await self.stop_timeout_monitor()
        self._cancel_event.clear()


class WorkflowRunner:
    """
    工作流运行器

    功能：
    - 启动/取消工作流
    - 事件驱动的阶段执行
    - 实时进度推送
    - 状态持久化
    - 取消令牌支持
    - 超时控制
    - 优雅关闭

    使用示例:
        runner = WorkflowRunner(workflow_store, event_bus)

        # 创建工作流
        workflow_id = await runner.create_workflow(
            query="transformer",
            year_range="2024-2026",
            max_papers=10,
            source="arxiv"
        )

        # 启动工作流（可配置超时）
        await runner.start_workflow(workflow_id, multi_agent_adapter, timeout_seconds=1800)

        # 取消工作流（优雅关闭）
        await runner.cancel_workflow(workflow_id, graceful=True, reason="用户请求")
    """

    def __init__(
        self,
        workflow_store: WorkflowStore,
        event_bus: Optional[EventBus] = None,
        download_dir: str = "output/papers",
        default_timeout_seconds: Optional[int] = 3600,  # 默认 1 小时超时
    ):
        self.workflow_store = workflow_store
        self.event_bus = event_bus or get_event_bus()
        self.download_dir = download_dir
        self.default_timeout_seconds = default_timeout_seconds

        # 运行中的工作流上下文
        self._running_contexts: Dict[str, WorkflowContext] = {}

        # 后台任务映射
        self._background_tasks: Dict[str, asyncio.Task] = {}

        # 取消锁，防止重复取消
        self._cancel_locks: Dict[str, asyncio.Lock] = {}

    async def create_workflow(
        self,
        query: str,
        year_range: Optional[str] = None,
        max_papers: int = 10,
        source: str = "arxiv",
    ) -> str:
        """创建工作流记录"""
        workflow_id = f"wf_{uuid.uuid4().hex[:12]}"
        now = datetime.now().isoformat()

        workflow = WorkflowRecord(
            id=workflow_id,
            query=query,
            year_range=year_range,
            max_papers=max_papers,
            source=source,
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

        self.workflow_store.create_workflow(workflow)

        # 记录创建事件
        self._add_event(
            workflow_id,
            "workflow_created",
            progress=0,
            message="工作流已创建",
        )

        return workflow_id

    async def start_workflow(
        self,
        workflow_id: str,
        adapter: Any,  # MultiAgentAdapter 实例
        timeout_seconds: Optional[int] = None,
    ) -> None:
        """
        启动工作流（后台运行）

        Args:
            workflow_id: 工作流 ID
            adapter: MultiAgentAdapter 实例
            timeout_seconds: 超时时间（秒），None 使用默认值
        """
        # 创建工作流上下文
        timeout = timeout_seconds if timeout_seconds is not None else self.default_timeout_seconds
        context = WorkflowContext(workflow_id, timeout_seconds=timeout)
        self._running_contexts[workflow_id] = context

        # 创建取消锁
        self._cancel_locks[workflow_id] = asyncio.Lock()

        # 启动超时监控
        await context.start_timeout_monitor()

        # 创建后台任务
        task = asyncio.create_task(
            self._run_workflow(workflow_id, adapter, context)
        )
        self._background_tasks[workflow_id] = task

        # 更新状态为 running
        self.workflow_store.update_workflow_status(
            workflow_id,
            status="running",
            message=f"工作流已启动（超时：{timeout}秒）",
        )

    async def cancel_workflow(
        self,
        workflow_id: str,
        reason: str = "用户请求取消",
        graceful: bool = False,
        graceful_timeout: float = 30.0,
    ) -> bool:
        """
        取消工作流

        Args:
            workflow_id: 工作流 ID
            reason: 取消原因
            graceful: 是否优雅关闭（等待当前操作完成）
            graceful_timeout: 优雅关闭等待超时（秒）

        Returns:
            True 如果成功取消，False 如果工作流不存在或已完成
        """
        # 检查工作流是否存在
        workflow = self.workflow_store.get_workflow(workflow_id)
        if not workflow:
            return False

        # 检查工作流状态
        if workflow.status in ("completed", "failed", "cancelled"):
            return False

        # 使用锁防止重复取消
        if workflow_id not in self._cancel_locks:
            self._cancel_locks[workflow_id] = asyncio.Lock()

        async with self._cancel_locks[workflow_id]:
            # 再次检查状态（防止竞态条件）
            workflow = self.workflow_store.get_workflow(workflow_id)
            if workflow.status in ("completed", "failed", "cancelled"):
                return False

            # 请求取消
            if workflow_id in self._running_contexts:
                context = self._running_contexts[workflow_id]
                await context.request_cancel(reason=reason, graceful=graceful)

                if graceful:
                    # 优雅关闭：等待当前操作完成
                    print(f"[WorkflowRunner] 工作流 {workflow_id} 正在优雅关闭，等待 {graceful_timeout} 秒...")

                    try:
                        # 等待取消事件或超时
                        cancelled = await asyncio.wait_for(
                            context.wait_for_cancel(timeout=graceful_timeout),
                            timeout=graceful_timeout + 5  # 额外缓冲时间
                        )
                        if cancelled:
                            print(f"[WorkflowRunner] 工作流 {workflow_id} 已响应取消请求")
                    except asyncio.TimeoutError:
                        print(f"[WorkflowRunner] 工作流 {workflow_id} 优雅关闭超时，强制取消")

            # 取消后台任务
            if workflow_id in self._background_tasks:
                task = self._background_tasks[workflow_id]
                if not task.done():
                    task.cancel()
                    try:
                        await task
                    except asyncio.CancelledError:
                        pass
                    except Exception as e:
                        # 忽略其他异常，任务已取消
                        print(f"[WorkflowRunner] 任务取消时异常：{e}")

            # 更新状态
            self.workflow_store.update_workflow_status(
                workflow_id,
                status="cancelled",
                message=f"工作流已取消：{reason}",
            )

            # 发送取消事件
            await self._publish_event(
                workflow_id,
                EVENT_WORKFLOW_CANCELLED,
                progress=0,
                message=f"工作流已取消：{reason}",
            )

            # 清理上下文
            await self._cleanup_workflow(workflow_id)

            return True

    async def _cleanup_workflow(self, workflow_id: str) -> None:
        """
        清理工作流资源

        Args:
            workflow_id: 工作流 ID
        """
        # 清理上下文
        if workflow_id in self._running_contexts:
            context = self._running_contexts[workflow_id]
            await context.cleanup()
            del self._running_contexts[workflow_id]

        # 清理后台任务
        if workflow_id in self._background_tasks:
            del self._background_tasks[workflow_id]

        # 清理取消锁
        if workflow_id in self._cancel_locks:
            del self._cancel_locks[workflow_id]

        # 清理适配器中的阶段缓存
        print(f"[WorkflowRunner] 已清理工作流 {workflow_id} 资源")

    async def start_workflow_with_local_papers(
        self,
        workflow_id: str,
        adapter: Any,
        paper_ids: list[str],
        timeout_seconds: Optional[int] = None,
    ) -> None:
        """
        从本地论文启动工作流（跳过搜索阶段）

        Args:
            workflow_id: 工作流 ID
            adapter: MultiAgentAdapter 实例
            paper_ids: 本地论文 ID 列表
            timeout_seconds: 超时时间（秒）
        """
        # 创建工作流上下文
        timeout = timeout_seconds if timeout_seconds is not None else self.default_timeout_seconds
        context = WorkflowContext(workflow_id, timeout_seconds=timeout)
        self._running_contexts[workflow_id] = context

        # 创建取消锁
        self._cancel_locks[workflow_id] = asyncio.Lock()

        # 启动超时监控
        await context.start_timeout_monitor()

        # 创建后台任务
        task = asyncio.create_task(
            self._run_workflow_with_local_papers(workflow_id, adapter, context, paper_ids)
        )
        self._background_tasks[workflow_id] = task

        # 更新状态为 running
        self.workflow_store.update_workflow_status(
            workflow_id,
            status="running",
            current_stage="analyst",
            progress=25,
            papers_found=len(paper_ids),
            message=f"工作流已启动（本地论文：{len(paper_ids)} 篇，从文献分析阶段开始，超时：{timeout}秒）",
        )

    async def _run_workflow_with_local_papers(
        self,
        workflow_id: str,
        adapter: Any,
        context: WorkflowContext,
        paper_ids: list[str],
    ) -> None:
        """
        执行使用本地论文的工作流（跳过搜索阶段）
        """
        try:
            # 先静默加载本地论文，并将搜索阶段视为已跳过
            search_result = await adapter.load_local_papers(
                paper_ids=paper_ids,
                workflow_id=workflow_id,
                on_progress=None,
            )
            context.papers_found = search_result.get("count", 0)
            context.stage_progress["search"] = 100

            await self._publish_event(
                workflow_id,
                EVENT_STAGE_COMPLETED,
                stage="search",
                status="completed",
                progress=100,
                message=f"已使用本地论文，跳过文献搜索阶段（共 {context.papers_found} 篇）",
                data={"papers_found": context.papers_found, "skipped": True},
            )

            self.workflow_store.update_workflow_status(
                workflow_id,
                status="running",
                current_stage="analyst",
                progress=context.get_overall_progress(),
                papers_found=context.papers_found,
                message=f"已加载 {context.papers_found} 篇本地论文，开始文献分析...",
            )

            # Analyst 及后续阶段的进度回调
            def on_progress(_workflow_id, stage, progress, message, data=None):
                context.stage_progress[stage] = progress
                if data:
                    context.papers_found = data.get("papers_found", context.papers_found)
                self.workflow_store.update_workflow_status(
                    workflow_id,
                    status="running",
                    current_stage=stage,
                    progress=context.get_overall_progress(),
                    message=message,
                )
                asyncio.create_task(
                    self._publish_event(
                        workflow_id,
                        EVENT_STAGE_PROGRESS,
                        stage=stage,
                        progress=progress,
                        message=message,
                        data=data,
                    )
                )

            # 检查取消
            if context.is_cancelled():
                await self._handle_cancelled_workflow(workflow_id, context, "analyst")
                return

            # 步骤 1: Analyst
            context.current_stage = "analyst"
            await self._publish_event(
                workflow_id,
                EVENT_STAGE_STARTED,
                stage="analyst",
                progress=0,
                message="开始分析论文...",
            )

            analysis_result = await adapter.run_analyst(
                workflow_id=workflow_id,
                on_progress=on_progress,
            )

            if context.is_cancelled():
                await self._handle_cancelled_workflow(workflow_id, context, "analyst")
                return

            # 步骤 3: Writer
            context.current_stage = "writer"
            await self._publish_event(
                workflow_id,
                EVENT_STAGE_STARTED,
                stage="writer",
                progress=0,
                message="开始撰写报告...",
            )

            writer_result = await adapter.run_writer(
                workflow_id=workflow_id,
                on_progress=on_progress,
            )

            if context.is_cancelled():
                await self._handle_cancelled_workflow(workflow_id, context, "writer")
                return

            # 步骤 4: Reviewer
            context.current_stage = "reviewer"
            await self._publish_event(
                workflow_id,
                EVENT_STAGE_STARTED,
                stage="reviewer",
                progress=0,
                message="开始审核报告...",
            )

            review_result = await adapter.run_reviewer(
                workflow_id=workflow_id,
                on_progress=on_progress,
            )

            if context.is_cancelled():
                await self._handle_cancelled_workflow(workflow_id, context, "reviewer")
                return

            # 步骤 5: Editor
            context.current_stage = "editor"
            await self._publish_event(
                workflow_id,
                EVENT_STAGE_STARTED,
                stage="editor",
                progress=0,
                message="开始编辑最终报告...",
            )

            editor_result = await adapter.run_editor(
                workflow_id=workflow_id,
                on_progress=on_progress,
            )

            if context.is_cancelled():
                await self._handle_cancelled_workflow(workflow_id, context, "editor")
                return

            # 工作流完成
            context.result = {
                "search": search_result,
                "analyst": analysis_result,
                "writer": writer_result,
                "reviewer": review_result,
                "editor": editor_result,
            }
            context.stage_progress["editor"] = 100

            # 保存最终报告
            final_report = editor_result.get("final_report", "")
            if final_report:
                await self._save_final_report(workflow_id, final_report)

            # 更新状态
            self.workflow_store.update_workflow_status(
                workflow_id,
                status="completed",
                current_stage=None,
                progress=100,
                message="工作流完成",
                result=context.result,
            )

            # 发布完成事件
            await self._publish_event(
                workflow_id,
                EVENT_WORKFLOW_COMPLETED,
                progress=100,
                message="工作流完成",
                data=context.result,
            )

            print(f"[WorkflowRunner] 工作流 {workflow_id} 完成")

        except Exception as e:
            context.error = str(e)
            self.workflow_store.update_workflow_status(
                workflow_id,
                status="failed",
                error=str(e),
                message=f"工作流失败：{str(e)}",
            )

            await self._publish_event(
                workflow_id,
                EVENT_WORKFLOW_FAILED,
                progress=context.get_overall_progress(),
                message=f"工作流失败：{str(e)}",
                data={"error": str(e)},
            )

            print(f"[WorkflowRunner] 工作流 {workflow_id} 失败：{e}")

        finally:
            # 清理
            await self._cleanup_workflow(workflow_id)

    async def _run_workflow(
        self,
        workflow_id: str,
        adapter: Any,
        context: WorkflowContext,
    ) -> None:
        """
        执行工作流（内部方法）

        支持：
        - 阶段间取消检查
        - 超时自动终止
        - 异常清理
        """
        try:
            # 启动超时监控
            await context.start_timeout_monitor()

            # 重写查询：使用 LLM 将自然语言转换为简洁关键词
            original_query = self.workflow_store.get_workflow(workflow_id).query
            from backend.app.services.query_rewriter import get_query_rewriter
            rewriter = get_query_rewriter()
            rewritten_query = await rewriter.rewrite(original_query)

            # 保存重写后的查询到数据库
            self.workflow_store.update_rewritten_query(workflow_id, rewritten_query)

            # 如果重写后的查询不同，记录日志
            if rewritten_query != original_query:
                print(f"[QueryRewrite] {original_query} → {rewritten_query}")

            # 阶段 1: Search
            await self._run_stage(
                workflow_id, "search", context,
                lambda: adapter.run_search(
                    query=rewritten_query,
                    year_range=self.workflow_store.get_workflow(workflow_id).year_range,
                    max_papers=self.workflow_store.get_workflow(workflow_id).max_papers,
                    source=self.workflow_store.get_workflow(workflow_id).source,
                    download_dir=self.download_dir,
                    workflow_id=workflow_id,
                    on_progress=self._on_stage_progress,
                )
            )

            # 检查取消
            if context.is_cancelled():
                raise asyncio.CancelledError()

            # 阶段 2: Analyst
            await self._run_stage(
                workflow_id, "analyst", context,
                lambda: adapter.run_analyst(
                    workflow_id=workflow_id,
                    on_progress=self._on_stage_progress,
                )
            )

            # 检查取消
            if context.is_cancelled():
                raise asyncio.CancelledError()

            # 阶段 3: Writer
            await self._run_stage(
                workflow_id, "writer", context,
                lambda: adapter.run_writer(
                    workflow_id=workflow_id,
                    on_progress=self._on_stage_progress,
                )
            )

            # 检查取消
            if context.is_cancelled():
                raise asyncio.CancelledError()

            # 阶段 4: Reviewer
            await self._run_stage(
                workflow_id, "reviewer", context,
                lambda: adapter.run_reviewer(
                    workflow_id=workflow_id,
                    on_progress=self._on_stage_progress,
                )
            )

            # 检查取消
            if context.is_cancelled():
                raise asyncio.CancelledError()

            # 阶段 5: Editor
            await self._run_stage(
                workflow_id, "editor", context,
                lambda: adapter.run_editor(
                    workflow_id=workflow_id,
                    on_progress=self._on_stage_progress,
                )
            )

            # 工作流完成
            await self._on_workflow_completed(workflow_id, context)

        except asyncio.CancelledError:
            # 工作流被取消
            print(f"[WorkflowRunner] 工作流 {workflow_id} 被取消：{context.cancel_reason}")
            await self._handle_cancelled_workflow(workflow_id, context)
            raise

        except Exception as e:
            # 工作流失败
            print(f"[WorkflowRunner] 工作流 {workflow_id} 失败：{e}")
            await self._on_workflow_failed(workflow_id, context, str(e))

        finally:
            # 总是清理资源
            await self._cleanup_workflow(workflow_id)

    async def _run_stage(
        self,
        workflow_id: str,
        stage_name: str,
        context: WorkflowContext,
        stage_func: Callable[[], Awaitable[Dict[str, Any]]],
    ) -> None:
        """运行单个阶段"""
        # 检查取消
        if context.cancel_requested:
            raise asyncio.CancelledError()

        context.current_stage = stage_name

        # 发送阶段开始事件
        await self._publish_event(
            workflow_id,
            EVENT_STAGE_STARTED,
            stage=stage_name,
            status="in_progress",
            progress=0,
            message=f"开始 {stage_name} 阶段",
        )

        # 更新数据库状态
        self.workflow_store.update_workflow_status(
            workflow_id,
            status="running",
            current_stage=stage_name,
            message=f"正在执行 {stage_name} 阶段...",
        )

        try:
            # 执行阶段函数
            result = await stage_func()

            # 更新阶段进度为 100%
            context.stage_progress[stage_name] = 100

            # 保存阶段结果到上下文
            context.result = result

            # 如果是 editor 阶段，保存报告到存储
            if stage_name == "editor" and result:
                final_report = result.get("final_report", "")
                if final_report:
                    self.add_report_to_store(workflow_id, final_report)

            # 发送阶段完成事件
            await self._publish_event(
                workflow_id,
                EVENT_STAGE_COMPLETED,
                stage=stage_name,
                status="completed",
                progress=100,
                message=f"{stage_name} 阶段完成",
                data=result,
            )

            # 保存阶段结果
            return result

        except Exception as e:
            # 发送阶段失败事件
            await self._publish_event(
                workflow_id,
                EVENT_STAGE_FAILED,
                stage=stage_name,
                status="failed",
                progress=context.stage_progress[stage_name],
                message=f"{stage_name} 阶段失败：{str(e)}",
            )
            raise

    def _on_stage_progress(
        self,
        workflow_id: str,
        stage_name: str,
        progress: int,
        message: str,
        data: Optional[Dict[str, Any]] = None,
    ) -> None:
        """阶段进度回调（同步）"""
        if workflow_id in self._running_contexts:
            context = self._running_contexts[workflow_id]
            context.stage_progress[stage_name] = progress

            # 更新数据库
            self.workflow_store.update_workflow_status(
                workflow_id,
                status="running",
                progress=context.get_overall_progress(),
                message=message,
            )

            # 异步发布事件（不阻塞）
            asyncio.create_task(
                self._publish_event(
                    workflow_id,
                    EVENT_STAGE_PROGRESS,
                    stage=stage_name,
                    status="in_progress",
                    progress=progress,
                    message=message,
                    data=data,
                )
            )

    async def _handle_cancelled_workflow(
        self,
        workflow_id: str,
        context: WorkflowContext,
    ) -> None:
        """
        处理被取消的工作流

        Args:
            workflow_id: 工作流 ID
            context: 工作流上下文
        """
        # 更新数据库状态
        self.workflow_store.update_workflow_status(
            workflow_id,
            status="cancelled",
            current_stage=context.current_stage,
            progress=context.get_overall_progress(),
            message=f"工作流被取消：{context.cancel_reason or '用户请求'}",
        )

        # 发送取消事件
        await self._publish_event(
            workflow_id,
            EVENT_WORKFLOW_CANCELLED,
            progress=context.get_overall_progress(),
            message=f"工作流被取消：{context.cancel_reason or '用户请求'}",
        )

    async def _on_workflow_completed(
        self,
        workflow_id: str,
        context: WorkflowContext,
    ) -> None:
        """工作流完成回调"""
        # 停止超时监控
        await context.stop_timeout_monitor()

        # 更新数据库状态
        self.workflow_store.update_workflow_status(
            workflow_id,
            status="completed",
            current_stage=None,
            progress=100,
            message="工作流完成",
        )

        # 发送完成事件
        await self._publish_event(
            workflow_id,
            EVENT_WORKFLOW_COMPLETED,
            progress=100,
            message="工作流完成",
            data=context.result,
        )

        # 清理上下文（在 finally 中统一处理）

    async def _on_workflow_failed(
        self,
        workflow_id: str,
        context: WorkflowContext,
        error: str,
    ) -> None:
        """工作流失败回调"""
        # 停止超时监控
        await context.stop_timeout_monitor()

        context.error = error

        # 更新数据库状态
        self.workflow_store.update_workflow_status(
            workflow_id,
            status="failed",
            current_stage=context.current_stage,
            progress=context.get_overall_progress(),
            message=f"工作流失败：{error}",
            error=error,
        )

        # 发送失败事件
        await self._publish_event(
            workflow_id,
            EVENT_WORKFLOW_FAILED,
            stage=context.current_stage,
            status="failed",
            progress=context.get_overall_progress(),
            message=f"工作流失败：{error}",
        )

        # 清理上下文（在 finally 中统一处理）

    async def _publish_event(
        self,
        workflow_id: str,
        event_type: str,
        progress: int,
        message: str,
        stage: Optional[str] = None,
        status: Optional[str] = None,
        data: Optional[Dict[str, Any]] = None,
    ) -> None:
        """发布事件"""
        event = Event(
            event_type=event_type,
            workflow_id=workflow_id,
            data={
                "stage": stage,
                "status": status,
                "progress": progress,
                "message": message,
                **(data or {}),
            },
        )
        await self.event_bus.publish(event)

        # 同时记录到数据库
        self._add_event(
            workflow_id,
            event_type,
            stage=stage,
            status=status,
            progress=progress,
            message=message,
            data=data,
        )

    def _add_event(
        self,
        workflow_id: str,
        event_type: str,
        message: str,
        stage: Optional[str] = None,
        status: Optional[str] = None,
        progress: int = 0,
        data: Optional[Dict[str, Any]] = None,
    ) -> None:
        """添加事件到数据库"""
        event = WorkflowEventRecord(
            id=f"evt_{uuid.uuid4().hex[:12]}",
            workflow_id=workflow_id,
            event_type=event_type,
            stage=stage,
            status=status,
            progress=progress,
            message=message,
            data=data,
            timestamp=datetime.now().isoformat(),
        )
        self.workflow_store.add_event(event)

    def get_context(self, workflow_id: str) -> Optional[WorkflowContext]:
        """获取工作流上下文"""
        return self._running_contexts.get(workflow_id)

    def is_running(self, workflow_id: str) -> bool:
        """检查工作流是否运行中"""
        return workflow_id in self._running_contexts

    def get_running_workflows(self) -> list:
        """获取所有运行中的工作流 ID"""
        return list(self._running_contexts.keys())

    async def shutdown(self) -> None:
        """关闭运行器（取消所有运行中的工作流）"""
        for workflow_id in list(self._running_contexts.keys()):
            await self.cancel_workflow(workflow_id)

    # ========== 论文和报告管理 ==========

    def add_paper_to_store(
        self,
        workflow_id: str,
        paper_data: Dict[str, Any],
    ) -> None:
        """添加论文到存储"""
        paper = PaperRecord(
            paper_id=paper_data.get("arxiv_id", f"paper_{uuid.uuid4().hex[:8]}"),
            workflow_id=workflow_id,
            title=paper_data.get("title", "Unknown"),
            authors=json.dumps(paper_data.get("authors", []), ensure_ascii=False),
            abstract=paper_data.get("summary", paper_data.get("abstract", "")),
            year=paper_data.get("published_year") or (
                paper_data.get("published", "")[:4] if paper_data.get("published") else None
            ),
            source=paper_data.get("source", "unknown"),
            pdf_path=paper_data.get("pdf_path"),
            download_status="downloaded" if paper_data.get("pdf_path") else "pending",
            created_at=datetime.now().isoformat(),
        )
        self.workflow_store.add_paper(paper)

    def add_report_to_store(
        self,
        workflow_id: str,
        report_content: str,
        file_path: Optional[str] = None,
    ) -> str:
        """添加报告到存储"""
        report_id = f"rpt_{uuid.uuid4().hex[:12]}"
        word_count = len(report_content.split())

        report = ReportRecord(
            report_id=report_id,
            workflow_id=workflow_id,
            content_markdown=report_content,
            file_path=file_path,
            word_count=word_count,
            created_at=datetime.now().isoformat(),
        )
        self.workflow_store.add_report(report)

        # 更新工作流结果
        workflow = self.workflow_store.get_workflow(workflow_id)
        if workflow:
            workflow.result = {"report_id": report_id, "file_path": file_path}
            self.workflow_store.update_workflow(workflow)

        return report_id
