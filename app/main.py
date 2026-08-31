from fastapi import FastAPI

app = FastAPI()

@app.get("/")
async def root():
    return {"message": "智能客服Agent运行中"}