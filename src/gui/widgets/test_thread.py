"""
测试线程模块
"""
import asyncio
from typing import List
from PyQt6.QtCore import QThread, pyqtSignal
from src.engine.test_manager import TestManager, TestTask, TestProgress
from src.engine.api_client import APIResponse
from src.data.db_manager import db_manager
from src.utils.logger import setup_logger

# 设置日志记录器
logger = setup_logger("test_thread")


class TestThread(QThread):
    """测试线程"""
    progress_updated = pyqtSignal(TestProgress)
    result_received = pyqtSignal(str, APIResponse)
    test_finished = pyqtSignal()
    test_error = pyqtSignal(str)
    
    def __init__(
            self,
            model_name: str,
            tasks: List[TestTask],
            test_task_id: str):
        super().__init__()
        # 在主线程中获取模型配置
        try:
            models = db_manager.get_model_configs()
            self.model_config = next(
                (m for m in models if m["name"] == model_name), None)
            if not self.model_config:
                raise ValueError(f"找不到模型配置: {model_name}")
        except Exception as e:
            logger.error(f"获取模型配置失败: {e}")
            self.model_config = None
            
        self.tasks = tasks
        self.test_task_id = test_task_id
        self.test_manager = TestManager()
        # 连接信号
        self.test_manager.result_received.connect(self.result_received)
    
    def run(self):
        """运行测试线程"""
        try:
            if not self.model_config:
                raise ValueError("模型配置无效")
                
            logger.info("开始执行测试任务...")
            
            # 创建事件循环
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            # 运行测试
            loop.run_until_complete(
                self.test_manager.run_test(
                    self.test_task_id,
                    self.tasks,
                    self._progress_callback,
                    self.model_config
                )
            )
            
            # 关闭事件循环
            logger.info("正在关闭事件循环...")
            loop.close()
            
            # 发送测试完成信号
            self.test_finished.emit()
            
        except Exception as e:
            logger.error(f"测试线程执行出错: {e}", exc_info=True)
            self.test_error.emit(str(e))
        finally:
            logger.info("测试线程结束运行")
    
    def _progress_callback(self, progress: TestProgress):
        """进度回调函数"""
        self.progress_updated.emit(progress) 