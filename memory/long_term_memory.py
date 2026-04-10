"""
长期记忆系统 - 基于文件的高质量、低噪音记忆存储

仅保存以下 4 类有价值的长期信息：
- user: 用户角色、经验、偏好、职责、协作风格
- feedback: 用户明确给出的协作反馈、纠正、禁忌、有效做法
- project: 无法从代码推导的项目上下文、业务背景、约束、决策原因
- reference: 外部信息源定位（文档、仪表盘、Slack 频道等）

禁止保存：
- 代码结构、架构、模块关系（可从代码推导）
- Git 历史、commit 信息
- Bug 修复步骤
- 当前任务状态、计划、todo
- PR 列表、活动日志
- 已写在 CLAUDE.md 等文件中的内容
- 敏感信息（token、密钥、密码、隐私）
"""

import os
import hashlib
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, List, Dict, Any, Literal
from dataclasses import dataclass, field, asdict
import json
import re

MemoryType = Literal["user", "feedback", "project", "reference"]


@dataclass
class MemoryEntry:
    """单条记忆条目"""

    id: str  # 唯一标识符（hash 生成）
    memory_type: MemoryType
    name: str  # 简短标题
    description: str  # 详细描述
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    expires_at: Optional[datetime] = None  # 过期时间（project 类型常用）
    source: Optional[str] = None  # 来源上下文（例如对话摘要）
    confidence: float = 1.0  # 置信度 0-1，用于过滤低质量记忆
    tags: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        d = asdict(self)
        d["created_at"] = self.created_at.isoformat()
        d["updated_at"] = self.updated_at.isoformat()
        if self.expires_at:
            d["expires_at"] = self.expires_at.isoformat()
        return d

    @classmethod
    def from_dict(cls, data: dict) -> "MemoryEntry":
        data["created_at"] = datetime.fromisoformat(data["created_at"])
        data["updated_at"] = datetime.fromisoformat(data["updated_at"])
        if data.get("expires_at"):
            data["expires_at"] = datetime.fromisoformat(data["expires_at"])
        return cls(**data)

    def is_expired(self) -> bool:
        """检查记忆是否过期"""
        if self.expires_at is None:
            return False
        return datetime.now() > self.expires_at

    def stale_days(self) -> int:
        """返回记忆未更新的天数"""
        delta = datetime.now() - self.updated_at
        return delta.days

    def is_stale(self, threshold_days: int = 180) -> bool:
        """检查记忆是否过时（超过阈值未更新）"""
        return self.stale_days() > threshold_days


