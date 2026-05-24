from __future__ import annotations
"""对话API路由 - 集成记忆系统、Skill工具调用、自我进化、知识库RAG"""
import asyncio
import json
import logging
import os
import shutil
import uuid
from typing import List, Optional

from fastapi import APIRouter, HTTPException, Query, UploadFile, File
from fastapi.responses import StreamingResponse
from sse_starlette.sse import EventSourceResponse

from models.schemas import (
    ChatRequest, ChatMessage,
    EvolutionRequest, SkillCreateRequest
)
from core.llm import llm_client, truncate_messages
from core.memory import memory_system
from core.evolution import evolution_engine
from core.skills import skill_manager
from core.knowledge import knowledge_base
from core.file_parser import extract_text, get_file_type, is_supported, extract_image_base64, get_image_media_type, SUPPORTED_EXTENSIONS
from config.settings import settings

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/chat", tags=["对话"])


# ===== 文件上传 =====

@router.post("/upload")
async def upload_files(files: List[UploadFile] = File(...)):
    """上传文件并提取文本内容作为对话上下文

    支持格式: docx, xlsx, pptx, pdf, png/jpg/gif/bmp/webp, txt/md/csv/json/yaml
    """
    if not files:
        raise HTTPException(status_code=400, detail="未选择文件")

    upload_dir = settings.DATA_DIR / "uploads"
    upload_dir.mkdir(parents=True, exist_ok=True)

    results = []
    for f in files:
        filename = f.filename or "unknown"
        if not is_supported(filename):
            results.append({
                "filename": filename,
                "type": "unsupported",
                "error": f"不支持的文件格式，支持: {', '.join(sorted(set(SUPPORTED_EXTENSIONS.values())))}"
            })
            continue

        # 保存文件
        file_id = str(uuid.uuid4())[:8]
        ext = os.path.splitext(filename)[1]
        save_path = upload_dir / f"{file_id}{ext}"

        try:
            with open(save_path, "wb") as out:
                shutil.copyfileobj(f.file, out)
        except Exception as e:
            results.append({
                "filename": filename,
                "type": "error",
                "error": f"文件保存失败: {e}"
            })
            continue

        # 提取文本
        file_type = get_file_type(filename)
        try:
            text = extract_text(str(save_path), filename)
        except Exception as e:
            logger.error(f"文件解析失败 {filename}: {e}")
            text = f"[文件解析失败: {e}]"

        result = {
            "filename": filename,
            "type": file_type,
            "text": text,
        }

        # 图片额外提供base64（用于视觉模型）
        if file_type == "image":
            b64 = extract_image_base64(str(save_path))
            if b64:
                result["image_base64"] = b64
                result["media_type"] = get_image_media_type(filename)

        results.append(result)

        # 清理临时文件
        try:
            os.remove(save_path)
        except Exception:
            pass

    return {"files": results}


