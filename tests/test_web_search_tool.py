"""
Web 搜索工具测试
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from tools.web_search_tool import WebSearchTool


class TestWebSearchToolInitialization:
    """Web 搜索工具初始化测试"""

    def test_defaults_to_bailian_when_api_key_exists(self, monkeypatch):
        monkeypatch.setenv("DASHSCOPE_API_KEY", "test-key")
        tool = WebSearchTool()
        assert tool.search_engine == "bailian_mcp"
        assert tool.responses_url.endswith("/responses")

    def test_defaults_to_duckduckgo_without_api_key(self, monkeypatch):
        monkeypatch.delenv("DASHSCOPE_API_KEY", raising=False)
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        tool = WebSearchTool()
        assert tool.search_engine == "duckduckgo"


class TestWebSearchToolResponseParsing:
    """百炼响应解析测试"""

    def test_parse_bailian_response_from_output_text(self):
        tool = WebSearchTool({"api_key": "test-key"})
        response_text = """
        {
          "id": "resp_123",
          "output_text": "{\\"results\\":[{\\"title\\":\\"Aliyun News\\",\\"url\\":\\"https://example.com\\",\\"snippet\\":\\"Snippet\\"}]}"
        }
        """
        parsed = tool._parse_bailian_response(response_text)
        assert parsed["results"][0]["title"] == "Aliyun News"
        assert parsed["results"][0]["url"] == "https://example.com"

    def test_parse_bailian_response_from_nested_content(self):
        tool = WebSearchTool({"api_key": "test-key"})
        response_text = """
        {
          "output": [
            {
              "content": [
                {
                  "type": "output_text",
                  "text": "{\\"results\\":[{\\"title\\":\\"Result A\\",\\"url\\":\\"https://a.com\\",\\"snippet\\":\\"A\\"}]}"
                }
              ]
            }
          ]
        }
        """
        parsed = tool._parse_bailian_response(response_text)
        assert parsed["results"][0]["title"] == "Result A"


class TestWebSearchToolExecution:
    """Web 搜索执行测试"""

    @pytest.mark.asyncio
    async def test_falls_back_to_duckduckgo_when_bailian_fails(self, monkeypatch):
        tool = WebSearchTool({"api_key": "test-key", "search_engine": "bailian_mcp"})

        async def fake_bailian(query, max_results):
            raise RuntimeError("boom")

        async def fake_duckduckgo(query, max_results):
            return [{"title": "Fallback", "url": "https://fallback.test", "snippet": "ok"}]

        monkeypatch.setattr(tool, "_bailian_mcp_search", fake_bailian)
        monkeypatch.setattr(tool, "_duckduckgo_search", fake_duckduckgo)

        result = await tool.search("test")
        assert result.success is True
        assert result.metadata["engine"] == "duckduckgo"
        assert result.warning is not None
        assert result.data["results"][0]["title"] == "Fallback"

    @pytest.mark.asyncio
    async def test_returns_bailian_results_when_available(self, monkeypatch):
        tool = WebSearchTool({"api_key": "test-key", "search_engine": "bailian_mcp"})

        async def fake_bailian(query, max_results):
            return [{"title": "Aliyun", "url": "https://aliyun.com", "snippet": "search"}]

        monkeypatch.setattr(tool, "_bailian_mcp_search", fake_bailian)

        result = await tool.search("aliyun")
        assert result.success is True
        assert result.metadata["engine"] == "bailian_mcp"
        assert result.data["results"][0]["title"] == "Aliyun"
