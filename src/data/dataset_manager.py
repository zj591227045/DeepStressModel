"""
数据集管理器模块，负责管理测试数据集
"""
from typing import Dict, List, Any, Optional
from src.data.test_datasets import DATASETS
from src.data.offline_dataset import decrypt_offline_package
from src.utils.logger import setup_logger
import os
import json

logger = setup_logger("dataset_manager")

class DatasetManager:
    """数据集管理器类"""
    
    def __init__(self):
        """初始化数据集管理器"""
        self.datasets = DATASETS.copy()
        self.original_datasets = DATASETS.copy()  # 保存原始数据集
        self.offline_dataset_info = None  # 当前加载的离线数据集信息
        self.raw_dataset = None  # 保存原始数据集内容，用于跑分基准测试
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
        
        # 如果是原始数据集，不允许删除
        if name in self.original_datasets:
            logger.warning(f"数据集 '{name}' 是原始数据集，不允许删除")
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
        加载离线数据包
        
        Args:
            file_path: 文件路径
            api_key: API密钥
            
        Returns:
            bool: 加载是否成功
        """
        try:
            # 解密离线包
            logger.info(f"正在加载离线包: {file_path}")
            
            # 使用自定义的解密函数解密离线包
            package_data = decrypt_offline_package(file_path, api_key)
            
            # 如果解密成功
            if package_data:
                # 获取格式化后的数据集
                formatted_dataset = package_data.get("formatted_dataset")
                
                # 获取数据集信息
                dataset_info = package_data.get("dataset_info")
                
                # 保存原始数据集，供跑分使用
                self.raw_dataset = package_data.get("raw_dataset")
                
                # 使用数据集更新本地数据集
                if formatted_dataset:
                    # 添加到数据集字典中
                    for name, data in formatted_dataset.items():
                        # 使用新名称，避免覆盖原始数据集
                        new_name = f"离线-{name}"
                        self.datasets[new_name] = data
                        logger.info(f"已添加离线数据集: {new_name}, 包含 {len(data)} 个提示")
                
                # 保存数据集信息
                self.offline_dataset_info = dataset_info
                
                logger.info("离线包加载成功")
                logger.debug(f"加载的数据集信息: {dataset_info}")
                
                return True
            else:
                logger.error("解密离线包失败，未能获取有效数据")
                return False
                
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
            self.raw_dataset = None
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
    
    def get_offline_dataset_data(self) -> Optional[List[Dict[str, Any]]]:
        """
        获取当前加载的离线数据集的原始数据
        主要用于跑分测试，不对外公开编辑
        
        Returns:
            Optional[List[Dict[str, Any]]]: 数据集原始数据列表
        """
        try:
            # 检查是否存在原始数据集
            if self.raw_dataset and "data" in self.raw_dataset and isinstance(self.raw_dataset["data"], list):
                logger.info(f"获取到离线数据集原始数据，共 {len(self.raw_dataset['data'])} 条")
                return self.raw_dataset["data"]
            
            # 返回空数据
            logger.warning("离线数据集不存在或格式不正确")
            return None
        except Exception as e:
            logger.error(f"获取离线数据集数据失败: {e}")
            return None
    
    def load_benchmark_dataset(self, file_path: str) -> bool:
        """
        直接加载基准测试数据集（无需解密）
        用于跑分测试，从JSON文件直接加载标准测试数据
        
        Args:
            file_path: 数据集文件路径
            
        Returns:
            bool: 加载是否成功
        """
        try:
            logger.info(f"正在加载基准测试数据集: {file_path}")
            
            # 检查文件是否存在
            if not os.path.exists(file_path):
                logger.error(f"基准测试数据集文件不存在: {file_path}")
                return False
            
            # 读取数据集文件
            with open(file_path, 'r', encoding='utf-8') as f:
                dataset = json.load(f)
            
            # 验证数据集格式
            if not isinstance(dataset, dict) or "data" not in dataset:
                logger.error("基准测试数据集格式不正确，缺少data字段")
                return False
            
            # 更新raw_dataset，供跑分使用
            self.raw_dataset = dataset
            
            # 保存数据集信息
            self.offline_dataset_info = {
                "名称": dataset.get("name", "标准基准测试"),
                "版本": dataset.get("version", "v1.0.0"),
                "描述": dataset.get("description", "标准基准测试数据集"),
                "记录数": str(len(dataset.get("data", []))),
                "metadata": {
                    "dataset_id": "benchmark-standard",
                    "dataset_name": dataset.get("name", "标准基准测试"),
                    "dataset_version": dataset.get("version", "v1.0.0"),
                    "is_benchmark": True
                }
            }
            
            logger.info(f"基准测试数据集加载成功，包含 {len(dataset.get('data', []))} 条测试项")
            return True
            
        except Exception as e:
            logger.error(f"加载基准测试数据集失败: {e}")
            return False

# 创建全局实例
dataset_manager = DatasetManager() 