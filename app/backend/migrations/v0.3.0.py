from __future__ import annotations
"""v0.3.0 初始迁移 - 引入迁移框架

为所有现有数据库添加 _migrations 表，记录当前版本。
不对现有表结构做任何修改。
"""


def upgrade(root_dir):
    """升级"""
    import sqlite3
    from datetime import datetime

    data_dir = root_dir / "data"
    migration_sql = """
    CREATE TABLE IF NOT EXISTS _migrations (
        version TEXT PRIMARY KEY,
        applied_at TEXT NOT NULL,
        note TEXT DEFAULT ''
    )
    """

    for db_name in ["assistant.db", "memory.db", "knowledge.db", "file_index.db"]:
        db_path = data_dir / db_name
        if db_path.exists():
            conn = sqlite3.connect(str(db_path))
            conn.execute(migration_sql)
            conn.execute(
                "INSERT OR IGNORE INTO _migrations (version, applied_at, note) VALUES (?,?,?)",
                ("v0.3.0", datetime.now().isoformat(), "initial migration framework")
            )
            conn.commit()
            conn.close()
            print(f"  ✅ {db_name}")


def downgrade(root_dir):
    """回滚（空操作，初始迁移不需要回滚）"""
    pass
