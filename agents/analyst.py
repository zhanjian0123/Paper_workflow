"""
Analyst Agent - 文献分析
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


class AnalystAgent(BaseAgent):
    """
    Analyst Agent - 文献分析专家
    负责从论文中提取关键信息和分析内容
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
        skills = ["critical_analysis", "innovation_detection", "comparison_analysis"]
        tools = ["pdf_parser", "filesystem"]

        super().__init__(
            name="analyst",
            description="Academic analysis specialist for extracting key information from papers",
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
        self._analysis_results: Dict[str, Any] = {}

    async def process_message(self, message: Any) -> Optional[Any]:
        """处理分析任务"""
        content = message.content

        if isinstance(content, dict):
            papers = content.get("papers", [])
            task_id = content.get("task_id", "")
        else:
            papers = []
            task_id = ""

        return await self._analyze_papers(papers, task_id)

    async def _analyze_papers(
        self, papers: list, task_id: str = ""
    ) -> Optional[Any]:
        """分析论文"""
        print(f"[Analyst] Analyzing {len(papers)} papers")

        analysis_results = []

        for paper in papers:
            pdf_path = paper.get("pdf_path")
            if pdf_path:
                # 解析 PDF
                content = await self._parse_pdf(pdf_path)
                # 提取关键信息
                analysis = await self._extract_key_info(paper, content)
                analysis_results.append(analysis)
            else:
                # 只有摘要信息
                analysis = await self._extract_key_info(paper, None)
                analysis_results.append(analysis)

        # 保存结果
        self._analysis_results[task_id] = analysis_results

        if self.task_memory and task_id:
            self.task_memory.mark_completed(task_id, {"analysis": analysis_results})

        return {
            "task_id": task_id,
            "analysis": analysis_results,
            "count": len(analysis_results),
        }

    async def _parse_pdf(self, pdf_path: str) -> str:
        """解析 PDF 文件"""
        if self.tools_registry:
            result = await self.tools_registry.execute_tool(
                "pdf_parser", "extract_text", file_path=pdf_path
            )
            if result.success:
                return result.data.get("full_text", "")
        return ""

    async def _extract_key_info(
        self, paper: Dict[str, Any], content: Optional[str]
    ) -> Dict[str, Any]:
        """提取关键信息"""
        # 获取三个 skill prompt 并合并
        critical_prompt = self._get_skill_prompt("critical_analysis")
        innovation_prompt = self._get_skill_prompt("innovation_detection")
        comparison_prompt = self._get_skill_prompt("comparison_analysis")

        # 合并三个 prompt
        system_prompt = f"{critical_prompt}\n\n---\n\n{innovation_prompt}\n\n---\n\n{comparison_prompt}"

        # 构建分析输入
        input_text = f"""
Paper: {paper.get('title', 'Unknown')}
Authors: {', '.join(paper.get('authors', []))}
Abstract: {paper.get('summary', '')}

Full Content: {content[:8000] if content else 'Not available'}

---

请作为批判性学术分析专家、创新点检测专家和对比分析专家，根据系统提示中的分析指导原则，对以上论文进行深度解构。

**请从以下维度进行分析：**

1. **研究问题与动机** - 识别论文试图解决的本质矛盾，评估其紧迫性与重要性
2. **核心贡献与创新性** - 区分是"从 0 到 1"的突破还是渐进式改进，分析理论/实践价值
3. **方法论与逻辑严密性** - 剖析技术路线的合理性，审查核心假设是否成立
4. **实验验证与结果稳健性** - 检查实验设计是否支持论点，关注消融实验和基准测试
5. **局限性与潜在风险** - 挖掘作者未提及的弱点（如样本偏差、过拟合、环境依赖等）

**重要原则：**
- 证据导向：所有分析必须有原文对应位置作为支撑，严禁臆测
- 去伪存真：不被复杂公式或晦涩术语迷惑，重点关注物理意义与逻辑核心
- 不盲从权威：对所有论文保持客观的质疑态度

**对比分析要求：**
- 提取核心差异点，便于后续与其他论文进行横向对比
- 识别各方案在设计哲学上的差异和性能指标的取舍（Trade-offs）
- 关注技术路线的演进趋势

请提取以下关键信息：
1. research_question: 研究问题（1-2 句话）
2. methodology: 方法论（1-2 句话）
3. key_contributions: 核心贡献（JSON 数组，每项 1 句话）
4. innovations: 创新点（JSON 数组，每项 1 句话）
5. limitations: 局限性（JSON 数组，每项 1 句话）

请以 JSON 格式返回，不要其他解释。
"""

        # 使用 LLM 提取关键信息
        try:
            import json
            import re

            llm_response = await self._call_llm(input_text, system_prompt=system_prompt, temperature=0.3)

            # 解析 JSON
            json_match = re.search(r'\{[\s\S]*\}', llm_response)
            if json_match:
                extracted = json.loads(json_match.group())

                analysis = {
                    # 保留所有原始字段
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
                    "id": paper.get("id", ""),
                    "pdf_path": paper.get("pdf_path", ""),
                    "source": paper.get("source", "unknown"),
                    # 分析字段 - 使用 LLM 提取的结果
                    "research_question": extracted.get("research_question", "待分析"),
                    "methodology": extracted.get("methodology", "待分析"),
                    "key_contributions": extracted.get("key_contributions", ["待分析"]),
                    "innovations": extracted.get("innovations", ["待分析"]),
                    "limitations": extracted.get("limitations", ["待分析"]),
                }
                print(f"[Analyst] 完成分析：{paper.get('title', 'Unknown')[:50]}...")
                return analysis
        except Exception as e:
            print(f"[Analyst] LLM 分析失败：{e}，使用默认分析结果")

        # 降级处理：返回基本信息
        analysis = {
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
            "id": paper.get("id", ""),
            "pdf_path": paper.get("pdf_path", ""),
            "source": paper.get("source", "unknown"),
            "research_question": "待分析",
            "methodology": "待分析",
            "key_contributions": ["待分析"],
            "innovations": ["待分析"],
            "limitations": ["待分析"],
        }
        return analysis

    async def execute_task(self, task_content: Any) -> Any:
        """执行分析任务（直接调用）"""
        if isinstance(task_content, dict):
            papers = task_content.get("papers", [])
        else:
            papers = []
        return await self._analyze_papers(papers)
