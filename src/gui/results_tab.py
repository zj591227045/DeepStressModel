"""
测试结果显示标签页
"""
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QProgressBar, QTableWidget, QTableWidgetItem,
    QHeaderView, QTextEdit, QPushButton, QFileDialog, QMessageBox,
    QDialog
)
from PyQt6.QtCore import Qt, pyqtSlot
from src.utils.logger import setup_logger
from src.data.db_manager import db_manager
from src.engine.api_client import APIResponse
from src.engine.test_manager import TestProgress
from src.gui.i18n.language_manager import LanguageManager
import time
import os
import csv

logger = setup_logger("results_tab")

class ResultsTab(QWidget):
    """测试结果显示标签页"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.language_manager = LanguageManager()
        self.current_records = {}  # 当前测试会话的记录
        self._init_ui()
        
        # 连接语言改变信号
        self.language_manager.language_changed.connect(self.update_ui_text)
    
    def _init_ui(self):
        """初始化UI"""
        layout = QVBoxLayout()
        
        # 创建工具栏
        toolbar = QHBoxLayout()
        
        # 导出按钮
        export_btn = QPushButton(self.tr('export_records'))
        export_btn.clicked.connect(self._export_records)
        toolbar.addWidget(export_btn)
        
        # 清除日志按钮
        clear_btn = QPushButton(self.tr('clear_logs'))
        clear_btn.clicked.connect(self._clear_logs)
        toolbar.addWidget(clear_btn)
        
        toolbar.addStretch()
        layout.addLayout(toolbar)
        
        # 创建结果表格
        self.result_table = QTableWidget()
        self.result_table.setColumnCount(12)
        self.result_table.setHorizontalHeaderLabels([
            "会话名称",
            "完成/总数",
            "成功率",
            "平均响应时间",
            "平均生成速度",
            "当前速度",
            "总字符数",
            "平均TPS",
            "总耗时",
            "模型名称",
            "并发数",
            "操作"
        ])
        
        # 设置表格属性
        header = self.result_table.horizontalHeader()
        # 先设置所有列自适应内容
        header.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        
        # 设置特定列的宽度策略
        min_widths = {
            0: 200,  # 会话名称
            1: 100,  # 完成/总数
            2: 80,   # 成功率
            3: 120,  # 平均响应时间
            4: 120,  # 平均生成速度
            5: 100,  # 当前速度
            6: 100,  # 总字符数
            7: 100,  # 平均TPS
            8: 100,  # 总耗时
            9: 150,  # 模型名称
            10: 80,  # 并发数
            11: 80   # 操作
        }
        
        # 应用最小宽度
        for col, width in min_widths.items():
            self.result_table.setColumnWidth(col, width)
        
        # 设置会话名称列可以自动拉伸
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        
        layout.addWidget(self.result_table)
        
        # 错误信息显示区域
        self.error_text = QTextEdit()
        self.error_text.setPlaceholderText(self.tr('error_info_placeholder'))
        self.error_text.setMaximumHeight(100)
        self.error_text.setReadOnly(True)
        layout.addWidget(self.error_text)
        
        self.setLayout(layout)
        
        # 加载历史记录
        self._load_history_records()
    
    def _load_history_records(self):
        """加载历史测试记录"""
        try:
            logger.debug("开始加载历史测试记录")
            records = db_manager.get_test_records()
            logger.debug(f"获取到 {len(records)} 条历史记录")
            
            # 清空现有记录
            self.result_table.clearContents()
            self.result_table.setRowCount(0)
            
            if not records:
                logger.info("没有历史测试记录")
                return
            
            # 设置表格行数
            self.result_table.setRowCount(len(records))
            
            # 添加记录到表格
            for row, record in enumerate(records):
                try:
                    self._add_record_to_table(row, record)
                except Exception as e:
                    logger.error(f"添加第 {row} 行记录失败: {e}", exc_info=True)
                    continue
            
            logger.info(f"成功加载 {len(records)} 条历史记录")
            
        except Exception as e:
            logger.error(f"加载历史记录失败: {e}", exc_info=True)
            QMessageBox.warning(self, "错误", f"加载历史记录失败: {e}")
    
    def _add_record_to_table(self, row: int, record: dict):
        """添加记录到表格"""
        try:
            # 设置会话名称
            self.result_table.setItem(row, 0, QTableWidgetItem(record["session_name"]))
            
            # 设置完成/总数
            completion = f"{record['successful_tasks']}/{record['total_tasks']}"
            self.result_table.setItem(row, 1, QTableWidgetItem(completion))
            
            # 设置成功率
            success_rate = (record['successful_tasks'] / record['total_tasks'] * 100) if record['total_tasks'] > 0 else 0
            self.result_table.setItem(row, 2, QTableWidgetItem(f"{success_rate:.1f}%"))
            
            # 设置平均响应时间
            self.result_table.setItem(row, 3, QTableWidgetItem(f"{record['avg_response_time']:.1f}s"))
            
            # 设置平均生成速度
            self.result_table.setItem(row, 4, QTableWidgetItem(f"{record['avg_generation_speed']:.1f}字/秒"))
            
            # 设置当前速度
            self.result_table.setItem(row, 5, QTableWidgetItem(f"{record['current_speed']:.1f}字/秒"))
            
            # 设置总字符数
            self.result_table.setItem(row, 6, QTableWidgetItem(str(record['total_chars'])))
            
            # 设置平均TPS
            self.result_table.setItem(row, 7, QTableWidgetItem(f"{record['avg_tps']:.1f}"))
            
            # 设置总耗时
            self.result_table.setItem(row, 8, QTableWidgetItem(f"{record['total_time']:.1f}s"))
            
            # 设置模型名称
            self.result_table.setItem(row, 9, QTableWidgetItem(record['model_name']))
            
            # 设置并发数
            self.result_table.setItem(row, 10, QTableWidgetItem(str(record['concurrency'])))
            
            # 创建操作按钮容器
            button_widget = QWidget()
            button_layout = QHBoxLayout()
            button_layout.setContentsMargins(2, 2, 2, 2)  # 设置较小的边距
            button_layout.setSpacing(4)  # 设置按钮之间的间距
            
            # 添加日志按钮
            log_btn = QPushButton(self.tr('view_log'))
            log_btn.setFixedWidth(40)  # 设置固定宽度
            log_btn.clicked.connect(lambda: self._view_log(record.get('log_file', ''), record['session_name']))
            button_layout.addWidget(log_btn)
            
            # 添加删除按钮
            delete_btn = QPushButton(self.tr('delete'))
            delete_btn.setFixedWidth(40)  # 设置固定宽度
            delete_btn.clicked.connect(lambda: self._delete_record(record['session_name']))
            button_layout.addWidget(delete_btn)
            
            button_widget.setLayout(button_layout)
            self.result_table.setCellWidget(row, 11, button_widget)
            
            logger.debug(f"记录已添加到表格第 {row} 行")
            
        except Exception as e:
            logger.error(f"添加记录到表格失败: {e}", exc_info=True)
    
    def _view_log(self, log_file: str, session_name: str):
        """查看日志文件"""
        logger.debug(f"尝试查看日志文件，会话: {session_name}, 日志文件路径: {log_file}")
        
        if not log_file:
            logger.warning(f"会话 {session_name} 的日志文件路径为空")
            QMessageBox.warning(self, self.tr('warning'), f"未找到会话 {session_name} 的日志文件")
            return
            
        if not os.path.exists(log_file):
            logger.warning(f"日志文件不存在: {log_file}")
            QMessageBox.warning(self, self.tr('error'), f"日志文件不存在: {log_file}")
            return
        
        logger.debug(f"开始读取日志文件: {log_file}")
        dialog = QDialog(self)
        dialog.setWindowTitle(self.tr('test_log_title').format(session_name=session_name))
        dialog.resize(800, 600)
        
        layout = QVBoxLayout()
        
        # 添加日志内容
        log_text = QTextEdit()
        log_text.setReadOnly(True)
        
        try:
            with open(log_file, "r", encoding="utf-8") as f:
                content = f.read()
                log_text.setText(content)
                logger.debug(f"成功读取日志文件，内容长度: {len(content)} 字符")
        except Exception as e:
            error_msg = f"读取日志文件失败: {e}"
            logger.error(error_msg, exc_info=True)
            log_text.setText(error_msg)
        
        layout.addWidget(log_text)
        
        # 添加关闭按钮
        close_btn = QPushButton(self.tr('close'))
        close_btn.clicked.connect(dialog.close)
        layout.addWidget(close_btn)
        
        dialog.setLayout(layout)
        dialog.exec()
    
    def _delete_record(self, session_name: str):
        """删除测试记录"""
        logger.debug(f"尝试删除测试记录，会话: {session_name}")
        
        reply = QMessageBox.question(
            self,
            self.tr('confirm_delete'),
            self.tr('confirm_delete_msg').format(session_name=session_name),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            try:
                logger.debug(f"开始删除测试记录: {session_name}")
                result = db_manager.delete_test_record(session_name)
                logger.debug(f"删除测试记录结果: {result}")
                
                if result:
                    # 重新加载记录
                    logger.info(f"成功删除测试记录: {session_name}，准备重新加载记录")
                    self._load_history_records()
                    QMessageBox.information(self, self.tr('success'), self.tr('record_deleted'))
                else:
                    error_msg = f"删除测试记录失败: {session_name}"
                    logger.error(error_msg)
                    QMessageBox.warning(self, self.tr('error'), error_msg)
            except Exception as e:
                error_msg = f"删除测试记录时发生错误: {e}"
                logger.error(error_msg, exc_info=True)
                QMessageBox.critical(self, self.tr('error'), error_msg)
    
    def _export_records(self):
        """导出测试记录"""
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            self.tr('export_title'),
            "",
            "CSV文件 (*.csv)"
        )
        
        if not file_path:
            return
        
        try:
            records = db_manager.get_test_records()
            with open(file_path, "w", encoding="utf-8-sig", newline="") as f:
                writer = csv.writer(f)
                # 写入表头
                writer.writerow([
                    "测试时间", "模型名称", "并发数", "总任务数",
                    "成功任务数", "失败任务数", "平均响应时间(ms)",
                    "平均生成速度(字符/秒)", "总Token数",
                    "平均TPS", "总耗时(ms)"
                ])
                
                # 写入数据
                for record in records:
                    writer.writerow([
                        record["test_time"],
                        record["model_name"],
                        record["concurrency"],
                        record["total_tasks"],
                        record["successful_tasks"],
                        record["failed_tasks"],
                        record["avg_response_time"],
                        record["avg_generation_speed"],
                        record["total_tokens"],
                        record["avg_tps"],
                        record["total_time"]
                    ])
            
            QMessageBox.information(self, self.tr('success'), self.tr('export_success'))
        except Exception as e:
            QMessageBox.critical(self, self.tr('error'), f"导出记录失败: {e}")
    
    def _clear_logs(self):
        """清除测试日志"""
        reply = QMessageBox.question(
            self,
            self.tr('confirm_clear'),
            self.tr('confirm_clear_logs'),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            if db_manager.clear_test_logs():
                QMessageBox.information(self, self.tr('success'), self.tr('logs_cleared'))
            else:
                QMessageBox.warning(self, self.tr('warning'), "清除日志文件时发生错误")
    
    def tr(self, key):
        """翻译文本"""
        return self.language_manager.get_text(key)
    
    def prepare_test(self, model_config: dict, concurrency: int, test_task_id: str):
        """准备新的测试会话"""
        # 生成会话名称
        session_name = time.strftime("test_%Y%m%d_%H%M%S")
        
        # 初始化会话记录
        self.current_records = {
            "session_name": session_name,
            "model_name": model_config["name"],
            "concurrency": concurrency,
            "test_task_id": test_task_id,
            "datasets": {}
        }
        
        logger.info(f"准备测试会话: {session_name}")
        
    def _save_test_records(self):
        """保存测试记录"""
        try:
            # 确保必要的字段存在
            if not hasattr(self, 'current_records'):
                logger.error("没有当前测试记录")
                return
            
            # 确保model_name字段存在
            if "model_name" not in self.current_records and "model_config" in self.current_records:
                self.current_records["model_name"] = self.current_records["model_config"]["name"]
            
            # 创建日志文件
            log_dir = os.path.join("data", "logs", "tests")
            os.makedirs(log_dir, exist_ok=True)
            logger.debug(f"创建日志目录: {log_dir}")
            
            log_file = os.path.join(log_dir, f"{self.current_records.get('test_task_id', 'unknown')}.log")
            logger.info(f"生成日志文件路径: {log_file}")
            
            # 计算统计数据
            total_tasks = self.current_records.get('total_tasks', 0)
            successful_tasks = self.current_records.get('successful_tasks', 0)
            failed_tasks = self.current_records.get('failed_tasks', 0)
            avg_response_time = self.current_records.get('avg_response_time', 0)
            avg_generation_speed = self.current_records.get('avg_generation_speed', 0)
            total_chars = self.current_records.get('total_chars', 0)
            total_tokens = self.current_records.get('total_tokens', 0)
            avg_tps = self.current_records.get('avg_tps', 0)
            total_time = self.current_records.get('total_time', 0)
            current_speed = self.current_records.get('current_speed', avg_generation_speed)
            
            # 写入日志文件（使用追加模式）
            with open(log_file, 'a', encoding='utf-8') as f:
                # 写入测试完成信息
                f.write("\n" + "="*50 + "\n")
                f.write("测试完成统计信息:\n")
                f.write(f"测试ID: {self.current_records.get('test_task_id', 'unknown')}\n")
                f.write(f"会话名称: {self.current_records.get('session_name', 'unknown')}\n")
                f.write(f"模型名称: {self.current_records.get('model_name', 'unknown')}\n")
                f.write(f"并发数: {self.current_records.get('concurrency', 0)}\n")
                f.write(f"开始时间: {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(self.current_records.get('start_time', 0)))}\n")
                f.write(f"结束时间: {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(self.current_records.get('end_time', time.time())))}\n")
                f.write(f"总耗时: {total_time:.2f}秒\n\n")
                
                # 写入数据集统计信息
                f.write("数据集统计信息:\n")
                for dataset_name, stats in self.current_records.get('datasets', {}).items():
                    f.write(f"\n{dataset_name}:\n")
                    f.write(f"  总任务数: {stats.get('total', 0)}\n")
                    f.write(f"  成功数: {stats.get('successful', 0)}\n")
                    f.write(f"  失败数: {stats.get('failed', 0)}\n")
                    f.write(f"  成功率: {(stats.get('successful', 0) / stats.get('total', 1) * 100):.1f}%\n")
                    f.write(f"  平均响应时间: {stats.get('avg_response_time', 0):.2f}秒\n")
                    f.write(f"  平均生成速度: {stats.get('avg_generation_speed', 0):.1f}字/秒\n")
                    f.write(f"  总字符数: {stats.get('total_chars', 0)}\n")
                
                # 写入错误信息（如果有）
                if 'error_message' in self.current_records:
                    f.write("\n错误信息:\n")
                    f.write(f"{self.current_records['error_message']}\n")
                
                f.write("\n" + "="*50 + "\n")
            
            # 保存到数据库
            db_record = {
                "test_task_id": self.current_records.get('test_task_id', 'unknown'),
                "session_name": self.current_records.get('session_name', 'unknown'),
                "model_name": self.current_records.get('model_name', 'unknown'),
                "concurrency": self.current_records.get('concurrency', 0),
                "total_tasks": total_tasks,
                "successful_tasks": successful_tasks,
                "failed_tasks": failed_tasks,
                "avg_response_time": avg_response_time,
                "avg_generation_speed": avg_generation_speed,
                "total_chars": total_chars,
                "total_tokens": total_tokens,
                "avg_tps": avg_tps,
                "total_time": total_time,
                "current_speed": current_speed,
                "test_time": time.strftime('%Y-%m-%d %H:%M:%S'),
                "log_file": log_file
            }
            
            success = db_manager.save_test_record(db_record)
            if success:
                logger.info(f"测试记录已保存到数据库: {db_record['test_task_id']}")
                # 重新加载记录列表
                self._load_history_records()
            else:
                logger.error("保存测试记录到数据库失败")
            
        except Exception as e:
            logger.error(f"保存测试记录失败: {e}", exc_info=True)
            raise

    def add_result(self, dataset_name: str, response: APIResponse):
        """添加测试结果"""
        try:
            if dataset_name not in self.current_records["datasets"]:
                self.current_records["datasets"][dataset_name] = {
                    "total": 0,
                    "successful": 0,
                    "failed": 0,
                    "total_time": 0.0,
                    "total_tokens": 0,
                    "total_chars": 0,
                    "start_time": time.time()
                }
            
            stats = self.current_records["datasets"][dataset_name]
            stats["total"] += 1
            
            if response.success:
                stats["successful"] += 1
                stats["total_time"] += response.duration
                stats["total_tokens"] += response.total_tokens
                stats["total_chars"] += response.total_chars
            else:
                stats["failed"] += 1
                if response.error_msg:
                    self.error_text.append(f"数据集 {dataset_name} 错误: {response.error_msg}")
            
            logger.debug(f"已添加数据集 {dataset_name} 的测试结果")
            
        except Exception as e:
            logger.error(f"添加测试结果失败: {e}", exc_info=True)

    def update_ui_text(self):
        """更新UI文本"""
        # 更新工具栏按钮文本
        for child in self.findChildren(QPushButton):
            if child.text() == self.tr('export_records') or child.text().startswith('导出'):
                child.setText(self.tr('export_records'))
            elif child.text() == self.tr('clear_logs') or child.text().startswith('清除'):
                child.setText(self.tr('clear_logs'))
            elif child.text() == self.tr('view_log') or child.text().startswith('查看'):
                child.setText(self.tr('view_log'))
            elif child.text() == self.tr('delete') or child.text().startswith('删除'):
                child.setText(self.tr('delete'))
        
        # 更新表格头
        self.result_table.setHorizontalHeaderLabels([
            self.tr('session_name'),
            self.tr('completion_total'),
            self.tr('success_rate'),
            self.tr('avg_response_time'),
            self.tr('avg_generation_speed'),
            self.tr('current_speed'),
            self.tr('total_chars'),
            self.tr('avg_tps'),
            self.tr('total_time'),
            self.tr('model_name'),
            self.tr('concurrency'),
            self.tr('operations')
        ])
        
        # 更新错误文本框占位符
        self.error_text.setPlaceholderText(self.tr('error_info_placeholder'))
