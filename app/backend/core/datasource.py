from __future__ import annotations
"""数据源管理 - 支持多个数据库连接配置

数据源配置存储在 data/datasources.json，支持：
- 达梦数据库(DM)
- MySQL
- PostgreSQL
- SQLite
"""
import json
import logging
import uuid
from pathlib import Path
from typing import List, Optional

from config.settings import settings

logger = logging.getLogger(__name__)

DATASOURCES_PATH = settings.DATA_DIR / "datasources.json"

# 数据源类型定义
DS_TYPES = {
    "dm": {"name": "达梦数据库", "port": 5236, "icon": "🗄️"},
    "mysql": {"name": "MySQL", "port": 3306, "icon": "🐬"},
    "postgresql": {"name": "PostgreSQL", "port": 5432, "icon": "🐘"},
    "sqlite": {"name": "SQLite", "port": 0, "icon": "📄"},
}


class DataSourceManager:
    """数据源管理器"""

    def __init__(self):
        self.datasources: List[dict] = []
        self._load()

    def _load(self):
        """加载数据源配置"""
        if not DATASOURCES_PATH.exists():
            # 首次运行，从settings迁移默认达梦配置
            default_ds = {
                "id": "dm-default",
                "name": "达梦主库",
                "type": "dm",
                "host": settings.DM_HOST,
                "standby_host": settings.DM_STANDBY_HOST,
                "port": settings.DM_PORT,
                "username": settings.DM_USERNAME,
                "password": settings.DM_PASSWORD,
                "database": settings.DM_DATABASE,
                "enabled": True,
            }
            self.datasources = [default_ds]
            self._save()
            logger.info(f"已创建默认数据源配置: {DATASOURCES_PATH}")
        else:
            try:
                with open(DATASOURCES_PATH, "r", encoding="utf-8") as f:
                    data = json.load(f)
                self.datasources = data.get("datasources", [])
                logger.info(f"加载了 {len(self.datasources)} 个数据源")
            except Exception as e:
                logger.error(f"加载数据源配置失败: {e}")
                self.datasources = []

    def _save(self):
        """保存数据源配置"""
        DATASOURCES_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(DATASOURCES_PATH, "w", encoding="utf-8") as f:
            json.dump({"datasources": self.datasources}, f, ensure_ascii=False, indent=2)

    def list_datasources(self) -> List[dict]:
        """列出所有数据源"""
        result = []
        for ds in self.datasources:
            info = {**ds}
            # 密码脱敏
            if info.get("password"):
                info["password"] = "***"
            result.append(info)
        return result

    def get_datasource(self, ds_id: str) -> Optional[dict]:
        """获取数据源（含密码）"""
        for ds in self.datasources:
            if ds["id"] == ds_id:
                return ds
        return None

    def add_datasource(self, ds_config: dict) -> dict:
        """添加数据源"""
        ds_id = ds_config.get("id") or str(uuid.uuid4())[:8]
        ds_config["id"] = ds_id
        ds_config.setdefault("enabled", True)

        # 设置默认端口
        ds_type = ds_config.get("type", "dm")
        if "port" not in ds_config or not ds_config["port"]:
            ds_config["port"] = DS_TYPES.get(ds_type, {}).get("port", 0)

        self.datasources.append(ds_config)
        self._save()
        logger.info(f"添加数据源: {ds_config.get('name')} ({ds_id})")
        return ds_config

    def update_datasource(self, ds_id: str, updates: dict) -> Optional[dict]:
        """更新数据源"""
        for ds in self.datasources:
            if ds["id"] == ds_id:
                # 不允许修改id和type
                updates.pop("id", None)
                # 密码特殊处理：***表示不修改
                if updates.get("password") == "***":
                    updates.pop("password")
                ds.update(updates)
                self._save()
                logger.info(f"更新数据源: {ds.get('name')} ({ds_id})")
                return ds
        return None

    def delete_datasource(self, ds_id: str) -> bool:
        """删除数据源"""
        before = len(self.datasources)
        self.datasources = [ds for ds in self.datasources if ds["id"] != ds_id]
        if len(self.datasources) < before:
            self._save()
            logger.info(f"删除数据源: {ds_id}")
            return True
        return False

    def test_connection(self, ds_id: str) -> dict:
        """测试数据源连接"""
        ds = self.get_datasource(ds_id)
        if not ds:
            return {"success": False, "message": f"数据源 {ds_id} 不存在"}

        ds_type = ds.get("type", "dm")

        if ds_type == "dm":
            return self._test_dm(ds)
        elif ds_type == "mysql":
            return self._test_mysql(ds)
        elif ds_type == "postgresql":
            return self._test_pg(ds)
        elif ds_type == "sqlite":
            return self._test_sqlite(ds)
        else:
            return {"success": False, "message": f"不支持的数据源类型: {ds_type}"}

    def _test_dm(self, ds: dict) -> dict:
        """测试达梦连接"""
        host = ds.get("host", "")
        port = ds.get("port", 5236)
        username = ds.get("username", "")
        password = ds.get("password", "")

        try:
            import dmPython
            conn = dmPython.connect(user=username, password=password, server=host, port=int(port))
            cursor = conn.cursor()
            cursor.execute("SELECT 1 FROM DUAL")
            cursor.fetchone()
            cursor.close()
            conn.close()
            return {"success": True, "message": f"连接成功！{host}:{port}"}
        except ImportError:
            import socket
            try:
                s = socket.create_connection((host, int(port)), timeout=5)
                s.close()
                return {"success": True, "message": f"端口可达（dmPython未安装，无法验证账号）{host}:{port}"}
            except Exception as e:
                return {"success": False, "message": f"连接失败: {e}"}
        except Exception as e:
            # 试备库
            standby = ds.get("standby_host", "")
            if standby:
                try:
                    import dmPython
                    conn = dmPython.connect(user=username, password=password, server=standby, port=int(port))
                    conn.close()
                    return {"success": True, "message": f"主库不可达，备库连接成功 {standby}:{port}"}
                except Exception:
                    pass
            return {"success": False, "message": f"连接失败: {e}"}

    def _test_mysql(self, ds: dict) -> dict:
        """测试MySQL连接"""
        try:
            import pymysql
            conn = pymysql.connect(
                host=ds.get("host", ""),
                port=int(ds.get("port", 3306)),
                user=ds.get("username", ""),
                password=ds.get("password", ""),
                database=ds.get("database", ""),
                connect_timeout=10,
            )
            conn.close()
            return {"success": True, "message": f"MySQL连接成功 {ds['host']}:{ds.get('port', 3306)}"}
        except ImportError:
            return {"success": False, "message": "pymysql未安装，请执行 pip install pymysql"}
        except Exception as e:
            return {"success": False, "message": f"MySQL连接失败: {e}"}

    def _test_pg(self, ds: dict) -> dict:
        """测试PostgreSQL连接"""
        try:
            import psycopg2
            conn = psycopg2.connect(
                host=ds.get("host", ""),
                port=int(ds.get("port", 5432)),
                user=ds.get("username", ""),
                password=ds.get("password", ""),
                dbname=ds.get("database", ""),
                connect_timeout=10,
            )
            conn.close()
            return {"success": True, "message": f"PostgreSQL连接成功 {ds['host']}:{ds.get('port', 5432)}"}
        except ImportError:
            return {"success": False, "message": "psycopg2未安装，请执行 pip install psycopg2-binary"}
        except Exception as e:
            return {"success": False, "message": f"PostgreSQL连接失败: {e}"}

    def _test_sqlite(self, ds: dict) -> dict:
        """测试SQLite连接"""
        import sqlite3
        db_path = ds.get("database", "")
        if not db_path:
            return {"success": False, "message": "请指定SQLite数据库文件路径"}
        try:
            conn = sqlite3.connect(db_path)
            conn.execute("SELECT 1")
            conn.close()
            return {"success": True, "message": f"SQLite连接成功: {db_path}"}
        except Exception as e:
            return {"success": False, "message": f"SQLite连接失败: {e}"}

    def execute_query(self, ds_id: str, sql: str, params: dict = None) -> List[dict]:
        """在指定数据源上执行查询"""
        ds = self.get_datasource(ds_id)
        if not ds:
            raise ValueError(f"数据源 {ds_id} 不存在")

        ds_type = ds.get("type", "dm")

        if ds_type == "dm":
            return self._query_dm(ds, sql, params)
        elif ds_type == "mysql":
            return self._query_mysql(ds, sql, params)
        elif ds_type == "postgresql":
            return self._query_pg(ds, sql, params)
        elif ds_type == "sqlite":
            return self._query_sqlite(ds, sql, params)
        else:
            raise ValueError(f"不支持的数据源类型: {ds_type}")

    def _query_dm(self, ds: dict, sql: str, params: dict = None) -> List[dict]:
        """达梦查询"""
        import dmPython
        host = ds["host"]
        password = ds.get("password", "")
        port = int(ds.get("port", 5236))

        conn = None
        try:
            conn = dmPython.connect(
                user=ds.get("username", ""),
                password=password,
                server=host,
                port=port,
            )
            database = ds.get("database", "")
            if database:
                cursor = conn.cursor()
                cursor.execute(f"SET SCHEMA {database}")
            cursor = conn.cursor()
            cursor.execute(sql, params or {})
            columns = [desc[0] for desc in cursor.description]
            rows = cursor.fetchall()
            return [dict(zip(columns, row)) for row in rows]
        except Exception as e:
            # 试备库
            standby = ds.get("standby_host", "")
            if standby and standby != host:
                try:
                    conn = dmPython.connect(
                        user=ds.get("username", ""),
                        password=password,
                        server=standby,
                        port=port,
                    )
                    database = ds.get("database", "")
                    if database:
                        cursor = conn.cursor()
                        cursor.execute(f"SET SCHEMA {database}")
                    cursor = conn.cursor()
                    cursor.execute(sql, params or {})
                    columns = [desc[0] for desc in cursor.description]
                    rows = cursor.fetchall()
                    return [dict(zip(columns, row)) for row in rows]
                except Exception:
                    pass
            raise
        finally:
            if conn:
                try:
                    conn.close()
                except Exception:
                    pass

    def _query_mysql(self, ds: dict, sql: str, params: dict = None) -> List[dict]:
        """MySQL查询"""
        import pymysql
        conn = pymysql.connect(
            host=ds["host"],
            port=int(ds.get("port", 3306)),
            user=ds.get("username", ""),
            password=ds.get("password", ""),
            database=ds.get("database", ""),
        )
        try:
            cursor = conn.cursor()
            cursor.execute(sql, params or {})
            columns = [desc[0] for desc in cursor.description]
            rows = cursor.fetchall()
            return [dict(zip(columns, row)) for row in rows]
        finally:
            conn.close()

    def _query_pg(self, ds: dict, sql: str, params: dict = None) -> List[dict]:
        """PostgreSQL查询"""
        import psycopg2
        import psycopg2.extras
        conn = psycopg2.connect(
            host=ds["host"],
            port=int(ds.get("port", 5432)),
            user=ds.get("username", ""),
            password=ds.get("password", ""),
            dbname=ds.get("database", ""),
        )
        try:
            cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            cursor.execute(sql, params or {})
            rows = cursor.fetchall()
            return [dict(row) for row in rows]
        finally:
            conn.close()

    def _query_sqlite(self, ds: dict, sql: str, params: dict = None) -> List[dict]:
        """SQLite查询"""
        import sqlite3
        conn = sqlite3.connect(ds.get("database", ""))
        conn.row_factory = sqlite3.Row
        try:
            cursor = conn.cursor()
            cursor.execute(sql, params or {})
            columns = [desc[0] for desc in cursor.description]
            rows = cursor.fetchall()
            return [dict(zip(columns, row)) for row in rows]
        finally:
            conn.close()


# 全局单例
ds_manager = DataSourceManager()
