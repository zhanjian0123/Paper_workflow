"""
输出目录索引同步

负责两类启动自愈：
1. 合并旧的 backend/output/workflow_store.db 到统一的项目根 output/workflow_store.db
2. 扫描 output 目录下已有的 PDF/Markdown 文件，回填 papers/reports 索引
"""
from __future__ import annotations

import logging
import re
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Iterable, Optional

from backend.app.core.config import Settings
from backend.app.services.workflow_store import (
    WorkflowRecord,
    PaperRecord,
    ReportRecord,
    WorkflowStore,
)

logger = logging.getLogger(__name__)

RECOVERED_PAPERS_WORKFLOW_ID = "wf_recovered_papers"
REPORT_FILE_PATTERN = re.compile(r"report_(\d{8})_(\d{6})\.md$")
ARXIV_PAPER_PATTERN = re.compile(r"^\d{4}\.\d{4,5}(v\d+)?$")
REPORT_MATCH_WINDOW_SECONDS = 15 * 60


def merge_legacy_workflow_store(primary_db_path: Path, legacy_db_path: Path) -> dict:
    """将旧路径数据库中的记录合并到统一主库中。"""
    primary_db_path = primary_db_path.resolve()
    legacy_db_path = legacy_db_path.resolve()

    stats = {
        "merged": False,
        "legacy_found": legacy_db_path.exists(),
        "legacy_path": str(legacy_db_path),
        "primary_path": str(primary_db_path),
    }

    if not legacy_db_path.exists() or legacy_db_path == primary_db_path:
        return stats

    primary_db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(primary_db_path))
    cursor = conn.cursor()

    try:
        cursor.execute("ATTACH DATABASE ? AS legacy_db", (str(legacy_db_path),))

        for table_name in ("workflows", "workflow_events", "papers", "reports"):
            columns = [
                row[1]
                for row in cursor.execute(f"PRAGMA table_info({table_name})").fetchall()
            ]
            column_sql = ", ".join(columns)
            cursor.execute(
                f"""
                INSERT OR IGNORE INTO {table_name} ({column_sql})
                SELECT {column_sql} FROM legacy_db.{table_name}
                """
            )

        conn.commit()
        stats["merged"] = True
    finally:
        cursor.execute("DETACH DATABASE legacy_db")
        conn.close()

    return stats


def sync_output_indexes(store: WorkflowStore, settings: Settings) -> dict:
    """扫描输出目录并回填数据库索引。"""
    roots = _existing_output_roots(settings)
    normalized_workflows = _normalize_recovered_workflows(store)

    report_stats = _sync_reports(store, roots)
    paper_stats = _sync_papers(store, roots)

    return {
        "roots": [str(root) for root in roots],
        "normalized_workflows": normalized_workflows,
        "reports_indexed": report_stats["indexed"],
        "reports_matched": report_stats["matched"],
        "reports_recovered": report_stats["recovered"],
        "papers_indexed": paper_stats["indexed"],
        "papers_recovered": paper_stats["recovered"],
    }


def _existing_output_roots(settings: Settings) -> list[Path]:
    roots = []
    for root in (settings.output_dir_path, settings.legacy_output_dir_path):
        resolved = root.resolve()
        if resolved.exists() and resolved not in roots:
            roots.append(resolved)
    return roots


