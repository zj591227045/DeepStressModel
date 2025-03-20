#!/usr/bin/env python3
"""
测试脚本：加密和上传基准测试结果

用法：
python test_encrypt_and_upload.py <测试结果JSON文件> <API密钥>
"""

import os
import sys
import json
import time
from datetime import datetime

# 导入必要模块
try:
    from src.benchmark.crypto.benchmark_log_encrypt import BenchmarkEncryption
    from src.utils.logger import setup_logger
except ImportError:
    # 如果无法导入，需要设置PYTHONPATH
    print("错误: 无法导入必要模块。请确保PYTHONPATH包含项目根目录。")
    print("例如: export PYTHONPATH=/path/to/DeepStressModel")
    sys.exit(1)

# 设置日志记录器
logger = setup_logger("test_encrypt_upload")

def encrypt_and_upload(json_file, api_key, server_url="http://localhost:8083/api/v1/benchmark-result/upload"):
    """
    加密并上传基准测试结果
    
    Args:
        json_file: 测试结果JSON文件路径
        api_key: API密钥
        server_url: 服务器URL
        
    Returns:
        dict: 上传结果
    """
    try:
        if not os.path.exists(json_file):
            logger.error(f"文件不存在: {json_file}")
            return {"status": "error", "message": f"文件不存在: {json_file}"}
            
        # 读取JSON文件
        with open(json_file, 'r', encoding='utf-8') as f:
            result_data = json.load(f)
            
        # 创建加密器
        encryptor = BenchmarkEncryption()
        
        # 准备元数据
        metadata = {
            "submitter": "测试脚本",
            "model_name": result_data.get("model", "未知模型"),
            "model_version": "1.0",
            "notes": "测试上传 - " + datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "timestamp": datetime.now().isoformat()
        }
        
        # 如果结果中包含model_info，从中获取model_name
        if "model_info" in result_data and isinstance(result_data["model_info"], dict):
            if "model_name" in result_data["model_info"]:
                metadata["model_name"] = result_data["model_info"]["model_name"]
                
            if "quantization" in result_data["model_info"]:
                metadata["model_version"] = result_data["model_info"]["quantization"]
        
        # 加密并上传
        logger.info(f"开始加密并上传文件: {json_file}")
        logger.info(f"服务器URL: {server_url}")
        logger.info(f"元数据: {metadata}")
        
        # 实际调用加密和上传
        try:
            # 将元数据转换为JSON字符串
            metadata_json = json.dumps(metadata, ensure_ascii=False)
            
            # 首先加密文件
            timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
            encrypted_file = f"test_encrypted_{timestamp}.dat"
            # 指定完整路径
            encrypted_path_full = os.path.join(os.path.dirname(json_file), encrypted_file)
            encrypted_path = encryptor.encrypt_and_save(result_data, encrypted_path_full, api_key)
            
            if not encrypted_path:
                logger.error("加密失败")
                return {"status": "error", "message": "加密失败"}
                
            logger.info(f"加密成功，文件保存至: {encrypted_path}")
            
            # 然后上传
            import requests
            
            # 准备请求数据
            data = {
                "api_key": api_key,
                "metadata": metadata_json
            }
            
            # 请求头设置
            headers = {
                "X-API-Key": api_key
            }
            
            # 准备文件
            files = {
                "file": open(encrypted_path, "rb")
            }
            
            # 发送请求
            response = requests.post(server_url, data=data, files=files, headers=headers)
            
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
                
        except Exception as upload_error:
            logger.error(f"加密或上传过程中出错: {str(upload_error)}")
            return {"status": "error", "message": str(upload_error)}
            
    except Exception as e:
        logger.error(f"处理文件出错: {str(e)}")
        return {"status": "error", "message": str(e)}

def main():
    """主函数"""
    if len(sys.argv) < 3:
        print(f"用法: {sys.argv[0]} <测试结果JSON文件> <API密钥>")
        return 1
    
    json_file = sys.argv[1]
    api_key = sys.argv[2]
    
    # 配置服务器URL
    server_url = os.environ.get(
        "BENCHMARK_SERVER_URL", 
        "http://localhost:8083/api/v1/benchmark-result/upload"
    )
    
    result = encrypt_and_upload(json_file, api_key, server_url)
    
    if result.get("status") == "success":
        print(f"上传成功, ID: {result.get('id', 'unknown')}")
        return 0
    else:
        print(f"上传失败: {result.get('message', '未知错误')}")
        return 1

if __name__ == "__main__":
    sys.exit(main()) 