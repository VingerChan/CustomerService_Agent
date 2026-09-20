from dotenv import load_dotenv
import os
from app.config.redis_conf import get_redis
from datetime import datetime
from fastapi import HTTPException

load_dotenv()

async def enforce_chat_rate_limit(user_id: str):
    """
    检查chat接口速率限制，超限则抛出429 to many request
    :param user_id: 用户ID
    :return:
    """
    limit = int(os.getenv('RATE_LIMIT_CHAT', '10'))
    window = 60    # 窗口大小：60秒
    client = get_redis(2)
    window_key = int(datetime.now().timestamp() // window)     # 整除
    key = f"ratelimit:chat:{user_id}:{window_key}"
    # 返回自增后的当前值
    count = await client.incr(key)
    if count == 1:    # 刚创建
        await client.expire(key, window)    # 设置60秒过期
    if count > limit:
        raise HTTPException(status_code=429, detail='请求过于频繁，请稍后再试')