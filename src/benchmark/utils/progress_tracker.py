"""
进度跟踪模块，负责处理测试进度更新
"""
import time
import logging
from typing import Dict, Any, Callable, Optional

# 设置日志记录器
logger = logging.getLogger("progress_tracker")

class ProgressTracker:
    """进度跟踪类，用于更新和管理测试进度"""
    
    def __init__(self, callback: Optional[Callable[[Dict[str, Any]], None]] = None):
        """
        初始化进度跟踪器
        
        Args:
            callback: 进度回调函数，接收一个字典参数，包含进度信息
        """
        self.callback = callback
        self.test_start_time = None
        self.current_progress = {
            "progress": 0,
            "current_item": 0,
            "total_items": 0,
            "latency": 0,
            "throughput": 0,
            "total_time": 0,
            "total_tokens": 0,
            "total_bytes": 0,
            "token_throughput": 0,
            "status": "未开始"
        }
        self.dataset_name = "标准基准测试"
    
    def set_callback(self, callback: Callable[[Dict[str, Any]], None]):
        """
        设置进度回调函数
        
        Args:
            callback: 进度回调函数，接收一个字典参数，包含进度信息
        """
        self.callback = callback
    
    def set_dataset_name(self, name: str):
        """
        设置数据集名称
        
        Args:
            name: 数据集名称
        """
        self.dataset_name = name
    
    def start_test(self):
        """开始测试，记录开始时间"""
        self.test_start_time = time.time()
        logger.debug(f"记录测试开始时间: {self.test_start_time}")
        
        # 发送初始进度
        self.update_progress({
            "progress": 1,  # 设为1%而不是0%，确保显示"测试进行中"
            "current_item": 0,
            "total_items": 0,
            "latency": 0,
            "throughput": 0,
            "status": "准备测试中..."
        })
    
    def update_progress(self, progress_info: Dict[str, Any]):
        """
        更新进度信息
        
        Args:
            progress_info: 进度信息
        """
        # 添加调试日志
        logger.debug(f"更新进度信息: {progress_info}")
        
        # 更新当前进度
        self.current_progress.update(progress_info)
        
        if self.callback:
            # 获取数据集名称
            dataset_name = self.dataset_name
            
            # 创建格式化的进度信息，添加datasets结构以供UI使用
            formatted_progress = self.current_progress.copy()
            
            # 计算总耗时
            total_duration = progress_info.get("total_time", 0)
            
            # 如果total_time为0，从测试开始时间计算
            if (total_duration == 0 or total_duration is None) and self.test_start_time:
                current_time = time.time()
                total_duration = current_time - self.test_start_time
                logger.debug(f"从start_time计算总耗时: {total_duration}")
            
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
            logger.debug(f"发送格式化进度数据: {formatted_progress}")
            
            # 调用回调函数
            self.callback(formatted_progress)
    
    def complete_test(self, test_results=None):
        """
        完成测试
        
        Args:
            test_results: 测试结果数据
        """
        if not self.test_start_time:
            return
            
        end_time = time.time()
        total_duration = end_time - self.test_start_time
        
        # 如果有测试结果，计算最终统计数据
        if test_results:
            total_tests = len(test_results)
            successful_tests = sum(1 for r in test_results if r.get("status") == "success")
            success_rate = successful_tests / total_tests if total_tests > 0 else 0
            
            # 计算平均延迟和吞吐量
            if successful_tests > 0:
                avg_latency = sum(r.get("latency", 0) for r in test_results) / successful_tests
                avg_throughput = sum(r.get("throughput", 0) for r in test_results) / successful_tests
                # 计算基于token的平均TPS
                token_throughputs = [r.get("token_throughput", 0) for r in test_results if r.get("status") == "success"]
                avg_token_tps = sum(token_throughputs) / len(token_throughputs) if token_throughputs else 0
            else:
                avg_latency = 0
                avg_throughput = 0
                avg_token_tps = 0
                
            # 统计文本信息
            total_input_chars = sum(len(r.get("input", "")) for r in test_results)
            total_output_chars = sum(len(r.get("output", "")) for r in test_results)
            total_chars = total_input_chars + total_output_chars
            
            # 统计token数量
            total_tokens = sum(r.get("tokens", 0) for r in test_results)
            
            # 更新最终进度
            self.update_progress({
                "progress": 100,
                "current_item": total_tests,
                "total_items": total_tests,
                "latency": avg_latency,
                "throughput": avg_throughput,
                "token_throughput": avg_token_tps,
                "total_time": total_duration,
                "total_tokens": total_tokens,
                "total_bytes": total_chars,
                "status": "测试完成",
                "success_rate": success_rate
            })
        else:
            # 如果没有测试结果，只更新状态
            self.update_progress({
                "progress": 100,
                "status": "测试完成",
                "total_time": total_duration
            })
        
        # 重置开始时间
        self.test_start_time = None


# 创建一个全局的进度跟踪器实例
progress_tracker = ProgressTracker() 