from langchain.tools import tool
from app.core.intent import get_intent_mapper
from app.rag.knowledge_base import get_knowledge_base

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


@tool
async def search_knowledge_base(query: str) -> str:
    """
    搜索知识库(FAQ和平台政策)

    当用户询问关于平台政策、使用规则、退换货政策、配送规则、账户注册、支付方式、售后服务等问题时，使用此工具获取准确信息。

    Args:
        query: 用户的问题或搜索关键词
    """
    knowledge_base = get_knowledge_base()
    results = await knowledge_base.get_formatted_results(query, n_results=3)
    return results