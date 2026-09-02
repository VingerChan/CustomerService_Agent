import httpx
import os
from dotenv import load_dotenv

load_dotenv()

async def get_user_info(token: str) -> dict:
    """
    通过token调用平台API获取用户信息
    :param token: 用户认证token
    :return:  用户信息
    """
    user_api = os.getenv('USER_API')
    headers = {'Authorization': f'Bearer {token}'}
    async with httpx.AsyncClient() as client:    # token无效或过期，会抛出异常
        response = await client.get(user_api, headers=headers)
        response.raise_for_status()
        return response.json()