from dotenv import load_dotenv
import os
from langchain.chat_models import init_chat_model
from langchain.agents import create_agent
from langchain.agents.middleware import SummarizationMiddleware
from app.tools.rag_tools import map_user_intent
from app.tools.api_tools import get_orders

# 加载env
load_dotenv()

# 初始化大模型
llm1 = init_chat_model(
    model='qwen3.5-plus',
    model_provider='openai',
    api_key=os.getenv('DASHSCOPE_API_KEY'),
    base_url=os.getenv('DASHSCOPE_BASE_URL'),
)

llm2 = init_chat_model(
    model='qwen-max',
    model_provider='openai',
    api_key=os.getenv('DASHSCOPE_API_KEY'),
    base_url=os.getenv('DASHSCOPE_BASE_URL'),
)

# 初始化中间件
middleware = SummarizationMiddleware(
    model=llm2,
    trigger=('messages', 10),    # 触发时机，当消息总数超过10时，进行总结
    keep=('messages', 1),    # 保留的会话数
)

system_prompt = """
你是一个智能客服助手。请按照以下规则处理用户请求：
## 核心工作流程
1.意图识别：当用户提出请求时，首先调用map_user_intent工具了解可用的API端点
2.API选择：查看返回的API列表和匹配度(score)：
    - 如果最高匹配度 >= 0.5，选择最匹配的API
    - 如果最高匹配度 < 0.5，说明用户请求与平台功能不匹配，直接回复"抱歉，我无法处理这个请求"
3.根据API选择最适用的工具
4、将工具返回的结果整理后回复用户
## 注意事项
- 根据API描述和用户query，判断匹配度是否合理
- 如果用户请求不明确，先调用map_user_intent获取候选API再判断
"""

agent = None
tools = [map_user_intent, get_orders]
def init_agent(checkpointer):
    global agent
    agent = create_agent(
        llm1,
        tools=tools,
        checkpointer=checkpointer,
        middleware=[middleware],
        system_prompt=system_prompt,
    )

def get_agent():
    return agent
