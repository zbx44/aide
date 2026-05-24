from __future__ import annotations
"""致远OA通知通道"""
import logging
from typing import List, Optional

import httpx

logger = logging.getLogger(__name__)


class SeeyonNotifier:
    """致远OA集成"""

    def __init__(self, base_url: str, username: str = "", password: str = ""):
        self.base_url = base_url.rstrip("/")
        self.username = username
        self.password = password
        self._token: Optional[str] = None
        self._client = httpx.Client(timeout=30.0)

    async def _get_token(self) -> str:
        """获取OA Token"""
        if self._token:
            return self._token

        url = f"{self.base_url}/seeyon/rest/token"
        resp = self._client.post(url, json={
            "userName": self.username,
            "password": self.password,
        })
        resp.raise_for_status()
        data = resp.json()
        self._token = data.get("token", data.get("id", ""))
        return self._token

    async def _headers(self) -> dict:
        """构建请求头"""
        token = await self._get_token()
        return {
            "Content-Type": "application/json",
            "token": token,
        }

    async def upload_attachment(self, file_path: str, filename: str = None) -> str:
        """上传附件，返回附件ID"""
        import os
        if not filename:
            filename = os.path.basename(file_path)

        token = await self._get_token()
        with open(file_path, "rb") as f:
            resp = self._client.post(
                f"{self.base_url}/seeyon/rest/attachment",
                headers={"token": token},
                files={"file": (filename, f)},
                data={"filename": filename},
            )
        resp.raise_for_status()
        data = resp.json()
        return str(data.get("fileUrl", data.get("id", "")))

    async def start_process(
        self,
        template_code: str,
        form_data: dict,
        subject: str = "",
        draft: bool = False,
        attachments: List[str] = None,
    ) -> dict:
        """发起致远流程

        Args:
            template_code: 模板编号
            form_data: 表单数据，如 {"formmain_0177": {"文本1": "值1"}}
            subject: 标题
            draft: True=保存待发，False=直接发送
            attachments: 附件ID列表
        """
        headers = await self._headers()

        payload = {
            "appName": "collaboration",
            "data": {
                "templateCode": template_code,
                "draft": "1" if draft else "0",
                "subject": subject,
                "data": form_data,
                "attachments": attachments or [],
            },
        }

        resp = self._client.post(
            f"{self.base_url}/seeyon/rest/bpm/process/start",
            headers=headers,
            json=payload,
        )
        resp.raise_for_status()
        result = resp.json()
        logger.info(f"致远流程发起成功: template={template_code}, subject={subject}")
        return result

    async def send_message(self, target: str, content: str,
                           attachments: list = None) -> bool:
        """统一通知接口实现：通过发起流程发送消息"""
        try:
            # 简单实现：以内容为标题发起一个流程
            await self.start_process(
                template_code=target,  # target作为模板编号
                form_data={},
                subject=content[:200],
                attachments=attachments,
            )
            return True
        except Exception as e:
            logger.error(f"致远OA发送消息失败: {e}")
            return False
