from dotenv import load_dotenv
import os
from langchain.chat_models import init_chat_model
from langchain.agents import create_agent

# 加载env
load_dotenv()

# 初始化大模型
llm = init_chat_model(
    model='qwen3.5-plus',
    model_provider='openai',
    api_key=os.getenv('DASHSCOPE_API_KEY'),
    base_url=os.getenv('DASHSCOPE_BASE_URL'),
)

agent = create_agent(
    model=llm,  # 模型
    tools=[],
)
