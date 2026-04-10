"""
ArXiv 工具 - 论文搜索和下载
"""

import asyncio
import urllib.parse
import random
import xml.etree.ElementTree as ET
from typing import Optional, List, Dict, Any
from pathlib import Path

from .base import BaseTool, ToolResult
from .http_client import HttpClient, RetryConfig


class ArxivTool(BaseTool):
    """
    ArXiv 论文搜索和下载工具
    支持搜索、获取详情、下载 PDF
    """

    name = "arxiv"
    description = "Search and download papers from ArXiv"

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__(config)
        self.base_url = "https://export.arxiv.org/api/query"
        self.download_base = "https://arxiv.org/pdf"
        self.max_results = config.get("max_results", 10) if config else 10
        self.download_dir = Path(config.get("download_dir", "output/papers")) if config else Path("output/papers")
        self.download_dir.mkdir(parents=True, exist_ok=True)
        # 初始化 HTTP 客户端，使用重试配置（针对 429 错误增加延迟）
        self.http_client = HttpClient(
            verify_ssl=False,
            timeout=30.0,
            retry_config=RetryConfig(max_retries=5, base_delay=10.0),  # 429 错误需要更长延迟
        )

    def get_schema(self) -> Dict[str, Any]:
        return {
            "search": {
                "query": {"type": "string", "required": True, "description": "Search query"},
                "max_results": {"type": "integer", "required": False, "description": "Max results to return"},
                "year_range": {"type": "string", "required": False, "description": "Year range (e.g., 2020-2024 or 2023)"},
            },
            "download": {
                "arxiv_id": {"type": "string", "required": True, "description": "ArXiv ID (e.g., 2301.00001)"},
                "save_dir": {"type": "string", "required": False, "description": "Directory to save PDF"},
            },
            "get_details": {
                "arxiv_id": {"type": "string", "required": True, "description": "ArXiv ID"},
            },
        }

    async def execute(self, action: str, **kwargs) -> ToolResult:
        """执行 ArXiv 操作"""
        if action == "search":
            return await self.search(**kwargs)
        elif action == "download":
            return await self.download(**kwargs)
        elif action == "get_details":
            return await self.get_details(**kwargs)
        else:
            return ToolResult(success=False, error=f"Unknown action: {action}")

    async def search(
        self, query: str, max_results: Optional[int] = None, year_range: Optional[str] = None
    ) -> ToolResult:
        """搜索论文"""
        max_results = max_results or self.max_results

        try:
            # 构建搜索 URL
            encoded_query = urllib.parse.quote(query)

            # 添加年份过滤
            year_filter = ""
            if year_range:
                if "-" in year_range:
                    start_year, end_year = year_range.split("-")
                    # ArXiv API requires space around 'TO' and 14-digit datetime format (YYYYMMDDHHMMSS)
                    year_filter = f"+AND+submittedDate:[{start_year}0101000000 TO {end_year}1231235959]"
                else:
                    # Single year: full year range
                    year_filter = f"+AND+submittedDate:[{year_range}0101000000 TO {year_range}1231235959]"

            url = (
                f"{self.base_url}?search_query=all:{encoded_query}{year_filter}"
                f"&start=0&max_results={max_results}"
                f"&sortBy=relevance&sortOrder=descending"
            )

            # ArXiv API 有严格的频率限制（每 3 秒最多 1 次请求）
            # 添加随机延迟（3-6 秒），避免触发频率限制
            await asyncio.sleep(random.uniform(3.0, 6.0))

            # 使用共享 HTTP 客户端发送请求，重试 429 状态码
            success, xml_content, error = await self.http_client.get(
                url,
                timeout=30,
                retry_on_status=[429],
            )

            if not success:
                return ToolResult(
                    success=True,
                    data={"papers": [], "total": 0},
                    metadata={"query": query, "source": "arxiv_api", "error": error},
                    warning="ArXiv API 调用失败（可能由于频率限制），未找到论文"
                )

            # 解析 XML
            papers = self._parse_search_results(xml_content)

            if not papers:
                # 搜索结果为空，返回空结果，不返回假数据
                return ToolResult(
                    success=True,
                    data={"papers": [], "total": 0},
                    metadata={"query": query, "source": "arxiv_api"},
                    warning="未找到相关论文"
                )

            return ToolResult(
                success=True,
                data={"papers": papers, "total": len(papers)},
                metadata={"query": query, "max_results": max_results, "year_range": year_range},
            )

        except Exception as e:
            # API 调用失败，返回空结果，不返回假数据
            return ToolResult(
                success=True,
                data={"papers": [], "total": 0},
                metadata={"query": query, "source": "arxiv_api", "error": str(e)},
                warning="ArXiv API 调用失败，未找到论文"
            )

    async def download(self, arxiv_id: str, save_dir: Optional[str] = None) -> ToolResult:
        """下载论文 PDF - 如果文件已存在则跳过下载"""
        try:
            pdf_url = f"{self.download_base}/{arxiv_id}.pdf"

            # 使用自定义目录或默认目录
            if save_dir:
                download_dir = Path(save_dir)
            else:
                download_dir = self.download_dir

            download_dir.mkdir(parents=True, exist_ok=True)
            file_path = download_dir / f"{arxiv_id}.pdf"

            # 检查文件是否已存在，如果存在则直接返回
            if file_path.exists():
                print(f"  ⏭️  文件已存在，跳过下载：{arxiv_id}.pdf")
                return ToolResult(
                    success=True,
                    data={"file_path": str(file_path), "arxiv_id": arxiv_id},
                    metadata={"url": pdf_url, "skipped": True}
                )

            # 添加随机延迟（1-3 秒），避免触发频率限制
            await asyncio.sleep(random.uniform(1.0, 3.0))

            # 使用共享 HTTP 客户端下载，重试 429 状态码
            success, error = await self.http_client.download_file(
                pdf_url,
                str(file_path),
                timeout=60,
                retry_on_status=[429],
            )

            if success:
                return ToolResult(
                    success=True,
                    data={"file_path": str(file_path), "arxiv_id": arxiv_id},
                    metadata={"url": pdf_url},
                )
            else:
                return ToolResult(success=False, error=f"下载失败：{error}")

        except Exception as e:
            return ToolResult(success=False, error=str(e))

    async def get_details(self, arxiv_id: str) -> ToolResult:
        """获取论文详情"""
        try:
            url = f"{self.base_url}?id_list={arxiv_id}"

            success, xml_content, error = await self.http_client.get(url, timeout=30)

            if not success:
                return ToolResult(
                    success=False,
                    error=f"ArXiv API error: {error}",
                )

            # 解析 XML
            papers = self._parse_search_results(xml_content)

            if papers:
                return ToolResult(success=True, data=papers[0])
            else:
                return ToolResult(
                    success=False, error=f"Paper not found: {arxiv_id}"
                )

        except Exception as e:
            return ToolResult(success=False, error=str(e))

    def _parse_search_results(self, xml_content: str) -> List[Dict[str, Any]]:
        """解析 ArXiv XML 搜索结果"""
        try:
            ns = {
                "atom": "http://www.w3.org/2005/Atom",
                "arxiv": "http://arxiv.org/schemas/atom",
            }

            root = ET.fromstring(xml_content)
            entries = root.findall("atom:entry", ns)

            papers = []
            for entry in entries:
                paper = {}

                # ID
                id_elem = entry.find("atom:id", ns)
                if id_elem is not None:
                    paper["id"] = id_elem.text

                # Title
                title_elem = entry.find("atom:title", ns)
                if title_elem is not None:
                    paper["title"] = title_elem.text.strip().replace("\n", " ")

                # Summary/Abstract
                summary_elem = entry.find("atom:summary", ns)
                if summary_elem is not None:
                    paper["summary"] = summary_elem.text.strip().replace("\n", " ")

                # Authors
                authors = []
                for author_elem in entry.findall("atom:author", ns):
                    name_elem = author_elem.find("atom:name", ns)
                    if name_elem is not None:
                        authors.append(name_elem.text)
                paper["authors"] = authors

                # Published date
                published_elem = entry.find("atom:published", ns)
                if published_elem is not None:
                    paper["published"] = published_elem.text

                # Categories (arxiv categories)
                categories = []
                for cat_elem in entry.findall("atom:category", ns):
                    term = cat_elem.get("term")
                    if term:
                        categories.append(term)
                paper["categories"] = categories

                # ArXiv ID (extract from id)
                arxiv_id = paper.get("id", "").split("/")[-1]
                paper["arxiv_id"] = arxiv_id

                papers.append(paper)

            return papers

        except Exception as e:
            print(f"Error parsing ArXiv results: {e}")
            return []
