from __future__ import annotations
"""系统设置API路由 - 数据源配置管理"""
import logging
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from config.settings import settings
from core.datasource import ds_manager

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/settings", tags=["系统设置"])


# ===== 数据源 CRUD =====

@router.get("/datasource")
async def list_datasources():
    """列出所有数据源（密码脱敏）"""
    return {"datasources": ds_manager.list_datasources()}


@router.get("/datasource/{ds_id}")
async def get_datasource(ds_id: str):
    """获取数据源详情（密码脱敏）"""
    ds = ds_manager.get_datasource(ds_id)
    if not ds:
        raise HTTPException(status_code=404, detail="数据源不存在")
    info = {**ds}
    if info.get("password"):
        info["password"] = "***"
    return info


class AddDataSourceRequest(BaseModel):
    name: str
    type: str = "dm"  # dm, mysql, postgresql, sqlite
    host: str = ""
    standby_host: str = ""
    port: int = 0
    username: str = ""
    password: str = ""
    database: str = ""


@router.post("/datasource")
async def add_datasource(req: AddDataSourceRequest):
    """添加数据源"""
    ds_config = req.dict()
    result = ds_manager.add_datasource(ds_config)
    return {"message": "添加成功", "datasource": result}


class UpdateDataSourceRequest(BaseModel):
    name: Optional[str] = None
    host: Optional[str] = None
    standby_host: Optional[str] = None
    port: Optional[int] = None
    username: Optional[str] = None
    password: Optional[str] = None
    database: Optional[str] = None
    enabled: Optional[bool] = None


@router.put("/datasource/{ds_id}")
async def update_datasource(ds_id: str, req: UpdateDataSourceRequest):
    """更新数据源"""
    updates = {k: v for k, v in req.dict().items() if v is not None}
    result = ds_manager.update_datasource(ds_id, updates)
    if not result:
        raise HTTPException(status_code=404, detail="数据源不存在")
    return {"message": "更新成功", "datasource": result}


@router.delete("/datasource/{ds_id}")
async def delete_datasource(ds_id: str):
    """删除数据源"""
    if ds_manager.delete_datasource(ds_id):
        return {"message": "删除成功"}
    raise HTTPException(status_code=404, detail="数据源不存在")


@router.post("/datasource/{ds_id}/test")
async def test_datasource(ds_id: str):
    """测试数据源连接"""
    result = ds_manager.test_connection(ds_id)
    return result


# ===== 旧兼容接口（设置页面通用） =====

@router.get("/datasource-status")
async def datasource_status():
    """数据源总览"""
    ds_list = ds_manager.list_datasources()
    return {
        "total": len(ds_list),
        "enabled": sum(1 for ds in ds_list if ds.get("enabled")),
        "types": list(set(ds.get("type", "unknown") for ds in ds_list)),
    }
