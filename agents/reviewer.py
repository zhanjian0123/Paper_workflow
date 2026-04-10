"""
Reviewer Agent - 质量审核
"""

import asyncio
from typing import Any, Optional, Dict
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

from agents.base import BaseAgent
from core.message_bus import MessageBus
from memory.task_memory import TaskMemory
from memory.agent_memory import AgentMemory
from core.skill_loader import SkillLoader
from mcp.tools_registry import ToolsRegistry


class ReviewerAgent(BaseAgent):
    """
    Reviewer Agent - 质量审核专家
    负责审核报告质量和准确性
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
        skills = ["peer_review", "critical_analysis"]
        tools = []

        super().__init__(
            name="reviewer",
            description="Quality review specialist for academic reports",
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

        self._review_comments: list = []

    async def process_message(self, message: Any) -> Optional[Any]:
        """处理审核任务"""
        content = message.content

        if isinstance(content, dict):
            draft = content.get("draft", "")
            task_id = content.get("task_id", "")
        else:
            draft = str(content)
            task_id = ""

        return await self._review(draft, task_id)

    async def _review(self, draft: str, task_id: str = "") -> Optional[Any]:
        """审核报告"""
        print("[Reviewer] Reviewing draft")

        # 获取审核技能 prompt
        review_prompt = self._get_skill_prompt("peer_review")

        # 生成审核意见 - 使用 LLM
        comments = await self._generate_review_llm(draft, review_prompt)

        self._review_comments = comments

        if self.task_memory and task_id:
            self.task_memory.mark_completed(task_id, {"review": comments})

        return {
            "task_id": task_id,
            "review": comments,
        }

    async def _generate_review_llm(self, draft: str, review_prompt: str) -> list:
        """使用 LLM 生成审核意见"""
        # 获取两个 skill prompt 并合并
        peer_review_prompt = self._get_skill_prompt("peer_review")
        critical_prompt = self._get_skill_prompt("critical_analysis")

        # 合并 prompt
        system_prompt = f"{peer_review_prompt}\n\n---\n\n{critical_prompt}"

        user_message = f"""请作为资深同行评审专家，审核以下文献分析报告：

报告内容：
{draft[:8000] if len(draft) > 8000 else draft}

---

请根据系统提示中的评审指导原则和批判性分析方法，从以下维度进行深入评估：

**核心评审维度：**
1. 技术正确性与严谨性 - 方法论是否存在逻辑错误，核心假设是否合理
2. 实验设计与实证充分性 - 对比实验是否公平，消融研究是否完备
3. 论证逻辑与结论一致性 - 结论是否被过度推导，证据是否支撑论点
4. 表述清晰度与呈现质量 - 摘要与引言是否清晰，图表是否与正文一致
5. 可重复性与伦理 - 是否提供足够细节供复现，是否存在数据偏差

**评审原则：**
- 建设性批判：指出问题的同时给出解决方案
- 证据导向：所有批评必须引用原文具体章节
- 高标准严要求：模拟顶会审稿人的决策逻辑

**批判性分析要求：**
- 识别作者试图掩盖的局限性
- 评估实验证据对核心主张的支撑强度
- 捕捉真正推动领域进步的原创性贡献
- 区分"从 0 到 1"的突破和渐进式改进

请对每个维度给出：
- aspect: 评估维度名称
- rating: 评级（优秀/良好/需改进/不足）
- comment: 具体评估意见和改进建议

请以 JSON 数组格式返回，不要其他解释。"""

        try:
            import json
            import re

            llm_response = await self._call_llm(user_message, system_prompt=system_prompt, temperature=0.3)

            # 解析 JSON
            json_match = re.search(r'\[[\s\S]*\]', llm_response)
            if json_match:
                comments = json.loads(json_match.group())
                print(f"[Reviewer] LLM 生成 {len(comments)} 条审核意见")
                return comments
        except Exception as e:
            print(f"[Reviewer] LLM 审核失败：{e}，使用默认审核意见")

        # 降级处理：返回默认审核意见
        return self._generate_default_review()

    def _generate_default_review(self) -> list:
        """生成默认审核意见"""
        return [
            {
                "aspect": "结构清晰度",
                "rating": "良好",
                "comment": "报告结构基本清晰，建议增加更多小节划分",
            },
            {
                "aspect": "内容准确性",
                "rating": "待验证",
                "comment": "建议核对原文献确保引用准确",
            },
            {
                "aspect": "表述专业性",
                "rating": "良好",
                "comment": "用语较为专业，部分地方可进一步精炼",
            },
            {
                "aspect": "完整性",
                "rating": "需改进",
                "comment": "建议补充更多实验细节和对比分析",
            },
        ]

    async def _generate_review(self, draft: str) -> list:
        """生成审核意见（保留向下兼容）"""
        return self._generate_default_review()

    async def execute_task(self, task_content: Any) -> Any:
        """执行审核任务（直接调用）"""
        draft = str(task_content) if not isinstance(task_content, dict) else task_content.get("draft", "")
        return await self._review(draft)
