"""
数据集管理器模块，负责管理测试数据集
"""
from typing import Dict, List, Any
from src.data.test_datasets import DATASETS
from src.utils.logger import setup_logger

logger = setup_logger("dataset_manager")

class DatasetManager:
    """数据集管理器类"""
    
    def __init__(self):
        """初始化数据集管理器"""
        self.datasets = DATASETS.copy()
        logger.info(f"数据集管理器初始化完成，加载了 {len(self.datasets)} 个数据集")
    
    def get_all_datasets(self) -> Dict[str, List[str]]:
        """获取所有数据集"""
        return self.datasets
    
    def get_dataset(self, name: str) -> List[str]:
        """获取指定名称的数据集"""
        if name in self.datasets:
            return self.datasets[name]
        logger.warning(f"请求的数据集 '{name}' 不存在")
        return []
    
    def add_dataset(self, name: str, prompts: List[str]) -> bool:
        """添加新数据集"""
        if name in self.datasets:
            logger.warning(f"数据集 '{name}' 已存在，无法添加")
            return False
        
        if not prompts:
            logger.warning(f"无法添加空数据集 '{name}'")
            return False
        
        self.datasets[name] = prompts
        logger.info(f"已添加数据集 '{name}'，包含 {len(prompts)} 个提示")
        return True
    
    def update_dataset(self, name: str, prompts: List[str]) -> bool:
        """更新数据集"""
        if name not in self.datasets:
            logger.warning(f"数据集 '{name}' 不存在，无法更新")
            return False
        
        if not prompts:
            logger.warning(f"无法将数据集 '{name}' 更新为空数据集")
            return False
        
        self.datasets[name] = prompts
        logger.info(f"已更新数据集 '{name}'，现包含 {len(prompts)} 个提示")
        return True
    
    def delete_dataset(self, name: str) -> bool:
        """删除数据集"""
        if name not in self.datasets:
            logger.warning(f"数据集 '{name}' 不存在，无法删除")
            return False
        
        del self.datasets[name]
        logger.info(f"已删除数据集 '{name}'")
        return True
    
    def get_dataset_names(self) -> List[str]:
        """获取所有数据集名称"""
        return list(self.datasets.keys())
    
    def get_dataset_count(self) -> int:
        """获取数据集数量"""
        return len(self.datasets)
    
    def get_prompt_count(self, name: str) -> int:
        """获取指定数据集的提示数量"""
        if name in self.datasets:
            return len(self.datasets[name])
        return 0

# 创建全局实例
dataset_manager = DatasetManager() 