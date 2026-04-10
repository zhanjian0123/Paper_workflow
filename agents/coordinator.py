"""
Coordinator Agent - 协调和管理整个工作流
"""

import asyncio
from typing import Any, Optional, List, Dict
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

from agents.base import BaseAgent
from core.message_bus import MessageBus
from memory.task_memory import TaskMemory, Task
from memory.agent_memory import AgentMemory
from core.skill_loader import SkillLoader
from mcp.tools_registry import ToolsRegistry

import uuid
from datetime import datetime


class CoordinatorAgent(BaseAgent):
    """
    Coordinator Agent - 工作流协调器
    负责任务分解、分配和进度追踪
    """

    def __init__(
        self,
        message_bus: MessageBus,
        task_memory: Optional[TaskMemory] = None,
        agent_memory: Optional[AgentMemory] = None,
        skill_loader: Optional[SkillLoader] = None,
        tools_registry: Optional[ToolsRegistry] = None,
        model_name: str = "qwen3.5-plus",
        base_url: Optional[str] = None,
        api_key: Optional[str] = None,
    ):
        skills = ["task_management"]
        tools = []

        super().__init__(
            name="coordinator",
            description="Workflow coordinator for task decomposition and assignment",
            skills=skills,
            tools=tools,
            message_bus=message_bus,
            task_memory=task_memory,
            agent_memory=agent_memory,
            skill_loader=skill_loader,
            model_name=model_name,
            base_url=base_url,
            api_key=api_key,
        )

        self.tools_registry = tools_registry
        self._pending_tasks: Dict[str, Dict[str, Any]] = {}
        self._task_results: Dict[str, Any] = {}

        # 注册其他 Agent
        self.managed_agents = [
            "search",
            "analyst",
            "writer",
            "reviewer",
            "editor",
        ]

    async def process_message(self, message: Any) -> Optional[Any]:
        """处理接收到的消息"""
        content = message.content
        msg_type = message.message_type

        if msg_type == "task":
            # 接收新任务
            return await self._handle_new_task(content, message.message_id)
        elif msg_type == "result":
            # 接收子任务结果
            return await self._handle_task_result(content, message.in_reply_to)
        elif msg_type == "error":
            # 处理错误
            return await self._handle_error(content)

        return None

    async def _handle_new_task(self, content: Any, message_id: str) -> Optional[Any]:
        """处理新任务请求"""
        # 内容格式：{"user_request": "...", "context": {...}}
        user_request = content.get("user_request", "") if isinstance(content, dict) else str(content)

        # 创建主任务
        main_task_id = self._create_task(
            title=f"Process: {user_request[:50]}...",
            description=user_request,
            priority=5,
        )

        # 使用 LLM 分解任务
        sub_tasks = await self._decompose_task(user_request)

        # 分配子任务给各个 Agent
        await self._assign_sub_tasks(sub_tasks, main_task_id, message_id)

        return {"status": "processing", "task_id": main_task_id, "sub_tasks": sub_tasks}

    async def _handle_task_result(self, result: Any, in_reply_to: Optional[str]) -> Optional[Any]:
        """处理子任务结果"""
        # 记录结果
        if in_reply_to:
            self._task_results[in_reply_to] = result

        # 检查是否所有子任务完成
        # 简化实现：直接返回结果
        return {"status": "result_received", "result": result}

    async def _handle_error(self, error_content: Any) -> Optional[Any]:
        """处理错误"""
        agent = error_content.get("agent", "unknown") if isinstance(error_content, dict) else "unknown"
        error = error_content.get("error", "Unknown error") if isinstance(error_content, dict) else str(error_content)
        print(f"[Coordinator] Error from {agent}: {error}")
        return None

    async def _decompose_task(self, user_request: str) -> List[Dict[str, Any]]:
        """
        使用 LLM 将任务分解为子任务
        基于 task_management skill prompt 进行智能分解
        """
        # 获取技能 prompt
        skill_prompt = self._get_skill_prompt("task_management")

        # 构建输入
        user_message = f"""请作为战略任务编排专家，分解以下任务为可执行的子任务：

用户请求：{user_request}

可用的 Agent：
- search: 文献搜索专家，负责在 ArXiv、Google Scholar 等数据库中搜索论文
- analyst: 文献分析专家，负责从论文中提取关键信息和方法论
- writer: 学术报告撰写专家，负责生成结构清晰的学术报告
- reviewer: 质量审核专家，负责审核报告质量并提出改进建议
- editor: 最终编辑，负责整合反馈生成终稿

---

请根据系统提示中的任务编排指导原则进行分解：

**任务分解原则：**
1. 原子化与独立性 - 确保每个子任务边界清晰，能够独立交付
2. 契约化输入输出 - 明确每个任务的输入前置条件和输出交付物格式
3. 依赖拓扑构建 - 识别任务间的先后顺序，区分串行任务与并行任务
4. Agent 精准适配 - 根据任务属性将其指派给具备相应 Skill 的最适 Agent

**重要原则：**
- 颗粒度适中 - 避免分解过粗或过细
- 闭环反馈 - 每个子任务的完成必须伴随质量确认
- 上下文连续性 - 确保执行 Agent 拥有必要的上下文背景

请返回 JSON 格式的子任务列表，每个子任务包含：
- title: 任务标题（简短）
- description: 任务详细描述
- assigned_to: 负责的 Agent（search/analyst/writer/reviewer/editor）
- priority: 优先级（1-5，5 最高）
- dependencies: 依赖的子任务 ID 列表（如果没有依赖则为空）

请直接返回 JSON 数组，不要添加其他解释：
"""

        # 调用 LLM 进行任务分解
        try:
            llm_response = await self._call_llm(user_message, system_prompt=skill_prompt, temperature=0.3)

            # 解析 LLM 返回的 JSON
            import json
            import re

            # 尝试提取 JSON（处理可能的 markdown 包裹）
            json_match = re.search(r'\[[\s\S]*\]', llm_response)
            if json_match:
                sub_tasks_raw = json.loads(json_match.group())

                # 转换为标准格式
                sub_tasks = []
                for i, task in enumerate(sub_tasks_raw):
                    sub_tasks.append({
                        "id": str(uuid.uuid4()),
                        "title": task.get("title", f"Task {i+1}"),
                        "description": task.get("description", ""),
                        "assigned_to": task.get("assigned_to", "analyst"),
                        "priority": task.get("priority", 3),
                        "dependencies": task.get("dependencies", []),
                    })

                if sub_tasks:
                    print(f"[Coordinator] LLM 分解任务得到 {len(sub_tasks)} 个子任务")
                    return sub_tasks
        except Exception as e:
            print(f"[Coordinator] LLM 任务分解失败：{e}，使用默认分解策略")

        # 默认分解流程（降级处理）
        sub_tasks = []
        if "search" in user_request.lower() or "论文" in user_request or "搜索" in user_request or "文献" in user_request:
            sub_tasks = [
                {
                    "id": str(uuid.uuid4()),
                    "title": "文献搜索",
                    "description": f"搜索相关论文：{user_request}",
                    "assigned_to": "search",
                    "priority": 5,
                    "dependencies": [],
                },
                {
                    "id": str(uuid.uuid4()),
                    "title": "文献分析",
                    "description": "分析搜索到的论文，提取关键信息",
                    "assigned_to": "analyst",
                    "priority": 4,
                    "dependencies": [],
                },
                {
                    "id": str(uuid.uuid4()),
                    "title": "报告撰写",
                    "description": "基于分析结果撰写报告",
                    "assigned_to": "writer",
                    "priority": 3,
                    "dependencies": [],
                },
                {
                    "id": str(uuid.uuid4()),
                    "title": "质量审核",
                    "description": "审核报告质量",
                    "assigned_to": "reviewer",
                    "priority": 2,
                    "dependencies": [],
                },
                {
                    "id": str(uuid.uuid4()),
                    "title": "最终编辑",
                    "description": "整合所有反馈，生成最终版本",
                    "assigned_to": "editor",
                    "priority": 1,
                    "dependencies": [],
                },
            ]
        else:
            sub_tasks = [
                {
                    "id": str(uuid.uuid4()),
                    "title": "分析任务",
                    "description": f"分析用户需求：{user_request}",
                    "assigned_to": "analyst",
                    "priority": 5,
                    "dependencies": [],
                },
                {
                    "id": str(uuid.uuid4()),
                    "title": "生成响应",
                    "description": "基于分析生成响应",
                    "assigned_to": "writer",
                    "priority": 4,
                    "dependencies": [],
                },
            ]

        print(f"[Coordinator] 使用默认策略分解任务得到 {len(sub_tasks)} 个子任务")
        return sub_tasks

    async def _assign_sub_tasks(
        self, sub_tasks: List[Dict[str, Any]], main_task_id: str, original_message_id: str
    ) -> None:
        """分配子任务给各个 Agent"""
        for i, task in enumerate(sub_tasks):
            assigned_to = task.get("assigned_to")
            if not assigned_to or assigned_to not in self.managed_agents:
                continue

            # 创建任务记录
            if self.task_memory:
                from memory.task_memory import Task
                task_record = Task(
                    task_id=task["id"],
                    title=task["title"],
                    description=task["description"],
                    status="pending",
                    priority=task.get("priority", 0),
                    assigned_to=assigned_to,
                    parent_task_id=main_task_id,
                    dependencies=task.get("dependencies", []),
                )
                self.task_memory.create_task(task_record)

            # 发送任务消息
            await self.send_message(
                target=assigned_to,
                content={
                    "task_id": task["id"],
                    "title": task["title"],
                    "description": task["description"],
                    "parent_task_id": main_task_id,
                    "original_request_id": original_message_id,
                },
                message_type="task",
                priority=task.get("priority", 0),
            )

            print(f"[Coordinator] Assigned task '{task['title']}' to {assigned_to}")

    async def execute_task(self, task_content: Any) -> Any:
        """执行 Coordinator 任务（直接调用）"""
        return await self._handle_new_task(task_content, str(uuid.uuid4()))

    def get_workflow_status(self) -> Dict[str, Any]:
        """获取工作流状态"""
        return {
            "managed_agents": self.managed_agents,
            "pending_tasks": len(self._pending_tasks),
            "completed_tasks": len(self._task_results),
        }
