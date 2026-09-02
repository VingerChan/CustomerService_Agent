import httpx
from fastapi import APIRouter, HTTPException, Depends
from app.schemas.chat import ChatResponse, ChatRequest
from langchain.messages import HumanMessage, AIMessage
from app.core.agent import get_agent
from app.core.auth import get_user_info

router = APIRouter(prefix='/api', tags=['对话'])

@router.post('/chat',response_model=ChatResponse)
async def chat(request: ChatRequest, agent = Depends(get_agent)):
    try:
        user_info = await get_user_info(request.token)
        user_id = str(user_info.get('user_id'))
        if not user_id:
            raise HTTPException(status_code=401, detail='无法获取用户信息')
        config = {'configurable': {'thread_id': user_id}}
        # 调用Agent 传入用户信息
        result = await agent.ainvoke({'messages': [HumanMessage(request.message)]}, config=config)
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