"""
离线包数据集解密模块

按照加密规范2.0解密离线包数据集，并将数据转换为测试工具兼容的格式
不将解密的数据保存到本地文件，而是保持在内存中，避免被篡改的风险
"""

import os
import json
import base64
import logging
import hashlib
import time
from pathlib import Path
from typing import Dict, List, Any, Optional

# 密码学库
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives import padding, hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding as asym_padding
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

# 设置日志
logger = logging.getLogger(__name__)

def load_offline_package(file_path: str) -> Dict[str, Any]:
    """加载离线包文件"""
    logger.info(f"正在加载离线包: {file_path}")
    with open(file_path, 'r', encoding='utf-8') as f:
        package = json.load(f)
    
    logger.info(f"离线包加载成功，包含键: {', '.join(package.keys())}")
    return package

def decrypt_private_key(encrypted_private_key: Dict[str, str], api_key: str):
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

def decrypt_session_key(encrypted_session_key: str, private_key):
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

def derive_key_with_hkdf(session_key: bytes, salt: bytes, info: bytes, length: int = 32) -> bytes:
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

def decrypt_dataset(encrypted_data: Dict[str, Any], session_key: bytes) -> Dict[str, Any]:
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

def get_dataset_info(dataset: Dict[str, Any], package_metadata: Dict[str, Any] = None) -> Dict[str, str]:
    """
    提取数据集基本信息
    
    Args:
        dataset: 解密后的数据集
        package_metadata: 离线包的原始元数据(可选)
        
    Returns:
        Dict[str, str]: 数据集信息
    """
    info = {}
    
    # 如果提供了原始元数据，优先使用
    if package_metadata:
        # 记录原始元数据，方便排查
        logger.debug(f"原始元数据: {package_metadata}")
        
        # 包格式版本，确保使用正确的值
        package_format = package_metadata.get("package_format", "3.0")
        logger.debug(f"包格式版本: {package_format}")
        
        # 保存原始元数据中的关键信息
        info["名称"] = package_metadata.get("dataset_name", "未知")
        info["版本"] = package_metadata.get("dataset_version", "未知")
        info["created_at"] = package_metadata.get("created_at", "")
        info["expires_at"] = package_metadata.get("expires_at", "")
        
        # 当前时间作为下载时间
        current_time = int(time.time() * 1000)
        
        # 构建完整的元数据信息
        info["metadata"] = {
            "package_format": package_format,
            "dataset_id": str(package_metadata.get("dataset_id", "1")),
            "dataset_name": package_metadata.get("dataset_name", "未知"),
            "dataset_version": package_metadata.get("dataset_version", "未知"),
            "download_time": current_time
        }
    
    # 从数据集本身提取基本信息
    # 如果元数据没有提供，或者某些字段缺失，则从数据集提取
    if "名称" not in info or info["名称"] == "未知":
        info["名称"] = dataset.get("name", "未知")
    
    if "版本" not in info or info["版本"] == "未知":
        info["版本"] = dataset.get("version", "未知")
    
    # 总是从数据集获取描述和记录数
    info["描述"] = dataset.get("description", "无描述")
    info["记录数"] = str(len(dataset.get("data", [])))
    
    # 添加大小信息（估算值）
    info["size"] = len(json.dumps(dataset).encode('utf-8'))
    
    # 记录最终的信息
    logger.debug(f"处理后的数据集信息: {info}")
    
    return info

def convert_to_test_format(dataset: Dict[str, Any]) -> Dict[str, List[str]]:
    """
    将解密后的数据集转换为测试工具兼容的格式
    从数据集中提取text字段，并组织成与test_datasets.py相同的格式
    """
    logger.info("正在将数据集转换为测试格式...")
    
    # 提取所有text字段
    texts = [item.get("text", "") for item in dataset.get("data", [])]
    
    # 按照label进行分组
    categorized_data = {}
    
    # 确定有多少个不同的标签
    unique_labels = set()
    for item in dataset.get("data", []):
        label = item.get("label", 0)
        unique_labels.add(label)
    
    # 为每个标签创建一个类别
    for label in unique_labels:
        label_texts = [item.get("text", "") for item in dataset.get("data", []) if item.get("label") == label]
        category_name = f"类别{label}"
        categorized_data[category_name] = label_texts
    
    # 如果没有分类，就创建一个默认类别
    if not categorized_data:
        categorized_data["默认类别"] = texts
    
    logger.info(f"数据集格式转换完成，共有{len(categorized_data)}个类别")
    return categorized_data

def decrypt_offline_package(file_path: str, api_key: str) -> Dict[str, List[str]]:
    """
    解密离线包并将其转换为测试工具兼容的格式
    
    Args:
        file_path: 离线包文件路径
        api_key: API密钥
    
    Returns:
        解密后并格式化的数据集
    """
    try:
        # 加载离线包
        package = load_offline_package(file_path)
        
        # 获取元数据
        metadata = package.get('metadata', {})
        
        # 解密私钥
        private_key = decrypt_private_key(package['encrypted_private_key'], api_key)
        
        # 解密会话密钥
        session_key = decrypt_session_key(package['dataset']['encrypted_session_key'], private_key)
        
        # 解密数据集
        dataset = decrypt_dataset(package['dataset']['encrypted_data'], session_key)
        
        # 转换为测试工具兼容的格式
        formatted_dataset = convert_to_test_format(dataset)
        
        # 获取数据集信息（用于显示），传递原始元数据
        dataset_info = get_dataset_info(dataset, metadata)
        
        return {
            "formatted_dataset": formatted_dataset,
            "dataset_info": dataset_info,
            "raw_dataset": dataset  # 原始数据集，仅保存在内存中
        }
    
    except Exception as e:
        logger.error(f"解密失败: {e}")
        raise 