@router.post("")
async def chat(req: ChatRequest):
    """发送消息 - 集成记忆+Skill+进化"""
    conversation_id = req.conversation_id or str(uuid.uuid4())
    user_id = req.user_id or "default"

    # 1. 保存用户消息到记忆系统
    memory_system.save_message(
        conversation_id=conversation_id,
        role="user",
        content=req.message,
    )

    # 2. 构建上下文（包含长期记忆检索）
    context_messages = memory_system.build_context(
        conversation_id=conversation_id,
        current_message=req.message,
        max_messages=llm_client.max_context_messages,
    )

    # 3. 获取系统prompt（含进化学习的规则）
    system_prompt = evolution_engine.get_system_prompt()

    # 4. 注入Skill能力描述
    visible_skills = skill_manager.get_visible_skills(user_id)
    skill_descriptions = "\n".join(
        f"- {s['display_name']}({s['name']}): {s['description']}"
        for s in visible_skills
    )
    skill_context = f"""
你可以使用以下工具来帮助用户（当用户需求匹配时，你会自动调用对应工具）：
{skill_descriptions}

注意：直接回答用户问题，如果需要用到工具会自动调用。不要提及工具的存在，自然地帮助用户。"""

    # 构建完整消息列表
    messages = [{"role": "system", "content": system_prompt + skill_context}]

    # 5. 文件上下文（如果上传了文件）
    if req.file_contexts:
        file_parts = []
        for fc in req.file_contexts:
            fname = fc.get("filename", "文件")
            ftype = fc.get("type", "未知")
            ftext = fc.get("text", "")
            if ftype == "image" and fc.get("image_base64"):
                file_parts.append(f"【图片: {fname}】（图片内容将通过视觉模型识别）")
            elif ftext:
                file_parts.append(f"【文件: {fname} (类型: {ftype})】\n{ftext}")
        if file_parts:
            messages.append({
                "role": "system",
                "content": f"用户上传了以下文件作为对话上下文，请参考这些内容回答用户问题：\n\n" + "\n\n".join(file_parts)
            })

        # 图片通过视觉模型处理：在最后一条用户消息中添加图片
        image_contexts = [fc for fc in req.file_contexts if fc.get("type") == "image" and fc.get("image_base64")]
        if image_contexts:
            # 修改最后一条用户消息为多模态格式
            user_msg = context_messages[-1] if context_messages else {"role": "user", "content": req.message}
            image_parts = []
            for ic in image_contexts:
                media_type = ic.get("media_type", "image/png")
                image_parts.append({
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:{media_type};base64,{ic['image_base64']}"
                    }
                })
            # 构建多模态content
            multimodal_content = [{"type": "text", "text": user_msg["content"]}] + image_parts
            if context_messages:
                context_messages[-1]["content"] = multimodal_content
            else:
                context_messages.append({"role": "user", "content": multimodal_content})

    # 6. 知识库RAG（如果选择了知识库）
    if req.kb_ids:
        rag_context = knowledge_base.build_rag_context(req.kb_ids, req.message)
        if rag_context:
            messages.append({
                "role": "system",
                "content": f"以下是从知识库中检索到的相关内容，请参考这些内容回答用户问题。如果检索内容与问题无关，可以忽略。\n\n【知识库内容】\n{rag_context}"
            })

    messages.extend(context_messages)

    # 截断消息防止超过上下文窗口
    messages = truncate_messages(messages, llm_client.context_window, reserved_tokens=llm_client.max_tokens)

    # 5. 尝试Function Calling方式处理
    try:
        result = await skill_manager.process_with_tools(messages, user_id)
        content = result["content"]
        tool_calls = result.get("tool_calls", [])
        thinking = result.get("thinking")

        # 如果有工具调用，附加结果说明
        if tool_calls:
            tool_summary_parts = []
            for tc in tool_calls:
                tc_result = tc.get("result", {})
                if isinstance(tc_result, dict):
                    if "error" in tc_result:
                        tool_summary_parts.append(f"⚠️ 工具 {tc['name']} 执行出错: {tc_result['error']}")
                    else:
                        tool_summary_parts.append(f"✅ 已执行: {tc['name']}")
            if tool_summary_parts and content:
                content = content + "\n\n---\n" + "\n".join(tool_summary_parts)

    except Exception as e:
        logger.warning(f"Function calling处理失败，回退普通对话: {e}")
        # 回退到普通对话
        result = llm_client.chat(messages)
        content = result["content"]
        thinking = result.get("thinking")
        tool_calls = []

    # 6. 保存助手回复
    meta = {}
    if thinking:
        meta["thinking"] = thinking
    if tool_calls:
        meta["tool_calls"] = tool_calls
    memory_system.save_message(
        conversation_id=conversation_id,
        role="assistant",
        content=content,
        metadata=meta if meta else None,
    )

    # 7. 后处理放到线程池，避免同步LLM调用阻塞事件循环
    # 注意: memory_system/evolution_engine 的 async 方法内部调了同步的 llm_client.chat()
    # 它们虽声明为 async 但实际是伪异步(propagates阻塞)，必须放到单独线程
    def _post_processing_blocking():
        try:
            import asyncio as _aio
            loop = _aio.new_event_loop()
            try:
                loop.run_until_complete(
                    memory_system.extract_and_save_memories(conversation_id)
                )
            except Exception as e:
                logger.error(f"记忆提取失败: {e}")
            try:
                msg_count = len(memory_system.get_messages(conversation_id))
                if msg_count % 20 == 0:
                    loop.run_until_complete(
                        memory_system.generate_summary(conversation_id)
                    )
            except Exception as e:
                logger.error(f"摘要生成失败: {e}")
            try:
                loop.run_until_complete(
                    evolution_engine.on_conversation_turn(conversation_id)
                )
            except Exception as e:
                logger.error(f"进化检查失败: {e}")
            finally:
                loop.close()
        except Exception as e:
            logger.error(f"后处理整体失败: {e}")

    loop = asyncio.get_event_loop()
    loop.run_in_executor(None, _post_processing_blocking)

    return {
        "conversation_id": conversation_id,
        "message": {
            "id": str(uuid.uuid4()),
            "role": "assistant",
            "content": content,
            "tool_calls": tool_calls,
        },
    }


