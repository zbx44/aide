from __future__ import annotations
"""知识库API路由"""
import logging
import os
import tempfile

from fastapi import APIRouter, HTTPException, UploadFile, File, Form, Query

from core.knowledge import knowledge_base

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/kb", tags=["知识库"])


# ===== 知识库管理 =====

@router.post("/create")
async def create_kb(name: str = Query(...), description: str = Query("")):
    """创建知识库"""
    try:
        return knowledge_base.create_kb(name, description)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/list")
async def list_kbs():
    """知识库列表"""
    return knowledge_base.list_kbs()


@router.get("/{kb_id}")
async def get_kb(kb_id: str):
    """获取知识库详情"""
    kb = knowledge_base.get_kb(kb_id)
    if not kb:
        raise HTTPException(status_code=404, detail="知识库不存在")
    docs = knowledge_base.get_documents(kb_id)
    return {**kb, "documents": docs}


@router.delete("/{kb_id}")
async def delete_kb(kb_id: str):
    """删除知识库"""
    knowledge_base.delete_kb(kb_id)
    return {"status": "ok"}


# ===== 文档管理 =====

@router.post("/{kb_id}/upload")
async def upload_document(kb_id: str, file: UploadFile = File(...)):
    """上传文档到知识库"""
    kb = knowledge_base.get_kb(kb_id)
    if not kb:
        raise HTTPException(status_code=404, detail="知识库不存在")

    # 保存临时文件
    suffix = os.path.splitext(file.filename)[1] or ".txt"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        content = await file.read()
        tmp.write(content)
        tmp_path = tmp.name

    try:
        result = knowledge_base.upload_document(kb_id, tmp_path, file.filename)
        return result
    finally:
        os.unlink(tmp_path)


@router.get("/{kb_id}/documents")
async def list_documents(kb_id: str):
    """获取知识库文档列表"""
    return knowledge_base.get_documents(kb_id)


@router.delete("/documents/{doc_id}")
async def delete_document(doc_id: str):
    """删除文档"""
    knowledge_base.delete_document(doc_id)
    return {"status": "ok"}


# ===== 检索 =====

@router.get("/{kb_id}/search")
async def search_kb(kb_id: str, q: str = Query(..., description="搜索关键词"),
                     top_k: int = Query(5, ge=1, le=20)):
    """检索知识库"""
    kb = knowledge_base.get_kb(kb_id)
    if not kb:
        raise HTTPException(status_code=404, detail="知识库不存在")
    return knowledge_base.search(kb_id, q, top_k=top_k)
