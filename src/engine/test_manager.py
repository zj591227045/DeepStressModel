"""
测试管理器模块，负责管理并发测试任务
"""
import asyncio
import time
import random
import uuid
import os
import traceback
from typing import Dict, List, Tuple, Optional, Callable
from dataclasses import dataclass
from PyQt6.QtCore import QObject, pyqtSignal
from src.utils.logger import setup_logger
from src.engine.api_client import APIClient, APIResponse
from src.utils.config import config

logger = setup_logger("test_manager")

@dataclass
class TestTask:
    """测试任务数据类"""
    dataset_name: str
    prompts: List[str]  # 改为列表，存储多个prompt
    weight: int
    concurrency: int

@dataclass
class TestProgress:
    """测试进度数据类"""
    test_task_id: str
    total_tasks: int
    completed_tasks: int
    successful_tasks: int
    failed_tasks: int
    avg_response_time: float
    avg_generation_speed: float
    avg_tps: float = 0.0  # 添加平均TPS属性
    last_error: str = ""
    dataset_stats: Dict[str, Dict] = None
    
    def __post_init__(self):
        if self.dataset_stats is None:
            self.dataset_stats = {}
    
    @property
    def progress_percentage(self) -> float:
        """计算进度百分比"""
        if self.total_tasks == 0:
            return 0.0
        return (self.completed_tasks / self.total_tasks) * 100
    
    def update(self, dataset_name: str, response: APIResponse):
        """更新进度"""
        self.completed_tasks += 1
        
        # 确保数据集统计信息存在
        if dataset_name not in self.dataset_stats:
            self.dataset_stats[dataset_name] = {
                "total": 0,
                "successful": 0,
                "failed": 0,
                "total_time": 0.0,
                "total_tokens": 0,
                "total_chars": 0,
                "current_speed": 0.0,
                "error_count": 0  # 添加错误计数
            }
        
        stats = self.dataset_stats[dataset_name]
        stats["total"] += 1
        
        if response.success:
            self.successful_tasks += 1
            stats["successful"] += 1
            stats["total_time"] += response.duration
            stats["total_tokens"] += response.total_tokens
            stats["total_chars"] += response.total_chars
            
            # 更新数据集平均值
            if stats["successful"] > 0:
                stats["avg_response_time"] = stats["total_time"] / stats["successful"]
                stats["avg_generation_speed"] = stats["total_chars"] / stats["total_time"] if stats["total_time"] > 0 else 0
                stats["avg_tps"] = stats["total_tokens"] / stats["total_time"] if stats["total_time"] > 0 else 0
                stats["current_speed"] = response.generation_speed
            
            # 更新总体平均值
            total_time = sum(s["total_time"] for s in self.dataset_stats.values() if s["successful"] > 0)
            total_chars = sum(s["total_chars"] for s in self.dataset_stats.values())
            total_tokens = sum(s["total_tokens"] for s in self.dataset_stats.values())
            
            if total_time > 0:
                self.avg_response_time = total_time / self.successful_tasks
                self.avg_generation_speed = total_chars / total_time
                self.avg_tps = total_tokens / total_time
        else:
            self.failed_tasks += 1
            stats["failed"] += 1
            stats["error_count"] += 1  # 增加错误计数
            self.last_error = response.error_msg

