from http.client import HTTPException

from fastapi import APIRouter
from app.schemas.chat import ChatResponse, ChatRequest
from langchain.messages import HumanMessage, AIMessage
from app.core.agent import agent

router = APIRouter(prefix='/api', tags=['对话'])

@router.post('/chat',response_model=ChatResponse)
async def chat(request: ChatRequest):
    try:
        # 调用Agent 传入用户信息
        result = agent.invoke({'messages': [HumanMessage(request.message)]})
        ai_message = result.get('messages', [])[-1]
        # 查看最后一条信息是否属于AIMessage
        if not isinstance(ai_message, AIMessage):
            raise HTTPException(status_code=500, detail='Agent未返回任何回复')
        reply = ai_message.content if hasattr(ai_message, 'content') else str(ai_message)
        return ChatResponse(reply=reply,session_id=request.session_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Agent调用失败：{str(e)}")