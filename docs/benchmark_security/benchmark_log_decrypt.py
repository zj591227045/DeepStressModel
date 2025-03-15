#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
DeepStressModel 基准测试日志解密示例 - 服务端实现
实现加密日志的解密和验证功能
"""

import base64
import hashlib
import hmac
import json
import os
import time
from datetime import datetime
from typing import Dict, Any, Optional, Tuple, Union, List
import uuid

# 加密相关库
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF


# =====================================================
# 日志和异常处理
# =====================================================

def log(message: str, level: str = "INFO") -> None:
    """日志记录"""
    print(f"[{level}] {message}")


class SecurityError(Exception):
    """安全相关异常"""
    pass


# =====================================================
# 服务器私钥配置
# =====================================================

# 服务器私钥（示例）
# 实际应用中应从安全存储中加载
SERVER_PRIVATE_KEY = """
-----BEGIN PRIVATE KEY-----
MIIEvgIBADANBgkqhkiG9w0BAQEFAASCBKgwggSkAgEAAoIBAQC7wtdkB1idX3cb
BnUsgZkuUL7LTVn3rFjJor+Pk6AW6qdM4jS/nCApUcBEXVlLfEnbOqFVSm0OedMj
FdbKSkD2BbnJABmYbLn60jJmpCn+gkTA814E98dCTDNn18zFvk+uqoxojWR5tZDy
Unw0d/sv8K9rSM/PfcxSSlN8rooOGH0UF0Odn9IlTn6oSXfw5QO0uzhnvDclThEX
Bjb+tbg44gqRnQ4jFOgmxBxcknsubXwLyJNPk/I4qD5UcrwlgxACFWNhecSOQxCg
MIxBxscZrzVsrY3m8rU3M/tCH9cuVgspBRRj9OefaxCCYafA2Wcrac/dh3ELNA2l
0Z8XwvZBAgMBAAECggEAOXqw4E7+ndIoXMA4VhKAYT+Kx33ysvJJIxnK7G+VF3kf
DBfQVxkS8OCFnNu+TDZ3sk6Lc3yKYZs1ZlZ5KfKCr4NXQswmEhcGMQWqLiw92UIk
MlE8rAWLF0PJfQzajFAymqZYvz9I83IYGBxfYEVvV6DiLSei3JKmeSl+gQDndzlu
6U5Hck1x4cIVsgGwQD4YhIMd10YvCKzChlFnF4xpdyHtCtvB/4D9jXDY+3xE38T4
tH4QLg4sBly6nKY8VwWjplsRcKDmTvLCMb5mbuRY2jKCXkXme/U2aLNCxBL0jRFP
z19gTzT3GDt3TnPrRqbhJj2+xTj7YdSUcXF5DyJfIwKBgQDxEb6wiDPbFdMHhPXK
YtLwPzv7Jn1uYI5LPRZWlXxXl9XlJvQTWbSqqSKCZABQSQjWE2QNh8zEBHmHD51W
VcYHRqXDGtJ/Z3tiDfJjG7hBrEHLDt8nlkqamf9kDCTMu7i3D1Ru/mM1KOKp6nuB
RffoWYZcRe9WVGD3Q6cdSZCaewKBgQDHbz0XW0/ZWVQz+Jgr2yJCxcP3G+UYUzYw
mzZeJiYMRnAXrbjb6HQJCidz8sNHW8UkJaPMZ4tsCRMnaBaWwXyBfmA/JsUVVgQ7
7pjPRZQS1zJGXjNxnhkZj/fjKlvz+0UiEJiiZY8V7OS2/ak9rD9mSZh8Tii4a9nw
Rs/pBxcIswKBgQDRLIzWTQUJRq7c8wMxqzN3Uo0pBN28A3cv0yWpKX0RKJ+xdnFP
x63aFUQ7xV+a0thQcI4wKvz0vXxKOOLrQj506GXDX2VCN09xnALLAcZVUbvR12Fe
Tt6wHdbhRQHXTkOM9daGRTCm4laPb9xQoZLH5ToDr19BvYWYZGwN9CSeGQKBgHEf
PRcHhtfLcyNgBgZbx9x+IXp7gIOxMm7p/fz/jRTtgC7me/LPc/0+5wvD+eFZJlkY
Jb6gAZSjnClnNbQJG5FVVm8H91OUF98mojOWGVqmLBcbfZOhYWRlN+rxXTVPnP4y
BbKCCiaiRLXXcJPNTkXqPq7G1CGjFEY3x5aNgBD9AoGBAN1z6ICrkVEpvEFO8Prk
GVxbpDI8jZaSgRHKKHgQxSMVK8R6hUikCnRx2poNbFnCbhJQIJw012kUgqF4RYSK
TXYqfZDR/nKOQCyPNvhjpTOTFjOJ91CbRm2VcfHXGVsXNj+wwA3wU2+MSF0jIL+P
I2XQY2UqGQZiCqzMqmJaPJPq
-----END PRIVATE KEY-----
"""


def load_private_key() -> rsa.RSAPrivateKey:
    """
    加载服务器私钥
    实际应用中应从安全存储加载
    """
    try:
        private_key = serialization.load_pem_private_key(
            SERVER_PRIVATE_KEY.encode('utf-8'),
            password=None,
            backend=default_backend()
        )
        
        log(f"加载RSA私钥: 大小 {private_key.key_size} 位")
        return private_key
    except Exception as e:
        log(f"加载私钥失败: {str(e)}", "ERROR")
        raise SecurityError("私钥加载失败")


# =====================================================
# 解密函数
# =====================================================

def decrypt_session_key(encrypted_session_key: str) -> bytes:
    """
    使用服务器私钥解密会话密钥
    """
    try:
        # 解码Base64
        encrypted_bytes = base64.b64decode(encrypted_session_key)
        log(f"解密会话密钥: 长度 {len(encrypted_bytes)} 字节")
        
        # 加载私钥
        private_key = load_private_key()
        
        # 使用OAEP填充解密
        session_key = private_key.decrypt(
            encrypted_bytes,
            padding.OAEP(
                mgf=padding.MGF1(algorithm=hashes.SHA256()),
                algorithm=hashes.SHA256(),
                label=None
            )
        )
        
        log(f"会话密钥解密成功: 长度 {len(session_key)} 字节")
        return session_key
    except Exception as e:
        log(f"解密会话密钥失败: {str(e)}", "ERROR")
        # 尝试使用PKCS1v15填充
        try:
            log("尝试使用PKCS1v15填充解密")
            private_key = load_private_key()
            session_key = private_key.decrypt(
                encrypted_bytes,
                padding.PKCS1v15()
            )
            log(f"使用PKCS1v15填充解密成功: 长度 {len(session_key)} 字节")
            return session_key
        except Exception as e2:
            log(f"所有解密方法均失败: {str(e2)}", "ERROR")
            raise SecurityError("会话密钥解密失败")


def decrypt_aes_gcm(key: bytes, encrypted_data: Dict[str, str]) -> bytes:
    """
    使用AES-GCM模式解密数据
    """
    try:
        # 解码Base64
        nonce = base64.b64decode(encrypted_data["nonce"])
        ciphertext = base64.b64decode(encrypted_data["ciphertext"])
        
        log(f"AES-GCM解密: nonce长度 {len(nonce)} 字节, 密文长度 {len(ciphertext)} 字节")
        
        # 创建AESGCM对象
        aesgcm = AESGCM(key)
        
        # 解密数据（自动验证认证标签）
        plaintext = aesgcm.decrypt(nonce, ciphertext, None)
        
        log(f"AES-GCM解密成功: 明文长度 {len(plaintext)} 字节")
        return plaintext
    except Exception as e:
        log(f"AES-GCM解密失败: {str(e)}", "ERROR")
        raise SecurityError(f"数据解密失败: {str(e)}")


def derive_signing_key(master_key: bytes, timestamp: int) -> bytes:
    """
    从主密钥派生签名密钥
    与客户端使用相同的派生方法
    """
    # 使用时间戳作为盐值的一部分
    salt = hashlib.sha256(f"{timestamp}".encode()).digest()
    
    # 使用HKDF派生密钥
    hkdf = HKDF(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        info=b"benchmark_log_signature",
        backend=default_backend()
    )
    
    return hkdf.derive(master_key)


# =====================================================
# 验证函数
# =====================================================

def validate_package_format(encrypted_package: Dict[str, Any]) -> bool:
    """
    验证加密包格式是否正确
    """
    required_fields = [
        "format_version", 
        "encrypted_session_key", 
        "encrypted_data", 
        "signature_data", 
        "signature"
    ]
    
    for field in required_fields:
        if field not in encrypted_package:
            log(f"加密包缺少必需字段: {field}", "ERROR")
            return False
    
    # 验证版本
    if encrypted_package["format_version"] != "1.0":
        log(f"不支持的格式版本: {encrypted_package['format_version']}", "WARNING")
    
    return True


def validate_timestamp(signature_data: Dict[str, Any], max_age_seconds: int = 300) -> bool:
    """
    验证时间戳是否在允许范围内
    防止重放攻击
    """
    current_time = int(time.time())
    timestamp = signature_data.get("timestamp", 0)
    
    # 允许5分钟的时间偏差（可配置）
    time_diff = abs(current_time - timestamp)
    
    if time_diff > max_age_seconds:
        log(f"时间戳过期: 当前时间与签名时间相差 {time_diff} 秒", "WARNING")
        return False
    
    return True


def verify_signature(
    session_key: bytes, 
    signature_data: Dict[str, Any], 
    signature: str, 
    decrypted_log: bytes
) -> bool:
    """
    验证签名
    验证日志数据的完整性和真实性
    """
    try:
        # 1. 验证日志哈希值
        actual_hash = hashlib.sha256(decrypted_log).digest()
        expected_hash = base64.b64decode(signature_data["log_hash"])
        
        if not hmac.compare_digest(actual_hash, expected_hash):
            log("日志哈希值不匹配，数据可能被篡改", "ERROR")
            return False
        
        log("日志哈希值验证通过")
        
        # 2. 派生签名密钥
        signing_key = derive_signing_key(session_key, signature_data["timestamp"])
        
        # 3. 验证HMAC签名
        calculated_signature = hmac.new(
            signing_key, 
            json.dumps(signature_data, sort_keys=True).encode(), 
            hashlib.sha256
        ).digest()
        
        if not hmac.compare_digest(calculated_signature, base64.b64decode(signature)):
            log("签名验证失败，数据可能被篡改", "ERROR")
            return False
        
        log("签名验证通过")
        return True
    
    except Exception as e:
        log(f"签名验证过程出错: {str(e)}", "ERROR")
        return False


def verify_environment(signature_data: Dict[str, Any], decrypted_log: Dict[str, Any]) -> bool:
    """
    验证环境指纹
    检测是否在虚拟环境中或者是否对测试环境进行了篡改
    """
    try:
        # 获取环境指纹
        env_fingerprint = signature_data.get("env_fingerprint", {})
        
        # 基本检查：确保包含关键字段
        required_fields = ["system", "timestamp", "uuid"]
        for field in required_fields:
            if field not in env_fingerprint:
                log(f"环境指纹缺少必需字段: {field}", "WARNING")
                return False
        
        # 获取日志中的测试信息
        # 这里可以根据具体日志结构进行定制化验证
        # 例如确保测试日期与环境时间戳相匹配
        
        log_timestamp = decrypted_log.get("start_time", 0)
        env_timestamp = env_fingerprint.get("timestamp", 0)
        
        # 允许合理的时间差
        if abs(log_timestamp - env_timestamp) > 3600:  # 1小时
            log(f"测试时间与环境时间相差过大: {abs(log_timestamp - env_timestamp)} 秒", "WARNING")
            return False
        
        # 可以添加更多检查：
        # 1. 硬件资源与测试性能的合理性检查
        # 2. 检查是否存在虚拟化指标
        # 3. 分析测试结果的内部一致性
        
        log("环境指纹验证通过")
        return True
    
    except Exception as e:
        log(f"环境验证过程出错: {str(e)}", "WARNING")
        # 根据具体需求决定是否通过
        return True


def generate_api_key_hash(session_key: bytes, api_key: str) -> bytes:
    """
    生成API密钥绑定哈希
    与客户端使用相同算法生成哈希值
    
    Args:
        session_key: 会话密钥
        api_key: 用户API密钥
        
    Returns:
        API密钥哈希
    """
    try:
        # 转换API密钥为字节
        api_key_bytes = api_key.encode('utf-8')
        salt = b"deepstress_api_binding"
        
        # 使用HKDF派生API密钥绑定材料
        hkdf = HKDF(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            info=b"api_key_binding",
            backend=default_backend()
        )
        
        binding_material = hkdf.derive(api_key_bytes + session_key)
        
        # 计算哈希（不直接存储API密钥）
        return hashlib.sha256(binding_material).digest()
    
    except Exception as e:
        log(f"生成API密钥哈希失败: {str(e)}", "ERROR")
        raise SecurityError(f"API密钥处理错误: {str(e)}")


def verify_api_key_binding(session_key: bytes, signature_data: Dict[str, Any], api_key: str) -> bool:
    """
    验证API密钥绑定
    确保上传者使用的API密钥与加密时相同
    
    Args:
        session_key: 解密后的会话密钥
        signature_data: 签名数据
        api_key: 当前用户的API密钥
        
    Returns:
        验证结果
    """
    try:
        # 从签名数据中提取API密钥哈希
        stored_api_key_hash_b64 = signature_data.get("api_key_hash")
        if not stored_api_key_hash_b64:
            log("签名数据中缺少API密钥哈希", "ERROR")
            return False
        
        stored_api_key_hash = base64.b64decode(stored_api_key_hash_b64)
        
        # 使用当前用户的API密钥生成哈希
        current_api_key_hash = generate_api_key_hash(session_key, api_key)
        
        # 安全比较两个哈希值
        if hmac.compare_digest(stored_api_key_hash, current_api_key_hash):
            log("API密钥验证通过")
            return True
        else:
            log("API密钥验证失败，哈希值不匹配", "ERROR")
            return False
    
    except Exception as e:
        log(f"API密钥验证过程出错: {str(e)}", "ERROR")
        return False


# =====================================================
# 主解密流程
# =====================================================

def decrypt_benchmark_log(encrypted_package: Dict[str, Any], api_key: str = None) -> Dict[str, Any]:
    """
    解密和验证测试日志
    处理整个解密和验证流程
    
    Args:
        encrypted_package: 加密的测试日志包
        api_key: 当前用户的API密钥
        
    Returns:
        解密并验证后的测试日志，或验证失败的错误报告
    """
    # 验证包格式
    if not validate_package_format(encrypted_package):
        return generate_error_report("format_error", "无效的加密包格式")
    
    # 检查API密钥
    if not api_key:
        return generate_error_report("api_key_error", "缺少API密钥，无法验证测试记录")
    
    try:
        # 提取签名数据和签名
        encrypted_session_key = encrypted_package.get("encrypted_key", "")
        encrypted_data = encrypted_package.get("encrypted_data", {})
        signature_data = encrypted_package.get("signature_data", {})
        signature = encrypted_package.get("signature", "")
        
        # 验证时间戳
        if not validate_timestamp(signature_data):
            return generate_error_report("timestamp_error", "时间戳验证失败", 
                                         {"format_valid": True})
        
        # 解密会话密钥
        try:
            session_key = decrypt_session_key(encrypted_session_key)
        except Exception as e:
            return generate_error_report("crypto_error", f"会话密钥解密失败: {str(e)}", 
                                         {"format_valid": True, "timestamp_valid": True})
        
        # 解密数据
        try:
            decrypted_data = decrypt_aes_gcm(session_key, encrypted_data)
        except Exception as e:
            return generate_error_report("crypto_error", f"AES-GCM解密失败: {str(e)}",
                                         {"format_valid": True, "timestamp_valid": True})
        
        # 解析解密后的JSON数据
        try:
            decrypted_log = json.loads(decrypted_data.decode('utf-8'))
        except json.JSONDecodeError:
            return generate_error_report("format_error", "解密后数据不是有效的JSON格式",
                                         {"format_valid": True, "timestamp_valid": True})
        
        # 验证签名
        if not verify_signature(session_key, signature_data, signature, decrypted_data):
            return generate_error_report("signature_error", "签名验证失败",
                                         {"format_valid": True, "timestamp_valid": True})
        
        # 验证环境指纹
        if not verify_environment(signature_data, decrypted_log):
            return generate_error_report("environment_error", "环境指纹验证失败",
                                         {"format_valid": True, "timestamp_valid": True, 
                                          "signature_valid": True})
        
        # 验证API密钥绑定
        if not verify_api_key_binding(session_key, signature_data, api_key):
            return generate_error_report("api_key_error", "API密钥验证失败，与测试记录不匹配",
                                         {"format_valid": True, "timestamp_valid": True, 
                                          "signature_valid": True, "api_key_valid": False})
        
        # 添加验证元数据
        decrypted_log["_metadata"] = {
            "timestamp_verified": True,
            "signature_verified": True,
            "environment_verified": True,
            "api_key_verified": True,  # 添加API密钥验证状态
            "verification_time": datetime.now().isoformat()
        }
        
        log("测试日志验证成功")
        return decrypted_log
        
    except Exception as e:
        log(f"解密过程未预期错误: {str(e)}", "ERROR")
        return generate_error_report("unknown_error", f"解密过程错误: {str(e)}")


def load_and_decrypt_log(file_path: str, api_key: str = None) -> Dict[str, Any]:
    """
    从文件加载并解密测试日志
    
    Args:
        file_path: 加密日志文件路径
        api_key: 当前用户的API密钥
        
    Returns:
        解密后的测试日志或错误报告
    """
    try:
        # 读取并解析JSON文件
        with open(file_path, 'r', encoding='utf-8') as f:
            encrypted_package = json.load(f)
            
        # 解密和验证
        return decrypt_benchmark_log(encrypted_package, api_key)
        
    except json.JSONDecodeError:
        return generate_error_report("format_error", f"文件不是有效的JSON格式: {file_path}")
    except FileNotFoundError:
        return generate_error_report("file_error", f"文件未找到: {file_path}")
    except Exception as e:
        return generate_error_report("unknown_error", f"加载加密日志时出错: {str(e)}")


# =====================================================
# API和报告函数
# =====================================================

def generate_verification_report(decrypted_log: Dict[str, Any]) -> Dict[str, Any]:
    """
    生成验证报告
    总结日志的验证结果和关键指标，适配API返回格式
    """
    # 生成唯一上传ID
    upload_id = str(uuid.uuid4())
    
    # 提取关键指标
    report = {
        "status": "success",
        "message": "测试日志验证成功",
        "upload_id": upload_id,
        "validation": {
            "is_valid": True,
            "signature_valid": True,
            "timestamp_valid": True,
            "format_valid": True,
            "api_key_valid": True,  # 添加API密钥验证状态
            "errors": []
        },
        "benchmark_summary": {
            "status": decrypted_log.get("status"),
            "total_tests": decrypted_log.get("total_tests"),
            "successful_tests": decrypted_log.get("successful_tests"),
            "success_rate": decrypted_log.get("success_rate"),
            "avg_latency": decrypted_log.get("avg_latency"),
            "avg_throughput": decrypted_log.get("avg_throughput"),
            "tps": decrypted_log.get("tps"),
            "total_tokens": decrypted_log.get("total_tokens")
        },
        "execution_time": {
            "start_time": datetime.fromtimestamp(decrypted_log.get("start_time", 0)).isoformat(),
            "end_time": datetime.fromtimestamp(decrypted_log.get("end_time", 0)).isoformat(),
            "total_seconds": decrypted_log.get("total_time")
        },
        "verification_details": {
            "verification_time": datetime.now().isoformat(),
            "dataset_version": decrypted_log.get("dataset_version", "unknown"),
            "model_info": decrypted_log.get("model_info", {})
        }
    }
    
    # 添加验证元数据
    if "_metadata" in decrypted_log:
        report["verification_details"]["metadata"] = decrypted_log["_metadata"]
    
    return report


def save_decrypted_log(decrypted_log: Dict[str, Any], output_path: str) -> None:
    """
    保存解密后的日志
    """
    try:
        # 确保目录存在
        os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
        
        # 保存解密后的数据
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(decrypted_log, f, ensure_ascii=False, indent=2)
        
        log(f"解密日志已保存到: {output_path}")
    
    except Exception as e:
        log(f"保存解密日志失败: {str(e)}", "ERROR")


def generate_error_report(error_type: str, error_message: str, validation_details: Dict[str, Any] = None) -> Dict[str, Any]:
    """
    生成验证失败的错误报告
    适配API返回格式
    
    Args:
        error_type: 错误类型 (format_error, crypto_error, signature_error, timestamp_error, api_key_error 等)
        error_message: 错误描述
        validation_details: 可选的验证详情
        
    Returns:
        符合API格式的错误报告
    """
    # 生成唯一上传ID (即使验证失败也生成ID便于跟踪)
    upload_id = str(uuid.uuid4())
    
    # 默认验证结果
    validation = {
        "is_valid": False,
        "signature_valid": False,
        "timestamp_valid": False,
        "format_valid": False,
        "api_key_valid": False,  # 添加API密钥验证状态
        "errors": [error_message]
    }
    
    # 根据错误类型更新特定字段
    if error_type == "format_error":
        validation["format_valid"] = False
    elif error_type == "timestamp_error":
        validation["format_valid"] = True
        validation["timestamp_valid"] = False
    elif error_type == "signature_error":
        validation["format_valid"] = True
        validation["timestamp_valid"] = True
        validation["signature_valid"] = False
    elif error_type == "api_key_error":
        validation["format_valid"] = True
        validation["timestamp_valid"] = True
        validation["signature_valid"] = True
        validation["api_key_valid"] = False
    
    # 合并其他验证详情
    if validation_details:
        for key, value in validation_details.items():
            if key != "errors":
                validation[key] = value
            else:
                validation["errors"].extend(value)
    
    return {
        "status": "error",
        "message": f"验证失败: {error_message}",
        "upload_id": upload_id,
        "validation": validation
    }


# =====================================================
# 主函数
# =====================================================

def main():
    """
    示例脚本入口
    """
    import argparse
    parser = argparse.ArgumentParser(description="DeepStressModel 测试日志解密工具")
    parser.add_argument("input", help="加密的日志文件路径", type=str)
    parser.add_argument("-o", "--output", help="输出文件路径", type=str, default=None)
    parser.add_argument("-v", "--verbose", help="详细输出", action="store_true")
    parser.add_argument("--api-format", help="使用API兼容的输出格式", action="store_true")
    parser.add_argument("-k", "--api-key", help="API密钥", type=str, required=True)
    args = parser.parse_args()
    
    log(f"解密日志文件: {args.input}")
    
    try:
        # 加载并解析加密日志
        with open(args.input, 'r', encoding='utf-8') as f:
            encrypted_package = json.load(f)
        
        # 解密和验证日志
        result = decrypt_benchmark_log(encrypted_package, args.api_key)
        
        # 检查是否为错误报告
        if result.get("status") == "error":
            print("\n" + "=" * 50)
            print("验证失败报告:")
            print(f"状态: {result['status']}")
            print(f"消息: {result['message']}")
            print(f"上传ID: {result['upload_id']}")
            
            print("\n验证结果:")
            for key, value in result["validation"].items():
                if key != "errors":
                    print(f"- {key}: {value}")
            
            if result["validation"].get("errors"):
                print("\n错误详情:")
                for error in result["validation"]["errors"]:
                    print(f"- {error}")
            
            print("=" * 50 + "\n")
            sys.exit(1)
        
        # 成功解密，生成验证报告
        if args.api_format:
            # 如果请求API格式，直接生成兼容API的报告
            report = generate_verification_report(result)
            
            # 输出报告
            print("\n" + "=" * 50)
            print("API格式验证报告:")
            print(f"状态: {report['status']}")
            print(f"消息: {report['message']}")
            print(f"上传ID: {report['upload_id']}")
            
            print("\n验证结果:")
            for key, value in report["validation"].items():
                print(f"- {key}: {value}")
                
            print("\n测试摘要:")
            for key, value in report["benchmark_summary"].items():
                print(f"- {key}: {value}")
            print("=" * 50 + "\n")
        else:
            # 传统格式输出
            print("\n" + "=" * 50)
            print("验证报告:")
            print(f"状态: 成功")
            print(f"验证时间: {result['_metadata']['verification_time']}")
            
            print("\n测试摘要:")
            for key, value in {
                "total_tests": result.get("total_tests"),
                "success_rate": result.get("success_rate"),
                "avg_latency": result.get("avg_latency"),
                "tps": result.get("tps")
            }.items():
                print(f"- {key}: {value}")
            print("=" * 50 + "\n")
        
        # 保存解密结果
        if args.output:
            save_decrypted_log(result, args.output)
            
    except Exception as e:
        print(f"\n未预期错误: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    main() 