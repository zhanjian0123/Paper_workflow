"""
Tools Registry - 管理所有可用工具
"""

from typing import Optional, Dict, Any, List, Type
from pathlib import Path

from tools.base import BaseTool, ToolResult
from tools.arxiv_tool import ArxivTool
from tools.filesystem_tool import FileSystemTool
from tools.pdf_parser_tool import PDFParserTool
from tools.web_search_tool import WebSearchTool
from tools.google_scholar_tool import GoogleScholarTool


class ToolsRegistry:
    """
    工具注册表 - 管理所有可用工具
    支持动态注册和查询工具
    """

    # 内置工具映射
    BUILTIN_TOOLS: Dict[str, Type[BaseTool]] = {
        "arxiv": ArxivTool,
        "filesystem": FileSystemTool,
        "pdf_parser": PDFParserTool,
        "web_search": WebSearchTool,
        "google_scholar": GoogleScholarTool,
    }

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        self._tools: Dict[str, BaseTool] = {}
        self._initialized = False

    def register_tool(self, name: str, tool: BaseTool) -> None:
        """注册一个工具实例"""
        self._tools[name] = tool

    def get_tool(self, name: str) -> Optional[BaseTool]:
        """获取工具实例"""
        if name in self._tools:
            return self._tools[name]

        # 如果是内置工具，动态创建实例
        if name in self.BUILTIN_TOOLS:
            tool_config = self.config.get(name, {})
            tool = self.BUILTIN_TOOLS[name](tool_config)
            self._tools[name] = tool
            return tool

        return None

    def get_tool_schema(self, name: str) -> Optional[Dict[str, Any]]:
        """获取工具的 schema"""
        tool = self.get_tool(name)
        if tool:
            return tool.get_schema()
        return None

    def list_tools(self) -> List[Dict[str, Any]]:
        """列出所有可用工具"""
        tools_info = []
        for name, tool_class in self.BUILTIN_TOOLS.items():
            tool = self.get_tool(name)
            tools_info.append(
                {
                    "name": name,
                    "description": tool.description if tool else tool_class.description,
                    "schema": tool.get_schema() if tool else {},
                }
            )
        for name, tool in self._tools.items():
            if name not in self.BUILTIN_TOOLS:
                tools_info.append(
                    {
                        "name": name,
                        "description": tool.description,
                        "schema": tool.get_schema(),
                    }
                )
        return tools_info

    async def execute_tool(
        self, name: str, action: str, **kwargs
    ) -> ToolResult:
        """执行工具"""
        tool = self.get_tool(name)
        if not tool:
            return ToolResult(
                success=False, error=f"Unknown tool: {name}"
            )

        if not tool._initialized:
            await tool.initialize()

        try:
            return await tool.execute(action, **kwargs)
        except Exception as e:
            return ToolResult(success=False, error=str(e))

    async def initialize_all(self) -> None:
        """初始化所有已注册的工具"""
        for tool in self._tools.values():
            await tool.initialize()
        self._initialized = True

    async def cleanup_all(self) -> None:
        """清理所有工具资源"""
        for tool in self._tools.values():
            await tool.cleanup()
        self._initialized = False