class LongTermMemory:
    """
    长期记忆管理器

    存储结构：
    {memory_root}/
    ├── MEMORY.md              # 索引文件
    └── entries/
        ├── user_*.md          # 用户记忆
        ├── feedback_*.md      # 反馈记忆
        ├── project_*.md       # 项目记忆
        └── reference_*.md     # 参考记忆
    """

    # 不允许保存的敏感关键词
    FORBIDDEN_PATTERNS = [
        r"api[_-]?key",
        r"secret",
        r"token",
        r"password",
        r"credential",
        r"private[_-]?key",
        r"access[_-]?id",
        r"access[_-]?token",
        r"auth[_-]?token",
        r"bearer",
        r"-----BEGIN.*KEY-----",
        r"sk-[a-zA-Z0-9]+",
    ]

    # 禁止写入的内容特征
    FORBIDDEN_CONTENTS = [
        "clint list",
        "pull request",
        "pr #",
        "commit ",
        "git ",
        "branch ",
        "merge request",
        "todo",
        "doing",
        "done",
        "in progress",
        "task status",
    ]

    def __init__(
        self,
        memory_root: Optional[Path] = None,
        stale_threshold_days: int = 180,
        max_index_entries: int = 200,
    ):
        """
        初始化长期记忆系统

        Args:
            memory_root: 记忆存储根目录
            stale_threshold_days: 记忆过时阈值（天）
            max_index_entries: 索引文件最大条目数（预算控制）
        """
        if memory_root is None:
            # 默认在项目目录下创建 .claude/memory
            project_root = Path(__file__).parent.parent
            memory_root = project_root / ".claude" / "memory"

        self.memory_root = Path(memory_root)
        self.entries_dir = self.memory_root / "entries"
        self.index_file = self.memory_root / "MEMORY.md"
        self.stale_threshold_days = stale_threshold_days
        self.max_index_entries = max_index_entries

        self._ensure_directories()
        self._ensure_index_file()

    def _ensure_directories(self) -> None:
        """确保目录存在"""
        self.entries_dir.mkdir(parents=True, exist_ok=True)

    def _ensure_index_file(self) -> None:
        """确保索引文件存在"""
        if not self.index_file.exists():
            self.index_file.write_text(
                "# Memory Index\n\n自动生成的长期记忆索引。\n\n"
            )

    # ========== 安全校验 ==========

    def _validate_memory_type(self, memory_type: str) -> MemoryType:
        """验证记忆类型"""
        valid_types = ["user", "feedback", "project", "reference"]
        if memory_type not in valid_types:
            raise ValueError(
                f"Invalid memory type: {memory_type}. Must be one of {valid_types}"
            )
        return memory_type

    def _contains_sensitive_info(self, content: str) -> bool:
        """检查内容是否包含敏感信息"""
        content_lower = content.lower()

        # 检查正则模式
        for pattern in self.FORBIDDEN_PATTERNS:
            if re.search(pattern, content_lower):
                return True

        # 检查关键词
        for keyword in self.FORBIDDEN_CONTENTS:
            if keyword.lower() in content_lower:
                return True

        return False

    def _is_code_structure_info(self, content: str) -> bool:
        """检查是否是纯代码结构信息（不应存入记忆）"""
        code_patterns = [
            r"def\s+\w+\(",
            r"class\s+\w+",
            r"import\s+\w+",
            r"from\s+\w+\s+import",
            r"file:?[:\w./\\]+",
            r"path:?[:\w./\\]+",
            r"module\s+\w+",
            r"package\s+\w+",
        ]

        for pattern in code_patterns:
            if re.search(pattern, content.lower()):
                return True

        return False

    def _generate_entry_id(self, memory_type: MemoryType, name: str) -> str:
        """生成记忆条目 ID"""
        content = f"{memory_type}:{name}:{datetime.now().isoformat()}"
        return hashlib.sha256(content.encode()).hexdigest()[:12]

    def _get_entry_filename(self, entry: MemoryEntry) -> str:
        """获取记忆条目的文件名"""
        safe_name = re.sub(r"[^a-z0-9]+", "_", entry.name.lower())[:50]
        return f"{entry.memory_type}_{safe_name}_{entry.id}.md"

    # ========== 索引管理 ==========

    def _read_index(self) -> List[Dict[str, Any]]:
        """读取索引文件"""
        if not self.index_file.exists():
            return []

        content = self.index_file.read_text()
        entries = []

        # 解析索引中的条目（简化的 TOML-like 格式）
        current_entry = None
        for line in content.split("\n"):
            line = line.strip()
            if line.startswith("- ["):
                # 条目行：- [Title](file.md) — description
                match = re.match(r"- \[(.+?)\]\((.+?)\)\s*—?\s*(.*)?", line)
                if match:
                    if current_entry:
                        entries.append(current_entry)
                    current_entry = {
                        "title": match.group(1),
                        "file": match.group(2),
                        "description": match.group(3) or "",
                    }

        if current_entry:
            entries.append(current_entry)

        return entries

    def _write_index(self, entries: List[Dict[str, Any]]) -> None:
        """写入索引文件"""
        lines = [
            "# Memory Index",
            "",
            f"自动生成的长期记忆索引。最后更新：{datetime.now().isoformat()}",
            f"共 {len(entries)} 条记录。",
            "",
            "---",
            "",
        ]

        for entry in entries:
            lines.append(f"- [{entry['title']}]({entry['file']}) — {entry['description']}")

        self.index_file.write_text("\n".join(lines) + "\n")

    def _update_index(
        self, entry: MemoryEntry, action: str = "add"
    ) -> None:
        """更新索引"""
        entries = self._read_index()
        filename = self._get_entry_filename(entry)

        if action == "add":
            # 添加新条目
            entry_line = {
                "title": f"{entry.memory_type}: {entry.name}",
                "file": filename,
                "description": entry.description[:100] + "..."
                if len(entry.description) > 100
                else entry.description,
            }

            # 检查是否已存在
            exists = any(e["file"] == filename for e in entries)
            if not exists:
                entries.append(entry_line)

                # 预算控制：超出限制时移除最旧的条目
                if len(entries) > self.max_index_entries:
                    entries = entries[-self.max_index_entries :]

        elif action == "remove":
            entries = [e for e in entries if e["file"] != filename]

        self._write_index(entries)

    # ========== 核心 API ==========

    def save(
        self,
        memory_type: MemoryType,
        name: str,
        description: str,
        source: Optional[str] = None,
        tags: Optional[List[str]] = None,
        expires_days: Optional[int] = None,
        validate: bool = True,
    ) -> Optional[MemoryEntry]:
        """
        保存一条长期记忆

        Args:
            memory_type: 记忆类型 (user/feedback/project/reference)
            name: 简短标题
            description: 详细描述
            source: 来源上下文
            tags: 标签列表
            expires_days: 过期天数（project 类型常用）
            validate: 是否进行严格校验

        Returns:
            保存成功的 MemoryEntry，失败则返回 None
        """
        # 类型验证
        memory_type = self._validate_memory_type(memory_type)

        # 内容校验
        if validate:
            if self._contains_sensitive_info(name + description):
                print(f"[LongTermMemory] 拒绝保存：包含敏感信息")
                return None

            if self._is_code_structure_info(description):
                print(f"[LongTermMemory] 拒绝保存：纯代码结构信息可从代码推导")
                return None

            # 检查是否为临时状态信息
            lower_content = (name + description).lower()
            if any(
                kw in lower_content
                for kw in ["todo", "doing", "in progress", "task:", "step:"]
            ):
                print(f"[LongTermMemory] 拒绝保存：临时任务状态信息")
                return None

        # 创建记忆条目
        entry = MemoryEntry(
            id=self._generate_entry_id(memory_type, name),
            memory_type=memory_type,
            name=name,
            description=description.strip(),
            source=source,
            tags=tags or [],
            expires_at=(
                datetime.now() + timedelta(days=expires_days)
                if expires_days
                else None
            ),
        )

        # 写入文件
        filepath = self.entries_dir / self._get_entry_filename(entry)
        self._write_entry_file(filepath, entry)

        # 更新索引
        self._update_index(entry, action="add")

        print(
            f"[LongTermMemory] 已保存 {memory_type} 记忆：{name[:50]}..."
            if len(name) > 50
            else f"[LongTermMemory] 已保存 {memory_type} 记忆：{name}"
        )

        return entry

    def _write_entry_file(self, filepath: Path, entry: MemoryEntry) -> None:
        """写入记忆正文文件"""
        # 记忆正文格式（带 frontmatter）
        content = f"""---
name: {entry.name}
description: {entry.description[:200]}
type: {entry.memory_type}
id: {entry.id}
created_at: {entry.created_at.isoformat()}
updated_at: {entry.updated_at.isoformat()}
"""
        if entry.expires_at:
            content += f"expires_at: {entry.expires_at.isoformat()}\n"
        if entry.source:
            content += f"source: {entry.source[:200]}\n"
        if entry.tags:
            content += f"tags: {', '.join(entry.tags)}\n"

        content += f"---\n\n{entry.description}\n"

        filepath.write_text(content, encoding="utf-8")

    def _read_entry_file(self, filepath: Path) -> Optional[MemoryEntry]:
        """读取记忆正文文件"""
        if not filepath.exists():
            return None

        content = filepath.read_text(encoding="utf-8")

        # 解析 frontmatter
        if not content.startswith("---"):
            return None

        parts = content.split("---", 2)
        if len(parts) < 3:
            return None

        frontmatter_text = parts[1].strip()
        body = parts[2].strip()

        # 解析 YAML-like frontmatter（简单实现）
        frontmatter = {}
        for line in frontmatter_text.split("\n"):
            if ":" in line:
                key, value = line.split(":", 1)
                frontmatter[key.strip()] = value.strip()

        # 构建 MemoryEntry
        try:
            entry = MemoryEntry(
                id=frontmatter.get("id", ""),
                memory_type=frontmatter.get("type", "project"),
                name=frontmatter.get("name", ""),
                description=body,
                created_at=datetime.fromisoformat(frontmatter.get("created_at")),
                updated_at=datetime.fromisoformat(frontmatter.get("updated_at")),
                source=frontmatter.get("source"),
                tags=(
                    frontmatter.get("tags", "").split(", ")
                    if frontmatter.get("tags")
                    else []
                ),
            )
            if frontmatter.get("expires_at"):
                entry.expires_at = datetime.fromisoformat(frontmatter["expires_at"])
            return entry
        except Exception as e:
            print(f"[LongTermMemory] 读取记忆文件失败：{e}")
            return None

    def get(
        self,
        memory_type: Optional[MemoryType] = None,
        query: Optional[str] = None,
        exclude_expired: bool = True,
        exclude_stale: bool = False,
    ) -> List[MemoryEntry]:
        """
        获取记忆条目

        Args:
            memory_type: 按类型过滤
            query: 关键词搜索
            exclude_expired: 排除过期记忆
            exclude_stale: 排除过时记忆

        Returns:
            匹配的记忆条目列表
        """
        entries = []

        # 遍历所有记忆文件
        if not self.entries_dir.exists():
            return []

        for filepath in self.entries_dir.glob("*.md"):
            entry = self._read_entry_file(filepath)
            if not entry:
                continue

            # 过滤过期记忆
            if exclude_expired and entry.is_expired():
                continue

            # 过滤过时记忆
            if exclude_stale and entry.is_stale(self.stale_threshold_days):
                continue

            # 按类型过滤
            if memory_type and entry.memory_type != memory_type:
                continue

            # 按关键词搜索
            if query:
                query_lower = query.lower()
                searchable = f"{entry.name} {entry.description} {' '.join(entry.tags)}"
                if query_lower not in searchable.lower():
                    continue

            entries.append(entry)

        # 按更新时间排序（最新的在前）
        entries.sort(key=lambda e: e.updated_at, reverse=True)

        return entries

    def delete(self, entry_id: str) -> bool:
        """
        删除记忆条目

        Args:
            entry_id: 记忆 ID

        Returns:
            是否删除成功
        """
        # 查找记忆文件
        for filepath in self.entries_dir.glob(f"*_{entry_id}.md"):
            filepath.unlink()
            self._update_index(
                MemoryEntry(
                    id=entry_id,
                    memory_type="project",
                    name="",
                    description="",
                ),
                action="remove",
            )
            print(f"[LongTermMemory] 已删除记忆：{entry_id}")
            return True

        print(f"[LongTermMemory] 未找到记忆：{entry_id}")
        return False

    def update(
        self,
        entry_id: str,
        description: Optional[str] = None,
        name: Optional[str] = None,
        tags: Optional[List[str]] = None,
    ) -> Optional[MemoryEntry]:
        """
        更新记忆条目

        Args:
            entry_id: 记忆 ID
            description: 新描述
            name: 新名称
            tags: 新标签

        Returns:
            更新后的 MemoryEntry，失败则返回 None
        """
        # 查找记忆文件
        for filepath in self.entries_dir.glob(f"*_{entry_id}.md"):
            entry = self._read_entry_file(filepath)
            if not entry:
                return None

            # 更新字段
            if description:
                entry.description = description.strip()
            if name:
                entry.name = name
            if tags:
                entry.tags = tags
            entry.updated_at = datetime.now()

            # 重新写入
            self._write_entry_file(filepath, entry)

            # 更新索引（先删后加）
            self._update_index(entry, action="remove")
            self._update_index(entry, action="add")

            print(f"[LongTermMemory] 已更新记忆：{entry.name}")
            return entry

        print(f"[LongTermMemory] 未找到记忆：{entry_id}")
        return None

    def get_index_summary(self) -> str:
        """获取索引摘要（用于注入上下文）"""
        entries = self._read_index()
        if not entries:
            return "暂无长期记忆。"

        lines = [f"## 长期记忆索引 ({len(entries)} 条)", ""]
        for entry in entries[:20]:  # 最多显示 20 条
            lines.append(f"- {entry['title']}")

        if len(entries) > 20:
            lines.append(f"- ... 还有 {len(entries) - 20} 条")

        return "\n".join(lines)

    def cleanup(self) -> Dict[str, int]:
        """
        清理过期和过时的记忆

        Returns:
            清理统计
        """
        stats = {"expired": 0, "stale": 0, "total": 0}

        for filepath in self.entries_dir.glob("*.md"):
            entry = self._read_entry_file(filepath)
            if not entry:
                continue

            stats["total"] += 1

            should_delete = False

            if entry.is_expired():
                should_delete = True
                stats["expired"] += 1
            elif entry.is_stale(self.stale_threshold_days):
                should_delete = True
                stats["stale"] += 1

            if should_delete:
                filepath.unlink()
                self._update_index(entry, action="remove")

        return stats

    def __repr__(self) -> str:
        count = len(list(self.entries_dir.glob("*.md")))
        return f"LongTermMemory(entries={count}, root={self.memory_root})"


# ========== 便捷函数 ==========

def should_remember(content: str, context: str = "") -> bool:
    """
    判断某条信息是否值得存入长期记忆

    规则：
    - 必须是长期有效的洞察
    - 不能从代码直接推导
    - 不包含敏感信息
    - 不是临时状态或过程记录
    """
    memory = LongTermMemory()

    if memory._contains_sensitive_info(content):
        return False

    if memory._is_code_structure_info(content):
        return False

    # 检查是否为临时状态
    lower_content = content.lower()
    if any(
        kw in lower_content
        for kw in ["todo", "doing", "in progress", "task:", "step:", "pr #"]
    ):
        return False

    # 检查是否有足够的信息量
    if len(content.strip()) < 50:
        return False

    return True
