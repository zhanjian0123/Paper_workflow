"""
工作流存储 - SQLite 持久化层

管理 4 张表：
- workflows: 工作流主表
- workflow_events: 事件日志表
- papers: 论文索引表
- reports: 报告索引表
"""
import sqlite3
import json
from datetime import datetime
from typing import Optional, List, Dict, Any
from dataclasses import dataclass
from pathlib import Path


@dataclass
class WorkflowRecord:
    """工作流记录"""
    id: str
    query: str
    year_range: Optional[str] = None
    max_papers: int = 10
    source: str = "arxiv"
    status: str = "pending"  # pending/running/completed/failed/cancelled
    current_stage: Optional[str] = None
    progress: int = 0
    message: str = ""
    papers_found: int = 0
    result: Optional[dict] = None
    error: Optional[str] = None
    created_at: str = ""
    updated_at: str = ""
    completed_at: Optional[str] = None
    rewritten_query: Optional[str] = None  # LLM 提炼后的关键词


@dataclass
class WorkflowEventRecord:
    """工作流事件记录"""
    id: str
    workflow_id: str
    event_type: str
    stage: Optional[str]
    status: Optional[str]
    progress: int
    message: str
    data: Optional[dict]
    timestamp: str


@dataclass
class PaperRecord:
    """论文记录"""
    paper_id: str
    workflow_id: str
    title: str
    authors: str  # JSON array
    abstract: str
    year: Optional[str]
    source: str
    pdf_path: Optional[str]
    download_status: str
    created_at: str


@dataclass
class ReportRecord:
    """报告记录"""
    report_id: str
    workflow_id: str
    content_markdown: str
    file_path: Optional[str]
    word_count: int
    created_at: str


