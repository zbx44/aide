from __future__ import annotations
"""定时数据分析引擎"""
import json
import logging
import uuid
from datetime import datetime
from pathlib import Path
from typing import List, Optional

import yaml

from config.settings import settings
from core.llm import llm_client
from core.database import dm_database

logger = logging.getLogger(__name__)

ANALYSIS_SYSTEM_PROMPT = """你是数据分析专家。请根据提供的数据库查询结果进行专业分析。
输出要求：
1. 结构清晰，使用标题和分段
2. 数据引用准确
3. 给出可操作的建议
4. 如有异常数据，重点指出

输出格式：直接输出Markdown格式内容。"""


class AnalysisEngine:
    """定时数据分析引擎"""

    def __init__(self):
        self.output_dir = settings.OUTPUT_DIR
        self.output_dir.mkdir(parents=True, exist_ok=True)

    async def run_task(self, config: dict) -> dict:
        """执行分析任务"""
        task_name = config.get("name", "unnamed")
        logger.info(f"开始执行分析任务: {task_name}")

        try:
            # 1. 从达梦数据库获取数据
            sql = config.get("sql", "")
            data = []
            if sql:
                data = dm_database.execute_query(sql)

            # 2. 拼装Prompt
            prompt = config.get("prompt", "请分析以下数据：\n{{data}}")
            data_str = json.dumps(data, ensure_ascii=False, indent=2) if data else "无数据"
            prompt = prompt.replace("{{data}}", data_str)

            messages = [
                {"role": "system", "content": ANALYSIS_SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ]

            # 3. 调用LLM分析
            analysis_result = llm_client.chat(messages, temperature=0.3)

            # 4. 渲染输出文档
            output_config = config.get("output", {})
            output_format = output_config.get("format", "docx")
            template = output_config.get("template")
            
            # 生成文件名
            from jinja2 import Template as JinjaTemplate
            filename_template = output_config.get("filename", "分析报告_{{date}}.docx")
            filename = JinjaTemplate(filename_template).render(
                date=datetime.now().strftime("%Y%m%d"),
                time=datetime.now().strftime("%H%M%S"),
                name=task_name,
            )

            # 构建文档内容
            doc_content = {
                "title": config.get("name", "分析报告"),
                "sections": self._markdown_to_sections(analysis_result),
            }

            # 渲染文档
            save_path = Path(output_config.get("save_path", "output/reports/"))
            save_path.mkdir(parents=True, exist_ok=True)
            file_path = save_path / filename

            if output_format == "docx":
                from renderers.docx_renderer import render_docx
                render_docx(doc_content, file_path)
            elif output_format == "xlsx":
                from renderers.xlsx_renderer import render_xlsx
                render_xlsx(doc_content, file_path)
            else:
                # 默认markdown
                with open(file_path.with_suffix(".md"), "w", encoding="utf-8") as f:
                    f.write(analysis_result)

            # 5. 推送通知（可选）
            notify_config = config.get("notify", {})
            if notify_config.get("enabled"):
                # 后续实现
                logger.info(f"推送通知: {notify_config}")

            result = {
                "task_name": task_name,
                "status": "success",
                "data_rows": len(data),
                "output_file": str(file_path),
                "executed_at": datetime.now().isoformat(),
            }
            logger.info(f"分析任务完成: {task_name}, 输出: {file_path}")
            return result

        except Exception as e:
            logger.error(f"分析任务失败: {task_name}, 错误: {e}")
            return {
                "task_name": task_name,
                "status": "failed",
                "error": str(e),
                "executed_at": datetime.now().isoformat(),
            }

    def _markdown_to_sections(self, md_text: str) -> List[dict]:
        """将Markdown分析结果转换为文档sections"""
        sections = []
        for line in md_text.split("\n"):
            line = line.rstrip()
            if not line:
                continue
            if line.startswith("### "):
                sections.append({"type": "heading", "level": 3, "text": line[4:]})
            elif line.startswith("## "):
                sections.append({"type": "heading", "level": 2, "text": line[3:]})
            elif line.startswith("# "):
                sections.append({"type": "heading", "level": 1, "text": line[2:]})
            elif line.startswith("- ") or line.startswith("* "):
                sections.append({"type": "bullet", "text": line[2:]})
            else:
                sections.append({"type": "paragraph", "text": line})
        return sections

    async def run_manual(self, task_config: dict) -> dict:
        """手动执行一次分析任务"""
        return await self.run_task(task_config)

    async def create_task(self, config_yaml: str) -> dict:
        """创建分析任务配置"""
        config = yaml.safe_load(config_yaml)
        task_name = config.get("name", "unnamed")
        
        # 保存到tasks目录
        task_file = settings.TASKS_DIR / f"{task_name}.yaml"
        with open(task_file, "w", encoding="utf-8") as f:
            f.write(config_yaml)

        return {"name": task_name, "file": str(task_file)}

    async def list_tasks(self) -> List[dict]:
        """列出所有任务"""
        tasks = []
        for task_file in settings.TASKS_DIR.glob("*.yaml"):
            with open(task_file, "r", encoding="utf-8") as f:
                config = yaml.safe_load(f)
            tasks.append({
                "name": config.get("name", task_file.stem),
                "enabled": config.get("enabled", True),
                "schedule": config.get("schedule", {}),
                "description": config.get("description", ""),
            })
        return tasks


# 全局单例
analysis_engine = AnalysisEngine()
