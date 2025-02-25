"""
测试管理器模块，负责管理并发测试任务
"""
import asyncio
import time
import random
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
    total_tasks: int
    completed_tasks: int
    successful_tasks: int
    failed_tasks: int
    avg_response_time: float
    avg_generation_speed: float
    last_error: str
    
    @property
    def progress_percentage(self) -> float:
        """计算进度百分比"""
        if self.total_tasks == 0:
            return 0.0
        return (self.completed_tasks / self.total_tasks) * 100

class TestManager(QObject):
    """测试管理器类"""
    # 定义信号
    progress_updated = pyqtSignal(TestProgress)
    result_received = pyqtSignal(str, APIResponse)
    
    def __init__(self):
        super().__init__()
        self.running = False
        self.progress = TestProgress(0, 0, 0, 0, 0.0, 0.0, "")
    
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
    
    def _update_progress(self, response: APIResponse, error_msg: str = ""):
        """更新测试进度"""
        self.progress.completed_tasks += 1
        
        if response.success:
            self.progress.successful_tasks += 1
            
            # 使用累积平均值计算
            n = self.progress.successful_tasks
            if n == 1:
                # 第一个成功的任务
                self.progress.avg_response_time = response.duration
                self.progress.avg_generation_speed = response.generation_speed
            else:
                # 更新累积平均值
                self.progress.avg_response_time = (
                    (self.progress.avg_response_time * (n - 1) + response.duration) / n
                )
                self.progress.avg_generation_speed = (
                    (self.progress.avg_generation_speed * (n - 1) + response.generation_speed) / n
                )
        else:
            self.progress.failed_tasks += 1
            self.progress.last_error = error_msg or response.error_msg
        
        # 发送进度更新信号
        self.progress_updated.emit(self.progress)
    
    async def _worker(
        self,
        client: APIClient,
        dataset_name: str,
        task_queue: asyncio.Queue,
        result_queue: asyncio.Queue
    ):
        """工作协程"""
        while self.running:
            try:
                task = await task_queue.get()
                if task is None:  # 停止信号
                    break
                
                dataset_name, prompt = task  # 从任务中获取数据集名称和prompt
                response = await client.generate(prompt)
                await result_queue.put((dataset_name, response))
                
                task_queue.task_done()
            except Exception as e:
                logger.error(f"工作协程异常: {e}")
                if self.running:  # 只在正常运行时更新错误状态
                    error_response = APIResponse(success=False, error_msg=str(e))
                    await result_queue.put((dataset_name, error_response))
                    task_queue.task_done()
    
    async def _result_handler(self, result_queue: asyncio.Queue):
        """结果处理协程"""
        while self.running:
            try:
                result = await result_queue.get()
                if result is None:  # 停止信号
                    break
                
                dataset_name, response = result
                self._update_progress(response)
                
                # 发送结果信号
                self.result_received.emit(dataset_name, response)
                
                result_queue.task_done()
            except Exception as e:
                logger.error(f"结果处理协程异常: {e}")
    
    async def run_test(
        self,
        model_config: dict,
        tasks: List[TestTask]
    ):
        """运行测试"""
        if self.running:
            logger.warning("测试已在运行中")
            return
        
        self.running = True
        logger.info("开始运行测试...")
        
        # 计算每个数据集实际的任务数量
        total_weight = sum(task.weight for task in tasks)
        total_tasks = []  # 存储展开后的所有任务
        
        for task in tasks:
            # 直接使用设置的并发数作为任务数量
            task_count = task.concurrency
            logger.info(f"数据集 {task.dataset_name} 分配任务数: {task_count}")
            
            # 如果prompts数量不足，则循环使用
            prompts_cycle = task.prompts.copy()
            selected_prompts = []
            
            # 生成指定数量的任务，通过循环使用prompts
            for i in range(task_count):
                if not prompts_cycle:  # 如果已经用完了所有prompts，重新填充
                    prompts_cycle = task.prompts.copy()
                # 随机选择一个prompt并从可用列表中移除
                prompt = random.choice(prompts_cycle)
                prompts_cycle.remove(prompt)
                selected_prompts.append(prompt)
            
            # 添加到总任务列表
            total_tasks.extend([(task.dataset_name, prompt) for prompt in selected_prompts])
        
        # 随机打乱任务顺序
        random.shuffle(total_tasks)
        logger.info(f"总任务数: {len(total_tasks)}")
        
        # 更新总任务数
        self.progress = TestProgress(
            total_tasks=len(total_tasks),
            completed_tasks=0,
            successful_tasks=0,
            failed_tasks=0,
            avg_response_time=0.0,
            avg_generation_speed=0.0,
            last_error=""
        )
        
        # 创建任务队列和结果队列
        task_queue = asyncio.Queue()
        result_queue = asyncio.Queue()
        
        # 创建API客户端
        client = self._create_api_client(model_config)
        
        try:
            # 创建工作协程
            workers = []
            total_concurrency = sum(task.concurrency for task in tasks)  # 使用总并发数
            for _ in range(total_concurrency):
                worker = asyncio.create_task(
                    self._worker(client, "", task_queue, result_queue)
                )
                workers.append(worker)
            
            # 创建结果处理协程
            result_handler = asyncio.create_task(
                self._result_handler(result_queue)
            )
            
            # 添加所有任务到队列
            for dataset_name, prompt in total_tasks:
                await task_queue.put((dataset_name, prompt))
            
            # 等待所有任务完成
            logger.info("等待所有任务完成...")
            await task_queue.join()
            logger.info("所有任务已完成")
            
            # 发送停止信号
            logger.info("发送停止信号...")
            for _ in range(len(workers)):
                await task_queue.put(None)
            await result_queue.put(None)
            
            # 等待所有工作协程结束
            logger.info("等待工作协程结束...")
            await asyncio.gather(*workers)
            await result_handler
            logger.info("所有工作协程已结束")
            
        except Exception as e:
            logger.error(f"测试执行出错: {e}")
        finally:
            logger.info("测试结束，清理资源...")
            self.running = False
            await client.close()
            logger.info("测试完全结束")
    
    def stop_test(self):
        """停止测试"""
        self.running = False
