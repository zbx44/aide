from __future__ import annotations
"""Text2SQL引擎 - 自然语言转SQL查询

核心流程：
1. 获取数据库Schema（表名、字段、中文注释、关系）
2. 构建Prompt（Schema + 用户问题 + 达梦方言适配）
3. LLM生成SQL
4. SQL安全检查（只允许SELECT）
5. 执行SQL，返回结果
6. LLM自然语言解读 + 表格展示
"""
import json
import logging
import re
from typing import Optional

from config.settings import settings
from core.llm import llm_client
from core.database import dm_database

logger = logging.getLogger(__name__)

TEXT2SQL_SYSTEM_PROMPT = """你是达梦数据库(DM) SQL专家。根据用户的自然语言问题和数据库表结构，生成准确的SQL查询语句。

## 重要规则
1. 只生成 SELECT 查询语句，绝对不能生成 INSERT/UPDATE/DELETE/DROP 等写操作
2. 使用达梦数据库语法：日期函数用 CURRENT_DATE / SYSDATE，分页用 LIMIT 或 ROWNUM
3. 字符串用单引号，表名和字段名用双引号（如果含特殊字符）
4. 充分利用字段注释理解业务含义
5. 如果用户的问题模糊，按最合理的理解生成SQL
6. 给字段起有意义的中文别名（用 AS "中文名"）

## 输出格式
严格输出JSON，格式如下：
{
  "sql": "SELECT ... FROM ... WHERE ...",
  "explanation": "简要说明这个查询做了什么",
  "tables_used": ["用到的表名"]
}

不要输出其他内容，不要用代码块包裹。"""


