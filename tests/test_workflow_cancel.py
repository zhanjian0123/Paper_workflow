"""
测试工作流取消功能

测试场景：
1. WorkflowContext 取消信号
2. WorkflowContext 超时监控
3. WorkflowRunner 取消工作流
4. WorkflowRunner 优雅关闭
"""
import pytest
import asyncio
from datetime import datetime, timedelta
from pathlib import Path
import sys

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from backend.app.services.workflow_runner import WorkflowContext, WorkflowRunner, STAGE_ORDER
from backend.app.services.workflow_store import WorkflowStore


class TestWorkflowContext:
    """测试 WorkflowContext 类"""

    @pytest.mark.asyncio
    async def test_cancel_event(self):
        """测试取消事件触发"""
        ctx = WorkflowContext("wf_test_001")

        # 初始状态
        assert not ctx.is_cancelled()
        assert not ctx.cancel_requested
        assert ctx.cancel_reason is None

        # 请求取消
        await ctx.request_cancel(reason="测试取消")

        # 验证取消状态
        assert ctx.is_cancelled()
        assert ctx.cancel_requested
        assert ctx.cancel_reason == "测试取消"
        assert ctx._cancel_event.is_set()

    @pytest.mark.asyncio
    async def test_wait_for_cancel(self):
        """测试等待取消请求"""
        ctx = WorkflowContext("wf_test_002")

        # 启动取消等待任务
        async def cancel_after_delay():
            await asyncio.sleep(0.1)
            await ctx.request_cancel(reason="延迟取消")

        asyncio.create_task(cancel_after_delay())

        # 等待取消
        result = await ctx.wait_for_cancel(timeout=1.0)
        assert result is True
        assert ctx.cancel_reason == "延迟取消"

    @pytest.mark.asyncio
    async def test_wait_for_cancel_timeout(self):
        """测试等待取消超时"""
        ctx = WorkflowContext("wf_test_003")

        # 不触发取消，等待应该超时
        result = await ctx.wait_for_cancel(timeout=0.1)
        assert result is False
        assert not ctx.is_cancelled()

    @pytest.mark.asyncio
    async def test_timeout_monitor(self):
        """测试超时监控"""
        ctx = WorkflowContext("wf_test_004", timeout_seconds=1)

        # 启动超时监控
        await ctx.start_timeout_monitor()

        # 等待超时
        await asyncio.sleep(1.5)

        # 验证已触发取消
        assert ctx.is_cancelled()
        assert "超时" in ctx.cancel_reason

        # 清理
        await ctx.stop_timeout_monitor()

    @pytest.mark.asyncio
    async def test_no_timeout_without_monitor(self):
        """测试没有超时监控时不会触发超时"""
        ctx = WorkflowContext("wf_test_005", timeout_seconds=1)

        # 不启动超时监控
        await asyncio.sleep(1.5)

        # 不应该触发取消
        assert not ctx.is_cancelled()

    @pytest.mark.asyncio
    async def test_cleanup(self):
        """测试清理资源"""
        ctx = WorkflowContext("wf_test_006", timeout_seconds=1)
        await ctx.start_timeout_monitor()

        # 清理
        await ctx.cleanup()

        # 超时监控应该已停止
        assert ctx._timeout_task is None or ctx._timeout_task.cancelled()

    def test_progress_calculation(self):
        """测试进度计算"""
        ctx = WorkflowContext("wf_test_007")

        # 初始进度为 0
        assert ctx.get_overall_progress() == 0

        # 设置阶段进度
        ctx.stage_progress["search"] = 100
        ctx.stage_progress["analyst"] = 50

        # 计算：25% * 100% + 25% * 50% = 25 + 12.5 = 37.5 -> 37
        progress = ctx.get_overall_progress()
        assert progress == 37

        # 所有阶段完成
        for stage in STAGE_ORDER:
            ctx.stage_progress[stage] = 100

        assert ctx.get_overall_progress() == 100

    def test_graceful_shutdown_flag(self):
        """测试优雅关闭标志"""
        ctx = WorkflowContext("wf_test_008")

        # 初始状态
        assert not ctx.is_graceful_shutdown

        # 普通取消
        asyncio.run(ctx.request_cancel(reason="普通取消", graceful=False))
        assert not ctx.is_graceful_shutdown

        # 优雅关闭
        ctx2 = WorkflowContext("wf_test_009")
        asyncio.run(ctx2.request_cancel(reason="优雅关闭", graceful=True))
        assert ctx2.is_graceful_shutdown


