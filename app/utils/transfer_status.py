from redis.asyncio import Redis
import os
from dotenv import load_dotenv
import json
from datetime import datetime
from app.utils.api_caller import call_api
import logging

logger = logging.getLogger(__name__)

load_dotenv()
redis_url = os.getenv('REDIS_TRANSFER_STATUS')


async def check_user_transfer_status(user_id: str) -> dict | None:
    """
    检查用户是否有转人工会话
    :param user_id: 用户ID
    :return:
    """
    redis_conn = Redis.from_url(redis_url)
    try:
        key = f"transfer:{user_id}"
        data = await redis_conn.get(key)
        if not data:
            return None
        return json.loads(data)
    finally:
        await redis_conn.aclose()

async def save_transfer_status(user_id: str, session_id: str, status: str, token: str = None):
    """
    保存转人工状态到Redis
    :param user_id: 用户ID
    :param session_id: 转接会话ID
    :param status: 状态(in_queue / human_active)
    :param token: 用户认证token
    :return:
    """
    redis_conn = Redis.from_url(redis_url)
    try:
        key = f"transfer:{user_id}"
        data = {
            'session_id': session_id,
            'status': status,
            'token': token,
            'created_at': datetime.now().isoformat()
        }
        await redis_conn.set(key, json.dumps(data), ex=1800)    # 30分钟
    finally:
        await redis_conn.aclose()

async def remove_transfer_status(user_id: str):
    """
    移除转人工状态(会话结束后)
    :param user_id: 用户ID
    :return:
    """
    redis_conn = Redis.from_url(redis_url)
    try:
        key = f"transfer:{user_id}"
        await redis_conn.delete(key)
    finally:
        await redis_conn.aclose()

async def forward_message(session_id: str, content: str, token: str) -> None:
    """
    排队中，留言转发消息给人工客服
    :param session_id: 转接会话ID
    :param content: 消息内容
    :param token: 用户认证token
    """
    try:
        await call_api(os.getenv('TRANSFER_MESSAGE'), token=token, method='POST', params={
            'session_id': session_id,
            'content': content,
            'message_type': 'text'
        })
    except Exception as e:
        logger.warning(f"转发消息失败：{e}")