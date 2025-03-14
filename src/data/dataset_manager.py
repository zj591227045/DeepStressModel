"""
数据集管理器模块，负责管理测试数据集
"""
from typing import Dict, List, Any, Optional
from src.data.test_datasets import DATASETS
from src.data.offline_dataset import decrypt_offline_package
from src.utils.logger import setup_logger

logger = setup_logger("dataset_manager")

class DatasetManager:
    """数据集管理器类"""
    
    def __init__(self):
        """初始化数据集管理器"""
        self.datasets = DATASETS.copy()
        self.original_datasets = DATASETS.copy()  # 保存原始数据集
        self.offline_dataset_info = None  # 当前加载的离线数据集信息
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
    
    def load_offline_package(self, file_path: str, api_key: str) -> bool:
        """
        加载并解密离线包数据集
        
        Args:
            file_path: 离线包文件路径
            api_key: API密钥
            
        Returns:
            bool: 加载是否成功
        """
        try:
            logger.info(f"开始加载离线包数据集: {file_path}")
            
            # 解密离线包
            result = decrypt_offline_package(file_path, api_key)
            
            # 获取格式化后的数据集和数据集信息
            formatted_dataset = result["formatted_dataset"]
            dataset_info = result["dataset_info"]
            
            # 保存原始数据集
            self.original_datasets = self.datasets.copy()
            
            # 替换当前数据集
            self.datasets = formatted_dataset
            
            # 保存数据集信息
            self.offline_dataset_info = dataset_info
            
            logger.info(f"离线包数据集加载成功，包含 {len(formatted_dataset)} 个类别")
            return True
        except Exception as e:
            logger.error(f"加载离线包数据集失败: {e}")
            return False
    
    def reset_to_original_datasets(self) -> bool:
        """
        重置为原始数据集
        
        Returns:
            bool: 重置是否成功
        """
        if self.original_datasets:
            self.datasets = self.original_datasets.copy()
            self.offline_dataset_info = None
            logger.info("已重置为原始数据集")
            return True
        return False
    
    def get_offline_dataset_info(self) -> Optional[Dict[str, str]]:
        """
        获取当前加载的离线数据集信息
        
        Returns:
            Optional[Dict[str, str]]: 数据集信息
        """
        return self.offline_dataset_info

# 创建全局实例
dataset_manager = DatasetManager() 