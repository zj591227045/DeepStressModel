"""
测试执行模块
"""
import time
import logging
from typing import Dict, List, Callable
from PyQt6.QtCore import QObject, pyqtSignal
from src.engine.test_manager import TestTask, TestProgress
from src.engine.api_client import APIResponse
from src.gui.widgets.test_thread import TestThread

# 设置日志记录器
logger = logging.getLogger("test_executor")


class TestExecutor(QObject):
    """测试执行器"""
    
    # 定义信号
    progress_updated = pyqtSignal(TestProgress)
    result_received = pyqtSignal(str, APIResponse)
    test_finished = pyqtSignal()
    test_error = pyqtSignal(str)
    
    def __init__(self):
        """初始化测试执行器"""
        super().__init__()
        self.test_thread = None
        self.test_task_id = None
        self.is_running = False
    
    def start_test(
            self,
            model_name: str,
            tasks: List[TestTask],
            test_task_id: str,
            on_progress_updated: Callable = None,
            on_result_received: Callable = None,
            on_test_finished: Callable = None,
            on_test_error: Callable = None):
        """开始测试
        
        Args:
            model_name: 模型名称
            tasks: 测试任务列表
            test_task_id: 测试任务ID
            on_progress_updated: 进度更新回调
            on_result_received: 结果接收回调
            on_test_finished: 测试完成回调
            on_test_error: 测试错误回调
        """
        try:
            # 检查是否已经在运行
            if self.is_running:
                logger.warning("测试已在运行中")
                return False
            
            # 创建测试线程
            self.test_thread = TestThread(
                model_name,
                tasks,
                test_task_id
            )
            
            # 连接信号
            if on_progress_updated:
                self.test_thread.progress_updated.connect(on_progress_updated)
            if on_result_received:
                self.test_thread.result_received.connect(on_result_received)
            if on_test_finished:
                self.test_thread.test_finished.connect(on_test_finished)
            if on_test_error:
                self.test_thread.test_error.connect(on_test_error)
            
            # 连接内部信号
            self.test_thread.progress_updated.connect(self.progress_updated)
            self.test_thread.result_received.connect(self.result_received)
            self.test_thread.test_finished.connect(self._on_test_finished)
            self.test_thread.test_error.connect(self._on_test_error)
            
            logger.info("测试线程已创建，信号已连接")
            
            # 保存测试任务ID
            self.test_task_id = test_task_id
            
            # 启动测试线程
            self.test_thread.start()
            self.is_running = True
            logger.info("测试线程开始运行")
            
            return True
        except Exception as e:
            logger.error(f"启动测试失败: {e}", exc_info=True)
            if on_test_error:
                on_test_error(str(e))
            self.test_error.emit(str(e))
            return False
    
    def stop_test(self):
        """停止测试"""
        if not self.is_running or not self.test_thread:
            logger.warning("没有正在运行的测试")
            return False
        
        try:
            # 停止测试线程
            if self.test_thread.isRunning():
                self.test_thread.terminate()  # 强制终止线程
                self.test_thread.wait(1000)  # 等待最多1秒
            
            self.is_running = False
            logger.info("测试已停止")
            return True
        except Exception as e:
            logger.error(f"停止测试失败: {e}", exc_info=True)
            return False
    
    def _on_test_finished(self):
        """测试完成处理"""
        self.is_running = False
        self.test_finished.emit()
    
    def _on_test_error(self, error_msg: str):
        """测试错误处理"""
        self.is_running = False
        self.test_error.emit(error_msg)
    
    def is_test_running(self):
        """检查测试是否正在运行"""
        return self.is_running 