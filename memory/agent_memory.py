"""
Agent 记忆 - SQLite 持久化 Agent 状态和对话历史
"""

import sqlite3
from datetime import datetime
from typing import Optional
from dataclasses import dataclass, asdict, field
from pathlib import Path
import json


@dataclass
class AgentState:
    """Agent 状态数据结构"""

    agent_name: str
    status: str = "idle"  # idle/busy/error
    current_task_id: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    last_active_at: Optional[datetime] = None
    error_message: Optional[str] = None
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        d = asdict(self)
        d["created_at"] = self.created_at.isoformat()
        d["updated_at"] = self.updated_at.isoformat()
        if self.last_active_at:
            d["last_active_at"] = self.last_active_at.isoformat()
        return d

    @classmethod
    def from_dict(cls, data: dict) -> "AgentState":
        data["created_at"] = datetime.fromisoformat(data["created_at"])
        data["updated_at"] = datetime.fromisoformat(data["updated_at"])
        if data.get("last_active_at"):
            data["last_active_at"] = datetime.fromisoformat(data["last_active_at"])
        return cls(**data)


@dataclass
class MessageHistory:
    """Agent 消息历史"""

    id: str
    agent_name: str
    role: str  # user/assistant/system
    content: str
    timestamp: datetime = field(default_factory=datetime.now)
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        d = asdict(self)
        d["timestamp"] = self.timestamp.isoformat()
        return d

    @classmethod
    def from_dict(cls, data: dict) -> "MessageHistory":
        data["timestamp"] = datetime.fromisoformat(data["timestamp"])
        return cls(**data)


class AgentMemory:
    """
    Agent 记忆 - 使用 SQLite 存储 Agent 状态和对话历史
    """

    def __init__(self, db_path: Optional[Path] = None):
        if db_path is None:
            db_path = Path(__file__).parent.parent / "output" / "agent_memory.db"
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self) -> None:
        """初始化数据库表"""
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()

        # Agent 状态表
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS agent_states (
                agent_name TEXT PRIMARY KEY,
                status TEXT NOT NULL DEFAULT 'idle',
                current_task_id TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                last_active_at TEXT,
                error_message TEXT,
                metadata TEXT
            )
        """
        )

        # 消息历史表
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS message_history (
                id TEXT PRIMARY KEY,
                agent_name TEXT NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                metadata TEXT
            )
        """
        )

        # 创建索引
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_agent ON message_history(agent_name)"
        )

        conn.commit()
        conn.close()

    def _get_connection(self) -> sqlite3.Connection:
        """获取数据库连接"""
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        return conn

    # ========== Agent 状态管理 ==========

    def save_state(self, state: AgentState) -> None:
        """保存 Agent 状态"""
        state.updated_at = datetime.now()
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute(
            """
            INSERT OR REPLACE INTO agent_states (
                agent_name, status, current_task_id, created_at,
                updated_at, last_active_at, error_message, metadata
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
            (
                state.agent_name,
                state.status,
                state.current_task_id,
                state.created_at.isoformat(),
                state.updated_at.isoformat(),
                state.last_active_at.isoformat() if state.last_active_at else None,
                state.error_message,
                json.dumps(state.metadata),
            ),
        )

        conn.commit()
        conn.close()

    def get_state(self, agent_name: str) -> Optional[AgentState]:
        """获取 Agent 状态"""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM agent_states WHERE agent_name = ?", (agent_name,)
        )
        row = cursor.fetchone()
        conn.close()

        if row:
            return AgentState(
                agent_name=row["agent_name"],
                status=row["status"],
                current_task_id=row["current_task_id"],
                created_at=datetime.fromisoformat(row["created_at"]),
                updated_at=datetime.fromisoformat(row["updated_at"]),
                last_active_at=(
                    datetime.fromisoformat(row["last_active_at"])
                    if row["last_active_at"]
                    else None
                ),
                error_message=row["error_message"],
                metadata=json.loads(row["metadata"]) if row["metadata"] else {},
            )
        return None

    def set_agent_status(
        self, agent_name: str, status: str, task_id: Optional[str] = None
    ) -> None:
        """设置 Agent 状态"""
        state = self.get_state(agent_name)
        if not state:
            state = AgentState(agent_name=agent_name)
        state.status = status
        state.current_task_id = task_id
        state.last_active_at = datetime.now()
        self.save_state(state)

    def get_all_agents(self) -> list[AgentState]:
        """获取所有 Agent 状态"""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM agent_states")
        rows = cursor.fetchall()
        conn.close()

        states = []
        for row in rows:
            states.append(
                AgentState(
                    agent_name=row["agent_name"],
                    status=row["status"],
                    current_task_id=row["current_task_id"],
                    created_at=datetime.fromisoformat(row["created_at"]),
                    updated_at=datetime.fromisoformat(row["updated_at"]),
                    last_active_at=(
                        datetime.fromisoformat(row["last_active_at"])
                        if row["last_active_at"]
                        else None
                    ),
                    error_message=row["error_message"],
                    metadata=json.loads(row["metadata"]) if row["metadata"] else {},
                )
            )
        return states

    # ========== 消息历史管理 ==========

    def add_message(self, history: MessageHistory) -> None:
        """添加消息到历史记录"""
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute(
            """
            INSERT INTO message_history (id, agent_name, role, content, timestamp, metadata)
            VALUES (?, ?, ?, ?, ?, ?)
        """,
            (
                history.id,
                history.agent_name,
                history.role,
                history.content,
                history.timestamp.isoformat(),
                json.dumps(history.metadata),
            ),
        )

        conn.commit()
        conn.close()

    def get_messages(
        self, agent_name: str, limit: int = 50
    ) -> list[MessageHistory]:
        """获取 Agent 的消息历史"""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT * FROM message_history
            WHERE agent_name = ?
            ORDER BY timestamp DESC
            LIMIT ?
        """,
            (agent_name, limit),
        )
        rows = cursor.fetchall()
        conn.close()

        histories = []
        for row in reversed(rows):  # 恢复为时间正序
            histories.append(
                MessageHistory(
                    id=row["id"],
                    agent_name=row["agent_name"],
                    role=row["role"],
                    content=row["content"],
                    timestamp=datetime.fromisoformat(row["timestamp"]),
                    metadata=json.loads(row["metadata"]) if row["metadata"] else {},
                )
            )
        return histories

    def clear_messages(self, agent_name: str) -> None:
        """清空 Agent 的消息历史"""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "DELETE FROM message_history WHERE agent_name = ?", (agent_name,)
        )
        conn.commit()
        conn.close()

    def get_recent_messages(
        self, agent_name: str, minutes: int = 30
    ) -> list[MessageHistory]:
        """获取最近一段时间内的消息"""
        conn = self._get_connection()
        cursor = conn.cursor()
        cutoff = datetime.now().timestamp() - (minutes * 60)
        cursor.execute(
            """
            SELECT * FROM message_history
            WHERE agent_name = ? AND timestamp >= datetime(?, 'unixepoch')
            ORDER BY timestamp ASC
        """,
            (agent_name, cutoff),
        )
        rows = cursor.fetchall()
        conn.close()

        return [
            MessageHistory(
                id=row["id"],
                agent_name=row["agent_name"],
                role=row["role"],
                content=row["content"],
                timestamp=datetime.fromisoformat(row["timestamp"]),
                metadata=json.loads(row["metadata"]) if row["metadata"] else {},
            )
            for row in rows
        ]
