"""
跑分模块集成文件，用于将新开发的跑分模块与现有UI集成
"""
import os
import sys
import asyncio
from typing import Dict, Any, Callable, Optional, List
from PyQt6.QtCore import QObject, pyqtSignal, QThread

from src.utils.logger import setup_logger
from src.utils.config import config
from src.benchmark.benchmark_manager import BenchmarkManager
from src.benchmark.plugin_manager import PluginManager

# 设置日志记录器
logger = setup_logger("benchmark_integration")


class AsyncWorker(QThread):
    """异步工作线程，用于执行异步操作"""
    
    finished = pyqtSignal(object)  # 完成信号，携带结果
    error = pyqtSignal(str)  # 错误信号，携带错误信息
    
    def __init__(self, coro, *args, **kwargs):
        """
        初始化异步工作线程
        
        Args:
            coro: 要执行的协程函数
            *args: 传递给协程的位置参数
            **kwargs: 传递给协程的关键字参数
        """
        super().__init__()
        self.coro = coro
        self.args = args
        self.kwargs = kwargs
    
    def run(self):
        """运行线程"""
        try:
            # 创建事件循环
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            # 执行协程
            result = loop.run_until_complete(self.coro(*self.args, **self.kwargs))
            
            # 关闭事件循环
            loop.close()
            
            # 发送完成信号
            self.finished.emit(result)
        except Exception as e:
            logger.error(f"异步操作错误: {str(e)}")
            self.error.emit(str(e))


