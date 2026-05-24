from __future__ import annotations
"""自我进化引擎 - 反思、学习、自我改进

核心循环：
1. 反思(Reflection)：定期回顾对话，发现不足
2. 学习(Learning)：从对话中提取规则和经验
3. 改进(Improvement)：更新system prompt、调整工具策略
4. 验证(Validation)：确认改进有效，记录日志

触发时机：
- 对话结束后自动反思（异步）
- 达到N轮对话后触发
- 用户手动触发
"""
import json
import logging
import uuid
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from config.settings import settings
from core.llm import llm_client
from core.memory import memory_system

logger = logging.getLogger(__name__)

# 系统prompt模板路径
PROMPT_FILE = settings.DATA_DIR / "system_prompt.json"


class EvolutionEngine:
    """自我进化引擎"""

    def __init__(self):
        self.data_dir = settings.DATA_DIR
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self._conversation_count = 0
        self._reflection_interval = 10  # 每10轮对话反思一次
        self._load_system_prompt()

    def _load_system_prompt(self):
        """加载或初始化系统prompt"""
        if PROMPT_FILE.exists():
            with open(PROMPT_FILE, "r", encoding="utf-8") as f:
                self.system_prompt_config = json.load(f)
        else:
            self.system_prompt_config = {
                "base_prompt": "你是知行，一个友善、专业的个人AI助手。直接回答用户问题，简洁明了。",
                "learned_rules": [],
                "personality_traits": ["友善", "专业", "简洁", "务实"],
                "response_style": "直接回答，避免冗余的客套话",
                "version": 1,
                "updated_at": datetime.now().isoformat(),
            }
            self._save_system_prompt()

    def _save_system_prompt(self):
        """保存系统prompt"""
        self.system_prompt_config["updated_at"] = datetime.now().isoformat()
        with open(PROMPT_FILE, "w", encoding="utf-8") as f:
            json.dump(self.system_prompt_config, f, ensure_ascii=False, indent=2)

    def get_system_prompt(self) -> str:
        """获取当前生效的完整系统prompt"""
        config = self.system_prompt_config
        parts = [config["base_prompt"]]

        # 加入人格特质
        if config.get("personality_traits"):
            traits = "、".join(config["personality_traits"])
            parts.append(f"\n人格特质：{traits}。")

        # 加入响应风格
        if config.get("response_style"):
            parts.append(f"\n回答风格：{config['response_style']}")

        # 加入学到的规则
        if config.get("learned_rules"):
            parts.append("\n\n以下是你在使用中积累的规则和经验：")
            for i, rule in enumerate(config["learned_rules"], 1):
                parts.append(f"{i}. {rule}")

        return "".join(parts)

    async def on_conversation_turn(self, conversation_id: str):
        """每次对话轮次后调用，判断是否需要反思"""
        self._conversation_count += 1
        if self._conversation_count % self._reflection_interval == 0:
            # 异步触发反思
            await self.reflect(conversation_id)

    async def reflect(self, conversation_id: str):
        """反思 - 回顾对话，发现不足，提取改进点"""
        logger.info(f"开始反思对话: {conversation_id}")

        messages = memory_system.get_messages(conversation_id, limit=30)
        if len(messages) < 4:
            return

        conversation_text = "\n".join(
            f"{'用户' if m['role'] == 'user' else '助手'}: {m['content']}"
            for m in messages
        )

        current_prompt = self.get_system_prompt()

        reflection_prompt = f"""你是一个AI自我反思系统。请分析以下对话，找出助手的不足之处和改进方向。

当前系统prompt：
{current_prompt}

对话记录：
{conversation_text}

请分析：
1. 助手有哪些回答不够好？（太啰嗦、不够准确、没理解意图等）
2. 应该如何改进？（新增规则、调整风格、补充知识等）
3. 有没有可以学到的规则？（如用户偏好特定格式、某个领域需要特殊处理）

以JSON格式输出：
{{
  "issues": ["问题1", "问题2"],
  "improvements": ["改进1", "改进2"],
  "new_rules": ["规则1", "规则2"],
  "style_adjustments": "风格调整建议"
}}

如果没有明显问题，输出空数组。只输出JSON。"""

        try:
            reflection = llm_client.chat_json([
                {"role": "system", "content": "你是AI自我反思系统。只输出JSON。"},
                {"role": "user", "content": reflection_prompt}
            ], temperature=0.3)

            # 记录反思日志
            memory_system.log_evolution(
                evo_type="reflection",
                content=json.dumps(reflection, ensure_ascii=False),
                before_state=current_prompt
            )

            # 应用改进
            if reflection.get("new_rules"):
                await self._apply_new_rules(reflection["new_rules"])

            if reflection.get("style_adjustments"):
                await self._apply_style_adjustment(reflection["style_adjustments"])

            logger.info(f"反思完成，发现 {len(reflection.get('issues', []))} 个问题")

        except Exception as e:
            logger.error(f"反思失败: {e}")

    async def _apply_new_rules(self, new_rules: List[str]):
        """应用新学到的规则"""
        existing = self.system_prompt_config.get("learned_rules", [])

        added = []
        for rule in new_rules:
            # 避免重复
            is_dup = any(rule[:15] in existing_rule for existing_rule in existing)
            if not is_dup:
                existing.append(rule)
                added.append(rule)

        if added:
            self.system_prompt_config["learned_rules"] = existing
            self.system_prompt_config["version"] = self.system_prompt_config.get("version", 1) + 1
            self._save_system_prompt()

            memory_system.log_evolution(
                evo_type="learning",
                content=f"新增 {len(added)} 条规则",
                after_state=json.dumps(added, ensure_ascii=False)
            )
            logger.info(f"新增 {len(added)} 条规则: {added}")

    async def _apply_style_adjustment(self, adjustment: str):
        """应用风格调整"""
        old_style = self.system_prompt_config.get("response_style", "")

        # 用LLM合并新旧风格
        merge_prompt = f"""请合并以下两个风格描述，保留两者的精华：

原风格：{old_style}
新建议：{adjustment}

输出合并后的风格描述（一段话）："""

        try:
            merged = llm_client.chat([
                {"role": "system", "content": "你输出一段简洁的风格描述。"},
                {"role": "user", "content": merge_prompt}
            ], temperature=0.3)

            self.system_prompt_config["response_style"] = merged.strip()
            self._save_system_prompt()

            memory_system.log_evolution(
                evo_type="prompt_update",
                content="更新回答风格",
                before_state=old_style,
                after_state=merged.strip()
            )
        except Exception as e:
            logger.error(f"风格调整失败: {e}")

    async def manual_evolve(self, instruction: str) -> dict:
        """手动触发进化 - 用户指定改进方向"""
        current_prompt = self.get_system_prompt()

        evolve_prompt = f"""用户要求你改进自己的行为方式。

当前系统prompt：
{current_prompt}

用户的改进指令：{instruction}

请分析并输出具体的改进方案，JSON格式：
{{
  "rule_changes": ["要新增或修改的规则"],
  "style_change": "风格调整",
  "personality_change": "人格特质调整（如需要）",
  "explanation": "对用户的解释"
}}"""

        try:
            result = llm_client.chat_json([
                {"role": "system", "content": "你是AI自我改进系统。只输出JSON。"},
                {"role": "user", "content": evolve_prompt}
            ], temperature=0.3)

            # 应用变更
            if result.get("rule_changes"):
                await self._apply_new_rules(result["rule_changes"])

            if result.get("style_change"):
                await self._apply_style_adjustment(result["style_change"])

            if result.get("personality_change"):
                traits = self.system_prompt_config.get("personality_traits", [])
                new_traits = result["personality_change"]
                if isinstance(new_traits, list):
                    traits = list(set(traits + new_traits))
                self.system_prompt_config["personality_traits"] = traits
                self._save_system_prompt()

            memory_system.log_evolution(
                evo_type="learning",
                content=f"手动进化: {instruction}",
                after_state=json.dumps(result, ensure_ascii=False)
            )

            return result
        except Exception as e:
            logger.error(f"手动进化失败: {e}")
            return {"error": str(e)}

    def get_status(self) -> dict:
        """获取进化状态"""
        return {
            "prompt_version": self.system_prompt_config.get("version", 1),
            "learned_rules_count": len(self.system_prompt_config.get("learned_rules", [])),
            "personality_traits": self.system_prompt_config.get("personality_traits", []),
            "total_conversations": self._conversation_count,
            "next_reflection_at": self._conversation_count + (
                self._reflection_interval - self._conversation_count % self._reflection_interval
            ),
            "updated_at": self.system_prompt_config.get("updated_at"),
        }


# 全局单例
evolution_engine = EvolutionEngine()
