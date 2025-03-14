"""
时间戳验证器模块，用于生成和验证时间戳
"""
import time
from typing import Tuple, Optional
from src.utils.logger import setup_logger

# 设置日志记录器
logger = setup_logger("timestamp_validator")

class TimestampValidator:
    """时间戳验证器类，用于生成和验证时间戳"""
    
    def __init__(self, validity_period: int = 300):
        """
        初始化时间戳验证器
        
        Args:
            validity_period: 时间戳有效期，单位为秒，默认为300秒（5分钟）
        """
        self.validity_period = validity_period
        self.time_offset = 0  # 时间偏移量（毫秒）
        self.last_sync_time = 0  # 上次同步时间
        self.sync_interval = 3600  # 同步间隔（秒）
    
    def generate_timestamp(self) -> str:
        """
        生成当前时间戳，考虑时间偏移
        
        Returns:
            str: 当前时间戳，毫秒级Unix时间戳
        """
        current_time = int(time.time() * 1000)
        adjusted_time = current_time + self.time_offset
        return str(adjusted_time)
    
    def validate_timestamp(self, timestamp: str) -> Tuple[bool, Optional[str]]:
        """
        验证时间戳是否有效
        
        Args:
            timestamp: 要验证的时间戳，毫秒级Unix时间戳
            
        Returns:
            Tuple[bool, Optional[str]]: (是否有效, 错误信息)
        """
        try:
            # 将时间戳转换为整数
            ts = int(timestamp)
            
            # 获取当前时间戳
            current_ts = int(time.time() * 1000)
            
            # 计算时间差（毫秒）
            time_diff = abs(current_ts - ts)
            
            # 转换为秒
            time_diff_seconds = time_diff / 1000
            
            # 检查时间戳是否在有效期内
            if time_diff_seconds > self.validity_period:
                return False, f"时间戳已过期，时间差: {time_diff_seconds:.2f}秒，超过有效期: {self.validity_period}秒"
            
            # 检查时间戳是否来自未来（允许一定的时钟偏差）
            if ts > current_ts + 10000:  # 允许10秒的时钟偏差
                return False, f"时间戳来自未来，时间差: {(ts - current_ts) / 1000:.2f}秒"
            
            return True, None
        except ValueError:
            return False, f"无效的时间戳格式: {timestamp}"
        except Exception as e:
            logger.error(f"验证时间戳失败: {str(e)}")
            return False, f"验证时间戳时发生错误: {str(e)}"
    
    def is_timestamp_valid(self, timestamp: str) -> bool:
        """
        检查时间戳是否有效（简化版本）
        
        Args:
            timestamp: 要验证的时间戳，毫秒级Unix时间戳
            
        Returns:
            bool: 时间戳是否有效
        """
        valid, _ = self.validate_timestamp(timestamp)
        return valid
    
    def get_timestamp_age(self, timestamp: str) -> Optional[float]:
        """
        获取时间戳的年龄（秒）
        
        Args:
            timestamp: 时间戳，毫秒级Unix时间戳
            
        Returns:
            Optional[float]: 时间戳的年龄（秒），如果时间戳无效则返回None
        """
        try:
            # 将时间戳转换为整数
            ts = int(timestamp)
            
            # 获取当前时间戳
            current_ts = int(time.time() * 1000)
            
            # 计算时间差（毫秒）并转换为秒
            return (current_ts - ts) / 1000
        except ValueError:
            logger.error(f"无效的时间戳格式: {timestamp}")
            return None
        except Exception as e:
            logger.error(f"获取时间戳年龄失败: {str(e)}")
            return None
    
    def update_time_offset(self, server_time: int) -> None:
        """
        更新时间偏移量
        
        Args:
            server_time: 服务器时间戳（毫秒）
        """
        current_time = int(time.time() * 1000)
        self.time_offset = server_time - current_time
        self.last_sync_time = current_time
        logger.info(f"更新时间偏移量: {self.time_offset}毫秒")
    
    def should_sync_time(self) -> bool:
        """
        检查是否应该同步时间
        
        Returns:
            bool: 是否应该同步时间
        """
        current_time = int(time.time() * 1000)
        return (current_time - self.last_sync_time) / 1000 > self.sync_interval 