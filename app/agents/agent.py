from dotenv import load_dotenv
import os
from langchain.chat_models import init_chat_model
from langchain.agents import create_agent
from app.tools.rag_tools import map_user_intent, search_knowledge_base
from app.tools.api_tools import get_orders, get_browse_history, search_products, get_order_detail, get_product_detail
from app.tools.memory_tools import save_user_preference
from app.tools.transfer_tools import transfer_to_human, check_transfer_status, send_transfer_message
from langchain_core.messages import SystemMessage, HumanMessage
from langchain.agents.middleware import wrap_model_call, ModelRequest, ModelResponse, AgentMiddleware
from typing import Callable, Awaitable
from app.utils.summary import SummaryGenerator
from langgraph.config import get_config
import asyncio
import logging

logger = logging.getLogger(__name__)

# 加载env
load_dotenv()

# 初始化大模型
llm1 = init_chat_model(
    model=os.getenv('LLM_MODEL'),
    model_provider='openai',
    api_key=os.getenv('DASHSCOPE_API_KEY'),
    base_url=os.getenv('DASHSCOPE_BASE_URL'),
)

"""短期记忆MiddleWare"""
def trim_by_rounds(messages: list, max_rounds: int =3, include_system: bool = True) -> list:
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
    trimmed = trim_by_rounds(messages, max_rounds=3)
    # 如果裁剪了消息，则创建新的request对象
    if len(trimmed) < len(messages):
        # request.override()创建修改后的副本，不修改原对象
        request = request.override(messages=trimmed)
    return await handler(request)

"""长期记忆middleware"""
class LongTermMemoryMiddleware(AgentMiddleware):
    """
    长期记忆Middleware
    在模型调用后检测轮次，每N轮触发摘要生成并保存到ChromaDB
    """
    def __init__(self, summary_generator: SummaryGenerator, summary_rounds: int =3):
        super().__init__()
        self.summary_generator = summary_generator
        self.summary_rounds = summary_rounds
        # 记录每个用户上次摘要时的轮次数，避免重复摘要
        self._last_summary_rounds: dict[str, int] = {}
    async def awrap_model_call(self,request: 'ModelRequest', handler: Callable[['ModelRequest'], Awaitable['ModelResponse']]) -> 'ModelResponse':
        # 调用handler生成回复(正常流程，不干预)
        response = await handler(request)
        # 从config获取user_id
        try:
            config = get_config()
            user_id = config.get('configurable', {}).get('thread_id')
        except Exception as e:
            user_id = None
        if not user_id:
            return response
        # 统计当前轮次(HumanMessage数量)
        human_count = sum(1 for msg in request.state['messages'] if isinstance(msg, HumanMessage))
        # 检查是否需要生成摘要
        last_round = self._last_summary_rounds.get(user_id, 0)
        rounds_since_last = human_count - last_round
        # 后台异步生成摘要
        if rounds_since_last >= self.summary_rounds:
            state_messages = list(request.state['messages'])
            if hasattr(response, 'result') and response.result:
                state_messages.extend(response.result)
            messages_snapshot = state_messages
            asyncio.create_task(self._generate_summary_safe(user_id, messages_snapshot))
            self._last_summary_rounds[user_id] = human_count
        return response

    async def _generate_summary_safe(self, user_id: str, messages: list):
        """
        安全地摘要生成
        :param user_id: 用户id
        :param messages: 消息列表
        :return: None
        """
        try:
            await self.summary_generator.generate_and_save(
                user_id=user_id,
                messages=messages,
                n_rounds=self.summary_rounds,
            )
        except Exception as e:
            logger.error(f"[LongTermMemory] 摘要生成异常: {e}", exc_info=True)

system_prompt = """
你是一个智能客服助手。请按照以下规则处理用户请求：

## 核心工作流程
1. 首先调用map_user_intent工具获取候选API
2. 根据返回的匹配度(score)判断：
   - 最高匹配度 >= 0.5：选择最匹配的API，调用对应工具
   - 最高匹配度 < 0.5：回复"抱歉，我无法处理这个请求"
3. 将工具返回的结果整理后回复用户

## 注意事项
- 如果用户请求不明确，先调用map_user_intent获取候选API再判断
- 回复时只处理用户的当前请求，不要混入无关内容
- 如果用户明确要求继续之前的对话（如"继续刚才的推荐"），则可以使用上下文

## 转人工客服
- 转人工时，将当前AI聊天历史作为参数传递，帮助人工客服了解上下文
- 当用户结束转人工会话后，必须完全忽略对话历史中任何关于转人工、人工客服、会话ID、排队等待的内容。不要在回复中提及这些信息的任何片段。像从未发生过转人工一样，正常处理用户的新请求。
"""

agent = None
tools = [map_user_intent, get_orders, get_browse_history, search_products, get_order_detail, get_product_detail, save_user_preference, transfer_to_human, check_transfer_status, send_transfer_message, search_knowledge_base]
def init_agent(checkpointer, summary_generator = None, summary_rounds: int = 3):
    global agent
    middleware_list = [trim_message_middleware]
    if summary_generator is not None:
        long_term_middleware = LongTermMemoryMiddleware(summary_generator, summary_rounds)
        middleware_list.append(long_term_middleware)
    agent = create_agent(
        llm1,
        tools=tools,
        checkpointer=checkpointer,
        middleware=middleware_list,
        system_prompt=system_prompt,
    )

def get_agent():
    return agent
