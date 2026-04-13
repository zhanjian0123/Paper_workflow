"""
Web 搜索工具 - 通用网络搜索
"""

import json
import os
import re
from typing import Optional, Dict, Any, List

from tools.http_client import HttpClient

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
        config = config or {}
        self.api_key = (
            config.get("api_key")
            or os.environ.get("DASHSCOPE_API_KEY")
            or os.environ.get("ANTHROPIC_API_KEY")
        )
        self.base_url = (
            config.get("base_url")
            or os.environ.get("DASHSCOPE_BASE_URL")
            or os.environ.get("ANTHROPIC_BASE_URL")
            or "https://dashscope.aliyuncs.com/compatible-mode/v1"
        )
        self.responses_url = self._build_responses_url(self.base_url)
        self.mcp_server_url = (
            config.get("mcp_server_url")
            or os.environ.get("DASHSCOPE_WEB_SEARCH_MCP_URL")
            or "https://dashscope.aliyuncs.com/api/v1/mcps/WebSearch/sse"
        )
        self.model_name = (
            config.get("model_name")
            or os.environ.get("DASHSCOPE_WEB_SEARCH_MODEL")
            or os.environ.get("MODEL_ID")
            or "qwen3.5-plus"
        )
        self.search_engine = (
            config.get("search_engine")
            or os.environ.get("WEB_SEARCH_ENGINE")
            or ("bailian_mcp" if self.api_key else "duckduckgo")
        )
        self.max_results = config.get("max_results", 10)
        self.fallback_enabled = self._parse_bool(
            config.get("fallback_enabled"),
            os.environ.get("WEB_SEARCH_FALLBACK_ENABLED", "true"),
        )
        verify_ssl = self._parse_bool(
            config.get("verify_ssl"),
            os.environ.get(
                "DASHSCOPE_VERIFY_SSL",
                os.environ.get("ANTHROPIC_VERIFY_SSL", "true"),
            ),
        )
        self.http_client = HttpClient(verify_ssl=verify_ssl, timeout=120)

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
            warning = None
            actual_engine = self.search_engine

            if self.search_engine == "bailian_mcp":
                try:
                    results = await self._bailian_mcp_search(query, max_results)
                except Exception as exc:
                    if not self.fallback_enabled:
                        raise
                    warning = f"百炼 MCP 搜索失败，已回退到 DuckDuckGo：{exc}"
                    actual_engine = "duckduckgo"
                    results = await self._duckduckgo_search(query, max_results)
            else:
                results = await self._duckduckgo_search(query, max_results)

            return ToolResult(
                success=True,
                data={"results": results, "total": len(results)},
                warning=warning,
                metadata={"query": query, "engine": actual_engine},
            )

        except Exception as e:
            return ToolResult(success=False, error=str(e))

    async def _bailian_mcp_search(
        self, query: str, max_results: int
    ) -> List[Dict[str, str]]:
        """通过百炼 Responses API 调用 WebSearch MCP 服务。"""
        if not self.api_key:
            raise ValueError("未配置 DASHSCOPE_API_KEY/ANTHROPIC_API_KEY，无法调用百炼 WebSearch MCP")

        payload = {
            "model": self.model_name,
            "input": (
                "请使用 websearch MCP 工具搜索以下问题，并仅返回 JSON。"
                "输出格式必须为 {\"results\": [{\"title\": \"...\", \"url\": \"...\", \"snippet\": \"...\"}] }。"
                f"最多返回 {max_results} 条结果。查询：{query}"
            ),
            "tools": [
                {
                    "type": "mcp",
                    "server_protocol": "sse",
                    "server_label": "websearch",
                    "server_description": "阿里云百炼联网搜索 MCP 服务",
                    "server_url": self.mcp_server_url,
                    "headers": {
                        "Authorization": f"Bearer {self.api_key}"
                    },
                }
            ],
        }
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }

        success, response_text, error = await self.http_client.post(
            self.responses_url,
            json=payload,
            headers=headers,
            timeout=120,
        )
        if not success:
            detail = response_text or error
            raise RuntimeError(f"百炼 Responses API 调用失败：{detail}")

        parsed = self._parse_bailian_response(response_text)
        results = parsed.get("results", [])
        if not results:
            raise RuntimeError("百炼 WebSearch MCP 未返回可解析的搜索结果")
        return results[:max_results]

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

    def _parse_bailian_response(self, response_text: str) -> Dict[str, List[Dict[str, str]]]:
        """从 Responses API 响应里提取模型输出的 JSON 搜索结果。"""
        payload = json.loads(response_text)
        candidate_texts = self._collect_candidate_texts(payload)

        for candidate in candidate_texts:
            parsed = self._extract_results_json(candidate)
            if parsed:
                return parsed

        raise ValueError("无法从百炼响应中提取 JSON 搜索结果")

    def _collect_candidate_texts(self, value: Any) -> List[str]:
        """递归收集可能包含模型文本输出的字段。"""
        texts: List[str] = []
        if isinstance(value, str):
            texts.append(value)
        elif isinstance(value, list):
            for item in value:
                texts.extend(self._collect_candidate_texts(item))
        elif isinstance(value, dict):
            prioritized_keys = ("output_text", "text", "content", "value")
            for key in prioritized_keys:
                item = value.get(key)
                if isinstance(item, str):
                    texts.append(item)
                elif isinstance(item, (list, dict)):
                    texts.extend(self._collect_candidate_texts(item))

            for item_key, item_value in value.items():
                if item_key not in prioritized_keys:
                    texts.extend(self._collect_candidate_texts(item_value))
        return texts

    def _extract_results_json(self, text: str) -> Optional[Dict[str, List[Dict[str, str]]]]:
        """从文本中提取 {results: [...]} JSON。"""
        stripped = text.strip()
        direct_candidates = [stripped]
        direct_candidates.extend(re.findall(r"\{[\s\S]*\}", stripped))

        for candidate in direct_candidates:
            try:
                parsed = json.loads(candidate)
            except json.JSONDecodeError:
                continue

            results = parsed.get("results")
            if not isinstance(results, list):
                continue

            normalized = []
            for item in results:
                if not isinstance(item, dict):
                    continue
                normalized.append(
                    {
                        "title": str(item.get("title", "")).strip(),
                        "url": str(item.get("url", "")).strip(),
                        "snippet": str(item.get("snippet", "")).strip(),
                    }
                )
            if normalized:
                return {"results": normalized}

        return None

    def _build_responses_url(self, base_url: str) -> str:
        normalized = base_url.rstrip("/")
        if normalized.endswith("/responses"):
            return normalized
        return f"{normalized}/responses"

    def _parse_bool(self, *values: Any) -> bool:
        for value in values:
            if value is None:
                continue
            if isinstance(value, bool):
                return value
            return str(value).strip().lower() in {"1", "true", "yes", "on"}
        return False
