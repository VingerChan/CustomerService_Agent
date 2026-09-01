from fastapi import FastAPI
from app.routers.chat import router as chat_router
app = FastAPI()

# 注册路由
app.include_router(chat_router)

@app.get("/")
async def root():
    return {"message": "智能客服Agent运行中"}