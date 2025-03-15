"""
基准测试日志加密模块的测试脚本
"""
import os
import json
import unittest
import tempfile
from datetime import datetime

from src.benchmark.crypto.benchmark_log_encrypt import BenchmarkEncryption, EncryptionError

class TestBenchmarkEncryption(unittest.TestCase):
    """基准测试日志加密模块的测试类"""
    
    def setUp(self):
        """测试前的设置"""
        self.api_key = "test_api_key_123456"
        self.encryptor = BenchmarkEncryption()
        
        # 准备测试数据
        self.test_log_data = {
            "status": "success",
            "dataset_version": "test_v1.0",
            "start_time": 1742039446.924232,
            "end_time": 1742039527.5310478,
            "total_time": 80.6068,
            "total_tests": 10,
            "successful_tests": 10,
            "success_rate": 1.0,
            "avg_latency": 49.6409,
            "avg_throughput": 0.5455,
            "tps": 1.2405,
            "total_input_chars": 1000,
            "total_output_chars": 5000,
            "total_chars": 6000,
            "total_tokens": 1500,
            "results": [
                {
                    "id": 1,
                    "input": "测试输入内容",
                    "output": "测试输出内容",
                    "expected_output": "",
                    "latency": 31.1440,
                    "throughput": 0.7063,
                    "token_throughput": 4.1741,
                    "input_tokens": 21,
                    "output_tokens": 109,
                    "tokens": 130,
                    "status": "success",
                    "timestamp": 1742039478071,
                    "start_time": 1742039446927,
                    "end_time": 1742039478071
                }
            ]
        }
    
    def test_encrypt_benchmark_log(self):
        """测试基准测试日志加密功能"""
        encrypted_package = self.encryptor.encrypt_benchmark_log(self.test_log_data, self.api_key)
        
        # 验证加密包格式
        self.assertIn("format_version", encrypted_package)
        self.assertIn("encrypted_session_key", encrypted_package)
        self.assertIn("encrypted_data", encrypted_package)
        self.assertIn("signature_data", encrypted_package)
        self.assertIn("signature", encrypted_package)
        self.assertIn("timestamp", encrypted_package)
        
        # 验证加密数据格式
        self.assertIn("nonce", encrypted_package["encrypted_data"])
        self.assertIn("data", encrypted_package["encrypted_data"])
        
        # 验证签名数据格式
        self.assertIn("log_hash", encrypted_package["signature_data"])
        self.assertIn("timestamp", encrypted_package["signature_data"])
        self.assertIn("nonce", encrypted_package["signature_data"])
        self.assertIn("api_key_hash", encrypted_package["signature_data"])
        
        print("加密数据包格式验证通过")
    
    def test_encrypt_and_save(self):
        """测试加密并保存功能"""
        # 创建临时文件
        with tempfile.NamedTemporaryFile(suffix='.json', delete=False) as temp_file:
            output_path = temp_file.name
        
        try:
            # 加密并保存
            self.encryptor.encrypt_and_save(self.test_log_data, output_path, self.api_key)
            
            # 验证文件是否存在
            self.assertTrue(os.path.exists(output_path))
            
            # 验证文件内容
            with open(output_path, 'r', encoding='utf-8') as f:
                encrypted_package = json.load(f)
            
            # 验证加密包格式
            self.assertIn("format_version", encrypted_package)
            self.assertIn("encrypted_session_key", encrypted_package)
            self.assertIn("encrypted_data", encrypted_package)
            self.assertIn("signature_data", encrypted_package)
            self.assertIn("signature", encrypted_package)
            self.assertIn("timestamp", encrypted_package)
            
            print("加密并保存功能验证通过")
        
        finally:
            # 清理临时文件
            if os.path.exists(output_path):
                os.unlink(output_path)
    
    def test_invalid_input_data(self):
        """测试无效的输入数据"""
        # 测试非字典类型的输入
        with self.assertRaises(EncryptionError) as context:
            self.encryptor.encrypt_benchmark_log("非字典数据", self.api_key)
        
        self.assertEqual(context.exception.code, "C1001")
        
        # 测试空API密钥
        with self.assertRaises(EncryptionError) as context:
            self.encryptor.encrypt_benchmark_log(self.test_log_data, "")
        
        self.assertEqual(context.exception.code, "C1001")
        
        # 测试非字符串类型的API密钥
        with self.assertRaises(EncryptionError) as context:
            self.encryptor.encrypt_benchmark_log(self.test_log_data, 123)
        
        self.assertEqual(context.exception.code, "C1001")
        
        print("无效输入数据测试通过")

if __name__ == "__main__":
    unittest.main() 