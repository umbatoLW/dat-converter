from fastapi import FastAPI, File, UploadFile, HTTPException
from typing import Dict, Any
import json
import os

# FastAPI应用实例
app = FastAPI()

# 获取环境变量
SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "")

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

# 必须导出app实例
# 重要：这行必须存在，Vercel才能识别为无服务器函数
app = app