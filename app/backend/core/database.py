from __future__ import annotations
"""达梦数据库连接管理"""
import logging
from typing import List, Optional

from config.settings import settings

logger = logging.getLogger(__name__)


class DMDatabase:
    """达梦数据库连接管理，支持主备切换"""

    def __init__(self):
        self.host = settings.DM_HOST
        self.standby_host = settings.DM_STANDBY_HOST
        self.port = settings.DM_PORT
        self.username = settings.DM_USERNAME
        self.password = settings.DM_PASSWORD
        self.database = settings.DM_DATABASE
        self._dmPython = None

    @property
    def dmPython(self):
        """延迟导入dmPython（离线环境可能未安装）"""
        if self._dmPython is None:
            try:
                import dmPython
                self._dmPython = dmPython
            except ImportError:
                raise ImportError(
                    "dmPython未安装，请先安装达梦数据库驱动。"
                    "开发阶段可跳过，不影响其他模块使用。"
                )
        return self._dmPython

    def connect(self, host: str = None):
        """连接达梦数据库"""
        target_host = host or self.host
        try:
            conn = self.dmPython.connect(
                user=self.username,
                password=self.password,
                server=target_host,
                port=self.port,
            )
            # 切换到指定schema
            cursor = conn.cursor()
            cursor.execute(f"SET SCHEMA {self.database}")
            conn.commit()
            logger.info(f"达梦数据库连接成功: {target_host}:{self.port}")
            return conn
        except Exception as e:
            logger.error(f"达梦数据库连接失败: {target_host}:{self.port}, 错误: {e}")
            return None

    def get_connection(self):
        """获取连接，主库优先，失败切备库"""
        conn = self.connect(self.host)
        if conn is None and self.standby_host:
            logger.info(f"主库不可用，尝试备库: {self.standby_host}")
            conn = self.connect(self.standby_host)
        if conn is None:
            raise ConnectionError("达梦数据库主备库均不可用")
        return conn

    def execute_query(self, sql: str, params: dict = None) -> List[dict]:
        """执行查询，返回字典列表"""
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(sql, params or {})
            columns = [desc[0] for desc in cursor.description]
            rows = cursor.fetchall()
            return [dict(zip(columns, row)) for row in rows]
        finally:
            conn.close()

    def test_connection(self) -> dict:
        """测试数据库连接"""
        result = {"primary": False, "standby": False}
        conn = self.connect(self.host)
        if conn:
            result["primary"] = True
            conn.close()
        if self.standby_host:
            conn = self.connect(self.standby_host)
            if conn:
                result["standby"] = True
                conn.close()
        return result


# 全局单例
dm_database = DMDatabase()
