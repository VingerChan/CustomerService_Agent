from pydantic import BaseModel
from typing import Literal

class TransferStatusUpdateRequest(BaseModel):
    session_id: str
    status: Literal['human_active', 'session_completed']