"""
跑分管理器模块，负责管理跑分相关功能
此版本使用分离的模块进行优化
"""
import os
import json
import time
import asyncio
import traceback
from datetime import datetime
from typing import Dict, List, Any, Callable, Optional, Union
import uuid

from src.utils.logger import setup_logger
from src.utils.config import config
from src.monitor.gpu_monitor import gpu_monitor
from src.benchmark.api.benchmark_api_client import BenchmarkAPIClient
from src.benchmark.crypto.data_encryptor import DataEncryptor
from src.benchmark.crypto.signature_manager import SignatureManager

# 导入分离出的模块
from src.benchmark.utils.hardware_info import collect_system_info, get_hardware_info
from src.benchmark.utils.dataset_handler import (
    load_dataset, validate_dataset_format, extract_dataset_info,
    get_dataset_info, is_dataset_loaded, prepare_test_data, load_offline_package
)
from src.benchmark.utils.result_handler import result_handler
from src.benchmark.utils.progress_tracker import progress_tracker
from src.benchmark.utils.test_execution.test_executor import execute_test, calculate_metrics

# 设置日志记录器
logger = setup_logger("benchmark_manager")

class BenchmarkManager:
    """跑分管理器类，负责管理跑分相关功能"""
    
    def __init__(self, config=None):
        """
        初始化跑分管理器
        
        Args:
            config: 配置对象，如果为None则使用全局配置
        """
        # 导入配置
        from src.utils.config import config as global_config
        self.config = config if config is not None else global_config
        
        # 初始化成员变量
        self.dataset = None
        self.dataset_info = None
        self.test_data = None  # 添加test_data属性初始化
        self.running = False
        self.progress_callback = None
        self.dataset_updated = False  # 初始化数据集更新标志为False
        
        # 设置API相关信息
        self.server_url = self.config.get("benchmark.server_url", "http://localhost:8083")
        self.api_key = self.config.get("benchmark.api_key", "")
        self.device_id = self.config.get("benchmark.device_id", str(uuid.uuid4()))
        self.nickname = self.config.get("benchmark.nickname", "未命名设备")
        
        # 设置测试模式：0 = 联网模式，1 = 离线模式
        self.test_mode = self.config.get("benchmark.mode", 1)
        
        # 设置结果目录
        self.result_dir = os.path.join(os.path.expanduser("~"), ".deepstressmodel", "benchmark_results")
        self.datasets_dir = os.path.join("data", "benchmark", "datasets")
        
        # 确保目录存在
        os.makedirs(self.result_dir, exist_ok=True)
        os.makedirs(self.datasets_dir, exist_ok=True)
        
        # 初始化API客户端
        self.api_client = BenchmarkAPIClient(
            server_url=self.server_url,
            api_key=self.api_key
        )
        
        # 设置API客户端的device_id
        self.api_client.device_id = self.device_id
        
        # 初始化时间同步标志
        self.time_synced = False
        
        # 初始化结果处理器
        result_handler.result_dir = self.result_dir
        
        # 初始化进度跟踪器
        progress_tracker.set_callback(self._handle_progress_update)
        
        # 导入数据加密工具
        try:
            from src.data.crypto_utils import DataEncryptor, SignatureManager
            self.data_encryptor = DataEncryptor()
            self.signature_manager = SignatureManager()
        except ImportError:
            logger.warning("无法导入数据加密工具，部分功能可能不可用")
            self.data_encryptor = None
            self.signature_manager = None
        
        logger.info("跑分管理器初始化完成")
    
    async def initialize_async(self):
        """
        异步初始化
        
        Returns:
            bool: 初始化是否成功
        """
        try:
            # 创建结果目录和数据集目录
            os.makedirs(self.result_dir, exist_ok=True)
            os.makedirs(self.datasets_dir, exist_ok=True)
            
            # 根据测试模式执行不同的初始化逻辑
            if self.test_mode == 0 and self.server_url:  # 联网测试模式且服务器URL已设置
                logger.info(f"初始化联网测试模式，服务器URL: {self.server_url}")
                # 在这里不进行服务器连接和设备注册，等待用户手动输入API密钥后再进行
            else:  # 离线测试模式
                logger.info("初始化离线测试模式，不进行服务器连接")
            
            logger.info("跑分管理器初始化完成")
            return True
        except Exception as e:
            logger.error(f"跑分管理器初始化失败: {str(e)}")
            return False
    
    async def _sync_time(self):
        """
        尝试同步时间
        
        Returns:
            bool: 同步是否成功
        """
        try:
            success = await self.api_client.sync_time()
            self.time_synced = success
            if success:
                logger.info("时间同步成功")
            else:
                logger.warning("时间同步失败")
            return success
        except Exception as e:
            logger.warning(f"时间同步失败: {str(e)}")
            self.time_synced = False
            return False
    
    def cleanup(self):
        """
        清理资源
        
        Returns:
            bool: 清理是否成功
        """
        try:
            logger.info("正在清理跑分管理器资源...")
            # 停止正在运行的测试
            if self.running:
                self.stop_benchmark()
            
            # 清理数据集
            self.dataset = None
            self.dataset_info = None
            
            # 关闭API客户端
            asyncio.create_task(self.api_client.close())
            
            logger.info("跑分管理器资源清理完成")
            return True
        except Exception as e:
            logger.error(f"清理跑分管理器资源失败: {str(e)}")
            return False
    
    def set_progress_callback(self, callback: Callable[[Dict[str, Any]], None]):
        """
        设置进度回调函数
        
        Args:
            callback: 进度回调函数，接收一个字典参数，包含进度信息
        """
        self.progress_callback = callback
        # 同时更新进度跟踪器的回调
        progress_tracker.set_callback(self._handle_progress_update)
    
    def _handle_progress_update(self, progress_info: Dict[str, Any]):
        """
        处理来自进度跟踪器的进度更新
        
        Args:
            progress_info: 进度信息
        """
        if self.progress_callback:
            self.progress_callback(progress_info)
    
    async def register_device(self) -> bool:
        """
        注册设备
        
        Returns:
            bool: 注册是否成功
        """
        try:
            # 先尝试同步时间
            await self.api_client.sync_time()
            
            # 注册设备 - 不再收集硬件信息
            result = await self.api_client.register_device(nickname=self.nickname)
            
            # 保存设备ID和API密钥
            self.device_id = result.get("device_id", "")
            self.api_key = result.get("api_key", "")
            
            # 更新配置
            self.config.set("benchmark.device_id", self.device_id)
            self.config.set("benchmark.api_key", self.api_key)
            
            # 更新API客户端和数据加密器
            self.api_client.api_key = self.api_key
            self.data_encryptor.api_key = self.api_key
            
            logger.info(f"设备注册成功，设备ID: {self.device_id}")
            return True
        except Exception as e:
            logger.error(f"设备注册失败: {str(e)}")
            return False
    
    async def authenticate(self) -> bool:
        """
        认证设备
        
        Returns:
            bool: 认证是否成功
        """
        try:
            # 检查API密钥
            if not self.api_key:
                logger.error("API密钥未设置，请先设置API密钥")
                return False
            
            # 认证设备
            result = await self.api_client.authenticate()
            
            # 如果服务器返回了设备ID，更新本地设备ID
            if "device_id" in result and not self.device_id:
                self.device_id = result["device_id"]
                self.config.set("benchmark.device_id", self.device_id)
            
            logger.info("设备认证成功")
            return True
        except Exception as e:
            logger.error(f"设备认证失败: {str(e)}")
            return False
    
    async def get_datasets(self) -> List[Dict[str, Any]]:
        """
        获取数据集列表
        
        Returns:
            List[Dict[str, Any]]: 数据集列表
        """
        try:
            # 检查API密钥
            if not self.api_key:
                logger.error("API密钥未设置，请先设置API密钥")
                return []
            
            # 认证设备
            if not await self.authenticate():
                return []
            
            # 获取数据集列表
            datasets = await self.api_client.get_datasets()
            
            logger.info(f"获取到 {len(datasets)} 个数据集")
            return datasets
        except Exception as e:
            logger.error(f"获取数据集列表失败: {str(e)}")
            return []
    
    async def download_dataset(self, dataset_version: str) -> bool:
        """
        下载数据集
        
        Args:
            dataset_version: 数据集版本
            
        Returns:
            bool: 下载是否成功
        """
        try:
            # 检查API密钥
            if not self.api_key:
                logger.error("API密钥未设置，请先设置API密钥")
                return False
            
            # 认证设备
            if not await self.authenticate():
                return False
            
            # 下载数据集
            dataset_info = await self.api_client.download_dataset(dataset_version)
            
            # 检查下载URL
            download_url = dataset_info.get("download_url")
            if not download_url:
                logger.error("获取数据集下载链接失败")
                return False
            
            # 下载数据集文件
            dataset_data = await self.api_client.download_dataset_file(download_url)
            
            # 保存数据集到datasets目录
            dataset_path = os.path.join(self.datasets_dir, f"dataset_{dataset_version}.json")
            with open(dataset_path, "wb") as f:
                f.write(dataset_data)
            
            # 加载数据集
            self.load_dataset(dataset_path)
            
            # 标记数据集已在本次会话中更新
            self.dataset_updated = True
            
            logger.info(f"数据集下载成功: {dataset_path}")
            return True
        except Exception as e:
            logger.error(f"下载数据集失败: {str(e)}")
            return False
    
    def upload_dataset(self, file_path: str = None) -> bool:
        """
        上传本地数据集（离线模式）
        
        Args:
            file_path: 本地数据集文件路径
            
        Returns:
            bool: 上传是否成功
        """
        try:
            if not file_path or not os.path.exists(file_path):
                logger.error("无效的数据集文件路径")
                return False
                
            # 获取文件信息
            file_size = os.path.getsize(file_path)
            file_name = os.path.basename(file_path)
            
            # 生成离线版本号
            dataset_version = "offline-" + datetime.now().strftime("%Y%m%d%H%M%S")
            
            # 复制数据集文件到datasets目录
            os.makedirs(self.datasets_dir, exist_ok=True)
            
            local_path = os.path.join(self.datasets_dir, f"{dataset_version}-{file_name}")
            with open(file_path, 'rb') as src_file, open(local_path, 'wb') as dst_file:
                dst_file.write(src_file.read())
            
            # 读取数据集文件
            with open(local_path, 'r', encoding='utf-8') as f:
                encrypted_dataset = json.load(f)
            
            # 解密数据集
            self.dataset = self.data_encryptor.decrypt_dataset(encrypted_dataset)
            
            # 保存数据集信息
            self.dataset_info = {
                "version": dataset_version,
                "created_at": datetime.now().isoformat(),
                "size": file_size,
                "file_name": file_name,
                "local_path": local_path
            }
            
            # 标记数据集已在本次会话中更新
            self.dataset_updated = True
            
            logger.info(f"数据集上传成功，版本: {dataset_version}，文件: {file_name}")
            return True
        except Exception as e:
            logger.error(f"上传数据集失败: {str(e)}")
            return False
    
    def get_dataset_info(self) -> Dict[str, Any]:
        """
        获取当前数据集信息
        
        Returns:
            Dict[str, Any]: 数据集信息
        """
        return get_dataset_info(self.dataset, self.dataset_info)
    
    def is_dataset_loaded(self) -> bool:
        """
        检查数据集是否已加载
        
        Returns:
            bool: 数据集是否已加载
        """
        return is_dataset_loaded(self.dataset, self.dataset_updated)
    
    def _standardize_api_url(self, api_url: str) -> str:
        """标准化API URL格式
        
        将API URL转换为标准格式，确保URL包含完整路径
        
        Args:
            api_url (str): 原始API URL
            
        Returns:
            str: 标准化后的API URL
        """
        if not api_url:
            return api_url
            
        # 确保URL包含完整路径
        if "chat/completions" not in api_url:
            # 如果URL不以/结尾，添加/
            if not api_url.endswith("/"):
                api_url += "/"
                
            # 标准化URL格式
            if api_url.endswith("v1/"):
                # URL已经正确格式化为v1/
                pass
            elif "/v1/v1/" in api_url:
                # 修复重复的v1
                api_url = api_url.replace("/v1/v1/", "/v1/")
            elif "/v1" in api_url and not api_url.endswith("v1/"):
                # 确保v1路径正确格式化
                parts = api_url.split("/v1")
                api_url = parts[0] + "/v1/"
                
            # 添加chat/completions路径
            api_url += "chat/completions"
            
        logger.debug(f"标准化API URL: {api_url}")
        return api_url
    
    async def run_benchmark(self, model, precision="FP32", api_url=None, model_params=None, concurrency=1, test_mode=1, use_gpu=True):
        """
        运行跑分测试
        
        Args:
            model (str): 模型名称（警告：此参数仅用于UI显示，API调用必须使用model_config["model"]）
            precision (str): 精度，如FP16、INT8等
            api_url (str): API地址
            model_params (dict): 模型参数
            concurrency (int): 并发数
            test_mode (int): 测试模式，1=在线，2=离线
            use_gpu (bool): 是否启用GPU
            
        Returns:
            dict: 测试结果
        """
        # 添加数据集验证逻辑 - 严格要求必须更新或上传测试数据集
        if not hasattr(self, 'dataset_updated') or not self.dataset_updated:
            error_msg = "测试未开始：请先联网更新数据集或上传测试集，确保使用最新的测试数据"
            logger.error(error_msg)
            return {
                "status": "error", 
                "message": error_msg,
                "ui_message": "请先更新数据集",
                "ui_detail": "为确保测试有效性，每次测试前都需要先联网更新数据集或上传自定义测试集。\n\n请点击「下载数据集」按钮获取最新测试集，或上传自定义测试集后再开始测试。",
                "ui_type": "warning"
            }
        
        # 警告注释
        logger.info("开始运行基准测试: 模型=%s, 精度=%s, 并发数=%s", model, precision, concurrency)
        
        # 检查并标准化API URL
        if not api_url:
            api_url = self.config.get("api_url", "")
            
        # 如果没有API URL，使用模型配置中的URL
        if not api_url and model_params and isinstance(model_params, dict) and "api_url" in model_params:
            api_url = model_params["api_url"]
        
        if not api_url:
            logger.error("缺少API URL")
            raise ValueError("运行测试需要提供API URL")
        
        # 记录开始时间并启动进度跟踪
        progress_tracker.start_test()
        progress_tracker.set_callback(self._handle_progress_update)
        
        # 设置当前数据集名称给进度跟踪器
        dataset_info = self.get_dataset_info()
        if dataset_info and isinstance(dataset_info, dict):
            if "名称" in dataset_info:
                progress_tracker.set_dataset_name(dataset_info["名称"])
            elif "metadata" in dataset_info and "dataset_name" in dataset_info["metadata"]:
                progress_tracker.set_dataset_name(dataset_info["metadata"]["dataset_name"])
            
        # 标准化API URL
        api_url = self._standardize_api_url(api_url)
        logger.info("使用API URL: %s", api_url)
        
        # 设置测试运行状态为True
        self.running = True
        
        try:
            # 确保已加载测试数据
            if self.test_data is None:
                self.test_data = prepare_test_data()
            
            # 如果test_data仍然为空，返回错误
            if self.test_data is None:
                logger.error("测试数据为空，无法执行测试")
                return {"status": "error", "message": "测试数据为空，无法执行测试"}
            
            # 设置测试参数
            model_config = {
                "model": model,
                "test_mode": test_mode
            }
            
            # 处理API URL
            if api_url:
                # 将完整URL保存到model_config中
                model_config["api_url"] = api_url
                logger.info(f"使用API URL: {api_url}")
            
            # 合并模型参数 - 添加类型检查
            if isinstance(model_params, dict):
                model_config.update(model_params)
            else:
                logger.warning(f"跳过model_params更新：不是字典类型，而是{type(model_params).__name__}")
            
            # 执行测试
            config = {
                "model_config": model_config,
                "precision": precision,
                "concurrency": concurrency,
                "use_gpu": use_gpu,
                "api_url": api_url,
                "running": self.running,
                "progress_callback": progress_tracker.update_progress
            }
            
            test_results = await execute_test(self.test_data, config)
            
            # 计算结束时间
            end_time = time.time()
            start_time = progress_tracker.test_start_time
            total_time = end_time - start_time
            
            # 统计结果
            total_tests = len(test_results)
            successful_tests = sum(1 for r in test_results if r.get("status") == "success")
            success_rate = successful_tests / total_tests if total_tests > 0 else 0
            
            # 计算平均延迟和吞吐量
            if successful_tests > 0:
                avg_latency = sum(r.get("latency", 0) for r in test_results) / successful_tests
                avg_throughput = sum(r.get("throughput", 0) for r in test_results) / successful_tests
            else:
                avg_latency = 0
                avg_throughput = 0
            
            # 计算每秒事务数（TPS）
            if total_time > 0:
                tps = total_tests / total_time
            else:
                tps = 0
            
            # 获取数据集信息
            dataset_version = "unknown"
            if isinstance(self.dataset_info, dict):
                if "version" in self.dataset_info:
                    dataset_version = self.dataset_info["version"]
                elif "metadata" in self.dataset_info and "version" in self.dataset_info["metadata"]:
                    dataset_version = self.dataset_info["metadata"]["version"]
            
            # 获取数据集名称
            dataset_name = "标准基准测试"
            if self.dataset_info and isinstance(self.dataset_info, dict):
                if "名称" in self.dataset_info:
                    dataset_name = self.dataset_info["名称"]
                elif "metadata" in self.dataset_info and "dataset_name" in self.dataset_info["metadata"]:
                    dataset_name = self.dataset_info["metadata"]["dataset_name"]
            
            # 统计文本信息
            total_input_chars = sum(len(r.get("input", "")) for r in test_results)
            total_output_chars = sum(len(r.get("output", "")) for r in test_results)
            total_chars = total_input_chars + total_output_chars
            
            # 统计token数量
            total_tokens = sum(r.get("tokens", 0) for r in test_results)
            
            # 计算性能指标
            metrics = calculate_metrics(test_results)
            
            # 计算总持续时间
            duration = total_time
            
            # 计算总字节数（输入+输出字符总数）
            total_bytes = total_input_chars + total_output_chars
            
            # 计算基于token的平均TPS
            avg_token_tps = 0
            if successful_tests > 0:
                token_throughputs = [r.get("token_throughput", 0) for r in test_results if r.get("status") == "success"]
                avg_token_tps = sum(token_throughputs) / len(token_throughputs) if token_throughputs else 0
            
            # 为UI创建datasets结构
            datasets = {
                dataset_name: {
                    "completed": len(test_results),
                    "total": len(test_results),
                    "success_rate": success_rate,
                    "avg_response_time": metrics["latency"],
                    "avg_gen_speed": metrics["throughput"],  # 字符生成速度
                    "total_time": duration,  # 总用时
                    "total_tokens": total_tokens,  # 总token数
                    "total_bytes": total_bytes,  # 总字节数
                    "avg_tps": avg_token_tps  # 使用基于token的吞吐量作为TPS
                }
            }
            
            # 收集系统信息
            system_info = collect_system_info()
            
            # 构建结果
            result = {
                "status": "success",
                "dataset_version": dataset_version,
                "start_time": start_time,
                "end_time": end_time,
                "total_time": total_time,
                "total_tests": total_tests,
                "successful_tests": successful_tests,
                "success_rate": success_rate,
                "avg_latency": avg_latency,
                "avg_throughput": avg_throughput,
                "tps": tps,
                "total_input_chars": total_input_chars,
                "total_output_chars": total_output_chars,
                "total_chars": total_chars,
                "total_tokens": total_tokens,
                "results": test_results,
                "datasets": datasets,
                "metrics": metrics,
                "system_info": system_info,
                "hardware_info": get_hardware_info(),
                "total_duration": duration,
                "avg_tps": avg_token_tps
            }
            
            # 通知进度跟踪器测试完成
            progress_tracker.complete_test(test_results)
            
            # 保存结果
            result_path = result_handler.save_result(result)
            if result_path:
                result["result_path"] = result_path
            
            return result
        except Exception as e:
            logger.error(f"运行基准测试出错: {str(e)}")
            logger.error(traceback.format_exc())
            return {"status": "error", "message": str(e)}
        finally:
            # 无论成功还是失败，都将运行状态设为False
            self.running = False
    
    def stop_benchmark(self):
        """停止跑分测试"""
        if self.running:
            logger.info("正在停止跑分测试...")
            self.running = False
            logger.info("跑分测试已停止")
    
    def load_dataset(self, dataset_path: str) -> bool:
        """
        加载数据集
        
        Args:
            dataset_path: 数据集路径
            
        Returns:
            bool: 加载是否成功
        """
        try:
            dataset = load_dataset(dataset_path)
            if not dataset:
                return False
                
            self.dataset = dataset
            self.dataset_info = extract_dataset_info(dataset)
            self.dataset_updated = True
            
            logger.info(f"成功加载数据集: {dataset_path}")
            return True
        except Exception as e:
            logger.error(f"加载数据集失败: {str(e)}")
            return False
    
    async def get_offline_package(self, dataset_id: str, save_path: str = None) -> bool:
        """
        获取离线测试数据包
        
        Args:
            dataset_id: 数据集ID
            save_path: 保存路径，默认为datasets目录
            
        Returns:
            bool: 获取是否成功
        """
        try:
            # 检查API密钥
            if not self.api_key:
                logger.error("API密钥未设置，请先设置API密钥")
                return False
            
            # 设置API客户端的API密钥
            logger.debug(f"使用API密钥: {self.api_key[:4]}...")
            self.api_client.api_key = self.api_key
            
            # 获取离线包
            logger.debug(f"开始获取离线包，数据集ID: {dataset_id}")
            offline_package = await self.api_client.get_offline_package(dataset_id)
            
            if not offline_package:
                logger.error("获取到的离线包为空")
                return False
                
            logger.debug(f"成功获取离线包，数据结构: {list(offline_package.keys()) if offline_package else '空'}")
            
            # 如果未指定保存路径，使用默认datasets目录
            if not save_path:
                save_path = self.datasets_dir
                logger.debug(f"使用默认保存路径: {save_path}")
            
            # 保存离线包
            logger.debug("开始保存离线包...")
            package_path = await self.api_client.save_offline_package(offline_package, save_path)
            logger.info(f"离线包保存成功: {package_path}")
            
            # 立即加载并解密离线包
            logger.debug("开始加载并解密离线包...")
            if await self.load_offline_package(package_path):
                logger.info("离线包加载并解密成功")
                return True
            else:
                logger.error("离线包加载或解密失败")
                return False
            
        except Exception as e:
            logger.error(f"获取离线包失败: {str(e)}")
            return False
    
    async def load_offline_package(self, package_path: str, api_key: str = None) -> bool:
        """
        加载并解密离线包
        
        Args:
            package_path: 离线包文件路径
            api_key: API密钥，如果未提供则使用当前配置的API密钥
            
        Returns:
            bool: 加载是否成功
        """
        # 如果未提供API密钥，则使用当前配置的API密钥
        if not api_key:
            api_key = self.api_key
        
        success = await load_offline_package(package_path, api_key)
        
        if success:
            # 标记数据集已在本次会话中更新
            self.dataset = {"version": "offline", "file_path": package_path}
            self.dataset_updated = True
        
        return success
    
    def set_api_key(self, api_key: str, device_id: str = None, nickname: str = None) -> bool:
        """
        手动设置API密钥
        
        Args:
            api_key: API密钥
            device_id: 设备ID（可选）
            nickname: 设备名称（可选）
            
        Returns:
            bool: 设置是否成功
        """
        try:
            if not api_key:
                logger.error("API密钥不能为空")
                return False
            
            # 更新API密钥
            self.api_key = api_key
            self.api_client.api_key = api_key
            self.data_encryptor.api_key = api_key
            
            # 更新签名管理器
            self.api_client.signature_manager = SignatureManager(api_key)
            
            # 如果提供了设备ID，也更新
            if device_id:
                self.device_id = device_id
                self.api_client.device_id = device_id
            
            # 如果提供了昵称，也更新
            if nickname:
                self.nickname = nickname
            
            # 更新配置
            self.config.set("benchmark.api_key", api_key)
            if device_id:
                self.config.set("benchmark.device_id", device_id)
            if nickname:
                self.config.set("benchmark.nickname", nickname)
            
            logger.info(f"API密钥设置成功: {api_key[:5]}...")
            return True
        except Exception as e:
            logger.error(f"设置API密钥失败: {str(e)}")
            return False
    
    async def enable_benchmark_module(self) -> bool:
        """
        启用跑分模块，连接服务器并验证API密钥
        
        Returns:
            bool: 启用是否成功
        """
        try:
            # 根据测试模式执行不同的逻辑
            if self.test_mode == 0:  # 联网测试模式
                # 检查服务器URL
                if not self.server_url:
                    logger.error("未设置服务器URL，无法启用联网测试模式")
                    return False
                
                # 同步时间
                if not await self._sync_time():
                    logger.error("时间同步失败，无法启用跑分模块")
                    return False
                
                # 检查API密钥
                if not self.api_key:
                    logger.warning("未设置API密钥，需要先注册或登录")
                    return False
                
                # 验证API密钥
                if not await self.authenticate():
                    logger.error("API密钥验证失败，请检查密钥是否有效")
                    return False
                
                logger.info("联网测试模式跑分模块启用成功")
            else:  # 离线测试模式
                logger.info("离线测试模式跑分模块启用成功")
            
            return True
        except Exception as e:
            logger.error(f"启用跑分模块失败: {str(e)}")
            return False
    
    async def disable_benchmark_module(self) -> bool:
        """
        禁用跑分模块
        
        Returns:
            bool: 禁用是否成功
        """
        try:
            # 如果有测试正在运行，先停止测试
            if self.running:
                self.stop_benchmark()
            
            # 根据测试模式执行不同的逻辑
            if self.test_mode == 0:  # 联网测试模式
                # 这里可以添加一些清理逻辑，如断开与服务器的连接等
                logger.info("联网测试模式跑分模块已禁用")
            else:  # 离线测试模式
                logger.info("离线测试模式跑分模块已禁用")
            
            return True
        except Exception as e:
            logger.error(f"禁用跑分模块失败: {str(e)}")
            return False 