"""
测试记录管理模块
"""
import os
import time
import logging
from typing import Dict, List, Tuple

# 设置日志记录器
logger = logging.getLogger("test_records_manager")


class TestRecordsManager:
    """测试记录管理类"""
    
    def __init__(self):
        """初始化测试记录管理器"""
        self.current_test_records = None
    
    def init_test_records(
            self,
            test_task_id: str,
            model_config: dict,
            selected_datasets: dict,
            total_concurrency: int):
        """初始化测试记录
        
        Args:
            test_task_id: 测试任务ID
            model_config: 模型配置
            selected_datasets: 选中的数据集，格式为 {dataset_name: (prompts, weight)}
            total_concurrency: 总并发数
        
        Returns:
            dict: 初始化的测试记录
        """
        try:
            # 计算总权重
            total_weight = sum(
                weight for _,
                weight in selected_datasets.values())
            logger.info(
                f"初始化测试记录: 总权重={total_weight}, 总并发数={total_concurrency}")

            records = {
                "test_task_id": test_task_id,
                "session_name": test_task_id,
                "model_name": model_config["name"],
                "model_config": model_config,
                "concurrency": total_concurrency,
                "datasets": {},
                "start_time": time.time(),
                "successful_tasks": 0,
                "failed_tasks": 0,
                "total_tokens": 0,
                "total_chars": 0,
                "total_time": 0.0,
                "avg_response_time": 0.0,
                "avg_generation_speed": 0.0,
                "current_speed": 0.0,
                "avg_tps": 0.0,
                "status": "running",
                "log_file": os.path.join(
                    "data",
                    "logs",
                    "tests",
                    f"{test_task_id}.log")}
            
            # 初始化每个数据集的统计信息
            total_tasks = 0  # 重置总任务数
            for dataset_name, (prompts, weight) in selected_datasets.items():
                # 计算每个数据集的实际并发数
                dataset_concurrency = max(
                    1, int((weight / total_weight) * total_concurrency))
                # 使用并发数作为该数据集的任务数
                dataset_tasks = dataset_concurrency
                total_tasks += dataset_tasks
                
                logger.info(
                    f"数据集 {dataset_name} 配置: 权重={weight}, 并发数={dataset_concurrency}, 任务数={dataset_tasks}")
                records["datasets"][dataset_name] = {
                    "total": dataset_tasks,  # 使用并发数作为任务数
                    "successful": 0,
                    "failed": 0,
                    "total_time": 0.0,
                    "total_tokens": 0,
                    "total_chars": 0,
                    "avg_response_time": 0.0,
                    "avg_generation_speed": 0.0,
                    "current_speed": 0.0,
                    "weight": weight,
                    "concurrency": dataset_concurrency,
                    "start_time": time.time()
                }
            
            # 设置总任务数为所有数据集的并发数之和
            records["total_tasks"] = total_tasks
            logger.info(f"总任务数设置为: {total_tasks} (所有数据集的并发数之和)")
            
            # 保存到本地缓存
            self.current_test_records = records
            
            return records
        except Exception as e:
            logger.error(f"初始化测试记录时出错: {e}", exc_info=True)
            raise
    
    def sync_test_records(self, results_tab=None):
        """同步测试记录到结果标签页
        
        Args:
            results_tab: 结果标签页实例
        """
        try:
            if not self.current_test_records:
                logger.warning("没有当前测试记录，无法同步")
                return
                
            # 更新结束时间
            if self.current_test_records["status"] in ["completed", "error"]:
                self.current_test_records["end_time"] = time.time()
            
            # 同步到 results_tab
            if results_tab:
                # 确保数据一致性
                if not hasattr(
                        results_tab,
                        'current_records') or not results_tab.current_records:
                    results_tab.current_records = self.current_test_records.copy()
                else:
                    # 更新关键字段
                    for key in [
                        "test_task_id",
                        "session_name",
                        "model_name",
                        "model_config",
                        "concurrency",
                        "total_tasks",
                        "successful_tasks",
                        "failed_tasks",
                        "total_tokens",
                        "total_chars",
                        "total_time",
                        "datasets",
                        "status",
                        "avg_response_time",
                        "avg_generation_speed",
                        "current_speed",
                        "avg_tps",
                        "start_time",
                            "end_time"]:
                        if key in self.current_test_records:
                            results_tab.current_records[key] = self.current_test_records[key]
                
                # 保存记录
                results_tab._save_test_records()
                logger.debug("测试记录已同步到 results_tab")
            else:
                logger.warning("未提供 results_tab，无法保存测试记录")
                
        except Exception as e:
            logger.error(f"同步测试记录时出错: {e}", exc_info=True)
    
    def clear_test_state(self):
        """清空测试状态"""
        self.current_test_records = None
        logger.info("测试状态已清空") 