from __future__ import annotations
"""Skill工具系统 - 注册、管理、渐进式披露、LLM function calling集成

核心设计：
1. Skill注册：每个skill有名称、描述、参数schema、执行函数、难度等级
2. 渐进式披露：根据用户交互深度，逐步展示更多skill
   - Level 1 (基础): 通用对话、简单查询
   - Level 2 (进阶): 文档生成、数据分析
   - Level 3 (高级): OA流程、数据库操作、系统管理
3. LLM Function Calling：将skill转换为OpenAI function格式，让vLLM自主决定调用
4. 自动发现：从skills/目录自动加载skill定义
"""
import json
import logging
import os
import re
import subprocess
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from config.settings import settings
from core.llm import llm_client
from core.memory import memory_system

logger = logging.getLogger(__name__)

# Skill内置定义
# ===== 技能可见性 & 默认启停配置 =====
# internal: 后台工具，LLM可调度但不对用户展示，用户也关不掉（系统必需）
# hidden:   默认不展示给用户，但用户可以在设置中手动开启
# visible:  默认展示给用户（用户可关闭）
_DEFAULTS = {
    "web_search":        {"visibility": "visible",  "enabled": True},
    "calculate":         {"visibility": "visible",  "enabled": True},
    "read_file":          {"visibility": "internal", "enabled": True},  # 后台工具，不暴露给用户
    "write_file":         {"visibility": "internal", "enabled": True},
    "edit_file":          {"visibility": "internal", "enabled": True},
    "list_dir":           {"visibility": "internal", "enabled": True},  # 已并入 local_file_search.browse
    "run_shell":          {"visibility": "internal", "enabled": True},
    "git_operation":      {"visibility": "hidden",   "enabled": True},  # 开发者工具，默认隐藏
    "create_document":    {"visibility": "visible",  "enabled": True},
    "analyze_data":       {"visibility": "visible",  "enabled": True},
    "ocr_recognize":      {"visibility": "visible",  "enabled": True},
    "query_database":     {"visibility": "hidden",   "enabled": False}, # 企业专属，默认关闭
    "start_oa_process":   {"visibility": "hidden",   "enabled": False},
    "send_notification":  {"visibility": "visible",  "enabled": True},
    "manage_schedule":    {"visibility": "hidden",   "enabled": True},  # 定时任务，非日常高级功能
    "evolve_self":        {"visibility": "hidden",   "enabled": True},  # 自我进化，不主动展示
    "local_file_search":  {"visibility": "visible",  "enabled": True},
    "skill_toggle":       {"visibility": "visible",  "enabled": True},
}

