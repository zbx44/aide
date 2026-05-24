"""数据模型"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Dict, List, Optional, Union

from pydantic import BaseModel, Field


# ===== 文档相关 =====

class DocCreateRequest(BaseModel):
    """创建文档请求"""
    description: str = Field(..., description="自然语言描述文档内容")
    doc_type: str = Field("docx", description="文档类型: docx/xlsx/pptx")
    extra_context: str = Field("", description="额外上下文")


class DocModifyRequest(BaseModel):
    """修改文档请求"""
    instruction: str = Field(..., description="自然语言修改指令")


class DocResponse(BaseModel):
    """文档响应"""
    doc_id: str
    type: str
    title: str
    file_path: str


# ===== 分析任务相关 =====

class TaskCreateRequest(BaseModel):
    """创建分析任务请求"""
    config_yaml: str = Field(..., description="任务YAML配置")


class TaskRunRequest(BaseModel):
    """手动执行任务请求"""
    task_name: str = Field(..., description="任务名称")


class TaskResponse(BaseModel):
    """任务响应"""
    name: str
    enabled: bool = True
    schedule: dict = {}
    description: str = ""


# ===== 对话相关 =====

class ChatRequest(BaseModel):
    """对话请求"""
    message: str = Field(..., description="用户消息")
    conversation_id: Optional[str] = Field(None, description="对话ID，多轮对话时传入")
    stream: bool = Field(True, description="是否流式输出")
    user_id: Optional[str] = Field("default", description="用户ID，用于渐进式披露和记忆隔离")
    kb_ids: Optional[List[str]] = Field(None, description="参考的知识库ID列表")
    file_contexts: Optional[List[Dict]] = Field(None, description="上传文件上下文 [{filename, text, type, image_base64?}]")


class ChatMessage(BaseModel):
    """对话消息"""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    conversation_id: str
    role: str  # user / assistant
    content: str
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat())


# ===== OA流程相关 =====

class OAStartProcessRequest(BaseModel):
    """发起OA流程请求"""
    template_code: str = Field(..., description="模板编号")
    subject: str = Field("", description="流程标题")
    form_data: dict = Field({}, description="表单数据")
    draft: bool = Field(False, description="True=保存待发，False=直接发送")
    attachments: List[str] = Field([], description="附件ID列表")


class OAUploadRequest(BaseModel):
    """OA上传附件请求（文件通过multipart上传，此为元数据）"""
    pass


# ===== 通知相关 =====

class NotifyRequest(BaseModel):
    """发送通知请求"""
    channel: str = Field(..., description="通知渠道: email/seeyon/qq")
    target: str = Field(..., description="通知目标")
    content: str = Field(..., description="通知内容")
    attachments: List[str] = Field([], description="附件路径列表")


# ===== 工具相关 =====

class OCRRequest(BaseModel):
    """OCR识别请求（图片通过multipart上传）"""
    pass


class ToolExecuteRequest(BaseModel):
    """工具执行请求"""
    name: str = Field(..., description="工具名称")
    params: dict = Field({}, description="工具参数")


# ===== 进化相关 =====

class EvolutionRequest(BaseModel):
    """自我进化请求"""
    instruction: str = Field(..., description="进化指令，如'回答更简洁'、'记住我喜欢表格格式'")


# ===== Skill管理 =====

class SkillCreateRequest(BaseModel):
    """创建Skill请求"""
    name: str = Field(..., description="Skill标识名")
    display_name: str = Field(..., description="显示名称")
    description: str = Field(..., description="功能描述")
    level: int = Field(1, ge=1, le=3, description="披露等级: 1=基础, 2=进阶, 3=高级")
    parameters: dict = Field({"type": "object", "properties": {}}, description="参数JSON Schema")
    category: str = Field("custom", description="分类")
