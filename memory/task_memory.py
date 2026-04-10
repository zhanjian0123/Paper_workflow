"""
任务记忆 - SQLite 持久化任务状态
"""

import sqlite3
from datetime import datetime
from typing import Optional, Any
from dataclasses import dataclass, field, asdict
from pathlib import Path
import json


@dataclass
class Task:
    """任务数据结构"""

    task_id: str
    title: str
    description: str
    status: str = "pending"  # pending/in_progress/completed/failed
    priority: int = 0  # 0-10, 越高越优先
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    completed_at: Optional[datetime] = None
    assigned_to: Optional[str] = None  # Agent 名称
    parent_task_id: Optional[str] = None
    dependencies: list[str] = field(default_factory=list)  # 依赖的任务 ID
    result: Optional[Any] = None  # 任务执行结果
    error_message: Optional[str] = None
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        d = asdict(self)
        d["created_at"] = self.created_at.isoformat()
        d["updated_at"] = self.updated_at.isoformat()
        if self.completed_at:
            d["completed_at"] = self.completed_at.isoformat()
        return d

    @classmethod
    def from_dict(cls, data: dict) -> "Task":
        data["created_at"] = datetime.fromisoformat(data["created_at"])
        data["updated_at"] = datetime.fromisoformat(data["updated_at"])
        if data.get("completed_at"):
            data["completed_at"] = datetime.fromisoformat(data["completed_at"])
        return cls(**data)


class TaskMemory:
    """
    任务记忆 - 使用 SQLite 存储任务状态
    支持任务分解、依赖关系、状态追踪
    """

    def __init__(self, db_path: Optional[Path] = None):
        if db_path is None:
            db_path = Path(__file__).parent.parent / "output" / "task_memory.db"
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self) -> None:
        """初始化数据库表"""
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS tasks (
                task_id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                description TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending',
                priority INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                completed_at TEXT,
                assigned_to TEXT,
                parent_task_id TEXT,
                dependencies TEXT,
                result TEXT,
                error_message TEXT,
                metadata TEXT
            )
        """
        )

        # 创建索引加速查询
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_status ON tasks(status)"
        )
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_assigned ON tasks(assigned_to)"
        )
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_parent ON tasks(parent_task_id)"
        )

        conn.commit()
        conn.close()

    def _get_connection(self) -> sqlite3.Connection:
        """获取数据库连接"""
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        return conn

    def create_task(self, task: Task) -> None:
        """创建新任务"""
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute(
            """
            INSERT INTO tasks (
                task_id, title, description, status, priority,
                created_at, updated_at, completed_at, assigned_to,
                parent_task_id, dependencies, result, error_message, metadata
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
            (
                task.task_id,
                task.title,
                task.description,
                task.status,
                task.priority,
                task.created_at.isoformat(),
                task.updated_at.isoformat(),
                task.completed_at.isoformat() if task.completed_at else None,
                task.assigned_to,
                task.parent_task_id,
                json.dumps(task.dependencies),
                json.dumps(task.result) if task.result else None,
                task.error_message,
                json.dumps(task.metadata),
            ),
        )

        conn.commit()
        conn.close()

    def get_task(self, task_id: str) -> Optional[Task]:
        """获取任务"""
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM tasks WHERE task_id = ?", (task_id,))
        row = cursor.fetchone()
        conn.close()

        if row:
            return Task(
                task_id=row["task_id"],
                title=row["title"],
                description=row["description"],
                status=row["status"],
                priority=row["priority"],
                created_at=datetime.fromisoformat(row["created_at"]),
                updated_at=datetime.fromisoformat(row["updated_at"]),
                completed_at=(
                    datetime.fromisoformat(row["completed_at"])
                    if row["completed_at"]
                    else None
                ),
                assigned_to=row["assigned_to"],
                parent_task_id=row["parent_task_id"],
                dependencies=json.loads(row["dependencies"]) if row["dependencies"] else [],
                result=json.loads(row["result"]) if row["result"] else None,
                error_message=row["error_message"],
                metadata=json.loads(row["metadata"]) if row["metadata"] else {},
            )
        return None

    def update_task(self, task: Task) -> None:
        """更新任务"""
        task.updated_at = datetime.now()
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute(
            """
            UPDATE tasks SET
                title = ?, description = ?, status = ?, priority = ?,
                updated_at = ?, completed_at = ?, assigned_to = ?,
                parent_task_id = ?, dependencies = ?, result = ?,
                error_message = ?, metadata = ?
            WHERE task_id = ?
        """,
            (
                task.title,
                task.description,
                task.status,
                task.priority,
                task.updated_at.isoformat(),
                task.completed_at.isoformat() if task.completed_at else None,
                task.assigned_to,
                task.parent_task_id,
                json.dumps(task.dependencies),
                json.dumps(task.result) if task.result else None,
                task.error_message,
                json.dumps(task.metadata),
                task.task_id,
            ),
        )

        conn.commit()
        conn.close()

    def delete_task(self, task_id: str) -> None:
        """删除任务"""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM tasks WHERE task_id = ?", (task_id,))
        conn.commit()
        conn.close()

    def get_tasks_by_status(self, status: str) -> list[Task]:
        """按状态获取任务"""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM tasks WHERE status = ?", (status,))
        rows = cursor.fetchall()
        conn.close()

        return [self._row_to_task(row) for row in rows]

    def get_tasks_by_agent(self, agent_name: str) -> list[Task]:
        """获取分配给特定 Agent 的任务"""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM tasks WHERE assigned_to = ? AND status != 'completed'",
            (agent_name,),
        )
        rows = cursor.fetchall()
        conn.close()

        return [self._row_to_task(row) for row in rows]

    def get_pending_tasks(self) -> list[Task]:
        """获取所有待处理任务"""
        return self.get_tasks_by_status("pending")

    def get_in_progress_tasks(self) -> list[Task]:
        """获取所有进行中任务"""
        return self.get_tasks_by_status("in_progress")

    def get_child_tasks(self, parent_task_id: str) -> list[Task]:
        """获取子任务"""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM tasks WHERE parent_task_id = ?", (parent_task_id,)
        )
        rows = cursor.fetchall()
        conn.close()

        return [self._row_to_task(row) for row in rows]

    def mark_completed(self, task_id: str, result: Any = None) -> None:
        """标记任务完成"""
        task = self.get_task(task_id)
        if task:
            task.status = "completed"
            task.completed_at = datetime.now()
            task.result = result
            self.update_task(task)

    def mark_failed(self, task_id: str, error_message: str) -> None:
        """标记任务失败"""
        task = self.get_task(task_id)
        if task:
            task.status = "failed"
            task.completed_at = datetime.now()
            task.error_message = error_message
            self.update_task(task)

    def _row_to_task(self, row: sqlite3.Row) -> Task:
        """将数据库行转换为 Task 对象"""
        return Task(
            task_id=row["task_id"],
            title=row["title"],
            description=row["description"],
            status=row["status"],
            priority=row["priority"],
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
            completed_at=(
                datetime.fromisoformat(row["completed_at"])
                if row["completed_at"]
                else None
            ),
            assigned_to=row["assigned_to"],
            parent_task_id=row["parent_task_id"],
            dependencies=json.loads(row["dependencies"]) if row["dependencies"] else [],
            result=json.loads(row["result"]) if row["result"] else None,
            error_message=row["error_message"],
            metadata=json.loads(row["metadata"]) if row["metadata"] else {},
        )
