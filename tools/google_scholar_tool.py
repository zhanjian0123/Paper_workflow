"""
Google Scholar 工具 - 学术论文搜索
"""

import urllib.parse
from typing import Optional, List, Dict, Any
from pathlib import Path

try:
    from scholarly import scholarly, ProxyGenerator
    SCHOLARLY_AVAILABLE = True
except ImportError:
    SCHOLARLY_AVAILABLE = False

from .base import BaseTool, ToolResult


class GoogleScholarTool(BaseTool):
    """
    Google Scholar 论文搜索工具
    支持搜索学术文献并获取元数据
    """

    name = "google_scholar"
    description = "Search academic papers from Google Scholar"

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__(config)
        self.max_results = config.get("max_results", 10) if config else 10

    def get_schema(self) -> Dict[str, Any]:
        return {
            "search": {
                "query": {"type": "string", "required": True, "description": "Search query"},
                "max_results": {"type": "integer", "required": False, "description": "Max results to return"},
                "year_range": {"type": "string", "required": False, "description": "Year range (e.g., 2020-2024 or 2023)"},
            },
        }

    async def execute(self, action: str, **kwargs) -> ToolResult:
        """执行 Google Scholar 操作"""
        if action == "search":
            return await self.search(**kwargs)
        else:
            return ToolResult(success=False, error=f"Unknown action: {action}")

    async def search(
        self, query: str, max_results: Optional[int] = None, year_range: Optional[str] = None
    ) -> ToolResult:
        """搜索论文"""
        max_results = max_results or self.max_results

        if not SCHOLARLY_AVAILABLE:
            return ToolResult(
                success=True,  # 统一：工具不可用时返回 success=True 带 warning
                data={"papers": [], "total": 0},
                metadata={"query": query, "source": "google_scholar", "error": "scholarly library not installed"},
                warning="scholarly 库未安装，无法使用 Google Scholar 搜索",
            )

        try:
            # 解析年份范围
            years = None
            if year_range:
                if "-" in year_range:
                    start_year, end_year = year_range.split("-")
                    years = (int(start_year), int(end_year))
                else:
                    year = int(year_range)
                    years = (year, year)

            # 尝试配置代理，失败则直接搜索
            pg = ProxyGenerator()
            try:
                # 尝试使用免费代理池（可能失败）
                pg.FreeProxies()
                scholarly.use_proxy(pg)
                print("[GoogleScholar] 已配置免费代理池")
            except Exception as proxy_err:
                print(f"[GoogleScholar] 代理配置失败 ({proxy_err})，尝试直接搜索...")
                # 不使用代理直接搜索
                pass

            # 使用 scholarly 库搜索
            print(f"[GoogleScholar] Searching for: {query}")
            search_query = scholarly.search_pubs(query)
            papers = []

            for _ in range(max_results):
                try:
                    pub = next(search_query)
                    paper = self._parse_paper(pub)

                    # 年份过滤
                    if years and paper.get("published_year"):
                        paper_year = paper["published_year"]
                        if not (years[0] <= paper_year <= years[1]):
                            continue

                    papers.append(paper)
                except StopIteration:
                    break
                except Exception as e:
                    print(f"[GoogleScholar] Error parsing paper: {e}")
                    continue

            if not papers:
                return ToolResult(
                    success=True,
                    data={"papers": [], "total": 0},
                    metadata={"query": query, "source": "google_scholar", "warning": "未找到相关论文"},
                )

            print(f"[GoogleScholar] Found {len(papers)} papers")
            return ToolResult(
                success=True,
                data={"papers": papers, "total": len(papers)},
                metadata={"query": query, "max_results": max_results, "year_range": year_range, "source": "google_scholar"},
            )

        except Exception as e:
            # 统一：异常时返回 success=True 带 warning，与其他工具保持一致
            return ToolResult(
                success=True,
                data={"papers": [], "total": 0},
                metadata={"query": query, "source": "google_scholar", "error": str(e)},
                warning=f"Google Scholar 搜索失败：{str(e)}",
            )

    def _parse_paper(self, pub: dict) -> Dict[str, Any]:
        """解析论文元数据"""
        # 处理作者字段 - 可能是字符串或列表
        author_data = pub.get("bib", {}).get("author", "")
        if isinstance(author_data, list):
            authors = author_data  # 已经是列表
        else:
            authors = author_data.split(" and ") if author_data else []

        # 获取摘要 - 尝试多个字段
        summary = (
            pub.get("bib", {}).get("abstract", "") or
            pub.get("bib", {}).get("snippet", "") or
            pub.get("bib", {}).get("summary", "") or
            ""
        )

        # 处理发表日期 - Google Scholar 返回 pub_year
        pub_year = pub.get("bib", {}).get("pub_year")
        published = f"{pub_year}-01-01" if pub_year else ""

        # 获取期刊/会议信息
        venue = pub.get("bib", {}).get("venue", "")

        paper = {
            "title": pub.get("bib", {}).get("title", "Unknown"),
            "authors": authors,
            "summary": summary,  # 完整摘要
            "published": published,  # 格式化后的日期
            "published_year": pub_year,
            "venue": venue,  # 期刊/会议
            "citations": pub.get("num_citations", 0),
            "source": "google_scholar",
            # ArXiv 相关字段（如果可用）
            "arxiv_id": "",
            "categories": [],
            "doi": "",
            "id": "",
        }

        # 提取 ArXiv ID（如果可用）
        arxiv_id = None
        pdf_url = None
        pub_urls = pub.get("pub_url", [])
        if pub_urls:
            if isinstance(pub_urls, list):
                for link in pub_urls:
                    if "arxiv.org" in link:
                        if "/abs/" in link:
                            arxiv_id = link.split("/abs/")[-1].split("/")[0]
                        elif "/pdf/" in link:
                            arxiv_id = link.split("/pdf/")[-1].replace(".pdf", "")
                        pdf_url = link
                        break
                paper["url"] = pdf_url or pub_urls[0]
            else:
                paper["url"] = str(pub_urls)
        else:
            paper["url"] = ""

        paper["arxiv_id"] = arxiv_id or ""

        return paper
