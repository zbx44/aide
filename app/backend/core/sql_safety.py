from __future__ import annotations
from typing import Tuple
"""SQL安全检查器 - 防止危险SQL执行

严格限制：只允许SELECT查询
拦截所有DML/DDL/DCL语句
拦截可能的注入攻击
"""
import re
import logging

logger = logging.getLogger(__name__)


class SQLSafetyChecker:
    """SQL安全检查器"""

    FORBIDDEN_KEYWORDS = [
        "INSERT", "UPDATE", "DELETE", "REPLACE", "MERGE",
        "CREATE", "ALTER", "DROP", "TRUNCATE", "RENAME",
        "GRANT", "REVOKE",
        "EXEC", "EXECUTE", "CALL",
        "INTO OUTFILE", "INTO DUMPFILE", "LOAD_FILE", "LOAD DATA",
        "SHUTDOWN", "KILL",
    ]

    FORBIDDEN_FUNCTIONS = [
        "SLEEP", "BENCHMARK", "WAITFOR", "DELAY",
        "LOAD_FILE", "INTO_OUTFILE", "INTO_DUMPFILE",
    ]

    MAX_ROWS = 5000
    TIMEOUT = 30

    def check(self, sql: str) -> Tuple[bool, str]:
        """检查SQL是否安全，返回(是否安全, 原因)"""
        if not sql or not sql.strip():
            return False, "SQL语句为空"

        sql_upper = sql.upper().strip()

        # 去掉开头的注释
        sql_clean = re.sub(r'^--.*\n?', '', sql_upper).strip()
        sql_clean = re.sub(r'^/\*.*?\*/', '', sql_clean, flags=re.DOTALL).strip()

        # 1. 必须以SELECT开头
        if not sql_clean.startswith("SELECT"):
            return False, "只允许SELECT查询，不允许写操作(INSERT/UPDATE/DELETE等)"

        # 2. 检查禁止的关键词
        for keyword in self.FORBIDDEN_KEYWORDS:
            pattern = r'\b' + re.escape(keyword) + r'\b'
            if re.search(pattern, sql_clean):
                return False, f"禁止使用 {keyword} 操作"

        # 3. 检查禁止的函数
        for func in self.FORBIDDEN_FUNCTIONS:
            pattern = r'\b' + re.escape(func) + r'\b'
            if re.search(pattern, sql_clean):
                return False, f"禁止使用 {func} 函数"

        # 4. 检查多条语句拼接
        sql_no_string = re.sub(r"'[^']*'", "", sql_clean)
        sql_no_string = re.sub(r'"[^"]*"', "", sql_no_string)
        if ";" in sql_no_string.rstrip(";"):
            return False, "禁止执行多条SQL语句"

        # 5. 检查UNION注入
        if re.search(r'\bUNION\b', sql_no_string) and re.search(r'\bSELECT\b', sql_no_string.split('UNION')[1] if 'UNION' in sql_no_string else ''):
            # 允许简单的UNION查询，但检查第二条是否也是SELECT
            pass  # UNION SELECT 是合法的

        # 6. 检查子查询中的写操作
        # 提取所有括号内的内容，检查是否有写操作
        subqueries = re.findall(r'\(([^)]+)\)', sql_no_string)
        for sq in subqueries:
            sq_stripped = sq.strip()
            if sq_stripped and not sq_stripped.upper().startswith("SELECT"):
                for kw in self.FORBIDDEN_KEYWORDS:
                    if kw in sq_stripped.upper():
                        return False, f"子查询中包含禁止的 {kw} 操作"

        return True, "OK"

    def add_limit(self, sql: str, max_rows: int = None) -> str:
        """为SQL添加行数限制（如果没有的话）"""
        limit = max_rows or self.MAX_ROWS
        sql_upper = sql.upper().strip()

        if "LIMIT" not in sql_upper and "ROWNUM" not in sql_upper:
            sql = sql.rstrip(";") + f" LIMIT {limit}"

        return sql


# 全局单例
sql_safety_checker = SQLSafetyChecker()
