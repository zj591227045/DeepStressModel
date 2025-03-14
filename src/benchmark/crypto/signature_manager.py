"""
签名管理器模块，用于生成和验证签名
"""
import json
import hashlib
import hmac
from typing import Dict, Any, Union, Tuple, Optional
from src.utils.logger import setup_logger
from src.benchmark.crypto.crypto_utils import CryptoUtils

# 设置日志记录器
logger = setup_logger("signature_manager")

class SignatureManager:
    """签名管理器类，用于生成和验证签名"""
    
    def __init__(self, secret_key: str = None):
        """
        初始化签名管理器
        
        Args:
            secret_key: 密钥，用于生成和验证签名，如果为None则使用HMAC算法
        """
        self.secret_key = secret_key.encode('utf-8') if secret_key else None
    
    def generate_signature(self, data: Union[Dict[str, Any], str, bytes], timestamp: str) -> str:
        """
        生成签名
        
        Args:
            data: 要签名的数据，可以是字典、字符串或字节
            timestamp: 时间戳或时间戳:nonce组合，毫秒级Unix时间戳
            
        Returns:
            str: 生成的签名
        """
        try:
            # 将数据转换为JSON字符串（如果是字典）
            if isinstance(data, dict):
                data_str = json.dumps(data, sort_keys=True, ensure_ascii=False)
            elif isinstance(data, str):
                data_str = data
            elif isinstance(data, bytes):
                data_str = data.decode('utf-8')
            else:
                raise ValueError(f"不支持的数据类型: {type(data)}")
            
            # 拼接数据和时间戳
            message = f"{data_str}{timestamp}"
            
            # 使用密钥生成签名
            if self.secret_key:
                # 使用HMAC-SHA256算法
                signature = hmac.new(
                    self.secret_key,
                    message.encode('utf-8'),
                    hashlib.sha256
                ).hexdigest()
            else:
                # 使用普通SHA256算法
                signature = hashlib.sha256(message.encode('utf-8')).hexdigest()
            
            return signature
        except Exception as e:
            logger.error(f"生成签名失败: {str(e)}")
            raise
    
    def verify_signature(self, data: Union[Dict[str, Any], str, bytes], timestamp: str, signature: str) -> bool:
        """
        验证签名
        
        Args:
            data: 要验证的数据，可以是字典、字符串或字节
            timestamp: 时间戳，毫秒级Unix时间戳
            signature: 要验证的签名
            
        Returns:
            bool: 签名是否有效
        """
        try:
            # 生成签名
            expected_signature = self.generate_signature(data, timestamp)
            
            # 比较签名
            return hmac.compare_digest(expected_signature, signature)
        except Exception as e:
            logger.error(f"验证签名失败: {str(e)}")
            return False
    
    def sign_data(self, data: Dict[str, Any], timestamp: str) -> Dict[str, Any]:
        """
        签名数据，并将签名添加到数据中
        
        Args:
            data: 要签名的数据
            timestamp: 时间戳，毫秒级Unix时间戳
            
        Returns:
            Dict[str, Any]: 包含签名的数据
        """
        try:
            # 生成签名
            signature = self.generate_signature(data, timestamp)
            
            # 创建新的数据字典，包含原始数据和签名
            signed_data = data.copy()
            signed_data['signature'] = signature
            signed_data['timestamp'] = timestamp
            
            return signed_data
        except Exception as e:
            logger.error(f"签名数据失败: {str(e)}")
            raise
    
    def verify_signed_data(self, signed_data: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
        """
        验证已签名的数据
        
        Args:
            signed_data: 包含签名的数据
            
        Returns:
            Tuple[bool, Optional[str]]: (是否有效, 错误信息)
        """
        try:
            # 提取签名和时间戳
            signature = signed_data.get('signature')
            timestamp = signed_data.get('timestamp')
            
            if not signature:
                return False, "数据中缺少签名"
            
            if not timestamp:
                return False, "数据中缺少时间戳"
            
            # 创建不包含签名的数据副本
            data_copy = signed_data.copy()
            data_copy.pop('signature', None)
            
            # 验证签名
            if not self.verify_signature(data_copy, timestamp, signature):
                return False, "签名验证失败"
            
            return True, None
        except Exception as e:
            logger.error(f"验证已签名数据失败: {str(e)}")
            return False, f"验证已签名数据时发生错误: {str(e)}"
    
    @staticmethod
    def generate_api_key() -> str:
        """
        生成API密钥
        
        Returns:
            str: 生成的API密钥
        """
        try:
            # 生成32字节的随机数据
            random_bytes = CryptoUtils.generate_aes_key(32)
            
            # 转换为十六进制字符串
            api_key = random_bytes.hex()
            
            return api_key
        except Exception as e:
            logger.error(f"生成API密钥失败: {str(e)}")
            raise 