class WorkflowStore:
    """
    工作流存储管理器
    """

    def __init__(self, db_path: Optional[Path] = None):
        if db_path is None:
            # 默认在 output 目录下创建
            project_root = Path(__file__).parent.parent.parent.parent
            db_path = project_root / "output" / "workflow_store.db"

        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self) -> None:
        """初始化数据库表"""
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()

        # 工作流主表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS workflows (
                id TEXT PRIMARY KEY,
                query TEXT NOT NULL,
                rewritten_query TEXT,
                year_range TEXT,
                max_papers INTEGER DEFAULT 10,
                source TEXT DEFAULT 'arxiv',
                status TEXT NOT NULL,
                current_stage TEXT,
                progress INTEGER DEFAULT 0,
                message TEXT,
                papers_found INTEGER DEFAULT 0,
                result TEXT,
                error TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                completed_at TIMESTAMP
            )
        """)

        # 工作流事件表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS workflow_events (
                id TEXT PRIMARY KEY,
                workflow_id TEXT NOT NULL,
                event_type TEXT NOT NULL,
                stage TEXT,
                status TEXT,
                progress INTEGER,
                message TEXT,
                data TEXT,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (workflow_id) REFERENCES workflows(id) ON DELETE CASCADE
            )
        """)

        # 论文索引表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS papers (
                paper_id TEXT PRIMARY KEY,
                workflow_id TEXT NOT NULL,
                title TEXT NOT NULL,
                authors TEXT,
                abstract TEXT,
                year TEXT,
                source TEXT,
                categories TEXT,
                venue TEXT,
                citations INTEGER,
                doi TEXT,
                url TEXT,
                pdf_path TEXT,
                download_status TEXT DEFAULT 'pending',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (workflow_id) REFERENCES workflows(id) ON DELETE CASCADE
            )
        """)

        # 报告索引表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS reports (
                report_id TEXT PRIMARY KEY,
                workflow_id TEXT NOT NULL,
                content_markdown TEXT,
                file_path TEXT,
                word_count INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (workflow_id) REFERENCES workflows(id) ON DELETE CASCADE
            )
        """)

        # 创建索引
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_workflow_status ON workflows(status)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_workflow_created ON workflows(created_at)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_event_workflow ON workflow_events(workflow_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_paper_workflow ON papers(workflow_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_paper_source ON papers(source)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_report_workflow ON reports(workflow_id)")

        # 启用 WAL 模式以提高并发性能
        cursor.execute("PRAGMA journal_mode=WAL")

        # 兼容旧版本数据库：补齐新增字段
        self._migrate_workflows_table(cursor)

        conn.commit()
        conn.close()

    def _migrate_workflows_table(self, cursor: sqlite3.Cursor) -> None:
        """兼容旧版 workflows 表结构"""
        cursor.execute("PRAGMA table_info(workflows)")
        columns = {row[1] for row in cursor.fetchall()}

        if "rewritten_query" not in columns:
            cursor.execute("ALTER TABLE workflows ADD COLUMN rewritten_query TEXT")

    def _get_connection(self) -> sqlite3.Connection:
        """获取数据库连接"""
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        return conn

    # ========== 工作流 CRUD ==========

    def create_workflow(self, workflow: WorkflowRecord) -> None:
        """创建工作流记录"""
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO workflows (
                id, query, rewritten_query, year_range, max_papers, source,
                status, current_stage, progress, message, papers_found,
                result, error, created_at, updated_at, completed_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            workflow.id,
            workflow.query,
            workflow.rewritten_query,
            workflow.year_range,
            workflow.max_papers,
            workflow.source,
            workflow.status,
            workflow.current_stage,
            workflow.progress,
            workflow.message,
            workflow.papers_found,
            json.dumps(workflow.result) if workflow.result else None,
            workflow.error,
            workflow.created_at,
            workflow.updated_at,
            workflow.completed_at,
        ))

        conn.commit()
        conn.close()

    def get_workflow(self, workflow_id: str) -> Optional[WorkflowRecord]:
        """获取工作流记录"""
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM workflows WHERE id = ?", (workflow_id,))
        row = cursor.fetchone()
        conn.close()

        if row:
            return self._row_to_workflow(row)
        return None

    def update_workflow(self, workflow: WorkflowRecord) -> None:
        """更新工作流记录"""
        workflow.updated_at = datetime.now().isoformat()

        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            UPDATE workflows SET
                status = ?,
                current_stage = ?,
                progress = ?,
                message = ?,
                papers_found = ?,
                result = ?,
                error = ?,
                updated_at = ?,
                completed_at = ?
            WHERE id = ?
        """, (
            workflow.status,
            workflow.current_stage,
            workflow.progress,
            workflow.message,
            workflow.papers_found,
            json.dumps(workflow.result) if workflow.result else None,
            workflow.error,
            workflow.updated_at,
            workflow.completed_at,
            workflow.id,
        ))

        conn.commit()
        conn.close()

    def update_workflow_status(
        self,
        workflow_id: str,
        status: str,
        current_stage: Optional[str] = None,
        progress: Optional[int] = None,
        message: Optional[str] = None,
        papers_found: Optional[int] = None,
        error: Optional[str] = None,
    ) -> None:
        """快速更新工作流状态"""
        conn = self._get_connection()
        cursor = conn.cursor()

        updates = ["status = ?", "updated_at = ?"]
        values = [status, datetime.now().isoformat()]

        if current_stage is not None:
            updates.append("current_stage = ?")
            values.append(current_stage)

        if progress is not None:
            updates.append("progress = ?")
            values.append(progress)

        if message is not None:
            updates.append("message = ?")
            values.append(message)

        if papers_found is not None:
            updates.append("papers_found = ?")
            values.append(papers_found)

        if error is not None:
            updates.append("error = ?")
            values.append(error)

        if status in ("completed", "failed", "cancelled"):
            updates.append("completed_at = ?")
            values.append(datetime.now().isoformat())

        values.append(workflow_id)

        cursor.execute(f"""
            UPDATE workflows SET
                {', '.join(updates)}
            WHERE id = ?
        """, values)

        conn.commit()
        conn.close()

    def update_rewritten_query(self, workflow_id: str, rewritten_query: str) -> None:
        """更新 LLM 重写后的查询"""
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            UPDATE workflows SET
                rewritten_query = ?,
                updated_at = ?
            WHERE id = ?
        """, (rewritten_query, datetime.now().isoformat(), workflow_id))

        conn.commit()
        conn.close()

    def get_workflows(
        self,
        status: Optional[str] = None,
        limit: int = 20,
        offset: int = 0,
    ) -> List[WorkflowRecord]:
        """获取工作流列表（按创建时间倒序）"""
        conn = self._get_connection()
        cursor = conn.cursor()

        if status:
            cursor.execute("""
                SELECT * FROM workflows
                WHERE status = ?
                ORDER BY created_at DESC
                LIMIT ? OFFSET ?
            """, (status, limit, offset))
        else:
            cursor.execute("""
                SELECT * FROM workflows
                ORDER BY created_at DESC
                LIMIT ? OFFSET ?
            """, (limit, offset))

        rows = cursor.fetchall()
        conn.close()

        return [self._row_to_workflow(row) for row in rows]

    def get_workflows_count(self, status: Optional[str] = None) -> int:
        """获取工作流总数"""
        conn = self._get_connection()
        cursor = conn.cursor()

        if status:
            cursor.execute("SELECT COUNT(*) FROM workflows WHERE status = ?", (status,))
        else:
            cursor.execute("SELECT COUNT(*) FROM workflows")

        count = cursor.fetchone()[0]
        conn.close()
        return count

    def delete_workflow(self, workflow_id: str) -> None:
        """删除工作流记录（级联删除相关事件、论文、报告）"""
        conn = self._get_connection()
        cursor = conn.cursor()

        # 先删除外键关联的记录
        cursor.execute("DELETE FROM workflow_events WHERE workflow_id = ?", (workflow_id,))
        cursor.execute("DELETE FROM papers WHERE workflow_id = ?", (workflow_id,))
        cursor.execute("DELETE FROM reports WHERE workflow_id = ?", (workflow_id,))
        cursor.execute("DELETE FROM workflows WHERE id = ?", (workflow_id,))

        conn.commit()
        conn.close()

    # ========== 工作流事件 ==========

    def add_event(self, event: WorkflowEventRecord) -> None:
        """添加工作流事件"""
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO workflow_events (
                id, workflow_id, event_type, stage, status, progress, message, data, timestamp
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            event.id,
            event.workflow_id,
            event.event_type,
            event.stage,
            event.status,
            event.progress,
            event.message,
            json.dumps(event.data) if event.data else None,
            event.timestamp,
        ))

        conn.commit()
        conn.close()

    def get_events(self, workflow_id: str, limit: int = 100) -> List[WorkflowEventRecord]:
        """获取工作流事件列表（按时间倒序）"""
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT * FROM workflow_events
            WHERE workflow_id = ?
            ORDER BY timestamp DESC
            LIMIT ?
        """, (workflow_id, limit))

        rows = cursor.fetchall()
        conn.close()

        return [self._row_to_event(row) for row in rows]

    # ========== 论文管理 ==========

    def add_paper(self, paper: PaperRecord) -> None:
        """添加论文记录"""
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            INSERT OR REPLACE INTO papers (
                paper_id, workflow_id, title, authors, abstract, year, source,
                categories, venue, citations, doi, url, pdf_path, download_status, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            paper.paper_id,
            paper.workflow_id,
            paper.title,
            paper.authors,  # JSON string
            paper.abstract,
            paper.year,
            paper.source,
            paper.categories if hasattr(paper, 'categories') else None,
            paper.venue if hasattr(paper, 'venue') else None,
            paper.citations if hasattr(paper, 'citations') else None,
            paper.doi if hasattr(paper, 'doi') else None,
            paper.url if hasattr(paper, 'url') else None,
            paper.pdf_path,
            paper.download_status,
            paper.created_at,
        ))

        conn.commit()
        conn.close()

    def get_papers_by_workflow(
        self,
        workflow_id: str,
        limit: int = 100,
        offset: int = 0,
    ) -> List[PaperRecord]:
        """获取工作流的论文列表"""
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT * FROM papers
            WHERE workflow_id = ?
            ORDER BY created_at DESC
            LIMIT ? OFFSET ?
        """, (workflow_id, limit, offset))

        rows = cursor.fetchall()
        conn.close()

        return [self._row_to_paper(row) for row in rows]

    def get_paper(self, paper_id: str) -> Optional[PaperRecord]:
        """获取论文详情"""
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM papers WHERE paper_id = ?", (paper_id,))
        row = cursor.fetchone()
        conn.close()

        if row:
            return self._row_to_paper(row)
        return None

    def update_paper(self, paper_id: str, **updates: Any) -> None:
        """更新论文记录"""
        if not updates:
            return

        allowed_fields = {
            "workflow_id",
            "title",
            "authors",
            "abstract",
            "year",
            "source",
            "pdf_path",
            "download_status",
        }
        valid_updates = {key: value for key, value in updates.items() if key in allowed_fields}
        if not valid_updates:
            return

        conn = self._get_connection()
        cursor = conn.cursor()

        set_clause = ", ".join(f"{field} = ?" for field in valid_updates)
        values = list(valid_updates.values()) + [paper_id]

        cursor.execute(
            f"UPDATE papers SET {set_clause} WHERE paper_id = ?",
            values,
        )

        conn.commit()
        conn.close()

    def get_all_papers(
        self,
        workflow_id: Optional[str] = None,
        source: Optional[str] = None,
        year_from: Optional[int] = None,
        year_to: Optional[int] = None,
        search_query: Optional[str] = None,
        limit: int = 20,
        offset: int = 0,
    ) -> List[PaperRecord]:
        """获取所有论文（支持过滤）"""
        conn = self._get_connection()
        cursor = conn.cursor()

        conditions = []
        values = []

        if workflow_id:
            conditions.append("workflow_id = ?")
            values.append(workflow_id)

        if source:
            conditions.append("source = ?")
            values.append(source)

        if year_from:
            conditions.append("year >= ?")
            values.append(str(year_from))

        if year_to:
            conditions.append("year <= ?")
            values.append(str(year_to))

        if search_query:
            conditions.append("title LIKE ?")
            values.append(f"%{search_query}%")

        where_clause = " WHERE " + " AND ".join(conditions) if conditions else ""

        cursor.execute(f"""
            SELECT * FROM papers
            {where_clause}
            ORDER BY created_at DESC
            LIMIT ? OFFSET ?
        """, values + [limit, offset])

        rows = cursor.fetchall()
        conn.close()

        return [self._row_to_paper(row) for row in rows]

    def get_papers_count(
        self,
        workflow_id: Optional[str] = None,
        source: Optional[str] = None,
    ) -> int:
        """获取论文总数"""
        conn = self._get_connection()
        cursor = conn.cursor()

        conditions = []
        values = []

        if workflow_id:
            conditions.append("workflow_id = ?")
            values.append(workflow_id)

        if source:
            conditions.append("source = ?")
            values.append(source)

        where_clause = " WHERE " + " AND ".join(conditions) if conditions else ""

        cursor.execute(f"SELECT COUNT(*) FROM papers {where_clause}", values)
        count = cursor.fetchone()[0]
        conn.close()
        return count

    def delete_papers(self, paper_ids: List[str]) -> int:
        """批量删除论文记录"""
        if not paper_ids:
            return 0

        conn = self._get_connection()
        cursor = conn.cursor()
        placeholders = ",".join("?" for _ in paper_ids)
        cursor.execute(
            f"DELETE FROM papers WHERE paper_id IN ({placeholders})",
            paper_ids,
        )
        deleted = cursor.rowcount
        conn.commit()
        conn.close()
        return deleted

    # ========== 报告管理 ==========

    def add_report(self, report: ReportRecord) -> None:
        """添加报告记录"""
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO reports (
                report_id, workflow_id, content_markdown, file_path, word_count, created_at
            ) VALUES (?, ?, ?, ?, ?, ?)
        """, (
            report.report_id,
            report.workflow_id,
            report.content_markdown,
            report.file_path,
            report.word_count,
            report.created_at,
        ))

        conn.commit()
        conn.close()

    def get_report(self, report_id: str) -> Optional[ReportRecord]:
        """获取报告详情"""
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM reports WHERE report_id = ?", (report_id,))
        row = cursor.fetchone()
        conn.close()

        if row:
            return self._row_to_report(row)
        return None

    def get_report_by_workflow(self, workflow_id: str) -> Optional[ReportRecord]:
        """根据工作流 ID 获取报告"""
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT * FROM reports
            WHERE workflow_id = ?
            ORDER BY created_at DESC
            LIMIT 1
        """, (workflow_id,))

        row = cursor.fetchone()
        conn.close()

        if row:
            return self._row_to_report(row)
        return None

    def get_all_reports(self, limit: int = 20, offset: int = 0) -> List[ReportRecord]:
        """获取所有报告列表"""
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT * FROM reports
            ORDER BY created_at DESC
            LIMIT ? OFFSET ?
        """, (limit, offset))

        rows = cursor.fetchall()
        conn.close()

        return [self._row_to_report(row) for row in rows]

    def get_reports_count(self) -> int:
        """获取报告总数"""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM reports")
        count = cursor.fetchone()[0]
        conn.close()
        return count

    def delete_reports(self, report_ids: List[str]) -> int:
        """批量删除报告记录"""
        if not report_ids:
            return 0

        conn = self._get_connection()
        cursor = conn.cursor()
        placeholders = ",".join("?" for _ in report_ids)
        cursor.execute(
            f"DELETE FROM reports WHERE report_id IN ({placeholders})",
            report_ids,
        )
        deleted = cursor.rowcount
        conn.commit()
        conn.close()
        return deleted

    # ========== Helper 方法 ==========

    def _row_to_workflow(self, row: sqlite3.Row) -> WorkflowRecord:
        """将数据库行转换为 WorkflowRecord"""
        return WorkflowRecord(
            id=row["id"],
            query=row["query"],
            rewritten_query=row["rewritten_query"],
            year_range=row["year_range"],
            max_papers=row["max_papers"],
            source=row["source"],
            status=row["status"],
            current_stage=row["current_stage"],
            progress=row["progress"],
            message=row["message"],
            papers_found=row["papers_found"],
            result=json.loads(row["result"]) if row["result"] else None,
            error=row["error"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            completed_at=row["completed_at"],
        )

    def _row_to_event(self, row: sqlite3.Row) -> WorkflowEventRecord:
        """将数据库行转换为 WorkflowEventRecord"""
        return WorkflowEventRecord(
            id=row["id"],
            workflow_id=row["workflow_id"],
            event_type=row["event_type"],
            stage=row["stage"],
            status=row["status"],
            progress=row["progress"],
            message=row["message"],
            data=json.loads(row["data"]) if row["data"] else None,
            timestamp=row["timestamp"],
        )

    def _row_to_paper(self, row: sqlite3.Row) -> PaperRecord:
        """将数据库行转换为 PaperRecord"""
        return PaperRecord(
            paper_id=row["paper_id"],
            workflow_id=row["workflow_id"],
            title=row["title"],
            authors=row["authors"],
            abstract=row["abstract"] or "",
            year=row["year"],
            source=row["source"],
            pdf_path=row["pdf_path"],
            download_status=row["download_status"],
            created_at=row["created_at"],
        )

    def _row_to_report(self, row: sqlite3.Row) -> ReportRecord:
        """将数据库行转换为 ReportRecord"""
        return ReportRecord(
            report_id=row["report_id"],
            workflow_id=row["workflow_id"],
            content_markdown=row["content_markdown"],
            file_path=row["file_path"],
            word_count=row["word_count"],
            created_at=row["created_at"],
        )

    def __repr__(self) -> str:
        return f"WorkflowStore(db={self.db_path})"
