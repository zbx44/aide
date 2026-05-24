from __future__ import annotations
from typing import Dict
"""文档API路由"""
import json
import logging
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from models.schemas import DocCreateRequest, DocModifyRequest, DocResponse
from engines.doc_engine import doc_engine
from config.settings import settings

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/doc", tags=["文档"])

# 简易内存存储（后续迁移到SQLite）
_doc_states: Dict[str, dict] = {}


@router.post("/create", response_model=DocResponse)
async def create_doc(req: DocCreateRequest):
    """创建文档"""
    try:
        result = await doc_engine.create_doc(
            description=req.description,
            doc_type=req.doc_type,
            extra_context=req.extra_context,
        )
        # 保存状态
        doc_id = result["doc_id"]
        _doc_states[doc_id] = {
            "doc_id": doc_id,
            "type": req.doc_type,
            "title": result["title"],
            "created_at": result.get("created_at", ""),
            "updated_at": result.get("updated_at", ""),
            "content": {},  # 首次创建时内容已在引擎内部
        }
        return DocResponse(**result)
    except Exception as e:
        logger.error(f"创建文档失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{doc_id}/modify", response_model=DocResponse)
async def modify_doc(doc_id: str, req: DocModifyRequest):
    """修改文档"""
    if doc_id not in _doc_states:
        raise HTTPException(status_code=404, detail="文档不存在")

    current_state = _doc_states[doc_id]
    try:
        result = await doc_engine.modify_doc(
            doc_id=doc_id,
            instruction=req.instruction,
            current_state=current_state,
        )
        # 更新状态
        _doc_states[doc_id].update({
            "title": result["title"],
            "updated_at": result.get("updated_at", ""),
        })
        return DocResponse(**result)
    except Exception as e:
        logger.error(f"修改文档失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{doc_id}/download")
async def download_doc(doc_id: str):
    """下载文档"""
    # 先查找文件系统（模板生成的文档可能不在_doc_states中）
    doc_dir = settings.OUTPUT_DIR / doc_id
    if doc_dir.exists():
        files = list(doc_dir.glob("*"))
        if files:
            # 排除目录，只取文件
            files = [f for f in files if f.is_file()]
        if files:
            latest = max(files, key=lambda f: f.stat().st_mtime)
            return FileResponse(
                path=str(latest),
                filename=latest.name,
                media_type="application/octet-stream",
            )

    # 兜底：检查内存状态
    if doc_id not in _doc_states:
        raise HTTPException(status_code=404, detail="文件不存在")

    raise HTTPException(status_code=404, detail="文件不存在")


@router.get("/{doc_id}/preview")
async def preview_doc(doc_id: str):
    """预览文档JSON状态"""
    if doc_id not in _doc_states:
        raise HTTPException(status_code=404, detail="文档不存在")
    return _doc_states[doc_id]


@router.get("/list")
async def list_docs():
    """文档列表"""
    return [
        {
            "doc_id": state["doc_id"],
            "type": state["type"],
            "title": state["title"],
            "updated_at": state.get("updated_at", ""),
        }
        for state in _doc_states.values()
    ]


@router.delete("/{doc_id}")
async def delete_doc(doc_id: str):
    """删除文档"""
    if doc_id in _doc_states:
        del _doc_states[doc_id]
    return {"status": "ok"}
