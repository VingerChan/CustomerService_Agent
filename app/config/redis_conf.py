import os
from dotenv import load_dotenv
from redis.asyncio import Redis

load_dotenv()

# 缓存各db的Redis客户端，每个db独立连接池
_clients: dict[int, Redis] = {}

REDIS_BASE_URL = os.getenv('REDIS_BASE_URL')


def get_redis(db: int = 0) -> Redis:
    """
    获取指定db编号的Redis客户端（单例）
    每个db独立连接池，互不干扰，并发安全

    :param db: Redis数据库编号，默认0
    :return: Redis客户端实例
    """
    if db not in _clients:
        _clients[db] = Redis.from_url(
            f"{REDIS_BASE_URL}/{db}",
        )
    return _clients[db]


async def close_all():
    """应用关闭时统一释放所有Redis连接"""
    for client in _clients.values():
        await client.aclose()
    _clients.clear()
