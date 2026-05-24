from __future__ import annotations
"""OA流程API路由"""
import logging

from fastapi import APIRouter, HTTPException, UploadFile, File

from models.schemas import OAStartProcessRequest, OAUploadRequest
from config.settings import settings

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/oa", tags=["OA流程"])


@router.post("/start-process")
async def start_process(req: OAStartProcessRequest):
    """发起致远OA流程"""
    if not settings.SEELYON_BASE_URL:
        raise HTTPException(status_code=500, detail="致远OA未配置")

    try:
        from notifiers.seeyon import SeeyonNotifier
        notifier = SeeyonNotifier(
            base_url=settings.SEELYON_BASE_URL,
            username=settings.SEELYON_USERNAME,
            password=settings.SEELYON_PASSWORD,
        )
        result = await notifier.start_process(
            template_code=req.template_code,
            form_data=req.form_data,
            subject=req.subject,
            draft=req.draft,
            attachments=req.attachments,
        )
        return {"status": "ok", "result": result}
    except Exception as e:
        logger.error(f"OA流程发起失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/upload")
async def upload_attachment(file: UploadFile = File(...)):
    """上传附件到致远OA"""
    if not settings.SEELYON_BASE_URL:
        raise HTTPException(status_code=500, detail="致远OA未配置")

    try:
        import tempfile
        from notifiers.seeyon import SeeyonNotifier

        # 保存临时文件
        with tempfile.NamedTemporaryFile(delete=False, suffix=f"_{file.filename}") as tmp:
            content = await file.read()
            tmp.write(content)
            tmp_path = tmp.name

        notifier = SeeyonNotifier(
            base_url=settings.SEELYON_BASE_URL,
            username=settings.SEELYON_USERNAME,
            password=settings.SEELYON_PASSWORD,
        )
        file_id = await notifier.upload_attachment(tmp_path, file.filename)

        # 清理临时文件
        import os
        os.unlink(tmp_path)

        return {"file_id": file_id, "filename": file.filename}
    except Exception as e:
        logger.error(f"附件上传失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/notify")
async def send_notify(req: dict):
    """发送通知（统一接口）"""
    channel = req.get("channel", "email")
    target = req.get("target", "")
    content = req.get("content", "")
    attachments = req.get("attachments", [])

    try:
        if channel == "email":
            from notifiers.email import EmailNotifier
            notifier = EmailNotifier(
                smtp_server=settings.EMAIL_SMTP,
                smtp_port=settings.EMAIL_SMTP_PORT,
                sender=settings.EMAIL_SENDER,
                password=settings.EMAIL_PASSWORD,
            )
            success = await notifier.send_message(target, content, attachments)
        elif channel == "seeyon":
            # OA流程通知
            pass
        else:
            raise HTTPException(status_code=400, detail=f"不支持的通知渠道: {channel}")

        return {"status": "ok" if success else "failed"}
    except Exception as e:
        logger.error(f"通知发送失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))
