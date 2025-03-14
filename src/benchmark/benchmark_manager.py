"""
跑分管理器模块，负责管理跑分相关功能
"""
import os
import json
import time
import asyncio
import platform
import psutil
from datetime import datetime
from typing import Dict, List, Optional, Any, Callable
from src.utils.logger import setup_logger
from src.utils.config import config
from src.monitor.gpu_monitor import gpu_monitor
from src.benchmark.api.benchmark_api_client import BenchmarkAPIClient
from src.benchmark.crypto.data_encryptor import DataEncryptor
from src.benchmark.crypto.signature_manager import SignatureManager

# 设置日志记录器
logger = setup_logger("benchmark_manager")

class BenchmarkManager:
    """跑分管理器类，负责管理跑分相关功能"""
    
    def __init__(self, config_obj):
        """
        初始化跑分管理器
        
        Args:
            config_obj: 配置对象
        """
        self.config = config_obj
        self.dataset = None
        self.dataset_info = None
        self.running = False
        self.progress_callback = None
        
        # 获取测试模式（0=联网测试，1=离线测试）
        self.test_mode = config_obj.get("benchmark.mode", 0)
        
        # 服务器配置 - 只在联网测试模式下设置服务器URL
        if self.test_mode == 0:  # 联网测试模式
            self.server_url = config_obj.get("benchmark.server_url", "http://localhost:8083")
        else:  # 离线测试模式
            self.server_url = ""
            
        # 从配置中读取API密钥
        self.api_key = config_obj.get("benchmark.api_key", "")
        self.server_public_key = None  # 需要从服务器获取
        
        # 设备信息
        self.device_id = config_obj.get("benchmark.device_id", "")
        self.nickname = config_obj.get("benchmark.nickname", "未命名设备")
        
        # 创建API客户端
        self.api_client = BenchmarkAPIClient(
            server_url=self.server_url,
            api_key=self.api_key,  # 使用从配置中读取的API密钥
            server_public_key=self.server_public_key,
            connect_timeout=config_obj.get("benchmark.connect_timeout", 10),
            max_retries=config_obj.get("benchmark.max_retries", 3)
        )
        
        # 创建数据加密器 - 初始时不设置API密钥
        self.data_encryptor = DataEncryptor(
            api_key="",  # 初始为空，等待用户输入后设置
            server_public_key=self.server_public_key
        )
        
        # 确保结果目录存在
        self.result_dir = os.path.join(os.path.expanduser("~"), ".deepstressmodel", "benchmark_results")
        os.makedirs(self.result_dir, exist_ok=True)
        
        # 不在初始化时直接调用异步方法
        self.time_synced = False
        
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
            
            # 创建结果目录
            os.makedirs(self.result_dir, exist_ok=True)
            
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
            
            # 保存数据集
            dataset_path = os.path.join(self.result_dir, f"dataset_{dataset_version}.json")
            with open(dataset_path, "wb") as f:
                f.write(dataset_data)
            
            # 加载数据集
            self.load_dataset(dataset_path)
            
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
            
            # 复制数据集文件到本地存储
            dataset_dir = os.path.join(self.result_dir, "datasets")
            os.makedirs(dataset_dir, exist_ok=True)
            
            local_path = os.path.join(dataset_dir, f"{dataset_version}-{file_name}")
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
        return self.dataset is not None
    
    async def run_benchmark(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """
        运行跑分测试
        
        Args:
            config: 测试配置
            
        Returns:
            Dict[str, Any]: 测试结果
        """
        try:
            # 检查API密钥（仅在联网模式下需要）
            if self.test_mode == 0 and not self.api_key:
                logger.error("API密钥未设置，请先设置API密钥")
                return {}
            
            # 检查数据集
            if not self.dataset:
                logger.error("数据集未加载，请先加载数据集")
                return {}
            
            # 设置运行标志
            self.running = True
            
            # 初始化结果
            result = {
                "model": config.get("model", "未知模型"),
                "precision": config.get("precision", "FP16"),
                "model_params": config.get("model_params", 0),
                "framework_config": config.get("framework_config", ""),
                "datasets": {},
                "hardware_info": self._get_hardware_info(),
                "start_time": time.time(),
                "end_time": None,
                "duration": 0,
                "errors": []
            }
            
            # 更新进度
            self._update_progress({
                "status": "running",
                "progress": 0,
                "message": "测试开始"
            })
            
            # 执行测试
            start_time = time.time()
            test_results = await self._execute_test(self.dataset, config)
            end_time = time.time()
            
            # 计算总耗时
            total_duration = end_time - start_time
            
            # 计算指标
            metrics = self._calculate_metrics(test_results)
            
            # 构建结果
            result = {
                "status": "success",
                "dataset_version": self.dataset_info["version"],
                "model": config.get("model", "未知模型"),
                "precision": config.get("precision", "未知精度"),
                "model_config": config.get("model_config", {}),
                "model_params": config.get("model_params", 0),
                "framework_config": config.get("framework_config", {}),
                "metrics": metrics,
                "system_info": self._collect_system_info(),
                "total_duration": total_duration,
                "timestamp": int(time.time() * 1000),
                "test_results": test_results
            }
            
            # 保存结果
            result_path = self._save_result(result)
            if result_path:
                result["result_path"] = result_path
            
            # 更新进度
            self._update_progress({
                "status": "completed",
                "progress": 100,
                "message": "测试完成",
                "result": result
            })
            
            # 重置运行状态
            self.running = False
            
            logger.info(f"基准测试完成，总耗时: {total_duration:.2f}秒，平均TPS: {metrics['throughput']:.2f}")
            return result
        except Exception as e:
            self.running = False
            logger.error(f"运行基准测试异常: {str(e)}")
            
            # 更新进度
            self._update_progress({
                "status": "error",
                "progress": 0,
                "message": f"测试异常: {str(e)}"
            })
            
            return {"status": "error", "message": str(e)}
    
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
        # 这里是测试执行的具体逻辑
        # 目前只是一个简单的模拟实现
        
        results = []
        total_items = len(test_data)
        
        for i, item in enumerate(test_data):
            if not self.running:
                break
            
            # 模拟测试执行
            await asyncio.sleep(0.1)
            
            # 生成测试结果
            result = {
                "id": item["id"],
                "input": item["input"],
                "output": "模拟输出",
                "expected_output": item.get("expected_output", ""),
                "latency": 0.1,  # 模拟延迟
                "throughput": 100  # 模拟吞吐量
            }
            
            results.append(result)
            
            # 更新进度
            progress = (i + 1) / total_items * 100
            self._update_progress({
                "progress": progress,
                "current_item": i + 1,
                "total_items": total_items,
                "latency": result["latency"],
                "throughput": result["throughput"],
                "total_time": (i + 1) * 0.1
            })
        
        return results
    
    def _update_progress(self, progress_info: Dict[str, Any]):
        """
        更新进度
        
        Args:
            progress_info: 进度信息
        """
        if self.progress_callback:
            self.progress_callback(progress_info)
    
    def _prepare_test_data(self) -> List[Dict[str, Any]]:
        """
        准备测试数据
        
        Returns:
            List[Dict[str, Any]]: 测试数据
        """
        # 这里应该从数据集中提取测试数据
        # 目前只是一个简单的模拟实现
        
        if not self.dataset:
            return []
        
        # 如果数据集中有测试数据，则使用数据集中的测试数据
        if "test_data" in self.dataset:
            return self.dataset["test_data"]
        
        # 否则，生成模拟测试数据
        return [
            {"id": 1, "input": "这是测试输入1", "expected_output": "这是期望输出1"},
            {"id": 2, "input": "这是测试输入2", "expected_output": "这是期望输出2"},
            {"id": 3, "input": "这是测试输入3", "expected_output": "这是期望输出3"},
            {"id": 4, "input": "这是测试输入4", "expected_output": "这是期望输出4"},
            {"id": 5, "input": "这是测试输入5", "expected_output": "这是期望输出5"}
        ]
    
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
    
    def export_offline_result(self, result: Dict[str, Any], export_path: str = None) -> str:
        """
        导出离线测试结果
        
        Args:
            result: 测试结果
            export_path: 导出路径，如果为None则使用默认路径
            
        Returns:
            str: 结果文件路径，失败则返回空字符串
        """
        try:
            # 收集当前测试设备的硬件信息
            hardware_info = self._collect_system_info()
            logger.info("已收集测试设备硬件信息用于结果导出")
            
            # 准备导出数据
            export_data = {
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
                "hardware_info": hardware_info,
                "hardware_fingerprint": self._generate_hardware_fingerprint(hardware_info),
                "test_type": "benchmark",
                "total_duration": result["total_duration"],
                "avg_tps": result["metrics"]["throughput"],
                "timestamp": int(time.time() * 1000),
                "api_key": self.api_key  # 包含API密钥以便服务器验证
            }
            
            # 转换为JSON
            export_json = json.dumps(export_data, ensure_ascii=False)
            
            # 加密数据
            encrypted_data = self.data_encryptor.encrypt_data(export_json.encode('utf-8'))
            
            # 生成结果文件名
            if not export_path:
                timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
                export_file = f"benchmark_result_{timestamp}.dat"
                export_path = os.path.join(self.result_dir, export_file)
            
            # 保存加密结果
            with open(export_path, 'wb') as f:
                f.write(encrypted_data)
            
            logger.info(f"离线测试结果已导出到: {export_path}")
            return export_path
        except Exception as e:
            logger.error(f"导出离线测试结果失败: {str(e)}")
            return ""
    
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
            save_path: 保存路径，默认为结果目录
            
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
            
            # 如果未指定保存路径，使用默认结果目录
            if not save_path:
                save_path = self.result_dir
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
                logger.info("离线包解密并加载成功")
                return True
            else:
                logger.error("离线包解密或加载失败")
                return False
                
        except Exception as e:
            logger.error(f"加载离线包失败: {str(e)}")
            return False 