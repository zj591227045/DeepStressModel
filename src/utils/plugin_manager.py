"""
插件管理器模块，负责发现、加载和管理插件
"""
import importlib
import os
import logging
from src.utils.logger import setup_logger

# 设置日志记录器
logger = setup_logger("plugin_manager")

class PluginManager:
    """插件管理器类，负责发现、加载和管理插件"""
    
    def __init__(self, app_context):
        """
        初始化插件管理器
        
        Args:
            app_context: 应用程序上下文，包含配置和其他资源
        """
        self.app_context = app_context
        self.plugins = {}
        
    def discover_plugins(self):
        """
        发现可用插件
        
        Returns:
            int: 发现的插件数量
        """
        plugin_dirs = [
            os.path.join('src', 'benchmark'),
            # 其他插件目录可以在这里添加
        ]
        
        count = 0
        for plugin_dir in plugin_dirs:
            plugin_file = os.path.join(plugin_dir, 'plugin.py')
            if os.path.exists(plugin_file):
                module_path = plugin_dir.replace(os.path.sep, '.') + '.plugin'
                try:
                    module = importlib.import_module(module_path)
                    for attr_name in dir(module):
                        attr = getattr(module, attr_name)
                        if (isinstance(attr, type) and 
                            attr.__module__ == module.__name__ and 
                            'Plugin' in attr_name):
                            plugin_instance = attr()
                            plugin_name = plugin_instance.get_name()
                            self.plugins[plugin_name] = plugin_instance
                            logger.info(f"发现插件: {plugin_name} v{plugin_instance.get_version()}")
                            count += 1
                except Exception as e:
                    logger.error(f"加载插件模块 {module_path} 失败: {str(e)}")
        
        return count
        
    def initialize_plugins(self):
        """
        初始化所有已发现的插件
        
        Returns:
            int: 成功初始化的插件数量
        """
        count = 0
        for name, plugin in list(self.plugins.items()):
            try:
                # 检查插件是否启用
                if self.app_context.config.get(f"plugins.{name}.enabled", False):
                    if plugin.initialize(self.app_context):
                        logger.info(f"插件 {name} 初始化成功")
                        count += 1
                    else:
                        logger.warning(f"插件 {name} 初始化失败")
                        del self.plugins[name]
                else:
                    logger.info(f"插件 {name} 已禁用")
                    del self.plugins[name]
            except Exception as e:
                logger.error(f"初始化插件 {name} 失败: {str(e)}")
                del self.plugins[name]
        
        return count
        
    def cleanup_plugins(self):
        """
        清理所有已加载的插件资源
        
        Returns:
            int: 成功清理的插件数量
        """
        count = 0
        for name, plugin in list(self.plugins.items()):
            try:
                if plugin.cleanup():
                    logger.info(f"插件 {name} 清理完成")
                    count += 1
                else:
                    logger.warning(f"插件 {name} 清理失败")
            except Exception as e:
                logger.error(f"清理插件 {name} 失败: {str(e)}")
        
        return count
        
    def get_plugin(self, name):
        """
        获取指定名称的插件实例
        
        Args:
            name: 插件名称
            
        Returns:
            object: 插件实例，如果不存在则返回None
        """
        return self.plugins.get(name)
        
    def has_plugin(self, name):
        """
        检查是否存在指定名称的插件
        
        Args:
            name: 插件名称
            
        Returns:
            bool: 插件是否存在
        """
        return name in self.plugins
        
    def get_all_plugins(self):
        """
        获取所有已加载的插件
        
        Returns:
            dict: 插件名称到插件实例的映射
        """
        return self.plugins.copy() 