BUILTIN_SKILLS = {
    "web_search": {
        "name": "web_search",
        "display_name": "网络搜索",
        "description": "搜索互联网获取最新信息",
        "level": 1,
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "搜索关键词"}
            },
            "required": ["query"]
        },
        "category": "information",
    },
    "calculate": {
        "name": "calculate",
        "display_name": "计算器",
        "description": "执行数学计算，支持复杂表达式",
        "level": 1,
        "parameters": {
            "type": "object",
            "properties": {
                "expression": {"type": "string", "description": "数学表达式"}
            },
            "required": ["expression"]
        },
        "category": "utility",
    },
    "read_file": {
        "name": "read_file",
        "display_name": "读取文件",
        "description": "读取本地文件内容（内部工具）",
        "level": 1,
        "parameters": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "文件路径"},
                "lines": {"type": "integer", "description": "读取行数(0=全部)"}
            },
            "required": ["path"]
        },
        "category": "local_tool",
    },
    "write_file": {
        "name": "write_file",
        "display_name": "写入文件",
        "description": "创建或覆盖写入文件内容（内部工具）",
        "level": 2,
        "parameters": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "文件路径"},
                "content": {"type": "string", "description": "文件内容"}
            },
            "required": ["path", "content"]
        },
        "category": "local_tool",
    },
    "edit_file": {
        "name": "edit_file",
        "display_name": "修改文件",
        "description": "修改文件中指定内容（内部工具）",
        "level": 2,
        "parameters": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "文件路径"},
                "old_text": {"type": "string", "description": "要替换的原文"},
                "new_text": {"type": "string", "description": "替换后的内容"}
            },
            "required": ["path", "old_text", "new_text"]
        },
        "category": "local_tool",
    },
    "list_dir": {
        "name": "list_dir",
        "display_name": "列出目录",
        "description": "列出目录下的文件和文件夹（内部工具，已并入文件检索的browse）",
        "level": 1,
        "parameters": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "目录路径"},
                "recursive": {"type": "boolean", "description": "是否递归"}
            },
            "required": ["path"]
        },
        "category": "local_tool",
    },
    "run_shell": {
        "name": "run_shell",
        "display_name": "执行命令",
        "description": "执行Shell命令并返回输出（内部工具）",
        "level": 3,
        "parameters": {
            "type": "object",
            "properties": {
                "command": {"type": "string", "description": "Shell命令"},
                "timeout": {"type": "integer", "description": "超时秒数(默认30)"}
            },
            "required": ["command"]
        },
        "category": "local_tool",
    },
    "git_operation": {
        "name": "git_operation",
        "display_name": "Git操作",
        "description": "执行Git操作：status/log/diff/add/commit/pull/push/checkout等",
        "level": 2,
        "parameters": {
            "type": "object",
            "properties": {
                "action": {"type": "string", "description": "Git子命令如status/log/diff/add/commit等"},
                "args": {"type": "string", "description": "额外参数"},
                "repo_path": {"type": "string", "description": "仓库路径(默认当前目录)"}
            },
            "required": ["action"]
        },
        "category": "local_tool",
    },
    "create_document": {
        "name": "create_document",
        "display_name": "生成文档",
        "description": "根据自然语言描述生成Word/Excel/PPT文档",
        "level": 2,
        "parameters": {
            "type": "object",
            "properties": {
                "description": {"type": "string", "description": "文档内容描述"},
                "doc_type": {"type": "string", "enum": ["docx", "xlsx", "pptx"], "description": "文档类型"}
            },
            "required": ["description"]
        },
        "category": "document",
    },
    "analyze_data": {
        "name": "analyze_data",
        "display_name": "数据分析",
        "description": "从数据库查询数据并进行分析，生成分析报告",
        "level": 2,
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "分析需求描述"},
                "sql": {"type": "string", "description": "SQL查询语句（可选）"}
            },
            "required": ["query"]
        },
        "category": "analysis",
    },
    "ocr_recognize": {
        "name": "ocr_recognize",
        "display_name": "OCR识别",
        "description": "识别图片中的文字",
        "level": 2,
        "parameters": {
            "type": "object",
            "properties": {
                "image_path": {"type": "string", "description": "图片文件路径"}
            },
            "required": ["image_path"]
        },
        "category": "tool",
    },
    "query_database": {
        "name": "query_database",
        "display_name": "数据库查询",
        "description": "执行SQL查询达梦数据库",
        "level": 3,
        "parameters": {
            "type": "object",
            "properties": {
                "sql": {"type": "string", "description": "SQL查询语句"}
            },
            "required": ["sql"]
        },
        "category": "database",
    },
    "start_oa_process": {
        "name": "start_oa_process",
        "display_name": "发起OA流程",
        "description": "在致远OA系统中发起审批流程",
        "level": 3,
        "parameters": {
            "type": "object",
            "properties": {
                "template_code": {"type": "string", "description": "流程模板编号"},
                "subject": {"type": "string", "description": "∙程标题"},
                "form_data": {"type": "object", "description": "表单数据"}
            },
            "required": ["template_code", "subject"]
        },
        "category": "oa",
    },
    "send_notification": {
        "name": "send_notification",
        "display_name": "发送通知",
        "description": "通过邮件/QQ/致远OA发送通知消息",
        "level": 2,
        "parameters": {
            "type": "object",
            "properties": {
                "channel": {"type": "string", "enum": ["email", "qq", "seeyon"], "description": "通知渠道"},
                "target": {"type": "string", "description": "通知目标"},
                "content": {"type": "string", "description": "通知内容"}
            },
            "required": ["channel", "target", "content"]
        },
        "category": "notification",
    },
    "manage_schedule": {
        "name": "manage_schedule",
        "display_name": "定时任务管理",
        "description": "创建、查看、管理定时分析任务",
        "level": 2,
        "parameters": {
            "type": "object",
            "properties": {
                "action": {"type": "string", "enum": ["list", "create", "run", "delete"], "description": "操作类型"},
                "config": {"type": "object", "description": "任务配置（create时需要）"}
            },
            "required": ["action"]
        },
        "category": "task",
    },
    "evolve_self": {
        "name": "evolve_self",
        "display_name": "自我进化",
        "description": "根据指令改进自己的行为方式、回答风格",
        "level": 3,
        "parameters": {
            "type": "object",
            "properties": {
                "instruction": {"type": "string", "description": "改进指令，如'回答更简洁'、'记住我喜欢表格格式'"}
            },
            "required": ["instruction"]
        },
        "category": "system",
    },
    "local_file_search": {
        "name": "local_file_search",
        "display_name": "本地文件检索",
        "description": "支持通过自然语言查询，同时检索文件（按文件名）和目录（按目录名），基于语义相似度返回结果。支持筛选（如只看Excel文件、只看文件夹）。首次使用会后台创建向量索引库，不阻塞操作。",
        "level": 1,
        "parameters": {
            "type": "object",
            "properties": {
                "action": {"type": "string", "enum": ["search", "add_dir", "remove_dir", "scan", "list_dirs", "stats", "progress", "browse"], "description": "操作类型: search=语义检索, add_dir=添加索引目录, remove_dir=移除目录, scan=扫描建索引, list_dirs=查看目录, stats=索引状态, progress=查看进度, browse=浏览目录内容("},
                "query": {"type": "string", "description": "自然语言描述(search时必填)，如'2023年产品会议的PPT''存放客户合同的文件夹'"},
                "dir_path": {"type": "string", "description": "目录路径(add_dir时必填)，如'D:/工作'"},
                "dir_id": {"type": "string", "description": "目录ID(remove_dir/scan时可选)"},
                "entry_type": {"type": "string", "enum": ["file", "dir"], "description": "筛选类型: file=只看文件, dir=只看文件夹, 不填=全部"},
                "ext_filter": {"type": "string", "description": "扩展名筛选(不加点)，如'xlsx''pdf''docx'"},
                "browse_path": {"type": "string", "description": "要浏览的目录路径(browse时必填)"},
                "recursive": {"type": "boolean", "description": "是否递归浏览子目录(browse时可选，默认否)"},
                "limit": {"type": "integer", "description": "返回结果数量(默认10)"}
            },
            "required": ["action"]
        },
        "category": "local_tool",
    },
    "skill_toggle": {
        "name": "skill_toggle",
        "display_name": "技能开关",
        "description": "查看所有技能状态，开启或关闭某个技能。如: '查看技能列表' '关闭Git操作' '开启数据库查询'",
        "level": 1,
        "parameters": {
            "type": "object",
            "properties": {
                "action": {"type": "string", "enum": ["list", "toggle"], "description": "list=查看所有技能状态, toggle=开关某个技能"},
                "name": {"type": "string", "description": "技能名(toggle时必填)"},
                "enabled": {"type": "boolean", "description": "true=开启, false=关闭(toggle时必填)"}
            },
            "required": ["action"]
        },
        "category": "system",
    },
}


