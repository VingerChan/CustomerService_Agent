from langchain.tools import tool
from app.core.intent import get_intent_mapper

@tool
async def map_user_intent(query: str) -> str:
    """
    将用户的自然语言意图映射到对应的API端点。

    当需要理解用户想要执行什么操作时使用此工具。
    返回匹配的API端点列表，包含端点地址、HTTP方法和匹配得分。
    如果最高匹配度低于0.5，说明用户请求于平台API不匹配

    Args:
        query: 用户的自然语言意图描述
    """
    intent_mapper = get_intent_mapper()
    try:
        endpoints = await intent_mapper.get_api_endpoints(query, n_results=3)
        if endpoints:
            api_list = []
            for endpoint in endpoints:
                api_list.append(
                    f"- {endpoint['id']}: {endpoint['method']} {endpoint['endpoint']} "
                    f"(匹配度: {endpoint['score']:.2f})\n  描述: {endpoint['description']}"
                )
            return "匹配到以下API端点：\n" + "\n".join(api_list)
        return "未匹配到相关API端点"
    except Exception as e:
        return f"意图映射失败：{str(e)}"