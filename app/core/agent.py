from dotenv import load_dotenv
import os
from langchain.chat_models import init_chat_model
from langchain.agents import create_agent
from langchain.agents.middleware import SummarizationMiddleware

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

agent = None

def init_agent(checkpointer):
    global agent
    agent = create_agent(
        llm1,
        tools=[],
        checkpointer=checkpointer,
        middleware=[middleware],
    )

def get_agent():
    return agent
