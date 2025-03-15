"""
跑分管理器模块，负责管理跑分相关功能
"""
import os
import json
import time
import asyncio
import platform
import psutil
import traceback
from datetime import datetime
from typing import Dict, List, Optional, Any, Callable, Union, Tuple
from src.utils.logger import setup_logger
from src.utils.config import config
from src.monitor.gpu_monitor import gpu_monitor
from src.benchmark.api.benchmark_api_client import BenchmarkAPIClient
from src.benchmark.crypto.data_encryptor import DataEncryptor
from src.benchmark.crypto.signature_manager import SignatureManager
import uuid
from src.utils.token_counter import token_counter

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
            # 检查环境
            self._check_environment()
            
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
        if not self.dataset:
            return None
            
        try:
            # 如果是离线数据集格式，从数据集管理器获取信息
            if isinstance(self.dataset, dict) and self.dataset.get("version") == "offline":
                # 引入数据集管理器模块
                from src.data.dataset_manager import dataset_manager
                
                # 获取离线数据集信息
                offline_info = dataset_manager.get_offline_dataset_info()
                if offline_info:
                    # 确保返回的元数据包含正确的字段
                    metadata = offline_info.get("metadata", {})
                    
                    return {
                        'metadata': metadata,
                        'size': offline_info.get("size", 0),
                        '名称': metadata.get('dataset_name', '未知'),
                        '版本': metadata.get('dataset_version', '未知'),
                        '描述': offline_info.get('描述', '无描述'),
                        '记录数': offline_info.get('记录数', '0')
                    }
            
            # 如果是原始数据集格式
            if isinstance(self.dataset, dict) and 'metadata' in self.dataset:
                return {
                    'metadata': self.dataset['metadata'],
                    'size': len(str(self.dataset)),
                    'test_cases': self.dataset.get('test_cases', []),
                    'description': self.dataset.get('description', '无描述')
                }
            
            # 如果是解密后的数据集格式
            return {
                'metadata': {
                    'dataset_name': self.dataset_info.get('名称', '未知'),
                    'dataset_version': self.dataset_info.get('版本', '未知'),
                    'package_format': '3.0',
                    'download_time': int(time.time() * 1000)
                },
                'size': self.dataset_info.get('size', 0),
                'test_cases': self.dataset.get('test_cases', []),
                'description': self.dataset.get('description', '无描述')
            }
        except Exception as e:
            logger.error(f"获取数据集信息失败: {str(e)}")
            return {
                'metadata': {
                    'dataset_name': '未知',
                    'dataset_version': '未知',
                    'package_format': '未知',
                    'download_time': 0
                },
                'size': 0,
                'test_cases': [],
                'description': '获取数据集信息失败'
            }
    
    def is_dataset_loaded(self) -> bool:
        """
        检查数据集是否已加载
        
        Returns:
            bool: 数据集是否已加载
        """
        # 检查离线数据集是否已加载
        from src.data.dataset_manager import dataset_manager
        if dataset_manager.get_offline_dataset_data() is not None:
            logger.info("检测到通过dataset_manager加载的数据集")
            return True
        
        # 只检查dataset，不再回退到标准测试数据集
        return self.dataset is not None and self.dataset_updated
    
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
        
        # 记录开始时间
        self.test_start_time = time.time()
        logger.debug(f"记录测试开始时间: {self.test_start_time}")
        
        # 标准化API URL
        api_url = self._standardize_api_url(api_url)
        logger.info("使用API URL: %s", api_url)
        
        # 设置测试运行状态为True
        self.running = True
        
        try:
            # 确保已加载测试数据
            if self.test_data is None:
                self.test_data = self._prepare_test_data()
            
            # 如果test_data仍然为空，返回错误
            if self.test_data is None:
                logger.error("测试数据为空，无法执行测试")
                return {"status": "error", "message": "测试数据为空，无法执行测试"}
            
            # 获取总共要处理的项数
            test_items = []
            
            # 用于处理自定义数据集格式，支持字典和列表格式
            if isinstance(self.test_data, dict):
                # 字典格式，直接获取 "items" 或 所有 key 的 "items"
                if "items" in self.test_data:
                    test_items.extend(self.test_data["items"])
                else:
                    # 检查每个 key 是否有 items
                    for k, v in self.test_data.items():
                        if isinstance(v, dict) and "items" in v:
                            test_items.extend(v["items"])
            elif isinstance(self.test_data, list):
                # 列表格式，直接使用
                test_items = self.test_data
            
            total_items = len(test_items)
            
            if total_items == 0:
                logger.warning("测试项目数量为0，无法执行测试")
                return {"status": "error", "message": "测试项目数量为0，无法执行测试"}
            
            # 在测试开始时初始化进度信息，让UI可以立即显示测试状态
            if self.progress_callback:
                initial_progress = {
                    "status": "initializing",
                    "message": f"正在准备测试数据，共{total_items}个测试项",
                    "current_item": 0,
                    "total_items": total_items,
                    "latency": 0,
                    "throughput": 0,
                    "total_time": 0,
                    "total_tokens": 0,
                    "total_bytes": 0,
                    "token_throughput": 0
                }
                self._update_progress(initial_progress)
            
            # 记录开始时间
            start_time = time.time()
            
            # 设置测试参数
            model_config = {
                "model": model,
                "test_mode": test_mode
            }
            
            # 处理API URL
            if api_url:
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
                
                # 将完整URL保存到model_config中
                model_config["api_url"] = api_url
                logger.info(f"使用API URL: {api_url}")
            
            # 合并模型参数 - 添加类型检查
            if isinstance(model_params, dict):
                model_config.update(model_params)
            else:
                logger.warning(f"跳过model_params更新：不是字典类型，而是{type(model_params).__name__}")
            
            # 执行测试
            test_results = await self._execute_test(
                test_data=test_items,
                config={
                    "model_config": model_config,
                    "precision": precision,
                    "concurrency": concurrency,
                    "use_gpu": use_gpu,
                    "api_url": api_url
                }
            )
            
            # 计算结束时间
            end_time = time.time()
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
            metrics = self._calculate_metrics(test_results)
            
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
                "system_info": self._collect_system_info(),
                "total_duration": duration,
                "avg_tps": avg_token_tps
            }
            
            # 保存结果
            result_path = self._save_result(result)
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
    
    async def _execute_test(self, test_data: List[Dict[str, Any]], config: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        执行测试
        
        Args:
            test_data: 测试数据
            config: 测试配置
            
        Returns:
            List[Dict[str, Any]]: 测试结果
        """
        #######################################################################
        # 重要提示: 本函数及其下游process_item函数中，模型名称必须使用
        # model_config["model"]字段，而不是model_config["name"]字段!
        # model_config["name"]字段只用于UI显示，不能用于API调用。
        # 使用错误的字段会导致API请求404错误，如:
        # "model \"ollama-llama3:8b-instruct-fp16\" not found"
        #######################################################################
        
        # 获取API URL - 关键修改
        api_url = config.get("api_url")
        if not api_url:
            logger.error("缺少API URL，无法执行测试")
            raise ValueError("缺少API URL，无法执行测试")
        
        # 确保URL包含完整路径
        if not "chat/completions" in api_url:
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
        
        logger.info(f"开始测试，目标API URL: {api_url}")
        
        # 从config中获取其他参数
        model_config = config.get("model_config", {})
        precision = config.get("precision", "FP16")
        use_gpu = config.get("use_gpu", True)
        
        # 获取并记录当前的硬件环境信息 - 只获取GPU服务器信息
        try:
            hardware_info = self._get_hardware_info()
            logger.info("测试目标服务器硬件信息:")
            logger.info(f"CPU: {hardware_info.get('cpu', '未知')}")
            logger.info(f"内存: {hardware_info.get('memory', '未知')}")
            logger.info(f"系统: {hardware_info.get('system', '未知')}")
            logger.info(f"GPU: {hardware_info.get('gpu', '未知')}")
            logger.info(f"硬件ID: {hardware_info.get('id', '未知')}")
        except Exception as e:
            logger.warning(f"获取硬件环境信息失败: {e}")
        
        # 这里是测试执行的具体逻辑
        results = []
        total_items = 0
        
        # 记录测试数据类型以便调试
        logger.debug(f"测试数据类型: {type(test_data).__name__}")
        
        # 检查test_data是否为字典或列表，并相应处理
        if isinstance(test_data, dict):
            # 如果是字典，尝试访问可能的数据字段
            logger.debug(f"测试数据是字典类型，键值: {list(test_data.keys())}")
            
            if "data" in test_data and isinstance(test_data["data"], list):
                test_items = test_data["data"]
                total_items = len(test_items)
                logger.info(f"从字典数据集中提取到 {total_items} 条测试项")
            elif "version" in test_data and "file_path" in test_data:
                logger.debug(f"检测到数据集引用格式: version={test_data.get('version')}, file_path={test_data.get('file_path')}")
                
                # 处理离线包格式
                logger.info("检测到离线包格式，尝试提取测试数据")
                try:
                    from src.data.dataset_manager import dataset_manager
                    offline_data = dataset_manager.get_offline_dataset_data()
                    if offline_data and isinstance(offline_data, list):
                        test_items = offline_data
                        total_items = len(test_items)
                        logger.info(f"从离线数据集中提取到 {total_items} 条测试项")
                    else:
                        logger.error("无法从离线包中提取有效测试数据")
                        test_items = []
                        total_items = 0
                except Exception as e:
                    logger.error(f"处理离线包数据失败: {e}")
                    test_items = []
                    total_items = 0
            else:
                # 无法识别的字典格式
                logger.error(f"无法识别的测试数据格式，键值: {list(test_data.keys())}")
                test_items = []
                total_items = 0
        elif isinstance(test_data, list):
            # 如果直接是列表，直接使用
            test_items = test_data
            total_items = len(test_items)
            logger.info(f"直接使用列表数据集，包含 {total_items} 条测试项")
        else:
            # 无法处理的数据类型
            logger.error(f"无法处理的测试数据类型: {type(test_data)}")
            test_items = []
            total_items = 0
        
        if total_items == 0:
            logger.warning("没有有效的测试数据，返回空结果")
            return results

        # 获取配置中的并发数，默认为1（顺序执行）
        concurrency = config.get("concurrency", 1)
        try:
            # 从全局配置获取默认并发数
            from src.utils.config import config as global_config
            default_concurrency = global_config.get("test.default_concurrency", 1)
            max_concurrency = global_config.get("test.max_concurrency", 9999)
            # 如果未指定并发数，使用默认值
            if concurrency <= 0:
                concurrency = default_concurrency
            # 限制最大并发数
            concurrency = min(concurrency, max_concurrency)
        except Exception as e:
            logger.warning(f"获取并发设置失败，使用默认值1: {e}")
            concurrency = 1

        logger.info(f"测试将使用并发数: {concurrency}")
        
        # 导入需要的模块用于API调用
        import aiohttp
        import json
        import time
        
        # 创建一个执行单个测试项的协程函数
        async def process_item(index, item):
            if not self.running:
                return None
            
            try:
                # 确保item是字典类型
                if not isinstance(item, dict):
                    logger.warning(f"跳过非字典类型的测试项 #{index}: {type(item)}")
                    return None
                
                # 获取测试输入
                input_text = item.get("text", item.get("input", ""))
                item_id = item.get("id", f"item-{index}")
                
                # 记录开始时间
                start_time = time.time()
                
                #######################################################################
                # 重要提示: API请求中的模型名称必须使用model_config["model"]字段
                # 而不是model_config["name"]字段!
                # 使用错误的字段会导致API请求404错误
                #######################################################################
                
                # 获取正确的模型名称 - 从model_config["model"]中获取，而不是使用默认的model参数或name字段
                model_config = config.get("model_config", {})
                
                # 优先使用model_config中的model字段 - 不要使用name字段，否则会导致API调用失败
                if model_config and "model" in model_config:
                    model_name = model_config["model"]
                    logger.info(f"使用model_config['model']作为模型名称: {model_name}")
                else:
                    # 后备使用config中的model参数
                    model_name = config.get("model", "gpt-3.5-turbo")
                    logger.warning(f"未找到model_config['model']，使用默认model参数: {model_name}")
                
                # 确保不误用name字段
                if model_config and "name" in model_config and "model" not in model_config:
                    logger.warning(f"警告: model_config中存在'name'字段({model_config['name']})，但找不到'model'字段。'name'字段是展示用的，不能用于API调用!")
                    
                request_data = {
                    "model": model_name,  # 使用正确的模型名称，不要使用model_config["name"]
                    "messages": [
                        {"role": "user", "content": input_text}
                    ],
                    "temperature": model_config.get("temperature", 0.7) if model_config else 0.7
                }
                
                # 如果配置中有其他参数，也加入请求
                if model_config:
                    if "max_tokens" in model_config:
                        request_data["max_tokens"] = model_config["max_tokens"]
                    if "top_p" in model_config:
                        request_data["top_p"] = model_config["top_p"]
                
                # 记录更详细的API调用信息 - 添加这部分日志
                logger.info(f"测试项 #{index} 调用API: URL={api_url}, 模型={model_name}")
                logger.debug(f"测试项 #{index} 请求头: {{'Content-Type': 'application/json'}}")
                # 仅记录请求体的摘要，避免日志过大
                content_summary = input_text[:50] + "..." if len(input_text) > 50 else input_text
                # 添加更详细的请求信息
                logger.debug(f"测试项 #{index} 完整请求数据: model={model_name}, temperature={request_data.get('temperature')}, max_tokens={request_data.get('max_tokens')}, top_p={request_data.get('top_p')}")
                logger.debug(f"测试项 #{index} 请求体摘要: 模型={model_name}, 输入={content_summary}")
                
                logger.debug(f"测试项 #{index} 发送请求: {input_text[:50]}...")
                
                # 实际调用API
                async with aiohttp.ClientSession() as session:
                    try:
                        # 记录更详细的API调用信息
                        logger.debug(f"测试项 #{index} 发送请求到: {api_url}")
                        logger.debug(f"测试项 #{index} 请求数据: {json.dumps(request_data)[:100]}...")
                        
                        async with session.post(
                            api_url, 
                            json=request_data,
                            headers={"Content-Type": "application/json"},
                            timeout=30  # 设置超时时间为30秒
                        ) as response:
                            # 记录结束时间
                            end_time = time.time()
                            latency = end_time - start_time
                            
                            # 计算吞吐量（字符数/秒）
                            input_length = len(input_text)
                            throughput = input_length / latency if latency > 0 else 0
                            
                            if response.status == 200:
                                # 成功获取响应
                                response_data = await response.json()
                                
                                # 提取模型输出
                                output_text = ""
                                if "choices" in response_data and len(response_data["choices"]) > 0:
                                    output_text = response_data["choices"][0].get("message", {}).get("content", "")
                                
                                logger.debug(f"测试项 #{index} 收到响应: 状态码={response.status}, 延迟={latency:.4f}秒")
                                
                                # 使用token_counter计算token数量
                                input_tokens = token_counter.count_tokens(input_text, model_name)
                                output_tokens = token_counter.count_tokens(output_text, model_name)
                                total_tokens = input_tokens + output_tokens
                                
                                # 计算基于token的吞吐量（tokens/秒）
                                token_throughput = total_tokens / latency if latency > 0 else 0
                                
                                # 构造测试结果
                                return {
                                    "id": item_id,
                                    "input": input_text,
                                    "output": output_text,
                "expected_output": item.get("expected_output", ""),
                                    "latency": latency,
                                    "throughput": throughput,  # 保留原有的字符吞吐量
                                    "token_throughput": token_throughput,  # 添加基于token的吞吐量
                                    "input_tokens": input_tokens,
                                    "output_tokens": output_tokens,
                                    "tokens": total_tokens,
                                    "status": "success",
                                    "timestamp": int(time.time() * 1000)
                                }
                            else:
                                # API调用失败 - 添加更详细的错误日志
                                error_text = await response.text()
                                logger.warning(f"测试项 #{index} API调用失败: URL={api_url}, 状态码={response.status}, 错误={error_text}")
                                return {
                                    "id": item_id,
                                    "input": input_text,
                                    "error": f"API调用失败: 状态码={response.status}, 错误={error_text}",
                                    "latency": latency,
                                    "throughput": 0,
                                    "status": "error",
                                    "timestamp": int(time.time() * 1000)
                                }
                    except asyncio.TimeoutError:
                        # 超时错误 - 添加更详细的错误日志
                        logger.warning(f"测试项 #{index} API调用超时: URL={api_url}, 超时阈值=30秒")
                        return {
                            "id": item_id,
                            "input": input_text,
                            "error": "API调用超时",
                            "latency": 30.0,  # 使用超时时间作为延迟
                            "throughput": 0,
                            "status": "timeout",
                            "timestamp": int(time.time() * 1000)
                        }
                    except Exception as e:
                        # 其他异常 - 添加更详细的错误日志
                        logger.error(f"测试项 #{index} 请求异常: URL={api_url}, 错误类型={type(e).__name__}, 错误={str(e)}")
                        return {
                            "id": item_id,
                            "input": input_text,
                            "error": f"请求异常: {str(e)}",
                            "latency": time.time() - start_time,
                            "throughput": 0,
                            "status": "error",
                            "timestamp": int(time.time() * 1000)
                        }
            except Exception as e:
                logger.error(f"处理测试项 #{index} 失败: {e}")
                logger.error(traceback.format_exc())
                return {
                    "id": item.get("id", f"item-{index}"),
                    "input": item.get("text", item.get("input", "")),
                    "error": str(e),
                    "latency": 0,
                    "throughput": 0,
                    "status": "error",
                    "timestamp": int(time.time() * 1000)
                }

        # 采用分批执行的方式，避免一次创建过多协程
        # 使用设置的并发数，但确保不超过测试项总数
        batch_size = min(concurrency, total_items)  
        # 如果批次大小较大，设置一个合理的进度更新频率
        update_frequency = min(batch_size, max(1, total_items // 5))  # 确保至少5次进度更新
        logger.info(f"使用实际并发数: {batch_size}, 进度更新频率: 每处理 {update_frequency} 个项目")
        completed = 0
        valid_results = []

        # 在开始执行测试前先更新一次进度为1%，确保显示"测试进行中"状态
        self._update_progress({
            "progress": 1,  # 设为1%而不是0%，确保显示"测试进行中"
            "current_item": 0,
            "total_items": total_items,
            "latency": 0,
            "throughput": 0,
            "total_time": time.time() - start_time if 'start_time' in locals() else 0,
            "total_tokens": 0,
            "total_bytes": 0,
            "token_throughput": 0
        })

        # 分批处理所有测试项
        for batch_start in range(0, total_items, batch_size):
            if not self.running:
                logger.info("测试已停止，中断执行")
                break
                
            batch_end = min(batch_start + batch_size, total_items)
            batch_items = test_items[batch_start:batch_end]
            batch_indices = list(range(batch_start, batch_end))
            
            logger.info(f"处理批次 {batch_start//batch_size + 1}/{(total_items-1)//batch_size + 1}, 项目范围: {batch_start+1}-{batch_end}")
            
            # 如果批次大小较大，则分段处理并更新进度
            if batch_size > update_frequency:
                for segment_start in range(0, len(batch_items), update_frequency):
                    segment_end = min(segment_start + update_frequency, len(batch_items))
                    segment_items = batch_items[segment_start:segment_end]
                    segment_indices = batch_indices[segment_start:segment_end]
                    
                    # 创建当前段的所有测试协程
                    tasks = [process_item(i, item) for i, item in zip(segment_indices, segment_items)]
                    
                    # 并发执行当前段的所有测试
                    segment_results = await asyncio.gather(*tasks)
                    
                    # 过滤掉None结果并添加到结果列表
                    segment_valid_results = [r for r in segment_results if r is not None]
                    valid_results.extend(segment_valid_results)
                    
                    # 更新完成数量
                    completed += len(segment_valid_results)
                    
                    # 更新总体进度
                    progress = completed / total_items * 100
                    self._update_progress({
                        "progress": progress,
                        "current_item": completed,
                        "total_items": total_items,
                        "latency": sum(r.get("latency", 0) for r in segment_valid_results) / len(segment_valid_results) if segment_valid_results else 0,
                        "throughput": sum(r.get("throughput", 0) for r in segment_valid_results) / len(segment_valid_results) if segment_valid_results else 0,
                        "total_time": time.time() - start_time if 'start_time' in locals() else 0,
                        "total_tokens": sum(r.get("tokens", 0) for r in segment_valid_results) if segment_valid_results else 0,
                        "total_bytes": sum(len(r.get("input", "")) for r in segment_valid_results) if segment_valid_results else 0,
                        "token_throughput": sum(r.get("token_throughput", 0) for r in segment_valid_results) / len(segment_valid_results) if segment_valid_results else 0
                    })
                    
                    logger.info(f"完成段 {segment_start//update_frequency + 1}/{(len(batch_items)-1)//update_frequency + 1}, 总进度: {progress:.1f}%")
            else:
                # 创建当前批次的所有测试协程
                tasks = [process_item(i, item) for i, item in zip(batch_indices, batch_items)]
                
                # 并发执行当前批次的所有测试
                batch_results = await asyncio.gather(*tasks)
                
                # 过滤掉None结果并添加到结果列表
                batch_valid_results = [r for r in batch_results if r is not None]
                valid_results.extend(batch_valid_results)
                
                # 更新完成数量
                completed += len(batch_valid_results)
                
                # 更新总体进度
                progress = completed / total_items * 100
                self._update_progress({
                    "progress": progress,
                    "current_item": completed,
                    "total_items": total_items,
                    "latency": sum(r.get("latency", 0) for r in batch_valid_results) / len(batch_valid_results) if batch_valid_results else 0,
                    "throughput": sum(r.get("throughput", 0) for r in batch_valid_results) / len(batch_valid_results) if batch_valid_results else 0,
                    "total_time": time.time() - start_time if 'start_time' in locals() else 0,
                    "total_tokens": sum(r.get("tokens", 0) for r in batch_valid_results) if batch_valid_results else 0,
                    "total_bytes": sum(len(r.get("input", "")) for r in batch_valid_results) if batch_valid_results else 0,
                    "token_throughput": sum(r.get("token_throughput", 0) for r in batch_valid_results) / len(batch_valid_results) if batch_valid_results else 0
                })
                
                logger.info(f"完成批次 {batch_start//batch_size + 1}/{(total_items-1)//batch_size + 1}, 进度: {progress:.1f}%")
        
        return valid_results
    
    def _update_progress(self, progress_info: Dict[str, Any]):
        """
        更新进度信息
        
        Args:
            progress_info: 进度信息
        """
        # 添加调试日志
        logger.debug(f"BenchmarkManager: 更新进度信息: {progress_info}")
        
        if self.progress_callback:
            # 获取数据集名称
            dataset_name = "标准基准测试"
            if self.dataset_info and isinstance(self.dataset_info, dict):
                if "名称" in self.dataset_info:
                    dataset_name = self.dataset_info["名称"]
                elif "metadata" in self.dataset_info and "dataset_name" in self.dataset_info["metadata"]:
                    dataset_name = self.dataset_info["metadata"]["dataset_name"]
            
            # 创建格式化的进度信息，添加datasets结构以供UI使用
            formatted_progress = progress_info.copy()
            
            # 计算总耗时
            total_duration = progress_info.get("total_time", 0)
            
            # 如果total_time为0，从测试开始时间计算
            if (total_duration == 0 or total_duration is None) and hasattr(self, 'test_start_time'):
                current_time = time.time()
                total_duration = current_time - self.test_start_time
                logger.debug(f"BenchmarkManager: 从start_time计算总耗时: {total_duration}")
            
            # 生成状态信息
            progress_percent = progress_info.get("progress", 0)
            completed = progress_info.get("current_item", 0)
            total = progress_info.get("total_items", 0)
            
            # 根据进度百分比设置状态文本
            if progress_percent == 0:
                status = "准备测试中..."
            elif progress_percent < 100:
                # 确保即使是很小的进度也显示为测试进行中
                status = f"测试进行中 ({completed}/{total})"
                logger.debug(f"更新测试进度: {progress_percent:.1f}%, 状态: {status}")
            else:
                status = "测试完成"
                
            # 添加状态字段
            formatted_progress["status"] = status
            
            # 添加datasets结构
            formatted_progress["datasets"] = {
                dataset_name: {
                    "completed": progress_info.get("current_item", 0),
                    "total": progress_info.get("total_items", 0),
                    "success_rate": 1.0,  # 默认所有项目都成功
                    "avg_response_time": progress_info.get("latency", 0),
                    "avg_gen_speed": progress_info.get("throughput", 0),  # 字符生成速度
                    "total_time": total_duration,  # 更新总用时
                    "total_duration": total_duration,  # 明确添加total_duration字段
                    "total_tokens": progress_info.get("total_tokens", 0),  # 总token数
                    "total_bytes": progress_info.get("total_bytes", 0),  # 总字节数
                    "avg_tps": progress_info.get("token_throughput", progress_info.get("throughput", 0))  # 使用token吞吐量作为TPS
                }
            }
            
            # 记录发送的数据
            logger.debug(f"BenchmarkManager: 发送格式化进度数据: {formatted_progress}")
            
            # 调用回调函数
            self.progress_callback(formatted_progress)
    
    def _prepare_test_data(self) -> List[Dict[str, Any]]:
        """
        准备测试数据
        
        Returns:
            List[Dict[str, Any]]: 测试数据
        """
        # 首先尝试从dataset_manager获取数据
        from src.data.dataset_manager import dataset_manager
        offline_data = dataset_manager.get_offline_dataset_data()
        if offline_data and isinstance(offline_data, list) and len(offline_data) > 0:
            logger.info(f"从dataset_manager获取到 {len(offline_data)} 条测试数据")
            return offline_data
        
        # 如果数据集中有测试数据，则使用数据集中的测试数据
        if self.dataset and isinstance(self.dataset, dict) and "data" in self.dataset:
            data = self.dataset["data"]
            if isinstance(data, list) and len(data) > 0:
                logger.info(f"从数据集中获取到 {len(data)} 条测试数据")
                return data
        
        # 不再生成模拟测试数据，如果没有有效数据，就返回空列表
        logger.error("未找到有效测试数据，请先获取离线数据集")
        return []
    
    def _calculate_metrics(self, test_results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        计算性能指标
        
        Args:
            test_results: 测试结果
            
        Returns:
            Dict[str, Any]: 性能指标
        """
        if not test_results:
            return {
                "throughput": 0,
                "latency": 0,
                "gpu_utilization": 0,
                "memory_utilization": 0
            }
        
        # 计算平均延迟和吞吐量
        latencies = [result.get("latency", 0) for result in test_results]
        throughputs = [result.get("throughput", 0) for result in test_results]
        
        avg_latency = sum(latencies) / len(latencies) if latencies else 0
        avg_throughput = sum(throughputs) / len(throughputs) if throughputs else 0
        
        # 获取GPU利用率
        gpu_utilization = 0
        memory_utilization = 0
        
        try:
            gpu_stats = gpu_monitor.get_stats()
            if gpu_stats and hasattr(gpu_stats, 'gpus') and gpu_stats.gpus:
                # 计算所有GPU的平均利用率
                gpu_utilization = sum(gpu.get("util", 0) for gpu in gpu_stats.gpus) / len(gpu_stats.gpus)
                # 计算所有GPU的平均显存利用率
                memory_utilization = sum(
                    gpu.get("memory_used", 0) / max(gpu.get("memory_total", 1), 1) * 100 
                    for gpu in gpu_stats.gpus
                ) / len(gpu_stats.gpus)
        except Exception as e:
            logger.error(f"计算GPU指标失败: {str(e)}")
        
        return {
            "throughput": avg_throughput,
            "latency": avg_latency,
            "gpu_utilization": gpu_utilization,
            "memory_utilization": memory_utilization
        }
    
    def _check_environment(self):
        """检查环境"""
        # 不再检查GPU是否可用，因为这对于跑分模块来说没有意义
        logger.info("跳过GPU可用性检查，不影响跑分功能")
    
    def _collect_system_info(self) -> Dict[str, Any]:
        """
        收集系统信息
        
        Returns:
            Dict[str, Any]: 系统信息
        """
        system_info = {
            "device_type": "desktop",  # 默认为桌面设备
            "app_version": "1.0.0",    # 应用版本
            "os_info": {
                "system": platform.system(),
                "release": platform.release(),
                "version": platform.version(),
                "platform": platform.platform(),
                "machine": platform.machine(),
                "architecture": platform.architecture()[0]
            },
            "cpu_info": {
                "brand": platform.processor(),
                "cores": psutil.cpu_count(logical=False),
                "threads": psutil.cpu_count(logical=True),
                "frequency": psutil.cpu_freq().current if psutil.cpu_freq() else 0
            },
            "memory_info": {
                "total": psutil.virtual_memory().total,
                "available": psutil.virtual_memory().available,
                "percent": psutil.virtual_memory().percent
            },
            "gpu_info": {
                "gpus": []
            },
            "network_info": {
                "hostname": platform.node()
            },
            "python_info": {
                "version": platform.python_version(),
                "implementation": platform.python_implementation(),
                "compiler": platform.python_compiler()
            },
            "timestamp": int(time.time() * 1000)
        }
        
        # 获取GPU信息
        try:
            gpu_stats = gpu_monitor.get_stats()
            if gpu_stats and hasattr(gpu_stats, 'gpus'):
                system_info["gpu_info"]["gpus"] = gpu_stats.gpus
        except Exception as e:
            logger.error(f"获取GPU信息失败: {str(e)}")
        
        return system_info
    
    def _get_hardware_info(self) -> Dict[str, Any]:
        """
        获取硬件信息，从GPU监控的SSH目标收集服务器信息
        
        Returns:
            Dict[str, Any]: 硬件信息
        """
        # 这里明确只获取GPU服务器的硬件信息，而不是本地设备
        hardware_info = {}
        
        try:
            logger.info("开始从GPU监控的SSH目标获取GPU服务器硬件信息...")
            # 获取GPU监控的统计信息
            gpu_stats = gpu_monitor.get_stats()
            
            if gpu_stats:
                logger.info("成功获取GPU服务器统计信息")
                logger.debug(f"GPU统计信息类型: {type(gpu_stats).__name__}")
                
                # 收集CPU信息
                cpu_info = "未知"
                try:
                    if hasattr(gpu_stats, 'cpu_info'):
                        cpu_info = gpu_stats.cpu_info
                        logger.debug(f"从GPU服务器获取到CPU信息: {cpu_info}")
                    else:
                        # 尝试通过SSH获取CPU信息
                        if hasattr(gpu_monitor, '_execute_command'):
                            logger.debug("尝试通过SSH命令获取GPU服务器CPU信息...")
                            cpu_cmd_result = gpu_monitor._execute_command("cat /proc/cpuinfo | grep 'model name' | head -n1 | cut -d':' -f2")
                            if cpu_cmd_result and cpu_cmd_result.strip():
                                cpu_info = cpu_cmd_result.strip()
                                logger.debug(f"通过SSH命令获取到GPU服务器CPU信息: {cpu_info}")
                except Exception as e:
                    logger.warning(f"获取GPU服务器CPU信息时出错: {e}")
                
                hardware_info["cpu"] = cpu_info
                logger.debug(f"已获取GPU服务器CPU信息: {cpu_info}")
                
                # 收集内存信息
                memory_info = f"{gpu_stats.total_memory}GB" if hasattr(gpu_stats, 'total_memory') and gpu_stats.total_memory > 0 else "未知"
                hardware_info["memory"] = memory_info
                logger.debug(f"已获取GPU服务器内存信息: {memory_info}")
                
                # 收集系统信息 - 尝试执行多种命令获取系统信息，以兼容不同系统包括unraid
                system_info = ""
                try:
                    if hasattr(gpu_monitor, '_execute_command'):
                        logger.debug("使用SSH执行命令获取GPU服务器系统信息...")
                        
                        # 尝试多种系统信息获取命令
                        commands = [
                            "lsb_release -d | cut -f2",                  # 标准Linux发行版
                            "cat /etc/os-release | grep PRETTY_NAME | cut -d'\"' -f2",  # 大多数现代Linux
                            "cat /etc/unraid-version 2>/dev/null",       # unRAID专用
                            "uname -a",                                  # 通用Unix/Linux
                            "hostnamectl | grep 'Operating System' | cut -d: -f2"  # systemd系统
                        ]
                        
                        for cmd in commands:
                            logger.debug(f"尝试执行: {cmd}")
                            cmd_result = gpu_monitor._execute_command(cmd)
                            if cmd_result and cmd_result.strip():
                                system_info = cmd_result.strip()
                                logger.debug(f"成功获取GPU服务器系统信息: {system_info}")
                                break
                                
                        if not system_info:
                            logger.warning("所有系统检测命令均未返回有效结果")
                            system_info = "未知Linux/Unix系统"
                except Exception as e:
                    logger.warning(f"获取GPU服务器系统信息时出错: {e}")
                    system_info = "未知"
                
                hardware_info["system"] = system_info
                logger.debug(f"已获取GPU服务器系统信息: {system_info}")
                
                # 收集GPU信息
                gpus = []
                if hasattr(gpu_stats, 'gpus') and gpu_stats.gpus:
                    logger.debug(f"检测到GPU服务器上有 {len(gpu_stats.gpus)} 个GPU")
                    for i, gpu in enumerate(gpu_stats.gpus):
                        gpu_name = gpu.get('info', 'Unknown GPU')
                        # 修复显卡内存单位问题：将MB转换为GB
                        memory_mb = int(gpu.get('memory_total', 0))
                        memory_gb = memory_mb / 1024  # 将MB转换为GB
                        gpu_str = f"{gpu_name} {memory_gb:.1f}GB"
                        gpus.append(gpu_str)
                        logger.debug(f"GPU服务器GPU {i+1}: {gpu_str} (原始内存值: {memory_mb}MB)")
                
                if gpus:
                    # 统计相同GPU的数量
                    gpu_counts = {}
                    for gpu in gpus:
                        gpu_counts[gpu] = gpu_counts.get(gpu, 0) + 1
                    
                    # 构建GPU信息字符串
                    gpu_info_parts = []
                    for gpu, count in gpu_counts.items():
                        if count > 1:
                            gpu_info_parts.append(f"{gpu} *{count}")
                        else:
                            gpu_info_parts.append(gpu)
                    
                    gpu_info = " , ".join(gpu_info_parts)
                    hardware_info["gpu"] = gpu_info
                    logger.debug(f"已获取GPU服务器GPU信息: {gpu_info}")
                else:
                    hardware_info["gpu"] = "未知"
                    logger.debug("未检测到GPU服务器GPU信息，设置为'未知'")
                
                # 生成唯一硬件ID
                hardware_id = self._generate_hardware_fingerprint(hardware_info)
                hardware_info["id"] = hardware_id
                hardware_info["source"] = "gpu_server"  # 明确标记数据来源
                logger.debug(f"已生成GPU服务器硬件ID: {hardware_id}")
                
                # 输出完整的硬件信息
                logger.info("成功获取GPU服务器硬件信息，详细内容如下:")
                logger.info(f"CPU: {hardware_info['cpu']}")
                logger.info(f"内存: {hardware_info['memory']}")
                logger.info(f"系统: {hardware_info['system']}")
                logger.info(f"GPU: {hardware_info['gpu']}")
                logger.info(f"硬件ID: {hardware_info['id']}")
            else:
                logger.warning("无法获取GPU服务器统计信息，将使用本地系统信息作为备用")
                # 如果无法获取GPU统计信息，使用本地系统信息作为备用
                system_info = self._collect_system_info()
                hardware_info["cpu"] = system_info["cpu_info"]["brand"]
                hardware_info["memory"] = f"{int(system_info['memory_info']['total'] / (1024*1024*1024))}GB"
                hardware_info["system"] = f"{system_info['os_info']['system']} {system_info['os_info']['release']}"
                hardware_info["gpu"] = "未知"
                hardware_info["id"] = self._generate_hardware_fingerprint(hardware_info)
                hardware_info["source"] = "local"  # 明确标记数据来源
                
                logger.warning("使用本地系统信息作为备用，而非GPU服务器信息。这是不正确的，请检查GPU监控配置。")
                logger.info("备用硬件信息详细内容如下:")
                logger.info(f"CPU: {hardware_info['cpu']}")
                logger.info(f"内存: {hardware_info['memory']}")
                logger.info(f"系统: {hardware_info['system']}")
                logger.info(f"GPU: {hardware_info['gpu']}")
                logger.info(f"硬件ID: {hardware_info['id']}")
        except Exception as e:
            logger.error(f"获取GPU服务器硬件信息失败: {str(e)}")
            logger.error("将使用默认未知值")
            hardware_info = {
                "cpu": "未知",
                "memory": "未知",
                "system": "未知",
                "gpu": "未知",
                "id": "unknown-" + str(int(time.time())),
                "source": "error"  # 明确标记数据来源
            }
        
        return hardware_info
    
    def _save_result(self, result: Dict[str, Any]) -> str:
        """
        保存测试结果
        
        Args:
            result: 测试结果
            
        Returns:
            str: 结果文件路径
        """
        try:
            # 生成结果文件名
            timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
            result_file = f"benchmark_result_{timestamp}.json"
            result_path = os.path.join(self.result_dir, result_file)
            
            # 在保存前记录硬件信息
            if "hardware_info" in result:
                logger.info("保存结果文件中包含以下硬件信息:")
                hardware_info = result["hardware_info"]
                logger.info(f"CPU: {hardware_info.get('cpu', '未知')}")
                logger.info(f"内存: {hardware_info.get('memory', '未知')}")
                logger.info(f"系统: {hardware_info.get('system', '未知')}")
                logger.info(f"GPU: {hardware_info.get('gpu', '未知')}")
                logger.info(f"硬件ID: {hardware_info.get('id', '未知')}")
            else:
                logger.warning("结果中未包含硬件信息！")
            
            # 保存结果
            with open(result_path, 'w', encoding='utf-8') as f:
                json.dump(result, f, ensure_ascii=False, indent=2)
            
            logger.info(f"测试结果已保存到: {result_path}")
            return result_path
        except Exception as e:
            logger.error(f"保存测试结果失败: {str(e)}")
            return ""
    
    async def _upload_result(self, result: Dict[str, Any]) -> bool:
        """
        上传测试结果
        
        Args:
            result: 测试结果
            
        Returns:
            bool: 上传是否成功
        """
        try:
            # 检查设备ID和API密钥
            if not self.device_id or not self.api_key:
                logger.error("设备ID或API密钥未设置，请先注册设备")
                return False
            
            # 认证设备
            if not await self.authenticate():
                return False
            
            # 收集当前测试设备的硬件信息
            hardware_info = self._collect_system_info()
            logger.info("已收集测试设备硬件信息用于结果上传")
            
            # 准备上传数据
            upload_data = {
                "device_id": self.device_id,
                "nickname": self.nickname,
                "dataset_version": result["dataset_version"],
                "model": result["model"],
                "precision": result["precision"],
                "model_config": result.get("model_config", {}),
                "model_params": result.get("model_params", 0),
                "framework_config": result.get("framework_config", {}),
                "metrics": result["metrics"],
                "system_info": result["system_info"],
                "test_type": "benchmark",
                "total_duration": result["total_duration"],
                "avg_tps": result["metrics"]["throughput"]
            }
            
            # 上传结果
            try:
                response = await self.api_client.submit_result(upload_data, hardware_info)
                
                # 保存排名信息
                if "rankings" in response:
                    result["rankings"] = response["rankings"]
                    
                    # 更新结果文件
                    if "result_path" in result and os.path.exists(result["result_path"]):
                        with open(result["result_path"], 'w', encoding='utf-8') as f:
                            json.dump(result, f, ensure_ascii=False, indent=2)
                
                logger.info("测试结果上传成功")
                return True
            except Exception as e:
                logger.error(f"测试结果上传失败: {str(e)}")
                return False
        except Exception as e:
            logger.error(f"上传测试结果异常: {str(e)}")
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
    
    def import_offline_dataset(self, file_path: str) -> bool:
        """
        导入离线数据集
        
        Args:
            file_path: 数据集文件路径
            
        Returns:
            bool: 导入是否成功
        """
        try:
            if not os.path.exists(file_path):
                logger.error(f"数据集文件不存在: {file_path}")
                return False
            
            # 读取加密数据集文件
            with open(file_path, 'rb') as f:
                encrypted_data = f.read()
            
            # 解密数据集
            try:
                # 使用数据加密器解密
                decrypted_data = self.data_encryptor.decrypt_data(encrypted_data)
                
                # 解析数据集
                dataset_json = json.loads(decrypted_data.decode('utf-8'))
                
                # 验证数据集格式
                if not self._validate_dataset_format(dataset_json):
                    logger.error("数据集格式无效")
                    return False
                
                # 保存数据集
                self.dataset = dataset_json
                self.dataset_info = self._extract_dataset_info(dataset_json)
                
                logger.info(f"成功导入离线数据集: {self.dataset_info.get('name')}, 版本: {self.dataset_info.get('version')}")
                return True
            except Exception as e:
                logger.error(f"解密数据集失败，请检查API密钥是否正确: {str(e)}")
                return False
        except Exception as e:
            logger.error(f"导入离线数据集失败: {str(e)}")
            return False
    
    def _validate_dataset_format(self, dataset: Dict[str, Any]) -> bool:
        """
        验证数据集格式
        
        Args:
            dataset: 数据集
            
        Returns:
            bool: 格式是否有效
        """
        # 检查必要字段
        required_fields = ["version", "name", "data", "metadata"]
        for field in required_fields:
            if field not in dataset:
                logger.error(f"数据集缺少必要字段: {field}")
                return False
        
        # 检查数据字段
        if not isinstance(dataset["data"], list) or len(dataset["data"]) == 0:
            logger.error("数据集的data字段必须是非空列表")
            return False
        
        return True
    
    def _extract_dataset_info(self, dataset: Dict[str, Any]) -> Dict[str, Any]:
        """
        提取数据集信息
        
        Args:
            dataset: 数据集
            
        Returns:
            Dict[str, Any]: 数据集信息
        """
        return {
            "name": dataset.get("name", "未知数据集"),
            "version": dataset.get("version", "未知版本"),
            "description": dataset.get("description", ""),
            "item_count": len(dataset.get("data", [])),
            "created_at": dataset.get("metadata", {}).get("created_at", ""),
            "published_at": dataset.get("metadata", {}).get("published_at", "")
        }
    
    def _generate_hardware_fingerprint(self, hardware_info: Dict[str, Any]) -> str:
        """
        生成硬件指纹
        
        Args:
            hardware_info: 硬件信息
            
        Returns:
            str: 硬件指纹
        """
        try:
            # 将硬件信息转换为JSON字符串
            hardware_str = json.dumps(hardware_info, sort_keys=True)
            
            # 使用SHA-256生成指纹
            import hashlib
            fingerprint = hashlib.sha256(hardware_str.encode()).hexdigest()
            
            return fingerprint
        except Exception as e:
            logger.error(f"生成硬件指纹异常: {str(e)}")
            raise
    
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
        try:
            # 如果未提供API密钥，则使用当前配置的API密钥
            if not api_key:
                api_key = self.api_key
                
            # 检查API密钥
            if not api_key:
                logger.error("API密钥未设置，请先设置API密钥")
                return False
            
            # 设置API客户端的API密钥
            logger.debug(f"使用API密钥进行解密: {api_key[:4]}...")
            self.api_client.api_key = api_key
            
            # 引入数据集管理器模块
            from src.data.dataset_manager import dataset_manager
            
            # 使用数据集管理器解密离线包
            success = dataset_manager.load_offline_package(package_path, api_key)
            
            if success:
                # 离线包解密并加载成功
                # 更新数据集信息
                dataset_info = dataset_manager.get_offline_dataset_info()
                if dataset_info:
                    self.dataset_info = {
                        "version": f"offline-{int(time.time())}",
                        "created_at": datetime.now().isoformat(),
                        "file_name": os.path.basename(package_path),
                        "名称": dataset_info.get("名称", "未知"),
                        "版本": dataset_info.get("版本", "未知"),
                        "描述": dataset_info.get("描述", "无描述"),
                        "记录数": dataset_info.get("记录数", "0")
                    }
                
                # 标记数据集已加载
                self.dataset = {"version": "offline", "file_path": package_path}
                
                # 标记数据集已在本次会话中更新
                self.dataset_updated = True
                
                logger.info("离线包解密并加载成功")
                return True
            else:
                logger.error("离线包解密或加载失败")
                return False
                
        except Exception as e:
            logger.error(f"加载离线包失败: {str(e)}")
            return False 