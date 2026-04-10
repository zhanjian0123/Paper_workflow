"""
ArXiv 工具测试
"""
import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from tools.arxiv_tool import ArxivTool
from tools.base import ToolResult


class TestArxivToolInitialization:
    """ArXiv 工具初始化测试"""

    def test_default_config(self):
        """测试默认配置"""
        tool = ArxivTool()
        assert tool.name == "arxiv"
        assert tool.max_results == 10

    def test_custom_config(self):
        """测试自定义配置"""
        tool = ArxivTool({"max_results": 5, "download_dir": "/tmp/test"})
        assert tool.max_results == 5


class TestArxivToolParseSearchResults:
    """XML 解析测试"""

    def test_parse_empty_xml(self):
        """测试解析空 XML"""
        tool = ArxivTool()
        papers = tool._parse_search_results("")
        assert papers == []

    def test_parse_invalid_xml(self):
        """测试解析无效 XML"""
        tool = ArxivTool()
        papers = tool._parse_search_results("<invalid>")
        assert papers == []

    def test_parse_valid_xml(self):
        """测试解析有效 XML"""
        tool = ArxivTool()
        xml_content = """<?xml version="1.0" encoding="UTF-8"?>
        <feed xmlns="http://www.w3.org/2005/Atom" xmlns:arxiv="http://arxiv.org/schemas/atom">
            <entry>
                <id>http://arxiv.org/abs/2401.00001</id>
                <title>Test Paper Title</title>
                <summary>Test abstract</summary>
                <author><name>Author A</name></author>
                <published>2024-01-01T00:00:00Z</published>
                <category term="cs.AI"/>
            </entry>
        </feed>
        """
        papers = tool._parse_search_results(xml_content)
        assert len(papers) == 1
        assert papers[0]["title"] == "Test Paper Title"
        assert papers[0]["arxiv_id"] == "2401.00001"


class TestArxivToolExecute:
    """工具执行测试"""

    @pytest.mark.asyncio
    async def test_unknown_action(self):
        """测试未知操作"""
        tool = ArxivTool()
        result = await tool.execute("unknown_action")
        assert result.success is False
        assert "Unknown action" in result.error

    @pytest.mark.asyncio
    async def test_search_returns_result_structure(self):
        """测试搜索返回结构"""
        tool = ArxivTool()
        result = await tool.execute("search", query="test")
        # 即使失败也应返回正确的结构
        assert isinstance(result, ToolResult)
        assert "data" in dir(result)
        assert result.data is not None


class TestToolResult:
    """ToolResult 测试"""

    def test_success_result(self):
        """测试成功结果"""
        result = ToolResult(success=True, data={"key": "value"})
        assert result.success is True
        assert result.data["key"] == "value"
        assert result.error is None

    def test_error_result(self):
        """测试错误结果"""
        result = ToolResult(success=False, error="Something went wrong")
        assert result.success is False
        assert result.error == "Something went wrong"

    def test_warning_result(self):
        """测试警告结果"""
        result = ToolResult(success=True, data={}, warning="Rate limited")
        assert result.success is True
        assert result.warning == "Rate limited"

    def test_to_dict(self):
        """测试转换为字典"""
        result = ToolResult(success=True, data={"key": "value"}, metadata={"extra": "info"})
        d = result.to_dict()
        assert d["success"] is True
        assert d["data"]["key"] == "value"
        assert d["metadata"]["extra"] == "info"
