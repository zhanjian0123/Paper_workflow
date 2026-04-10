"""
PDF 解析工具 - 从 PDF 文件中提取文本
"""

import asyncio
from typing import Optional, Dict, Any
from pathlib import Path
import aiofiles

try:
    from pypdf import PdfReader
    PYPDF_AVAILABLE = True
except ImportError:
    PYPDF_AVAILABLE = False

from .base import BaseTool, ToolResult


class PDFParserTool(BaseTool):
    """
    PDF 解析工具 - 从 PDF 文件中提取文本
    支持逐页解析和全文提取
    """

    name = "pdf_parser"
    description = "Extract text from PDF files"

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__(config)
        self.default_output_dir = Path(
            config.get("output_dir", "output/papers")
        ) if config else Path("output/papers")

    def get_schema(self) -> Dict[str, Any]:
        return {
            "extract_text": {
                "file_path": {"type": "string", "required": True, "description": "PDF file path"},
                "page_range": {
                    "type": "object",
                    "required": False,
                    "description": "Page range {'start': int, 'end': int}",
                },
            },
            "get_metadata": {
                "file_path": {"type": "string", "required": True, "description": "PDF file path"},
            },
            "count_pages": {
                "file_path": {"type": "string", "required": True, "description": "PDF file path"},
            },
        }

    async def execute(self, action: str, **kwargs) -> ToolResult:
        """执行 PDF 解析操作"""
        if action == "extract_text":
            return await self.extract_text(**kwargs)
        elif action == "get_metadata":
            return await self.get_metadata(**kwargs)
        elif action == "count_pages":
            return await self.count_pages(**kwargs)
        else:
            return ToolResult(success=False, error=f"Unknown action: {action}")

    async def extract_text(
        self,
        file_path: str,
        page_range: Optional[Dict[str, int]] = None,
    ) -> ToolResult:
        """从 PDF 提取文本"""
        if not PYPDF_AVAILABLE:
            return ToolResult(
                success=True,  # 统一：工具不可用时返回 success=True 带 warning
                data={"texts": [], "full_text": ""},
                metadata={"error": "pypdf not installed"},
                warning="pypdf 库未安装，无法解析 PDF",
            )

        try:
            path = Path(file_path)
            if not path.exists():
                return ToolResult(success=False, error=f"File not found: {file_path}")

            reader = PdfReader(str(path))
            num_pages = len(reader.pages)

            # 确定页面范围
            if page_range:
                start = page_range.get("start", 0)
                end = page_range.get("end", num_pages)
            else:
                start, end = 0, num_pages

            # 提取文本
            texts = []
            for i in range(start, min(end, num_pages)):
                page = reader.pages[i]
                text = page.extract_text()
                if text:
                    texts.append({"page": i + 1, "text": text})

            return ToolResult(
                success=True,
                data={
                    "texts": texts,
                    "full_text": "\n".join([t["text"] for t in texts]),
                    "total_pages": num_pages,
                    "extracted_pages": len(texts),
                },
                metadata={"file_path": str(path)},
            )

        except Exception as e:
            return ToolResult(success=False, error=str(e))

    async def get_metadata(self, file_path: str) -> ToolResult:
        """获取 PDF 元数据"""
        if not PYPDF_AVAILABLE:
            return ToolResult(
                success=True,  # 统一：工具不可用时返回 success=True 带 warning
                data={},
                metadata={"error": "pypdf not installed"},
                warning="pypdf 库未安装，无法获取 PDF 元数据",
            )

        try:
            path = Path(file_path)
            if not path.exists():
                return ToolResult(success=False, error=f"File not found: {file_path}")

            reader = PdfReader(str(path))
            metadata = reader.metadata

            return ToolResult(
                success=True,
                data={
                    "title": metadata.get("/Title", "Unknown"),
                    "author": metadata.get("/Author", "Unknown"),
                    "subject": metadata.get("/Subject", ""),
                    "creator": metadata.get("/Creator", ""),
                    "producer": metadata.get("/Producer", ""),
                    "creation_date": str(metadata.get("/CreationDate", "")),
                    "page_count": len(reader.pages),
                },
                metadata={"file_path": str(path)},
            )

        except Exception as e:
            return ToolResult(success=False, error=str(e))

    async def count_pages(self, file_path: str) -> ToolResult:
        """计算 PDF 页数"""
        if not PYPDF_AVAILABLE:
            return ToolResult(
                success=True,  # 统一：工具不可用时返回 success=True 带 warning
                data={"page_count": 0},
                metadata={"error": "pypdf not installed"},
                warning="pypdf 库未安装，无法计算 PDF 页数",
            )

        try:
            path = Path(file_path)
            if not path.exists():
                return ToolResult(success=False, error=f"File not found: {file_path}")

            reader = PdfReader(str(path))

            return ToolResult(
                success=True,
                data={"page_count": len(reader.pages)},
                metadata={"file_path": str(path)},
            )

        except Exception as e:
            return ToolResult(success=False, error=str(e))
