from __future__ import annotations
from typing import List
"""文档模板API路由 - 模板列表、生成文档、模板管理"""
import logging
import os
import shutil
import uuid
from pathlib import Path

from fastapi import APIRouter, HTTPException, UploadFile, File
from pydantic import BaseModel

from config.settings import settings
from core.template_engine import template_engine

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/template", tags=["文档模板"])


class GenerateRequest(BaseModel):
    """生成文档请求"""
    template_name: str
    variables: dict = {}


class CreateTemplateRequest(BaseModel):
    """创建自定义模板请求"""
    name: str
    description: str = ""
    category: str = "其他"
    icon: str = "📄"
    doc_type: str = "docx"
    ai_prompt: str = ""
    variables: List[dict] = []


@router.get("/list")
async def list_templates(category: str = None):
    """列出所有可用模板"""
    templates = template_engine.list_templates(category)
    return {"templates": templates}


@router.get("/{name}")
async def get_template(name: str):
    """获取模板详情"""
    tmpl = template_engine.get_template(name)
    if not tmpl:
        raise HTTPException(status_code=404, detail=f"模板 '{name}' 不存在")
    return tmpl


@router.post("/generate")
async def generate_document(req: GenerateRequest):
    """根据模板生成文档"""
    result = template_engine.generate_document(req.template_name, req.variables)

    if result.get("error"):
        logger.warning(f"文档生成失败: {result['error']}")
        raise HTTPException(status_code=400, detail=result["error"])

    logger.info(f"文档生成成功: {result.get('filename')}, doc_id={result.get('doc_id')}")
    return result


@router.post("/create")
async def create_template(req: CreateTemplateRequest):
    """创建自定义模板"""
    user_dir = settings.USER_DIR / "templates" / req.name

    if user_dir.exists():
        raise HTTPException(status_code=400, detail=f"模板 '{req.name}' 已存在")

    user_dir.mkdir(parents=True, exist_ok=True)

    # 生成template.yaml
    import yaml
    config = {
        "name": req.name,
        "description": req.description,
        "category": req.category,
        "icon": req.icon,
        "doc_type": req.doc_type,
        "variables": req.variables,
        "ai_prompt": req.ai_prompt,
        "output": {
            "filename": f"{req.name}_{{{{date}}}}.{req.doc_type}"
        }
    }

    with open(user_dir / "template.yaml", "w", encoding="utf-8") as f:
        yaml.dump(config, f, allow_unicode=True, default_flow_style=False, sort_keys=False)

    return {"name": req.name, "dir": str(user_dir)}


@router.post("/{name}/upload-template-file")
async def upload_template_file(name: str, file: UploadFile = File(...)):
    """上传模板文件（Word/PPT）"""
    tmpl_info = template_engine.get_template(name)
    if not tmpl_info:
        raise HTTPException(status_code=404, detail=f"模板 '{name}' 不存在")

    tmpl_dir = Path(tmpl_info["dir"])

    # 保存文件
    filename = file.filename or "template.docx"
    save_path = tmpl_dir / filename

    with open(save_path, "wb") as f:
        shutil.copyfileobj(file.file, f)

    # 更新template.yaml中的template_file字段
    yaml_path = tmpl_dir / "template.yaml"
    if yaml_path.exists():
        import yaml
        with open(yaml_path, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f)
        config["template_file"] = filename
        with open(yaml_path, "w", encoding="utf-8") as f:
            yaml.dump(config, f, allow_unicode=True, default_flow_style=False, sort_keys=False)

    return {"filename": filename, "saved": True}


@router.delete("/{name}")
async def delete_template(name: str):
    """删除自定义模板（只允许删用户模板）"""
    user_dir = settings.USER_DIR / "templates" / name

    if not user_dir.exists():
        raise HTTPException(status_code=404, detail=f"模板 '{name}' 不存在")

    # 检查是不是系统模板
    system_dir = settings.CONFIG_DIR / "templates" / name
    if system_dir.exists() and not user_dir.exists():
        raise HTTPException(status_code=400, detail="系统模板不允许删除")

    shutil.rmtree(user_dir)
    return {"deleted": True}


@router.get("/categories/list")
async def list_categories():
    """列出所有模板分类"""
    templates = template_engine.list_templates()
    categories = list(set(t.get("category", "其他") for t in templates))
    return {"categories": sorted(categories)}
