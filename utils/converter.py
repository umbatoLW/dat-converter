#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
DAT文件转换工具函数
"""

import struct
from typing import Tuple, Optional, Dict, Any
import io

def detect_image_format_and_key(dat_content: bytes) -> Tuple[Optional[str], Optional[int]]:
    """
    检测DAT文件的图片格式和解密密钥
    """
    formats = [
        ('jpg', b'\xFF\xD8\xFF', 3),
        ('png', b'\x89PNG\r\n\x1a\n', 8),
        ('gif', b'GIF87a', 6),
        ('gif', b'GIF89a', 6),
        ('bmp', b'BM', 2),
    ]
    
    for ext, header, header_len in formats:
        if len(dat_content) >= header_len:
            test_key = dat_content[0] ^ header[0]
            decrypted = bytes([b ^ test_key for b in dat_content[:header_len]])
            if decrypted == header:
                return ext, test_key
    return None, None

def decrypt_dat_file(dat_content: bytes, key: int) -> bytes:
    """
    解密DAT文件
    """
    return bytes([b ^ key for b in dat_content])

def is_valid_image(data: bytes, format_type: str) -> bool:
    """
    验证解密后的数据是否是有效的图片
    """
    if format_type == 'jpg':
        return data.startswith(b'\xFF\xD8\xFF')
    elif format_type == 'png':
        return data.startswith(b'\x89PNG\r\n\x1a\n')
    elif format_type == 'gif':
        return data.startswith(b'GIF87a') or data.startswith(b'GIF89a')
    elif format_type == 'bmp':
        return data.startswith(b'BM')
    return False