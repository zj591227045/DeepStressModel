#!/usr/bin/env python3
"""
DeepStressModel加密模块完整功能测试脚本

此脚本测试从公钥加载到加密导出的整个流程，验证：
1. Cython编译的key_storage模块能否正确加载
2. 基准测试日志加密功能是否正常
3. 加密结果的保存和读取
4. 输出加密结果的完整性
"""

import os
import sys
import json
import tempfile
import getpass
from datetime import datetime, timedelta

# 添加项目根目录到路径
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../.."))
sys.path.insert(0, project_root)

def test_full_functionality():
    """测试完整功能链"""
    print("===== DeepStressModel加密模块完整功能测试 =====")
    
    # 步骤1: 测试key_storage模块 - 现在通过benchmark_log_encrypt模块获取公钥
    print("1. 测试公钥获取...")
    try:
        # 导入benchmark_log_encrypt模块
        from src.benchmark.crypto.benchmark_log_encrypt import BenchmarkEncryption, get_public_key
        
        # 直接使用benchmark_log_encrypt模块中的get_public_key函数
        public_key = get_public_key()
        print(f"✓ 公钥加载成功! 长度: {len(public_key)} 字节")
        print(f"公钥片段: {public_key[:30]}...{public_key[-30:]}")
    except Exception as e:
        print(f"✗ 公钥加载失败: {str(e)}")
        return False
    
    # 步骤2: 测试benchmark_log_encrypt模块
    print("\n2. 测试benchmark_log_encrypt模块...")
    try:
        # BenchmarkEncryption已在上一步导入
        encryptor = BenchmarkEncryption()
        print("✓ 加密器初始化成功!")
    except Exception as e:
        print(f"✗ 加密器初始化失败: {str(e)}")
        return False
    
    # 步骤3: 准备测试数据
    print("\n3. 准备测试数据...")
    now = datetime.now()
    start_time = (now - timedelta(minutes=5)).isoformat()
    end_time = now.isoformat()
    
    test_data = {
        "status": "completed",
        "dataset_version": "v1.2.3",
        "model_version": "DeepStressModel v0.9.5-beta",
        "start_time": start_time,
        "end_time": end_time,
        "total_time": 300.58,  # 秒
        "environment": {
            "os": "macOS",
            "python_version": "3.13.0",
            "cpu_info": "Apple M3 Pro",
            "gpu_info": "Apple GPU",
            "memory": "32GB"
        },
        "results": {
            "accuracy": 0.95,
            "precision": 0.93,
            "recall": 0.94,
            "f1_score": 0.935,
            "rmse": 0.032,
            "latency_mean": 0.045,  # 秒
            "latency_p95": 0.089,  # 秒
            "throughout": 22.5  # 样本/秒
        },
        "metadata": {
            "tester": "自动化测试",
            "test_id": "test-001",
            "notes": "完整功能测试"
        }
    }
    print("✓ 测试数据准备完成!")
    
    # 步骤4: 测试加密功能
    print("\n4. 测试加密功能...")
    
    # 请求用户输入API密钥
    print("\n请输入API密钥以进行测试（测试环境可使用任意值）：")
    api_key = getpass.getpass("API密钥: ")
    
    if not api_key:
        print("警告: 未提供API密钥，将使用默认测试密钥")
        api_key = "test_api_key_for_development_only"
    
    try:
        encrypted_package = encryptor.encrypt_benchmark_log(test_data, api_key)
        print("✓ 加密成功!")
        
        # 验证加密包的结构
        required_fields = [
            "format_version", "encrypted_session_key", "encrypted_data", 
            "signature_data", "signature", "timestamp"
        ]
        
        for field in required_fields:
            if field not in encrypted_package:
                print(f"✗ 加密结果缺少字段: {field}")
                return False
        
        print("✓ 加密结果结构验证通过!")
    except Exception as e:
        print(f"✗ 加密失败: {str(e)}")
        return False
    
    # 步骤5: 测试保存加密结果
    print("\n5. 测试保存加密结果...")
    try:
        # 使用临时文件
        with tempfile.NamedTemporaryFile(suffix='.json', delete=False) as temp_file:
            output_path = temp_file.name
        
        encryptor.encrypt_and_save(test_data, output_path, api_key)
        
        # 验证文件是否存在
        if not os.path.exists(output_path):
            print(f"✗ 输出文件不存在: {output_path}")
            return False
        
        # 验证文件内容
        with open(output_path, 'r', encoding='utf-8') as f:
            saved_data = json.load(f)
        
        for field in required_fields:
            if field not in saved_data:
                print(f"✗ 保存的文件缺少字段: {field}")
                return False
        
        print(f"✓ 加密结果已成功保存到文件: {output_path}")
        
        # 清理临时文件
        os.unlink(output_path)
        print("✓ 测试完成后已清理临时文件")
    except Exception as e:
        print(f"✗ 保存加密结果失败: {str(e)}")
        return False
    
    return True

def main():
    """主函数"""
    success = test_full_functionality()
    
    if success:
        print("\n✅ 所有测试通过! DeepStressModel加密模块工作正常。")
    else:
        print("\n❌ 测试失败! 请检查错误信息。")
        sys.exit(1)

if __name__ == "__main__":
    main() 