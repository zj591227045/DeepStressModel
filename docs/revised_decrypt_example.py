#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
DeepStressModel 离线包解密示例
按照修订后的加密规范 v2.0 解密离线包
"""

import base64
import json
import hashlib
import os
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives import padding as sym_padding
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from cryptography.hazmat.primitives.serialization import load_pem_private_key
from cryptography.hazmat.backends import default_backend
from Crypto.Util.Padding import unpad
from Crypto.Cipher import AES

# 日志函数
def log(message, level="INFO"):
    print(f"[{level}] {message}")

def load_offline_package(file_path):
    """加载离线包文件"""
    with open(file_path, 'r', encoding='utf-8') as f:
        return json.load(f)

def decrypt_private_key(api_key, encrypted_private_key):
    """
    使用派生的密钥解密私钥
    完全按照规范实现
    """
    try:
        # 提取盐值、IV和加密数据
        salt = base64.b64decode(encrypted_private_key["salt"])
        iv = base64.b64decode(encrypted_private_key["iv"])
        encrypted_data = base64.b64decode(encrypted_private_key["data"])
        
        log(f"解密私钥 - 盐值长度: {len(salt)}字节, 盐值(hex): {salt.hex()}")
        log(f"解密私钥 - IV长度: {len(iv)}字节, IV(hex): {iv.hex()}")
        log(f"解密私钥 - 加密数据长度: {len(encrypted_data)}字节")
        
        # 派生密钥
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000,
            backend=default_backend()
        )
        key = kdf.derive(api_key.encode())
        log(f"解密私钥 - 派生密钥(hex): {key.hex()}, 长度: {len(key)}字节")
        
        # 创建解密器
        cipher = Cipher(algorithms.AES(key), modes.CBC(iv), backend=default_backend())
        decryptor = cipher.decryptor()
        
        # 解密数据
        decrypted_padded_data = decryptor.update(encrypted_data) + decryptor.finalize()
        log(f"解密私钥 - 填充数据长度: {len(decrypted_padded_data)}字节")
        
        # 去除PKCS7填充
        unpadder = sym_padding.PKCS7(algorithms.AES.block_size).unpadder()
        decrypted_data = unpadder.update(decrypted_padded_data) + unpadder.finalize()
        log(f"解密私钥 - 去除填充后数据长度: {len(decrypted_data)}字节")
        
        # 转换为字符串
        decrypted_str = decrypted_data.decode('utf-8')
        log(f"解密私钥 - 解密成功，PEM格式私钥头部: {decrypted_str[:50]}")
        log(f"解密私钥 - PEM格式私钥尾部: {decrypted_str[-50:]}")
        
        return decrypted_str
    except Exception as e:
        log(f"解密私钥失败: {str(e)}", "ERROR")
        import traceback
        log(traceback.format_exc(), "ERROR")
        return None

def decrypt_session_key(encrypted_session_key, private_key_pem):
    """
    使用RSA私钥解密会话密钥
    优先尝试PKCS1v15填充，失败后尝试OAEP填充
    """
    try:
        # 解码会话密钥
        encrypted_bytes = base64.b64decode(encrypted_session_key)
        log(f"解密会话密钥 - 加密会话密钥长度: {len(encrypted_bytes)}字节")
        log(f"解密会话密钥 - 加密会话密钥(hex): {encrypted_bytes.hex()[:64]}...")
        
        # 加载私钥
        private_key = load_pem_private_key(
            private_key_pem.encode('utf-8'),
            password=None,
            backend=default_backend()
        )
        log(f"解密会话密钥 - 私钥加载成功, 密钥大小: {private_key.key_size}位")
        
        # 尝试使用PKCS1v15填充进行RSA解密
        try:
            log("解密会话密钥 - 尝试使用PKCS1v15填充解密")
            session_key = private_key.decrypt(
                encrypted_bytes,
                padding.PKCS1v15()
            )
            log(f"解密会话密钥 - PKCS1v15解密成功, 会话密钥长度: {len(session_key)}字节")
            log(f"解密会话密钥 - 会话密钥(hex): {session_key.hex()}")
            return session_key
        except Exception as e:
            log(f"解密会话密钥 - PKCS1v15解密失败: {str(e)}", "WARNING")
        
        # 如果PKCS1v15失败，尝试使用OAEP填充
        try:
            log("解密会话密钥 - 尝试使用OAEP填充(MGF1 with SHA-256)解密")
            session_key = private_key.decrypt(
                encrypted_bytes,
                padding.OAEP(
                    mgf=padding.MGF1(algorithm=hashes.SHA256()),
                    algorithm=hashes.SHA256(),
                    label=None
                )
            )
            log(f"解密会话密钥 - OAEP解密成功, 会话密钥长度: {len(session_key)}字节")
            log(f"解密会话密钥 - 会话密钥(hex): {session_key.hex()}")
            return session_key
        except Exception as e:
            log(f"解密会话密钥 - OAEP解密也失败: {str(e)}", "ERROR")
        
        log("解密会话密钥 - 所有RSA解密方法均失败", "ERROR")
        return None
    except Exception as e:
        log(f"解密会话密钥失败: {str(e)}", "ERROR")
        import traceback
        log(traceback.format_exc(), "ERROR")
        return None

def decrypt_dataset(encrypted_data, session_key):
    """
    使用会话密钥解密数据集
    按照新规范，使用HKDF从会话密钥派生AES密钥
    """
    try:
        # 记录会话密钥信息
        log(f"解密数据集 - 会话密钥长度: {len(session_key)}字节")
        log(f"解密数据集 - 会话密钥(hex): {session_key.hex()}")
        
        # 提取加密算法信息
        algorithm = encrypted_data.get("algorithm", "AES-256-CBC-PKCS7")
        log(f"解密数据集 - 加密算法: {algorithm}")
        
        # 提取密钥派生参数
        key_derivation = encrypted_data.get("key_derivation", {})
        method = key_derivation.get("method", "HKDF-SHA256")
        salt = base64.b64decode(key_derivation.get("salt", ""))
        info = key_derivation.get("info", "dataset_encryption").encode('utf-8')
        log(f"解密数据集 - 密钥派生方法: {method}")
        log(f"解密数据集 - 密钥派生盐值(hex): {salt.hex()}, 长度: {len(salt)}字节")
        log(f"解密数据集 - 密钥派生信息: {info}")
        
        # 使用HKDF从会话密钥派生AES密钥
        hkdf = HKDF(
            algorithm=hashes.SHA256(),
            length=32,  # 256位密钥
            salt=salt,
            info=info,
            backend=default_backend()
        )
        derived_key = hkdf.derive(session_key)
        log(f"解密数据集 - 派生AES密钥(hex): {derived_key.hex()}, 长度: {len(derived_key)}字节")
        
        # 解析IV和加密数据
        iv = base64.b64decode(encrypted_data["iv"])
        ciphertext = base64.b64decode(encrypted_data["data"])
        log(f"解密数据集 - IV(hex): {iv.hex()}, 长度: {len(iv)}字节")
        log(f"解密数据集 - 加密数据长度: {len(ciphertext)}字节")
        
        # 使用AES-CBC解密
        cipher = AES.new(derived_key, AES.MODE_CBC, iv)
        decrypted_padded = cipher.decrypt(ciphertext)
        log(f"解密数据集 - 解密后的填充数据长度: {len(decrypted_padded)}字节")
        
        # 去除PKCS7填充
        decrypted = unpad(decrypted_padded, AES.block_size)
        log(f"解密数据集 - 去除填充后数据长度: {len(decrypted)}字节")
        
        # 解析JSON
        dataset = json.loads(decrypted.decode('utf-8'))
        log(f"解密数据集 - 解密成功，数据集包含 {len(dataset.keys())} 个顶级键")
        return dataset
        
    except Exception as e:
        log(f"解密数据集失败: {str(e)}", "ERROR")
        import traceback
        log(traceback.format_exc(), "ERROR")
        return None

def verify_signature(data, signature, timestamp, api_key):
    """验证签名"""
    # 将数据转换为JSON字符串，并按键排序
    data_str = json.dumps(data, sort_keys=True)
    
    # 拼接数据、时间戳和密钥
    message = f"{data_str}{timestamp}{api_key}"
    
    # 使用SHA-256生成签名
    calculated_signature = hashlib.sha256(message.encode()).hexdigest()
    
    # 比较签名
    if calculated_signature == signature:
        log(f"签名验证成功")
        return True
    else:
        log(f"签名验证失败", "WARNING")
        return False

def main():
    # API密钥
    api_key = "你的API密钥"
    
    # 离线包文件路径
    file_path = "离线包文件路径.json"
    
    # 加载离线包
    log(f"开始加载离线包: {file_path}")
    package = load_offline_package(file_path)
    log(f"离线包加载成功，包含以下顶级键: {list(package.keys())}")
    
    # 验证包格式版本
    package_format = package.get("metadata", {}).get("package_format", "unknown")
    log(f"离线包格式版本: {package_format}")
    if package_format != "4.0":
        log(f"警告: 离线包格式版本不是预期的4.0，可能需要使用不同的解密方法", "WARNING")
    
    # 提取加密数据
    encrypted_private_key = package["encrypted_private_key"]
    encrypted_dataset = package["dataset"]
    
    # 1. 使用API密钥解密私钥
    log("步骤1: 使用API密钥解密私钥")
    private_key_pem = decrypt_private_key(api_key, encrypted_private_key)
    if not private_key_pem:
        log("解密私钥失败，无法继续", "ERROR")
        return
    
    # 2. 使用解密的私钥解密会话密钥
    log("步骤2: 使用私钥解密会话密钥")
    encrypted_session_key = encrypted_dataset["encrypted_session_key"]
    session_key = decrypt_session_key(encrypted_session_key, private_key_pem)
    if not session_key:
        log("解密会话密钥失败，无法继续", "ERROR")
        return
    
    # 3. 使用会话密钥解密数据集
    log("步骤3: 使用会话密钥解密数据集")
    encrypted_data = encrypted_dataset["encrypted_data"]
    dataset = decrypt_dataset(encrypted_data, session_key)
    if not dataset:
        log("解密数据集失败", "ERROR")
        return
    
    # 4. 验证用户签名
    log("步骤4: 验证用户签名")
    timestamp = encrypted_dataset["timestamp"]
    user_signature = encrypted_dataset["user_signature"]
    verify_signature(dataset, user_signature, timestamp, api_key)
    
    # 保存解密后的数据集
    output_path = "decrypted_dataset.json"
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(dataset, f, indent=2)
    
    log(f"解密完成，数据集已保存到: {output_path}")
    log(f"数据集包含 {len(dataset.keys())} 个顶级键: {list(dataset.keys())}")

if __name__ == "__main__":
    main() 