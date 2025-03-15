#!/usr/bin/env python3
"""
基准测试结果加密与上传工具

用于加密并上传已有的基准测试结果
"""
import os
import sys
import json
import argparse
from datetime import datetime
from typing import Dict, Any

# 添加项目根目录到系统路径
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../../"))
sys.path.insert(0, project_root)

from src.utils.logger import setup_logger
from src.benchmark.crypto.benchmark_log_encrypt import BenchmarkEncryption, EncryptionError

# 设置日志记录器
logger = setup_logger("encrypt_and_upload")

def load_result(result_path: str) -> Dict[str, Any]:
    """
    加载测试结果
    
    Args:
        result_path: 结果文件路径
        
    Returns:
        Dict[str, Any]: 测试结果
    """
    try:
        with open(result_path, 'r', encoding='utf-8') as f:
            result = json.load(f)
        return result
    except Exception as e:
        logger.error(f"加载测试结果失败: {str(e)}")
        raise ValueError(f"无法加载测试结果文件: {str(e)}")

def main():
    """命令行入口点"""
    parser = argparse.ArgumentParser(description="DeepStressModel 测试结果加密与上传工具")
    parser.add_argument("input", help="测试结果文件路径", type=str)
    parser.add_argument("-o", "--output", help="加密输出文件路径", type=str, default=None)
    parser.add_argument("-k", "--api-key", help="API密钥", type=str, required=True)
    parser.add_argument("-u", "--upload", help="上传到服务器", action="store_true")
    parser.add_argument("-s", "--server", help="服务器URL", type=str, 
                        default="https://benchmark.example.com/api/v1/benchmark/upload")
    parser.add_argument("-m", "--metadata", help="元数据JSON文件路径", type=str, default=None)
    args = parser.parse_args()
    
    try:
        # 加载测试结果
        result = load_result(args.input)
        
        # 初始化加密器
        encryptor = BenchmarkEncryption()
        
        # 加载元数据
        metadata = None
        if args.metadata:
            with open(args.metadata, 'r', encoding='utf-8') as f:
                metadata = json.load(f)
        else:
            # 创建默认元数据
            metadata = {
                "submitter": os.environ.get("USER", "unknown_user"),
                "submission_time": datetime.now().isoformat()
            }
            
            # 添加结果中的硬件信息到元数据
            if "hardware_info" in result:
                metadata["hardware_info"] = result["hardware_info"]
            
            if "system_info" in result:
                metadata["system_info"] = result["system_info"]
        
        if args.upload:
            # 加密并上传
            logger.info(f"正在加密并上传测试结果: {args.input}")
            upload_result = encryptor.encrypt_and_upload(
                result,
                api_key=args.api_key,
                server_url=args.server,
                metadata=metadata
            )
            
            print("上传结果:")
            print(json.dumps(upload_result, ensure_ascii=False, indent=2))
        else:
            # 加密并保存到文件
            output_path = args.output or f"encrypted_{os.path.basename(args.input)}"
            logger.info(f"正在加密测试结果: {args.input} -> {output_path}")
            encryptor.encrypt_and_save(result, output_path, api_key=args.api_key)
            print(f"已加密并保存到: {output_path}")
    
    except EncryptionError as e:
        print(f"错误 {e.code}: {e.message}")
        if e.details:
            print(f"详情: {e.details}")
        sys.exit(1)
    except Exception as e:
        print(f"错误: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main() 