class BenchmarkIntegration(QObject):
    """跑分模块集成类，用于将新开发的跑分模块与现有UI集成"""
    
    # 定义信号
    progress_updated = pyqtSignal(dict)  # 进度更新信号
    test_finished = pyqtSignal(dict)  # 测试完成信号
    test_error = pyqtSignal(str)  # 测试错误信号
    
    def __init__(self):
        """初始化跑分模块集成"""
        super().__init__()
        
        # 初始化跑分管理器
        self.benchmark_manager = BenchmarkManager(config)
        
        # 初始化插件管理器
        self.plugin_manager = PluginManager(config)
        
        # 加载插件
        self.plugin_manager.load_all_plugins()
        
        # 设置进度回调
        self.benchmark_manager.set_progress_callback(self._on_progress_updated)
        
        # 初始化成员变量
        self.async_workers = []  # 保存异步工作线程的引用
        self.running = False
        
        # 初始化异步资源的标志
        self.async_initialized = False
        
        logger.info("跑分模块集成初始化完成")
    
    async def initialize_async(self):
        """
        初始化异步资源
        
        Returns:
            bool: 初始化是否成功
        """
        if self.async_initialized:
            return True
            
        try:
            # 初始化跑分管理器的异步资源
            # 注意：这里不会自动连接服务器或注册设备
            success = await self.benchmark_manager.initialize_async()
            self.async_initialized = success
            return success
        except Exception as e:
            logger.error(f"初始化异步资源失败: {str(e)}")
            return False
    
    def _on_progress_updated(self, progress: Dict[str, Any]):
        """
        进度回调处理
        
        Args:
            progress: 进度信息
        """
        # 转发进度信号
        self.progress_updated.emit(progress)
        
        # 通知插件
        self.plugin_manager.notify_plugins("benchmark_progress", progress)
    
    def register_device(self, nickname: str, callback: Callable[[bool, str], None]):
        """
        注册设备
        
        Args:
            nickname: 设备名称
            callback: 回调函数，接收成功标志和消息
        """
        # 设置昵称
        self.benchmark_manager.nickname = nickname
        
        # 创建异步工作线程，先初始化异步资源，再注册设备
        async def register_with_init():
            # 先初始化异步资源
            if not self.async_initialized:
                init_success = await self.initialize_async()
                if not init_success:
                    return False
            
            # 注册设备
            return await self.benchmark_manager.register_device()
        
        # 创建异步工作线程
        worker = AsyncWorker(register_with_init)
        
        # 连接信号
        worker.finished.connect(lambda result: callback(result, "设备注册成功" if result else "设备注册失败"))
        worker.error.connect(lambda error: callback(False, f"设备注册失败: {error}"))
        
        # 启动线程
        worker.start()
        self.async_workers.append(worker)
    
    def authenticate(self, callback: Callable[[bool, str], None]):
        """
        设备认证
        
        Args:
            callback: 回调函数，接收成功标志和消息
        """
        # 创建异步工作线程，先初始化异步资源，再认证
        async def authenticate_with_init():
            # 先初始化异步资源
            if not self.async_initialized:
                init_success = await self.initialize_async()
                if not init_success:
                    return False
            
            # 认证设备
            return await self.benchmark_manager.authenticate()
        
        # 创建异步工作线程
        worker = AsyncWorker(authenticate_with_init)
        
        # 连接信号
        worker.finished.connect(lambda result: callback(result, "设备认证成功" if result else "设备认证失败"))
        worker.error.connect(lambda error: callback(False, f"设备认证失败: {error}"))
        
        # 启动线程
        worker.start()
        self.async_workers.append(worker)
    
    def get_datasets(self, callback: Callable[[List[Dict[str, Any]], str], None]):
        """
        获取数据集列表
        
        Args:
            callback: 回调函数，接收数据集列表和消息
        """
        # 创建异步工作线程，先初始化异步资源，再获取数据集
        async def get_datasets_with_init():
            # 先初始化异步资源
            if not self.async_initialized:
                init_success = await self.initialize_async()
                if not init_success:
                    return []
            
            # 获取数据集
            return await self.benchmark_manager.get_datasets()
        
        # 创建异步工作线程
        worker = AsyncWorker(get_datasets_with_init)
        
        # 连接信号
        worker.finished.connect(lambda datasets: callback(datasets, f"获取到 {len(datasets)} 个数据集"))
        worker.error.connect(lambda error: callback([], f"获取数据集失败: {error}"))
        
        # 启动线程
        worker.start()
        self.async_workers.append(worker)
    
    def download_dataset(self, dataset_version: str, callback: Callable[[bool, str], None]):
        """
        下载数据集
        
        Args:
            dataset_version: 数据集版本
            callback: 回调函数，接收成功标志和消息
        """
        # 创建异步工作线程，先初始化异步资源，再下载数据集
        async def download_dataset_with_init():
            # 先初始化异步资源
            if not self.async_initialized:
                init_success = await self.initialize_async()
                if not init_success:
                    return False
            
            # 下载数据集
            return await self.benchmark_manager.download_dataset(dataset_version)
        
        # 创建异步工作线程
        worker = AsyncWorker(download_dataset_with_init)
        
        # 连接信号
        worker.finished.connect(lambda result: callback(result, "数据集下载成功" if result else "数据集下载失败"))
        worker.error.connect(lambda error: callback(False, f"数据集下载失败: {error}"))
        
        # 启动线程
        worker.start()
        self.async_workers.append(worker)
    
    def upload_dataset(self, file_path: str) -> bool:
        """
        上传本地数据集（离线模式）
        
        Args:
            file_path: 本地数据集文件路径
            
        Returns:
            bool: 上传是否成功
        """
        return self.benchmark_manager.upload_dataset(file_path)
    
    def get_dataset_info(self) -> Dict[str, Any]:
        """
        获取当前数据集信息
        
        Returns:
            Dict[str, Any]: 数据集信息
        """
        return self.benchmark_manager.get_dataset_info()
    
    def is_dataset_loaded(self) -> bool:
        """
        检查数据集是否已加载
        
        Returns:
            bool: 数据集是否已加载
        """
        return self.benchmark_manager.is_dataset_loaded()
    
    def run_benchmark(self, config: Dict[str, Any]):
        """
        运行跑分测试
        
        Args:
            config: 测试配置
        """
        if self.running:
            logger.warning("已有测试正在运行")
            return
        
        self.running = True
        
        # 创建异步工作线程，先初始化异步资源，再运行测试
        async def run_benchmark_with_init():
            # 先初始化异步资源
            if not self.async_initialized:
                init_success = await self.initialize_async()
                if not init_success:
                    self.test_error.emit("初始化异步资源失败")
                    self.running = False
                    return None
            
            # 运行测试
            try:
                result = await self.benchmark_manager.run_benchmark(config)
                self.running = False
                return result
            except Exception as e:
                self.running = False
                raise e
        
        # 创建异步工作线程
        worker = AsyncWorker(run_benchmark_with_init)
        
        # 连接信号
        worker.finished.connect(self._on_test_finished)
        worker.error.connect(self._on_test_error)
        
        # 启动线程
        worker.start()
        self.async_workers.append(worker)
    
    def stop_benchmark(self):
        """停止跑分测试"""
        if not self.running:
            return
        
        self.benchmark_manager.stop_benchmark()
        self.running = False
    
    def _on_test_finished(self, result: Dict[str, Any]):
        """
        测试完成处理
        
        Args:
            result: 测试结果
        """
        self.running = False
        
        # 通知插件
        self.plugin_manager.notify_plugins("benchmark_complete", result)
        
        # 转发测试完成信号
        self.test_finished.emit(result)
    
    def _on_test_error(self, error: str):
        """
        测试错误处理
        
        Args:
            error: 错误信息
        """
        self.running = False
        
        # 通知插件
        self.plugin_manager.notify_plugins("benchmark_error", {"message": error})
        
        # 转发测试错误信号
        self.test_error.emit(error)
    
    def export_result(self, result: Dict[str, Any], format_type: str = "json", output_path: Optional[str] = None) -> str:
        """
        导出测试结果
        
        Args:
            result: 测试结果
            format_type: 导出格式，支持json、csv、markdown、html
            output_path: 输出路径，如果为None则使用默认路径
            
        Returns:
            str: 导出文件路径，如果导出失败则返回空字符串
        """
        # 查找结果导出插件
        exporter_plugin = self.plugin_manager.get_plugin("result_exporter")
        if not exporter_plugin:
            logger.error("未找到结果导出插件")
            return ""
        
        # 设置当前结果
        exporter_plugin.current_result = result
        
        # 导出结果
        return exporter_plugin.export_result(format_type, output_path)
    
    def cleanup(self):
        """清理资源"""
        # 停止所有异步工作线程
        for worker in self.async_workers:
            if worker.isRunning():
                worker.terminate()
                worker.wait()
        
        # 清理跑分管理器资源
        self.benchmark_manager.cleanup()
        
        # 卸载所有插件
        self.plugin_manager.unload_all_plugins()
        
        logger.info("跑分模块集成资源清理完成")

    def enable_benchmark_module(self, callback: Callable[[bool, str], None]):
        """
        启用跑分模块，连接服务器并验证API密钥
        
        Args:
            callback: 回调函数，接收成功标志和消息
        """
        # 创建异步工作线程
        async def enable_module():
            # 先初始化异步资源
            if not self.async_initialized:
                init_success = await self.initialize_async()
                if not init_success:
                    return False
            
            # 启用跑分模块
            return await self.benchmark_manager.enable_benchmark_module()
        
        # 创建异步工作线程
        worker = AsyncWorker(enable_module)
        
        # 连接信号
        worker.finished.connect(lambda result: callback(result, "跑分模块启用成功" if result else "跑分模块启用失败"))
        worker.error.connect(lambda error: callback(False, f"跑分模块启用失败: {error}"))
        
        # 启动线程
        worker.start()
        self.async_workers.append(worker)
    
    def disable_benchmark_module(self, callback: Callable[[bool, str], None]):
        """
        禁用跑分模块
        
        Args:
            callback: 回调函数，接收成功标志和消息
        """
        # 创建异步工作线程
        async def disable_module():
            # 先初始化异步资源
            if not self.async_initialized:
                init_success = await self.initialize_async()
                if not init_success:
                    return False
            
            # 禁用跑分模块
            return await self.benchmark_manager.disable_benchmark_module()
        
        # 创建异步工作线程
        worker = AsyncWorker(disable_module)
        
        # 连接信号
        worker.finished.connect(lambda result: callback(result, "跑分模块禁用成功" if result else "跑分模块禁用失败"))
        worker.error.connect(lambda error: callback(False, f"跑分模块禁用失败: {error}"))
        
        # 启动线程
        worker.start()
        self.async_workers.append(worker)
    
    def set_api_key(self, api_key: str, device_id: str = None, nickname: str = None) -> bool:
        """
        设置API密钥
        
        Args:
            api_key: API密钥
            device_id: 设备ID（可选）
            nickname: 设备名称（可选）
            
        Returns:
            bool: 设置是否成功
        """
        try:
            return self.benchmark_manager.set_api_key(api_key, device_id, nickname)
        except Exception as e:
            logger.error(f"设置API密钥失败: {str(e)}")
            return False

    def get_offline_package(self, dataset_id: int, callback=None):
        """
        获取离线测试数据包
        
        Args:
            dataset_id: 数据集ID
            callback: 回调函数，接收参数 (success: bool, message: str, package: dict)
        """
        try:
            # 检查API密钥
            api_key = config.get("benchmark.api_key")
            logger.debug(f"获取离线包 - API密钥状态: {'已配置' if api_key else '未配置'}")
            if not api_key:
                if callback:
                    callback(False, "API密钥未设置", None)
                return
            
            # 获取离线包
            async def _get_package():
                try:
                    # 先初始化异步资源
                    if not self.async_initialized:
                        logger.debug("获取离线包 - 初始化异步资源")
                        init_success = await self.initialize_async()
                        if not init_success:
                            logger.error("获取离线包 - 初始化异步资源失败")
                            if callback:
                                callback(False, "初始化异步资源失败", None)
                            return
                        logger.debug("获取离线包 - 异步资源初始化成功")
                    
                    # 重置API客户端状态
                    if hasattr(self.benchmark_manager, 'api_client') and self.benchmark_manager.api_client:
                        logger.debug("获取离线包 - 重置API客户端状态")
                        # 确保API客户端重新创建会话
                        if hasattr(self.benchmark_manager.api_client, 'session') and self.benchmark_manager.api_client.session:
                            if not self.benchmark_manager.api_client.session.closed:
                                await self.benchmark_manager.api_client.session.close()
                                logger.debug("获取离线包 - 关闭之前的HTTP会话")
                            self.benchmark_manager.api_client.session = None
                    
                    # 获取离线包
                    logger.debug(f"获取离线包 - 开始请求数据集(ID: {dataset_id})")
                    package = await self.benchmark_manager.get_offline_package(dataset_id)
                    logger.debug(f"获取离线包 - 服务器响应: {package if package else '空'}")
                    
                    if package:
                        logger.info(f"获取离线包成功 - 数据集大小: {len(str(package))} 字节")
                        if callback:
                            callback(True, "获取成功", package)
                    else:
                        logger.error("获取离线包 - 服务器返回空数据")
                        if callback:
                            callback(False, "获取失败：返回数据为空", None)
                except Exception as e:
                    logger.error(f"获取离线包异常: {str(e)}")
                    if callback:
                        callback(False, f"获取失败: {str(e)}", None)
                finally:
                    # 确保清理资源
                    if hasattr(self.benchmark_manager, 'api_client') and self.benchmark_manager.api_client:
                        if hasattr(self.benchmark_manager.api_client, 'session') and self.benchmark_manager.api_client.session:
                            if not self.benchmark_manager.api_client.session.closed:
                                try:
                                    await self.benchmark_manager.api_client.session.close()
                                    logger.debug("获取离线包 - 清理HTTP会话资源")
                                except Exception as e:
                                    logger.error(f"关闭HTTP会话失败: {str(e)}")
            
            # 创建事件循环
            logger.debug("获取离线包 - 创建事件循环")
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            # 创建并运行任务
            logger.debug("获取离线包 - 开始执行异步任务")
            loop.run_until_complete(_get_package())
            
            # 关闭事件循环
            logger.debug("获取离线包 - 关闭事件循环")
            loop.close()
            
        except Exception as e:
            logger.error(f"获取离线包失败: {str(e)}")
            if callback:
                callback(False, f"获取失败: {str(e)}", None)
    
    def load_offline_package(self, package_path: str, callback: Callable[[bool, str], None] = None):
        """
        加载并解密离线包
        
        Args:
            package_path: 离线包文件路径
            callback: 回调函数，接收成功标志和消息
        """
        # 获取API密钥
        api_key = self.config.get("benchmark.api_key", "")
        if not api_key:
            logger.error("未配置API密钥，无法解密离线包")
            if callback:
                callback(False, "未配置API密钥，请先在设置中配置API密钥")
            return
            
        # 创建异步工作线程，先初始化异步资源，再加载离线包
        async def load_offline_package_with_init():
            # 先初始化异步资源
            if not self.async_initialized:
                init_success = await self.initialize_async()
                if not init_success:
                    return False
            
            # 加载离线包
            return await self.benchmark_manager.load_offline_package(package_path, api_key)
        
        # 创建异步工作线程
        worker = AsyncWorker(load_offline_package_with_init)
        
        # 连接信号
        if callback:
            worker.finished.connect(lambda result: callback(result, "离线包加载成功" if result else "离线包加载失败"))
            worker.error.connect(lambda error: callback(False, f"离线包加载失败: {error}"))
        
        # 保存工作线程引用并启动
        self.async_workers.append(worker)
        worker.start()


# 创建全局实例
benchmark_integration = BenchmarkIntegration() 