class SkillManager:
    """Skill管理器 - 注册、发现、渐进式披露、Function Calling"""

    def __init__(self):
        self._skills: Dict[str, dict] = {}
        self._executors: Dict[str, Callable] = {}
        self._skill_usage: Dict[str, int] = {}  # skill使用计数
        self._user_level: Dict[str, int] = {}  # 用户解锁等级
        self.skills_dir = settings.DATA_DIR / "skills"
        self.skills_dir.mkdir(parents=True, exist_ok=True)

        # 技能启停配置（持久化到文件）
        self._skill_config_path = settings.DATA_DIR / "skill_config.json"
        self._skill_config: Dict[str, dict] = {}  # {name: {enabled: bool, visibility: str}}
        self._load_skill_config()

        # 注册内置skills
        for name, skill_def in BUILTIN_SKILLS.items():
            self.register_skill(skill_def)

        # 从文件系统加载自定义skills
        self._load_custom_skills()

    def register_skill(self, skill_def: dict, executor: Callable = None):
        """注册一个skill"""
        name = skill_def["name"]
        self._skills[name] = skill_def
        if executor:
            self._executors[name] = executor
        self._skill_usage.setdefault(name, 0)
        logger.debug(f"注册skill: {name} (level {skill_def.get('level', 1)})")

    def _load_custom_skills(self):
        """从skills/目录加载自定义skill定义"""
        for skill_file in self.skills_dir.glob("*.json"):
            try:
                with open(skill_file, "r", encoding="utf-8") as f:
                    skill_def = json.load(f)
                if "name" in skill_def:
                    self.register_skill(skill_def)
                    logger.info(f"加载自定义skill: {skill_def['name']}")
            except Exception as e:
                logger.error(f"加载skill文件失败 {skill_file}: {e}")

    # ===== 技能启停配置 =====

    def _load_skill_config(self):
        """从文件加载技能启停配置"""
        # 先用默认值初始化
        for name, defaults in _DEFAULTS.items():
            self._skill_config[name] = dict(defaults)
        # 覆盖用户配置
        if self._skill_config_path.exists():
            try:
                with open(self._skill_config_path, "r", encoding="utf-8") as f:
                    saved = json.load(f)
                for name, cfg in saved.items():
                    if name in self._skill_config:
                        self._skill_config[name].update(cfg)
                    else:
                        # 自定义skill也保存到配置了
                        self._skill_config[name] = cfg
                logger.info(f"加载技能配置: {len(saved)}项")
            except Exception as e:
                logger.warning(f"加载技能配置失败: {e}")

    def _save_skill_config(self):
        """持久化技能配置"""
        try:
            with open(self._skill_config_path, "w", encoding="utf-8") as f:
                json.dump(self._skill_config, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"保存技能配置失败: {e}")

    def toggle_skill(self, name: str, enabled: Optional[bool] = None) -> dict:
        """开启/关闭一个技能
        Args:
            name: 技能名
            enabled: True=开启, False=关闭, None=切换
        Returns: 操作结果
        """
        if name not in self._skills:
            return {"error": f"未知技能: {name}"}
        cfg = self._skill_config.setdefault(name, {})
        # internal类型的技能不允许用户关闭
        visibility = cfg.get("visibility", _DEFAULTS.get(name, {}).get("visibility", "visible"))
        if visibility == "internal":
            return {"error": f"'{name}' 是系统内部工具，无法关闭"}
        if enabled is None:
            enabled = not cfg.get("enabled", _DEFAULTS.get(name, {}).get("enabled", True))
        cfg["enabled"] = enabled
        self._save_skill_config()
        return {
            "name": name,
            "enabled": enabled,
            "visibility": visibility,
            "message": f"{'已开启' if enabled else '已关闭'}技能: {self._skills[name].get('display_name', name)}",
        }

    def get_skill_config(self, name: str) -> dict:
        """获取单个技能的配置"""
        default = _DEFAULTS.get(name, {"visibility": "visible", "enabled": True})
        return {**default, **self._skill_config.get(name, {})}

    def get_all_skill_configs(self, include_internal: bool = False) -> list:
        """获取所有技能配置（供设置页面展示）"""
        result = []
        for name, skill in self._skills.items():
            cfg = self.get_skill_config(name)
            # 不展示内部工具
            if not include_internal and cfg.get("visibility") == "internal":
                continue
            # 已禁用的也展示，让用户可以重新开启
            result.append({
                "name": name,
                "display_name": skill.get("display_name", name),
                "description": skill.get("description", ""),
                "category": skill.get("category", ""),
                "level": skill.get("level", 1),
                "enabled": cfg.get("enabled", True),
                "visibility": cfg.get("visibility", "visible"),
                "usage_count": self._skill_usage.get(name, 0),
                "is_builtin": name in BUILTIN_SKILLS,
            })
        # 按分类排序
        cat_order = {"information": 0, "utility": 1, "local_tool": 2, "document": 3, "analysis": 4, "tool": 5, "notification": 6, "task": 7, "database": 8, "oa": 9, "system": 10}
        result.sort(key=lambda x: (cat_order.get(x["category"], 99), x["name"]))
        return result

    def save_custom_skill(self, skill_def: dict) -> str:
        """保存自定义skill到文件"""
        name = skill_def["name"]
        file_path = self.skills_dir / f"{name}.json"
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(skill_def, f, ensure_ascii=False, indent=2)
        self.register_skill(skill_def)
        return str(file_path)

    def delete_skill(self, name: str) -> bool:
        """删除自定义skill"""
        if name in BUILTIN_SKILLS:
            return False  # 不允许删除内置skill
        if name in self._skills:
            del self._skills[name]
            self._executors.pop(name, None)
            file_path = self.skills_dir / f"{name}.json"
            if file_path.exists():
                file_path.unlink()
            return True
        return False

    # ===== 渐进式披露 =====

    def get_visible_skills(self, user_id: str = "default") -> List[dict]:
        """获取当前用户可见且已启用的skills

        过滤逻辑：
        1. enabled=False → 不展示（除非是 internal）
        2. visibility=internal → 不对用户展示（但仍可被LLM调用）
        3. visibility=hidden → 只在用户手动开启后才展示
        4. visibility=visible → 正常展示
        """
        current_level = self._user_level.get(user_id, 1)

        # 计算是否应该升级
        level1_usage = sum(
            self._skill_usage.get(name, 0)
            for name, skill in self._skills.items()
            if skill.get("level", 1) == 1
        )
        level2_usage = sum(
            self._skill_usage.get(name, 0)
            for name, skill in self._skills.items()
            if skill.get("level", 1) == 2
        )

        if current_level < 2 and level1_usage >= 3:
            current_level = 2
            self._user_level[user_id] = 2
            logger.info(f"用户 {user_id} 解锁Level 2 skills")

        if current_level < 3 and level2_usage >= 5:
            current_level = 3
            self._user_level[user_id] = 3
            logger.info(f"用户 {user_id} 解锁Level 3 skills")

        self._user_level.setdefault(user_id, current_level)

        # 过滤可见skills
        visible = []
        for name, skill in self._skills.items():
            cfg = self.get_skill_config(name)
            level_ok = skill.get("level", 1) <= current_level
            enabled = cfg.get("enabled", True)
            visibility = cfg.get("visibility", "visible")

            # internal 不对用户展示
            if visibility == "internal":
                continue
            # 未启用的不展示
            if not enabled:
                continue
            # 等级不够不展示
            if not level_ok:
                continue

            visible.append({
                **skill,
                "usage_count": self._skill_usage.get(name, 0),
            })

        return visible

    def get_skill_level_info(self, user_id: str = "default") -> dict:
        """获取用户skill等级信息"""
        current_level = self._user_level.get(user_id, 1)
        level1_usage = sum(
            self._skill_usage.get(name, 0)
            for name, skill in self._skills.items()
            if skill.get("level", 1) == 1
        )
        level2_usage = sum(
            self._skill_usage.get(name, 0)
            for name, skill in self._skills.items()
            if skill.get("level", 1) == 2
        )
        return {
            "current_level": current_level,
            "level1_usage": level1_usage,
            "level2_usage": level2_usage,
            "next_level_requirement": {
                1: "使用3次基础工具解锁进阶功能",
                2: "使用5次进阶工具解锁高级功能",
                3: "已解锁全部功能",
            }.get(current_level, ""),
        }

    # ===== Function Calling集成 =====

    def get_functions_schema(self, user_id: str = "default") -> List[dict]:
        """生成OpenAI Function Calling格式的工具列表

        过滤逻辑：
        - enabled=False → 不包含（连LLM也不给）
        - visibility=internal → 包含（LLM可以调用，只是不对用户展示）
        - 其他 → 正常包含
        """
        funcs = []
        for name, skill in self._skills.items():
            cfg = self.get_skill_config(name)
            if not cfg.get("enabled", True):
                continue  # 已禁用的不给LLM
            # internal和visible的都给LLM
            func_def = {
                "type": "function",
                "function": {
                    "name": skill["name"],
                    "description": skill["description"],
                    "parameters": skill.get("parameters", {
                        "type": "object",
                        "properties": {}
                    }),
                }
            }
            funcs.append(func_def)
        return funcs

    async def process_with_tools(self, messages: List[dict],
                                  user_id: str = "default",
                                  max_tool_calls: int = 5) -> dict:
        """带工具调用的对话处理（异步httpx实现）

        流程：
        1. 发送消息 + tools给LLM
        2. LLM决定是否调用工具
        3. 如果调用，执行工具，把结果追加到消息
        4. 再次让LLM生成回复
        5. 循环直到LLM不再调用工具或达到最大调用次数
        """
        functions = self.get_functions_schema(user_id)
        if not functions:
            content = llm_client.chat(messages)["content"]
            return {"content": content, "tool_calls": []}

        # 检测后端是否支持tools参数，不支持则跳过
        if not getattr(llm_client, 'supports_tools', True):
            content = llm_client.chat(messages)["content"]
            return {"content": content, "tool_calls": []}

        all_tool_calls = []
        all_thinking = []

        for round_num in range(max_tool_calls):
            # 使用httpx异步调用（非OpenAI SDK）
            try:
                payload = {
                    "model": llm_client.model,
                    "messages": messages,
                    "tools": functions,
                    "tool_choice": "auto",
                    "temperature": llm_client.temperature,
                    "max_tokens": llm_client.max_tokens,
                }
                resp = await llm_client.async_client.post(
                    llm_client._get_url(),
                    headers=llm_client._get_headers(),
                    json=payload,
                    timeout=30.0,
                )
                # 400通常意味着后端不支持tools参数
                if resp.status_code == 400:
                    logger.warning(f"LLM返回400（可能不支持tools），回退普通对话")
                    llm_client.supports_tools = False
                    content = llm_client.chat(messages)["content"]
                    return {"content": content, "tool_calls": []}
                resp.raise_for_status()
                data = resp.json()
            except Exception as e:
                logger.warning(f"Function calling不可用，回退普通对话: {e}")
                content = llm_client.chat(messages)["content"]
                return {"content": content, "tool_calls": []}

            choice = data["choices"][0]
            message = choice["message"]
            finish_reason = choice.get("finish_reason", "")

            # 解析思考内容
            raw_content = message.get("content") or ""
            parsed = llm_client._parse_thinking(raw_content)
            content_text = parsed["content"]
            thinking_text = parsed.get("thinking")
            if thinking_text:
                all_thinking.append(thinking_text)

            tool_call_list = message.get("tool_calls")

            # 如果没有工具调用，返回最终回复
            if not tool_call_list:
                # 检查是否还有未完成的工具链（思考模型可能会描述而不是调用）
                # 如果思考内容中提到需要调工具但没有实际调用，尝试提取并自动执行
                pending_tool = self._extract_pending_tool_call(thinking_text or "", content_text, functions)
                if pending_tool and round_num < max_tool_calls - 1:
                    logger.info(f"检测到思考中提到但未执行的工具调用: {pending_tool['name']}")
                    # 自己构造tool_call消息
                    tc_id = f"auto_{uuid.uuid4().hex[:8]}"
                    tool_call_list = [{
                        "id": tc_id,
                        "type": "function",
                        "function": {
                            "name": pending_tool["name"],
                            "arguments": json.dumps(pending_tool["arguments"], ensure_ascii=False)
                        }
                    }]
                    content_text = ""  # 清空描述性文本，让工具真正执行
                else:
                    # 清理内容中残留的工具调用XML标签
                    clean_content = self._clean_tool_tags(content_text)
                    return {
                        "content": clean_content,
                        "tool_calls": all_tool_calls,
                        "thinking": "\n\n".join(all_thinking) if all_thinking else None,
                    }

            # 处理工具调用
            messages.append({
                "role": "assistant",
                "content": content_text or raw_content,  # 保留原始内容给vLLM
                "tool_calls": [
                    {
                        "id": tc["id"],
                        "type": "function",
                        "function": tc["function"],
                    }
                    for tc in tool_call_list
                ]
            })

            for tc in tool_call_list:
                func_name = tc["function"]["name"]
                try:
                    func_args = json.loads(tc["function"]["arguments"])
                except (json.JSONDecodeError, TypeError):
                    func_args = {}

                # 记录使用
                self._skill_usage[func_name] = self._skill_usage.get(func_name, 0) + 1

                # 执行工具
                tool_result = await self._execute_skill(func_name, func_args)

                all_tool_calls.append({"name": func_name, "arguments": func_args, "result": tool_result})

                # 将结果追加到消息（剥离思考标签）
                result_str = json.dumps(tool_result, ensure_ascii=False) if not isinstance(tool_result, str) else tool_result
                # 清理结果中的思考标签避免污染后续对话
                result_clean = re.sub(r'<think>[\s\S]*?</think>', '', result_str)
                messages.append({
                    "role": "tool",
                    "tool_call_id": tc["id"],
                    "content": result_clean,
                })

                # 记忆：保存工具调用到长期记忆
                try:
                    memory_system.save_long_term(
                        category="fact",
                        content=f"调用了工具 {func_name}，参数: {json.dumps(func_args, ensure_ascii=False)[:100]}",
                        importance=0.3,
                    )
                except Exception:
                    pass

        # 达到最大调用次数，最后让LLM生成总结
        final_content = llm_client.chat(messages)["content"]
        return {"content": final_content, "tool_calls": all_tool_calls, "thinking": "\n\n".join(all_thinking) if all_thinking else None}

    def _extract_pending_tool_call(self, thinking: str, content: str, available_functions: List[dict]) -> Optional[dict]:
        """从思考过程或内容中提取模型提到但未实际执行的工具调用
        
        思考模型经常在思考中描述需要调用的工具但不生成实际的 tool_call，
        这个方法检测这种情况并提取出工具调用信息。
        支持：
        1. XML标签格式：<tool_name>json</tool_name>
        2. 自然语言描述："我需要调用xxx"
        3. JSON代码块：```json {"name": "xxx"} ```
        """
        text = f"{thinking} {content}"
        
        # 获取可用工具名称
        available_names = {f["function"]["name"] for f in available_functions}
        
        # ===== 策略1: 匹配XML标签格式 <tool_name>...</tool_name> =====
        for name in available_names:
            # 匹配 <local_file_search>...</local_file_search> 等格式
            xml_pattern = rf'<{name}>([\s\S]*?)</{name}>'
            xml_match = re.search(xml_pattern, text)
            if xml_match:
                inner = xml_match.group(1).strip()
                try:
                    args = json.loads(inner)
                    return {"name": name, "arguments": args}
                except json.JSONDecodeError:
                    # 尝试解析key=value格式
                    args = {}
                    for kv_match in re.finditer(r'(\w+)\s*[=：:]\s*["\']?([^"\'\s,>]+)', inner):
                        args[kv_match.group(1)] = kv_match.group(2)
                    if args:
                        return {"name": name, "arguments": args}
            
            # 匹配自闭合格式 <tool_name attr="val" />
            self_close = rf'<{name}\s+([^>]*?)/?>'
            sc_match = re.search(self_close, text)
            if sc_match:
                attrs_str = sc_match.group(1)
                args = {}
                for attr_match in re.finditer(r'(\w+)\s*=\s*["\']([^"\']*)["\']', attrs_str):
                    args[attr_match.group(1)] = attr_match.group(2)
                if args:
                    return {"name": name, "arguments": args}
        
        # ===== 策略2: 匹配JSON代码块中的工具调用 =====
        json_block_pattern = r'```(?:json)?\s*([\s\S]*?)```'
        for jb_match in re.finditer(json_block_pattern, text):
            try:
                parsed = json.loads(jb_match.group(1).strip())
                if isinstance(parsed, dict) and parsed.get("name") in available_names:
                    return {"name": parsed["name"], "arguments": parsed.get("arguments", parsed.get("parameters", {}))}
            except (json.JSONDecodeError, AttributeError):
                pass
        
        # ===== 策略3: 特定工具的语义提取 =====
        for name in available_names:
            if name != "local_file_search":
                continue
            
            # add_dir: 创建索引目录
            if any(kw in text for kw in ['创建索引', '添加目录', 'add_dir', '添加索引目录']):
                # 匹配Windows路径：D:\xxx 或 D:/xxx，支持中文
                path_patterns = [
                    r'([A-Z]:[\\/][\\/\w\-\s\u4e00-\u9fff.]+)',  # D:\测试文件
                    r'["\']([A-Z]:[\\/][^"\']*)["\']',  # "D:\test"
                    r'索引目录[：:]\s*([A-Z]:[\\/][\\/\w\-\s\u4e00-\u9fff.]+)',  # 索引目录：D:\xxx
                    r'目录[：:]\s*([A-Z]:[\\/][\\/\w\-\s\u4e00-\u9fff.]+)',
                ]
                for pp in path_patterns:
                    path_match = re.search(pp, text)
                    if path_match:
                        dir_path = path_match.group(1).strip()
                        return {"name": "local_file_search", "arguments": {"action": "add_dir", "dir_path": dir_path}}
            
            # scan: 扫描建立索引
            if any(kw in text for kw in ['扫描', 'scan', '建立索引']):
                dir_id_match = re.search(r'dir_id[":\s]+["\']?([\w-]+)', text)
                if dir_id_match:
                    return {"name": "local_file_search", "arguments": {"action": "scan", "dir_id": dir_id_match.group(1)}}
                return {"name": "local_file_search", "arguments": {"action": "scan"}}
            
            # search: 文件检索
            if any(kw in text for kw in ['检索文件', '搜索文件', 'file search', 'find file']):
                query_match = re.search(r'(?:查询|搜索|检索|关键词)["：:"\']?\s*([\u4e00-\u9fff\w]+)', text)
                if query_match:
                    return {"name": "local_file_search", "arguments": {"action": "search", "query": query_match.group(1)}}
        
        return None

    @staticmethod
    def _clean_tool_tags(text: str) -> str:
        """清理内容中残留的工具调用XML标签"""
        if not text:
            return text
        # 清理  格式
        text = re.sub(r'<(\w+)(\s+[^>]*)?>([\s\S]*?)</\1>', lambda m: m.group(3).strip() if not any(kw in m.group(1) for kw in ['local_file_search', 'calculate', 'web_search', 'query_database', 'read_file', 'write_file', 'edit_file', 'list_dir', 'run_shell', 'git_operation', 'create_document', 'analyze_data', 'start_oa_process', 'send_notification', 'manage_schedule', 'evolve_self', 'ocr_recognize']) else '', text)
        # 清理自闭合标签
        text = re.sub(r'<(\w+)(\s+[^>]*)?/>', '', text)
        # 清理多余空行
        text = re.sub(r'\n{3,}', '\n\n', text)
        return text.strip()

    async def _execute_skill(self, name: str, params: dict) -> Any:
        """执行skill"""
        if name in self._executors:
            try:
                result = self._executors[name](**params)
                if hasattr(result, '__awaitable__'):
                    result = await result
                return result
            except Exception as e:
                logger.error(f"Skill执行失败 {name}: {e}")
                return {"error": str(e)}

        # 内置skill的默认实现
        return await self._execute_builtin(name, params)

    async def _execute_builtin(self, name: str, params: dict) -> Any:
        """内置skill执行逻辑"""
        if name == "calculate":
            try:
                # 安全计算
                allowed = set("0123456789+-*/.() ")
                expr = params.get("expression", "")
                if not all(c in allowed for c in expr):
                    return {"error": "表达式包含不安全字符"}
                result = eval(expr)
                return {"result": result, "expression": expr}
            except Exception as e:
                return {"error": f"计算失败: {e}"}

        elif name == "web_search":
            # 网络搜索 - 需要配置搜索API
            return {"message": "网络搜索功能需要配置搜索API", "query": params.get("query")}

        elif name == "create_document":
            try:
                from engines.doc_engine import doc_engine
                result = await doc_engine.create_doc(
                    description=params.get("description", ""),
                    doc_type=params.get("doc_type", "docx"),
                )
                return result
            except Exception as e:
                return {"error": f"文档生成失败: {e}"}

        elif name == "analyze_data":
            try:
                from engines.analysis_engine import analysis_engine
                config = {
                    "name": "即时分析",
                    "sql": params.get("sql", ""),
                    "prompt": params.get("query", "请分析数据"),
                }
                result = await analysis_engine.run_manual(config)
                return result
            except Exception as e:
                return {"error": f"数据分析失败: {e}"}

        elif name == "query_database":
            try:
                from core.database import dm_database
                rows = dm_database.execute_query(params.get("sql", ""))
                return {"rows": rows, "count": len(rows)}
            except Exception as e:
                return {"error": f"数据库查询失败: {e}"}

        elif name == "start_oa_process":
            try:
                from notifiers.seeyon import seeyon_notifier
                result = await seeyon_notifier.start_process(
                    template_code=params.get("template_code", ""),
                    subject=params.get("subject", ""),
                    form_data=params.get("form_data", {}),
                )
                return result
            except Exception as e:
                return {"error": f"OA流程发起失败: {e}"}

        elif name == "send_notification":
            try:
                if params.get("channel") == "email":
                    from notifiers.email import email_notifier
                    result = email_notifier.send(
                        to=params.get("target", ""),
                        content=params.get("content", ""),
                    )
                elif params.get("channel") == "qq":
                    from notifiers.qq import qq_notifier
                    result = qq_notifier.send(
                        target=params.get("target", ""),
                        content=params.get("content", ""),
                    )
                else:
                    result = {"message": f"暂不支持 {params.get('channel')} 通知渠道"}
                return result
            except Exception as e:
                return {"error": f"通知发送失败: {e}"}

        elif name == "manage_schedule":
            try:
                from engines.analysis_engine import analysis_engine
                action = params.get("action", "list")
                if action == "list":
                    return await analysis_engine.list_tasks()
                elif action == "create":
                    return await analysis_engine.create_task(
                        json.dumps(params.get("config", {}))
                    )
                elif action == "run":
                    return await analysis_engine.run_manual(params.get("config", {}))
                else:
                    return {"message": f"未知操作: {action}"}
            except Exception as e:
                return {"error": f"任务管理失败: {e}"}

        elif name == "evolve_self":
            try:
                from core.evolution import evolution_engine
                result = await evolution_engine.manual_evolve(
                    params.get("instruction", "")
                )
                return result
            except Exception as e:
                return {"error": f"自我进化失败: {e}"}

        elif name == "ocr_recognize":
            return {"message": "OCR需要上传图片文件，请使用专用接口"}

        elif name == "local_file_search":
            try:
                from core.file_indexer import file_indexer
                action = params.get("action", "search")

                if action == "search":
                    query = params.get("query", "")
                    if not query:
                        return {"error": "请提供检索关键词或自然语言描述"}
                    limit = params.get("limit", 10)
                    entry_type = params.get("entry_type")  # 'file' / 'dir' / None
                    ext_filter = params.get("ext_filter")    # 'xlsx', 'pdf', ...

                    # 正在索引中，返回进度
                    if file_indexer.progress.is_indexing:
                        return {
                            "status": "indexing",
                            "message": "索引库正在构建中，请稍后再检索",
                            "progress": file_indexer.progress.get_snapshot(),
                            "formatted": file_indexer.progress.get_formatted(),
                        }

                    # 首次使用自动触发后台索引
                    if not file_indexer.encoder._built:
                        file_indexer.scan_background()
                        return {
                            "status": "indexing_started",
                            "message": "首次检索，正在后台创建文件索引库。\n您可以继续其他操作，随时输入'查看索引进度'了解进展。",
                            "progress": file_indexer.progress.get_snapshot(),
                            "formatted": file_indexer.progress.get_formatted(),
                        }

                    results = file_indexer.search(
                        query, limit=limit,
                        entry_type=entry_type,
                        ext_filter=ext_filter,
                    )
                    if not results:
                        hint = ""
                        if ext_filter:
                            hint += f"\n提示: 当前筛选了.{ext_filter}文件，去掉筛选试试？"
                        if entry_type:
                            hint += f"\n提示: 当前只看{'文件夹' if entry_type == 'dir' else '文件'}，去掉类型筛选试试？"
                        return {
                            "message": f"未找到与 \"{query}\" 相关的结果。{hint}\n可以尝试: 1.更换描述; 2.添加更多索引目录(add_dir); 3.重新扫描(scan)"
                        }
                    formatted = file_indexer.format_results(results)
                    return {"results": results, "count": len(results), "formatted": formatted}

                elif action == "add_dir":
                    dir_path = params.get("dir_path", "")
                    if not dir_path:
                        return {"error": "请提供目录路径"}
                    result = file_indexer.add_dir(dir_path)
                    return result

                elif action == "remove_dir":
                    dir_id = params.get("dir_id", "")
                    if not dir_id:
                        return {"error": "请提供目录ID"}
                    result = file_indexer.remove_dir(dir_id)
                    return result

                elif action == "scan":
                    dir_id = params.get("dir_id", None)
                    # 后台扫描，不阻塞
                    result = file_indexer.scan_background(dir_id)
                    return result

                elif action == "progress":
                    # 查看索引进度
                    snap = file_indexer.progress.get_snapshot()
                    return {
                        "progress": snap,
                        "formatted": file_indexer.progress.get_formatted(),
                    }

                elif action == "browse":
                    # 浏览目录内容（合并原 list_dir 功能）
                    browse_path = params.get("browse_path", "")
                    if not browse_path:
                        return {"error": "请提供目录路径"}
                    if not os.path.isdir(browse_path):
                        return {"error": f"目录不存在: {browse_path}"}
                    recursive = params.get("recursive", False)
                    items = []
                    try:
                        if recursive:
                            for root, dirs, files in os.walk(browse_path):
                                dirs[:] = [d for d in dirs if d not in SKIP_DIRS and not d.startswith(".")]
                                for d in dirs:
                                    fp = os.path.join(root, d)
                                    items.append({"name": d, "path": fp, "type": "dir"})
                                for f in files:
                                    fp = os.path.join(root, f)
                                    try:
                                        sz = os.path.getsize(fp)
                                    except OSError:
                                        sz = 0
                                    items.append({"name": f, "path": fp, "type": "file", "size": sz})
                                if len(items) > 500:
                                    break
                        else:
                            for entry in os.listdir(browse_path):
                                fp = os.path.join(browse_path, entry)
                                if os.path.isdir(fp):
                                    items.append({"name": entry, "path": fp, "type": "dir"})
                                else:
                                    try:
                                        sz = os.path.getsize(fp)
                                    except OSError:
                                        sz = 0
                                    items.append({"name": entry, "path": fp, "type": "file", "size": sz})
                    except Exception as e:
                        return {"error": f"浏览目录失败: {e}"}
                    return {"path": browse_path, "items": items, "count": len(items)}

                elif action == "list_dirs":
                    dirs = file_indexer.list_dirs()
                    return {"dirs": dirs, "count": len(dirs)}

                elif action == "stats":
                    stats = file_indexer.get_stats()
                    return stats

                else:
                    return {"error": f"未知操作: {action}，支持: search/add_dir/remove_dir/scan/list_dirs/stats/progress"}

            except Exception as e:
                logger.error(f"本地文件检索失败: {e}")
                return {"error": f"本地文件检索失败: {e}"}

        elif name == "skill_toggle":
            try:
                action = params.get("action", "list")
                if action == "list":
                    configs = self.get_all_skill_configs()
                    lines = ["📋 技能开关状态：", ""]
                    for c in configs:
                        icon = "✅" if c["enabled"] else "⬜"
                        vis = "" if c["visibility"] == "visible" else f' ({"隐藏" if c["visibility"] == "hidden" else "内部"})'
                        lines.append(f"{icon} 【{c['display_name']}】 {c['name']}{vis}")
                        lines.append(f"   {c['description'][:60]}")
                    return {"formatted": "\n".join(lines), "skills": configs}
                elif action == "toggle":
                    skill_name = params.get("name", "")
                    if not skill_name:
                        return {"error": "请指定技能名"}
                    result = self.toggle_skill(skill_name, params.get("enabled"))
                    return result
                else:
                    return {"error": f"未知操作: {action}"}
            except Exception as e:
                logger.error(f"技能开关操作失败: {e}")
                return {"error": f"技能开关操作失败: {e}"}

        # ===== 本地工具 =====
        elif name == "read_file":
            try:
                file_path = params.get("path", "")
                lines = params.get("lines", 0) or 0
                if not os.path.exists(file_path):
                    return {"error": f"文件不存在: {file_path}"}
                with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                    if lines > 0:
                        content = "".join(f.readline() for _ in range(lines))
                    else:
                        content = f.read()
                # 限制返回大小
                if len(content) > 50000:
                    content = content[:50000] + "\n... (截断，文件过长)"
                return {"path": file_path, "content": content, "size": len(content)}
            except Exception as e:
                return {"error": f"读取文件失败: {e}"}

        elif name == "write_file":
            try:
                file_path = params.get("path", "")
                content = params.get("content", "")
                os.makedirs(os.path.dirname(file_path) or ".", exist_ok=True)
                with open(file_path, "w", encoding="utf-8") as f:
                    f.write(content)
                return {"path": file_path, "size": len(content), "status": "written"}
            except Exception as e:
                return {"error": f"写入文件失败: {e}"}

        elif name == "edit_file":
            try:
                file_path = params.get("path", "")
                old_text = params.get("old_text", "")
                new_text = params.get("new_text", "")
                if not os.path.exists(file_path):
                    return {"error": f"文件不存在: {file_path}"}
                with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                    content = f.read()
                if old_text not in content:
                    return {"error": "未找到要替换的文本"}
                count = content.count(old_text)
                content = content.replace(old_text, new_text, 1)  # 只替换第一个
                with open(file_path, "w", encoding="utf-8") as f:
                    f.write(content)
                return {"path": file_path, "replacements": count, "status": "edited"}
            except Exception as e:
                return {"error": f"修改文件失败: {e}"}

        elif name == "list_dir":
            try:
                dir_path = params.get("path", ".")
                recursive = params.get("recursive", False)
                if not os.path.isdir(dir_path):
                    return {"error": f"目录不存在: {dir_path}"}
                if recursive:
                    result = []
                    for root, dirs, files in os.walk(dir_path):
                        for d in dirs:
                            fp = os.path.join(root, d)
                            result.append({"name": d, "path": fp, "type": "dir"})
                        for f in files:
                            fp = os.path.join(root, f)
                            sz = os.path.getsize(fp)
                            result.append({"name": f, "path": fp, "type": "file", "size": sz})
                        if len(result) > 500:
                            break
                else:
                    result = []
                    for entry in os.listdir(dir_path):
                        fp = os.path.join(dir_path, entry)
                        if os.path.isdir(fp):
                            result.append({"name": entry, "path": fp, "type": "dir"})
                        else:
                            sz = os.path.getsize(fp)
                            result.append({"name": entry, "path": fp, "type": "file", "size": sz})
                return {"path": dir_path, "items": result, "count": len(result)}
            except Exception as e:
                return {"error": f"列出目录失败: {e}"}

        elif name == "run_shell":
            try:
                import subprocess
                command = params.get("command", "")
                timeout = params.get("timeout", 30)
                # 安全限制：禁止危险命令
                dangerous = ["rm -rf /", "mkfs", "dd if=", ":(){:|:&};:"]
                for d in dangerous:
                    if d in command:
                        return {"error": f"禁止执行危险命令"}
                result = subprocess.run(
                    command, shell=True, capture_output=True, text=True,
                    timeout=timeout, cwd=settings.DATA_DIR
                )
                output = result.stdout[-20000:] if len(result.stdout) > 20000 else result.stdout
                error = result.stderr[-5000:] if len(result.stderr) > 5000 else result.stderr
                return {
                    "command": command,
                    "exit_code": result.returncode,
                    "stdout": output,
                    "stderr": error,
                }
            except subprocess.TimeoutExpired:
                return {"error": f"命令超时({timeout}s)"}
            except Exception as e:
                return {"error": f"执行命令失败: {e}"}

        elif name == "git_operation":
            try:
                import subprocess
                action = params.get("action", "status")
                args = params.get("args", "")
                repo_path = params.get("repo_path", ".")
                # 构建git命令
                git_cmd = f"git -C {repo_path} {action}"
                if args:
                    git_cmd += f" {args}"
                result = subprocess.run(
                    git_cmd, shell=True, capture_output=True, text=True,
                    timeout=30
                )
                return {
                    "command": git_cmd,
                    "exit_code": result.returncode,
                    "stdout": result.stdout[-10000:],
                    "stderr": result.stderr[-5000:],
                }
            except Exception as e:
                return {"error": f"Git操作失败: {e}"}

        else:
            return {"error": f"未知skill: {name}"}

    # ===== 查询接口 =====

    def list_all_skills(self) -> List[dict]:
        """列出所有skills（管理用）"""
        return [
            {
                **skill,
                "usage_count": self._skill_usage.get(name, 0),
                "is_builtin": name in BUILTIN_SKILLS,
            }
            for name, skill in self._skills.items()
        ]

    def get_skill(self, name: str) -> Optional[dict]:
        """获取单个skill信息"""
        if name in self._skills:
            return {
                **self._skills[name],
                "usage_count": self._skill_usage.get(name, 0),
            }
        return None


# 全局单例
skill_manager = SkillManager()
