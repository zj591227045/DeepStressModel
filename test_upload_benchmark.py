#!/usr/bin/env python3
"""
测试脚本：上传加密的基准测试结果到服务器

用法：
python test_upload_benchmark.py <加密文件路径> <API密钥>
"""

import os
import sys
import json
import requests
from datetime import datetime

# 配置日志
import logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger("test_upload")

def upload_benchmark_result(file_path, api_key, server_url="http://localhost:8083/api/v1/benchmark-result/upload"):
    """
    上传加密的基准测试结果到服务器
    
    Args:
        file_path: 加密文件路径
        api_key: API密钥
        server_url: 服务器URL
        
    Returns:
        dict: 服务器响应
    """
    try:
        if not os.path.exists(file_path):
            logger.error(f"文件不存在: {file_path}")
            return {"status": "error", "message": f"文件不存在: {file_path}"}
        
        # 准备元数据 - 作为JSON字符串
        metadata = {
            "submitter": "测试脚本",
            "model_name": "测试模型",
            "model_version": "1.0",
            "notes": "测试上传",
            "timestamp": datetime.now().isoformat()
        }
        
        # 将元数据转换为JSON字符串
        metadata_json = json.dumps(metadata, ensure_ascii=False)
        
        # 准备请求数据
        data = {
            "metadata": metadata_json  # 元数据作为JSON字符串
        }
        
        # 可选: 添加API密钥到请求头
        headers = {}
        if api_key:
            headers["X-API-Key"] = api_key
        
        # 准备文件
        files = {
            "file": open(file_path, "rb")
        }
        
        # 发送请求
        logger.info(f"正在上传文件: {file_path}")
        logger.info(f"目标URL: {server_url}")
        logger.info(f"元数据: {metadata}")
        
        response = requests.post(
            server_url, 
            data=data, 
            files=files, 
            headers=headers
        )
        
        # 关闭文件
        files["file"].close()
        
        # 检查响应
        if response.status_code == 200:
            try:
                result = response.json()
                logger.info(f"上传成功: {result}")
                return result
            except json.JSONDecodeError:
                logger.error(f"服务器返回的不是JSON格式: {response.text[:100]}")
                return {"status": "error", "message": f"服务器返回的不是JSON格式: {response.text[:100]}"}
        else:
            logger.error(f"服务器返回错误状态码: {response.status_code}, 响应: {response.text}")
            return {"status": "error", "message": f"服务器返回错误状态码: {response.status_code}, 响应: {response.text}"}
            
    except Exception as e:
        logger.error(f"上传文件出错: {str(e)}")
        return {"status": "error", "message": str(e)}

def main():
    """主函数"""
    if len(sys.argv) < 2:
        print(f"用法: {sys.argv[0]} <加密文件路径> [API密钥]")
        return 1
    
    file_path = sys.argv[1]
    api_key = sys.argv[2] if len(sys.argv) > 2 else None
    
    # 配置服务器URL
    server_url = os.environ.get(
        "BENCHMARK_SERVER_URL", 
        "http://localhost:8083/api/v1/benchmark-result/upload"
    )
    
    result = upload_benchmark_result(file_path, api_key, server_url)
    
    if result.get("status") == "success":
        print(f"上传成功, ID: {result.get('id', 'unknown')}")
        return 0
    else:
        print(f"上传失败: {result.get('message', '未知错误')}")
        return 1

if __name__ == "__main__":
    sys.exit(main()) 