import logging
import os
import re
from typing import Optional, AsyncGenerator
from app.schemas.chat import ChatRequest, ChatResponse
from dotenv import load_dotenv
from app.utils.transfer_status import save_transfer_status, forward_message, check_user_transfer_status
from app.utils.message_utils import retrieve_memories, build_messages
from langchain_core.messages import AIMessageChunk
from app.utils.sanitizer import detect_injection, sanitize_input
import json

load_dotenv()

logger = logging.getLogger(__name__)

REJECTION_REPLY = "抱歉，您的消息包含不支持的内容，请重新描述您的电商相关问题。"
SYSTEM_ERROR_REPLY = "抱歉，系统暂时出现问题，请稍后重试。"
CONTENT_BLOCKED_REPLY = "抱歉，您的消息包含不支持的内容，请重新描述您的问题。"


def filter_output(text: str) -> str:
    """输出过滤：脱敏敏感信息"""
    # 订单号脱敏：只显示前6位和后4位
    text = re.sub(
        r'订单号[：:]\s*(\d{6})\d+(\d{4})',
        lambda m: f'订单号：{m.group(1)}****{m.group(2)}',
        text
    )
    # 移除可能泄露的 API key
    api_key = os.getenv('DASHSCOPE_API_KEY', '')
    if api_key and api_key in text:
        text = text.replace(api_key, "***")
    return text

async def handle_transfer(user_id: str, request: ChatRequest, transfer_info: dict) -> Optional[ChatResponse]:
    """
    处理转人工状态。如果消息已被转人工拦截，返回 ChatResponse；否则返回 None。
    :param user_id: 用户ID
    :param request: 聊天请求
    :param transfer_info: Redis中的转人工状态信息
    :return: ChatResponse 或 None
    """
    session_id = transfer_info['session_id']
    transfer_token = transfer_info.get('token', request.token)

    if transfer_info['status'] == 'in_queue':
        return await _handle_in_queue(user_id, request, session_id, transfer_token)

    elif transfer_info['status'] == 'human_active':
        return await _handle_human_active(user_id, request, session_id, transfer_token)

    return None


async def _handle_in_queue(
    user_id: str, request: ChatRequest, session_id: str, transfer_token: str
) -> ChatResponse:
    """处理排队中的转人工状态"""
    from app.utils.api_caller import call_api

    try:
        queue_result = await call_api(
            os.getenv('TRANSFER_QUEUE').replace('{session_id}', session_id),
            token=transfer_token,
            method='GET',
        )
        status = queue_result.get('status', 'in_queue')

        # VinShop已分配客服，自动同步Redis状态
        if status == 'human_active':
            await save_transfer_status(user_id, session_id, 'human_active', transfer_token)
            await forward_message(session_id, request.message, transfer_token)
            return ChatResponse(
                reply="",
                session_id=user_id,
                transfer_status='active',
                transfer_session_id=session_id
            )

        # 仍在排队：转发消息作为留言
        await forward_message(session_id, request.message, transfer_token)

        position = queue_result.get('position', 0)
        estimated_wait = queue_result.get('estimated_wait_seconds', 0)
        return ChatResponse(
            reply=f"您当前正在排队中，排队位置：第{position}位，"
                  f"预计等待：{estimated_wait}秒。\n"
                  f"如需留言请说\"留言：xxx\"，如需取消转人工请说\"取消转人工\"。",
            session_id=user_id,
            transfer_status='pending',
            transfer_session_id=session_id
        )
    except Exception as e:
        logger.error(f"查询排队状态失败: {e}")
        return ChatResponse(
            reply="您当前正在排队中，请稍后...",
            session_id=user_id,
            transfer_status='pending',
            transfer_session_id=session_id
        )


async def _handle_human_active(
    user_id: str, request: ChatRequest, session_id: str, transfer_token: str
) -> ChatResponse:
    """处理已接通人工客服的状态"""
    await forward_message(session_id, request.message, transfer_token)
    return ChatResponse(
        reply="",
        session_id=user_id,
        transfer_status='active',
        transfer_session_id=session_id
    )


async def stream_agent_response(
    user_id: str,
    token: str,
    message: str,
    agent
) -> AsyncGenerator[str, None]:
    """
    流式调用Agent并生成SSE格式响应
    :param user_id: 用户ID
    :param token: 用户认证token
    :param message: 用户消息
    :param agent: Agent实例
    :yield: SSE格式字符串，格式: data: {"type": "text|transfer|done", ...}\n\n
    """
    # === 防护1：输入清洗 ===
    message = sanitize_input(message)

    # === 防护2：注入检测 ===
    is_injection, pattern = detect_injection(message)
    if is_injection:
        logger.warning(f"[Security] 检测到注入尝试: user_id={user_id}, pattern={pattern}")
        yield f"data: {json.dumps({'type': 'text', 'content': REJECTION_REPLY}, ensure_ascii=False)}\n\n"
        yield f"data: {json.dumps({'type': 'done'})}\n\n"
        return

    # 1. 检索长期记忆
    memories = await retrieve_memories(user_id, message)

    # 2. 构建消息列表
    messages = build_messages(memories, message)

    # 3. 流式调用Agent
    config = {'configurable': {'thread_id': user_id, 'token': token}}
    transfer_detected = False

    try:
        async for chunk, metadata in agent.astream(
            {"messages": messages},
            config,
            stream_mode="messages"
        ):
            if isinstance(chunk, AIMessageChunk):
                # 检测转人工 tool_calls
                if hasattr(chunk, 'tool_calls') and chunk.tool_calls:
                    for tool_call in chunk.tool_calls:
                        if tool_call.get('name') == 'transfer_to_human':
                            transfer_detected = True

                # 输出文本内容
                if chunk.content:
                    # === 防护3：输出过滤 ===
                    filtered_content = filter_output(chunk.content)
                    yield f"data: {json.dumps({'type': 'text', 'content': filtered_content}, ensure_ascii=False)}\n\n"
    except Exception as e:
        # === 防护4：平台内容审核异常处理 ===
        error_msg = str(e)
        if 'data_inspection_failed' in error_msg or 'inappropriate content' in error_msg:
            logger.warning(f"[Security] 平台内容审核拦截: user_id={user_id}")
            yield f"data: {json.dumps({'type': 'text', 'content': CONTENT_BLOCKED_REPLY}, ensure_ascii=False)}\n\n"
        else:
            logger.error(f"Agent调用异常: {e}", exc_info=True)
            yield f"data: {json.dumps({'type': 'text', 'content': SYSTEM_ERROR_REPLY}, ensure_ascii=False)}\n\n"

    # 4. 流结束后，处理转人工状态
    if transfer_detected:
        transfer_info = await check_user_transfer_status(user_id)
        if transfer_info:
            yield f"data: {json.dumps({'type': 'transfer', 'status': 'pending', 'session_id': transfer_info['session_id']}, ensure_ascii=False)}\n\n"

    # 5. 发送完成信号
    yield f"data: {json.dumps({'type': 'done'})}\n\n"