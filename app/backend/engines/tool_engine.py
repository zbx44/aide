from __future__ import annotations
from typing import List
"""智能工具引擎"""
import logging

logger = logging.getLogger(__name__)


class ToolEngine:
    """智能工具集"""

    def __init__(self):
        self._tools = {}

    def register(self, name: str, func, description: str = ""):
        """注册工具"""
        self._tools[name] = {
            "name": name,
            "func": func,
            "description": description,
        }

    def list_tools(self) -> List[dict]:
        """列出所有工具"""
        return [
            {"name": t["name"], "description": t["description"]}
            for t in self._tools.values()
        ]

    async def execute(self, name: str, **kwargs):
        """执行工具"""
        if name not in self._tools:
            raise ValueError(f"工具不存在: {name}")
        return await self._tools[name]["func"](**kwargs)


# 全局单例
tool_engine = ToolEngine()
