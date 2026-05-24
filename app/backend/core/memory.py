from __future__ import annotations
"""记忆系统 - 对话记忆持久化、摘要、长期记忆检索

设计：
1. 短期记忆：最近N轮对话原文（SQLite存储，按conversation_id组织）
2. 长期记忆：自动摘要 + 用户/助手关键信息提取（向量检索可选，当前用关键词+LLM语义匹配）
3. 工作记忆：当前会话的上下文摘要，作为system prompt注入
4. 自我进化记忆：反思记录、学到的规则、更新过的prompt
"""
import json
import logging
import re
import sqlite3
import uuid
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from config.settings import settings

logger = logging.getLogger(__name__)


class MemorySystem:
    """记忆系统 - 持久化存储 + 智能检索"""

    def __init__(self):
        self.db_path = settings.DATA_DIR / "memory.db"
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self):
        """初始化数据库表"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS conversation_messages (
                    id TEXT PRIMARY KEY,
                    conversation_id TEXT NOT NULL,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    metadata TEXT DEFAULT '{}'
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_conv_msg_conv
                ON conversation_messages(conversation_id, created_at)
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS long_term_memory (
                    id TEXT PRIMARY KEY,
                    category TEXT NOT NULL,  -- fact/preference/rule/lesson/skill
                    content TEXT NOT NULL,
                    source_conversation_id TEXT,
                    importance REAL DEFAULT 0.5,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    access_count INTEGER DEFAULT 0,
                    metadata TEXT DEFAULT '{}'
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_ltm_category
                ON long_term_memory(category)
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS conversation_summaries (
                    conversation_id TEXT PRIMARY KEY,
                    summary TEXT NOT NULL,
                    key_topics TEXT DEFAULT '[]',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS evolution_log (
                    id TEXT PRIMARY KEY,
                    type TEXT NOT NULL,  -- reflection/learning/prompt_update/skill_update
                    content TEXT NOT NULL,
                    before_state TEXT,
                    after_state TEXT,
                    created_at TEXT NOT NULL
                )
            """)
            conn.commit()

    # ===== 对话消息持久化 =====

    def save_message(self, conversation_id: str, role: str, content: str,
                     metadata: dict = None) -> str:
        """保存对话消息"""
        msg_id = str(uuid.uuid4())
        now = datetime.now().isoformat()
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "INSERT INTO conversation_messages (id, conversation_id, role, content, created_at, metadata) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (msg_id, conversation_id, role, content, now, json.dumps(metadata or {}, ensure_ascii=False))
            )
            conn.commit()
        return msg_id

    def get_messages(self, conversation_id: str, limit: int = 50,
                     offset: int = 0) -> List[dict]:
        """获取对话消息"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT * FROM conversation_messages "
                "WHERE conversation_id = ? ORDER BY created_at ASC LIMIT ? OFFSET ?",
                (conversation_id, limit, offset)
            ).fetchall()
            return [dict(r) for r in rows]

    def get_recent_messages(self, conversation_id: str, n: int = 20) -> List[dict]:
        """获取最近N条消息"""
        return self.get_messages(conversation_id, limit=n)

    def list_conversations(self) -> List[dict]:
        """列出所有对话"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute("""
                SELECT conversation_id,
                       COUNT(*) as msg_count,
                       MAX(created_at) as last_at,
                       (SELECT content FROM conversation_messages cm2
                        WHERE cm2.conversation_id = cm.conversation_id
                        ORDER BY cm2.created_at DESC LIMIT 1) as last_message
                FROM conversation_messages cm
                GROUP BY conversation_id
                ORDER BY last_at DESC
            """).fetchall()
            return [dict(r) for r in rows]

    def delete_conversation(self, conversation_id: str):
        """删除对话"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("DELETE FROM conversation_messages WHERE conversation_id = ?",
                         (conversation_id,))
            conn.execute("DELETE FROM conversation_summaries WHERE conversation_id = ?",
                         (conversation_id,))
            conn.commit()

    # ===== 对话摘要 =====

    def save_summary(self, conversation_id: str, summary: str,
                     key_topics: List[str] = None):
        """保存对话摘要"""
        now = datetime.now().isoformat()
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT INTO conversation_summaries (conversation_id, summary, key_topics, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(conversation_id) DO UPDATE SET
                    summary = excluded.summary,
                    key_topics = excluded.key_topics,
                    updated_at = excluded.updated_at
            """, (conversation_id, summary, json.dumps(key_topics or [], ensure_ascii=False), now, now))
            conn.commit()

    def get_summary(self, conversation_id: str) -> Optional[dict]:
        """获取对话摘要"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT * FROM conversation_summaries WHERE conversation_id = ?",
                (conversation_id,)
            ).fetchone()
            return dict(row) if row else None

    async def generate_summary(self, conversation_id: str) -> str:
        """用LLM生成对话摘要"""
        messages = self.get_messages(conversation_id, limit=60)
        if not messages:
            return ""

        from core.llm import llm_client
        conversation_text = "\n".join(
            f"{'用户' if m['role'] == 'user' else '助手'}: {m['content']}"
            for m in messages
        )

        prompt = f"""请总结以下对话的关键内容，提取：
1. 主要话题
2. 用户的意图和需求
3. 助手提供的关键信息
4. 任何需要记住的重要事实或偏好

对话内容：
{conversation_text}

请用简洁的中文输出摘要。"""

        summary = llm_client.chat([
            {"role": "system", "content": "你是对话摘要助手，擅长提炼关键信息。"},
            {"role": "user", "content": prompt}
        ], temperature=0.3)

        # 提取关键主题
        topics_prompt = f"从以下摘要中提取3-5个关键词/主题，以JSON数组格式输出：\n{summary}"
        try:
            topics = llm_client.chat_json([
                {"role": "system", "content": "输出JSON数组，如[\"关键词1\",\"关键词2\"]"},
                {"role": "user", "content": topics_prompt}
            ], temperature=0.1)
            key_topics = topics if isinstance(topics, list) else []
        except Exception:
            key_topics = []

        self.save_summary(conversation_id, summary, key_topics)
        return summary

    # ===== 长期记忆 =====

    def save_long_term(self, category: str, content: str,
                       source_conversation_id: str = None,
                       importance: float = 0.5,
                       metadata: dict = None) -> str:
        """保存长期记忆"""
        mem_id = str(uuid.uuid4())
        now = datetime.now().isoformat()
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "INSERT INTO long_term_memory "
                "(id, category, content, source_conversation_id, importance, created_at, updated_at, metadata) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (mem_id, category, content, source_conversation_id,
                 importance, now, now, json.dumps(metadata or {}, ensure_ascii=False))
            )
            conn.commit()
        return mem_id

    def search_long_term(self, query: str, category: str = None,
                         limit: int = 10) -> List[dict]:
        """搜索长期记忆（关键词匹配 + LLM语义评分可选）"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row

            if category:
                rows = conn.execute(
                    "SELECT * FROM long_term_memory WHERE category = ? "
                    "ORDER BY importance DESC, updated_at DESC LIMIT ?",
                    (category, limit * 3)
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM long_term_memory "
                    "ORDER BY importance DESC, updated_at DESC LIMIT ?",
                    (limit * 3,)
                ).fetchall()

            results = [dict(r) for r in rows]

        # 关键词匹配打分
        query_lower = query.lower()
        query_words = set(re.findall(r'\w+', query_lower))
        scored = []
        for r in results:
            content_lower = r["content"].lower()
            score = r["importance"]
            # 精确匹配加分
            if query_lower in content_lower:
                score += 2.0
            # 词汇重叠加分
            content_words = set(re.findall(r'\w+', content_lower))
            overlap = query_words & content_words
            if overlap:
                score += len(overlap) * 0.3
            r["_score"] = score
            scored.append(r)

        scored.sort(key=lambda x: x["_score"], reverse=True)

        # 更新访问计数
        for r in scored[:limit]:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute(
                    "UPDATE long_term_memory SET access_count = access_count + 1 WHERE id = ?",
                    (r["id"],)
                )
                conn.commit()

        return scored[:limit]

    async def extract_and_save_memories(self, conversation_id: str):
        """从对话中提取关键信息存入长期记忆"""
        messages = self.get_messages(conversation_id, limit=40)
        if len(messages) < 4:
            return []

        from core.llm import llm_client
        conversation_text = "\n".join(
            f"{'用户' if m['role'] == 'user' else '助手'}: {m['content']}"
            for m in messages
        )

        prompt = f"""分析以下对话，提取值得长期记住的信息，按类别分类：

