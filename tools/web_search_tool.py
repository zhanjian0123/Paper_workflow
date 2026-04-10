"""
Web 搜索工具 - 通用网络搜索
"""

from typing import Optional, Dict, Any, List
from pathlib import Path

from .base import BaseTool, ToolResult


class WebSearchTool(BaseTool):
    """
    Web 搜索工具 - 执行网络搜索
    支持多种搜索引擎（待配置）
    """

    name = "web_search"
    description = "Search the web for information"

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__(config)
        self.search_engine = config.get("search_engine", "duckduckgo") if config else "duckduckgo"
        self.max_results = config.get("max_results", 10) if config else 10

    def get_schema(self) -> Dict[str, Any]:
        return {
            "search": {
                "query": {"type": "string", "required": True, "description": "Search query"},
                "max_results": {"type": "integer", "required": False, "description": "Max results"},
            },
        }

    async def execute(self, action: str, **kwargs) -> ToolResult:
        """执行搜索操作"""
        if action == "search":
            return await self.search(**kwargs)
        else:
            return ToolResult(success=False, error=f"Unknown action: {action}")

    async def search(
        self, query: str, max_results: Optional[int] = None
    ) -> ToolResult:
        """执行网络搜索"""
        max_results = max_results or self.max_results

        try:
            if self.search_engine == "duckduckgo":
                results = await self._duckduckgo_search(query, max_results)
            else:
                results = await self._duckduckgo_search(query, max_results)

            return ToolResult(
                success=True,
                data={"results": results, "total": len(results)},
                metadata={"query": query, "engine": self.search_engine},
            )

        except Exception as e:
            return ToolResult(success=False, error=str(e))

    async def _duckduckgo_search(
        self, query: str, max_results: int
    ) -> List[Dict[str, str]]:
        """
        DuckDuckGo 搜索
        使用 duckduckgo_search 库执行网络搜索
        """
        from duckduckgo_search import DDGS
        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=max_results))
            return [
                {
                    "title": r.get("title", ""),
                    "url": r.get("href", ""),
                    "snippet": r.get("body", ""),
                }
                for r in results
            ]
