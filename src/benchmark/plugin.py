"""
跑分模块插件实现
"""
from src.utils.plugin_interface import PluginInterface
from src.utils.logger import setup_logger

# 设置日志记录器
logger = setup_logger("benchmark_plugin")

class BenchmarkPlugin(PluginInterface):
    """跑分模块插件类，实现插件接口"""
    
    def __init__(self):
        """初始化跑分插件"""
        self.benchmark_manager = None
        self.app_context = None
        self.enabled = False
        
    def initialize(self, app_context):
        """
        初始化插件
        
        Args:
            app_context: 应用程序上下文，包含配置和其他资源
            
        Returns:
            bool: 初始化是否成功
        """
        try:
            self.app_context = app_context
            self.enabled = app_context.config.get('benchmark.enabled', False)
            
            if self.enabled:
                logger.info("正在初始化跑分插件...")
                
                # 延迟导入，避免循环依赖
                from src.benchmark.benchmark_manager import BenchmarkManager
                self.benchmark_manager = BenchmarkManager(app_context.config)
                
                # 注册UI组件
                if hasattr(app_context, 'ui_manager'):
                    logger.info("正在注册跑分UI组件...")
                    from src.benchmark.gui.benchmark_tab import BenchmarkTab
                    from src.benchmark.gui.benchmark_history_tab import BenchmarkHistoryTab
                    
                    app_context.ui_manager.register_tab('benchmark', BenchmarkTab())
                    app_context.ui_manager.register_tab('benchmark_history', BenchmarkHistoryTab())
                    logger.info("跑分UI组件注册成功")
                
                logger.info("跑分插件初始化成功")
            else:
                logger.info("跑分插件已禁用")
            
            return True
        except Exception as e:
            logger.error(f"初始化跑分插件失败: {str(e)}")
            self.enabled = False
            return False
        
    def cleanup(self):
        """
        清理插件资源
        
        Returns:
            bool: 清理是否成功
        """
        try:
            logger.info("正在清理跑分插件资源...")
            
            # 清理跑分管理器资源
            if self.benchmark_manager:
                self.benchmark_manager.cleanup()
                self.benchmark_manager = None
                
            # 移除UI组件
            if self.enabled and hasattr(self.app_context, 'ui_manager'):
                logger.info("正在移除跑分UI组件...")
                self.app_context.ui_manager.unregister_tab('benchmark')
                self.app_context.ui_manager.unregister_tab('benchmark_history')
                logger.info("跑分UI组件移除成功")
            
            logger.info("跑分插件资源清理完成")
            return True
        except Exception as e:
            logger.error(f"清理跑分插件资源失败: {str(e)}")
            return False
        
    def get_name(self):
        """
        获取插件名称
        
        Returns:
            str: 插件名称
        """
        return "benchmark"
        
    def get_version(self):
        """
        获取插件版本
        
        Returns:
            str: 插件版本
        """
        return "1.0.0"
        
    def is_enabled(self):
        """
        检查插件是否启用
        
        Returns:
            bool: 插件是否启用
        """
        return self.enabled 