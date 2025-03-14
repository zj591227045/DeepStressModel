"""
跑分管理器模块
"""
import os
import json
import time
import uuid
import platform
import psutil
import requests
from datetime import datetime
from typing import Dict, List, Optional, Any, Callable
from src.utils.config import config
from src.utils.logger import setup_logger
from src.monitor.gpu_monitor import gpu_monitor
from src.data.dataset_manager import dataset_manager

# 设置日志记录器
logger = setup_logger("benchmark_manager")


class BenchmarkManager:
    """跑分管理器类"""
    
    def __init__(self):
        """初始化跑分管理器"""
        self.dataset = None
        self.dataset_info = None
        self.running = False
        self.progress_callback = None
        self.server_url = config.get("benchmark.server_url", "http://localhost:8083")
        self.result_dir = os.path.join(os.path.expanduser("~"), ".deepstressmodel", "benchmark_results")
        
        # 确保结果目录存在
        os.makedirs(self.result_dir, exist_ok=True)
    
    def update_dataset(self) -> bool:
        """
        从服务器更新数据集（联网模式）
        
        Returns:
            bool: 更新是否成功
        """
        try:
            # 构建API请求
            url = f"{self.server_url}/api/v1/datasets/latest"
            headers = {"Content-Type": "application/json"}
            
            # 发送请求
            response = requests.get(url, headers=headers)
            response.raise_for_status()
            
            # 解析响应
            data = response.json()
            
            # 下载数据集
            dataset_url = data["download_url"]
            dataset_version = data["version"]
            
            # 保存数据集信息
            self.dataset_info = {
                "version": dataset_version,
                "created_at": data["created_at"],
                "size": data["size"]
            }
            
            # 下载并解密数据集
            self._download_dataset(dataset_url, dataset_version)
            
            # 加载数据集
            self._load_dataset(dataset_version)
            
            logger.info(f"数据集更新成功，版本: {dataset_version}")
            return True
        except Exception as e:
            logger.error(f"更新数据集失败: {str(e)}")
            raise
    
    def upload_dataset(self, file_path: str = None, api_key: str = None) -> bool:
        """
        上传并解密离线数据包（离线模式）
        
        Args:
            file_path: 离线包文件路径
            api_key: API密钥
            
        Returns:
            bool: 上传是否成功
        """
        try:
            if not file_path or not os.path.exists(file_path):
                raise ValueError("无效的数据集文件路径")
            
            if not api_key:
                raise ValueError("API密钥不能为空")
                
            # 获取文件信息
            file_size = os.path.getsize(file_path)
            file_name = os.path.basename(file_path)
            
            # 生成离线版本号
            timestamp = int(time.time() * 1000)
            dataset_version = f"offline_{timestamp}"
            
            # 保存离线包信息（不保存API密钥）
            self.dataset_info = {
                "version": dataset_version,
                "created_at": datetime.now().isoformat(),
                "size": file_size,
                "file_name": file_name,
                "original_path": file_path
            }
            
            # 加载并解密数据集
            success = self._load_offline_dataset(file_path, api_key, dataset_version)
            if not success:
                raise ValueError("解密数据集失败")
            
            logger.info(f"离线数据包加载成功，版本: {dataset_version}，文件: {file_name}")
            return True
        except Exception as e:
            logger.error(f"加载离线数据包失败: {str(e)}")
            raise
    
    def get_dataset_info(self) -> Dict[str, Any]:
        """
        获取当前数据集信息
        
        Returns:
            Dict[str, Any]: 数据集信息
        """
        # 优先使用离线数据集信息
        offline_info = dataset_manager.get_offline_dataset_info()
        if offline_info:
            result = self.dataset_info.copy() if self.dataset_info else {"version": "未知", "created_at": "", "size": 0}
            # 合并离线数据集的详细信息
            result.update({
                "名称": offline_info.get("名称", "未知"),
                "版本": offline_info.get("版本", "未知"),
                "描述": offline_info.get("描述", "无描述"),
                "记录数": offline_info.get("记录数", "0")
            })
            return result
        
        return self.dataset_info or {"version": "未知", "created_at": "", "size": 0}
    
    def is_dataset_loaded(self) -> bool:
        """
        检查数据集是否已加载
        
        Returns:
            bool: 数据集是否已加载
        """
        # 检查离线数据集是否已加载
        if dataset_manager.get_offline_dataset_info() is not None:
            return True
        
        return self.dataset is not None
    
    def run_benchmark(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """
        执行跑分测试
        
        Args:
            config: 测试配置
            
        Returns:
            Dict[str, Any]: 测试结果
        """
        if not self.is_dataset_loaded():
            raise ValueError("数据集未加载")
        
        self.running = True
        start_time = time.time()
        
        try:
            # 1. 环境检查
            self._check_environment()
            
            # 2. 准备测试数据
            test_data = self._prepare_test_data()
            
            # 3. 执行测试
            test_results = self._execute_test(test_data, config)
            
            # 4. 计算性能指标
            metrics = self._calculate_metrics(test_results)
            
            # 5. 收集系统信息
            system_info = self._collect_system_info()
            
            # 6. 生成结果
            end_time = time.time()
            result = {
                "device_id": config["device_id"],
                "nickname": config["nickname"],
                "dataset_version": self.dataset_info["version"],
                "model": config["model"],
                "model_config": config.get("model_config", {}),  # 添加完整的模型配置
                "model_params": config.get("model_params", 0),  # 添加模型参数量
                "precision": config["precision"],
                "framework_config": config["framework_config"],
                "start_time": datetime.fromtimestamp(start_time).isoformat(),
                "end_time": datetime.fromtimestamp(end_time).isoformat(),
                "total_duration": end_time - start_time,
                "metrics": metrics,
                "system_info": system_info,
                "test_results": test_results
            }
            
            # 7. 保存结果
            self._save_result(result)
            
            # 8. 上传结果（如果是联网模式）
            if config["mode"] == "online":
                self._upload_result(result)
            
            return result
        finally:
            self.running = False
    
    def stop_benchmark(self):
        """停止跑分测试"""
        self.running = False
    
    def _download_dataset(self, url: str, version: str):
        """
        下载数据集
        
        Args:
            url: 数据集下载地址
            version: 数据集版本
        """
        # 模拟下载逻辑
        logger.info(f"正在下载数据集，版本: {version}")
        time.sleep(1)  # 模拟下载时间
    
    def _load_dataset(self, version: str, file_path: str = None):
        """
        加载数据集
        
        Args:
            version: 数据集版本
            file_path: 数据集文件路径
        """
        # 模拟加载逻辑
        logger.info(f"正在加载数据集，版本: {version}")
        self.dataset = {"version": version, "data": [], "path": file_path}  # 模拟数据集
    
    def _load_offline_dataset(self, file_path: str, api_key: str, version: str) -> bool:
        """
        加载离线数据包
        
        Args:
            file_path: 离线包文件路径
            api_key: API密钥
            version: 版本号
            
        Returns:
            bool: 加载是否成功
        """
        logger.info(f"正在加载离线数据包，版本: {version}")
        
        # 使用数据集管理器加载并解密离线包
        success = dataset_manager.load_offline_package(file_path, api_key)
        
        if success:
            # 模拟数据集对象，实际上我们使用dataset_manager中的数据
            self.dataset = {"version": version, "path": file_path}
            logger.info(f"离线数据包加载成功")
        else:
            logger.error(f"离线数据包加载失败")
            
        return success
    
    def _check_environment(self):
        """检查环境"""
        # 检查GPU是否可用
        gpu_stats = gpu_monitor.get_stats()
        if not gpu_stats or len(gpu_stats["gpus"]) == 0:
            logger.warning("未检测到可用的GPU")
    
    def _prepare_test_data(self) -> List[Dict[str, Any]]:
        """
        准备测试数据
        
        Returns:
            List[Dict[str, Any]]: 测试数据列表
        """
        # 如果有离线数据集，使用离线数据集
        if dataset_manager.get_offline_dataset_info() is not None:
            # 将所有类别的数据集平铺为一个列表
            all_prompts = []
            
            # 获取所有数据集
            datasets = dataset_manager.get_all_datasets()
            for category, prompts in datasets.items():
                # 为每个提示添加分类标签
                for prompt in prompts:
                    all_prompts.append({
                        "id": len(all_prompts) + 1,
                        "input": prompt,
                        "category": category
                    })
            
            logger.info(f"从离线数据集准备了 {len(all_prompts)} 个测试样本")
            return all_prompts
        
        # 模拟测试数据（兼容旧逻辑）
        return [
            {"id": 1, "input": "这是测试输入1", "expected_output": "这是期望输出1"},
            {"id": 2, "input": "这是测试输入2", "expected_output": "这是期望输出2"},
            # 更多测试数据...
        ]
    
    def _execute_test(self, test_data: List[Dict[str, Any]], config: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        执行测试
        
        Args:
            test_data: 测试数据
            config: 测试配置
            
        Returns:
            List[Dict[str, Any]]: 测试结果列表
        """
        results = []
        total_items = len(test_data)
        
        # 模拟测试执行
        for i, item in enumerate(test_data):
            if not self.running:
                break
            
            # 模拟API调用
            start_time = time.time()
            time.sleep(0.5)  # 模拟处理时间
            end_time = time.time()
            
            # 记录结果
            result = {
                "id": item["id"],
                "input": item["input"],
                "output": "这是模拟输出",
                "input_tokens": 10,
                "output_tokens": 20,
                "duration": end_time - start_time,
                "success": True
            }
            results.append(result)
            
            # 更新进度
            progress = {
                "current": i + 1,
                "total": total_items,
                "percent": (i + 1) / total_items * 100,
                "status": "running",
                "message": f"正在测试 {i + 1}/{total_items}",
                "result": result
            }
            
            # 发送进度更新信号（通过回调函数）
            if hasattr(self, "progress_callback") and callable(self.progress_callback):
                self.progress_callback(progress)
        
        return results
    
    def _calculate_metrics(self, test_results: List[Dict[str, Any]]) -> Dict[str, float]:
        """
        计算性能指标
        
        Args:
            test_results: 测试结果列表
            
        Returns:
            Dict[str, float]: 性能指标
        """
        # 计算总时间和总token数
        total_time = sum(result["duration"] for result in test_results)
        total_input_tokens = sum(result["input_tokens"] for result in test_results)
        total_output_tokens = sum(result["output_tokens"] for result in test_results)
        
        # 计算平均延迟
        avg_latency = total_time / len(test_results) if test_results else 0
        
        # 计算吞吐量（每秒处理的token数）
        throughput = total_output_tokens / total_time if total_time > 0 else 0
        
        # 计算成功率
        success_count = sum(1 for result in test_results if result["success"])
        success_rate = success_count / len(test_results) if test_results else 0
        
        # 计算字符生成速度（假设每个token平均2个字符）
        char_speed = throughput * 2
        
        return {
            "avg_latency": avg_latency,
            "throughput": throughput,
            "success_rate": success_rate,
            "char_speed": char_speed
        }
    
    def _collect_system_info(self) -> Dict[str, Any]:
        """
        收集系统信息
        
        Returns:
            Dict[str, Any]: 系统信息
        """
        # 获取GPU信息
        gpu_stats = gpu_monitor.get_stats()
        gpu_info = []
        if gpu_stats and "gpus" in gpu_stats:
            for gpu in gpu_stats["gpus"]:
                gpu_info.append({
                    "name": gpu.get("name", "未知"),
                    "memory_total": gpu.get("memory_total", 0),
                    "driver_version": gpu.get("driver_version", "未知")
                })
        
        # 获取CPU信息
        cpu_info = {
            "model": platform.processor(),
            "cores": psutil.cpu_count(logical=False),
            "threads": psutil.cpu_count(logical=True)
        }
        
        # 获取内存信息
        memory = psutil.virtual_memory()
        memory_info = {
            "total": memory.total,
            "available": memory.available
        }
        
        # 获取操作系统信息
        os_info = {
            "system": platform.system(),
            "release": platform.release(),
            "version": platform.version()
        }
        
        return {
            "gpu": gpu_info,
            "cpu": cpu_info,
            "memory": memory_info,
            "os": os_info
        }
    
    def _save_result(self, result: Dict[str, Any]):
        """
        保存测试结果
        
        Args:
            result: 测试结果
        """
        # 生成结果文件名
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        filename = f"benchmark_{timestamp}.json"
        filepath = os.path.join(self.result_dir, filename)
        
        # 保存为JSON文件
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        
        logger.info(f"测试结果已保存到: {filepath}")
    
    def _upload_result(self, result: Dict[str, Any]) -> bool:
        """
        上传测试结果（联网模式）
        
        Args:
            result: 测试结果
            
        Returns:
            bool: 上传是否成功
        """
        try:
            # 构建API请求
            url = f"{self.server_url}/api/v1/results"
            headers = {"Content-Type": "application/json"}
            
            # 准备上传数据（移除大型测试结果详情）
            upload_data = result.copy()
            upload_data.pop("test_results", None)
            
            # 发送请求
            response = requests.post(url, headers=headers, json=upload_data)
            response.raise_for_status()
            
            logger.info("测试结果上传成功")
            return True
        except Exception as e:
            logger.error(f"上传测试结果失败: {str(e)}")
            return False
    
    def set_progress_callback(self, callback):
        """
        设置进度回调函数
        
        Args:
            callback: 进度回调函数
        """
        self.progress_callback = callback 