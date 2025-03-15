"""
结果处理模块，负责保存和处理测试结果
"""
import os
import json
import time
from datetime import datetime
from typing import Dict, Any, Optional
from src.utils.logger import setup_logger

# 设置日志记录器
logger = setup_logger("result_handler")

class ResultHandler:
    """结果处理类，用于保存和处理测试结果"""
    
    def __init__(self, result_dir=None):
        """
        初始化结果处理器
        
        Args:
            result_dir: 结果保存目录
        """
        # 如果没有指定结果目录，使用默认目录
        if not result_dir:
            self.result_dir = os.path.join(os.path.expanduser("~"), ".deepstressmodel", "benchmark_results")
        else:
            self.result_dir = result_dir
        
        # 确保目录存在
        os.makedirs(self.result_dir, exist_ok=True)
    
    def save_result(self, result: Dict[str, Any]) -> str:
        """
        保存测试结果
        
        Args:
            result: 测试结果
            
        Returns:
            str: 结果文件路径
        """
        try:
            # 生成结果文件名
            timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
            result_file = f"benchmark_result_{timestamp}.json"
            result_path = os.path.join(self.result_dir, result_file)
            
            # 在保存前记录硬件信息
            if "hardware_info" in result:
                logger.info("保存结果文件中包含以下硬件信息:")
                hardware_info = result["hardware_info"]
                logger.info(f"CPU: {hardware_info.get('cpu', '未知')}")
                logger.info(f"内存: {hardware_info.get('memory', '未知')}")
                logger.info(f"系统: {hardware_info.get('system', '未知')}")
                logger.info(f"GPU: {hardware_info.get('gpu', '未知')}")
                logger.info(f"硬件ID: {hardware_info.get('id', '未知')}")
            else:
                logger.warning("结果中未包含硬件信息！")
            
            # 保存结果
            with open(result_path, 'w', encoding='utf-8') as f:
                json.dump(result, f, ensure_ascii=False, indent=2)
            
            logger.info(f"测试结果已保存到: {result_path}")
            return result_path
        except Exception as e:
            logger.error(f"保存测试结果失败: {str(e)}")
            return ""
    
    def load_result(self, result_path: str) -> Optional[Dict[str, Any]]:
        """
        加载测试结果
        
        Args:
            result_path: 结果文件路径
            
        Returns:
            Optional[Dict[str, Any]]: 测试结果或None（失败时）
        """
        try:
            if not os.path.exists(result_path):
                logger.error(f"结果文件不存在: {result_path}")
                return None
            
            # 读取结果文件
            with open(result_path, 'r', encoding='utf-8') as f:
                result = json.load(f)
            
            logger.info(f"成功加载测试结果: {result_path}")
            return result
        except Exception as e:
            logger.error(f"加载测试结果失败: {str(e)}")
            return None
    
    def update_result(self, result_path: str, updates: Dict[str, Any]) -> bool:
        """
        更新测试结果
        
        Args:
            result_path: 结果文件路径
            updates: 要更新的字段
            
        Returns:
            bool: 更新是否成功
        """
        try:
            # 加载结果
            result = self.load_result(result_path)
            if not result:
                return False
            
            # 更新字段
            result.update(updates)
            
            # 保存结果
            with open(result_path, 'w', encoding='utf-8') as f:
                json.dump(result, f, ensure_ascii=False, indent=2)
            
            logger.info(f"成功更新测试结果: {result_path}")
            return True
        except Exception as e:
            logger.error(f"更新测试结果失败: {str(e)}")
            return False


# 创建一个全局的结果处理器实例
result_handler = ResultHandler() 