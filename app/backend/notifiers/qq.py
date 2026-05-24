from __future__ import annotations
from typing import List
"""QQ通知通道（预留）"""
import logging

logger = logging.getLogger(__name__)


class QQNotifier:
    """QQ通知 - 后续对接IM接口后实现"""

    def __init__(self, config: dict = None):
        self.config = config or {}

    async def send_message(self, target: str, content: str,
                           attachments: List[str] = None) -> bool:
        """发送QQ消息"""
        logger.warning("QQ通知尚未实现，IM接口待配置")
        return False
