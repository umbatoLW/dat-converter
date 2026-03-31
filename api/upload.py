from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, Dict, Any
import requests
import zipfile
import tempfile
import os
import io
import base64
import json
import time

# 创建FastAPI应用
app = FastAPI(title="DAT转换API")

# 添加CORS中间件
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 请求模型
class UploadRequest(BaseModel):
    zip_url: str
    filename: Optional[str] = "converted_images.zip"

# 响应模型
class UploadResponse(BaseModel):
    success: bool
    message: str
    download_url: Optional[str] = None
    file_id: Optional[str] = None
    stats: Optional[Dict[str, Any]] = None

def detect_image_format_and_key(dat_content: bytes):
    """检测图片格式和密钥"""
    if len(dat_content) < 8:
        return None, None
    
    formats = [
        ('jpg', b'\xFF\xD8\xFF', 3),
        ('png', b'\x89PNG\r\n\x1a\n', 8),
        ('gif', b'GIF87a', 6),
        ('gif', b'GIF89a', 6),
        ('bmp', b'BM', 2),
    ]
    
    for ext, header, header_len in formats:
        if len(dat_content) >= header_len:
            key = dat_content[0] ^ header[0]
            decrypted = bytes([b ^ key for b in dat_content[:header_len]])
            if decrypted == header:
                return ext, key
    
    return None, None

def decrypt_dat_file(data: bytes, key: int) -> bytes:
    """解密DAT文件"""
    return bytes([b ^ key for b in data])

def process_zip_file(zip_content: bytes) -> Dict[str, Any]:
    """处理ZIP文件中的DAT转换"""
    try:
        with tempfile.TemporaryDirectory() as temp_dir:
            # 保存ZIP文件
            zip_path = os.path.join(temp_dir, "input.zip")
            with open(zip_path, 'wb') as f:
                f.write(zip_content)
            
            # 打开ZIP文件
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                all_files = zip_ref.namelist()
                
                # 统计信息
                stats = {
                    "total_files": len(all_files),
                    "dat_files": 0,
                    "converted": 0,
                    "failed": 0,
                    "failed_files": []
                }
                
                # 创建输出目录
                output_dir = os.path.join(temp_dir, "output")
                os.makedirs(output_dir, exist_ok=True)
                
                # 处理每个文件
                for file_path in all_files:
                    if file_path.lower().endswith('.dat'):
                        stats["dat_files"] += 1
                        
                        try:
                            # 提取DAT文件
                            zip_ref.extract(file_path, temp_dir)
                            dat_path = os.path.join(temp_dir, file_path)
                            
                            # 读取DAT文件
                            with open(dat_path, 'rb') as f:
                                dat_content = f.read()
                            
                            # 检测格式和密钥
                            image_format, key = detect_image_format_and_key(dat_content)
                            
                            if image_format and key is not None:
                                # 解密数据
                                decrypted_data = decrypt_dat_file(dat_content, key)
                                
                                # 验证是否是JPG
                                if image_format == 'jpg' and decrypted_data.startswith(b'\xFF\xD8\xFF'):
                                    # 生成输出文件名
                                    base_name = os.path.basename(file_path)
                                    name_without_ext = os.path.splitext(base_name)[0]
                                    output_file = f"{name_without_ext}.jpg"
                                    output_path = os.path.join(output_dir, output_file)
                                    
                                    # 保存文件
                                    with open(output_path, 'wb') as f:
                                        f.write(decrypted_data)
                                    
                                    stats["converted"] += 1
                                else:
                                    stats["failed"] += 1
                                    stats["failed_files"].append(file_path)
                            else:
                                stats["failed"] += 1
                                stats["failed_files"].append(file_path)
                            
                            # 清理临时文件
                            try:
                                os.remove(dat_path)
                            except:
                                pass
                                
                        except Exception as e:
                            stats["failed"] += 1
                            stats["failed_files"].append(file_path)
                
                # 如果转换成功，创建输出ZIP
                if stats["converted"] > 0:
                    # 获取所有输出文件
                    output_files = []
                    for root, dirs, files in os.walk(output_dir):
                        for file in files:
                            if file.lower().endswith('.jpg'):
                                output_files.append(os.path.join(root, file))
                    
                    if output_files:
                        # 创建ZIP文件
                        zip_buffer = io.BytesIO()
                        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zipf:
                            for file_path in output_files:
                                zipf.write(file_path, os.path.basename(file_path))
                        
                        zip_buffer.seek(0)
                        zip_data = zip_buffer.getvalue()
                        zip_base64 = base64.b64encode(zip_data).decode('utf-8')
                        
                        return {
                            "success": True,
                            "message": f"转换完成: 共{stats['dat_files']}个DAT文件，成功{stats['converted']}个，失败{stats['failed']}个",
                            "zip_base64": zip_base64,
                            "stats": stats
                        }
                
                return {
                    "success": False,
                    "message": f"没有成功转换任何文件。找到{stats['dat_files']}个DAT文件，全部转换失败。",
                    "zip_base64": None,
                    "stats": stats
                }
                
    except Exception as e:
        return {
            "success": False,
            "message": f"处理ZIP文件时出错: {str(e)}",
            "zip_base64": None,
            "stats": None
        }

@app.get("/")
async def root():
    return {"message": "DAT转换API服务运行中", "status": "ok"}

@app.get("/health")
async def health_check():
    return {"status": "healthy", "timestamp": time.time()}

@app.post("/upload")
async def upload_file(request: UploadRequest):
    """
    接收ZIP文件的URL，处理并返回转换结果
    """
    try:
        # 1. 验证输入
        if not request.zip_url:
            raise HTTPException(status_code=400, detail="缺少zip_url参数")
        
        if not request.zip_url.startswith(('http://', 'https://')):
            raise HTTPException(status_code=400, detail="zip_url必须是有效的HTTP/HTTPS链接")
        
        # 2. 下载ZIP文件
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }
            response = requests.get(request.zip_url, headers=headers, timeout=30)
            response.raise_for_status()
            zip_content = response.content
            
            if len(zip_content) == 0:
                raise HTTPException(status_code=400, detail="下载的ZIP文件为空")
                
        except requests.exceptions.RequestException as e:
            raise HTTPException(status_code=400, detail=f"下载ZIP文件失败: {str(e)}")
        
        # 3. 处理DAT转换
        result = process_zip_file(zip_content)
        
        if not result["success"]:
            return UploadResponse(
                success=False,
                message=result["message"],
                stats=result["stats"]
            )
        
        # 4. 返回base64编码的ZIP文件
        # 注意：这里我们直接返回base64，实际使用中可以考虑上传到云存储
        zip_base64 = result["zip_base64"]
        file_id = f"converted_{int(time.time())}_{hash(zip_base64[:100])}"
        
        # 生成data URL，可以直接在浏览器中下载
        download_url = f"data:application/zip;base64,{zip_base64}"
        
        return UploadResponse(
            success=True,
            message=result["message"],
            download_url=download_url,
            file_id=file_id,
            stats=result["stats"]
        )
        
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"服务器内部错误: {str(e)}")

# Vercel需要这个导出
app = app
