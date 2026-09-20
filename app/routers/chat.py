from fastapi import APIRouter, HTTPException, Depends
from app.schemas.chat import ChatRequest
from app.agents.agent import get_agent
from app.utils.auth import get_user_info
from app.utils.transfer_status import check_user_transfer_status
from app.core.chat_handler import handle_transfer, stream_agent_response
from starlette.responses import JSONResponse, StreamingResponse
from app.config.rate_limit import enforce_chat_rate_limit

router = APIRouter(prefix='/api', tags=['对话'])

@router.post('/chat')
async def chat(request: ChatRequest, agent=Depends(get_agent)):
    # 1. 用户认证
    try:
        user_info = await get_user_info(request.token)
        user_id = str(user_info.get('user_id'))
    except Exception:
        raise HTTPException(status_code=401, detail='token无效或已过期')
    if not user_id:
        raise HTTPException(status_code=401, detail='无法获取用户信息')
    # 2.限流检查
    await enforce_chat_rate_limit(user_id)
    # 3. 检查转人工状态（非流式拦截）
    try:
        transfer_info = await check_user_transfer_status(user_id)
    except Exception:
        transfer_info = None

    if transfer_info:
        result = await handle_transfer(user_id, request, transfer_info)
        if result is not None:
            return JSONResponse(content=result.model_dump())

    # 4. 正常对话流程（流式返回）
    return StreamingResponse(
        stream_agent_response(user_id, request.token, request.message, agent),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        }
    )