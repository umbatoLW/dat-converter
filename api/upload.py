#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
DAT转换API - 处理扣子平台的文件转换请求
部署在Vercel的无服务器函数
"""

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel
import requests
import zipfile
import io
import base64
import os
import uuid
from datetime import datetime, timedelta
import tempfile
from typing import List, Dict, Any, Optional
import json

# 创建FastAPI应用
app = FastAPI(title="DAT转换API", version="1.0.0")

# 从环境变量获取Supabase配置
SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "")
SUPABASE_BUCKET = "dat-conversions"  # Supabase存储桶名称

# 请求模型
class UploadRequest(BaseModel):
    zip_url: Optional[str] = None
    zip_base64: Optional[str] = None
    filename: Optional[str] = None
    stats: Optional[Dict[str, Any]] = None

class FileInfo(BaseModel):
    name: str
    content_base64: str
    file_type: str

@app.get("/")
async def root():
    """根端点，健康检查"""
    return {
        "service": "DAT转换API",
        "status": "running",
        "version": "1.0.0",
        "endpoints": {
            "test": "/test",
            "upload": "/upload (POST)",
            "download": "/download/{file_id} (GET)"
        }
    }

@app.get("/test")
async def test():
    """测试端点，检查环境变量"""
    return {
        "status": "running",
        "supabase_configured": bool(SUPABASE_URL and SUPABASE_KEY),
        "supabase_url_short": SUPABASE_URL[:20] + "..." if SUPABASE_URL else "未设置"
    }

def detect_image_format_and_key(dat_content: bytes) -> tuple:
    """
    检测DAT文件的图片格式和解密密钥
    返回: (格式, 密钥) 或 (None, None)
    """
    # 支持的图片格式及其文件头
    formats = [
        ('jpg', b'\xFF\xD8\xFF', 3),      # JPEG
        ('png', b'\x89PNG\r\n\x1a\n', 8), # PNG
        ('gif', b'GIF87a', 6),           # GIF
        ('gif', b'GIF89a', 6),           # GIF
        ('bmp', b'BM', 2),               # BMP
    ]
    
    for ext, header, header_len in formats:
        if len(dat_content) >= header_len:
            # 尝试找出正确的密钥
            test_key = dat_content[0] ^ header[0]
            decrypted = bytes([b ^ test_key for b in dat_content[:header_len]])
            if decrypted == header:
                return ext, test_key
    return None, None

def process_dat_conversion(zip_content: bytes) -> Dict[str, Any]:
    """
    处理ZIP文件中的DAT转换
    返回转换结果
    """
    try:
        # 创建临时目录
        with tempfile.TemporaryDirectory() as temp_dir:
            # 保存ZIP到临时文件
            zip_path = os.path.join(temp_dir, "input.zip")
            with open(zip_path, 'wb') as f:
                f.write(zip_content)
            
            # 处理ZIP文件
            converted_files = []
            total_files = 0
            converted_count = 0
            failed_count = 0
            
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                # 获取所有文件
                all_files = zip_ref.namelist()
                
                for file_path in all_files:
                    if file_path.lower().endswith('.dat'):
                        total_files += 1
                        try:
                            # 提取DAT文件
                            zip_ref.extract(file_path, temp_dir)
                            dat_file_path = os.path.join(temp_dir, file_path)
                            
                            # 读取DAT文件
                            with open(dat_file_path, 'rb') as f:
                                dat_content = f.read()
                            
                            # 检测格式和解密
                            image_format, key = detect_image_format_and_key(dat_content)
                            
                            if image_format and key is not None:
                                # 解密数据
                                decrypted_data = bytes([b ^ key for b in dat_content])
                                
                                # 验证解密后的数据
                                if image_format == 'jpg' and decrypted_data.startswith(b'\xFF\xD8\xFF'):
                                    # 准备文件信息
                                    file_name = os.path.splitext(os.path.basename(file_path))[0] + f".{image_format}"
                                    file_content_base64 = base64.b64encode(decrypted_data).decode('utf-8')
                                    
                                    converted_files.append({
                                        "name": file_name,
                                        "content_base64": file_content_base64,
                                        "file_type": image_format
                                    })
                                    converted_count += 1
                                else:
                                    failed_count += 1
                            else:
                                failed_count += 1
                            
                            # 清理临时文件
                            try:
                                os.remove(dat_file_path)
                            except:
                                pass
                                
                        except Exception as e:
                            failed_count += 1
                            print(f"处理文件 {file_path} 失败: {str(e)}")
            
            # 创建结果ZIP文件
            zip_buffer = io.BytesIO()
            with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zipf:
                for file_info in converted_files:
                    file_content = base64.b64decode(file_info["content_base64"])
                    zipf.writestr(file_info["name"], file_content)
            
            zip_buffer.seek(0)
            zip_data = zip_buffer.read()
            zip_base64 = base64.b64encode(zip_data).decode('utf-8')
            
            return {
                "success": True,
                "message": f"转换完成，共{total_files}个DAT文件，成功{converted_count}个，失败{failed_count}个",
                "zip_base64": zip_base64,
                "converted_count": converted_count,
                "failed_count": failed_count,
                "total_files": total_files
            }
            
    except Exception as e:
        return {
            "success": False,
            "message": f"处理失败: {str(e)}",
            "zip_base64": "",
            "converted_count": 0,
            "failed_count": 0,
            "total_files": 0
        }

def upload_to_supabase(zip_data: bytes, filename: str) -> Optional[str]:
    """
    上传ZIP文件到Supabase存储
    返回: 文件ID 或 None
    """
    try:
        if not SUPABASE_URL or not SUPABASE_KEY:
            print("Supabase配置未设置，跳过上传")
            return None
        
        # 生成唯一文件名
        file_id = str(uuid.uuid4())
        file_extension = os.path.splitext(filename)[1] or ".zip"
        supabase_filename = f"{file_id}{file_extension}"
        
        # 这里需要根据实际的Supabase SDK进行调整
        # 假设使用Supabase Python客户端
        from supabase import create_client, Client
        
        supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
        
        # 上传文件
        result = supabase.storage.from_(SUPABASE_BUCKET).upload(
            supabase_filename,
            zip_data,
            {"content-type": "application/zip"}
        )
        
        if result:
            return file_id
        else:
            return None
            
    except Exception as e:
        print(f"上传到Supabase失败: {e}")
        return None

@app.post("/upload")
async def upload_file(request: UploadRequest):
    """
    接收扣子平台的ZIP文件（URL或base64），转换DAT文件，返回下载链接
    """
    try:
        # 检查输入
        if not request.zip_url and not request.zip_base64:
            raise HTTPException(
                status_code=400,
                detail="请提供zip_url或zip_base64参数"
            )
        
        zip_content = None
        
        # 从URL获取ZIP文件
        if request.zip_url:
            try:
                response = requests.get(request.zip_url, timeout=30)
                response.raise_for_status()
                zip_content = response.content
            except Exception as e:
                raise HTTPException(
                    status_code=400,
                    detail=f"无法从URL下载ZIP文件: {str(e)}"
                )
        
        # 从base64获取ZIP文件
        elif request.zip_base64:
            try:
                zip_content = base64.b64decode(request.zip_base64)
            except Exception as e:
                raise HTTPException(
                    status_code=400,
                    detail=f"base64解码失败: {str(e)}"
                )
        
        if not zip_content or len(zip_content) == 0:
            raise HTTPException(
                status_code=400,
                detail="ZIP文件内容为空"
            )
        
        # 处理DAT转换
        conversion_result = process_dat_conversion(zip_content)
        
        if not conversion_result["success"]:
            return JSONResponse(
                status_code=400,
                content={
                    "success": False,
                    "message": conversion_result["message"],
                    "download_url": ""
                }
            )
        
        # 如果配置了Supabase，则上传
        file_id = None
        download_url = ""
        
        if SUPABASE_URL and SUPABASE_KEY:
            zip_data = base64.b64decode(conversion_result["zip_base64"])
            file_id = upload_to_supabase(zip_data, request.filename or f"converted_{datetime.now().strftime('%Y%m%d_%H%M%S')}.zip")
            
            if file_id:
                download_url = f"https://dat-converter.vercel.app/api/download/{file_id}"
        
        # 如果没有Supabase，或者上传失败，则直接返回base64
        if not download_url:
            download_url = f"data:application/zip;base64,{conversion_result['zip_base64'][:1000]}..."
            if len(conversion_result['zip_base64']) > 1000:
                download_url += f" (前1000字符，完整数据{len(conversion_result['zip_base64'])}字符)"
        
        return {
            "success": True,
            "message": conversion_result["message"],
            "file_id": file_id or "not_stored",
            "download_url": download_url,
            "direct_download": bool(file_id),  # 是否有直接的下载链接
            "converted_count": conversion_result["converted_count"],
            "failed_count": conversion_result["failed_count"],
            "total_files": conversion_result["total_files"],
            "zip_size": len(zip_content),
            "result_size": len(conversion_result["zip_base64"])
        }
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"处理请求时发生错误: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"服务器内部错误: {str(e)}"
        )

@app.get("/download/{file_id}")
async def download_file(file_id: str):
    """
    从Supabase下载文件
    """
    try:
        if not SUPABASE_URL or not SUPABASE_KEY:
            raise HTTPException(
                status_code=500,
                detail="文件存储服务未配置"
            )
        
        from supabase import create_client, Client
        supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
        
        # 尝试从Supabase获取文件
        try:
            # 这里需要根据实际的Supabase存储结构调整
            file_data = supabase.storage.from_(SUPABASE_BUCKET).download(f"{file_id}.zip")
            
            if not file_data:
                raise HTTPException(
                    status_code=404,
                    detail=f"文件 {file_id} 不存在"
                )
            
            return {
                "success": True,
                "file_id": file_id,
                "content_type": "application/zip",
                "content": base64.b64encode(file_data).decode('utf-8')
            }
            
        except Exception as e:
            raise HTTPException(
                status_code=404,
                detail=f"文件不存在或已过期: {str(e)}"
            )
            
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"下载文件时出错: {str(e)}"
        )

# 这是Vercel要求的导出格式
# 必须命名为'app'，Vercel会自动识别
app = app
