@app.post("/upload")
async def upload_file(request_data: dict):
    """
    接收扣子平台传来的ZIP URL，下载、转换并返回结果
    """
    try:
        import requests
        import zipfile
        import io
        import base64
        from datetime import datetime
        
        # 获取参数
        zip_url = request_data.get("zip_url")
        filename = request_data.get("filename", f"converted_{datetime.now().strftime('%Y%m%d_%H%M%S')}.zip")
        
        if not zip_url:
            return {
                "success": False,
                "message": "未收到ZIP文件URL",
                "download_url": ""
            }
        
        # 1. 从扣子平台下载ZIP文件
        response = requests.get(zip_url, stream=True)
        if response.status_code != 200:
            return {
                "success": False,
                "message": f"下载ZIP文件失败: {response.status_code}",
                "download_url": ""
            }
        
        # 2. 处理DAT文件转换
        conversion_result = process_dat_conversion(response.content)
        
        if not conversion_result["success"]:
            return {
                "success": False,
                "message": conversion_result["message"],
                "download_url": ""
            }
        
        # 3. 上传到Supabase存储
        file_id = upload_to_supabase(
            conversion_result["zip_data"],
            filename
        )
        
        if not file_id:
            return {
                "success": False,
                "message": "文件上传失败",
                "download_url": ""
            }
        
        # 4. 返回下载链接
        download_url = f"https://dat-converter.vercel.app/download/{file_id}"
        
        return {
            "success": True,
            "message": conversion_result["message"],
            "download_url": download_url,
            "file_id": file_id,
            "converted_count": conversion_result["converted_count"],
            "failed_count": conversion_result["failed_count"]
        }
        
    except Exception as e:
        return {
            "success": False,
            "message": f"处理失败: {str(e)}",
            "download_url": ""
        }
