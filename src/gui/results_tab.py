"""
结果显示组件，用于展示测试进度和结果
"""
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QProgressBar, QTableWidget, QTableWidgetItem,
    QHeaderView, QTextEdit
)
from PyQt6.QtCore import Qt, pyqtSlot
from src.engine.api_client import APIResponse
from src.engine.test_manager import TestProgress
from src.utils.logger import setup_logger
import time

logger = setup_logger("results_tab")

class ResultsTab(QWidget):
    """结果显示组件"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self._init_ui()
        self._dataset_rows = {}  # 数据集行索引映射
        self._dataset_start_times = {}  # 记录每个数据集的开始时间
    
    def _init_ui(self):
        """初始化UI"""
        layout = QVBoxLayout()
        
        # 进度条区域
        progress_layout = QHBoxLayout()
        self.progress_bar = QProgressBar()
        self.progress_bar.setTextVisible(True)
        progress_layout.addWidget(self.progress_bar)
        self.progress_label = QLabel("总任务数: 0")
        progress_layout.addWidget(self.progress_label)
        layout.addLayout(progress_layout)
        
        # 数据集结果表格
        self.result_table = QTableWidget()
        self.result_table.setColumnCount(9)  # 增加到9列
        self.result_table.setHorizontalHeaderLabels([
            "数据集", "完成/总数", "成功率", "平均响应时间", 
            "平均生成速度", "当前速度", "总字符数", "平均TPS", "总耗时"
        ])
        header = self.result_table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self.result_table)
        
        # 错误信息区域
        self.error_text = QTextEdit()
        self.error_text.setReadOnly(True)
        self.error_text.setMaximumHeight(100)
        self.error_text.setPlaceholderText("测试过程中的错误信息将在此显示...")  # 添加提示文本
        self.error_text.hide()  # 初始时隐藏错误信息区域
        layout.addWidget(self.error_text)
        
        self.setLayout(layout)
    
    def _format_time(self, ms: float) -> str:
        """格式化时间显示"""
        if ms < 1000:
            return f"{ms:.1f}ms"
        elif ms < 60000:
            return f"{ms/1000:.2f}s"
        else:
            minutes = int(ms / 60000)
            seconds = (ms % 60000) / 1000
            return f"{minutes}分{seconds:.1f}秒"
    
    def _format_speed(self, chars_per_sec: float) -> str:
        """格式化速度显示"""
        return f"{chars_per_sec:.1f} 字符/秒"
    
    def _update_dataset_row(self, dataset_name: str, response: APIResponse):
        """更新数据集结果行"""
        if dataset_name not in self._dataset_rows:
            logger.error(f"找不到数据集 {dataset_name} 的记录")
            return
        
        # 如果有错误信息，显示错误信息区域
        if not response.success:
            self.error_text.show()
            self.error_text.append(f"数据集 {dataset_name}: {response.error_msg}")
        
        stats = self._dataset_rows[dataset_name]
        row = stats["row"]
        
        logger.info(f"更新数据集 {dataset_name} 的统计信息:")
        logger.info(f"  - 更新前状态: {stats}")
        
        # 更新完成数量
        if response.success:
            stats["successful"] += 1
            stats["total_time"] += response.duration
            stats["total_chars"] += len(response.response_text)
            
            # 统一使用token_counter计算token
            from src.utils.token_counter import token_counter
            tokens = token_counter.count_tokens(response.response_text, response.model_name)
            stats["total_tokens"] += tokens
            
            # 计算当前token生成速度
            stats["current_tps"] = tokens / (response.duration + 1e-6)
            stats["current_speed"] = len(response.response_text) / (response.duration + 1e-6)
            
            logger.info(f"  - 成功任务统计:")
            logger.info(f"    * 总字符数: {stats['total_chars']}")
            logger.info(f"    * 总token数: {stats['total_tokens']}")
            logger.info(f"    * 当前TPS: {stats['current_tps']:.1f}")
            logger.info(f"    * 响应时间: {response.duration:.2f}s")
        else:
            stats["failed"] += 1
            logger.error(f"任务失败: {response.error_msg}")
        
        stats["completed"] = stats["successful"] + stats["failed"]
        
        logger.info(f"  - 更新后状态:")
        logger.info(f"    * 完成数: {stats['completed']}")
        logger.info(f"    * 成功数: {stats['successful']}")
        logger.info(f"    * 失败数: {stats['failed']}")
        logger.info(f"    * 总数: {stats['total']}")
        
        # 更新统计信息
        success_rate = (stats["successful"] / stats["completed"]) * 100 if stats["completed"] > 0 else 0
        avg_time = stats["total_time"] / max(stats["successful"], 1)
        avg_speed = (stats["total_chars"] / (stats["total_time"] + 1e-6)) if stats["total_time"] > 0 else 0
        
        # 计算平均TPS
        avg_tps = (stats["total_tokens"] / (stats["total_time"] + 1e-6)) if stats["total_time"] > 0 else 0
        logger.info(f"    * 平均TPS: {avg_tps:.1f}")
        
        total_elapsed = (time.time() - stats["start_time"]) * 1000
        
        # 更新表格显示
        display_text = f"{stats['completed']}/{stats['total']} (失败: {stats['failed']})"
        logger.info(f"  - 表格显示文本: {display_text}")
        
        self.result_table.setItem(row, 1, QTableWidgetItem(display_text))
        self.result_table.setItem(row, 2,
            QTableWidgetItem(f"{success_rate:.1f}%")
        )
        self.result_table.setItem(row, 3,
            QTableWidgetItem(self._format_time(avg_time * 1000))  # 转换为毫秒
        )
        self.result_table.setItem(row, 4,
            QTableWidgetItem(self._format_speed(avg_speed))
        )
        self.result_table.setItem(row, 5,
            QTableWidgetItem(self._format_speed(stats["current_speed"]))
        )
        self.result_table.setItem(row, 6,
            QTableWidgetItem(f"{stats['total_chars']:,}")  # 添加千位分隔符
        )
        self.result_table.setItem(row, 7,
            QTableWidgetItem(f"{avg_tps:.1f}")
        )
        self.result_table.setItem(row, 8,
            QTableWidgetItem(self._format_time(total_elapsed))
        )
    
    @pyqtSlot(TestProgress)
    def update_progress(self, progress: TestProgress):
        """更新进度信息"""
        # 更新进度条
        self.progress_bar.setValue(int(progress.progress_percentage))
        self.progress_label.setText(
            f"总任务数: {progress.total_tasks}"
        )
        
        # 更新错误信息
        if progress.last_error:
            self.error_text.show()
            self.error_text.append(progress.last_error)
    
    @pyqtSlot(str, APIResponse)
    def add_result(self, dataset_name: str, response: APIResponse):
        """添加测试结果"""
        self._update_dataset_row(dataset_name, response)
    
    def prepare_test(self, dataset_tasks: dict):
        """准备开始新的测试
        
        Args:
            dataset_tasks: 数据集任务字典，格式为 {dataset_name: (prompts_list, concurrency)}
        """
        logger.info(f"开始准备测试...")
        logger.info(f"接收到的dataset_tasks: {dataset_tasks}")
        
        # 清空现有数据
        self.result_table.setRowCount(0)
        self._dataset_rows.clear()
        self.error_text.clear()
        self.error_text.hide()
        
        total_tasks = 0
        
        # 初始化每个数据集的行
        for dataset_name, (prompts, concurrency) in dataset_tasks.items():
            logger.info(f"初始化数据集 {dataset_name}:")
            logger.info(f"  - 原始任务数: {len(prompts)}")
            logger.info(f"  - 并发数: {concurrency}")
            logger.info(f"  - 设置的任务数: {concurrency}")
            
            # 添加新行
            row = self.result_table.rowCount()
            self.result_table.insertRow(row)
            
            # 设置数据集名称
            self.result_table.setItem(row, 0, QTableWidgetItem(dataset_name))
            
            # 初始化统计数据
            stats = {
                "row": row,
                "total": concurrency,  # 使用并发数作为任务数
                "completed": 0,
                "successful": 0,
                "failed": 0,
                "total_time": 0,
                "total_chars": 0,
                "total_tokens": 0,
                "current_speed": 0.0,
                "current_tps": 0.0,
                "start_time": time.time()
            }
            
            total_tasks += concurrency
            self._dataset_rows[dataset_name] = stats
            
            # 更新进度显示
            self.result_table.setItem(row, 1, QTableWidgetItem(f"0/{stats['total']}"))
            self.result_table.setItem(row, 2, QTableWidgetItem("0%"))
            self.result_table.setItem(row, 3, QTableWidgetItem("0ms"))
            self.result_table.setItem(row, 4, QTableWidgetItem("0 字符/秒"))
            self.result_table.setItem(row, 5, QTableWidgetItem("0 字符/秒"))
            self.result_table.setItem(row, 6, QTableWidgetItem("0"))
            self.result_table.setItem(row, 7, QTableWidgetItem("0 token/秒"))
            self.result_table.setItem(row, 8, QTableWidgetItem("0秒"))
            
            logger.info(f"数据集 {dataset_name} 的初始状态:")
            logger.info(f"  - _dataset_rows: {stats}")
            
            total_tasks = sum(stats["total"] for stats in self._dataset_rows.values())
            logger.info(f"  - 当前总任务数: {total_tasks}")
        
        # 更新进度条最大值
        self.progress_bar.setMaximum(total_tasks)
        self.progress_bar.setValue(0)
        self.progress_label.setText(f"进度: 0/{total_tasks}")
        
        logger.info(f"测试准备完成，最终总任务数: {total_tasks}")
