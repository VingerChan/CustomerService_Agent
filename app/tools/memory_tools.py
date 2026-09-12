from langchain.tools import tool
from langchain_core.runnables import RunnableConfig
from app.memory.long_term import get_vector_memory

@tool
async def save_user_preference(preference_key: str, preference_value: str, config: RunnableConfig) -> str:
    """
    保存用户偏好到长期记忆。

    当用户在对话中明确表达个人偏好时使用此工具。
    例如：喜欢的品牌、偏好的颜色、预算范围、购物风格、常买的商品类别等。
    同一偏好键会自动更新（upsert），不会重复存储。

    Args:
        preference_key: 偏好键名，如 "favorite_category"(喜欢的商品类别),
            "preferred_brand"(偏好的品牌), "budget_range"(预算范围),
            "preferred_color"(喜欢的颜色), "shopping_style"(购物风格)
        preference_value: 偏好的具体值，如 "电子产品", "Nike", "500-1000元"
        config: RunnableConfig，包含用户信息
    """
    user_id = config.get('configurable', {}).get('thread_id')
    if not user_id:
        return "无法获取用户信息，偏好保存失败"
    try:
        vector_memory = get_vector_memory()
        await vector_memory.update_user_preference(
            user_id=user_id,
            preference_key=preference_key,
            preference_value=preference_value,
        )
        return f"已保存用户偏好：{preference_key} = {preference_value}"
    except Exception as e:
        return f"偏好保存失败：{str(e)}"