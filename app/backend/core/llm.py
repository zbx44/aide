from __future__ import annotations
"""LLM客户端 - 使用httpx直接调用OpenAI兼容API，兼容Python 3.8"""
import json
import logging
import asyncio
from typing import AsyncGenerator, Dict, List, Optional

import httpx

from config.settings import settings

logger = logging.getLogger(__name__)


def estimate_tokens(text: str) -> int:
    """估算文本token数
    中文约1.5字/token，英文约4字符/token
    这是粗略估算，实际分词器可能有差异，预留20%余量
    """
    if not text:
        return 0
    # 计算中文字符数
    chinese_chars = sum(1 for c in text if '\u4e00' <= c <= '\u9fff')
    # 计算非中文字符数
    other_chars = len(text) - chinese_chars
    # 中文: ~1.5字/token，英文: ~4字符/token，预留20%余量
    tokens = int(chinese_chars / 1.5 + other_chars / 4) * 1.2
    return max(int(tokens), 1)


def estimate_messages_tokens(messages: List[dict]) -> int:
    """估算消息列表总token数（包括消息格式开销）"""
    total = 0
    for msg in messages:
        # 每条消息有~4 token的格式开销（role, separators等）
        total += 4
        content = msg.get("content", "")
        if isinstance(content, str):
            total += estimate_tokens(content)
        elif isinstance(content, list):
            # 多模态消息
            for part in content:
                if isinstance(part, dict) and part.get("type") == "text":
                    total += estimate_tokens(part.get("text", ""))
                elif isinstance(part, dict) and part.get("type") == "image_url":
                    # 图片token估算：低分辨率~85, 高分辨率~170-1105
                    total += 500
        # tool_calls的token
        tool_calls = msg.get("tool_calls")
        if tool_calls:
            for tc in tool_calls:
                func = tc.get("function", {})
                total += estimate_tokens(func.get("name", ""))
                total += estimate_tokens(func.get("arguments", ""))
    return total


def truncate_messages(messages: List[dict], max_tokens: int, reserved_tokens: int = 1024) -> List[dict]:
    """截断消息列表使其不超过token限制
    
    策略：
    1. 所有system消息合并为一条（放在最前），满足vLLM "system must be at beginning" 要求
    2. 保留最新的对话，从最早的开始删
    3. 确保至少有一条user消息，满足vLLM "user query found" 要求
    4. 预留reserved_tokens给模型生成用
    
    Args:
        messages: 消息列表
        max_tokens: 上下文窗口上限
        reserved_tokens: 为模型回复预留的token空间
    
    Returns:
        截断后的消息列表
    """
    if not messages:
        return messages

    available = max_tokens - reserved_tokens
    if available <= 0:
        logger.warning(f"上下文窗口太小或预留空间太大: max={max_tokens}, reserved={reserved_tokens}")
        available = max_tokens // 2

    # 1. 合并所有system消息为一条（vLLM要求system只能在开头）
    system_parts = []
    conv_msgs = []
    for msg in messages:
        if msg.get("role") == "system":
            content = msg.get("content", "")
            if isinstance(content, str) and content.strip():
                system_parts.append(content.strip())
        else:
            conv_msgs.append(msg)

    merged_system = None
    if system_parts:
        merged_system = {"role": "system", "content": "\n\n".join(system_parts)}

    # 2. 计算system占用token
    system_tokens = estimate_messages_tokens([merged_system]) if merged_system else 0
    remaining = available - system_tokens

    if remaining <= 0 and merged_system:
        # system太长，截断system内容
        max_system_chars = int(available / 1.5)  # 粗略估算
        merged_system["content"] = merged_system["content"][:max_system_chars]
        system_tokens = estimate_messages_tokens([merged_system])
        remaining = available - system_tokens

    # 3. 从最新的对话消息开始保留，直到token用完
    kept = []
    used = 0
    for msg in reversed(conv_msgs):
        msg_tokens = estimate_messages_tokens([msg])
        if used + msg_tokens > remaining:
            break
        kept.insert(0, msg)
        used += msg_tokens

    # 4. 确保至少有一条user消息（vLLM要求有user query）
    has_user = any(m.get("role") == "user" for m in kept)
    if not has_user and conv_msgs:
        # 从被截断的消息中找最后一条user消息
        for msg in reversed(conv_msgs):
            if msg.get("role") == "user" and msg not in kept:
                # 如果加上这条超限，删掉最早的一条assistant
                msg_tokens = estimate_messages_tokens([msg])
                if used + msg_tokens > remaining and len(kept) > 1:
                    # 删最早的非user消息腾空间
                    for i, m in enumerate(kept):
                        if m.get("role") == "assistant":
                            freed = estimate_messages_tokens([m])
                            kept.pop(i)
                            used -= freed
                            break
                kept.append(msg)
                kept.sort(key=lambda m: conv_msgs.index(m) if m in conv_msgs else 999)
                break

    # 5. 组装结果：system在最前，对话消息在后
    result = []
    if merged_system:
        result.append(merged_system)
    result.extend(kept)

    if len(result) < len(messages):
        logger.info(f"上下文截断: {len(messages)}条消息 → {len(result)}条 (约{estimate_messages_tokens(result)}tokens)")
    
    return result


