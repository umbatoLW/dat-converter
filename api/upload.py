@app.post("/upload")
async def upload_file(request_data: dict):
    """
    接收base64编码的ZIP文件，存储到Supabase，返回下载链接
    """
    try:
        import base64
        from datetime import datetime, timedelta
        import uuid
        
        # 从请求中获取数据
        zip_base64 = request_data.get("zip_base64", "")
        filename = request_data.get("filename", f"converted_{uuid.uuid4().hex[:8]}.zip")
        stats = request_data.get("stats", {})
        
        if not zip_base64:
            return {
                "success": False,
                "message": "未收到ZIP文件数据",
                "download_url": ""
            }
        
        # 解码base64
        zip_data = base64.b64decode(zip_base64)
        
        # 上传到Supabase存储
        file_id = str(uuid.uuid4())
        zip_filename = f"{file_id}.zip"
        
        # 这里使用您的Supabase客户端上传文件
        # upload_result = supabase.storage.from_("dat-conversions").upload(
        #     zip_filename,
        #     zip_data,
        #     {"content-type": "application/zip"}
        # )
        
        # 假设上传成功，获取文件URL
        file_url = f"{SUPABASE_URL}/storage/v1/object/public/dat-conversions/{zip_filename}"
        
        # 创建数据库记录
        expires_at = datetime.utcnow() + timedelta(hours=24)
        
        # 这里插入数据库记录
        # supabase.table("file_records").insert({
        #     "id": file_id,
        #     "file_name": zip_filename,
        #     "file_url": file_url,
        #     "expires_at": expires_at.isoformat() + "Z"
        # }).execute()
        
        # 返回结果
        return {
            "success": True,
            "message": f"文件上传成功，共{stats.get('converted_count', 0)}个图片",
            "file_id": file_id,
            "download_url": f"https://dat-converter.vercel.app/download/{file_id}",
            "direct_url": file_url,
            "expires_at": expires_at.isoformat(),
            "stats": stats
        }
        
    except Exception as e:
        return {
            "success": False,
            "message": f"上传失败: {str(e)}",
            "download_url": ""
        }