@router.post("/stream")
async def chat_stream(req: ChatRequest):
    """流式对话 - SSE"""
    conversation_id = req.conversation_id or str(uuid.uuid4())
    user_id = req.user_id or "default"

    # 保存用户消息
    memory_system.save_message(
        conversation_id=conversation_id,
        role="user",
        content=req.message,
    )

    # 构建上下文
    context_messages = memory_system.build_context(
        conversation_id=conversation_id,
        current_message=req.message,
    )
    system_prompt = evolution_engine.get_system_prompt()

    visible_skills = skill_manager.get_visible_skills(user_id)
    skill_descriptions = "\n".join(
        f"- {s['display_name']}({s['name']}): {s['description']}"
        for s in visible_skills
    )
    skill_context = f"\n\n你可以使用以下工具：\n{skill_descriptions}"

    messages = [{"role": "system", "content": system_prompt + skill_context}]

    # 文件上下文
    if req.file_contexts:
        file_parts = []
        for fc in req.file_contexts:
            fname = fc.get("filename", "文件")
            ftype = fc.get("type", "未知")
            ftext = fc.get("text", "")
            if ftype == "image" and fc.get("image_base64"):
                file_parts.append(f"【图片: {fname}】（图片内容将通过视觉模型识别）")
            elif ftext:
                file_parts.append(f"【文件: {fname} (类型: {ftype})】\n{ftext}")
        if file_parts:
            messages.append({
                "role": "system",
                "content": f"用户上传了以下文件作为对话上下文，请参考这些内容回答用户问题：\n\n" + "\n\n".join(file_parts)
            })

        # 图片通过视觉模型处理
        image_contexts = [fc for fc in req.file_contexts if fc.get("type") == "image" and fc.get("image_base64")]
        if image_contexts:
            user_msg = context_messages[-1] if context_messages else {"role": "user", "content": req.message}
            image_parts = []
            for ic in image_contexts:
                media_type = ic.get("media_type", "image/png")
                image_parts.append({
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:{media_type};base64,{ic['image_base64']}"
                    }
                })
            multimodal_content = [{"type": "text", "text": user_msg["content"]}] + image_parts
            if context_messages:
                context_messages[-1]["content"] = multimodal_content
            else:
                context_messages.append({"role": "user", "content": multimodal_content})

    # 知识库RAG
    if req.kb_ids:
        rag_context = knowledge_base.build_rag_context(req.kb_ids, req.message)
        if rag_context:
            messages.append({
                "role": "system",
                "content": f"以下是从知识库中检索到的相关内容，请参考这些内容回答用户问题。如果检索内容与问题无关，可以忽略。\n\n【知识库内容】\n{rag_context}"
            })

    messages.extend(context_messages)

    # 截断消息防止超过上下文窗口
    messages = truncate_messages(messages, llm_client.context_window, reserved_tokens=llm_client.max_tokens)

    # 先尝试工具调用（异步），然后流式输出最终回复
    tool_calls = []
    try:
        functions = skill_manager.get_functions_schema(user_id)
        if functions and getattr(llm_client, 'supports_tools', True):
            tool_resp = await llm_client.async_client.post(
                llm_client._get_url(),
                headers=llm_client._get_headers(),
                json={
                    "model": llm_client.model,
                    "messages": messages,
                    "tools": functions,
                    "tool_choice": "auto",
                    "temperature": llm_client.temperature,
                    "max_tokens": llm_client.max_tokens,
                },
                timeout=30.0,
            )
            # 400 = 后端不支持tools，标记并跳过
            if tool_resp.status_code == 400:
                logger.warning("LLM返回400（不支持tools），跳过tool calling")
                llm_client.supports_tools = False
            else:
                tool_resp.raise_for_status()
                tool_data = tool_resp.json()
                choice = tool_data["choices"][0]
                tool_call_list = choice.get("message", {}).get("tool_calls")
                if tool_call_list:
                    messages.append({
                        "role": "assistant",
                        "content": choice["message"].get("content") or "",
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
                        skill_manager._skill_usage[func_name] = skill_manager._skill_usage.get(func_name, 0) + 1
                        tool_result = await skill_manager._execute_skill(func_name, func_args)
                        tool_calls.append({"name": func_name, "arguments": func_args, "result": tool_result})
                        messages.append({
                            "role": "tool",
                            "tool_call_id": tc["id"],
                            "content": json.dumps(tool_result, ensure_ascii=False) if not isinstance(tool_result, str) else tool_result,
                        })
    except Exception as e:
        logger.warning(f"流式模式工具调用失败: {e}")

    async def event_stream():
        full_content = ""
        full_thinking = ""
        is_error = False
        try:
            # 先发送工具调用信息
            if tool_calls:
                tool_info = "\n".join(
                    f"🔨 调用工具: {tc['name']}" for tc in tool_calls
                )
                yield {"data": json.dumps({"type": "tool_calls", "tools": tool_info}, ensure_ascii=False), "event": "tool"}

            async for chunk in llm_client.chat_stream_async(messages):
                chunk_type = chunk.get("type", "content")
                chunk_text = chunk.get("text", "")

                if chunk_type == "error":
                    is_error = True
                    full_content = chunk_text
                    yield {"data": json.dumps({"type": "error", "text": chunk_text}, ensure_ascii=False), "event": "error"}
                    break
                elif chunk_type == "thinking":
                    full_thinking += chunk_text
                    yield {"data": json.dumps({"type": "thinking", "text": chunk_text}, ensure_ascii=False), "event": "thinking"}
                elif chunk_type == "content":
                    full_content += chunk_text
                    yield {"data": json.dumps({"type": "content", "text": chunk_text}, ensure_ascii=False), "event": "message"}

        except Exception as e:
            logger.error(f"流式对话异常: {e}", exc_info=True)
            if not full_content:
                full_content = f"抱歉，对话过程中出现错误：{str(e)}"
                is_error = True
                yield {"data": json.dumps({"type": "error", "text": full_content}, ensure_ascii=False), "event": "error"}

        # 保存助手回复（错误消息也保存，方便排查）
        if full_content:
            try:
                meta = {}
                if full_thinking:
                    meta["thinking"] = full_thinking
                if tool_calls:
                    meta["tool_calls"] = tool_calls
                if is_error:
                    meta["is_error"] = True
                memory_system.save_message(
                    conversation_id=conversation_id,
                    role="assistant",
                    content=full_content,
                    metadata=meta if meta else None,
                )
            except Exception as e:
                logger.warning(f"保存消息失败: {e}")

        # 后处理放到线程池避免阻塞事件循环
        def _post_blocking():
            try:
                import asyncio as _aio
                loop = _aio.new_event_loop()
                try:
                    if not is_error:
                        loop.run_until_complete(
                            memory_system.extract_and_save_memories(conversation_id)
                        )
                        msg_count = len(memory_system.get_messages(conversation_id))
                        if msg_count % 20 == 0:
                            loop.run_until_complete(
                                memory_system.generate_summary(conversation_id)
                            )
                        loop.run_until_complete(
                            evolution_engine.on_conversation_turn(conversation_id)
                        )
                except Exception as e:
                    logger.error(f"后处理失败: {e}")
                finally:
                    loop.close()
            except Exception:
                pass

        try:
            asyncio.get_event_loop().run_in_executor(None, _post_blocking)
        except RuntimeError:
            pass

        yield {"data": json.dumps({"type": "done", "conversation_id": conversation_id}, ensure_ascii=False), "event": "done"}

    return EventSourceResponse(event_stream())


# ===== 对话管理 =====

@router.get("/conversations")
async def list_conversations():
    """对话列表"""
    return memory_system.list_conversations()


@router.get("/conversations/{conversation_id}/messages")
async def get_messages(conversation_id: str, limit: int = Query(50, ge=1, le=200)):
    """获取对话历史"""
    messages = memory_system.get_messages(conversation_id, limit=limit)
    if not messages:
        raise HTTPException(status_code=404, detail="对话不存在")
    return messages


@router.delete("/conversations/{conversation_id}")
async def delete_conversation(conversation_id: str):
    """删除对话"""
    memory_system.delete_conversation(conversation_id)
    return {"status": "ok"}


@router.get("/conversations/{conversation_id}/summarize")
async def summarize_conversation(conversation_id: str):
    """手动触发对话摘要"""
    try:
        summary = await memory_system.generate_summary(conversation_id)
        return {"summary": summary}
    except Exception as e:
        logger.warning(f"生成摘要失败: {e}")
        return {"summary": "", "error": str(e)}


# ===== 记忆管理 =====

@router.get("/memory/search")
async def search_memory(q: str = Query(..., description="搜索关键词"),
                         category: str = Query(None, description="分类过滤"),
                         limit: int = Query(10, ge=1, le=50)):
    """搜索长期记忆"""
    results = memory_system.search_long_term(q, category=category, limit=limit)
    return results


@router.get("/memory/long-term")
async def list_long_term_memory(category: str = Query(None)):
    """列出长期记忆"""
    return memory_system.search_long_term("", category=category, limit=50)


@router.delete("/memory/long-term/{memory_id}")
async def delete_long_term_memory(memory_id: str):
    """删除长期记忆"""
    import sqlite3
    with sqlite3.connect(memory_system.db_path) as conn:
        conn.execute("DELETE FROM long_term_memory WHERE id = ?", (memory_id,))
        conn.commit()
    return {"status": "ok"}


# ===== 进化管理 =====

@router.post("/evolve")
async def manual_evolve(req: EvolutionRequest):
    """手动触发自我进化"""
    result = await evolution_engine.manual_evolve(req.instruction)
    return result


@router.get("/evolve/status")
async def get_evolve_status():
    """获取进化状态"""
    return evolution_engine.get_status()


@router.get("/evolve/logs")
async def get_evolve_logs(type: str = Query(None), limit: int = Query(50)):
    """获取进化日志"""
    return memory_system.get_evolution_logs(evo_type=type, limit=limit)


# ===== Skill管理 =====

@router.get("/skills")
async def list_skills(user_id: str = Query("default")):
    """获取可见skills（渐进式披露）"""
    visible = skill_manager.get_visible_skills(user_id)
    level_info = skill_manager.get_skill_level_info(user_id)
    return {"skills": visible, "level_info": level_info}


@router.get("/skills/all")
async def list_all_skills():
    """列出所有skills（管理视图）"""
    return skill_manager.list_all_skills()


@router.post("/skills")
async def create_skill(req: SkillCreateRequest):
    """创建自定义skill"""
    skill_def = {
        "name": req.name,
        "display_name": req.display_name,
        "description": req.description,
        "level": req.level,
        "parameters": req.parameters,
        "category": req.category,
    }
    file_path = skill_manager.save_custom_skill(skill_def)
    return {"status": "ok", "file": file_path}


@router.delete("/skills/{name}")
async def delete_skill(name: str):
    """删除自定义skill"""
    if skill_manager.delete_skill(name):
        return {"status": "ok"}
    raise HTTPException(status_code=400, detail="无法删除内置skill或skill不存在")


@router.get("/skills/{name}")
async def get_skill(name: str):
    """获取skill详情"""
    skill = skill_manager.get_skill(name)
    if skill:
        return skill
    raise HTTPException(status_code=404, detail="Skill不存在")


# ===== LLM Provider管理 =====

@router.get("/llm/status")
async def get_llm_status():
    """获取当前LLM配置"""
    return llm_client.get_status()


@router.post("/llm/switch")
async def switch_llm_provider(req: dict):
    """切换LLM Provider"""
    provider = req.get("provider", "")
    thinking_model = req.get("thinking_model", None)  # None=自动, true/false=手动覆盖
    if not provider:
        raise HTTPException(status_code=400, detail="缺少provider参数")
    try:
        llm_client.switch_provider(provider)
        if thinking_model is not None:
            llm_client.thinking_model = thinking_model
        llm_client.supports_tools = True  # 重置，让后续请求自动检测
        return {"status": "ok", **llm_client.get_status()}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/llm/config")
async def save_llm_config(req: dict):
    """保存某个provider的配置到环境变量文件"""
    provider = req.get("provider", "")
    if provider not in ("vllm", "tencent", "openai", "custom"):
        raise HTTPException(status_code=400, detail="无效的provider")

    # 构建要保存的键值对
    updates = {}
    prefix = f"LLM_{provider.upper()}_"
    if provider == "vllm":
        prefix = "LLM_"

    if req.get("base_url"):
        updates[f"{prefix}BASE_URL"] = req["base_url"]
    if req.get("api_key"):
        updates[f"{prefix}API_KEY"] = req["api_key"]
    if req.get("model"):
        updates[f"{prefix}MODEL"] = req["model"]

    if not updates:
        return {"message": "无变更"}

    # 更新settings实例
    settings_obj = settings
    for key, value in updates.items():
        if hasattr(settings_obj, key):
            setattr(settings_obj, key, value)
        # 同时更新llm_client对应属性
        if provider == llm_client.provider:
            if "BASE_URL" in key:
                llm_client.base_url = value
            elif "API_KEY" in key:
                llm_client.api_key = value
            elif "MODEL" in key:
                llm_client.model = value

    # 写入user.env持久化
    env_path = settings.USER_DIR / "user.env"
    existing = {}
    if env_path.exists():
        with open(env_path, "r", encoding="utf-8", errors="ignore") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, _, v = line.partition("=")
                    existing[k.strip()] = v.strip()

    existing.update(updates)
    env_path.parent.mkdir(parents=True, exist_ok=True)
    with open(env_path, "w", encoding="utf-8") as f:
        f.write("# 用户自定义配置 - 重启后生效\n")
        f.write("# 此文件优先级高于 config/default.env\n\n")
        for k, v in existing.items():
            f.write(f"{k}={v}\n")

    return {"message": f"已保存 {len(updates)} 项配置到 user/user.env，重启后生效"}
