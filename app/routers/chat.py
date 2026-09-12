import httpx
from fastapi import APIRouter, HTTPException, Depends
from app.schemas.chat import ChatResponse, ChatRequest
from langchain.messages import HumanMessage, AIMessage, SystemMessage
from app.agents.agent import get_agent
from app.core.auth import get_user_info
from app.memory.long_term import get_vector_memory

router = APIRouter(prefix='/api', tags=['对话'])

@router.post('/chat',response_model=ChatResponse)
async def chat(request: ChatRequest, agent = Depends(get_agent)):
    try:
        user_info = await get_user_info(request.token)
        user_id = str(user_info.get('user_id'))
        if not user_id:
            raise HTTPException(status_code=401, detail='无法获取用户信息')
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
        # 调用Agent 传入用户信息
        result = await agent.ainvoke({'messages': messages}, config=config)
        ai_message = result.get('messages', [])[-1]
        # 查看最后一条信息是否属于AIMessage
        if not isinstance(ai_message, AIMessage):
            raise HTTPException(status_code=500, detail='Agent未返回任何回复')
        reply = ai_message.content if hasattr(ai_message, 'content') else str(ai_message)
        return ChatResponse(reply=reply,session_id=user_id)
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=401, detail='token无效或已过期')
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Agent调用失败：{str(e)}")