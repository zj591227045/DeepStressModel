"""
插件管理器模块，负责管理跑分模块的插件化接口
"""
import os
import sys
import importlib
import inspect
from typing import Dict, List, Any, Callable, Optional, Type
from src.utils.logger import setup_logger
from src.utils.config import config

# 设置日志记录器
logger = setup_logger("plugin_manager")

class BenchmarkPlugin:
    """跑分插件基类，所有插件必须继承此类"""
    
    def __init__(self, config_obj):
        """
        初始化插件
        
        Args:
            config_obj: 配置对象
        """
        self.config = config_obj
        self.name = self.__class__.__name__
        self.version = "1.0.0"
        self.description = "基础跑分插件"
        self.author = "DeepStressModel团队"
        self.enabled = True
    
    def initialize(self) -> bool:
        """
        初始化插件
        
        Returns:
            bool: 初始化是否成功
        """
        logger.info(f"插件 {self.name} 初始化")
        return True
    
    def cleanup(self) -> bool:
        """
        清理插件资源
        
        Returns:
            bool: 清理是否成功
        """
        logger.info(f"插件 {self.name} 清理资源")
        return True
    
    def get_info(self) -> Dict[str, Any]:
        """
        获取插件信息
        
        Returns:
            Dict[str, Any]: 插件信息
        """
        return {
            "name": self.name,
            "version": self.version,
            "description": self.description,
            "author": self.author,
            "enabled": self.enabled
        }
    
    def enable(self) -> bool:
        """
        启用插件
        
        Returns:
            bool: 启用是否成功
        """
        self.enabled = True
        logger.info(f"插件 {self.name} 已启用")
        return True
    
    def disable(self) -> bool:
        """
        禁用插件
        
        Returns:
            bool: 禁用是否成功
        """
        self.enabled = False
        logger.info(f"插件 {self.name} 已禁用")
        return True
    
    def is_enabled(self) -> bool:
        """
        检查插件是否启用
        
        Returns:
            bool: 插件是否启用
        """
        return self.enabled
    
    def on_benchmark_start(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """
        跑分开始事件处理
        
        Args:
            config: 跑分配置
            
        Returns:
            Dict[str, Any]: 处理结果
        """
        return {"status": "success"}
    
    def on_benchmark_progress(self, progress: Dict[str, Any]) -> Dict[str, Any]:
        """
        跑分进度事件处理
        
        Args:
            progress: 进度信息
            
        Returns:
            Dict[str, Any]: 处理结果
        """
        return {"status": "success"}
    
    def on_benchmark_complete(self, result: Dict[str, Any]) -> Dict[str, Any]:
        """
        跑分完成事件处理
        
        Args:
            result: 跑分结果
            
        Returns:
            Dict[str, Any]: 处理结果
        """
        return {"status": "success"}
    
    def on_benchmark_error(self, error: Dict[str, Any]) -> Dict[str, Any]:
        """
        跑分错误事件处理
        
        Args:
            error: 错误信息
            
        Returns:
            Dict[str, Any]: 处理结果
        """
        return {"status": "success"}


class PluginManager:
    """插件管理器类，负责管理跑分模块的插件"""
    
    def __init__(self, config_obj):
        """
        初始化插件管理器
        
        Args:
            config_obj: 配置对象
        """
        self.config = config_obj
        self.plugins: Dict[str, BenchmarkPlugin] = {}
        self.plugin_dirs = [
            os.path.join(os.path.dirname(__file__), "plugins"),
            os.path.join(os.getcwd(), "data", "benchmark", "plugins")
        ]
        
        # 确保插件目录存在
        for plugin_dir in self.plugin_dirs:
            os.makedirs(plugin_dir, exist_ok=True)
        
        logger.info("插件管理器初始化完成")
    
    def discover_plugins(self) -> List[str]:
        """
        发现可用插件
        
        Returns:
            List[str]: 插件名称列表
        """
        discovered_plugins = []
        
        for plugin_dir in self.plugin_dirs:
            if not os.path.exists(plugin_dir):
                continue
            
            # 将插件目录添加到系统路径
            if plugin_dir not in sys.path:
                sys.path.append(plugin_dir)
            
            # 遍历插件目录中的所有Python文件
            for filename in os.listdir(plugin_dir):
                if filename.endswith(".py") and not filename.startswith("__"):
                    module_name = filename[:-3]  # 去掉.py后缀
                    discovered_plugins.append(module_name)
        
        logger.info(f"发现 {len(discovered_plugins)} 个插件: {', '.join(discovered_plugins)}")
        return discovered_plugins
    
    def load_plugin(self, plugin_name: str) -> bool:
        """
        加载插件
        
        Args:
            plugin_name: 插件名称
            
        Returns:
            bool: 加载是否成功
        """
        try:
            # 如果插件已加载，则先卸载
            if plugin_name in self.plugins:
                self.unload_plugin(plugin_name)
            
            # 导入插件模块
            module = importlib.import_module(plugin_name)
            
            # 查找插件类（继承自BenchmarkPlugin的类）
            plugin_class = None
            for name, obj in inspect.getmembers(module):
                if (inspect.isclass(obj) and 
                    issubclass(obj, BenchmarkPlugin) and 
                    obj != BenchmarkPlugin):
                    plugin_class = obj
                    break
            
            if not plugin_class:
                logger.error(f"插件 {plugin_name} 中未找到有效的插件类")
                return False
            
            # 实例化插件
            plugin = plugin_class(self.config)
            
            # 初始化插件
            if not plugin.initialize():
                logger.error(f"插件 {plugin_name} 初始化失败")
                return False
            
            # 添加到插件列表
            self.plugins[plugin_name] = plugin
            
            logger.info(f"插件 {plugin_name} 加载成功")
            return True
        except Exception as e:
            logger.error(f"加载插件 {plugin_name} 失败: {str(e)}")
            return False
    
    def load_all_plugins(self) -> Dict[str, bool]:
        """
        加载所有发现的插件
        
        Returns:
            Dict[str, bool]: 插件加载结果，键为插件名称，值为加载是否成功
        """
        results = {}
        discovered_plugins = self.discover_plugins()
        
        for plugin_name in discovered_plugins:
            results[plugin_name] = self.load_plugin(plugin_name)
        
        logger.info(f"加载了 {sum(results.values())} 个插件，失败 {len(results) - sum(results.values())} 个")
        return results
    
    def unload_plugin(self, plugin_name: str) -> bool:
        """
        卸载插件
        
        Args:
            plugin_name: 插件名称
            
        Returns:
            bool: 卸载是否成功
        """
        if plugin_name not in self.plugins:
            logger.warning(f"插件 {plugin_name} 未加载，无法卸载")
            return False
        
        try:
            # 清理插件资源
            plugin = self.plugins[plugin_name]
            if not plugin.cleanup():
                logger.warning(f"插件 {plugin_name} 资源清理失败")
            
            # 从插件列表中移除
            del self.plugins[plugin_name]
            
            # 尝试从sys.modules中移除插件模块
            if plugin_name in sys.modules:
                del sys.modules[plugin_name]
            
            logger.info(f"插件 {plugin_name} 卸载成功")
            return True
        except Exception as e:
            logger.error(f"卸载插件 {plugin_name} 失败: {str(e)}")
            return False
    
    def unload_all_plugins(self) -> Dict[str, bool]:
        """
        卸载所有插件
        
        Returns:
            Dict[str, bool]: 插件卸载结果，键为插件名称，值为卸载是否成功
        """
        results = {}
        plugin_names = list(self.plugins.keys())
        
        for plugin_name in plugin_names:
            results[plugin_name] = self.unload_plugin(plugin_name)
        
        logger.info(f"卸载了 {sum(results.values())} 个插件，失败 {len(results) - sum(results.values())} 个")
        return results
    
    def get_plugin(self, plugin_name: str) -> Optional[BenchmarkPlugin]:
        """
        获取插件实例
        
        Args:
            plugin_name: 插件名称
            
        Returns:
            Optional[BenchmarkPlugin]: 插件实例，如果插件未加载则返回None
        """
        return self.plugins.get(plugin_name)
    
    def get_all_plugins(self) -> Dict[str, BenchmarkPlugin]:
        """
        获取所有插件实例
        
        Returns:
            Dict[str, BenchmarkPlugin]: 插件实例字典，键为插件名称，值为插件实例
        """
        return self.plugins
    
    def get_enabled_plugins(self) -> Dict[str, BenchmarkPlugin]:
        """
        获取所有启用的插件实例
        
        Returns:
            Dict[str, BenchmarkPlugin]: 启用的插件实例字典，键为插件名称，值为插件实例
        """
        return {name: plugin for name, plugin in self.plugins.items() if plugin.is_enabled()}
    
    def enable_plugin(self, plugin_name: str) -> bool:
        """
        启用插件
        
        Args:
            plugin_name: 插件名称
            
        Returns:
            bool: 启用是否成功
        """
        if plugin_name not in self.plugins:
            logger.warning(f"插件 {plugin_name} 未加载，无法启用")
            return False
        
        return self.plugins[plugin_name].enable()
    
    def disable_plugin(self, plugin_name: str) -> bool:
        """
        禁用插件
        
        Args:
            plugin_name: 插件名称
            
        Returns:
            bool: 禁用是否成功
        """
        if plugin_name not in self.plugins:
            logger.warning(f"插件 {plugin_name} 未加载，无法禁用")
            return False
        
        return self.plugins[plugin_name].disable()
    
    def is_plugin_enabled(self, plugin_name: str) -> bool:
        """
        检查插件是否启用
        
        Args:
            plugin_name: 插件名称
            
        Returns:
            bool: 插件是否启用
        """
        if plugin_name not in self.plugins:
            return False
        
        return self.plugins[plugin_name].is_enabled()
    
    def notify_plugins(self, event: str, data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        通知所有启用的插件
        
        Args:
            event: 事件名称
            data: 事件数据
            
        Returns:
            List[Dict[str, Any]]: 插件处理结果列表
        """
        results = []
        enabled_plugins = self.get_enabled_plugins()
        
        for plugin_name, plugin in enabled_plugins.items():
            try:
                # 根据事件类型调用相应的处理方法
                if event == "benchmark_start":
                    result = plugin.on_benchmark_start(data)
                elif event == "benchmark_progress":
                    result = plugin.on_benchmark_progress(data)
                elif event == "benchmark_complete":
                    result = plugin.on_benchmark_complete(data)
                elif event == "benchmark_error":
                    result = plugin.on_benchmark_error(data)
                else:
                    logger.warning(f"未知事件类型: {event}")
                    continue
                
                results.append({
                    "plugin": plugin_name,
                    "result": result
                })
            except Exception as e:
                logger.error(f"插件 {plugin_name} 处理事件 {event} 失败: {str(e)}")
                results.append({
                    "plugin": plugin_name,
                    "error": str(e)
                })
        
        return results
    
    def register_plugin_directory(self, directory: str) -> bool:
        """
        注册插件目录
        
        Args:
            directory: 插件目录路径
            
        Returns:
            bool: 注册是否成功
        """
        if not os.path.exists(directory) or not os.path.isdir(directory):
            logger.error(f"插件目录 {directory} 不存在或不是目录")
            return False
        
        if directory in self.plugin_dirs:
            logger.warning(f"插件目录 {directory} 已注册")
            return True
        
        self.plugin_dirs.append(directory)
        logger.info(f"插件目录 {directory} 注册成功")
        return True
    
    def create_plugin_template(self, plugin_name: str, output_dir: str = None) -> str:
        """
        创建插件模板
        
        Args:
            plugin_name: 插件名称
            output_dir: 输出目录，默认为第一个插件目录
            
        Returns:
            str: 插件文件路径，如果创建失败则返回空字符串
        """
        if not output_dir:
            output_dir = self.plugin_dirs[0]
        
        if not os.path.exists(output_dir):
            os.makedirs(output_dir, exist_ok=True)
        
        plugin_file = os.path.join(output_dir, f"{plugin_name}.py")
        
        # 检查文件是否已存在
        if os.path.exists(plugin_file):
            logger.error(f"插件文件 {plugin_file} 已存在")
            return ""
        
        # 创建插件模板
        template = f'''"""
{plugin_name} 插件
"""
from src.benchmark.plugin_manager import BenchmarkPlugin
from typing import Dict, Any

class {plugin_name.capitalize()}Plugin(BenchmarkPlugin):
    """
    {plugin_name.capitalize()} 插件类
    """
    
    def __init__(self, config):
        """
        初始化插件
        
        Args:
            config: 配置对象
        """
        super().__init__(config)
        self.name = "{plugin_name}"
        self.version = "1.0.0"
        self.description = "{plugin_name.capitalize()} 插件"
        self.author = "Your Name"
    
    def initialize(self) -> bool:
        """
        初始化插件
        
        Returns:
            bool: 初始化是否成功
        """
        # 在这里添加初始化代码
        return super().initialize()
    
    def cleanup(self) -> bool:
        """
        清理插件资源
        
        Returns:
            bool: 清理是否成功
        """
        # 在这里添加清理代码
        return super().cleanup()
    
    def on_benchmark_start(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """
        跑分开始事件处理
        
        Args:
            config: 跑分配置
            
        Returns:
            Dict[str, Any]: 处理结果
        """
        # 在这里添加跑分开始事件处理代码
        return {{"status": "success", "message": "跑分开始"}}
    
    def on_benchmark_progress(self, progress: Dict[str, Any]) -> Dict[str, Any]:
        """
        跑分进度事件处理
        
        Args:
            progress: 进度信息
            
        Returns:
            Dict[str, Any]: 处理结果
        """
        # 在这里添加跑分进度事件处理代码
        return {{"status": "success", "message": f"跑分进度: {{progress.get('progress', 0)}}%"}}
    
    def on_benchmark_complete(self, result: Dict[str, Any]) -> Dict[str, Any]:
        """
        跑分完成事件处理
        
        Args:
            result: 跑分结果
            
        Returns:
            Dict[str, Any]: 处理结果
        """
        # 在这里添加跑分完成事件处理代码
        return {{"status": "success", "message": "跑分完成"}}
    
    def on_benchmark_error(self, error: Dict[str, Any]) -> Dict[str, Any]:
        """
        跑分错误事件处理
        
        Args:
            error: 错误信息
            
        Returns:
            Dict[str, Any]: 处理结果
        """
        # 在这里添加跑分错误事件处理代码
        return {{"status": "success", "message": f"跑分错误: {{error.get('message', '未知错误')}}"}}
'''
        
        try:
            with open(plugin_file, 'w', encoding='utf-8') as f:
                f.write(template)
            
            logger.info(f"插件模板 {plugin_file} 创建成功")
            return plugin_file
        except Exception as e:
            logger.error(f"创建插件模板失败: {str(e)}")
            return "" 