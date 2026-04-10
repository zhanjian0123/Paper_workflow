"""
Writer Agent - 报告撰写
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


class WriterAgent(BaseAgent):
    """
    Writer Agent - 学术报告撰写专家
    负责生成结构清晰的学术报告
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
        skills = ["academic_writing", "comparison_analysis"]
        tools = ["filesystem"]

        super().__init__(
            name="writer",
            description="Academic report writing specialist",
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
        self._draft_content: str = ""

    async def process_message(self, message: Any) -> Optional[Any]:
        """处理写作任务"""
        content = message.content

        if isinstance(content, dict):
            analysis = content.get("analysis", [])
            original_papers = content.get("original_papers", [])
            task_id = content.get("task_id", "")
        else:
            analysis = []
            original_papers = []
            task_id = ""

        return await self._write_report(analysis, task_id, original_papers)

    async def _write_report(
        self, analysis: list, task_id: str = "", original_papers: list = None
    ) -> Optional[Any]:
        """撰写报告"""
        print(f"[Writer] Writing report based on {len(analysis)} analyses")

        # 获取写作技能 prompt
        writing_prompt = self._get_skill_prompt("academic_writing")

        # 生成报告 - 使用 LLM
        report = await self._generate_report_llm(analysis, original_papers, writing_prompt)

        # 保存草稿
        self._draft_content = report

        if self.task_memory and task_id:
            self.task_memory.mark_completed(task_id, {"draft": report})

        return {
            "task_id": task_id,
            "draft": report,
        }

    async def _generate_report_llm(self, analysis: list, original_papers: list = None, writing_prompt: str = None) -> str:
        """使用 LLM 生成报告内容"""
        papers_to_use = analysis if analysis else (original_papers or [])

        # 获取两个 skill prompt 并合并
        writing_prompt = self._get_skill_prompt("academic_writing")
        comparison_prompt = self._get_skill_prompt("comparison_analysis")

        # 合并 prompt
        system_prompt = f"{writing_prompt}\n\n---\n\n{comparison_prompt}"

        # 构建输入数据
        papers_summary = []
        for i, paper in enumerate(papers_to_use[:10], 1):  # 限制前 10 篇
            title = paper.get('title', 'Unknown')
            authors = ', '.join(paper.get('authors', []))
            summary = paper.get('summary', 'N/A')
            research_question = paper.get('research_question', '')
            methodology = paper.get('methodology', '')
            key_contributions = paper.get('key_contributions', [])

            paper_summary = f"""
论文 {i}:
- 标题：{title}
- 作者：{authors}
- 摘要：{summary[:1000] if summary else 'N/A'}
- 研究问题：{research_question if research_question and research_question != '待分析' else 'N/A'}
- 方法论：{methodology if methodology and methodology != '待分析' else 'N/A'}
- 核心贡献：{', '.join(key_contributions) if key_contributions and key_contributions != ['待分析'] else 'N/A'}
"""
            papers_summary.append(paper_summary)

        papers_text = '\n'.join(papers_summary)

        user_message = f"""基于以下论文分析，撰写一篇结构清晰的文献分析报告：

{papers_text}

---

请根据系统提示中的写作指导原则和对比分析方法，生成一份高质量的文献分析报告。

**重要要求：**
1. 采用"整合式"写法，不要按论文逐个罗列（禁止"论文 A 说...论文 B 说..."的简单堆砌）
2. 按"主题/议题"组织内容，进行多文献观点的对比与整合
3. 使用学术专业语气，评价性动词（如：指出、论证、揭示、证实）
4. 报告结构应包含：报告题目、引言、核心议题分析（按主题分节）、方法论对比、结论与洞察、参考文献

**对比分析要求：**
- 构建对比表格，直观展示各论文的核心参数与结果
- 分析各方案在设计哲学上的差异、性能指标背后的取舍（Trade-offs）
- 总结技术演进趋势，指出各方案的适用场景

请直接返回完整的报告内容，使用 Markdown 格式。"""

        try:
            report = await self._call_llm(user_message, system_prompt=system_prompt, temperature=0.5)
            print(f"[Writer] LLM 生成报告完成，{len(report)} 字符")
            return report
        except Exception as e:
            print(f"[Writer] LLM 生成报告失败：{e}，使用模板生成")
            # 降级到模板生成
            return await self._generate_report_template(analysis, original_papers)

    async def _generate_report_template(self, analysis: list, original_papers: list = None) -> str:
        """模板方式生成报告（降级处理）"""
        report = f"""# 文献分析报告

## 概述
本报告基于对所选文献的系统分析生成。
- **分析文献数量**: {len(analysis)} 篇

---

## 文献详细列表

"""
        papers_to_use = analysis if analysis else (original_papers or [])

        for i, paper in enumerate(papers_to_use, 1):
            title = paper.get('title', 'Unknown')
            authors = paper.get('authors', [])
            arxiv_id = paper.get('arxiv_id', '')
            doi = paper.get('doi', '')
            published = paper.get('published', '')
            published_year = paper.get('published_year', '')
            venue = paper.get('venue', '')
            citations = paper.get('citations', 0)
            summary = paper.get('summary', paper.get('abstract', 'N/A'))
            url = paper.get('url', '')
            categories = paper.get('categories', [])
            source = paper.get('source', '')

            basic_info_lines = [
                f"- **作者**: {', '.join(authors) if authors else 'N/A'}",
            ]

            if published:
                basic_info_lines.append(f"- **发表日期**: {published[:10]}")
            elif published_year:
                basic_info_lines.append(f"- **发表年份**: {published_year}")
            else:
                basic_info_lines.append(f"- **发表日期**: N/A")

            if venue:
                basic_info_lines.append(f"- **期刊/会议**: {venue}")

            if source == 'arxiv' and arxiv_id:
                basic_info_lines.append(f"- **ArXiv ID**: {arxiv_id}")

            if doi:
                basic_info_lines.append(f"- **DOI**: {doi}")

            if citations and citations > 0:
                basic_info_lines.append(f"- **引用数**: {citations}")

            link_display = url if url else (f'https://arxiv.org/abs/{arxiv_id}' if arxiv_id else 'N/A')
            basic_info_lines.append(f"- **链接**: {link_display}")

            if source == 'arxiv' and categories:
                basic_info_lines.append(f"- **分类**: {', '.join(categories)}")

            basic_info = '\n'.join(basic_info_lines)

            report += f"""### 文献 {i}: {title}

**基本信息**
{basic_info}

**摘要**
{summary if summary else 'N/A'}

"""
            research_question = paper.get('research_question', '')
            methodology = paper.get('methodology', '')
            key_contributions = paper.get('key_contributions', [])

            if research_question and research_question != '待分析':
                report += f"""**研究问题**
{research_question}

"""
            if methodology and methodology != '待分析':
                report += f"""**方法论**
{methodology}

"""
            if key_contributions and key_contributions != ['待分析']:
                report += """**核心贡献**
"""
                for contrib in key_contributions:
                    report += f"- {contrib}\n"
                report += "\n"

            report += "---\n\n"

        report += """
## 总结
以上是对所选文献的初步分析报告。建议进一步深入阅读原文以获取更完整的信息。

---
*本报告由 Multi-Agent 文献工作流系统自动生成*
"""
        return report

    async def _generate_report(self, analysis: list, original_papers: list = None) -> str:
        """生成报告内容（保留向下兼容）"""
        return await self._generate_report_template(analysis, original_papers)

    async def execute_task(self, task_content: Any) -> Any:
        """执行写作任务（直接调用）"""
        if isinstance(task_content, dict):
            analysis = task_content.get("analysis", [])
        else:
            analysis = []
        return await self._write_report(analysis)
