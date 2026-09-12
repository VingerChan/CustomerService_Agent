from fastapi import APIRouter, Security, HTTPException
from app.schemas.transfer import TransferStatusUpdateRequest
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from app.utils.auth import get_user_info
from app.utils.transfer_status import remove_transfer_status, save_transfer_status


security = HTTPBearer()

router = APIRouter(prefix='/api/transfer', tags=['转人工'])

@router.post('/status-update')
async def update_transfer_status(request: TransferStatusUpdateRequest, credentials: HTTPAuthorizationCredentials = Security(security)):
    """
    前端在收到VinShop WebSocket通知后调用此接口更新转人工状态
    :param request: 包含session_id 和 status 的请求体
    :param credentials: Bearer Token
    :return:
    """
    token = credentials.credentials
    try:
        user_info = await get_user_info(token)
        user_id = str(user_info.get('user_id'))
        if not user_id:
            raise HTTPException(status_code=401, detail='无法获取用户信息')
    except Exception:
        raise HTTPException(status_code=401, detail='token无效或已过期')
    try:
        if request.status == 'session_completed':
            # 会话结束：删除Redis中的转人工标记
            await remove_transfer_status(user_id)
        else:    # 客服接入，更新状态为human_active
            await save_transfer_status(user_id=user_id, session_id=request.session_id, status=request.status, token=token)
        return {'success': True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"状态更新失败：{str(e)}")