类别说明：
- fact: 客观事实（用户的姓名、职位、项目信息等）
- preference: 用户偏好（喜欢的风格、习惯等）
- rule: 工作规则（流程要求、格式规范等）
- lesson: 经验教训（什么做法好/不好）

对话内容：
{conversation_text}

请以JSON格式输出，如：
[
  {{"category": "fact", "content": "用户叫张三，在成都工作", "importance": 0.8}},
  {{"category": "preference", "content": "用户喜欢简洁的回答风格", "importance": 0.6}}
]

如果没有值得记住的信息，输出空数组 []。只输出JSON。"""

        try:
            memories = llm_client.chat_json([
                {"role": "system", "content": "你是信息提取助手，从对话中提取关键记忆。只输出JSON。"},
                {"role": "user", "content": prompt}
            ], temperature=0.2)

            if not isinstance(memories, list):
                memories = []

            saved = []
            for m in memories:
                if isinstance(m, dict) and "category" in m and "content" in m:
                    # 检查是否已有类似记忆，避免重复
                    existing = self.search_long_term(m["content"], category=m["category"], limit=3)
                    is_duplicate = any(
                        m["content"][:20] in e["content"] for e in existing
                    )
                    if not is_duplicate:
                        mem_id = self.save_long_term(
                            category=m["category"],
                            content=m["content"],
                            source_conversation_id=conversation_id,
                            importance=m.get("importance", 0.5)
                        )
                        saved.append(mem_id)

            if saved:
                logger.info(f"从对话 {conversation_id} 提取了 {len(saved)} 条长期记忆")
            return saved
        except Exception as e:
            logger.error(f"提取长期记忆失败: {e}")
            return []

    # ===== 工作记忆构建 =====

    def build_context(self, conversation_id: str, current_message: str = "",
                      max_messages: int = 20) -> List[dict]:
        """构建完整的对话上下文，包括长期记忆检索注入

        返回格式: [{"role": ..., "content": ...}, ...]
        """
        # 1. 获取对话摘要（如果有的话）
        summary = self.get_summary(conversation_id)
        summary_text = summary["summary"] if summary else ""

        # 2. 搜索相关长期记忆
        relevant_memories = []
        if current_message:
            relevant_memories = self.search_long_term(current_message, limit=5)

        # 3. 获取最近消息
        recent = self.get_recent_messages(conversation_id, n=max_messages)

        # 4. 构建上下文
        context_messages = []

        # 系统提示中注入记忆
        memory_context = ""
        if summary_text:
            memory_context += f"\n\n[之前对话的摘要]\n{summary_text}\n"
        if relevant_memories:
            memory_context += "\n[相关的长期记忆]\n"
            for m in relevant_memories:
                memory_context += f"- ({m['category']}) {m['content']}\n"

        if memory_context:
            # 注入到第一条system消息后面，或者作为单独的上下文
            context_messages.append({
                "role": "system",
                "content": f"以下是你应该记住的上下文信息：{memory_context}"
            })

        # 添加最近对话
        for msg in recent:
            context_messages.append({
                "role": msg["role"],
                "content": msg["content"]
            })

        return context_messages

    # ===== 进化日志 =====

    def log_evolution(self, evo_type: str, content: str,
                      before_state: str = None, after_state: str = None) -> str:
        """记录进化日志"""
        evo_id = str(uuid.uuid4())
        now = datetime.now().isoformat()
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "INSERT INTO evolution_log (id, type, content, before_state, after_state, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (evo_id, evo_type, content, before_state, after_state, now)
            )
            conn.commit()
        return evo_id

    def get_evolution_logs(self, evo_type: str = None, limit: int = 50) -> List[dict]:
        """获取进化日志"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            if evo_type:
                rows = conn.execute(
                    "SELECT * FROM evolution_log WHERE type = ? ORDER BY created_at DESC LIMIT ?",
                    (evo_type, limit)
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM evolution_log ORDER BY created_at DESC LIMIT ?",
                    (limit,)
                ).fetchall()
            return [dict(r) for r in rows]


# 全局单例
memory_system = MemorySystem()
