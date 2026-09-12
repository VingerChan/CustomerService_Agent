from contextlib import asynccontextmanager
from fastapi import FastAPI
from langgraph.checkpoint.redis.aio import AsyncRedisSaver
from app.routers.chat import router as chat_router
import os
from dotenv import load_dotenv
load_dotenv()
from app.agents.agent import init_agent
from app.core.intent import get_intent_mapper
import json
from app.utils.summary import SummaryGenerator
from app.memory.long_term import get_vector_memory
from app.routers.transfer import router as transfer_router

# 全局checkpointer实例，供chat.py使用
_checkpointer = None

def get_checkpointer():
    """
    获取全局checkpointer实例
    :return:
    """
    return _checkpointer

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
        FastAPI应用生命周期管理
        启动时：初始化Agent、加载API文档
        关闭时：清理资源
    """
    global _checkpointer
    # Redis Checkpointer配置(短期记忆)
    ttl_config = {
        'default_ttl': 1440,    # 24小时(分钟)
        'refresh_on_read': True,    # 读取时刷新
    }
    async with AsyncRedisSaver.from_conn_string(os.getenv('REDIS_URL'), ttl=ttl_config) as checkpointer:
        await checkpointer.asetup()
        _checkpointer = checkpointer
        # 初始化VectorMemory和SummaryGenerator(长期记忆)
        vector_memory = get_vector_memory()
        summary_generator = SummaryGenerator(vector_memory=vector_memory, api_key=os.getenv('DASHSCOPE_API_KEY'), base_url=os.getenv('DASHSCOPE_BASE_URL'))

        init_agent(checkpointer, summary_generator=summary_generator, summary_rounds=3)
        # 加载API文档到向量数据库
        intent_mapper = get_intent_mapper()
        with open('data/api_docs.json','r',encoding='utf-8') as f:
            api_docs = json.load(f)
        count = await intent_mapper.load_api_docs(api_docs)
        print(f"已加载 {count} 条API文档到向量数据库")
        yield    # 应用开始接收请求
app = FastAPI(lifespan=lifespan)

# 注册路由
app.include_router(chat_router)
app.include_router(transfer_router)

@app.get("/")
async def root():
    return {"message": "智能客服Agent运行中"}