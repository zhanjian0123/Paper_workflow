"""
Agent 基类 - 所有 Agent 的抽象基类
"""

import asyncio
from abc import ABC, abstractmethod
from typing import Any, Optional, List, Dict, Union
from pathlib import Path

import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.message_bus import MessageBus, Message
from memory.task_memory import TaskMemory, Task
from memory.agent_memory import AgentMemory, AgentState, MessageHistory
from core.skill_loader import SkillLoader
from core.llm_client import LLMClient
from core.logger import get_logger

import uuid
from datetime import datetime

# 获取日志记录器
logger = get_logger(__name__)


class BaseAgent(ABC):
    """
    Agent 抽象基类
    所有具体 Agent 必须继承此类并实现抽象方法
    """

    def __init__(
        self,
        name: str,
        description: str,
        skills: List[str],
        tools: List[str],
        message_bus: MessageBus,
        task_memory: Optional[TaskMemory] = None,
        agent_memory: Optional[AgentMemory] = None,
        skill_loader: Optional[SkillLoader] = None,
        model_name: str = "qwen3.5-plus",
        base_url: Optional[str] = None,
        api_key: Optional[str] = None,
    ):
        self.name = name
        self.description = description
        self.skills: List[str] = skills  # 技能名称列表
        self.tools: List[str] = tools  # 工具名称列表
        self.message_bus = message_bus
        self.task_memory = task_memory
        self.agent_memory = agent_memory or AgentMemory()
        self.skill_loader = skill_loader or SkillLoader()
        self.model_name = model_name
        self.base_url = base_url
        self.api_key = api_key

        # 初始化 LLM 客户端
        self.llm_client = LLMClient(
            api_key=api_key,
            base_url=base_url,
            model_name=model_name,
        )

        self._running = False
        self._current_task: Optional[Task] = None

        # 注册到消息总线
        self.message_bus.register_agent(name)

        # 初始化 Agent 状态
        self._init_state()

    def _init_state(self) -> None:
        """初始化 Agent 状态"""
        state = self.agent_memory.get_state(self.name)
        if not state:
            state = AgentState(agent_name=self.name)
            self.agent_memory.save_state(state)

    def _update_status(self, status: str, task_id: Optional[str] = None) -> None:
        """更新 Agent 状态"""
        self.agent_memory.set_agent_status(self.name, status, task_id)

    def _get_skill_prompt(self, skill_name: str) -> Optional[str]:
        """获取技能的 system prompt"""
        return self.skill_loader.get_skill_prompt(skill_name)

    def _get_all_skill_prompts(self) -> Dict[str, str]:
        """获取所有技能的 prompts"""
        prompts: Dict[str, str] = {}
        for skill_name in self.skills:
            prompt = self._get_skill_prompt(skill_name)
            if prompt:
                prompts[skill_name] = prompt
        return prompts

    async def _call_llm(
        self,
        user_message: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
    ) -> str:
        """
        调用 LLM 进行推理
        user_message: 用户输入消息
        system_prompt: 可选的系统提示（如 skill prompt）
        temperature: 温度参数
        """
        # 显示 LLM 调用信息
        if system_prompt:
            is_skill_md = '# Role' in system_prompt or '## ' in system_prompt
            source = "SKILL.md" if is_skill_md else "YAML/其他"
            logger.info(f"[{self.name}] LLM 调用 | 提示来源={source} | 提示长度={len(system_prompt)} | 输入长度={len(user_message)}")
        else:
            logger.info(f"[{self.name}] LLM 调用 | 输入长度={len(user_message)}")

        messages = [{"role": "user", "content": user_message}]
        return await self.llm_client.chat(
            messages=messages,
            system=system_prompt,
            temperature=temperature,
        )

    async def _call_llm_with_messages(
        self,
        messages: List[Dict[str, str]],
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
    ) -> str:
        """
        调用 LLM 进行推理（支持多轮对话）
        messages: 消息列表，每项为 {"role": "user|assistant", "content": "..."}
        system_prompt: 可选的系统提示
        temperature: 温度参数
        """
        return await self.llm_client.chat(
            messages=messages,
            system=system_prompt,
            temperature=temperature,
        )

    async def send_message(
        self,
        target: str,
        content: Any,
        message_type: str = "task",
        priority: int = 0,
        in_reply_to: Optional[str] = None,
    ) -> None:
        """发送消息"""
        message = Message(
            source=self.name,
            target=target,
            content=content,
            message_type=message_type,
            priority=priority,
            in_reply_to=in_reply_to,
        )
        await self.message_bus.send(message)

    async def receive_message(self, timeout: Optional[float] = None) -> Message:
        """接收消息"""
        return await self.message_bus.receive(self.name, timeout=timeout)

    def _save_message(
        self,
        role: str,
        content: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """保存消息到历史记录"""
        history = MessageHistory(
            id=str(uuid.uuid4()),
            agent_name=self.name,
            role=role,
            content=content,
            metadata=metadata or {},
        )
        self.agent_memory.add_message(history)

    def _create_task(
        self,
        title: str,
        description: str,
        priority: int = 0,
        parent_task_id: Optional[str] = None,
        dependencies: Optional[List[str]] = None,
    ) -> str:
        """创建子任务"""
        task = Task(
            task_id=str(uuid.uuid4()),
            title=title,
            description=description,
            priority=priority,
            parent_task_id=parent_task_id,
            dependencies=dependencies or [],
        )
        if self.task_memory:
            self.task_memory.create_task(task)
        return task.task_id

    @abstractmethod
    async def process_message(self, message: Message) -> Optional[Message]:
        """
        处理接收到的消息
        子类必须实现此方法
        """
        pass

    @abstractmethod
    async def execute_task(self, task_content: Any) -> Any:
        """
        执行具体任务
        子类必须实现此方法
        """
        pass

    async def run(self) -> None:
        """
        运行 Agent 主循环
        持续监听消息队列并处理消息
        """
        self._running = True
        self._update_status("idle")

        while self._running:
            try:
                # 接收消息（1 秒超时，避免无限阻塞）
                try:
                    message = await self.receive_message(timeout=1.0)
                    self._update_status("busy", self._current_task.task_id if self._current_task else None)

                    # 保存接收的消息
                    self._save_message("user", str(message.content))

                    # 处理消息
                    response = await self.process_message(message)

                    if response:
                        await self.send_message(
                            target=message.source,
                            content=response.content,
                            message_type="result",
                            in_reply_to=message.message_id,
                        )

                    self._update_status("idle")

                except asyncio.TimeoutError:
                    # 没有新消息，继续循环
                    await asyncio.sleep(0.1)

            except Exception as e:
                # 记录错误
                self._update_status("error")
                error_msg = f"Agent {self.name} error: {str(e)}"
                logger.exception(error_msg)

                # 发送错误消息
                await self.send_message(
                    target="coordinator",
                    content={"error": str(e), "agent": self.name},
                    message_type="error",
                )

    def stop(self) -> None:
        """停止 Agent"""
        self._running = False
        self._update_status("idle")

    async def run_once(self, task_content: Any) -> Any:
        """
        运行单次任务（不启动主循环）
        用于测试或直接调用
        """
        self._update_status("busy")
        try:
            result = await self.execute_task(task_content)
            self._update_status("idle")
            return result
        except Exception as e:
            self._update_status("error")
            raise
