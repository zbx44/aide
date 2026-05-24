from __future__ import annotations
"""智能体广场API路由"""

import asyncio
import json
import logging
import uuid
from pathlib import Path
from typing import List, Optional

from fastapi import APIRouter, File, HTTPException, Query, UploadFile
from fastapi.responses import StreamingResponse

from core.fastagi import fastagi_client

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/agent", tags=["智能体广场"])


# ===== 智能体列表 =====

@router.get("/list")
async def list_agents():
    """获取智能体列表"""
    agents = fastagi_client.get_agents()
    return {"agents": agents, "count": len(agents)}


@router.get("/{agent_id}")
async def get_agent(agent_id: str):
    """获取智能体详情"""
    agent = fastagi_client.get_agent(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="智能体不存在")
    return agent


# ===== 对话 =====

class AgentChatRequest:
    """智能体对话请求"""
    def __init__(
        self,
        agent_id: str,
        query: str,
        conversation_id: str = "",
        user: str = "aide",
        inputs: Optional[dict] = None,
        files: Optional[List[dict]] = None,
        stream: bool = False,
    ):
        self.agent_id = agent_id
        self.query = query
        self.conversation_id = conversation_id
        self.user = user
        self.inputs = inputs
        self.files = files
        self.stream = stream


@router.post("/chat")
async def agent_chat(req: dict):
    """阻塞模式对话"""
    agent_id = req.get("agent_id", "")
    query = req.get("query", "")
    if not agent_id or not query:
        raise HTTPException(status_code=400, detail="缺少 agent_id 或 query")

    result = await fastagi_client.chat(
        agent_id=agent_id,
        query=query,
        conversation_id=req.get("conversation_id", ""),
        user=req.get("user", "aide"),
        inputs=req.get("inputs"),
        files=req.get("files"),
    )

    if "error" in result:
        raise HTTPException(status_code=500, detail=result["error"])
    return result


@router.post("/chat/stream")
async def agent_chat_stream(req: dict):
    """流式模式对话"""
    agent_id = req.get("agent_id", "")
    query = req.get("query", "")
    if not agent_id or not query:
        raise HTTPException(status_code=400, detail="缺少 agent_id 或 query")

    async def event_stream():
        conv_id = req.get("conversation_id", "")
        async for chunk in fastagi_client.chat_stream(
            agent_id=agent_id,
            query=query,
            conversation_id=conv_id,
            user=req.get("user", "aide"),
            inputs=req.get("inputs"),
            files=req.get("files"),
        ):
            event = chunk.get("event", "message")
            data = chunk.get("data", {})
            yield {"data": json.dumps(data, ensure_ascii=False), "event": event}

        # 发送结束事件
        yield {"data": json.dumps({"type": "done"}, ensure_ascii=False), "event": "done"}

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


# ===== 文件上传 =====

@router.post("/{agent_id}/upload")
async def agent_upload_file(agent_id: str, file: UploadFile = File(...), user: str = Query("aide")):
    """上传文件到智能体"""
    import tempfile
    import shutil

    # 保存到临时文件
    suffix = Path(file.filename or "upload").suffix
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        shutil.copyfileobj(file.file, tmp)
        tmp_path = tmp.name

    try:
        result = await fastagi_client.upload_file(
            agent_id=agent_id,
            file_path=tmp_path,
            file_name=file.filename or "upload",
            user=user,
        )
        if "error" in result:
            raise HTTPException(status_code=500, detail=result["error"])
        return result
    finally:
        Path(tmp_path).unlink(missing_ok=True)


# ===== 配置管理 =====

@router.get("/config")
async def get_config():
    """获取FastAGI连接配置"""
    return fastagi_client.get_fastagi_config()


@router.post("/config")
async def update_config(req: dict):
    """更新FastAGI连接配置"""
    result = await fastagi_client.update_fastagi_config(
        base_url=req.get("base_url", ""),
        app_id=req.get("app_id", ""),
        secret_key=req.get("secret_key", ""),
    )
    if "error" in result:
        raise HTTPException(status_code=500, detail=result["error"])
    return result


@router.post("/agents/save")
async def save_agents(req: dict):
    """保存智能体列表"""
    agents = req.get("agents", [])
    result = await fastagi_client.save_agents(agents)
    if "error" in result:
        raise HTTPException(status_code=500, detail=result["error"])
    return result


@router.post("/reload")
async def reload_config():
    """重新加载配置"""
    fastagi_client.reload_config()
    return {"message": "配置已重新加载", "agents_count": len(fastagi_client.agents)}
