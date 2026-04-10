"""
记忆服务 - 封装现有的 LongTermMemory

提供与 Pydantic Schema 兼容的接口
"""
import sys
from pathlib import Path
from typing import Optional, List

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from memory.long_term_memory import LongTermMemory, MemoryEntry


class MemoryService:
    """
    记忆服务

    封装 LongTermMemory，提供与 API Schema 兼容的接口
    """

    def __init__(self):
        self._memory = LongTermMemory()

    def get(
        self,
        memory_type: Optional[str] = None,
        query: Optional[str] = None,
        exclude_expired: bool = True,
        exclude_stale: bool = False,
    ) -> List[MemoryEntry]:
        """获取记忆列表"""
        return self._memory.get(
            memory_type=memory_type,
            query=query,
            exclude_expired=exclude_expired,
            exclude_stale=exclude_stale,
        )

    def save(
        self,
        memory_type: str,
        name: str,
        description: str,
        tags: Optional[List[str]] = None,
        expires_days: Optional[int] = None,
    ) -> Optional[MemoryEntry]:
        """保存记忆"""
        return self._memory.save(
            memory_type=memory_type,
            name=name,
            description=description,
            tags=tags,
            expires_days=expires_days,
        )

    def delete(self, entry_id: str) -> bool:
        """删除记忆"""
        return self._memory.delete(entry_id)

    def update(
        self,
        entry_id: str,
        name: Optional[str] = None,
        description: Optional[str] = None,
        tags: Optional[List[str]] = None,
    ) -> Optional[MemoryEntry]:
        """更新记忆"""
        return self._memory.update(
            entry_id=entry_id,
            name=name,
            description=description,
            tags=tags,
        )

    def cleanup(self) -> dict:
        """清理过期/过时记忆"""
        stats = self._memory.cleanup()
        return stats

    # ========== 校验方法（公开） ==========

    def _contains_sensitive_info(self, content: str) -> bool:
        """检查是否包含敏感信息"""
        return self._memory._contains_sensitive_info(content)

    def _is_code_structure_info(self, content: str) -> bool:
        """检查是否是纯代码结构信息"""
        return self._memory._is_code_structure_info(content)

    def get_index_summary(self) -> str:
        """获取索引摘要"""
        return self._memory.get_index_summary()
