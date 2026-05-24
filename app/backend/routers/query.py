from __future__ import annotations
"""数据查询API路由 - 自然语言查询 + SQL执行 + 可视化构建"""
import logging
from typing import List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/query", tags=["数据查询"])


class NaturalQueryRequest(BaseModel):
    """自然语言查询请求"""
    question: str
    datasource_id: Optional[str] = None


class SQLQueryRequest(BaseModel):
    """直接SQL查询请求"""
    sql: str
    max_rows: int = 1000
    datasource_id: Optional[str] = None


class VisualQueryRequest(BaseModel):
    """可视化查询构建请求"""
    table_name: str
    columns: List[str] = []
    conditions: List[dict] = []
    order_by: Optional[str] = None
    order_dir: str = "ASC"
    limit: int = 100
    datasource_id: Optional[str] = None


@router.post("/natural")
async def natural_language_query(req: NaturalQueryRequest):
    """自然语言查询 - 说人话查数据

    示例:
        "查一下本月故障率最高的5台设备"
        "3号车间上周的维修记录"
    """
    from core.text2sql import text2sql_engine

    result = text2sql_engine.query(req.question)

    if result.get("error") and result.get("error") == "schema_not_configured":
        raise HTTPException(
            status_code=503,
            detail="数据库表结构未配置，请联系管理员配置 db_schema.yaml"
        )

    return result


@router.post("/sql")
async def execute_sql_query(req: SQLQueryRequest):
    """直接执行SQL查询（需通过安全检查）

    只允许SELECT语句，自动添加行数限制。
    """
    from core.sql_safety import sql_safety_checker
    from core.datasource import ds_manager

    # 确定使用哪个数据源
    ds_id = req.datasource_id
    if not ds_id:
        # 默认用第一个启用的数据源
        ds_list = ds_manager.list_datasources()
        enabled = [ds for ds in ds_list if ds.get("enabled")]
        if enabled:
            ds_id = enabled[0]["id"]

    if not ds_id:
        raise HTTPException(status_code=503, detail="未配置可用数据源，请在设置中添加")

    # 安全检查
    is_safe, reason = sql_safety_checker.check(req.sql)
    if not is_safe:
        raise HTTPException(status_code=400, detail=f"SQL安全检查未通过: {reason}")

    sql = sql_safety_checker.add_limit(req.sql, req.max_rows)

    try:
        rows = ds_manager.execute_query(ds_id, sql)

        if not rows:
            return {"columns": [], "rows": [], "total": 0}

        columns = list(rows[0].keys())
        data_rows = [[str(row.get(col, "")) for col in columns] for row in rows]

        return {"columns": columns, "rows": data_rows, "total": len(data_rows)}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"SQL执行失败: {e}")


@router.post("/visual")
async def visual_query(req: VisualQueryRequest):
    """可视化查询构建器 - 拼装SQL执行"""
    from core.sql_safety import sql_safety_checker
    from core.datasource import ds_manager
    from core.schema_manager import schema_manager

    ds_id = req.datasource_id
    if not ds_id:
        ds_list = ds_manager.list_datasources()
        enabled = [ds for ds in ds_list if ds.get("enabled")]
        if enabled:
            ds_id = enabled[0]["id"]

    if not ds_id:
        raise HTTPException(status_code=503, detail="未配置可用数据源")

    # 检查表是否在Schema中
    table_info = schema_manager.get_table(req.table_name)
    if not table_info:
        raise HTTPException(status_code=400, detail=f"未知的数据表: {req.table_name}")

    # 构建SQL
    if req.columns:
        cols = ", ".join(f'"{c}"' for c in req.columns)
    else:
        cols = "*"

    sql = f'SELECT {cols} FROM "{req.table_name}"'

    conditions = []
    for cond in req.conditions:
        field = cond.get("field", "")
        op = cond.get("op", "=")
        value = cond.get("value", "")

        if not field or not value:
            continue

        allowed_ops = ["=", "!=", ">", ">=", "<", "<=", "LIKE", "NOT LIKE", "IN", "IS", "IS NOT"]
        if op.upper() not in allowed_ops:
            continue

        if op.upper() in ("LIKE", "NOT LIKE"):
            conditions.append(f'"{field}" {op} \'%{value}%\'')
        elif op.upper() == "IN":
            values = [v.strip() for v in value.split(",")]
            values_str = ", ".join(f"'{v}'" for v in values)
            conditions.append(f'"{field}" {op} ({values_str})')
        else:
            conditions.append(f'"{field}" {op} \'{value}\'')

    if conditions:
        sql += " WHERE " + " AND ".join(conditions)

    if req.order_by:
        direction = "DESC" if req.order_dir.upper() == "DESC" else "ASC"
        sql += f' ORDER BY "{req.order_by}" {direction}'

    sql += f" LIMIT {req.limit}"

    is_safe, reason = sql_safety_checker.check(sql)
    if not is_safe:
        raise HTTPException(status_code=400, detail=f"生成的SQL安全检查未通过: {reason}")

    try:
        rows = ds_manager.execute_query(ds_id, sql)

        if not rows:
            return {"columns": [], "rows": [], "total": 0, "sql": sql}

        columns = list(rows[0].keys())
        data_rows = [[str(row.get(col, "")) for col in columns] for row in rows]

        return {"columns": columns, "rows": data_rows, "total": len(data_rows), "sql": sql}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"查询执行失败: {e}")


@router.get("/datasources")
async def get_query_datasources():
    """获取可用数据源列表（给前端下拉用）"""
    from core.datasource import ds_manager
    ds_list = ds_manager.list_datasources()
    return {"datasources": [ds for ds in ds_list if ds.get("enabled")]}


@router.get("/schema")
async def get_schema():
    """获取数据库Schema信息"""
    from core.schema_manager import schema_manager
    return schema_manager.schema


@router.post("/schema/extract")
async def extract_schema():
    """从达梦数据库自动提取Schema（管理员操作）"""
    from core.schema_manager import schema_manager
    result = schema_manager.auto_extract_and_save()
    if result.get("error"):
        raise HTTPException(status_code=500, detail=result["error"])
    return result
