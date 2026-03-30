from fastapi import FastAPI, HTTPException
import os
import json

app = FastAPI()

# 获取环境变量
SUPABASE_URL = os.getenv("SUPABASE_URL", "您的Supabase项目URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "您的Supabase匿名密钥")

@app.get("/")
async def root():
    return {"message": "DAT转换API服务运行中"}

@app.get("/test")
async def test():
    return {
        "status": "running",
        "supabase_url": SUPABASE_URL[:20] + "..." if SUPABASE_URL else "未设置"
    }

@app.post("/upload")
async def upload_file():
    return {
        "success": True,
        "message": "API工作正常",
        "file_id": "test-123",
        "download_url": "https://example.com/test"
    }