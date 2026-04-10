"""
MCP Client - 连接和管理 MCP 服务器
"""

import asyncio
import json
import yaml
from typing import Optional, Dict, Any, List
from pathlib import Path


class MCPClient:
    """
    MCP Client - 连接 MCP 服务器并调用工具
    简化实现：直接映射到本地工具，预留远程 MCP 服务器支持
    """

    def __init__(self, config_path: Optional[Path] = None):
        if config_path is None:
            config_path = Path(__file__).parent.parent / "config" / "mcp_servers.yml"
        self.config_path = Path(config_path)
        self.servers: Dict[str, Dict[str, Any]] = {}
        self._initialized = False

    def load_config(self) -> Dict[str, Any]:
        """加载 MCP 服务器配置"""
        if not self.config_path.exists():
            return {}

        with open(self.config_path, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f)

        self.servers = config.get("servers", {})
        return self.servers

    def get_server_config(self, server_name: str) -> Optional[Dict[str, Any]]:
        """获取特定服务器的配置"""
        if not self.servers:
            self.load_config()
        return self.servers.get(server_name)

    async def initialize(self) -> None:
        """初始化 MCP 连接"""
        self.load_config()
        self._initialized = True

    async def call_tool(
        self, server_name: str, tool_name: str, arguments: Dict[str, Any]
    ) -> Any:
        """
        调用 MCP 服务器的工具
        简化实现：返回工具名称和参数，由上层调用本地工具
        """
        if not self._initialized:
            await self.initialize()

        server_config = self.get_server_config(server_name)
        if not server_config:
            raise ValueError(f"Unknown MCP server: {server_name}")

        # 返回调用信息，由上层决定如何执行
        return {
            "server": server_name,
            "tool": tool_name,
            "arguments": arguments,
            "config": server_config,
        }

    async def list_tools(self, server_name: str) -> List[Dict[str, Any]]:
        """获取服务器支持的工具列表"""
        if not self._initialized:
            await self.initialize()

        server_config = self.get_server_config(server_name)
        if not server_config:
            return []

        # 从配置中读取工具定义
        return server_config.get("tools", [])

    async def get_tool_schema(
        self, server_name: str, tool_name: str
    ) -> Optional[Dict[str, Any]]:
        """获取工具的参数 schema"""
        tools = await self.list_tools(server_name)
        for tool in tools:
            if tool.get("name") == tool_name:
                return tool.get("schema")
        return None

    async def close(self) -> None:
        """关闭所有连接"""
        self._initialized = False
