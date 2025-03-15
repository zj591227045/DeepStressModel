"""
数据集处理模块，负责数据集的加载、解密和处理
"""
import os
import json
import time
from datetime import datetime
from typing import Dict, List, Optional, Any
from src.utils.logger import setup_logger
from src.data.dataset_manager import dataset_manager

# 设置日志记录器
logger = setup_logger("dataset_handler")

def load_dataset(dataset_path: str) -> Dict[str, Any]:
    """
    加载数据集文件
    
    Args:
        dataset_path: 数据集文件路径
        
    Returns:
        Dict[str, Any]: 加载的数据集
    """
    try:
        logger.info(f"正在加载数据集: {dataset_path}")
        
        # 检查文件是否存在
        if not os.path.exists(dataset_path):
            logger.error(f"数据集文件不存在: {dataset_path}")
            return None
        
        # 尝试读取JSON文件
        with open(dataset_path, 'r', encoding='utf-8') as f:
            dataset = json.load(f)
        
        logger.info(f"数据集加载成功: {dataset_path}")
        return dataset
    except Exception as e:
        logger.error(f"加载数据集失败: {str(e)}")
        return None

def validate_dataset_format(dataset: Dict[str, Any]) -> bool:
    """
    验证数据集格式
    
    Args:
        dataset: 数据集
        
    Returns:
        bool: 格式是否有效
    """
    # 检查必要字段
    required_fields = ["version", "name", "data", "metadata"]
    for field in required_fields:
        if field not in dataset:
            logger.error(f"数据集缺少必要字段: {field}")
            return False
    
    # 检查数据字段
    if not isinstance(dataset["data"], list) or len(dataset["data"]) == 0:
        logger.error("数据集的data字段必须是非空列表")
        return False
    
    return True

def extract_dataset_info(dataset: Dict[str, Any]) -> Dict[str, Any]:
    """
    提取数据集信息
    
    Args:
        dataset: 数据集
        
    Returns:
        Dict[str, Any]: 数据集信息
    """
    return {
        "name": dataset.get("name", "未知数据集"),
        "version": dataset.get("version", "未知版本"),
        "description": dataset.get("description", ""),
        "item_count": len(dataset.get("data", [])),
        "created_at": dataset.get("metadata", {}).get("created_at", ""),
        "published_at": dataset.get("metadata", {}).get("published_at", "")
    }

def get_dataset_info(dataset, dataset_info) -> Dict[str, Any]:
    """
    获取当前数据集信息
    
    Args:
        dataset: 数据集对象
        dataset_info: 数据集信息对象
        
    Returns:
        Dict[str, Any]: 数据集信息
    """
    try:
        # 如果是离线数据集格式，从数据集管理器获取信息
        if isinstance(dataset, dict) and dataset.get("version") == "offline":
            # 获取离线数据集信息
            offline_info = dataset_manager.get_offline_dataset_info()
            if offline_info:
                # 确保返回的元数据包含正确的字段
                metadata = offline_info.get("metadata", {})
                
                return {
                    'metadata': metadata,
                    'size': offline_info.get("size", 0),
                    '名称': metadata.get('dataset_name', '未知'),
                    '版本': metadata.get('dataset_version', '未知'),
                    '描述': offline_info.get('描述', '无描述'),
                    '记录数': offline_info.get('记录数', '0')
                }
        
        # 如果是原始数据集格式
        if isinstance(dataset, dict) and 'metadata' in dataset:
            return {
                'metadata': dataset['metadata'],
                'size': len(str(dataset)),
                'test_cases': dataset.get('test_cases', []),
                'description': dataset.get('description', '无描述')
            }
        
        # 如果是解密后的数据集格式
        return {
            'metadata': {
                'dataset_name': dataset_info.get('名称', '未知'),
                'dataset_version': dataset_info.get('版本', '未知'),
                'package_format': '3.0',
                'download_time': int(time.time() * 1000)
            },
            'size': dataset_info.get('size', 0),
            'test_cases': dataset.get('test_cases', []),
            'description': dataset.get('description', '无描述')
        }
    except Exception as e:
        logger.error(f"获取数据集信息失败: {str(e)}")
        return {
            'metadata': {
                'dataset_name': '未知',
                'dataset_version': '未知',
                'package_format': '未知',
                'download_time': 0
            },
            'size': 0,
            'test_cases': [],
            'description': '获取数据集信息失败'
        }

def is_dataset_loaded(dataset, dataset_updated: bool) -> bool:
    """
    检查数据集是否已加载
    
    Args:
        dataset: 数据集对象
        dataset_updated: 数据集是否已更新标志
        
    Returns:
        bool: 数据集是否已加载
    """
    # 检查离线数据集是否已加载
    if dataset_manager.get_offline_dataset_data() is not None:
        logger.info("检测到通过dataset_manager加载的数据集")
        return True
    
    # 只检查dataset，不再回退到标准测试数据集
    return dataset is not None and dataset_updated

def prepare_test_data() -> List[Dict[str, Any]]:
    """
    准备测试数据
    
    Returns:
        List[Dict[str, Any]]: 测试数据
    """
    # 首先尝试从dataset_manager获取数据
    offline_data = dataset_manager.get_offline_dataset_data()
    if offline_data and isinstance(offline_data, list) and len(offline_data) > 0:
        logger.info(f"从dataset_manager获取到 {len(offline_data)} 条测试数据")
        return offline_data
    
    # 不再生成模拟测试数据，如果没有有效数据，就返回空列表
    logger.error("未找到有效测试数据，请先获取离线数据集")
    return []

async def load_offline_package(package_path: str, api_key: str) -> bool:
    """
    加载并解密离线包
    
    Args:
        package_path: 离线包文件路径
        api_key: API密钥，如果未提供则使用当前配置的API密钥
        
    Returns:
        bool: 加载是否成功
    """
    try:
        # 检查API密钥
        if not api_key:
            logger.error("API密钥未设置，请先设置API密钥")
            return False
            
        logger.debug(f"使用API密钥进行解密: {api_key[:4]}...")
        
        # 使用数据集管理器解密离线包
        success = dataset_manager.load_offline_package(package_path, api_key)
        
        if success:
            # 离线包解密并加载成功
            # 更新数据集信息
            dataset_info = dataset_manager.get_offline_dataset_info()
            if dataset_info:
                updated_info = {
                    "version": f"offline-{int(time.time())}",
                    "created_at": datetime.now().isoformat(),
                    "file_name": os.path.basename(package_path),
                    "名称": dataset_info.get("名称", "未知"),
                    "版本": dataset_info.get("版本", "未知"),
                    "描述": dataset_info.get("描述", "无描述"),
                    "记录数": dataset_info.get("记录数", "0")
                }
                
                logger.debug(f"更新数据集信息: {updated_info}")
            
            logger.info("离线包解密并加载成功")
            return True
        else:
            logger.error("离线包解密或加载失败")
            return False
            
    except Exception as e:
        logger.error(f"加载离线包失败: {str(e)}")
        return False 