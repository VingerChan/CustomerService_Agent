from contextlib import asynccontextmanager
from fastapi import FastAPI
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from app.routers.chat import router as chat_router
import os
from dotenv import load_dotenv
load_dotenv()
from app.core.agent import init_agent

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
        FastAPI应用生命周期管理
        启动时：初始化Agent
        关闭时：清理资源
    """
    async with AsyncPostgresSaver.from_conn_string(conn_string=os.getenv('POSTGRESSQL_URL')) as checkpointer:
        await checkpointer.setup()
        init_agent(checkpointer)
        yield    # 应用开始接收请求
app = FastAPI(lifespan=lifespan)

# 注册路由
app.include_router(chat_router)

@app.get("/")
async def root():
    return {"message": "智能客服Agent运行中"}