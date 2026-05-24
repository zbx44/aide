from __future__ import annotations
"""AIDE 数据库迁移框架

每次升级涉及的数据库变更（新表、新字段、索引等）通过迁移脚本管理。
迁移脚本放在 migrations/ 目录下，按版本号命名。

迁移脚本示例（migrations/v0.3.0.py）：
    def upgrade(root_dir):
        db_path = root_dir / "data" / "assistant.db"
        conn = sqlite3.connect(db_path)
        conn.execute("ALTER TABLE ...")
        conn.commit()
        conn.close()

    def downgrade(root_dir):
        # 可选的回滚逻辑
        pass
"""
import importlib.util
import logging
import sqlite3
import sys
from pathlib import Path
from typing import List, Optional

logger = logging.getLogger(__name__)

# 迁移记录表
MIGRATION_TABLE = """
CREATE TABLE IF NOT EXISTS _migrations (
    version TEXT PRIMARY KEY,
    applied_at TEXT NOT NULL,
    note TEXT DEFAULT ''
)
"""


class MigrationRunner:
    """数据库迁移执行器"""

    def __init__(self, root_dir: str = None):
        if root_dir:
            self.root_dir = Path(root_dir)
        else:
            env_root = __import__("os").environ.get("AIDE_ROOT")
            self.root_dir = Path(env_root) if env_root else Path(__file__).parent.parent.parent.parent

        self.data_dir = self.root_dir / "data"
        self.migrations_dir = self.root_dir / "app" / "backend" / "migrations"

    def _get_db_paths(self) -> List[Path]:
        """获取所有需要迁移的数据库路径"""
        paths = []
        for db_name in ["assistant.db", "memory.db", "knowledge.db", "file_index.db"]:
            db_path = self.data_dir / db_name
            if db_path.exists():
                paths.append(db_path)
        return paths

    def _ensure_migration_table(self, db_path: Path):
        """确保迁移记录表存在"""
        conn = sqlite3.connect(str(db_path))
        conn.execute(MIGRATION_TABLE)
        conn.commit()
        conn.close()

    def _get_applied_versions(self, db_path: Path) -> set:
        """获取已应用的迁移版本"""
        self._ensure_migration_table(db_path)
        conn = sqlite3.connect(str(db_path))
        rows = conn.execute("SELECT version FROM _migrations").fetchall()
        conn.close()
        return {row[0] for row in rows}

    def _record_migration(self, db_path: Path, version: str, note: str = ""):
        """记录已应用的迁移"""
        conn = sqlite3.connect(str(db_path))
        from datetime import datetime
        conn.execute(
            "INSERT OR IGNORE INTO _migrations (version, applied_at, note) VALUES (?,?,?)",
            (version, datetime.now().isoformat(), note)
        )
        conn.commit()
        conn.close()

    def get_pending_migrations(self) -> List[str]:
        """获取待执行的迁移列表"""
        if not self.migrations_dir.exists():
            return []

        # 获取所有迁移脚本
        all_versions = []
        for f in sorted(self.migrations_dir.glob("v*.py")):
            all_versions.append(f.stem)  # e.g., "v0.3.0"

        # 获取已应用的版本（从主数据库）
        main_db = self.data_dir / "assistant.db"
        if main_db.exists():
            applied = self._get_applied_versions(main_db)
        else:
            applied = set()

        pending = [v for v in all_versions if v not in applied]
        return pending

    def run_pending(self) -> dict:
        """执行所有待执行的迁移

        Returns:
            结果dict
        """
        pending = self.get_pending_migrations()
        if not pending:
            logger.info("没有待执行的数据库迁移")
            return {"applied": [], "errors": []}

        logger.info(f"待执行的迁移: {pending}")
        applied = []
        errors = []

        for version in pending:
            script_path = self.migrations_dir / f"{version}.py"
            if not script_path.exists():
                errors.append(f"{version}: 迁移脚本不存在")
                continue

            try:
                result = self._run_single_migration(version, script_path)
                if result:
                    applied.append(version)
                else:
                    errors.append(f"{version}: 迁移返回失败")
            except Exception as e:
                logger.error(f"迁移 {version} 失败: {e}")
                errors.append(f"{version}: {e}")
                break  # 迁移失败则停止

        return {"applied": applied, "errors": errors}

    def _run_single_migration(self, version: str, script_path: Path) -> bool:
        """执行单个迁移脚本"""
        logger.info(f"执行迁移: {version}")

        # 动态加载迁移脚本
        spec = importlib.util.spec_from_file_location(f"migration_{version}", str(script_path))
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        # 执行upgrade函数
        if hasattr(module, "upgrade"):
            module.upgrade(self.root_dir)
        else:
            logger.warning(f"迁移脚本 {version} 没有 upgrade() 函数")
            return False

        # 记录到所有数据库
        for db_path in self._get_db_paths():
            self._record_migration(db_path, version, note="auto upgrade")

        logger.info(f"迁移完成: {version}")
        return True


# ===== 初始迁移（v0.3.0） =====
# 这是第一次引入迁移框架，为所有现有数据库添加 _migrations 表

def initial_migration_v030(root_dir: Path):
    """v0.3.0 初始迁移：为所有数据库添加迁移记录表"""
    data_dir = root_dir / "data"
    for db_name in ["assistant.db", "memory.db", "knowledge.db", "file_index.db"]:
        db_path = data_dir / db_name
        if db_path.exists():
            conn = sqlite3.connect(str(db_path))
            conn.execute(MIGRATION_TABLE)
            conn.execute(
                "INSERT OR IGNORE INTO _migrations (version, applied_at, note) VALUES (?,?,?)",
                ("v0.3.0", __import__("datetime").datetime.now().isoformat(), "initial migration framework")
            )
            conn.commit()
            conn.close()
            logger.info(f"初始化迁移表: {db_name}")
