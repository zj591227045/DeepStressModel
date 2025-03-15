#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
DeepStressModel 基准测试日志加密示例 - 客户端实现
实现公钥混淆和测试日志加密功能
"""

import base64
import hashlib
import hmac
import json
import os
import random
import secrets
import socket
import sys
import time
import uuid
from datetime import datetime
import platform
from typing import Dict, List, Any, Tuple, Optional, Union

# 加密相关库
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
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
# 公钥存储和混淆
# =====================================================

# 公钥片段（已混淆）
# 实际项目中，这些片段应分散存储在不同的模块中
PUBLIC_KEY_FRAGMENTS = [
    {
        "data": "X9fJpQzMbTlK89F2aHgwR4xnmAtIuYcvVBZyUhNDeOo3WEkPs7L6G0q1C==ZipCnx7Bge5Sm3sPoUJ",
        "marker": "djEyNDU2Nzg=.ZjViMzgwOTIxMw==.NDk4NzYzNTJmMQ=="
    },
    {
        "data": "bTU2NjdxcmpnZXBpN2pwb2Rmam9sc==VGgTVEEzVe71pHRjdbNXAyZCIsInRhZyI6InM==mIiwicGF5bG9hZCI6I",
        "marker": "c2RmZmpvc2lqZQ==.ZmFkc2ZzZGE=.YnZjdnZiY24="
    },
    {
        "data": "2dpZjM4OXBqbWZmd==LS0tLS1CRUdJTiBQVUJMSUMgS0VZLS0tLS0==saWZncGRmc2FmZHNhZg==",
        "marker": "ZGFzZnNhZg==.ZmRzYWY=.ZHNhZmRz"
    },
    {
        "data": "eHl6MTIzZGZqaQ==LS0tLS1FTkQgUFVCTElDIEtFWS0tLS0t==MTIzNDU2aGdmZHM=",
        "marker": "aGdmZHNhZmRq.ZmRzYWZk.Z2Zkc2Zm"
    },
    {
        "data": "cG9pMzI0NWRmamRz==TUlJQklqQU5CZ2txaGtpRzl3MEJBUUVGQUFPQ0FROEFNSUlCQ2dLQ0FRRUF==ZHNhZjMyMTNkZnNhZg==",
        "marker": "dGVzdDEyMzQ1.ZGZzYWZkc2FmZHM=.amhnZmRzYWY="
    }
]

# 自定义编码表（替代标准Base64）
CUSTOM_ENCODING_CHARS = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/"
CUSTOM_DECODING_MAP = {char: i for i, char in enumerate(CUSTOM_ENCODING_CHARS)}

# 实际RSA公钥（用于演示，实际项目中这里会被替换成真实的混淆公钥）
# 在实际部署时会使用 obfuscate_public_key() 生成混淆片段
DEMO_PUBLIC_KEY = """
-----BEGIN PUBLIC KEY-----
MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEAu8LXZAdYnV93GwZ1LIGZ
LlC+y01Z96xYyaK/j5OgFuqnTOI0v5wgKVHARF1ZS3xJ2zqhVUptDnnTIxXWykpA
9gW5yQAZmGy5+tIyZqQp/oJEwPNeBPfHQkwzZ9fMxb5PrqqMaI1kebWQ8lJ8NHf7
L/Cva0jPz33MUkpTfK6KDhh9FBdDnZ/SJU5+qEl38OUDtLs4Z7w3JU4RFwY2/rW4
OOIKkZ0OIxToJsQcXJJ7Lm18C8iTT5PyOKg+VHK8JYMQAhVjYXnEjkMQoDCMQcbH
Ga81bK2N5vK1NzP7Qh/XLlYLKQUUY/Tnn2sQgmGnwNlnK2nP3YdxCzQNpdGfF8L2
QQIDAQAB
-----END PUBLIC KEY-----
"""


def generate_custom_encoding_table(seed: int = 42) -> Dict[int, str]:
    """生成自定义编码表"""
    chars = list(CUSTOM_ENCODING_CHARS)
    random.seed(seed)
    random.shuffle(chars)
    return {i: char for i, char in enumerate(chars)}


def custom_encode(data: bytes, encoding_table: Dict[int, str]) -> str:
    """使用自定义表编码数据"""
    # 将字节转换为二进制字符串
    binary_str = ''.join(format(byte, '08b') for byte in data)
    
    # 填充以确保长度是6的倍数
    padding_length = (6 - len(binary_str) % 6) % 6
    binary_str += '0' * padding_length
    
    # 每6位转换为一个字符
    result = []
    for i in range(0, len(binary_str), 6):
        index = int(binary_str[i:i+6], 2)
        result.append(encoding_table[index])
        
    return ''.join(result)


def custom_decode(encoded_str: str, encoding_table: Dict[int, str]) -> bytes:
    """使用自定义表解码数据"""
    # 反转编码表
    decoding_table = {char: i for i, char in encoding_table.items()}
    
    # 将每个字符转换为6位二进制
    binary_str = ''
    for char in encoded_str:
        if char in decoding_table:
            binary_str += format(decoding_table[char], '06b')
    
    # 每8位转换为一个字节
    result = bytearray()
    for i in range(0, len(binary_str) - 7, 8):
        byte = int(binary_str[i:i+8], 2)
        result.append(byte)
        
    return bytes(result)


def split_into_fragments(data: str, fragment_count: int = 5) -> List[str]:
    """将数据分割成多个片段"""
    fragment_size = len(data) // fragment_count
    fragments = []
    
    for i in range(fragment_count - 1):
        start = i * fragment_size
        end = (i + 1) * fragment_size
        fragments.append(data[start:end])
    
    # 最后一个片段包含剩余所有数据
    fragments.append(data[(fragment_count - 1) * fragment_size:])
    
    return fragments


def generate_obfuscation_data(seed: str, length: int) -> str:
    """生成混淆数据"""
    random.seed(seed)
    chars = CUSTOM_ENCODING_CHARS
    return ''.join(random.choice(chars) for _ in range(length))


def encrypt_position(position: int, total: int) -> str:
    """加密位置信息"""
    # 简单混淆，实际项目中应使用更复杂的方法
    part1 = base64.b64encode(f"v{position * 12345678}".encode()).decode()
    part2 = base64.b64encode(f"f{position * 5 + total * 9}213".encode()).decode()
    part3 = base64.b64encode(f"{total * 9876352}f{position}".encode()).decode()
    
    return f"{part1}.{part2}.{part3}"


def decrypt_position(encrypted: str) -> int:
    """解密位置信息"""
    try:
        parts = encrypted.split('.')
        if len(parts) != 3:
            return -1
            
        # 解析第一部分来获取位置
        part1 = base64.b64decode(parts[0]).decode()
        if part1.startswith('v'):
            position = int(part1[1:]) // 12345678
            return position
    except Exception:
        return -1
    
    return -1


def obfuscate_public_key(public_key_pem: str) -> List[Dict[str, str]]:
    """
    将公钥混淆处理，以防止直接提取
    返回混淆后的片段列表
    """
    # 1. 将公钥转换为字节
    key_bytes = public_key_pem.encode()
    
    # 2. 使用自定义编码
    custom_encoding_table = generate_custom_encoding_table(seed=42)
    encoded_key = custom_encode(key_bytes, custom_encoding_table)
    
    # 3. 分割成多个片段
    fragments = split_into_fragments(encoded_key, fragment_count=5)
    
    # 4. 为每个片段添加混淆数据
    obfuscated_fragments = []
    for i, fragment in enumerate(fragments):
        # 添加混淆头和尾
        obfuscation_prefix = generate_obfuscation_data(f"prefix_{i}", len(fragment)//3)
        obfuscation_suffix = generate_obfuscation_data(f"suffix_{i}", len(fragment)//4)
        
        # 组合片段
        obfuscated_fragment = obfuscation_prefix + fragment + obfuscation_suffix
        
        # 添加位置信息（混淆）
        position_marker = encrypt_position(i, len(fragments))
        
        obfuscated_fragments.append({
            "data": obfuscated_fragment,
            "marker": position_marker
        })
    
    # 5. 打乱片段顺序
    random.shuffle(obfuscated_fragments)
    
    # 打印混淆后的片段（用于调试/生成）
    for i, fragment in enumerate(obfuscated_fragments):
        log(f"片段 {i}: {fragment}")
        
    return obfuscated_fragments


def get_obfuscated_key_fragments() -> List[Dict[str, str]]:
    """获取混淆后的公钥片段"""
    # 实际项目中，这些片段可能从不同模块动态获取
    return PUBLIC_KEY_FRAGMENTS


def reassemble_public_key() -> rsa.RSAPublicKey:
    """
    重组公钥
    从混淆的片段中提取和重建原始公钥
    """
    try:
        # 在演示中直接使用示例公钥（实际应用中要使用下面注释的代码）
        public_key_bytes = DEMO_PUBLIC_KEY.encode('utf-8')
        public_key = serialization.load_pem_public_key(
            public_key_bytes,
            backend=default_backend()
        )
        
        log(f"使用演示公钥（实际应用中应重组混淆的公钥片段）")
        return public_key
        
        # 下面是实际重组的代码（用于生产环境）
        """
        # 1. 获取混淆的公钥片段
        obfuscated_fragments = get_obfuscated_key_fragments()
        
        # 2. 对片段排序
        sorted_fragments = sorted(
            obfuscated_fragments, 
            key=lambda x: decrypt_position(x["marker"])
        )
        
        # 3. 提取每个片段中的实际数据
        actual_fragments = []
        for i, fragment in enumerate(sorted_fragments):
            # 去除混淆头和尾
            prefix_len = len(fragment["data"]) // 3
            suffix_len = len(fragment["data"]) // 4
            actual_fragment = fragment["data"][prefix_len:-suffix_len]
            actual_fragments.append(actual_fragment)
        
        # 4. 合并片段
        encoded_key = "".join(actual_fragments)
        
        # 5. 使用自定义解码
        custom_encoding_table = generate_custom_encoding_table(seed=42)
        key_bytes = custom_decode(encoded_key, custom_encoding_table)
        
        # 6. 加载公钥
        public_key_pem = key_bytes.decode()
        public_key = serialization.load_pem_public_key(
            public_key_pem.encode(),
            backend=default_backend()
        )
        
        log(f"成功重组公钥")
        return public_key
        """
    except Exception as e:
        log(f"重组公钥失败: {str(e)}", "ERROR")
        raise SecurityError("公钥重组失败")


# =====================================================
# 环境指纹收集
# =====================================================

def get_environment_fingerprint() -> Dict[str, Any]:
    """
    收集环境指纹
    用于防止在虚拟环境中操作或篡改测试结果
    """
    try:
        # 基本系统信息
        fingerprint = {
            "system": platform.system(),
            "release": platform.release(),
            "version": platform.version(),
            "machine": platform.machine(),
            "processor": platform.processor(),
            "hostname": socket.gethostname(),
            "uuid": str(uuid.uuid4()),  # 会话唯一ID
            "timestamp": int(time.time())
        }
        
        # CPU信息
        try:
            import psutil
            fingerprint["cpu_count"] = psutil.cpu_count()
            fingerprint["cpu_freq"] = psutil.cpu_freq().current if psutil.cpu_freq() else None
            fingerprint["memory"] = psutil.virtual_memory().total
        except ImportError:
            fingerprint["cpu_info"] = "基础信息"
        
        # 添加Python信息
        fingerprint["python_version"] = sys.version
        fingerprint["executable"] = sys.executable
        
        # 添加特征散列
        feature_str = json.dumps(fingerprint, sort_keys=True)
        fingerprint["signature"] = hashlib.sha256(feature_str.encode()).hexdigest()
        
        return fingerprint
    except Exception as e:
        log(f"收集环境指纹出错: {str(e)}", "WARNING")
        # 返回基本信息
        return {
            "system": platform.system(),
            "timestamp": int(time.time()),
            "uuid": str(uuid.uuid4())
        }


# =====================================================
# 加密函数
# =====================================================

def encrypt_aes_gcm(key: bytes, data: bytes) -> Dict[str, str]:
    """
    使用AES-GCM模式加密数据
    AES-GCM提供认证加密，可以检测篡改
    """
    # 生成随机12字节随机数（nonce）
    nonce = secrets.token_bytes(12)
    
    # 创建AESGCM对象
    aesgcm = AESGCM(key)
    
    # 加密数据（包含认证标签）
    ciphertext = aesgcm.encrypt(nonce, data, None)
    
    return {
        "nonce": base64.b64encode(nonce).decode(),
        "ciphertext": base64.b64encode(ciphertext).decode()
    }


def encrypt_rsa_oaep(public_key: rsa.RSAPublicKey, data: bytes) -> bytes:
    """
    使用RSA-OAEP加密数据
    适用于加密会话密钥等小块数据
    """
    encrypted_data = public_key.encrypt(
        data,
        padding.OAEP(
            mgf=padding.MGF1(algorithm=hashes.SHA256()),
            algorithm=hashes.SHA256(),
            label=None
        )
    )
    return encrypted_data


def derive_signing_key(master_key: bytes, timestamp: int) -> bytes:
    """
    从主密钥派生签名密钥
    使用HKDF增加安全性
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


