import logging
from app.memory.long_term import get_vector_memory
from langchain.messages import HumanMessage, SystemMessage
from typing import Optional
import re

logger = logging.getLogger(__name__)

async def retrieve_memories(user_id: str, query: str) -> list:
    """
    从长期记忆中检索与当前问题相关的历史记忆
    :param user_id: 用户ID
    :param query:  用户查询
    :return: 记忆列表
    """
    try:
        vector_memory = get_vector_memory()
        return await vector_memory.search_memory(
            user_id=user_id,
            query=query,
            n_results=5,
            max_age_days=90
        )
    except Exception as e:
        logger.warning(f"检索长期记忆失败：{e}")
        return []

def build_messages(memories: list, user_message: str) -> list:
    """
    构建Agent消息列表，历史记忆作为SystemMessage + HumanMessage
    :param memories: 长期记忆列表
    :param user_message: 用户当前消息
    :return: 消息列表
    """
    messages = []
    if memories:
        memory_text = '\n'.join(f"- [{m['topic']}] {m['content']}" for m in memories)
        messages.append(SystemMessage(content=f"以下是用户的历史记忆，请参考：\n{memory_text}"))
    messages.append(HumanMessage(content=user_message))
    return messages

def extract_session_id_from_reply(reply: str) -> Optional[str]:
    """
    从Agent回复文本中提取转人工会话ID
    :param reply: Agent回复文本
    :return: 会话ID，未找到则返回None
    """
    match = re.search(r'会话ID:\s*(hs_\w+)', reply)
    if match:
        return match.group(1)
    return None
