from pydantic import BaseModel, Field

class ChatRequest(BaseModel):
    message: str = Field(..., description='用户输入的消息')
    session_id: str = Field(..., description='会话ID')

class ChatResponse(BaseModel):
    reply: str = Field(...,description='Agent生成的回复')
    session_id: str = Field(...,description='会话ID')