class LLMClient:
    """多平台LLM客户端 - 基于httpx直接调用OpenAI兼容API"""

    def __init__(self):
        self.provider = settings.LLM_PROVIDER
        self._init_provider()
        # 连接池设置：限制并发连接数、启用keep-alive
        self.client = httpx.Client(
            timeout=httpx.Timeout(120.0, connect=10.0),
            limits=httpx.Limits(max_connections=20, max_keepalive_connections=10),
        )
        self.async_client = httpx.AsyncClient(
            timeout=httpx.Timeout(120.0, connect=10.0),
            limits=httpx.Limits(max_connections=20, max_keepalive_connections=10),
        )
        self.max_tokens = settings.LLM_MAX_TOKENS
        self.temperature = settings.LLM_TEMPERATURE
        self.context_window = settings.LLM_CONTEXT_WINDOW
        self.max_context_messages = settings.LLM_MAX_CONTEXT_MESSAGES
        self.thinking_model = settings.LLM_THINKING_MODEL
        self.supports_tools = True  # 运行时检测，收到400自动置False

        logger.info(f"LLM初始化: provider={self.provider}, base_url={self.base_url}, model={self.model}")

    def _init_provider(self):
        """根据provider设置连接参数"""
        if self.provider == "vllm":
            self.base_url = settings.LLM_BASE_URL
            self.api_key = settings.LLM_API_KEY
            self.model = settings.LLM_MODEL
        elif self.provider == "tencent":
            self.base_url = settings.LLM_TENCENT_BASE_URL
            self.api_key = settings.LLM_TENCENT_API_KEY
            self.model = settings.LLM_TENCENT_MODEL
        elif self.provider == "openai":
            self.base_url = settings.LLM_OPENAI_BASE_URL
            self.api_key = settings.LLM_OPENAI_API_KEY
            self.model = settings.LLM_OPENAI_MODEL
        elif self.provider == "custom":
            self.base_url = settings.LLM_CUSTOM_BASE_URL
            self.api_key = settings.LLM_CUSTOM_API_KEY
            self.model = settings.LLM_CUSTOM_MODEL
        else:
            raise ValueError(f"未知的LLM_PROVIDER: {self.provider}，支持: vllm/tencent/openai/custom")

    def _get_url(self):
        """拼接Chat Completions API URL"""
        base = self.base_url.rstrip('/')
        return f"{base}/chat/completions"

    def _get_headers(self):
        """构造请求头"""
        h = {"Content-Type": "application/json"}
        if self.api_key:
            h["Authorization"] = f"Bearer {self.api_key}"
        return h

    # 每个provider的默认特性
    PROVIDER_PROFILES = {
        "vllm": {"thinking": True, "tools": True},     # 本地vLLM部署，通常是Qwen等思考模型
        "tencent": {"thinking": True, "tools": True},  # 腾讯TokenHub，GLM-5等思考模型
        "openai": {"thinking": True, "tools": True},    # OpenAI兼容端点（可能含思考模型）
        "custom": {"thinking": False, "tools": True},   # 自定义端点
    }

    def switch_provider(self, provider: str):
        """运行时切换provider，自动调整特性标记"""
        self.provider = provider
        self._init_provider()
        # 自动调整思考模型和工具支持标记
        profile = self.PROVIDER_PROFILES.get(provider, {"thinking": False, "tools": True})
        self.thinking_model = profile["thinking"]
        self.supports_tools = profile["tools"]
        logger.info(f"切换provider到 {provider}: thinking={self.thinking_model}, tools={self.supports_tools}")

    def chat(self, messages: List[Dict], temperature: float = None,
             max_tokens: int = None, **kwargs) -> dict:
        """同步对话，返回完整回复（含思考过程）

        Returns:
            {"content": "正式回答", "thinking": "思考过程"} 或 {"content": "回答", "thinking": None}
        """
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature or self.temperature,
            "max_tokens": max_tokens or self.max_tokens,
            **kwargs,
        }
        resp = self.client.post(
            self._get_url(),
            headers=self._get_headers(),
            json=payload,
        )
        resp.raise_for_status()
        data = resp.json()
        msg = data["choices"][0]["message"]
        raw = msg.get("content", "") or ""

        # GLM-5系列：reasoning_content独立字段
        reasoning = msg.get("reasoning_content")
        if reasoning:
            return {"content": raw.strip(), "thinking": reasoning.strip()}

        # Qwen3系列：content里包含<think>标签
        return self._parse_thinking(raw)

    def _parse_thinking(self, raw: str) -> dict:
        """解析思考模型输出，拆分思考过程和正式回答

        Qwen3思考模型输出格式：
        <与>think>\n思考过程\n<与>/think>\n正式回答

        Returns:
            {"content": "正式回答", "thinking": "思考过程"}
        """
        if not self.thinking_model or not raw:
            return {"content": raw or "", "thinking": None}

        import re
        # 匹配 <think>...</think> 块（允许前后有多余空白）
        pattern = r'^\s*<think>([\s\S]*?)<\/think>\s*'
        match = re.match(pattern, raw)
        if match:
            thinking = match.group(1).strip()
            content = raw[match.end():].strip()
            return {"content": content, "thinking": thinking if thinking else None}

        # 没有think标签，直接返回原文
        return {"content": raw, "thinking": None}

    def chat_stream(self, messages: List[Dict], temperature: float = None,
                    max_tokens: int = None, **kwargs):
        """流式对话，yield每个chunk"""
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature or self.temperature,
            "max_tokens": max_tokens or self.max_tokens,
            "stream": True,
            **kwargs,
        }
        with self.client.stream(
            "POST",
            self._get_url(),
            headers=self._get_headers(),
            json=payload,
        ) as resp:
            resp.raise_for_status()
            for line in resp.iter_lines():
                if not line or not line.startswith("data: "):
                    continue
                data_str = line[6:]  # strip "data: "
                if data_str.strip() == "[DONE]":
                    break
                try:
                    chunk = json.loads(data_str)
                    delta = chunk["choices"][0].get("delta", {})
                    content = delta.get("content")
                    if content:
                        yield content
                except (json.JSONDecodeError, KeyError, IndexError):
                    continue

    async def chat_stream_async(self, messages: List[Dict],
                                 temperature: float = None,
                                 max_tokens: int = None, **kwargs
                                 ) -> AsyncGenerator[dict, None]:
        """异步流式对话，yield解析后的chunk

        Yields:
            {"type": "thinking", "text": "..."}  — 思考过程
            {"type": "content", "text": "..."}   — 正式回答
            {"type": "error", "text": "..."}    — 错误信息
        """
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature or self.temperature,
            "max_tokens": max_tokens or self.max_tokens,
            "stream": True,
            **kwargs,
        }

        # 思考标签解析状态
        in_thinking = False
        think_buffer = ""
        content_started = False
        TAG_OPEN = "<think>"
        TAG_CLOSE = "</think>"
        TAG_OPEN_LEN = len(TAG_OPEN)
        TAG_CLOSE_LEN = len(TAG_CLOSE)

        try:
            async with self.async_client.stream(
                "POST",
                self._get_url(),
                headers=self._get_headers(),
                json=payload,
            ) as resp:
                if resp.status_code >= 400:
                    error_body = await resp.aread()
                    error_msg = f"LLM请求失败({resp.status_code}): {error_body.decode('utf-8', errors='replace')[:200]}"
                    logger.error(error_msg)
                    yield {"type": "error", "text": error_msg}
                    return

                async for line in resp.aiter_lines():
                    if not line or not line.startswith("data: "):
                        continue
                    data_str = line[6:]
                    if data_str.strip() == "[DONE]":
                        break
                    try:
                        chunk = json.loads(data_str)
                        delta = chunk["choices"][0].get("delta", {})
                        content = delta.get("content")
                        # GLM-5系列：思考过程在reasoning_content字段
                        reasoning = delta.get("reasoning_content")

                        # 处理独立的reasoning_content字段（GLM-5系列）
                        if reasoning:
                            if not self.thinking_model:
                                self.thinking_model = True  # 自动检测
                            yield {"type": "thinking", "text": reasoning}
                            continue

                        if not content:
                            continue
                    except (json.JSONDecodeError, KeyError, IndexError):
                        continue

                    # 非思考模型直接输出
                    if not self.thinking_model:
                        yield {"type": "content", "text": content}
                        continue

                    # === 思考模型标签流式解析 ===
                    think_buffer += content

                    while think_buffer:
                        if in_thinking:
                            close_idx = think_buffer.find(TAG_CLOSE)
                            if close_idx != -1:
                                # 思考块结束
                                think_text = think_buffer[:close_idx]
                                if think_text:
                                    yield {"type": "thinking", "text": think_text}
                                think_buffer = think_buffer[close_idx + TAG_CLOSE_LEN:]
                                in_thinking = False
                                continue
                            else:
                                # 思考块继续，输出安全的部分
                                safe_len = len(think_buffer) - TAG_CLOSE_LEN + 1
                                if safe_len > 0:
                                    yield {"type": "thinking", "text": think_buffer[:safe_len]}
                                    think_buffer = think_buffer[safe_len:]
                                break
                        else:
                            if not content_started:
                                # 查找<think>标签
                                open_idx = think_buffer.find(TAG_OPEN)
                                if open_idx != -1:
                                    content_started = True
                                    before = think_buffer[:open_idx]
                                    if before.strip():
                                        yield {"type": "content", "text": before}
                                    think_buffer = think_buffer[open_idx + TAG_OPEN_LEN:]
                                    in_thinking = True
                                    continue
                                else:
                                    safe_len = len(think_buffer) - TAG_OPEN_LEN + 1
                                    if safe_len > 0:
                                        # 没有think标签，直接输出
                                        content_started = True
                                        yield {"type": "content", "text": think_buffer}
                                        think_buffer = ""
                                    break
                            else:
                                # 正式回答已开始
                                yield {"type": "content", "text": think_buffer}
                                think_buffer = ""
                                break

                    # 防止缓冲区无限增长
                    if len(think_buffer) > 50000:
                        if in_thinking:
                            yield {"type": "thinking", "text": think_buffer}
                        else:
                            yield {"type": "content", "text": think_buffer}
                        think_buffer = ""

        except httpx.ConnectError as e:
            logger.error(f"LLM连接失败: {e}")
            yield {"type": "error", "text": "⚠️ 无法连接大模型服务，请检查网络和LLM_BASE_URL配置"}
        except httpx.TimeoutException as e:
            logger.error(f"LLM请求超时: {e}")
            yield {"type": "error", "text": "⚠️ 大模型响应超时，请稍后重试"}
        except Exception as e:
            logger.error(f"LLM流式异常: {e}", exc_info=True)
            yield {"type": "error", "text": f"⚠️ 对话出错: {str(e)[:100]}"}

    def chat_json(self, messages: List[Dict], temperature: float = 0.3,
                  max_retries: int = 2, **kwargs) -> Dict:
        """对话并解析JSON回复，自动重试+容错"""
        last_error = None

        for attempt in range(max_retries + 1):
            result = self.chat(messages, temperature=temperature, **kwargs)
            content = result["content"].strip()

            # 清理markdown代码块包裹
            if content.startswith("```"):
                lines = content.split("\n")
                lines = [l for l in lines if not l.strip().startswith("```")]
                content = "\n".join(lines).strip()

            # 移除BOM和零宽字符
            content = content.replace('\ufeff', '').replace('\u200b', '')

            # 第一次尝试：直接解析
            try:
                return json.loads(content)
            except json.JSONDecodeError as e:
                last_error = e
                logger.warning(f"JSON解析失败(尝试{attempt+1}/{max_retries+1}): {e}")

                # 第二次尝试：提取{}包裹的内容
                import re
                match = re.search(r'\{[\s\S]*\}', content)
                if match:
                    try:
                        return json.loads(match.group())
                    except json.JSONDecodeError:
                        pass

                # 第三次尝试：修复常见JSON错误
                fixed = self._fix_json(content)
                if fixed:
                    try:
                        return json.loads(fixed)
                    except json.JSONDecodeError:
                        pass

                # 重试：让LLM重新生成
                if attempt < max_retries:
                    logger.info(f"请求LLM重新生成JSON...")
                    messages_copy = list(messages)
                    messages_copy.append({
                        "role": "assistant",
                        "content": content
                    })
                    messages_copy.append({
                        "role": "user",
                        "content": "你上次的输出JSON格式有误，请只输出合法的JSON，不要包含注释、尾逗号或其他非JSON内容。"
                    })
                    messages = messages_copy
                    continue

        # 全部失败，返回一个安全的默认结构
        logger.error(f"JSON解析彻底失败: {last_error}")
        return {
            "title": "生成失败",
            "sections": [{"type": "paragraph", "text": f"AI生成的内容格式异常，请重试。错误: {last_error}"}],
            "_raw_content": content[:500],
            "_parse_error": str(last_error),
        }

    @staticmethod
    def _fix_json(content: str) -> Optional[str]:
        """尝试修复常见的JSON格式错误"""
        import re

        # 提取JSON主体
        match = re.search(r'\{[\s\S]*\}', content)
        if not match:
            return None
        text = match.group()

        # 修复1：移除JS风格注释
        text = re.sub(r'//[^\n]*', '', text)
        text = re.sub(r'/\*[\s\S]*?\*/', '', text)

        # 修复2：移除尾逗号
        text = re.sub(r',\s*([}\]])', r'\1', text)

        # 修复3：key没有引号
        text = re.sub(r'(?<=[{,\n])\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*:', r'"\1":', text)

        # 修复4：单引号→双引号
        text = text.replace("'", '"')

        # 修复5：True/False/None→true/false/null
        text = re.sub(r'\bTrue\b', 'true', text)
        text = re.sub(r'\bFalse\b', 'false', text)
        text = re.sub(r'\bNone\b', 'null', text)

        return text

    def get_status(self) -> Dict:
        """获取当前LLM配置状态"""
        return {
            "provider": self.provider,
            "base_url": self.base_url,
            "model": self.model,
            "max_tokens": self.max_tokens,
            "temperature": self.temperature,
            "thinking_model": self.thinking_model,
            "supports_tools": self.supports_tools,
        }


# 全局单例
llm_client = LLMClient()
