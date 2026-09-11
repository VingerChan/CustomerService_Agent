from dotenv import load_dotenv
import os
from langchain.chat_models import init_chat_model
from langchain.agents import create_agent
from app.tools.rag_tools import map_user_intent
from app.tools.api_tools import get_orders, get_browse_history, search_products, get_order_detail, get_product_detail
from langchain_core.messages import SystemMessage, HumanMessage
from langchain.agents.middleware import wrap_model_call, ModelRequest, ModelResponse
from typing import Callable, Awaitable

# 加载env
load_dotenv()

# 初始化大模型
llm1 = init_chat_model(
    model='qwen3.5-plus',
    model_provider='openai',
    api_key=os.getenv('DASHSCOPE_API_KEY'),
    base_url=os.getenv('DASHSCOPE_BASE_URL'),
)

def trim_by_rounds(messages: list, max_rounds: int =4, include_system: bool = True) -> list:
    """
    按轮次裁剪对话历史，保留最近4轮对话
    :param messages: 消息列表
    :param max_rounds: 保留的最大轮次数
    :param include_system: 是否保留SystemMessage
    :return: 裁剪后的消息列表
    """
    system_msgs = []
    conversation_msg = []
    # 将系统消息SystemMessage 和 对话消息(HumanMessage、AIMessage)分开处理
    for msg in messages:
        if include_system and isinstance(msg, SystemMessage):
            system_msgs.append(msg)
        else:
            conversation_msg.append(msg)
    # 系统消息作为Prompt不算一轮对话
    # 以HumanMessage作为每轮对话的起点，计算索引
    round_starts = [i for i, msg in enumerate(conversation_msg) if isinstance(msg, HumanMessage)]
    # 轮次未超限，返回原消息列表
    if len(round_starts) <= max_rounds:
        return messages
    trimmed_conversation = conversation_msg[round_starts[-max_rounds]:]
    return system_msgs + trimmed_conversation

@wrap_model_call
async def trim_message_middleware(request: ModelRequest, handler: Callable[[ModelRequest], Awaitable[ModelResponse]]):
    messages = request.messages
    trimmed = trim_by_rounds(messages, max_rounds=2)
    # 如果裁剪了消息，则创建新的request对象
    if len(trimmed) < len(messages):
        # request.override()创建修改后的副本，不修改原对象
        request = request.override(messages=trimmed)
    return await handler(request)

system_prompt = """
你是一个智能客服助手。请按照以下规则处理用户请求：
## 核心工作流程
1.意图识别：当用户提出请求时，首先调用map_user_intent工具了解可用的API端点
2.API选择：查看返回的API列表和匹配度(score)：
    - 如果最高匹配度 >= 0.5，选择最匹配的API
    - 如果最高匹配度 < 0.5，说明用户请求与平台功能不匹配，直接回复"抱歉，我无法处理这个请求"
3.工具选择：根据选择的API，调用对应的业务工具
    - 订单列表：get_orders(获取订单历史，用于分析用户偏好)
    - 浏览记录：get_browse_history(获取浏览历史，用于分析用户偏好)
    - 商品搜索：search_products(支持关键词搜索、价格区间、排序)
    - 订单详情：get_order_detail(查询单个订单的详细信息，如物流状态、支付方式、收货地址)
    - 商品详情：get_product_detail(查询单个商品的详细信息，如规格参数、库存、价格) 
4、将工具返回的结果整理后回复用户
## 注意事项
- 根据API描述和用户query，判断匹配度是否合理
- 如果用户请求不明确，先调用map_user_intent获取候选API再判断
- 回复时只处理用户的当前请求，不要在回复中混入与当前请求无关的其他话题内容 
- 如果用户明确要求继续之前的对话（如"继续刚才的推荐"），则可以使用上下文
"""

agent = None
tools = [map_user_intent, get_orders, get_browse_history, search_products, get_order_detail, get_product_detail]
def init_agent(checkpointer):
    global agent
    agent = create_agent(
        llm1,
        tools=tools,
        checkpointer=checkpointer,
        middleware=[trim_message_middleware],
        system_prompt=system_prompt,
    )

def get_agent():
    return agent