class TestWorkflowRunner:
    """测试 WorkflowRunner 类"""

    @pytest.fixture
    def workflow_store(self, tmp_path):
        """创建临时数据库"""
        db_path = tmp_path / "test_workflow_store.db"
        return WorkflowStore(db_path=db_path)

    @pytest.fixture
    def workflow_runner(self, workflow_store):
        """创建 WorkflowRunner 实例"""
        return WorkflowRunner(workflow_store=workflow_store, default_timeout_seconds=60)

    @pytest.mark.asyncio
    async def test_create_workflow(self, workflow_runner):
        """测试创建工作流"""
        workflow_id = await workflow_runner.create_workflow(
            query="测试查询",
            year_range="2024-2026",
            max_papers=5,
            source="arxiv",
        )

        assert workflow_id.startswith("wf_")

        # 验证数据库记录
        workflow = workflow_runner.workflow_store.get_workflow(workflow_id)
        assert workflow is not None
        assert workflow.query == "测试查询"
        assert workflow.status == "pending"

    @pytest.mark.asyncio
    async def test_cancel_nonexistent_workflow(self, workflow_runner):
        """测试取消不存在的工作流"""
        result = await workflow_runner.cancel_workflow("wf_nonexistent")
        assert result is False

    @pytest.mark.asyncio
    async def test_cancel_completed_workflow(self, workflow_runner):
        """测试取消已完成的工作流"""
        # 创建并手动设置为 completed
        workflow_id = await workflow_runner.create_workflow(query="测试")
        workflow_runner.workflow_store.update_workflow_status(
            workflow_id, status="completed"
        )

        result = await workflow_runner.cancel_workflow(workflow_id)
        assert result is False

    @pytest.mark.asyncio
    async def test_cancel_running_workflow(self, workflow_runner):
        """测试取消运行中的工作流"""
        # 创建工作流
        workflow_id = await workflow_runner.create_workflow(query="测试")

        # 模拟运行中状态
        ctx = WorkflowContext(workflow_id)
        workflow_runner._running_contexts[workflow_id] = ctx
        workflow_runner._background_tasks[workflow_id] = asyncio.create_task(asyncio.sleep(10))

        # 取消
        result = await workflow_runner.cancel_workflow(workflow_id, reason="测试取消")
        assert result is True

        # 验证状态
        workflow = workflow_runner.workflow_store.get_workflow(workflow_id)
        assert workflow.status == "cancelled"
        assert "测试取消" in workflow.message

        # 清理背景任务
        await asyncio.sleep(0.1)

    @pytest.mark.asyncio
    async def test_graceful_shutdown(self, workflow_runner):
        """测试优雅关闭"""
        workflow_id = await workflow_runner.create_workflow(query="测试")

        # 模拟运行中状态
        ctx = WorkflowContext(workflow_id)
        workflow_runner._running_contexts[workflow_id] = ctx

        # 创建一个会响应取消的任务
        async def cancellable_task():
            try:
                await asyncio.sleep(10)
            except asyncio.CancelledError:
                raise

        task = asyncio.create_task(cancellable_task())
        workflow_runner._background_tasks[workflow_id] = task

        # 优雅关闭
        result = await workflow_runner.cancel_workflow(
            workflow_id,
            reason="优雅关闭测试",
            graceful=True,
            graceful_timeout=0.5,
        )

        assert result is True

        # 验证取消原因已记录
        assert ctx.cancel_reason == "优雅关闭测试"
        assert ctx.is_graceful_shutdown

    @pytest.mark.asyncio
    async def test_is_running(self, workflow_runner):
        """测试检查运行状态"""
        workflow_id = await workflow_runner.create_workflow(query="测试")

        assert not workflow_runner.is_running(workflow_id)

        # 添加上下文
        ctx = WorkflowContext(workflow_id)
        workflow_runner._running_contexts[workflow_id] = ctx

        assert workflow_runner.is_running(workflow_id)

    @pytest.mark.asyncio
    async def test_get_running_workflows(self, workflow_runner):
        """测试获取运行中的工作流列表"""
        # 初始为空
        assert workflow_runner.get_running_workflows() == []

        # 添加上下文
        for i in range(3):
            ctx = WorkflowContext(f"wf_test_{i}")
            workflow_runner._running_contexts[f"wf_test_{i}"] = ctx

        running = workflow_runner.get_running_workflows()
        assert len(running) == 3
        assert "wf_test_0" in running
        assert "wf_test_1" in running
        assert "wf_test_2" in running

    @pytest.mark.asyncio
    async def test_shutdown(self, workflow_runner):
        """测试关闭运行器（取消所有工作流）"""
        # 添加多个运行中工作流（先创建工作流记录）
        for i in range(3):
            workflow_id = await workflow_runner.create_workflow(query=f"测试{i}")
            ctx = WorkflowContext(workflow_id)
            workflow_runner._running_contexts[workflow_id] = ctx
            workflow_runner._cancel_locks[workflow_id] = asyncio.Lock()

        # 关闭
        await workflow_runner.shutdown()

        # 验证所有工作流已清理
        assert len(workflow_runner._running_contexts) == 0


class TestWorkflowContextRaceConditions:
    """测试竞态条件"""

    @pytest.mark.asyncio
    async def test_concurrent_cancel_requests(self):
        """测试并发取消请求"""
        ctx = WorkflowContext("wf_race_001")

        # 并发发送多个取消请求
        await asyncio.gather(
            ctx.request_cancel(reason="取消 1"),
            ctx.request_cancel(reason="取消 2"),
            ctx.request_cancel(reason="取消 3"),
        )

        # 只应该有一个取消原因被记录（最后一个）
        assert ctx.is_cancelled()
        assert ctx.cancel_reason in ["取消 1", "取消 2", "取消 3"]

    @pytest.mark.asyncio
    async def test_cancel_during_completion(self):
        """测试在完成过程中取消"""
        ctx = WorkflowContext("wf_race_002")

        # 模拟完成回调
        async def complete_workflow():
            await asyncio.sleep(0.1)
            # 完成时检查取消
            if ctx.is_cancelled():
                return "cancelled"
            return "completed"

        # 在完成后立即取消
        task = asyncio.create_task(complete_workflow())
        await asyncio.sleep(0.05)
        await ctx.request_cancel(reason="完成中取消")

        result = await task
        assert result == "cancelled"
