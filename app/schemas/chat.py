from pydantic import BaseModel, Field
from typing import Optional

class ChatRequest(BaseModel):
    message: str = Field(..., description='用户输入的消息')
    token: str = Field(..., description='用户认证token，用于调用平台API获取用户信息')

class ChatResponse(BaseModel):
    reply: str = Field(..., description='Agent生成的回复')
    session_id: str = Field(..., description='会话ID')
    transfer_status: Optional[str] = Field(
        None,
        description='转人工状态：null(未转)、pending(排队中)、active(人工服务中)'
    )
    transfer_session_id: Optional[str] = Field(
        None,
        description='转人工会话ID，仅当transfer_status不为null时有值'
    )