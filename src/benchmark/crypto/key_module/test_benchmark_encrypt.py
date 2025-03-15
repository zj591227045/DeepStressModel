#!/usr/bin/env python3
"""
测试修改后的基准测试日志加密模块
"""
import os
import sys
import json
import getpass

# 添加项目根目录到系统路径
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../.."))
sys.path.insert(0, project_root)

def test_benchmark_encrypt():
    """测试基准测试日志加密模块"""
    try:
        # 导入加密模块
        from src.benchmark.crypto.benchmark_log_encrypt import BenchmarkEncryption
        
        # 初始化加密器
        print("初始化加密器...")
        encryptor = BenchmarkEncryption()
        
        # 准备测试数据
        test_data = {
            "status": "success",
            "dataset_version": "test_v1.0",
            "start_time": 1742039446.924232,
            "end_time": 1742039527.5310478,
            "total_time": 80.6068,
            "results": [{"id": 1, "input": "测试输入", "output": "测试输出"}]
        }
        
        # 请求用户输入API密钥
        print("\n请输入API密钥以进行测试（测试环境可使用任意值）：")
        api_key = getpass.getpass("API密钥: ")
        
        if not api_key:
            print("警告: 未提供API密钥，将使用默认测试密钥")
            api_key = "test_api_key_for_development_only"
        
        # 测试加密
        print("测试数据加密...")
        encrypted = encryptor.encrypt_benchmark_log(test_data, api_key)
        
        # 检查加密结果
        if not isinstance(encrypted, dict):
            print("错误: 加密结果不是字典类型")
            return False
        
        required_fields = ["format_version", "encrypted_session_key", "encrypted_data", 
                          "signature_data", "signature", "timestamp"]
        
        for field in required_fields:
            if field not in encrypted:
                print(f"错误: 缺少必需字段 '{field}'")
                return False
        
        print("所有必需字段验证通过！")
        
        # 测试保存到文件
        output_path = "test_encrypted.json"
        print(f"测试保存加密结果到文件: {output_path}")
        encryptor.encrypt_and_save(test_data, output_path, api_key)
        
        # 验证文件是否存在
        if not os.path.exists(output_path):
            print(f"错误: 加密文件 {output_path} 未创建")
            return False
        
        # 读取并验证文件内容
        with open(output_path, 'r', encoding='utf-8') as f:
            file_content = json.load(f)
            
        if not isinstance(file_content, dict) or "format_version" not in file_content:
            print("错误: 保存的文件内容格式不正确")
            return False
            
        print("文件保存和读取测试通过！")
        
        # 清理测试文件
        os.unlink(output_path)
        print(f"已删除测试文件: {output_path}")
        
        return True
    except Exception as e:
        print(f"错误: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """主函数"""
    print("===== 基准测试日志加密模块测试 =====")
    
    # 测试模块
    success = test_benchmark_encrypt()
    
    if success:
        print("\n✓ 测试通过！基准测试日志加密模块工作正常。")
        return 0
    else:
        print("\n✗ 测试失败！请检查模块是否正确。")
        return 1

if __name__ == "__main__":
    sys.exit(main()) 