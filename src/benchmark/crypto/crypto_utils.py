"""
基础加密工具模块，提供AES和RSA加密/解密功能
"""
import os
import base64
import hashlib
from typing import Tuple, Union, Dict, Any
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives import padding, hashes
from cryptography.hazmat.primitives.asymmetric import rsa, padding as asym_padding
from cryptography.hazmat.primitives.serialization import (
    load_pem_private_key,
    load_pem_public_key,
    Encoding,
    PrivateFormat,
    PublicFormat,
    NoEncryption
)
from cryptography.hazmat.backends import default_backend
from src.utils.logger import setup_logger

# 设置日志记录器
logger = setup_logger("crypto_utils")

class CryptoUtils:
    """基础加密工具类，提供AES和RSA加密/解密功能"""
    
    @staticmethod
    def generate_aes_key(key_size: int = 32) -> bytes:
        """
        生成AES密钥
        
        Args:
            key_size: 密钥大小，单位为字节，默认为32（256位）
            
        Returns:
            bytes: 生成的AES密钥
        """
        return os.urandom(key_size)
    
    @staticmethod
    def aes_encrypt(data: Union[str, bytes], key: bytes) -> Dict[str, str]:
        """
        使用AES-256-CBC模式加密数据
        
        Args:
            data: 要加密的数据，可以是字符串或字节
            key: AES密钥，必须是32字节（256位）
            
        Returns:
            Dict[str, str]: 包含加密数据和IV的字典，格式为：
                {
                    "iv": "Base64编码的IV",
                    "data": "Base64编码的加密数据"
                }
        """
        try:
            # 确保数据是字节类型
            if isinstance(data, str):
                data = data.encode('utf-8')
            
            # 生成随机IV
            iv = os.urandom(16)
            
            # 创建加密器
            cipher = Cipher(algorithms.AES(key), modes.CBC(iv), backend=default_backend())
            encryptor = cipher.encryptor()
            
            # 填充数据
            padder = padding.PKCS7(algorithms.AES.block_size).padder()
            padded_data = padder.update(data) + padder.finalize()
            
            # 加密数据
            encrypted_data = encryptor.update(padded_data) + encryptor.finalize()
            
            # 返回Base64编码的IV和加密数据
            return {
                "iv": base64.b64encode(iv).decode('utf-8'),
                "data": base64.b64encode(encrypted_data).decode('utf-8')
            }
        except Exception as e:
            logger.error(f"AES加密失败: {str(e)}")
            raise
    
    @staticmethod
    def aes_decrypt(encrypted_data: Dict[str, str], key: bytes) -> bytes:
        """
        使用AES-256-CBC模式解密数据
        
        Args:
            encrypted_data: 包含加密数据和IV的字典，格式为：
                {
                    "iv": "Base64编码的IV",
                    "data": "Base64编码的加密数据"
                }
            key: AES密钥，必须是32字节（256位）
            
        Returns:
            bytes: 解密后的数据
        """
        try:
            # 解码IV和加密数据
            iv = base64.b64decode(encrypted_data["iv"])
            ciphertext = base64.b64decode(encrypted_data["data"])
            
            # 创建解密器
            cipher = Cipher(algorithms.AES(key), modes.CBC(iv), backend=default_backend())
            decryptor = cipher.decryptor()
            
            # 解密数据
            padded_data = decryptor.update(ciphertext) + decryptor.finalize()
            
            # 去除填充
            unpadder = padding.PKCS7(algorithms.AES.block_size).unpadder()
            data = unpadder.update(padded_data) + unpadder.finalize()
            
            return data
        except Exception as e:
            logger.error(f"AES解密失败: {str(e)}")
            raise
    
    @staticmethod
    def generate_rsa_key_pair(key_size: int = 2048) -> Tuple[bytes, bytes]:
        """
        生成RSA密钥对
        
        Args:
            key_size: 密钥大小，单位为位，默认为2048
            
        Returns:
            Tuple[bytes, bytes]: (私钥, 公钥)，均为PEM格式
        """
        try:
            # 生成RSA密钥对
            private_key = rsa.generate_private_key(
                public_exponent=65537,
                key_size=key_size,
                backend=default_backend()
            )
            
            # 获取公钥
            public_key = private_key.public_key()
            
            # 将密钥转换为PEM格式
            private_pem = private_key.private_bytes(
                encoding=Encoding.PEM,
                format=PrivateFormat.PKCS8,
                encryption_algorithm=NoEncryption()
            )
            
            public_pem = public_key.public_bytes(
                encoding=Encoding.PEM,
                format=PublicFormat.SubjectPublicKeyInfo
            )
            
            return private_pem, public_pem
        except Exception as e:
            logger.error(f"生成RSA密钥对失败: {str(e)}")
            raise
    
    @staticmethod
    def rsa_encrypt(data: Union[str, bytes], public_key: bytes) -> str:
        """
        使用RSA公钥加密数据
        
        Args:
            data: 要加密的数据，可以是字符串或字节
            public_key: RSA公钥，PEM格式
            
        Returns:
            str: Base64编码的加密数据
        """
        try:
            # 确保数据是字节类型
            if isinstance(data, str):
                data = data.encode('utf-8')
            
            # 加载公钥
            key = load_pem_public_key(public_key, backend=default_backend())
            
            # 加密数据
            encrypted_data = key.encrypt(
                data,
                asym_padding.OAEP(
                    mgf=asym_padding.MGF1(algorithm=hashes.SHA256()),
                    algorithm=hashes.SHA256(),
                    label=None
                )
            )
            
            # 返回Base64编码的加密数据
            return base64.b64encode(encrypted_data).decode('utf-8')
        except Exception as e:
            logger.error(f"RSA加密失败: {str(e)}")
            raise
    
    @staticmethod
    def rsa_decrypt(encrypted_data: str, private_key: bytes) -> bytes:
        """
        使用RSA私钥解密数据
        
        Args:
            encrypted_data: Base64编码的加密数据
            private_key: RSA私钥，PEM格式
            
        Returns:
            bytes: 解密后的数据
        """
        try:
            # 解码加密数据
            ciphertext = base64.b64decode(encrypted_data)
            
            # 加载私钥
            key = load_pem_private_key(private_key, password=None, backend=default_backend())
            
            # 解密数据
            data = key.decrypt(
                ciphertext,
                asym_padding.OAEP(
                    mgf=asym_padding.MGF1(algorithm=hashes.SHA256()),
                    algorithm=hashes.SHA256(),
                    label=None
                )
            )
            
            return data
        except Exception as e:
            logger.error(f"RSA解密失败: {str(e)}")
            raise
    
    @staticmethod
    def generate_hash(data: Union[str, bytes], algorithm: str = 'sha256') -> str:
        """
        生成数据的哈希值
        
        Args:
            data: 要哈希的数据，可以是字符串或字节
            algorithm: 哈希算法，默认为'sha256'
            
        Returns:
            str: 十六进制表示的哈希值
        """
        try:
            # 确保数据是字节类型
            if isinstance(data, str):
                data = data.encode('utf-8')
            
            # 选择哈希算法
            if algorithm.lower() == 'sha256':
                hash_obj = hashlib.sha256(data)
            elif algorithm.lower() == 'sha512':
                hash_obj = hashlib.sha512(data)
            elif algorithm.lower() == 'md5':
                hash_obj = hashlib.md5(data)
            else:
                raise ValueError(f"不支持的哈希算法: {algorithm}")
            
            # 返回十六进制表示的哈希值
            return hash_obj.hexdigest()
        except Exception as e:
            logger.error(f"生成哈希值失败: {str(e)}")
            raise
    
    @staticmethod
    def derive_key_from_password(password: str, salt: bytes = None, iterations: int = 100000) -> Tuple[bytes, bytes]:
        """
        从密码派生密钥
        
        Args:
            password: 密码
            salt: 盐值，如果为None则生成随机盐值
            iterations: 迭代次数，默认为100000
            
        Returns:
            Tuple[bytes, bytes]: (密钥, 盐值)
        """
        try:
            # 如果没有提供盐值，则生成随机盐值
            if salt is None:
                salt = os.urandom(16)
            
            # 从密码派生密钥
            key = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt, iterations, dklen=32)
            
            return key, salt
        except Exception as e:
            logger.error(f"从密码派生密钥失败: {str(e)}")
            raise 