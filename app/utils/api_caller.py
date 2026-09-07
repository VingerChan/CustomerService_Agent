import os
from dotenv import load_dotenv
import httpx
import asyncio

load_dotenv()
BASE_URL = os.getenv("BASE_URL")

async def call_api(endpoint: str, token: str, method: str = 'GET', params: dict = None, max_retries: int = 3) -> dict:
    """
    通用API调用工具
    :param endpoint: API端点路径
    :param token: 用户认证token
    :param method: HTTP方法，默认GET
    :param params: 查询参数(可选)
    :param max_retries: 最大重试次数
    :return: API返回的JSON结果
    :raises: ValueError, httpx.HTTPStatusError, Exception
    """
    # 参数验证
    if not endpoint.startswith('/'):
        raise ValueError(f"endpoint必须以'/'开头：{endpoint}")
    url = f"{BASE_URL}{endpoint}"
    headers = {'Authorization': f"Bearer {token}"}
    # 重试机制
    last_exception = None
    for attempt in range(max_retries):
        try:
            async with httpx.AsyncClient() as client:
                if method.upper() == 'GET':
                    response = await client.get(url, headers=headers, params=params)
                elif method.upper() == 'POST':
                    response = await client.post(url, headers=headers, params=params)
                else:
                    raise ValueError(f"不支持的HTTP方法：{method}")
                response.raise_for_status()    # HTTP状态码非2xx时抛出异常
                return response.json()
        except httpx.HTTPStatusError as e:
            last_exception = e
            if e.response.status_code < 500:    # 客户端错误不重试
                raise
            if attempt < max_retries - 1:
                # 指数退避等待，第1次等1秒，第2次等2秒，避免频繁重试
                await asyncio.sleep(2 ** attempt)
        except httpx.RequestError as e:
            last_exception = e
            if attempt < max_retries - 1:
                await asyncio.sleep(2 ** attempt)
        except Exception as e:
            raise
    raise last_exception    # 所有重试都失败，抛出最后一个异常
