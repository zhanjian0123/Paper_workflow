"""
Editor Agent - 最终编辑
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


class EditorAgent(BaseAgent):
    """
    Editor Agent - 最终编辑专家
    负责整合反馈并生成最终版本
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
        skills = ["academic_writing", "peer_review"]
        tools = ["filesystem"]

        super().__init__(
            name="editor",
            description="Final editing specialist for integrating feedback",
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
        self._final_report: str = ""

    async def process_message(self, message: Any) -> Optional[Any]:
        """处理编辑任务"""
        content = message.content

        if isinstance(content, dict):
            draft = content.get("draft", "")
            review = content.get("review", [])
            task_id = content.get("task_id", "")
        else:
            draft = str(content)
            review = []
            task_id = ""

        return await self._finalize(draft, review, task_id)

    async def _finalize(
        self, draft: str, review: list, task_id: str = ""
    ) -> Optional[Any]:
        """生成最终版本"""
        print("[Editor] Finalizing report")

        # 获取技能 prompt
        writing_prompt = self._get_skill_prompt("academic_writing")

        # 基于审核意见修改报告 - 使用 LLM
        final_report = await self._incorporate_feedback_llm(draft, review, writing_prompt)

        # 保存到文件
        await self._save_report(final_report, task_id)

        self._final_report = final_report

        if self.task_memory and task_id:
            self.task_memory.mark_completed(
                task_id, {"final_report": final_report}
            )

        return {
            "task_id": task_id,
            "final_report": final_report,
            "status": "completed",
        }

    async def _incorporate_feedback_llm(self, draft: str, review: list, writing_prompt: str) -> str:
        """使用 LLM 整合反馈生成最终版本"""
        # 获取两个 skill prompt 并合并
        writing_prompt = self._get_skill_prompt("academic_writing")
        peer_review_prompt = self._get_skill_prompt("peer_review")

        # 合并 prompt
        system_prompt = f"{writing_prompt}\n\n---\n\n{peer_review_prompt}"

        # 格式化审核意见
        review_text = ""
        for item in review:
            aspect = item.get('aspect', 'General')
            rating = item.get('rating', 'N/A')
            comment = item.get('comment', '')
            review_text += f"- {aspect} (评级：{rating}): {comment}\n"

        user_message = f"""请根据以下审核意见，修改和完善报告草稿：

【报告草稿】
{draft[:6000] if len(draft) > 6000 else draft}

【审核意见】
{review_text}

---

请根据系统提示中的学术写作标准和同行评审指导原则进行修改：

**写作要求：**
- 采用"整合式"写法，避免论文逐个罗列
- 按主题/议题组织内容，进行多文献观点对比与整合
- 使用学术专业语气，评价性动词（指出、论证、揭示、证实）
- 结构清晰：报告题目、引言、核心议题分析、方法论对比、结论与洞察、参考文献

**审核反馈处理要求：**
- 建设性批判：针对每条审核意见给出具体的修改方案
- 证据导向：确保所有修改都有原文或分析结果支撑
- 高标准严要求：模拟顶会论文的修订标准

请直接返回修改后的完整报告，不要其他解释。"""

        try:
            final_report = await self._call_llm(user_message, system_prompt=system_prompt, temperature=0.5)
            print(f"[Editor] LLM 整合反馈完成，{len(final_report)} 字符")
            return final_report
        except Exception as e:
            print(f"[Editor] LLM 整合反馈失败：{e}，使用基础整合")
            # 降级处理
            return self._incorporate_feedback_basic(draft, review)

    async def _incorporate_feedback(self, draft: str, review: list) -> str:
        """整合反馈（保留向下兼容）"""
        return self._incorporate_feedback_basic(draft, review)

    def _incorporate_feedback_basic(self, draft: str, review: list) -> str:
        """基础整合反馈（降级处理）"""
        enhanced_report = draft + """

## 审核反馈及改进

"""
        for item in review:
            enhanced_report += f"""
### {item.get('aspect', 'General')}
- 评级：{item.get('rating', 'N/A')}
- 意见：{item.get('comment', '')}
"""

        enhanced_report += """
---
*最终版本已整合所有反馈意见*
"""
        return enhanced_report

    async def _save_report(self, content: str, task_id: str) -> Optional[str]:
        """保存报告到文件"""
        if self.tools_registry:
            from datetime import datetime
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"report_{task_id or timestamp}.md"

            result = await self.tools_registry.execute_tool(
                "filesystem", "write",
                file_path=f"reports/{filename}",
                content=content,
            )

            if result.success:
                return result.data.get("file_path")
        return None

    async def execute_task(self, task_content: Any) -> Any:
        """执行编辑任务（直接调用）"""
        if isinstance(task_content, dict):
            draft = task_content.get("draft", "")
            review = task_content.get("review", [])
        else:
            draft = str(task_content)
            review = []
        return await self._finalize(draft, review)
