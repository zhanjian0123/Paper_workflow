"""
Search Agent - 文献搜索
"""

import asyncio
import random
from typing import Any, Optional, List, Dict, Callable
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

from agents.base import BaseAgent
from core.message_bus import MessageBus
from memory.task_memory import TaskMemory
from memory.agent_memory import AgentMemory
from core.skill_loader import SkillLoader
from mcp.tools_registry import ToolsRegistry


class SearchAgent(BaseAgent):
    """
    Search Agent - 文献搜索专家
    负责搜索和下载学术论文
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
        skills = ["literature_search"]
        tools = ["arxiv", "google_scholar", "web_search", "filesystem"]

        super().__init__(
            name="search",
            description="Academic literature search specialist",
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
        self._search_results: List[Dict[str, Any]] = []

    async def process_message(self, message: Any) -> Optional[Any]:
        """处理搜索任务"""
        content = message.content

        if isinstance(content, dict):
            query = content.get("query") or content.get("description", "")
            task_id = content.get("task_id", "")
            year_range = content.get("year_range", None)
            download_dir = content.get("download_dir", "output/papers")
            max_papers = content.get("max_papers", 10)
            source = content.get("source", "arxiv")  # arxiv, google_scholar, or both
            workflow_id = content.get("workflow_id", "")
            on_progress = content.get("on_progress", None)
        else:
            query = str(content)
            task_id = ""
            year_range = None
            download_dir = "output/papers"
            max_papers = 10
            source = "arxiv"
            workflow_id = ""
            on_progress = None

        return await self._search(query, task_id, year_range, download_dir, max_papers, source, workflow_id, on_progress)

    async def _search(self, query: str, task_id: str = "", year_range: Optional[str] = None,
                      download_dir: str = "output/papers", max_papers: int = 10,
                      source: str = "arxiv", workflow_id: str = "",
                      on_progress: Optional[Callable] = None) -> Optional[Any]:
        """执行搜索 - 直接使用 ArXiv API，不调用 LLM"""
        print(f"[Search] Searching for: {query}, source: {source}, year_range: {year_range}, max_papers: {max_papers}")

        # 直接使用原始查询，不调用 LLM 优化
        optimized_query = query

        # 根据 source 选择搜索工具
        if self.tools_registry:
            all_papers = []
            warnings = []

            # 确定要使用的数据源
            sources_to_use = []
            if source == "both":
                sources_to_use = ["arxiv", "google_scholar"]
            elif source == "google" or source == "google_scholar":
                sources_to_use = ["google_scholar"]
            else:  # arxiv 或默认
                sources_to_use = ["arxiv"]

            # 从每个数据源搜索
            for src in sources_to_use:
                print(f"[Search] Searching in {src}...")
                if on_progress:
                    on_progress("search", 15, f"正在搜索 {src}...")
                await asyncio.sleep(0.1)

                result = await self.tools_registry.execute_tool(
                    src, "search", query=optimized_query, max_results=max_papers, year_range=year_range
                )

                if result.success and result.data.get("papers"):
                    papers = result.data.get("papers", [])
                    all_papers.extend(papers)
                    print(f"  ✓ Found {len(papers)} papers from {src}")
                    if on_progress:
                        on_progress("search", 20, f"从 {src} 找到 {len(papers)} 篇论文")
                        await asyncio.sleep(0.1)
                    if result.warning:
                        warnings.append(f"{src}: {result.warning}")
                elif result.success:
                    warning = result.warning or result.metadata.get("warning")
                    if warning:
                        warnings.append(f"{src}: {warning}")
                        print(f"  - {src} warning: {warning}")
                    else:
                        print(f"  - No papers found from {src}")
                else:
                    print(f"  ✗ Error from {src}: {result.error}")
                    warnings.append(f"{src}: {result.error}")

            # 去重（根据标题）
            seen_titles = set()
            unique_papers = []
            for paper in all_papers:
                title = paper.get("title", "").lower()
                if title not in seen_titles:
                    seen_titles.add(title)
                    unique_papers.append(paper)

            # 限制数量
            unique_papers = unique_papers[:max_papers]

            if unique_papers:
                self._search_results = unique_papers

                # 下载论文 PDF 到指定目录
                downloaded = 0
                skipped = 0
                total_to_download = min(len(self._search_results), max_papers)

                for i, paper in enumerate(self._search_results):
                    if downloaded + skipped >= max_papers:
                        break

                    # 在每篇下载前添加随机延迟（2-5 秒），避免触发频率限制
                    if i > 0:  # 第一篇不延迟
                        if on_progress:
                            on_progress("search", 55, f"等待 {random.uniform(2.0, 5.0):.1f} 秒避免频率限制...")
                        await asyncio.sleep(random.uniform(2.0, 5.0))

                    arxiv_id = paper.get("arxiv_id")
                    url = paper.get("url", "")

                    # 尝试从 ArXiv 下载
                    if arxiv_id:
                        if on_progress:
                            progress = 55 + int(((downloaded + skipped) / total_to_download) * 40)
                            on_progress("search", progress, f"正在下载 {arxiv_id}.pdf ({downloaded + skipped + 1}/{total_to_download})...")
                        await asyncio.sleep(0.1)

                        download_result = await self.tools_registry.execute_tool(
                            "arxiv", "download", arxiv_id=arxiv_id, save_dir=download_dir
                        )
                        if download_result.success:
                            paper["pdf_path"] = download_result.data.get("file_path")
                            # 检查是否是跳过下载（文件已存在）
                            if download_result.metadata and download_result.metadata.get("skipped"):
                                skipped += 1
                                print(f"  ⏭️  已跳过：{arxiv_id}.pdf (文件已存在)")
                            else:
                                downloaded += 1
                                print(f"  ✓ Downloaded: {arxiv_id}.pdf")
                        else:
                            print(f"  ✗ Download failed: {arxiv_id} - {download_result.error}")
                    elif url and "arxiv.org" in url:
                        # 从 URL 提取 ArXiv ID
                        arxiv_id = url.split("/abs/")[-1].split("/")[0] if "/abs/" in url else None
                        if arxiv_id:
                            if on_progress:
                                progress = 55 + int(((downloaded + skipped) / total_to_download) * 40)
                                on_progress("search", progress, f"正在下载 {arxiv_id}.pdf ({downloaded + skipped + 1}/{total_to_download})...")
                            await asyncio.sleep(0.1)

                            download_result = await self.tools_registry.execute_tool(
                                "arxiv", "download", arxiv_id=arxiv_id, save_dir=download_dir
                            )
                            if download_result.success:
                                paper["pdf_path"] = download_result.data.get("file_path")
                                # 检查是否是跳过下载（文件已存在）
                                if download_result.metadata and download_result.metadata.get("skipped"):
                                    skipped += 1
                                    print(f"  ⏭️  已跳过：{arxiv_id}.pdf (文件已存在)")
                                else:
                                    downloaded += 1
                                    print(f"  ✓ Downloaded: {arxiv_id}.pdf")

                # 下载完成
                if on_progress:
                    on_progress("search", 95, f"下载完成，新下载 {downloaded} 篇，跳过 {skipped} 篇")
                    await asyncio.sleep(0.1)

                # 保存搜索结果到任务记忆
                if self.task_memory and task_id:
                    self.task_memory.mark_completed(
                        task_id,
                        {"papers": self._search_results, "count": len(self._search_results)},
                    )

                return {
                    "task_id": task_id,
                    "papers": self._search_results,
                    "count": len(self._search_results),
                    "source": source,
                }
            else:
                # 搜索结果为空
                warning = "；".join(warnings) if warnings else "未找到相关论文"
                print(f"[Search] {warning}")
                return {
                    "task_id": task_id,
                    "papers": [],
                    "count": 0,
                    "warning": warning,
                }

        return {"task_id": task_id, "papers": [], "error": "Tools registry not available"}

    async def execute_task(self, task_content: Any) -> Any:
        """执行搜索任务（直接调用）"""
        if isinstance(task_content, dict):
            query = task_content.get("query", str(task_content))
            year_range = task_content.get("year_range")
            download_dir = task_content.get("download_dir", "output/papers")
            max_papers = task_content.get("max_papers", 10)
            source = task_content.get("source", "arxiv")
        else:
            query = str(task_content)
            year_range = None
            download_dir = "output/papers"
            max_papers = 10
            source = "arxiv"
        return await self._search(query, "", year_range, download_dir, max_papers, source)
