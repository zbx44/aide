from __future__ import annotations
from typing import List
"""邮件通知通道"""
import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email.mime.text import MIMEText
from email import encoders
from pathlib import Path

logger = logging.getLogger(__name__)


class EmailNotifier:
    """邮件通知"""

    def __init__(self, smtp_server: str, smtp_port: int = 465,
                 sender: str = "", password: str = ""):
        self.smtp_server = smtp_server
        self.smtp_port = smtp_port
        self.sender = sender
        self.password = password

    async def send_message(self, target: str, content: str,
                           attachments: List[str] = None) -> bool:
        """发送邮件

        Args:
            target: 收件人邮箱
            content: 邮件内容
            attachments: 附件文件路径列表
        """
        try:
            msg = MIMEMultipart()
            msg["From"] = self.sender
            msg["To"] = target
            msg["Subject"] = content[:100]  # 取前100字作标题

            msg.attach(MIMEText(content, "plain", "utf-8"))

            # 添加附件
            if attachments:
                for file_path in attachments:
                    path = Path(file_path)
                    if path.exists():
                        with open(path, "rb") as f:
                            part = MIMEBase("application", "octet-stream")
                            part.set_payload(f.read())
                            encoders.encode_base64(part)
                            part.add_header(
                                "Content-Disposition",
                                f"attachment; filename={path.name}"
                            )
                            msg.attach(part)

            with smtplib.SMTP_SSL(self.smtp_server, self.smtp_port) as server:
                server.login(self.sender, self.password)
                server.sendmail(self.sender, [target], msg.as_string())

            logger.info(f"邮件发送成功: {target}")
            return True
        except Exception as e:
            logger.error(f"邮件发送失败: {e}")
            return False