def _sync_reports(store: WorkflowStore, roots: Iterable[Path]) -> dict:
    existing_reports = store.get_all_reports(limit=10000, offset=0)
    indexed_paths = {
        _normalized_path(report.file_path): report
        for report in existing_reports
        if report.file_path
    }
    reports_by_workflow = {report.workflow_id: report for report in existing_reports}

    completed_workflows = sorted(
        store.get_workflows(status="completed", limit=10000, offset=0),
        key=lambda workflow: _parse_iso_datetime(workflow.completed_at or workflow.created_at)
        or datetime.min,
    )
    available_workflows = [
        workflow for workflow in completed_workflows if workflow.id not in reports_by_workflow
    ]

    report_files = sorted(
        {
            report_file.resolve()
            for root in roots
            for report_file in (root / "reports").glob("*.md")
            if report_file.is_file()
        },
        key=lambda path: path.stat().st_mtime,
    )

    indexed = 0
    matched = 0
    recovered = 0

    for report_file in report_files:
        normalized = _normalized_path(report_file)
        if normalized in indexed_paths:
            continue

        recovered_report_id = f"rpt_recovered_{report_file.stem[-16:]}"
        existing_report = store.get_report(recovered_report_id)
        if existing_report:
            updates = {}
            if _normalized_path(existing_report.file_path) != normalized:
                updates["file_path"] = str(report_file)
            if not existing_report.content_markdown:
                updates["content_markdown"] = report_file.read_text(
                    encoding="utf-8",
                    errors="ignore",
                )
            if updates:
                store.update_report(recovered_report_id, **updates)
            indexed_paths[normalized] = store.get_report(recovered_report_id) or existing_report
            continue

        report_content = report_file.read_text(encoding="utf-8", errors="ignore")
        timestamp = _extract_report_timestamp(report_file) or datetime.fromtimestamp(
            report_file.stat().st_mtime
        )
        workflow = _match_workflow_by_timestamp(available_workflows, timestamp)

        if workflow:
            workflow_id = workflow.id
            available_workflows.remove(workflow)
            matched += 1
        else:
            workflow = _ensure_recovered_report_workflow(store, report_file, timestamp)
            workflow_id = workflow.id
            recovered += 1

        report = ReportRecord(
            report_id=recovered_report_id,
            workflow_id=workflow_id,
            content_markdown=report_content,
            file_path=str(report_file),
            word_count=len(report_content.split()),
            created_at=timestamp.isoformat(),
        )
        store.add_report(report)
        _attach_report_to_workflow(store, workflow_id, report.report_id, str(report_file))
        indexed += 1

    return {"indexed": indexed, "matched": matched, "recovered": recovered}


def _sync_papers(store: WorkflowStore, roots: Iterable[Path]) -> dict:
    existing_papers = store.get_all_papers(limit=10000, offset=0)
    indexed_paths = {
        _normalized_path(paper.pdf_path): paper
        for paper in existing_papers
        if paper.pdf_path
    }

    indexed = 0
    recovered = 0
    recovery_workflow: Optional[WorkflowRecord] = None

    paper_files = sorted(
        {
            paper_file.resolve()
            for root in roots
            for paper_file in (root / "papers").glob("*.pdf")
            if paper_file.is_file()
        },
        key=lambda path: path.stat().st_mtime,
    )

    for paper_file in paper_files:
        normalized = _normalized_path(paper_file)
        if normalized in indexed_paths:
            continue

        paper_id = paper_file.stem
        existing_record = store.get_paper(paper_id)
        if existing_record:
            store.update_paper(
                paper_id,
                pdf_path=str(paper_file),
                download_status="downloaded",
            )
            indexed += 1
            continue

        if recovery_workflow is None:
            recovery_workflow = _ensure_recovered_papers_workflow(store)

        created_at = datetime.fromtimestamp(paper_file.stat().st_mtime).isoformat()
        store.add_paper(
            PaperRecord(
                paper_id=paper_id,
                workflow_id=recovery_workflow.id,
                title=paper_id,
                authors="[]",
                abstract="",
                year=_infer_year_from_paper_id(paper_id),
                source="arxiv" if ARXIV_PAPER_PATTERN.match(paper_id) else "recovered_file",
                pdf_path=str(paper_file),
                download_status="downloaded",
                created_at=created_at,
            )
        )
        indexed += 1
        recovered += 1

    if recovery_workflow:
        _update_recovered_papers_workflow_summary(store, recovery_workflow.id)

    return {"indexed": indexed, "recovered": recovered}


def _match_workflow_by_timestamp(
    workflows: list[WorkflowRecord],
    file_timestamp: datetime,
) -> Optional[WorkflowRecord]:
    best_workflow = None
    best_delta = None

    for workflow in workflows:
        workflow_time = _parse_iso_datetime(workflow.completed_at or workflow.created_at)
        if workflow_time is None:
            continue

        delta = abs((workflow_time - file_timestamp).total_seconds())
        if delta > REPORT_MATCH_WINDOW_SECONDS:
            continue

        if best_delta is None or delta < best_delta:
            best_workflow = workflow
            best_delta = delta

    return best_workflow


