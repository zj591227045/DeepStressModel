#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
DeepStressModel 离线包加密示例
按照修订后的加密规范 v2.0 加密离线包
"""

import base64
import json
import hashlib
import os
import secrets
import time
from datetime import datetime, timedelta
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives import padding as sym_padding
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from cryptography.hazmat.primitives.serialization import load_pem_private_key
from cryptography.hazmat.backends import default_backend

# 日志函数
def log(message, level="INFO"):
    print(f"[{level}] {message}")

def generate_rsa_key_pair():
    """生成RSA密钥对"""
    private_key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=2048,
        backend=default_backend()
    )
    
    # 获取私钥的PEM格式
    private_key_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption()
    ).decode('utf-8')
    
    # 获取公钥的PEM格式
    public_key = private_key.public_key()
    public_key_pem = public_key.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo
    ).decode('utf-8')
    
    log(f"生成RSA密钥对 - 密钥大小: 2048位")
    log(f"生成RSA密钥对 - 私钥: {private_key_pem[:50]}...")
    log(f"生成RSA密钥对 - 公钥: {public_key_pem[:50]}...")
    
    return private_key_pem, public_key_pem, private_key, public_key

def encrypt_private_key(private_key_pem, api_key):
    """
    使用派生的密钥加密RSA私钥
    按照规范实现
    """
    try:
        # 生成随机盐值（32字节）
        salt = secrets.token_bytes(32)
        log(f"加密私钥 - 生成随机盐值: {salt.hex()}, 长度: {len(salt)}字节")
        
        # 使用PBKDF2派生密钥
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000,
            backend=default_backend()
        )
        key = kdf.derive(api_key.encode())
        log(f"加密私钥 - 派生密钥: {key.hex()}, 长度: {len(key)}字节")
        
        # 生成随机IV（16字节）
        iv = secrets.token_bytes(16)
        log(f"加密私钥 - 生成随机IV: {iv.hex()}, 长度: {len(iv)}字节")
        
        # 对私钥PEM进行填充
        padder = sym_padding.PKCS7(algorithms.AES.block_size).padder()
        padded_data = padder.update(private_key_pem.encode()) + padder.finalize()
        log(f"加密私钥 - 填充后数据长度: {len(padded_data)}字节")
        
        # 使用AES-CBC加密
        cipher = Cipher(algorithms.AES(key), modes.CBC(iv), backend=default_backend())
        encryptor = cipher.encryptor()
        encrypted_data = encryptor.update(padded_data) + encryptor.finalize()
        log(f"加密私钥 - 加密后数据长度: {len(encrypted_data)}字节")
        
        # 构建加密结果
        result = {
            "salt": base64.b64encode(salt).decode(),
            "iv": base64.b64encode(iv).decode(),
            "data": base64.b64encode(encrypted_data).decode()
        }
        
        log(f"加密私钥 - 加密成功")
        return result
    except Exception as e:
        log(f"加密私钥失败: {str(e)}", "ERROR")
        import traceback
        log(traceback.format_exc(), "ERROR")
        return None

def encrypt_session_key(session_key, public_key):
    """
    使用RSA公钥加密会话密钥
    按照规范实现
    """
    try:
        # 使用PKCS1v15填充进行RSA加密
        encrypted_session_key = public_key.encrypt(
            session_key,
            padding.PKCS1v15()
        )
        
        log(f"加密会话密钥 - 会话密钥长度: {len(session_key)}字节")
        log(f"加密会话密钥 - 加密后长度: {len(encrypted_session_key)}字节")
        
        # Base64编码
        encrypted_session_key_b64 = base64.b64encode(encrypted_session_key).decode()
        
        return encrypted_session_key_b64
    except Exception as e:
        log(f"加密会话密钥失败: {str(e)}", "ERROR")
        import traceback
        log(traceback.format_exc(), "ERROR")
        return None

def encrypt_dataset(dataset, session_key):
    """
    使用会话密钥加密数据集
    按照新规范，使用HKDF从会话密钥派生AES密钥
    """
    try:
        # 将数据集转换为JSON字符串
        dataset_json = json.dumps(dataset, ensure_ascii=False).encode('utf-8')
        log(f"加密数据集 - 数据集JSON长度: {len(dataset_json)}字节")
        
        # 生成随机盐值（16字节）用于HKDF
        salt = secrets.token_bytes(16)
        log(f"加密数据集 - HKDF盐值: {salt.hex()}, 长度: {len(salt)}字节")
        
        # 定义信息字符串
        info = b"dataset_encryption"
        
        # 使用HKDF从会话密钥派生AES密钥
        hkdf = HKDF(
            algorithm=hashes.SHA256(),
            length=32,  # 256位密钥
            salt=salt,
            info=info,
            backend=default_backend()
        )
        derived_key = hkdf.derive(session_key)
        log(f"加密数据集 - 派生AES密钥: {derived_key.hex()}, 长度: {len(derived_key)}字节")
        
        # 生成随机IV（16字节）
        iv = secrets.token_bytes(16)
        log(f"加密数据集 - IV: {iv.hex()}, 长度: {len(iv)}字节")
        
        # 对数据集JSON进行PKCS7填充
        padder = sym_padding.PKCS7(algorithms.AES.block_size).padder()
        padded_data = padder.update(dataset_json) + padder.finalize()
        log(f"加密数据集 - 填充后数据长度: {len(padded_data)}字节")
        
        # 使用AES-CBC加密
        cipher = Cipher(algorithms.AES(derived_key), modes.CBC(iv), backend=default_backend())
        encryptor = cipher.encryptor()
        encrypted_data = encryptor.update(padded_data) + encryptor.finalize()
        log(f"加密数据集 - 加密后数据长度: {len(encrypted_data)}字节")
        
        # 构建加密结果
        result = {
            "algorithm": "AES-256-CBC-PKCS7",
            "key_derivation": {
                "method": "HKDF-SHA256",
                "salt": base64.b64encode(salt).decode(),
                "info": "dataset_encryption"
            },
            "iv": base64.b64encode(iv).decode(),
            "data": base64.b64encode(encrypted_data).decode()
        }
        
        log(f"加密数据集 - 加密成功")
        return result
    except Exception as e:
        log(f"加密数据集失败: {str(e)}", "ERROR")
        import traceback
        log(traceback.format_exc(), "ERROR")
        return None

def generate_signature(data, timestamp, api_key):
    """生成签名"""
    # 将数据转换为JSON字符串，并按键排序
    data_str = json.dumps(data, sort_keys=True)
    
    # 拼接数据、时间戳和密钥
    message = f"{data_str}{timestamp}{api_key}"
    
    # 使用SHA-256生成签名
    signature = hashlib.sha256(message.encode()).hexdigest()
    
    log(f"生成签名 - 时间戳: {timestamp}")
    log(f"生成签名 - 签名: {signature[:16]}...")
    
    return signature

def create_offline_package(dataset, api_key, dataset_id=1):
    """创建完整的离线包"""
    try:
        # 1. 生成RSA密钥对
        private_key_pem, public_key_pem, private_key, public_key = generate_rsa_key_pair()
        
        # 2. 使用API密钥加密私钥
        log("步骤1: 使用API密钥加密私钥")
        encrypted_private_key = encrypt_private_key(private_key_pem, api_key)
        if not encrypted_private_key:
            log("加密私钥失败，无法继续", "ERROR")
            return None
        
        # 3. 生成随机会话密钥（32字节）
        log("步骤2: 生成随机会话密钥")
        session_key = secrets.token_bytes(32)
        log(f"会话密钥: {session_key.hex()}, 长度: {len(session_key)}字节")
        
        # 4. 使用RSA公钥加密会话密钥
        log("步骤3: 使用RSA公钥加密会话密钥")
        encrypted_session_key = encrypt_session_key(session_key, public_key)
        if not encrypted_session_key:
            log("加密会话密钥失败，无法继续", "ERROR")
            return None
        
        # 5. 使用会话密钥加密数据集
        log("步骤4: 使用会话密钥加密数据集")
        encrypted_data = encrypt_dataset(dataset, session_key)
        if not encrypted_data:
            log("加密数据集失败，无法继续", "ERROR")
            return None
        
        # 6. 生成时间戳和签名
        timestamp = str(int(time.time() * 1000))
        signature = generate_signature(dataset, timestamp, api_key)
        
        # 7. 构建离线包
        now = datetime.now()
        package = {
            "metadata": {
                "package_format": "4.0",
                "dataset_id": dataset_id,
                "created_at": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "expires_at": (now + timedelta(days=30)).strftime("%Y-%m-%dT%H:%M:%SZ")
            },
            "encrypted_private_key": encrypted_private_key,
            "dataset": {
                "encrypted_session_key": encrypted_session_key,
                "encrypted_data": encrypted_data,
                "timestamp": timestamp,
                "user_signature": signature
            }
        }
        
        log(f"离线包创建成功，格式版本: 4.0, 数据集ID: {dataset_id}")
        return package
    except Exception as e:
        log(f"创建离线包失败: {str(e)}", "ERROR")
        import traceback
        log(traceback.format_exc(), "ERROR")
        return None

def save_offline_package(package, file_path):
    """保存离线包到文件"""
    try:
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(package, f, indent=2, ensure_ascii=False)
        log(f"离线包已保存到: {file_path}")
        return True
    except Exception as e:
        log(f"保存离线包失败: {str(e)}", "ERROR")
        return False

def main():
    # API密钥
    api_key = "你的API密钥"
    
    # 测试数据集
    dataset = {
        "name": "测试数据集",
        "version": "1.0.0",
        "items": [
            {"id": 1, "value": "测试项目1"},
            {"id": 2, "value": "测试项目2"},
            {"id": 3, "value": "测试项目3"}
        ],
        "metadata": {
            "created_at": "2024-05-12T10:30:00Z",
            "author": "测试用户"
        }
    }
    
    # 创建离线包
    log("开始创建离线包")
    package = create_offline_package(dataset, api_key)
    if not package:
        log("创建离线包失败", "ERROR")
        return
    
    # 保存离线包
    output_path = "encrypted_package.json"
    if save_offline_package(package, output_path):
        log(f"离线包创建成功，已保存到: {output_path}")
    else:
        log("保存离线包失败", "ERROR")

if __name__ == "__main__":
    main() 