def generate_api_key_hash(session_key: bytes, api_key: str) -> bytes:
    """
    生成API密钥绑定哈希
    将API密钥与会话密钥绑定，防止未授权用户提交测试记录
    
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


def encrypt_benchmark_log(log_data: Dict[str, Any], api_key: str = None) -> Dict[str, Any]:
    """
    加密测试日志
    
    Args:
        log_data: 原始测试日志数据
        api_key: 用户API密钥（必需）
        
    Returns:
        加密后的测试日志包
        
    Raises:
        SecurityError: 如果加密失败或API密钥缺失
    """
    if not api_key:
        raise SecurityError("API密钥缺失，无法加密测试日志")
    
    try:
        # 将日志数据转换为JSON
        log_json = json.dumps(log_data, ensure_ascii=False).encode('utf-8')
        log(f"原始测试日志大小: {len(log_json)} 字节")
        
        # 1. 生成随机会话密钥
        session_key = secrets.token_bytes(32)  # 256位密钥
        log(f"生成会话密钥: 长度 {len(session_key)} 字节")
        
        # 2. 使用会话密钥加密日志数据
        encrypted_log = encrypt_aes_gcm(session_key, log_json)
        log(f"加密日志数据: {len(encrypted_log['ciphertext'])} 字节")
        
        # 3. 重组并加载公钥
        public_key = reassemble_public_key()
        log(f"加载RSA公钥: 大小 {public_key.key_size} 位")
        
        # 4. 使用公钥加密会话密钥
        encrypted_session_key = encrypt_rsa_oaep(public_key, session_key)
        log(f"加密会话密钥: {len(encrypted_session_key)} 字节")
        
        # 5. 计算原始日志数据的哈希值
        log_hash = hashlib.sha256(log_json).digest()
        
        # 6. 收集环境指纹
        env_fingerprint = get_environment_fingerprint()
        log(f"收集环境指纹: {len(env_fingerprint.keys())} 个特征")
        
        # 7. 计算API密钥哈希并添加到签名数据
        api_key_hash = generate_api_key_hash(session_key, api_key)
        
        # 8. 构建签名数据
        signature_data = {
            "log_hash": base64.b64encode(log_hash).decode(),
            "timestamp": int(time.time()),
            "env_fingerprint": env_fingerprint,
            "nonce": secrets.token_hex(16),
            "api_key_hash": base64.b64encode(api_key_hash).decode()
        }
        
        # 9. 派生签名密钥并生成签名
        signing_key = derive_signing_key(session_key, signature_data["timestamp"])
        signature = hmac.new(
            signing_key, 
            json.dumps(signature_data, sort_keys=True).encode(), 
            hashlib.sha256
        ).digest()
        
        log(f"生成签名: 长度 {len(signature)} 字节")
        
        # 10. 组装最终加密数据包
        final_encrypted_package = {
            "format_version": "1.0",
            "encrypted_session_key": base64.b64encode(encrypted_session_key).decode(),
            "encrypted_data": encrypted_log,
            "signature_data": signature_data,
            "signature": base64.b64encode(signature).decode(),
            "timestamp": datetime.now().isoformat()
        }
        
        log(f"加密完成: 生成加密包大小约 {len(json.dumps(final_encrypted_package))} 字节")
        return final_encrypted_package
        
    except Exception as e:
        log(f"加密测试日志失败: {str(e)}", "ERROR")
        import traceback
        log(traceback.format_exc(), "ERROR")
        raise SecurityError(f"加密测试日志失败: {str(e)}")


# =====================================================
# 离线加密函数
# =====================================================

def encrypt_and_store_offline_log(log_data: Dict[str, Any], output_path: str, api_key: str = None) -> Dict[str, Any]:
    """
    加密测试日志并存储到文件
    
    Args:
        log_data: 原始测试日志数据
        output_path: 输出文件路径
        api_key: 用户API密钥（必需）
        
    Returns:
        加密元数据
        
    Raises:
        SecurityError: 如果加密或存储失败
    """
    if not api_key:
        raise SecurityError("API密钥缺失，无法加密测试日志")
    
    try:
        # 加密日志
        encrypted_package = encrypt_benchmark_log(log_data, api_key)
        
        # 确保目录存在
        os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
        
        # 存储加密后的数据
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(encrypted_package, f, ensure_ascii=False, indent=2)
        
        log(f"加密日志已保存到: {output_path}")
        
        # 生成元数据（用于显示）
        metadata = {
            "timestamp": encrypted_package["signature_data"]["timestamp"],
            "log_hash": encrypted_package["signature_data"]["log_hash"][:16] + "...",
            "nonce": encrypted_package["signature_data"]["nonce"],
            "file_path": output_path
        }
        
        return metadata
    except Exception as e:
        log(f"保存加密日志失败: {str(e)}", "ERROR")
        import traceback
        log(traceback.format_exc(), "ERROR")
        raise SecurityError(f"保存加密日志失败: {str(e)}")


# =====================================================
# 辅助函数
# =====================================================

def generate_test_log() -> Dict[str, Any]:
    """生成测试日志（用于示例）"""
    return {
        "status": "success",
        "dataset_version": "test-v1.0",
        "start_time": time.time() - 100,
        "end_time": time.time(),
        "total_time": 100.0,
        "total_tests": 10,
        "successful_tests": 10,
        "success_rate": 1.0,
        "avg_latency": 45.5,
        "avg_throughput": 0.5,
        "tps": 1.2,
        "total_input_chars": 2000,
        "total_output_chars": 30000,
        "total_chars": 32000,
        "total_tokens": 9000,
        "results": [
            {
                "id": 1,
                "input": "这是测试数据",
                "output": "This is test data",
                "expected_output": "",
                "latency": 30.5,
                "throughput": 0.7,
                "token_throughput": 4.1,
                "input_tokens": 20,
                "output_tokens": 100,
                "tokens": 120,
                "status": "success",
                "timestamp": int(time.time() * 1000),
                "start_time": int((time.time() - 30) * 1000),
                "end_time": int(time.time() * 1000),
            }
        ]
    }


def print_public_key_fragments() -> None:
    """打印公钥片段（用于部署）"""
    # 混淆公钥
    public_key_pem = DEMO_PUBLIC_KEY.strip()
    fragments = obfuscate_public_key(public_key_pem)
    
    print("\n=== 混淆后的公钥片段（用于嵌入到客户端代码） ===\n")
    print("PUBLIC_KEY_FRAGMENTS = [")
    for fragment in fragments:
        print(f"    {{\n        \"data\": \"{fragment['data']}\",")
        print(f"        \"marker\": \"{fragment['marker']}\"\n    }},")
    print("]")


# =====================================================
# 主函数
# =====================================================

def main():
    """
    示例脚本入口
    """
    import argparse
    parser = argparse.ArgumentParser(description="DeepStressModel 测试日志加密工具")
    parser.add_argument("input", help="测试日志文件路径", type=str)
    parser.add_argument("-o", "--output", help="输出文件路径", type=str, default="encrypted_benchmark_log.json")
    parser.add_argument("-k", "--api-key", help="API密钥", type=str, required=True)
    args = parser.parse_args()
    
    try:
        # 读取测试日志
        with open(args.input, 'r', encoding='utf-8') as f:
            log_data = json.load(f)
        
        log(f"从 {args.input} 加载测试日志")
        
        # 加密并保存
        metadata = encrypt_and_store_offline_log(log_data, args.output, args.api_key)
        
        log(f"加密日志已保存到: {args.output}")
        print(f"加密时间戳: {metadata['timestamp']}")
        print(f"日志哈希: {metadata['log_hash']}")
    
    except Exception as e:
        log(f"加密失败: {str(e)}", "ERROR")
        sys.exit(1)


if __name__ == "__main__":
    main() 