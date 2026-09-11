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

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
        FastAPI应用生命周期管理
        启动时：初始化Agent、加载API文档
        关闭时：清理资源
    """
    # Redis Checkpointer配置(短期记忆)
    ttl_config = {
        'default_ttl': 1440,    # 24小时(分钟)
        'refresh_on_read': True,    # 读取时刷新
    }
    async with AsyncRedisSaver.from_conn_string(os.getenv('REDIS_URL'), ttl=ttl_config) as checkpointer:
        await checkpointer.asetup()
        init_agent(checkpointer)
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

@app.get("/")
async def root():
    return {"message": "智能客服Agent运行中"}