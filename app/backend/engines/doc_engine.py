from __future__ import annotations
"""文档生成引擎"""
import json
import logging
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional

from config.settings import settings
from core.llm import llm_client

logger = logging.getLogger(__name__)

# 文档JSON状态的system prompt
DOC_SYSTEM_PROMPT = """你是一个专业的文档生成助手。用户用自然语言描述需求，你需要生成结构化的文档JSON。

严格按以下格式输出JSON，不要输出其他内容：

对于Word文档(.docx)：
{
  "title": "文档标题",
  "sections": [
    {"type": "heading", "level": 1, "text": "一级标题"},
    {"type": "heading", "level": 2, "text": "二级标题"},
    {"type": "paragraph", "text": "段落内容"},
    {"type": "table", "headers": ["列1", "列2"], "rows": [["值1", "值2"]]},
    {"type": "chart", "chart_type": "bar|line|pie|scatter", "title": "图表标题", 
     "x_axis": "X轴标签", "y_axis": "Y轴标签",
     "data": {"labels": ["A","B"], "datasets": [{"label": "系列1", "values": [1,2]}]}},
    {"type": "page_break": null}
  ]
}

对于Excel文档(.xlsx)：
{
  "title": "工作簿标题",
  "sheets": [
    {
      "name": "Sheet1",
      "headers": ["列1", "列2", "列3"],
      "rows": [["值1", "值2", "值3"]],
      "column_widths": [15, 20, 15],
      "chart": null  // 可选: {"type": "bar", "title": "...", "data_range": "A1:C5"}
    }
  ]
}

对于PPT文档(.pptx)：
{
  "title": "演示文稿标题",
  "slides": [
    {"layout": "title", "title": "封面标题", "subtitle": "副标题"},
    {"layout": "content", "title": "页面标题", 
     "body": [{"type": "text", "content": "内容"}, {"type": "bullet", "items": ["要点1","要点2"]}]},
    {"layout": "chart", "title": "图表页", 
     "chart": {"chart_type": "bar", "title": "...", "data": {"labels": [...], "datasets": [...]}}}
  ]
}

注意：
- 内容要充实、专业，不要只写占位符
- 图表数据要合理
- 只输出JSON，不要包裹在```代码块中
"""


class DocEngine:
    """文档生成引擎"""

    def __init__(self):
        self.output_dir = settings.OUTPUT_DIR
        self.output_dir.mkdir(parents=True, exist_ok=True)

    async def create_doc(self, description: str, doc_type: str = "docx",
                         extra_context: str = "") -> dict:
        """根据自然语言描述创建文档"""
        doc_id = str(uuid.uuid4())

        messages = [
            {"role": "system", "content": DOC_SYSTEM_PROMPT},
            {"role": "user", "content": f"请生成一个{doc_type.upper()}文档：{description}\n{extra_context}"}
        ]

        # 调用LLM生成文档JSON
        doc_json = llm_client.chat_json(messages, temperature=0.5)

        # 构建文档状态
        doc_state = {
            "doc_id": doc_id,
            "type": doc_type,
            "title": doc_json.get("title", "未命名文档"),
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
            "content": doc_json,
        }

        # 渲染为文件
        file_path = await self._render(doc_state)

        return {
            "doc_id": doc_id,
            "type": doc_type,
            "title": doc_state["title"],
            "file_path": str(file_path),
        }

    async def modify_doc(self, doc_id: str, instruction: str,
                          current_state: dict) -> dict:
        """根据自然语言指令修改文档"""
        messages = [
            {"role": "system", "content": DOC_SYSTEM_PROMPT},
            {"role": "user", "content": f"当前文档状态：\n{json.dumps(current_state['content'], ensure_ascii=False, indent=2)}"},
            {"role": "user", "content": f"请修改文档：{instruction}\n输出修改后的完整JSON"}
        ]

        doc_json = llm_client.chat_json(messages, temperature=0.5)

        # 更新状态
        current_state["content"] = doc_json
        current_state["title"] = doc_json.get("title", current_state["title"])
        current_state["updated_at"] = datetime.now().isoformat()

        # 重新渲染
        file_path = await self._render(current_state)

        return {
            "doc_id": doc_id,
            "type": current_state["type"],
            "title": current_state["title"],
            "file_path": str(file_path),
        }

    async def _render(self, doc_state: dict) -> Path:
        """根据文档状态渲染文件"""
        doc_type = doc_state["type"]
        content = doc_state["content"]
        title = doc_state.get("title", "未命名")
        doc_id = doc_state["doc_id"]

        # 创建文档专属输出目录
        doc_dir = self.output_dir / doc_id
        doc_dir.mkdir(parents=True, exist_ok=True)

        if doc_type == "docx":
            from renderers.docx_renderer import render_docx
            file_path = doc_dir / f"{title}.docx"
            render_docx(content, file_path)
        elif doc_type == "xlsx":
            from renderers.xlsx_renderer import render_xlsx
            file_path = doc_dir / f"{title}.xlsx"
            render_xlsx(content, file_path)
        elif doc_type == "pptx":
            from renderers.pptx_renderer import render_pptx
            file_path = doc_dir / f"{title}.pptx"
            render_pptx(content, file_path)
        else:
            raise ValueError(f"不支持的文档类型: {doc_type}")

        return file_path


# 全局单例
doc_engine = DocEngine()
