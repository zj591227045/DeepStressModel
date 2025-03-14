#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
DeepStressModel 离线包解密工具
基于修订版加密规范2.0

解密流程:
1. 使用API密钥解密RSA私钥
2. 使用RSA私钥解密会话密钥
3. 使用会话密钥通过HKDF派生AES密钥来解密数据集
"""

import os
import json
import base64
import hashlib
import logging
import argparse
from pathlib import Path
from getpass import getpass

# 密码学库
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives import padding, hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding as asym_padding
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

# 设置日志
logging.basicConfig(
    level=logging.INFO,
    format='[%(levelname)s] %(message)s'
)
logger = logging.getLogger(__name__)

def load_offline_package(file_path):
    """加载离线包文件"""
    logger.info(f"正在加载离线包: {file_path}")
    with open(file_path, 'r', encoding='utf-8') as f:
        package = json.load(f)
    
    logger.info(f"离线包加载成功，包含键: {', '.join(package.keys())}")
    return package

def decrypt_private_key(encrypted_private_key, api_key):
    """使用API密钥解密RSA私钥"""
    logger.info("开始解密私钥...")
    
    # 解码salt、iv和加密数据
    salt = base64.b64decode(encrypted_private_key['salt'])
    iv = base64.b64decode(encrypted_private_key['iv'])
    encrypted_data = base64.b64decode(encrypted_private_key['data'])
    
    logger.debug(f"Salt长度: {len(salt)}字节, IV长度: {len(iv)}字节, 加密数据长度: {len(encrypted_data)}字节")
    
    # 使用PBKDF2派生密钥
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=100000
    )
    key = kdf.derive(api_key.encode('utf-8'))
    logger.debug(f"派生密钥长度: {len(key)}字节")
    
    # 使用AES-CBC解密
    cipher = Cipher(algorithms.AES(key), modes.CBC(iv))
    decryptor = cipher.decryptor()
    padded_private_key = decryptor.update(encrypted_data) + decryptor.finalize()
    
    # 去除PKCS7填充
    unpadder = padding.PKCS7(algorithms.AES.block_size).unpadder()
    private_key_pem = unpadder.update(padded_private_key) + unpadder.finalize()
    
    # 加载RSA私钥
    private_key = serialization.load_pem_private_key(
        private_key_pem,
        password=None
    )
    
    logger.info("私钥解密成功")
    return private_key

def decrypt_session_key(encrypted_session_key, private_key):
    """使用RSA私钥解密会话密钥"""
    logger.info("开始解密会话密钥...")
    
    # 解码加密的会话密钥
    encrypted_key = base64.b64decode(encrypted_session_key)
    logger.debug(f"加密会话密钥长度: {len(encrypted_key)}字节")
    
    # 尝试使用PKCS1v15填充解密
    try:
        session_key = private_key.decrypt(
            encrypted_key,
            asym_padding.PKCS1v15()
        )
        logger.debug("使用PKCS1v15填充成功解密会话密钥")
    except Exception as e:
        logger.debug(f"PKCS1v15解密失败: {e}")
        # 尝试使用OAEP填充解密
        try:
            session_key = private_key.decrypt(
                encrypted_key,
                asym_padding.OAEP(
                    mgf=asym_padding.MGF1(algorithm=hashes.SHA256()),
                    algorithm=hashes.SHA256(),
                    label=None
                )
            )
            logger.debug("使用OAEP填充成功解密会话密钥")
        except Exception as e2:
            logger.error(f"OAEP解密也失败: {e2}")
            raise Exception("会话密钥解密失败") from e2
    
    logger.info(f"会话密钥解密成功，长度: {len(session_key)}字节")
    return session_key

def derive_key_with_hkdf(session_key, salt, info, length=32):
    """使用HKDF从会话密钥派生AES密钥"""
    logger.info(f"使用HKDF从会话密钥派生AES密钥，目标长度: {length}字节")
    
    hkdf = HKDF(
        algorithm=hashes.SHA256(),
        length=length,
        salt=salt,
        info=info
    )
    
    derived_key = hkdf.derive(session_key)
    logger.debug(f"派生密钥长度: {len(derived_key)}字节")
    return derived_key

def decrypt_dataset(encrypted_data, session_key):
    """使用会话密钥解密数据集"""
    logger.info("开始解密数据集...")
    
    # 解析加密数据结构
    algorithm = encrypted_data.get('algorithm')
    logger.info(f"加密算法: {algorithm}")
    
    # 获取密钥派生信息
    key_derivation = encrypted_data.get('key_derivation', {})
    method = key_derivation.get('method')
    salt = base64.b64decode(key_derivation.get('salt', ''))
    info = key_derivation.get('info', '').encode('utf-8')
    
    logger.info(f"密钥派生方法: {method}, 信息: {info.decode('utf-8')}")
    
    # 解码IV和加密数据
    iv = base64.b64decode(encrypted_data.get('iv', ''))
    data = base64.b64decode(encrypted_data.get('data', ''))
    
    logger.debug(f"IV长度: {len(iv)}字节, 加密数据长度: {len(data)}字节")
    
    # 使用HKDF派生AES密钥
    if method == "HKDF-SHA256":
        key = derive_key_with_hkdf(session_key, salt, info)
    else:
        raise ValueError(f"不支持的密钥派生方法: {method}")
    
    # 使用AES-CBC解密
    if algorithm == "AES-256-CBC-PKCS7":
        cipher = Cipher(algorithms.AES(key), modes.CBC(iv))
        decryptor = cipher.decryptor()
        padded_data = decryptor.update(data) + decryptor.finalize()
        
        # 去除PKCS7填充
        unpadder = padding.PKCS7(algorithms.AES.block_size).unpadder()
        decrypted_data = unpadder.update(padded_data) + unpadder.finalize()
        
        # 解析JSON数据
        dataset = json.loads(decrypted_data.decode('utf-8'))
        logger.info("数据集解密成功")
        return dataset
    else:
        raise ValueError(f"不支持的加密算法: {algorithm}")

def verify_signature(data, signature, public_key):
    """验证数据签名"""
    logger.info("验证数据签名...")
    # 这里需要实现签名验证逻辑
    # 由于当前没有服务器公钥，所以跳过验证
    logger.warning("签名验证被跳过，无法验证数据完整性")
    return True

def main():
    parser = argparse.ArgumentParser(description='DeepStressModel 离线包解密工具')
    parser.add_argument('file', help='离线包文件路径')
    parser.add_argument('--output', '-o', help='输出解密数据的文件路径')
    parser.add_argument('--debug', action='store_true', help='启用调试日志')
    parser.add_argument('--api-key', help='API密钥 (不提供则会提示输入)')
    
    args = parser.parse_args()
    
    if args.debug:
        logger.setLevel(logging.DEBUG)
    
    # 加载离线包
    package = load_offline_package(args.file)
    
    # 获取API密钥
    api_key = args.api_key
    if not api_key:
        api_key = getpass("请输入API密钥: ")
    
    try:
        # 解密私钥
        private_key = decrypt_private_key(package['encrypted_private_key'], api_key)
        
        # 解密会话密钥
        session_key = decrypt_session_key(package['dataset']['encrypted_session_key'], private_key)
        
        # 解密数据集
        dataset = decrypt_dataset(package['dataset']['encrypted_data'], session_key)
        
        # 确定输出文件路径
        if args.output:
            output_file = args.output
        else:
            input_file = Path(args.file)
            output_file = input_file.with_suffix('.decrypted.json')
        
        # 保存解密的数据
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(dataset, f, indent=2, ensure_ascii=False)
        
        logger.info(f"解密成功! 数据已保存到: {output_file}")
        
    except Exception as e:
        logger.error(f"解密失败: {e}")
        return 1
    
    return 0

if __name__ == "__main__":
    exit(main()) 