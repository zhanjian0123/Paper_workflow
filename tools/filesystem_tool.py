"""
文件系统工具 - 文件读写操作
"""

import asyncio
from typing import Optional, Dict, Any, List
from pathlib import Path
import aiofiles
import json

from .base import BaseTool, ToolResult


class FileSystemTool(BaseTool):
    """
    文件系统工具 - 读写文件
    支持读取、写入、列出目录内容
    """

    name = "filesystem"
    description = "Read and write files to the local filesystem"

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__(config)
        self.base_dir = Path(config.get("base_dir", "output")) if config else Path("output")
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def get_schema(self) -> Dict[str, Any]:
        return {
            "read": {
                "file_path": {"type": "string", "required": True, "description": "File path to read"},
            },
            "write": {
                "file_path": {"type": "string", "required": True, "description": "File path to write"},
                "content": {"type": "string", "required": True, "description": "Content to write"},
            },
            "list_dir": {
                "dir_path": {"type": "string", "required": False, "description": "Directory to list"},
            },
        }

    async def execute(self, action: str, **kwargs) -> ToolResult:
        """执行文件系统操作"""
        if action == "read":
            return await self.read(**kwargs)
        elif action == "write":
            return await self.write(**kwargs)
        elif action == "list_dir":
            return await self.list_dir(**kwargs)
        else:
            return ToolResult(success=False, error=f"Unknown action: {action}")

    async def read(self, file_path: str) -> ToolResult:
        """读取文件内容"""
        try:
            path = Path(file_path)
            if not path.is_absolute():
                path = self.base_dir / path

            if not path.exists():
                return ToolResult(
                    success=False, error=f"File not found: {file_path}"
                )

            async with aiofiles.open(path, "r", encoding="utf-8") as f:
                content = await f.read()

            return ToolResult(
                success=True,
                data={"content": content, "file_path": str(path)},
                metadata={"size": len(content)},
            )

        except Exception as e:
            return ToolResult(success=False, error=str(e))

    async def write(
        self, file_path: str, content: str, mode: str = "w"
    ) -> ToolResult:
        """写入文件内容"""
        try:
            path = Path(file_path)
            if not path.is_absolute():
                path = self.base_dir / path

            # 确保目录存在
            path.parent.mkdir(parents=True, exist_ok=True)

            async with aiofiles.open(path, mode, encoding="utf-8") as f:
                await f.write(content)

            return ToolResult(
                success=True,
                data={"file_path": str(path), "bytes_written": len(content)},
            )

        except Exception as e:
            return ToolResult(success=False, error=str(e))

    async def list_dir(self, dir_path: Optional[str] = None) -> ToolResult:
        """列出目录内容"""
        try:
            if dir_path:
                path = Path(dir_path)
                if not path.is_absolute():
                    path = self.base_dir / path
            else:
                path = self.base_dir

            if not path.exists():
                return ToolResult(
                    success=False, error=f"Directory not found: {dir_path}"
                )

            if not path.is_dir():
                return ToolResult(
                    success=False, error=f"Not a directory: {dir_path}"
                )

            items = []
            for item in path.iterdir():
                items.append(
                    {
                        "name": item.name,
                        "type": "directory" if item.is_dir() else "file",
                        "path": str(item),
                    }
                )

            return ToolResult(
                success=True,
                data={"items": items, "dir_path": str(path)},
                metadata={"count": len(items)},
            )

        except Exception as e:
            return ToolResult(success=False, error=str(e))

    async def read_json(self, file_path: str) -> ToolResult:
        """读取 JSON 文件"""
        result = await self.read(file_path)
        if result.success:
            try:
                result.data["json_content"] = json.loads(result.data["content"])
            except json.JSONDecodeError as e:
                return ToolResult(success=False, error=f"Invalid JSON: {e}")
        return result

    async def write_json(
        self, file_path: str, content: Any, indent: int = 2
    ) -> ToolResult:
        """写入 JSON 文件"""
        try:
            json_str = json.dumps(content, ensure_ascii=False, indent=indent)
            return await self.write(file_path, json_str)
        except Exception as e:
            return ToolResult(success=False, error=str(e))
