from __future__ import annotations
"""Schema管理器 - 数据库表结构管理

支持从YAML配置文件加载和从达梦数据库自动提取。
"""
import logging
import os
from pathlib import Path
from typing import List, Optional

from config.settings import settings

logger = logging.getLogger(__name__)


class SchemaManager:
    """数据库Schema管理器"""

    def __init__(self):
        self.schema_file = settings.CONFIG_DIR / "db_schema.yaml"
        self.schema = None
        self._load()

    def _load(self):
        """从YAML文件加载Schema"""
        if self.schema_file.exists():
            try:
                import yaml
                with open(self.schema_file, "r", encoding="utf-8") as f:
                    self.schema = yaml.safe_load(f)
                tables = self.schema.get("tables", []) if self.schema else []
                logger.info(f"加载Schema: {len(tables)} 个表")
            except Exception as e:
                logger.error(f"加载Schema失败: {e}")
                self.schema = {"tables": [], "relations": []}
        else:
            self.schema = {"tables": [], "relations": []}

    def reload(self):
        """重新加载"""
        self._load()

    def get_tables(self) -> List[dict]:
        """获取所有表信息"""
        return self.schema.get("tables", [])

    def get_table(self, table_name: str) -> Optional[dict]:
        """获取单个表信息"""
        for t in self.get_tables():
            if t.get("name") == table_name:
                return t
        return None

    def get_relations(self) -> List[dict]:
        """获取表间关系"""
        return self.schema.get("relations", [])

    def get_schema_text(self) -> str:
        """获取Schema的文本描述（用于Prompt构建）"""
        lines = []
        for table in self.get_tables():
            name = table.get("name", "")
            comment = table.get("comment", "")
            lines.append(f"表 {name}（{comment}）:")
            for col in table.get("columns", []):
                lines.append(
                    f"  {col.get('name', '')} {col.get('type', '')} — {col.get('comment', '')}"
                )
            lines.append("")

        for rel in self.get_relations():
            lines.append(
                f"关系: {rel.get('from', '')} → {rel.get('to', '')}（{rel.get('comment', '')}）"
            )

        return "\n".join(lines)

    def extract_from_database(self) -> dict:
        """从达梦数据库自动提取Schema

        Returns:
            提取的Schema dict
        """
        try:
            from core.database import dm_database

            # 获取所有用户表
            tables_sql = """
            SELECT TABLE_NAME, COMMENTS 
            FROM ALL_TAB_COMMENTS 
            WHERE OWNER = 'DMDB' AND TABLE_TYPE = 'TABLE'
            ORDER BY TABLE_NAME
            """

            tables_result = dm_database.execute_query(tables_sql)
            if not tables_result:
                return {"tables": [], "relations": []}

            schema = {"tables": [], "relations": []}

            for table_row in tables_result:
                table_name = table_row.get("TABLE_NAME", "")
                table_comment = table_row.get("COMMENTS", "")

                # 获取列信息
                columns_sql = f"""
                SELECT COLUMN_NAME, DATA_TYPE, DATA_LENGTH, COMMENTS
                FROM ALL_COL_COMMENTS 
                WHERE OWNER = 'DMDB' AND TABLE_NAME = '{table_name}'
                ORDER BY COLUMN_ID
                """

                try:
                    columns_result = dm_database.execute_query(columns_sql)
                    columns = []
                    for col_row in (columns_result or []):
                        columns.append({
                            "name": col_row.get("COLUMN_NAME", ""),
                            "type": col_row.get("DATA_TYPE", ""),
                            "comment": col_row.get("COMMENTS", ""),
                        })

                    schema["tables"].append({
                        "name": table_name,
                        "comment": table_comment or table_name,
                        "columns": columns,
                    })
                except Exception as e:
                    logger.error(f"获取表 {table_name} 的列信息失败: {e}")

            return schema

        except Exception as e:
            logger.error(f"从数据库提取Schema失败: {e}")
            return {"tables": [], "relations": [], "error": str(e)}

    def save_schema(self, schema: dict) -> str:
        """保存Schema到YAML文件"""
        import yaml

        self.schema_file.parent.mkdir(parents=True, exist_ok=True)

        with open(self.schema_file, "w", encoding="utf-8") as f:
            yaml.dump(schema, f, allow_unicode=True, default_flow_style=False, sort_keys=False)

        self.schema = schema
        logger.info(f"Schema已保存: {len(schema.get('tables', []))} 个表")
        return str(self.schema_file)

    def auto_extract_and_save(self) -> dict:
        """自动从数据库提取Schema并保存

        Returns:
            {"tables_count": N, "file": "path", "error": null}
        """
        schema = self.extract_from_database()
        if schema.get("error"):
            return {"tables_count": 0, "file": "", "error": schema["error"]}

        file_path = self.save_schema(schema)
        return {
            "tables_count": len(schema.get("tables", [])),
            "file": file_path,
            "error": None,
        }


# 全局单例
schema_manager = SchemaManager()
