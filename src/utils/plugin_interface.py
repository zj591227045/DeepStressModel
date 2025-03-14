"""
插件接口模块，定义插件的基本接口
"""
from abc import ABC, abstractmethod

class PluginInterface(ABC):
    """插件接口基类，所有插件都应该继承此类"""
    
    @abstractmethod
    def initialize(self, app_context):
        """
        初始化插件
        
        Args:
            app_context: 应用程序上下文，包含配置和其他资源
            
        Returns:
            bool: 初始化是否成功
        """
        pass
        
    @abstractmethod
    def cleanup(self):
        """
        清理插件资源
        
        Returns:
            bool: 清理是否成功
        """
        pass
        
    @abstractmethod
    def get_name(self):
        """
        获取插件名称
        
        Returns:
            str: 插件名称
        """
        pass
        
    @abstractmethod
    def get_version(self):
        """
        获取插件版本
        
        Returns:
            str: 插件版本
        """
        pass
        
    @abstractmethod
    def is_enabled(self):
        """
        检查插件是否启用
        
        Returns:
            bool: 插件是否启用
        """
        pass 