import httpx
from fastapi import APIRouter, HTTPException, Depends
from app.schemas.chat import ChatResponse, ChatRequest
from langchain.messages import HumanMessage, AIMessage, SystemMessage
from app.agents.agent import get_agent
from app.utils.auth import get_user_info
from app.memory.long_term import get_vector_memory
from app.utils.transfer_status import check_user_transfer_status
from app.utils.api_caller import call_api
import re

router = APIRouter(prefix='/api', tags=['对话'])

@router.post('/chat',response_model=ChatResponse)
async def chat(request: ChatRequest, agent = Depends(get_agent)):
    try:
        user_info = await get_user_info(request.token)
        user_id = str(user_info.get('user_id'))
        if not user_id:
            raise HTTPException(status_code=401, detail='无法获取用户信息')
        # 检查转人工状态
        transfer_info = await check_user_transfer_status(user_id)
        if transfer_info:
            if transfer_info['status'] == 'in_queue':
                # 排队中：调用VinShop API获取排队信息返回
                try:
                    session_id = transfer_info['session_id']
                    queue_result = await call_api(
                        f"/api/transfer/queue-position/{session_id}/",
                        token=transfer_info.get('token', request.token),
                        method='GET'
                    )
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
                except Exception:
                    return ChatResponse(
                        reply="您当前正在排队中，请稍后...",
                        session_id=user_id,
                        transfer_status='pending',
                        transfer_session_id=transfer_info['session_id']
                    )
            elif transfer_info['status'] == 'human_active':
                # 已接通人工客服：Agent不回复
                return ChatResponse(
                    reply="",
                    session_id=user_id,
                    transfer_status='active',
                    transfer_session_id=transfer_info['session_id']
                )

        # ===== 无转人工标记：正常Agent处理 =====
        # 从长期记忆中检索与当前问题相关的历史记忆
        try:
            vector_memory = get_vector_memory()
            memories = await vector_memory.search_memory(
                user_id=user_id,
                query=request.message,
                n_results=5,
                max_age_days=90
            )
        except Exception:
            memories = []
        # 构建消息列表：历史记忆作为SystemMessage + 用户当前消息
        messages = []
        if memories:
            memory_text = '\n'.join(f"- [{m['topic']}] {m['content']}" for m in memories)
            messages.append(SystemMessage(content=f"以下是用户的历史记忆，请参考：\n{memory_text}"))
        messages.append(HumanMessage(request.message))
        config = {'configurable': {'thread_id': user_id, 'token': request.token}}
        # 调用Agent
        result = await agent.ainvoke({'messages': messages}, config=config)
        ai_message = result.get('messages', [])[-1]
        if not isinstance(ai_message, AIMessage):
            raise HTTPException(status_code=500, detail='Agent未返回任何回复')
        reply = ai_message.content if hasattr(ai_message, 'content') else str(ai_message)
        # 检测是否触发了转人工工具
        transfer_status = None
        transfer_session_id = None
        if hasattr(ai_message, 'tool_calls') and ai_message.tool_calls:
            for tool_call in ai_message.tool_calls:
                tool_name = tool_call.get('name', '')
                if tool_name == 'transfer_to_human':
                    transfer_status = 'pending'
                    break
        # 首次触发转人工时，从Agent回复文本中提取会话ID
        # 如果回复中包含"会话ID:"，提取transfer_session_id
        if '会话ID:' in reply:
            match = re.search(r'会话ID:\s*(hs_\w+)', reply)
            if match:
                transfer_session_id = match.group(1)
        return ChatResponse(
            reply=reply,
            session_id=user_id,
            transfer_status=transfer_status,
            transfer_session_id=transfer_session_id
        )
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=401, detail='token无效或已过期')
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Agent调用失败：{str(e)}")