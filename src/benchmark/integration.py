"""
跑分模块集成文件，用于将新开发的跑分模块与现有UI集成
"""
import os
import sys
import asyncio
from typing import Dict, Any, Callable, Optional, List
from PyQt6.QtCore import QObject, pyqtSignal, QThread
from datetime import datetime

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
        
        # 导入配置
        from src.utils.config import config as global_config
        self.config = global_config  # 保存配置引用
        
        # 初始化跑分管理器
        self.benchmark_manager = BenchmarkManager(self.config)
        
        # 初始化插件管理器
        self.plugin_manager = PluginManager(self.config)
        
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
        # 添加调试日志
        logger.debug(f"BenchmarkIntegration: 收到进度更新，准备发送信号. 数据键: {list(progress.keys() if isinstance(progress, dict) else ['非字典数据'])}")
        
        # 检查总耗时相关字段
        if "datasets" in progress and progress["datasets"]:
            first_dataset_name = list(progress["datasets"].keys())[0]
            first_dataset = progress["datasets"][first_dataset_name]
            
            # 检查并记录总耗时相关字段
            duration_fields = {
                "total_duration": first_dataset.get("total_duration", "MISSING"),
                "total_time": first_dataset.get("total_time", "MISSING"),
                "test_duration": first_dataset.get("test_duration", "MISSING"),
                "duration": first_dataset.get("duration", "MISSING")
            }
            logger.debug(f"BenchmarkIntegration: 数据集 '{first_dataset_name}' 的总耗时字段: {duration_fields}")
            
            # 如果所有总耗时字段都不存在，则补充一个
            all_missing = all(value == "MISSING" for value in duration_fields.values())
            if all_missing and "completed" in first_dataset and "total" in first_dataset:
                # 检查是否有单项测试的耗时数据可以累加
                if "items" in first_dataset and isinstance(first_dataset["items"], list):
                    total_duration = sum(item.get("duration", 0) for item in first_dataset["items"] if isinstance(item, dict))
                    if total_duration > 0:
                        logger.debug(f"BenchmarkIntegration: 为数据集 '{first_dataset_name}' 补充总耗时: {total_duration}")
                        first_dataset["total_duration"] = total_duration
        
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
                # 从配置中提取所需参数
                model = config.get("model", "")
                precision = config.get("precision", "FP16")
                
                # 统一处理API URL
                api_url = None
                # 1. 尝试从model_config中获取api_url
                model_config = config.get("model_config", {})
                if isinstance(model_config, dict) and "api_url" in model_config:
                    api_url = model_config["api_url"]
                
                # 2. 如果model_config中没有，尝试从framework_config中获取
                if not api_url:
                    framework_config = config.get("framework_config", {})
                    if isinstance(framework_config, dict) and "api_url" in framework_config:
                        api_url = framework_config["api_url"]
                
                # 3. 如果还是没有，检查config本身
                if not api_url and "api_url" in config:
                    api_url = config["api_url"]
                
                # 4. 确保URL包含完整路径
                if api_url:
                    # 如果URL不以/结尾，添加/
                    if not api_url.endswith("/"):
                        api_url += "/"
                    
                    # 如果URL不包含chat/completions，添加它
                    if "chat/completions" not in api_url:
                        # 移除可能的v1/结尾
                        if api_url.endswith("v1/"):
                            api_url = api_url
                        # 移除重复的v1
                        elif "/v1/v1/" in api_url:
                            api_url = api_url.replace("/v1/v1/", "/v1/")
                        # 如果已经包含v1但不以v1/结尾，确保正确格式
                        elif "/v1" in api_url and not api_url.endswith("v1/"):
                            parts = api_url.split("/v1")
                            api_url = parts[0] + "/v1/"
                        
                        # 现在添加chat/completions
                        api_url += "chat/completions"
                    
                    logger.info(f"完整API URL: {api_url}")
                
                # 4. 获取其他参数
                model_params = config.get("model_params", {})
                concurrency = config.get("concurrency", 1)
                test_mode = config.get("test_mode", 1)
                use_gpu = config.get("use_gpu", True)
                
                # 5. 获取API超时设置
                api_timeout = config.get("api_timeout", None)
                
                logger.info(f"开始测试，参数: model={model}, precision={precision}, concurrency={concurrency}, api_timeout={api_timeout}")
                
                # 调用带有单独参数的run_benchmark方法
                result = await self.benchmark_manager.run_benchmark(
                    model=model,
                    precision=precision,
                    api_url=api_url,
                    model_params=model_params,
                    concurrency=concurrency,
                    test_mode=test_mode,
                    use_gpu=use_gpu,
                    api_timeout=api_timeout
                )
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
        
        # 添加调试日志，检查框架信息
        logger.info(f"[_on_test_finished] 测试完成，framework_info存在: {'framework_info' in result}")
        if 'framework_info' in result:
            logger.info(f"[_on_test_finished] 信号发送前的framework_info: {result['framework_info']}")
        
        # 检查result对象属性
        logger.info(f"[_on_test_finished] result对象id: {id(result)}, 类型: {type(result).__name__}")
        logger.info(f"[_on_test_finished] result包含的键: {list(result.keys())}")
        
        # 保存测试结果
        self.benchmark_manager.latest_test_result = result
        
        # 通知插件
        self.plugin_manager.notify_plugins("benchmark_complete", result)
        
        # 检查result的status字段
        if result and isinstance(result, dict) and result.get("status") == "error":
            # 如果status为error，则发送test_error信号
            error_msg = result.get("message", "未知错误")
            logger.warning(f"[_on_test_finished] 检测到测试失败，错误信息: {error_msg}")
            logger.info(f"[_on_test_finished] 即将发送test_error信号...")
            self.test_error.emit(error_msg)
            logger.info(f"[_on_test_finished] test_error信号已发送")
        else:
            # 如果status为success或未指定，则发送test_finished信号
            logger.info(f"[_on_test_finished] 测试成功，即将发送test_finished信号...")
            self.test_finished.emit(result)
            logger.info(f"[_on_test_finished] test_finished信号已发送")
    
    def _on_test_error(self, error: str):
        """
        测试错误处理
        
        Args:
            error: 错误信息
        """
        self.running = False
        
        # 处理可能包含UI提示的错误对象
        error_message = error
        ui_message = None
        ui_detail = None
        ui_type = "error"
        
        # 如果error是字典类型，提取其中的UI相关信息
        if isinstance(error, dict):
            error_message = error.get("message", str(error))
            ui_message = error.get("ui_message")
            ui_detail = error.get("ui_detail")
            ui_type = error.get("ui_type", "error")
            
            # 构建包含UI信息的错误对象
            error_obj = {
                "message": error_message,
                "ui_message": ui_message,
                "ui_detail": ui_detail,
                "ui_type": ui_type
            }
            
            # 通知插件
            self.plugin_manager.notify_plugins("benchmark_error", error_obj)
            
            # 转发测试错误信号，包含UI信息
            self.test_error.emit(error_obj)
        else:
            # 对于普通字符串错误，仍使用原有流程
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
            device_id: 设备ID，如果为None则使用当前设备ID
            nickname: 设备昵称，如果为None则使用当前昵称
            
        Returns:
            bool: 设置是否成功
        """
        try:
            # 保存到全局配置
            self.config.set("benchmark.api_key", api_key)
            
            # 设置API密钥到benchmark_manager
            self.benchmark_manager.api_key = api_key
            self.benchmark_manager.api_client.api_key = api_key
            
            # 设置设备ID和昵称（如果提供）
            if device_id:
                self.config.set("benchmark.device_id", device_id)
                self.benchmark_manager.device_id = device_id
                self.benchmark_manager.api_client.device_id = device_id
            
            if nickname:
                self.config.set("benchmark.nickname", nickname)
                self.benchmark_manager.nickname = nickname
            
            logger.info(f"API密钥设置成功: {api_key[:4]}...")
            return True
        except Exception as e:
            logger.error(f"设置API密钥失败: {str(e)}")
            return False
    
    def encrypt_result(self) -> Dict[str, Any]:
        """
        仅加密当前测试结果并保存到本地，如果已有加密文件则直接使用
        
        Returns:
            Dict[str, Any]: 加密结果，包含状态和消息
        """
        try:
            # 检查是否有测试结果
            if not hasattr(self.benchmark_manager, 'latest_test_result') or self.benchmark_manager.latest_test_result is None:
                return {
                    "status": "error",
                    "message": "没有可加密的测试结果",
                    "ui_message": "加密失败",
                    "ui_detail": "没有可加密的测试结果，请先运行测试。"
                }
            
            # 获取API密钥
            api_key = self.benchmark_manager.api_key
            
            # 检查API密钥
            if not api_key:
                return {
                    "status": "error",
                    "message": "缺少API密钥，无法加密测试结果",
                    "ui_message": "加密失败",
                    "ui_detail": "未设置API密钥，请先设置API密钥后再尝试加密。"
                }
            
            # 检查测试结果中是否已有加密文件路径
            latest_result = self.benchmark_manager.latest_test_result
            if "encrypted_path" in latest_result and os.path.exists(latest_result["encrypted_path"]):
                logger.info(f"测试结果已有加密文件，直接使用: {latest_result['encrypted_path']}")
                return {
                    "status": "success",
                    "message": "使用已存在的加密文件",
                    "encrypted_path": latest_result["encrypted_path"],
                    "original_path": latest_result.get("result_path", ""),
                    "ui_message": "加密状态",
                    "ui_detail": f"测试结果已有加密文件:\n{latest_result['encrypted_path']}\n\n点击确定可以打开保存位置。"
                }
            
            # 添加检查和调试日志，确保framework_info被保留
            logger.info(f"加密前检查latest_result中framework_info存在: {'framework_info' in latest_result}")
            if 'framework_info' in latest_result:
                logger.info(f"加密前latest_result中的framework_info: {latest_result['framework_info']}")
            
            # 检查是否已经有result_path
            if "result_path" not in latest_result or not latest_result["result_path"]:
                logger.warning("结果中没有result_path，需要先保存结果文件")
                # 保存结果，获取result_path
                from src.benchmark.utils.result_handler import result_handler
                result_path = result_handler.save_result(latest_result)
                if result_path:
                    latest_result["result_path"] = result_path
                    logger.info(f"创建了新的原始结果文件: {result_path}")
            else:
                logger.info(f"使用已有的原始结果文件: {latest_result['result_path']}")
            
            # 加密结果
            from src.benchmark.utils.result_handler import result_handler
            original_path, encrypted_path = result_handler.save_encrypted_result(latest_result, api_key)
            
            if encrypted_path and os.path.exists(encrypted_path):
                logger.info(f"测试结果已加密并保存到: {encrypted_path}")
                # 更新测试结果中的加密文件路径
                latest_result["encrypted_path"] = encrypted_path
                return {
                    "status": "success",
                    "message": "测试结果加密成功",
                    "encrypted_path": encrypted_path,
                    "original_path": original_path,
                    "ui_message": "加密成功",
                    "ui_detail": f"测试结果已加密并保存到本地:\n{encrypted_path}\n\n点击确定可以打开保存位置。"
                }
            else:
                logger.error("测试结果加密失败")
                return {
                    "status": "error",
                    "message": "测试结果加密失败",
                    "ui_message": "加密失败",
                    "ui_detail": "测试结果加密失败，请检查加密配置后重试。"
                }
        except Exception as e:
            logger.error(f"加密测试结果失败: {str(e)}")
            return {
                "status": "error",
                "message": f"加密测试结果失败: {str(e)}",
                "ui_message": "加密失败",
                "ui_detail": f"加密测试结果失败: {str(e)}\n\n请检查日志获取详细信息。",
                "can_retry": True
            }
            
    def upload_result(self) -> Dict[str, Any]:
        """
        上传加密的测试结果，优先使用已加密的文件
        
        Returns:
            Dict[str, Any]: 上传结果，包含状态、消息和上传ID
        """
        try:
            # 检查是否有测试结果
            if not hasattr(self.benchmark_manager, 'latest_test_result') or self.benchmark_manager.latest_test_result is None:
                return {
                    "status": "error",
                    "message": "没有可上传的测试结果",
                    "ui_message": "上传失败",
                    "ui_detail": "没有可上传的测试结果，请先运行测试。"
                }
            
            # 获取API密钥和服务器URL
            api_key = self.benchmark_manager.api_key
            server_url = self.benchmark_manager.server_url
            
            # 检查API密钥
            if not api_key:
                return {
                    "status": "error",
                    "message": "缺少API密钥，无法上传测试结果",
                    "ui_message": "上传失败",
                    "ui_detail": "未设置API密钥，请先设置API密钥后再尝试上传。"
                }
            
            # 检查服务器URL
            if not server_url:
                return {
                    "status": "error",
                    "message": "缺少服务器URL，无法上传测试结果",
                    "ui_message": "上传失败",
                    "ui_detail": "未设置服务器URL，请检查配置后再尝试上传。"
                }
            
            # 准备元数据
            metadata = {
                "device_id": self.benchmark_manager.device_id,
                "nickname": self.benchmark_manager.nickname,
                "submitter": self.benchmark_manager.nickname,
                "model_name": self.benchmark_manager.latest_test_result.get("model_name", "未知模型"),
                "hardware_info": self.benchmark_manager.latest_test_result.get("hardware_info", {}),
                "notes": f"从客户端上传的测试结果 - {datetime.now().isoformat()}"
            }
            
            # 构建API URL
            api_url = f"{server_url}/api/v1/benchmark-result/upload"
            
            # 检查是否已经有加密文件
            if "encrypted_path" not in self.benchmark_manager.latest_test_result or not os.path.exists(self.benchmark_manager.latest_test_result["encrypted_path"]):
                logger.info("测试结果中没有加密文件路径，需要先进行加密")
                # 尝试加密
                encrypt_result = self.encrypt_result()
                if encrypt_result.get("status") != "success":
                    logger.error(f"无法加密测试结果: {encrypt_result.get('message', '未知错误')}")
                    return encrypt_result
            else:
                logger.info(f"使用已有的加密文件: {self.benchmark_manager.latest_test_result['encrypted_path']}")
            
            # 上传结果 (使用可能已经存在的加密文件)
            from src.benchmark.utils.result_handler import result_handler
            upload_result = result_handler.upload_encrypted_result(
                self.benchmark_manager.latest_test_result,
                api_key=api_key,
                server_url=api_url,
                metadata=metadata
            )
            
            if upload_result.get("status") == "success":
                logger.info(f"测试结果上传成功，ID: {upload_result.get('upload_id', 'unknown')}")
                return {
                    "status": "success",
                    "message": "测试结果上传成功",
                    "upload_id": upload_result.get('upload_id', 'unknown'),
                    "ui_message": "上传成功",
                    "ui_detail": f"测试结果已成功上传到服务器。\n上传ID: {upload_result.get('upload_id', '未知')}"
                }
            else:
                error_msg = upload_result.get("message", "未知错误")
                logger.error(f"上传测试结果失败: {error_msg}")
                return {
                    "status": "error",
                    "message": f"上传测试结果失败: {error_msg}",
                    "error": error_msg,
                    "ui_message": "上传失败",
                    "ui_detail": f"上传测试结果失败: {error_msg}\n\n您可以稍后重试上传。",
                    "can_retry": True
                }
        except Exception as e:
            logger.error(f"上传测试结果失败: {str(e)}")
            return {
                "status": "error", 
                "message": f"上传测试结果失败: {str(e)}",
                "ui_message": "上传失败",
                "ui_detail": f"上传测试结果失败: {str(e)}\n\n请检查日志获取详细信息。",
                "can_retry": True
            }

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
        try:
            # 检查文件是否存在
            if not os.path.exists(package_path):
                logger.error(f"离线包文件不存在: {package_path}")
                if callback:
                    callback(False, f"离线包文件不存在: {package_path}")
                return
            
            # 获取API密钥
            api_key = self.config.get("benchmark.api_key", "")
            if not api_key:
                logger.error("未配置API密钥，无法解密离线包")
                if callback:
                    callback(False, "未配置API密钥，请先在设置中配置API密钥")
                return
            
            logger.info(f"开始加载离线包: {package_path}")
            
            # 创建异步工作线程，先初始化异步资源，再加载离线包
            async def load_offline_package_with_init():
                logger.debug("离线包加载 - 初始化异步资源")
                # 先初始化异步资源
                if not self.async_initialized:
                    init_success = await self.initialize_async()
                    if not init_success:
                        logger.error("初始化异步资源失败，无法加载离线包")
                        return False
                
                # 加载离线包
                logger.debug(f"离线包加载 - 调用benchmark_manager.load_offline_package, API密钥: {api_key[:4]}...")
                return await self.benchmark_manager.load_offline_package(package_path, api_key)
            
            # 创建异步工作线程
            worker = AsyncWorker(load_offline_package_with_init)
            
            # 连接信号
            if callback:
                def on_finished(result):
                    success = bool(result)
                    message = "离线包加载成功" if success else "离线包加载失败，请检查文件格式或API密钥是否正确"
                    logger.info(f"离线包加载结果: {'成功' if success else '失败'}")
                    callback(success, message)
                
                def on_error(error):
                    logger.error(f"离线包加载错误: {error}")
                    callback(False, f"离线包加载失败: {error}")
                
                worker.finished.connect(on_finished)
                worker.error.connect(on_error)
            
            # 保存工作线程引用并启动
            self.async_workers.append(worker)
            worker.start()
            
        except Exception as e:
            logger.error(f"加载离线包出错: {str(e)}")
            if callback:
                callback(False, f"加载离线包出错: {str(e)}")
            return


# 创建全局实例
benchmark_integration = BenchmarkIntegration() 