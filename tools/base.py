"""
工具基类 - 所有工具的抽象基类
"""

from abc import ABC, abstractmethod
from typing import Any, Optional, Dict, List
from dataclasses import dataclass, field


@dataclass
class ToolResult:
    """工具执行结果"""

    success: bool
    data: Any = None
    error: Optional[str] = None
    warning: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}

    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "data": self.data,
            "error": self.error,
            "warning": self.warning,
            "metadata": self.metadata,
        }


class BaseTool(ABC):
    """
    工具抽象基类
    所有具体工具必须继承此类并实现抽象方法
    """

    name: str = "base_tool"
    description: str = "Base tool"

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config: Dict[str, Any] = config or {}
        self._initialized = False

    @abstractmethod
    async def execute(self, **kwargs) -> ToolResult:
        """
        执行工具
        子类必须实现此方法
        """
        pass

    def validate(self, **kwargs) -> bool:
        """
        验证参数
        默认实现总是返回 True，子类可以重写
        """
        return True

    def get_schema(self) -> Dict[str, Any]:
        """
        获取工具的参数 schema
        默认实现返回空字典，子类可以重写
        """
        return {}

    async def initialize(self) -> None:
        """
        初始化工具
        子类可以重写此方法进行资源初始化
        """
        self._initialized = True

    async def cleanup(self) -> None:
        """
        清理工具资源
        子类可以重写此方法进行资源清理
        """
        self._initialized = False

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(name={self.name})"
