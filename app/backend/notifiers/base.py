from __future__ import annotations
"""通知接口基类"""
from typing import List, Optional, Protocol


class NotifyChannel(Protocol):
    """统一通知接口协议"""

    async def send_message(self, target: str, content: str,
                          attachments: List[str] = None) -> bool:
        """发送消息

        Args:
            target: 通知目标（邮箱/QQ号/OA模板编号等）
            content: 消息内容
            attachments: 附件文件路径列表

        Returns:
            是否发送成功
        """
        ...
