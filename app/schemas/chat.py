from pydantic import BaseModel, Field

class ChatRequest(BaseModel):
    message: str = Field(..., description='用户输入的消息')
    token: str = Field(..., description='用户认证token，用于调用平台API获取用户信息')

class ChatResponse(BaseModel):
    reply: str = Field(...,description='Agent生成的回复')
    session_id: str = Field(...,description='会话ID')