class TestManager(QObject):
    """测试管理器类"""
    # 定义信号
    progress_updated = pyqtSignal(TestProgress)
    result_received = pyqtSignal(str, APIResponse)
    
    def __init__(self):
        super().__init__()
        self.running = False
        self.test_task_id = None
        self.progress = None
    
    def _create_api_client(self, model_config: dict) -> APIClient:
        """创建API客户端"""
        return APIClient(
            api_url=model_config["api_url"],
            api_key=model_config["api_key"],
            model=model_config["model"],
            timeout=config.get("test.timeout", 30),
            max_retries=config.get("test.retry_count", 3),
            max_tokens=model_config.get("max_tokens", 2048),
            temperature=model_config.get("temperature", 0.7),
            top_p=model_config.get("top_p", 0.9)
        )
    
    def _update_progress(self, dataset_name: str, response: APIResponse, error_msg: str = ""):
        """更新测试进度"""
        try:
            logger.debug(f"[DEBUG] 开始更新测试进度: dataset={dataset_name}, success={response.success}")
            self.progress.completed_tasks += 1
            
            # 确保数据集统计信息存在
            if dataset_name not in self.progress.dataset_stats:
                logger.debug(f"[DEBUG] 初始化数据集 {dataset_name} 的统计信息")
                self.progress.dataset_stats[dataset_name] = {
                    "total": 0,
                    "successful": 0,
                    "failed": 0,
                    "total_time": 0.0,
                    "total_tokens": 0,
                    "total_chars": 0,
                    "avg_response_time": 0.0,
                    "avg_generation_speed": 0.0,
                    "start_time": time.time()
                }
            
            stats = self.progress.dataset_stats[dataset_name]
            stats["total"] += 1
            
            if response.success:
                logger.debug(f"[DEBUG] 成功任务: dataset={dataset_name}, duration={response.duration:.2f}s")
                self.progress.successful_tasks += 1
                stats["successful"] += 1
                stats["total_time"] += response.duration
                stats["total_tokens"] += response.total_tokens
                stats["total_chars"] += response.total_chars
                
                # 更新数据集平均值
                if stats["successful"] > 0:
                    stats["avg_response_time"] = stats["total_time"] / stats["successful"]
                    stats["avg_generation_speed"] = stats["total_chars"] / stats["total_time"] if stats["total_time"] > 0 else 0
                    stats["avg_tps"] = stats["total_tokens"] / stats["total_time"] if stats["total_time"] > 0 else 0
                    logger.debug(f"[DEBUG] 数据集 {dataset_name} 统计更新: avg_time={stats['avg_response_time']:.2f}s, speed={stats['avg_generation_speed']:.1f}字符/秒")
                
                # 更新总体平均值
                n = self.progress.successful_tasks
                if n > 0:
                    self.progress.avg_response_time = (
                        (self.progress.avg_response_time * (n - 1) + response.duration) / n
                    )
                    self.progress.avg_generation_speed = (
                        (self.progress.avg_generation_speed * (n - 1) + response.generation_speed) / n
                    )
                    self.progress.avg_tps = (
                        (self.progress.avg_tps * (n - 1) + response.total_tokens / response.duration) / n
                    )
                logger.debug(f"[DEBUG] 总体统计更新: avg_time={self.progress.avg_response_time:.2f}s, speed={self.progress.avg_generation_speed:.1f}字符/秒")
            else:
                logger.debug(f"[DEBUG] 失败任务: dataset={dataset_name}, error={error_msg or response.error_msg}")
                self.progress.failed_tasks += 1
                stats["failed"] += 1
                self.progress.last_error = error_msg or response.error_msg
            
            # 发送进度更新信号
            progress_percent = self.progress.progress_percentage
            logger.debug(
                f"[DEBUG] 发送进度更新信号: completed={self.progress.completed_tasks}/{self.progress.total_tasks} "
                f"({progress_percent:.1f}%), success={self.progress.successful_tasks}, "
                f"failed={self.progress.failed_tasks}"
            )
            self.progress_updated.emit(self.progress)
            logger.debug("[DEBUG] 进度更新信号已发送")
            
        except Exception as e:
            logger.error(f"[ERROR] 更新进度时发生错误: {e}", exc_info=True)
            raise
    
    async def _worker(self, worker_id: str, task_queue: asyncio.Queue,
                     result_queue: asyncio.Queue, api_client: APIClient,
                     log_file: str):
        """工作协程"""
        try:
            while True:
                task = await task_queue.get()
                if task is None:
                    logger.info(f"工作协程 {worker_id} 收到停止信号")
                    # 记录工作协程停止日志
                    with open(log_file, 'a', encoding='utf-8') as f:
                        f.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] 工作协程 {worker_id} 收到停止信号\n")
                    task_queue.task_done()
                    break
                
                dataset_name, prompt = task
                try:
                    # 记录开始处理任务日志
                    with open(log_file, 'a', encoding='utf-8') as f:
                        f.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {worker_id} 开始处理任务:\n")
                        f.write(f"- 数据集: {dataset_name}\n")
                        f.write(f"- Prompt: {prompt[:100]}...\n")
                    
                    response = await api_client.generate(prompt)
                    
                    # 记录任务完成日志
                    with open(log_file, 'a', encoding='utf-8') as f:
                        f.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {worker_id} 完成任务:\n")
                        f.write(f"- 成功: {response.success}\n")
                        if response.success:
                            f.write(f"- 响应时间: {response.duration:.2f}s\n")
                            f.write(f"- 生成字符数: {response.total_chars}\n")
                            f.write(f"- 生成Token数: {response.total_tokens}\n")
                        else:
                            f.write(f"- 错误: {response.error_msg}\n")
                        f.write("\n")
                    
                    await result_queue.put((dataset_name, response))
                except Exception as e:
                    logger.error(f"任务处理失败: {e}", exc_info=True)
                    # 记录任务失败日志
                    with open(log_file, 'a', encoding='utf-8') as f:
                        f.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {worker_id} 任务处理失败: {e}\n\n")
                    await result_queue.put((dataset_name, APIResponse(success=False, error_msg=str(e))))
                finally:
                    task_queue.task_done()
                    
        except Exception as e:
            logger.error(f"工作协程 {worker_id} 异常退出: {e}", exc_info=True)
            # 记录工作协程异常退出日志
            with open(log_file, 'a', encoding='utf-8') as f:
                f.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] 工作协程 {worker_id} 异常退出: {e}\n")
                f.write(traceback.format_exc() + "\n")
        finally:
            logger.info(f"工作协程 {worker_id} 结束")
            # 记录工作协程结束日志
            with open(log_file, 'a', encoding='utf-8') as f:
                f.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] 工作协程 {worker_id} 结束\n")
    
    async def _result_handler(self, result_queue: asyncio.Queue,
                            progress: TestProgress,
                            progress_callback=None,
                            log_file: str = None):
        """结果处理协程"""
        try:
            while True:
                result = await result_queue.get()
                if result is None:
                    logger.info("[DEBUG] 结果处理协程收到停止信号")
                    # 记录结果处理协程停止日志
                    if log_file:
                        with open(log_file, 'a', encoding='utf-8') as f:
                            f.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] 结果处理协程收到停止信号\n")
                    result_queue.task_done()
                    break
                
                dataset_name, response = result
                progress.update(dataset_name, response)
                
                # 发送结果接收信号
                self.result_received.emit(dataset_name, response)
                logger.debug(f"[DEBUG] 发送结果接收信号: dataset={dataset_name}, success={response.success}")
                
                if progress_callback:
                    progress_callback(progress)
                
                # 记录进度更新日志
                if log_file:
                    with open(log_file, 'a', encoding='utf-8') as f:
                        f.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] 进度更新:\n")
                        f.write(f"- 数据集: {dataset_name}\n")
                        f.write(f"- 完成进度: {progress.progress_percentage:.1f}%\n")
                        f.write(f"- 平均响应时间: {progress.avg_response_time:.2f}s\n")
                        f.write(f"- 平均生成速度: {progress.avg_generation_speed:.2f}字/秒\n\n")
                
                result_queue.task_done()
                
        except Exception as e:
            logger.error(f"结果处理协程异常退出: {e}", exc_info=True)
            # 记录结果处理协程异常日志
            if log_file:
                with open(log_file, 'a', encoding='utf-8') as f:
                    f.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] 结果处理协程异常退出: {e}\n")
                    f.write(traceback.format_exc() + "\n")
        finally:
            logger.info("[DEBUG] 结果处理协程结束")
            # 记录结果处理协程结束日志
            if log_file:
                with open(log_file, 'a', encoding='utf-8') as f:
                    f.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] 结果处理协程结束\n")
    
    async def run_test(self, test_task_id: str, tasks: List[TestTask], progress_callback=None, model_config: dict = None):
        """运行测试任务"""
        try:
            logger.info(f"[DEBUG] 开始运行测试 (ID: {test_task_id})...")
            
            # 计算总权重和总并发数
            total_weight = sum(task.weight for task in tasks)
            total_concurrency = sum(task.concurrency for task in tasks)
            logger.info(f"[DEBUG] 总权重: {total_weight}, 总并发数: {total_concurrency}")
            
            # 创建日志文件
            log_dir = os.path.join("data", "logs", "tests")
            os.makedirs(log_dir, exist_ok=True)
            logger.debug(f"创建日志目录: {log_dir}")
            log_file = os.path.join(log_dir, f"{test_task_id}.log")
            logger.debug(f"生成日志文件路径: {log_file}")
            
            # 写入测试开始信息
            with open(log_file, 'w', encoding='utf-8') as f:
                f.write(f"测试开始时间: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write(f"测试ID: {test_task_id}\n")
                f.write(f"总权重: {total_weight}\n")
                f.write(f"总并发数: {total_concurrency}\n")
                if model_config:
                    f.write(f"模型: {model_config.get('name', 'unknown')}\n")
                    f.write(f"API URL: {model_config.get('api_url', 'unknown')}\n")
                    f.write(f"模型名称: {model_config.get('model', 'unknown')}\n")
                f.write("-" * 50 + "\n\n")
            
            # 创建进度对象
            # 计算实际任务数量 - 根据并发数限制每个数据集的任务数
            total_prompts = 0
            for task in tasks:
                # 每个并发处理一个任务，所以任务数 = 并发数
                task_count = task.concurrency
                total_prompts += task_count
                logger.info(f"数据集 {task.dataset_name} 实际执行任务数: {task_count}")
            
            self.progress = TestProgress(
                test_task_id=test_task_id,
                total_tasks=total_prompts,
                completed_tasks=0,
                successful_tasks=0,
                failed_tasks=0,
                avg_response_time=0.0,
                avg_generation_speed=0.0,
                avg_tps=0.0,
                last_error="",
                dataset_stats={}
            )
            
            # 创建API客户端
            api_client = self._create_api_client(model_config or {})
            
            # 创建任务队列
            task_queue = asyncio.Queue()
            result_queue = asyncio.Queue()
            
            # 添加任务到队列 - 根据并发数限制每个数据集的任务数
            for task in tasks:
                # 从prompts中随机选择任务数量的prompt
                selected_prompts = random.sample(
                    task.prompts, 
                    min(task.concurrency, len(task.prompts))
                )
                
                for prompt in selected_prompts:
                    await task_queue.put((task.dataset_name, prompt))
                    
                # 记录任务添加日志
                with open(log_file, 'a', encoding='utf-8') as f:
                    f.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] 添加数据集任务: {task.dataset_name}\n")
                    f.write(f"- 选择Prompts数量: {len(selected_prompts)}\n")
                    f.write(f"- 权重: {task.weight}\n")
                    f.write(f"- 并发数: {task.concurrency}\n\n")
            
            # 创建工作协程
            workers = []
            for i in range(total_concurrency):
                worker = asyncio.create_task(
                    self._worker(
                        f"worker_{i}",
                        task_queue,
                        result_queue,
                        api_client,
                        log_file
                    )
                )
                workers.append(worker)
                logger.info(f"工作协程 worker_{i} 启动")
                
                # 记录工作协程启动日志
                with open(log_file, 'a', encoding='utf-8') as f:
                    f.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] 工作协程 worker_{i} 启动\n")
            
            # 创建结果处理协程
            result_handler = asyncio.create_task(
                self._result_handler(
                    result_queue,
                    self.progress,
                    progress_callback,
                    log_file
                )
            )
            
            # 等待所有任务完成
            await task_queue.join()
            
            # 停止工作协程
            for worker in workers:
                await task_queue.put(None)  # 发送停止信号
            await asyncio.gather(*workers)
            
            # 停止结果处理协程
            await result_queue.put(None)  # 发送停止信号
            await result_handler
            
            # 关闭API客户端
            await api_client.close()
            
            # 写入测试结束信息
            with open(log_file, 'a', encoding='utf-8') as f:
                f.write(f"\n[{time.strftime('%Y-%m-%d %H:%M:%S')}] 测试完成\n")
                f.write("-" * 50 + "\n")
                f.write(f"总任务数: {self.progress.total_tasks}\n")
                f.write(f"完成任务数: {self.progress.completed_tasks}\n")
                f.write(f"成功任务数: {self.progress.successful_tasks}\n")
                f.write(f"失败任务数: {self.progress.failed_tasks}\n")
                f.write(f"平均响应时间: {self.progress.avg_response_time:.2f}s\n")
                f.write(f"平均生成速度: {self.progress.avg_generation_speed:.2f}字/秒\n")
                f.write(f"平均TPS: {self.progress.avg_tps:.2f}\n")
            
            logger.info("[DEBUG] 测试完成")
            
        except Exception as e:
            logger.error(f"[ERROR] 测试执行失败: {e}", exc_info=True)
            # 记录错误信息到日志文件
            with open(log_file, 'a', encoding='utf-8') as f:
                f.write(f"\n[{time.strftime('%Y-%m-%d %H:%M:%S')}] 测试执行失败: {e}\n")
                f.write(traceback.format_exc())
            raise
    
    def stop_test(self):
        """停止测试"""
        self.running = False
