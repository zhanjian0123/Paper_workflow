#!/usr/bin/env python3
"""
数据库迁移脚本：添加 rewritten_query 字段到 workflows 表

使用方法:
    python scripts/migrate_add_rewritten_query.py
"""

import sqlite3
from pathlib import Path

def migrate():
    """执行数据库迁移"""
    # 数据库路径
    project_root = Path(__file__).parent.parent
    db_path = project_root / "output" / "workflow_store.db"

    if not db_path.exists():
        print(f"数据库不存在：{db_path}")
        print("首次运行时会自动创建，无需迁移")
        return

    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()

    # 检查字段是否存在
    cursor.execute("PRAGMA table_info(workflows)")
    columns = [col[1] for col in cursor.fetchall()]

    if "rewritten_query" in columns:
        print("✅ rewritten_query 字段已存在，无需迁移")
        conn.close()
        return

    # 添加字段
    try:
        cursor.execute("ALTER TABLE workflows ADD COLUMN rewritten_query TEXT")
        conn.commit()
        print("✅ 成功添加 rewritten_query 字段")
    except sqlite3.OperationalError as e:
        print(f"❌ 迁移失败：{e}")
    finally:
        conn.close()

if __name__ == "__main__":
    migrate()
