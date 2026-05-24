from __future__ import annotations
"""FastAGI 智能体客户端 - 对接滴普FastAGI大模型工作流平台

功能：
1. 管理智能体列表（从本地配置加载）
2. 调用FastAGI对话接口（阻塞/流式）
3. 上传文件到FastAGI智能体
4. 自动签名认证（HMAC-SHA256）
"""
import hashlib
import hmac
import json
import logging
import time
import uuid
from pathlib import Path
from typing import Any, AsyncGenerator, Dict, List, Optional

import httpx

from config.settings import settings

logger = logging.getLogger(__name__)

# 智能体配置文件路径
AGENTS_CONFIG_PATH = settings.DATA_DIR / "agents.json"

# 默认智能体配置模板
DEFAULT_AGENTS_CONFIG = {
    "fastagi": {
        "base_url": "https://fastagi-cloud-test.deepexi.com",
        "app_id": "",
        "secret_key": ""
    },
    "agents": [
        {
            "id": "example-agent",
            "name": "示例智能体",
            "icon": "🤖",
            "category": "通用",
            "description": "这是一个示例智能体，请在配置中替换为实际的FastAGI智能体",
            "agent_id": "",
            "enabled": False
        }
    ]
}


class FastAGIClient:
    """FastAGI 智能体客户端"""

    def __init__(self):
        self.base_url = ""
        self.app_id = ""
        self.secret_key = ""
        self.agents: List[dict] = []
        self._client = httpx.AsyncClient(timeout=httpx.Timeout(180.0, connect=10.0))
        self._load_config()

    def _load_config(self):
        """加载智能体配置"""
        if not AGENTS_CONFIG_PATH.exists():
            # 首次运行，写入默认配置
            AGENTS_CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
            with open(AGENTS_CONFIG_PATH, "w", encoding="utf-8") as f:
                json.dump(DEFAULT_AGENTS_CONFIG, f, ensure_ascii=False, indent=2)
            logger.info(f"已创建默认智能体配置: {AGENTS_CONFIG_PATH}")

        try:
            with open(AGENTS_CONFIG_PATH, "r", encoding="utf-8") as f:
                config = json.load(f)

            fastagi = config.get("fastagi", {})
            self.base_url = fastagi.get("base_url", "").rstrip("/")
            self.app_id = fastagi.get("app_id", "")
            self.secret_key = fastagi.get("secret_key", "")
            self.agents = config.get("agents", [])

            # 过滤启用的智能体
            self.agents = [a for a in self.agents if a.get("enabled", True)]
            logger.info(f"加载了 {len(self.agents)} 个智能体配置")
        except Exception as e:
            logger.error(f"加载智能体配置失败: {e}")
            self.agents = []

    def reload_config(self):
        """重新加载配置（用户修改配置后调用）"""
        self._load_config()

    def _calculate_signature(self, app_id: str, secret_key: str, timestamp: str) -> str:
        """生成请求签名"""
        message = f"{app_id}{timestamp}"
        return hmac.new(
            secret_key.encode(),
            message.encode(),
            hashlib.sha256
        ).hexdigest()

    def _get_headers(self, app_user: str = "aide") -> dict:
        """构造请求头（含签名）"""
        timestamp = str(int(time.time() * 1000))
        signature = self._calculate_signature(self.app_id, self.secret_key, timestamp)
        return {
            "app_id": self.app_id,
            "signature": signature,
            "timestamp": timestamp,
            "app_user": app_user,
        }

    def get_agents(self) -> List[dict]:
        """获取智能体列表"""
        return self.agents

    def get_agent(self, agent_id: str) -> Optional[dict]:
        """获取单个智能体配置"""
        for a in self.agents:
            if a["id"] == agent_id:
                return a
        return None

    async def chat(
        self,
        agent_id: str,
        query: str,
        conversation_id: str = "",
        user: str = "aide",
        inputs: Optional[dict] = None,
        files: Optional[List[dict]] = None,
    ) -> dict:
        """阻塞模式对话"""
        agent = self.get_agent(agent_id)
        if not agent:
            return {"error": f"智能体 {agent_id} 不存在"}

        if not self.base_url or not self.app_id:
            return {"error": "FastAGI 未配置，请在 data/agents.json 中设置 app_id 和 secret_key"}

        fastagi_agent_id = agent.get("agent_id", "")
        if not fastagi_agent_id:
            return {"error": f"智能体 {agent_id} 未配置 FastAGI agent_id"}

        url = f"{self.base_url}/api/openapi/chat/chat-messages"
        headers = self._get_headers(user)

        body = {
            "inputs": inputs or {},
            "agent_id": fastagi_agent_id,
            "query": query,
            "response_mode": "blocking",
            "user": user,
        }
        if conversation_id:
            body["conversation_id"] = conversation_id
        if files:
            body["files"] = files

        try:
            resp = await self._client.post(url, headers=headers, json=body)
            resp.raise_for_status()
            return resp.json()
        except httpx.HTTPStatusError as e:
            logger.error(f"FastAGI对话失败: {e.response.status_code} {e.response.text}")
            return {"error": f"FastAGI请求失败: HTTP {e.response.status_code}"}
        except Exception as e:
            logger.error(f"FastAGI对话异常: {e}")
            return {"error": f"FastAGI请求异常: {e}"}

    async def chat_stream(
        self,
        agent_id: str,
        query: str,
        conversation_id: str = "",
        user: str = "aide",
        inputs: Optional[dict] = None,
        files: Optional[List[dict]] = None,
    ) -> AsyncGenerator[dict, None]:
        """流式模式对话，yield SSE事件字典"""
        agent = self.get_agent(agent_id)
        if not agent:
            yield {"event": "error", "data": {"error": f"智能体 {agent_id} 不存在"}}
            return

        if not self.base_url or not self.app_id:
            yield {"event": "error", "data": {"error": "FastAGI 未配置"}}
            return

        fastagi_agent_id = agent.get("agent_id", "")
        if not fastagi_agent_id:
            yield {"event": "error", "data": {"error": f"智能体 {agent_id} 未配置 agent_id"}}
            return

        url = f"{self.base_url}/api/openapi/chat/chat-messages"
        headers = self._get_headers(user)

        body = {
            "inputs": inputs or {},
            "agent_id": fastagi_agent_id,
            "query": query,
            "response_mode": "streaming",
            "user": user,
        }
        if conversation_id:
            body["conversation_id"] = conversation_id
        if files:
            body["files"] = files

        try:
            async with self._client.stream("POST", url, headers=headers, json=body) as resp:
                resp.raise_for_status()
                async for line in resp.aiter_lines():
                    line = line.strip()
                    if not line:
                        continue
                    # FastAGI SSE格式: event: xxx\ndata: xxx
                    if line.startswith("data:"):
                        raw = line[5:].strip()
                        if not raw:
                            continue
                        try:
                            data = json.loads(raw)
                            event_type = data.get("event", "message")
                            yield {"event": event_type, "data": data}
                        except json.JSONDecodeError:
                            yield {"event": "message", "data": {"answer": raw}}
        except httpx.HTTPStatusError as e:
            yield {"event": "error", "data": {"error": f"HTTP {e.response.status_code}"}}
        except Exception as e:
            logger.error(f"FastAGI流式对话异常: {e}")
            yield {"event": "error", "data": {"error": str(e)}}

    async def upload_file(
        self,
        agent_id: str,
        file_path: str,
        file_name: str,
        user: str = "aide",
    ) -> dict:
        """上传文件到FastAGI智能体"""
        agent = self.get_agent(agent_id)
        if not agent:
            return {"error": f"智能体 {agent_id} 不存在"}

        fastagi_agent_id = agent.get("agent_id", "")
        if not fastagi_agent_id:
            return {"error": f"智能体 {agent_id} 未配置 agent_id"}

        url = f"{self.base_url}/api/openapi/chat/files/upload"
        headers = self._get_headers(user)
        # 上传文件不用Content-Type: application/json，httpx会自动处理multipart
        headers.pop("Content-Type", None)

        try:
            with open(file_path, "rb") as f:
                resp = await self._client.post(
                    url,
                    headers=headers,
                    data={"agent_id": fastagi_agent_id, "users": user},
                    files={"file": (file_name, f)},
                )
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            logger.error(f"FastAGI文件上传失败: {e}")
            return {"error": f"文件上传失败: {e}"}

    def get_fastagi_config(self) -> dict:
        """获取FastAGI连接配置（隐藏密钥）"""
        return {
            "base_url": self.base_url,
            "app_id": self.app_id,
            "secret_key_set": bool(self.secret_key),
            "agents_count": len(self.agents),
        }

    async def update_fastagi_config(
        self,
        base_url: str = "",
        app_id: str = "",
        secret_key: str = "",
    ) -> dict:
        """更新FastAGI连接配置"""
        try:
            with open(AGENTS_CONFIG_PATH, "r", encoding="utf-8") as f:
                config = json.load(f)

            fastagi = config.get("fastagi", {})
            if base_url:
                fastagi["base_url"] = base_url.rstrip("/")
            if app_id:
                fastagi["app_id"] = app_id
            if secret_key:
                fastagi["secret_key"] = secret_key
            config["fastagi"] = fastagi

            with open(AGENTS_CONFIG_PATH, "w", encoding="utf-8") as f:
                json.dump(config, f, ensure_ascii=False, indent=2)

            # 重载配置
            self._load_config()
            return {"message": "配置更新成功"}
        except Exception as e:
            return {"error": f"配置更新失败: {e}"}

    async def save_agents(self, agents: List[dict]) -> dict:
        """保存智能体列表"""
        try:
            with open(AGENTS_CONFIG_PATH, "r", encoding="utf-8") as f:
                config = json.load(f)

            config["agents"] = agents

            with open(AGENTS_CONFIG_PATH, "w", encoding="utf-8") as f:
                json.dump(config, f, ensure_ascii=False, indent=2)

            # 重载
            self._load_config()
            return {"message": f"已保存 {len(agents)} 个智能体"}
        except Exception as e:
            return {"error": f"保存失败: {e}"}


# 全局单例
fastagi_client = FastAGIClient()