def _normalize_recovered_workflows(store: WorkflowStore) -> int:
    """修正恢复工作流中的非标准 stage，避免 API 序列化失败。"""
    normalized = 0

    for workflow in store.get_workflows(limit=10000, offset=0):
        if not workflow.id.startswith("wf_recovered"):
            continue

        if workflow.current_stage is None:
            continue

        workflow.current_stage = None
        store.update_workflow(workflow)
        normalized += 1

    return normalized


def _ensure_recovered_papers_workflow(store: WorkflowStore) -> WorkflowRecord:
    workflow = store.get_workflow(RECOVERED_PAPERS_WORKFLOW_ID)
    if workflow:
        return workflow

    now = datetime.now().isoformat()
    workflow = WorkflowRecord(
        id=RECOVERED_PAPERS_WORKFLOW_ID,
        query="Recovered papers from output directory",
        year_range=None,
        max_papers=0,
        source="system",
        status="completed",
        current_stage=None,
        progress=100,
        message="Auto-indexed papers found on disk.",
        papers_found=0,
        result=None,
        error=None,
        created_at=now,
        updated_at=now,
        completed_at=now,
    )
    store.create_workflow(workflow)
    return workflow


def _ensure_recovered_report_workflow(
    store: WorkflowStore,
    report_file: Path,
    timestamp: datetime,
) -> WorkflowRecord:
    workflow_id = f"wf_recovered_{report_file.stem[-16:]}"
    workflow = store.get_workflow(workflow_id)
    if workflow:
        return workflow

    title = _extract_report_title(report_file) or report_file.stem
    workflow = WorkflowRecord(
        id=workflow_id,
        query=f"Recovered report: {title}",
        year_range=None,
        max_papers=0,
        source="system",
        status="completed",
        current_stage=None,
        progress=100,
        message="Auto-indexed report found on disk.",
        papers_found=0,
        result=None,
        error=None,
        created_at=timestamp.isoformat(),
        updated_at=timestamp.isoformat(),
        completed_at=timestamp.isoformat(),
    )
    store.create_workflow(workflow)
    return workflow


def _attach_report_to_workflow(
    store: WorkflowStore,
    workflow_id: str,
    report_id: str,
    file_path: str,
) -> None:
    workflow = store.get_workflow(workflow_id)
    if not workflow:
        return

    workflow.result = {
        **(workflow.result or {}),
        "report_id": report_id,
        "file_path": file_path,
    }
    store.update_workflow(workflow)


def _update_recovered_papers_workflow_summary(store: WorkflowStore, workflow_id: str) -> None:
    workflow = store.get_workflow(workflow_id)
    if not workflow:
        return

    papers_found = store.get_papers_count(workflow_id=workflow_id)
    workflow.papers_found = papers_found
    workflow.max_papers = papers_found
    workflow.message = f"Auto-indexed {papers_found} paper files from disk."
    store.update_workflow(workflow)


def _extract_report_timestamp(report_file: Path) -> Optional[datetime]:
    match = REPORT_FILE_PATTERN.match(report_file.name)
    if not match:
        return None

    try:
        return datetime.strptime("".join(match.groups()), "%Y%m%d%H%M%S")
    except ValueError:
        return None


def _extract_report_title(report_file: Path) -> str:
    try:
        first_line = report_file.read_text(encoding="utf-8", errors="ignore").splitlines()[0]
    except IndexError:
        return ""
    return first_line.lstrip("# ").strip()


def _parse_iso_datetime(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def _infer_year_from_paper_id(paper_id: str) -> Optional[str]:
    if ARXIV_PAPER_PATTERN.match(paper_id):
        return f"20{paper_id[:2]}"
    return None


def _normalized_path(path_value: Optional[str | Path]) -> str:
    if not path_value:
        return ""
    return str(Path(path_value).resolve())
