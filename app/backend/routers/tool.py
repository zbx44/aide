from __future__ import annotations
"""工具API路由"""
import logging
import tempfile
import os

from fastapi import APIRouter, HTTPException, UploadFile, File

from engines.tool_engine import tool_engine

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/tool", tags=["智能工具"])


@router.get("/list")
async def list_tools():
    """可用工具列表"""
    return tool_engine.list_tools()


@router.post("/ocr")
async def ocr_recognize(file: UploadFile = File(...)):
    """OCR图文识别（支持PaddleOCR和LLM方式）"""
    try:
        # 方式1: 尝试PaddleOCR
        from paddleocr import PaddleOCR
        ocr = PaddleOCR(use_angle_cls=True, lang="ch")

        suffix = os.path.splitext(file.filename)[1] or ".png"
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            content = await file.read()
            tmp.write(content)
            tmp_path = tmp.name

        result = ocr.ocr(tmp_path, cls=True)
        os.unlink(tmp_path)

        texts = []
        for line in result:
            if line:
                for item in line:
                    texts.append(item[1][0])

        return {"text": "\n".join(texts), "lines": len(texts), "engine": "paddleocr"}

    except ImportError:
        # PaddleOCR未安装，回退到LLM视觉模型识别
        logger.info("PaddleOCR未安装，尝试LLM方式识别...")
        try:
            import base64
            from core.llm import llm_client

            content = await file.read()
            b64 = base64.b64encode(content).decode()

            suffix = os.path.splitext(file.filename)[1] or ".png"
            mime_map = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
                        ".gif": "image/gif", ".webp": "image/webp", ".bmp": "image/bmp"}
            mime = mime_map.get(suffix.lower(), "image/png")

            messages = [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "请识别并提取这张图片中的所有文字，按原始格式输出。"},
                        {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{b64}"}},
                    ]
                }
            ]

            text = llm_client.chat(messages, max_tokens=4096)
            lines = [l for l in text.split("\n") if l.strip()]
            return {"text": text, "lines": len(lines), "engine": "llm"}

        except Exception as e2:
            logger.error(f"LLM OCR也失败: {e2}")
            raise HTTPException(
                status_code=501,
                detail="OCR功能暂不可用：PaddleOCR未安装，且LLM视觉识别也失败。"
                       f"请安装PaddleOCR: pip install paddleocr paddlepaddle"
            )

    except Exception as e:
        logger.error(f"OCR识别失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/execute")
async def execute_tool(req: dict):
    """执行工具"""
    try:
        result = await tool_engine.execute(
            name=req.get("name"),
            **req.get("params", {})
        )
        return {"result": result}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"工具执行失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ===== 文件索引进度查询 =====

@router.get("/file-index/progress")
async def file_index_progress():
    """查询文件索引构建进度（前端轮询）"""
    try:
        from core.file_indexer import file_indexer
        return {
            "progress": file_indexer.progress.get_snapshot(),
            "formatted": file_indexer.progress.get_formatted(),
        }
    except Exception as e:
        return {"error": str(e), "progress": {"is_indexing": False}}


@router.get("/file-index/stats")
async def file_index_stats():
    """查询文件索引统计信息"""
    try:
        from core.file_indexer import file_indexer
        return file_indexer.get_status()
    except Exception as e:
        return {"error": str(e)}


# ===== 技能启停管理 =====

@router.get("/skills/config")
async def get_skills_config():
    """获取所有技能的开关配置"""
    try:
        from core.skills import skill_manager
        return {"skills": skill_manager.get_all_skill_configs()}
    except Exception as e:
        return {"error": str(e)}


@router.post("/skills/toggle")
async def toggle_skill(req: dict):
    """开关一个技能
    Body: {"name": "xxx", "enabled": true/false}
    """
    try:
        from core.skills import skill_manager
        result = skill_manager.toggle_skill(
            name=req.get("name", ""),
            enabled=req.get("enabled"),
        )
        return result
    except Exception as e:
        return {"error": str(e)}
