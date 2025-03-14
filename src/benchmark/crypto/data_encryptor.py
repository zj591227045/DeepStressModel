"""
数据加密器模块，用于加密和解密数据
"""
import os
import json
import base64
from typing import Dict, Any, Tuple, Union, Optional
from src.utils.logger import setup_logger
from src.benchmark.crypto.crypto_utils import CryptoUtils
from src.benchmark.crypto.signature_manager import SignatureManager
from src.benchmark.crypto.timestamp_validator import TimestampValidator

# 设置日志记录器
logger = setup_logger("data_encryptor")

class DataEncryptor:
    """数据加密器类，用于加密和解密数据"""
    
    def __init__(self, api_key: str = None, server_public_key: bytes = None):
        """
        初始化数据加密器
        
        Args:
            api_key: API密钥，用于签名
            server_public_key: 服务器公钥，用于加密会话密钥
        """
        self.api_key = api_key
        self.server_public_key = server_public_key
        self.signature_manager = SignatureManager(api_key) if api_key else None
        self.timestamp_validator = TimestampValidator()
    
    def encrypt_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        加密数据
        
        Args:
            data: 要加密的数据
            
        Returns:
            Dict[str, Any]: 加密后的数据包
        """
        try:
            # 生成时间戳
            timestamp = self.timestamp_validator.generate_timestamp()
            
            # 将数据转换为JSON字符串
            data_str = json.dumps(data, ensure_ascii=False)
            
            # 生成AES会话密钥
            session_key = CryptoUtils.generate_aes_key()
            
            # 使用AES加密数据
            encrypted_data = CryptoUtils.aes_encrypt(data_str, session_key)
            
            # 使用服务器公钥加密会话密钥
            encrypted_session_key = None
            if self.server_public_key:
                encrypted_session_key = CryptoUtils.rsa_encrypt(session_key, self.server_public_key)
            
            # 生成用户签名
            user_signature = None
            if self.signature_manager:
                user_signature = self.signature_manager.generate_signature(data, timestamp)
            
            # 构建加密包
            encrypted_package = {
                "encrypted_data": encrypted_data,
                "encrypted_session_key": encrypted_session_key,
                "user_signature": user_signature,
                "timestamp": timestamp,
                "format_version": "2.0"
            }
            
            return encrypted_package
        except Exception as e:
            logger.error(f"加密数据失败: {str(e)}")
            raise
    
    def decrypt_data(self, encrypted_package: Dict[str, Any], private_key: bytes = None) -> Dict[str, Any]:
        """
        解密数据
        
        Args:
            encrypted_package: 加密的数据包
            private_key: 私钥，用于解密会话密钥
            
        Returns:
            Dict[str, Any]: 解密后的数据
        """
        try:
            # 检查格式版本
            format_version = encrypted_package.get("format_version")
            if format_version != "2.0":
                raise ValueError(f"不支持的数据格式版本: {format_version}")
            
            # 提取加密数据
            encrypted_data = encrypted_package.get("encrypted_data")
            if not encrypted_data:
                raise ValueError("加密包中缺少加密数据")
            
            # 提取加密会话密钥
            encrypted_session_key = encrypted_package.get("encrypted_session_key")
            if not encrypted_session_key and private_key:
                raise ValueError("加密包中缺少加密会话密钥")
            
            # 解密会话密钥
            session_key = None
            if encrypted_session_key and private_key:
                session_key = CryptoUtils.rsa_decrypt(encrypted_session_key, private_key)
            
            # 如果没有会话密钥，尝试使用API密钥作为会话密钥
            if not session_key and self.api_key:
                # 从API密钥派生会话密钥
                session_key, _ = CryptoUtils.derive_key_from_password(self.api_key)
            
            if not session_key:
                raise ValueError("无法获取会话密钥")
            
            # 解密数据
            decrypted_data_bytes = CryptoUtils.aes_decrypt(encrypted_data, session_key)
            
            # 将JSON字符串转换为字典
            decrypted_data = json.loads(decrypted_data_bytes.decode('utf-8'))
            
            # 验证用户签名
            if self.signature_manager:
                user_signature = encrypted_package.get("user_signature")
                timestamp = encrypted_package.get("timestamp")
                
                if user_signature and timestamp:
                    if not self.signature_manager.verify_signature(decrypted_data, timestamp, user_signature):
                        logger.warning("用户签名验证失败")
            
            return decrypted_data
        except Exception as e:
            logger.error(f"解密数据失败: {str(e)}")
            raise
    
    def encrypt_dataset(self, dataset: Dict[str, Any]) -> Dict[str, Any]:
        """
        加密数据集
        
        Args:
            dataset: 要加密的数据集
            
        Returns:
            Dict[str, Any]: 加密后的数据集包
        """
        try:
            # 生成时间戳
            timestamp = self.timestamp_validator.generate_timestamp()
            
            # 将数据集转换为JSON字符串
            dataset_str = json.dumps(dataset, ensure_ascii=False)
            
            # 生成AES会话密钥
            session_key = CryptoUtils.generate_aes_key()
            
            # 使用AES加密数据集
            encrypted_data = CryptoUtils.aes_encrypt(dataset_str, session_key)
            
            # 使用服务器公钥加密会话密钥
            encrypted_session_key = None
            if self.server_public_key:
                encrypted_session_key = CryptoUtils.rsa_encrypt(session_key, self.server_public_key)
            
            # 生成用户签名
            user_signature = None
            if self.signature_manager:
                user_signature = self.signature_manager.generate_signature(dataset, timestamp)
            
            # 构建加密包
            encrypted_package = {
                "encrypted_data": encrypted_data,
                "encrypted_session_key": encrypted_session_key,
                "user_signature": user_signature,
                "server_signature": None,  # 服务器签名需要由服务器添加
                "timestamp": timestamp,
                "version": dataset.get("version", "unknown"),
                "format_version": "2.0"
            }
            
            return encrypted_package
        except Exception as e:
            logger.error(f"加密数据集失败: {str(e)}")
            raise
    
    def decrypt_dataset(self, encrypted_package: Dict[str, Any], private_key: bytes = None) -> Dict[str, Any]:
        """
        解密数据集
        
        Args:
            encrypted_package: 加密的数据集包
            private_key: 私钥，用于解密会话密钥
            
        Returns:
            Dict[str, Any]: 解密后的数据集
        """
        try:
            # 检查格式版本
            format_version = encrypted_package.get("format_version")
            if format_version != "2.0":
                raise ValueError(f"不支持的数据集格式版本: {format_version}")
            
            # 提取加密数据
            encrypted_data = encrypted_package.get("encrypted_data")
            if not encrypted_data:
                raise ValueError("加密包中缺少加密数据")
            
            # 提取加密会话密钥
            encrypted_session_key = encrypted_package.get("encrypted_session_key")
            if not encrypted_session_key and private_key:
                raise ValueError("加密包中缺少加密会话密钥")
            
            # 解密会话密钥
            session_key = None
            if encrypted_session_key and private_key:
                session_key = CryptoUtils.rsa_decrypt(encrypted_session_key, private_key)
            
            # 如果没有会话密钥，尝试使用API密钥作为会话密钥
            if not session_key and self.api_key:
                # 从API密钥派生会话密钥
                session_key, _ = CryptoUtils.derive_key_from_password(self.api_key)
            
            if not session_key:
                raise ValueError("无法获取会话密钥")
            
            # 解密数据
            decrypted_data_bytes = CryptoUtils.aes_decrypt(encrypted_data, session_key)
            
            # 将JSON字符串转换为字典
            dataset = json.loads(decrypted_data_bytes.decode('utf-8'))
            
            # 验证用户签名
            if self.signature_manager:
                user_signature = encrypted_package.get("user_signature")
                timestamp = encrypted_package.get("timestamp")
                
                if user_signature and timestamp:
                    if not self.signature_manager.verify_signature(dataset, timestamp, user_signature):
                        logger.warning("用户签名验证失败")
            
            return dataset
        except Exception as e:
            logger.error(f"解密数据集失败: {str(e)}")
            raise
    
    def encrypt_result(self, result: Dict[str, Any]) -> Dict[str, Any]:
        """
        加密测试结果
        
        Args:
            result: 要加密的测试结果
            
        Returns:
            Dict[str, Any]: 加密后的测试结果包
        """
        try:
            # 生成时间戳
            timestamp = self.timestamp_validator.generate_timestamp()
            
            # 将测试结果转换为JSON字符串
            result_str = json.dumps(result, ensure_ascii=False)
            
            # 生成AES会话密钥
            session_key = CryptoUtils.generate_aes_key()
            
            # 使用AES加密测试结果
            encrypted_data = CryptoUtils.aes_encrypt(result_str, session_key)
            
            # 使用服务器公钥加密会话密钥
            encrypted_session_key = None
            if self.server_public_key:
                encrypted_session_key = CryptoUtils.rsa_encrypt(session_key, self.server_public_key)
            
            # 生成用户签名
            user_signature = None
            if self.signature_manager:
                user_signature = self.signature_manager.generate_signature(result, timestamp)
            
            # 构建加密包
            encrypted_package = {
                "encrypted_data": encrypted_data,
                "encrypted_session_key": encrypted_session_key,
                "user_signature": user_signature,
                "timestamp": timestamp,
                "format_version": "2.0"
            }
            
            return encrypted_package
        except Exception as e:
            logger.error(f"加密测试结果失败: {str(e)}")
            raise
    
    def decrypt_result(self, encrypted_package: Dict[str, Any], private_key: bytes = None) -> Dict[str, Any]:
        """
        解密测试结果
        
        Args:
            encrypted_package: 加密的测试结果包
            private_key: 私钥，用于解密会话密钥
            
        Returns:
            Dict[str, Any]: 解密后的测试结果
        """
        try:
            # 检查格式版本
            format_version = encrypted_package.get("format_version")
            if format_version != "2.0":
                raise ValueError(f"不支持的测试结果格式版本: {format_version}")
            
            # 提取加密数据
            encrypted_data = encrypted_package.get("encrypted_data")
            if not encrypted_data:
                raise ValueError("加密包中缺少加密数据")
            
            # 提取加密会话密钥
            encrypted_session_key = encrypted_package.get("encrypted_session_key")
            if not encrypted_session_key and private_key:
                raise ValueError("加密包中缺少加密会话密钥")
            
            # 解密会话密钥
            session_key = None
            if encrypted_session_key and private_key:
                session_key = CryptoUtils.rsa_decrypt(encrypted_session_key, private_key)
            
            # 如果没有会话密钥，尝试使用API密钥作为会话密钥
            if not session_key and self.api_key:
                # 从API密钥派生会话密钥
                session_key, _ = CryptoUtils.derive_key_from_password(self.api_key)
            
            if not session_key:
                raise ValueError("无法获取会话密钥")
            
            # 解密数据
            decrypted_data_bytes = CryptoUtils.aes_decrypt(encrypted_data, session_key)
            
            # 将JSON字符串转换为字典
            result = json.loads(decrypted_data_bytes.decode('utf-8'))
            
            # 验证用户签名
            if self.signature_manager:
                user_signature = encrypted_package.get("user_signature")
                timestamp = encrypted_package.get("timestamp")
                
                if user_signature and timestamp:
                    if not self.signature_manager.verify_signature(result, timestamp, user_signature):
                        logger.warning("用户签名验证失败")
            
            return result
        except Exception as e:
            logger.error(f"解密测试结果失败: {str(e)}")
            raise 