class Text2SQLEngine:
    """自然语言转SQL引擎"""

    def __init__(self):
        self.schema_text = ""
        self._load_schema()

    def _load_schema(self):
        """加载数据库Schema描述"""
        schema_file = settings.CONFIG_DIR / "db_schema.yaml"
        if schema_file.exists():
            self._load_from_yaml(schema_file)
        else:
            logger.warning(f"未找到Schema文件: {schema_file}，Text2SQL功能受限")
            self.schema_text = "（未配置数据库表结构，请联系管理员）"

    def _load_from_yaml(self, schema_file):
        """从YAML文件加载Schema"""
        try:
            import yaml
            with open(schema_file, "r", encoding="utf-8") as f:
                schema = yaml.safe_load(f)

            if not schema or "tables" not in schema:
                self.schema_text = "（Schema文件格式错误）"
                return

            lines = []
            for table in schema.get("tables", []):
                table_name = table.get("name", "unknown")
                table_comment = table.get("comment", "")
                lines.append(f"\n表: {table_name}（{table_comment}）")
                lines.append("字段:")

                for col in table.get("columns", []):
                    col_name = col.get("name", "")
                    col_type = col.get("type", "")
                    col_comment = col.get("comment", "")
                    lines.append(f"  - {col_name} ({col_type}) — {col_comment}")

            # 表间关系
            relations = schema.get("relations", [])
            if relations:
                lines.append("\n表间关系:")
                for rel in relations:
                    lines.append(f"  - {rel.get('from', '')} → {rel.get('to', '')}（{rel.get('comment', '')}）")

            self.schema_text = "\n".join(lines)
            logger.info(f"加载Schema成功: {len(schema.get('tables', []))} 个表")

        except Exception as e:
            logger.error(f"加载Schema文件失败: {e}")
            self.schema_text = "（Schema加载失败）"

    def reload_schema(self):
        """重新加载Schema（管理员修改后调用）"""
        self._load_schema()

    def generate_sql(self, question: str) -> dict:
        """将自然语言问题转为SQL

        Args:
            question: 用户自然语言问题

        Returns:
            {
                "sql": "SELECT ...",
                "explanation": "查询说明",
                "tables_used": ["表名"],
                "raw_response": "LLM原始回复"
            }
        """
        if not self.schema_text or "未配置" in self.schema_text or "未找到" in self.schema_text:
            return {
                "sql": "",
                "explanation": "数据库表结构未配置，无法生成查询。请联系管理员配置 db_schema.yaml",
                "tables_used": [],
                "error": "schema_not_configured"
            }

        prompt = f"""## 数据库表结构

{self.schema_text}

## 用户问题
{question}

请生成SQL查询语句。"""

        messages = [
            {"role": "system", "content": TEXT2SQL_SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ]

        try:
            result = llm_client.chat_json(messages, temperature=0.2)

            sql = result.get("sql", "").strip()
            explanation = result.get("explanation", "")
            tables_used = result.get("tables_used", [])

            # 清理SQL：去掉可能的代码块包裹
            if sql.startswith("```"):
                sql = re.sub(r'^```\w*\n?', '', sql)
                sql = re.sub(r'\n?```$', '', sql)
                sql = sql.strip()

            return {
                "sql": sql,
                "explanation": explanation,
                "tables_used": tables_used,
            }

        except Exception as e:
            logger.error(f"Text2SQL生成失败: {e}")
            return {
                "sql": "",
                "explanation": f"生成SQL失败: {e}",
                "tables_used": [],
                "error": str(e)
            }

    def execute_query(self, sql: str, max_rows: int = 1000) -> dict:
        """执行SQL查询

        Args:
            sql: SQL查询语句
            max_rows: 最大返回行数

        Returns:
            {
                "columns": ["列名1", "列名2"],
                "rows": [["值1", "值2"], ...],
                "total": 行数,
                "error": null
            }
        """
        # 安全检查
        from core.sql_safety import sql_safety_checker
        is_safe, reason = sql_safety_checker.check(sql)
        if not is_safe:
            return {
                "columns": [],
                "rows": [],
                "total": 0,
                "error": f"SQL安全检查未通过: {reason}"
            }

        try:
            # 添加行数限制
            sql_upper = sql.upper().strip()
            if "LIMIT" not in sql_upper and "ROWNUM" not in sql_upper:
                sql = sql.rstrip(";") + f" LIMIT {max_rows}"

            # 执行查询
            rows = dm_database.execute_query(sql)

            if not rows:
                return {
                    "columns": [],
                    "rows": [],
                    "total": 0,
                    "error": None,
                }

            # 提取列名
            columns = list(rows[0].keys()) if rows else []

            # 转换为列表
            data_rows = []
            for row in rows[:max_rows]:
                data_rows.append([str(row.get(col, "")) for col in columns])

            return {
                "columns": columns,
                "rows": data_rows,
                "total": len(data_rows),
                "error": None,
            }

        except Exception as e:
            logger.error(f"SQL执行失败: {e}")
            return {
                "columns": [],
                "rows": [],
                "total": 0,
                "error": f"SQL执行失败: {e}"
            }

    def explain_result(self, question: str, query_result: dict) -> str:
        """用LLM解读查询结果

        Args:
            question: 用户的原始问题
            query_result: execute_query()的返回结果

        Returns:
            自然语言解读文本
        """
        if query_result.get("error"):
            return f"查询出错: {query_result['error']}"

        columns = query_result.get("columns", [])
        rows = query_result.get("rows", [])
        total = query_result.get("total", 0)

        if total == 0:
            return "查询结果为空，没有匹配的数据。"

        # 构建数据摘要（避免数据太多超过token限制）
        preview_rows = rows[:20]
        data_text = f"列: {', '.join(columns)}\n"
        for i, row in enumerate(preview_rows, 1):
            data_text += f"第{i}行: {', '.join(str(v) for v in row)}\n"
        if total > 20:
            data_text += f"... 还有 {total - 20} 行数据\n"

        prompt = f"""用户问：{question}

查询结果（共{total}条记录）：
{data_text}

请用中文简洁解读查询结果：
1. 直接回答用户的问题
2. 指出关键数据和趋势
3. 如果有异常值，重点指出
4. 给出简要建议（如适用）

用Markdown格式输出，包含表格展示关键数据。"""

        try:
            explanation = llm_client.chat([
                {"role": "system", "content": "你是数据分析专家，擅长解读数据并用简洁的语言回答问题。"},
                {"role": "user", "content": prompt},
            ], temperature=0.3)
            return explanation
        except Exception as e:
            logger.error(f"结果解读失败: {e}")
            # 降级：返回原始数据
            return f"查询到 {total} 条记录。\n列: {', '.join(columns)}"

    def query(self, question: str) -> dict:
        """完整的自然语言查询流程

        Args:
            question: 自然语言问题

        Returns:
            {
                "question": "原始问题",
                "sql": "生成的SQL",
                "explanation": "SQL说明",
                "columns": [...],
                "rows": [...],
                "total": 10,
                "interpretation": "自然语言解读",
                "error": null
            }
        """
        # 1. 生成SQL
        sql_result = self.generate_sql(question)

        if sql_result.get("error") or not sql_result.get("sql"):
            return {
                "question": question,
                "sql": "",
                "explanation": sql_result.get("explanation", "生成SQL失败"),
                "columns": [],
                "rows": [],
                "total": 0,
                "interpretation": "",
                "error": sql_result.get("error", "generate_failed")
            }

        sql = sql_result["sql"]

        # 2. 执行SQL
        query_result = self.execute_query(sql)

        # 3. 解读结果
        if query_result.get("error"):
            interpretation = f"SQL执行出错: {query_result['error']}"
        else:
            interpretation = self.explain_result(question, query_result)

        return {
            "question": question,
            "sql": sql,
            "explanation": sql_result.get("explanation", ""),
            "tables_used": sql_result.get("tables_used", []),
            "columns": query_result.get("columns", []),
            "rows": query_result.get("rows", []),
            "total": query_result.get("total", 0),
            "interpretation": interpretation,
            "error": query_result.get("error"),
        }


# 全局单例
text2sql_engine = Text2SQLEngine()
