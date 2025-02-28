"""
测试标签页模块
"""
import asyncio
import time
import uuid
import os
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox,
    QLabel, QComboBox, QSpinBox, QPushButton,
    QProgressBar, QTextEdit, QListWidget, QAbstractItemView,
    QListWidgetItem, QSlider, QMessageBox, QGridLayout, QSizePolicy, QFormLayout,
    QTableWidget, QTableWidgetItem, QHeaderView, QTabWidget, QMainWindow
)
from PyQt6.QtCore import Qt, QTimer, QThread, pyqtSignal
from src.utils.config import config
from src.utils.logger import setup_logger
from src.monitor.gpu_monitor import gpu_monitor
from src.engine.test_manager import TestManager, TestTask, TestProgress
from src.engine.api_client import APIResponse
from src.data.test_datasets import DATASETS
from src.data.db_manager import db_manager
from src.gui.results_tab import ResultsTab
from typing import List, Dict

logger = setup_logger("test_tab")

class DatasetListItem(QWidget):
    """数据集列表项"""
    def __init__(self, dataset_name: str, parent=None):
        super().__init__(parent)
        self.dataset_name = dataset_name
        self.init_ui()
        logger.info(f"创建数据集列表项: {dataset_name}")
    
    def init_ui(self):
        """初始化UI"""
        layout = QHBoxLayout()
        layout.setContentsMargins(5, 2, 5, 2)
        layout.setSpacing(10)  # 增加组件之间的间距
        
        # 数据集名称标签
        name_label = QLabel(self.dataset_name)
        name_label.setMinimumWidth(100)  # 设置最小宽度确保名称显示完整
        layout.addWidget(name_label)
        
        # 权重滑块
        self.weight_slider = QSlider(Qt.Orientation.Horizontal)
        self.weight_slider.setRange(1, 10)  # 设置权重范围1-10
        self.weight_slider.setValue(1)  # 默认权重为1
        self.weight_slider.setMinimumWidth(200)  # 设置最小宽度
        self.weight_slider.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)  # 水平方向自适应
        self.weight_slider.setTickPosition(QSlider.TickPosition.TicksBelow)  # 在下方显示刻度
        self.weight_slider.setTickInterval(1)  # 主刻度间隔为1
        self.weight_slider.valueChanged.connect(self._on_weight_changed)
        
        # 权重值显示标签
        self.weight_label = QLabel("1")
        self.weight_label.setFixedWidth(30)  # 设置固定宽度
        self.weight_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)  # 右对齐
        
        layout.addWidget(self.weight_slider, 1)  # 设置stretch factor为1，允许滑块拉伸
        layout.addWidget(self.weight_label)
        
        self.setLayout(layout)
        logger.info(f"数据集 {self.dataset_name} 初始化完成，默认权重: 1")
    
    def _on_weight_changed(self, value):
        """权重改变事件处理"""
        self.weight_label.setText(str(value))
        logger.info(f"数据集 {self.dataset_name} 权重改变: {value}")
    
    def get_weight(self) -> int:
        """获取权重值"""
        weight = self.weight_slider.value()
        logger.info(f"获取数据集 {self.dataset_name} 的权重: {weight}")
        return weight

class MonitorThread(QThread):
    """GPU监控线程"""
    stats_updated = pyqtSignal(object)  # 数据更新信号
    server_config_needed = pyqtSignal()  # 请求服务器配置信号
    
    def __init__(self, update_interval=0.5):
        super().__init__()
        self.update_interval = update_interval
        self.running = False
        self._last_stats = None
        self._active_server = None
        self._initialized = False  # 添加初始化标志
    
    def set_active_server(self, server_config):
        """从主线程设置活动服务器配置"""
        if server_config != self._active_server:  # 只在配置变化时更新
            self._active_server = server_config
            self._initialized = False  # 重置初始化标志
            if server_config:
                logger.info(f"监控线程收到新的服务器配置: {server_config['name']}")
            else:
                logger.info("监控线程收到空服务器配置")
    
    def run(self):
        """运行监控循环"""
        self.running = True
        while self.running:
            try:
                if not self._initialized:  # 只在未初始化时请求配置
                    self.server_config_needed.emit()
                    self._initialized = True
                
                if self._active_server:
                    stats = gpu_monitor.get_stats()
                    if stats and stats != self._last_stats:
                        self._last_stats = stats
                        self.stats_updated.emit(stats)
                else:
                    self.stats_updated.emit(None)
            except Exception as e:
                logger.debug(f"监控数据获取失败: {e}")
                self.stats_updated.emit(None)
            
            time.sleep(self.update_interval)
    
    def stop(self):
        """停止监控"""
        self.running = False

class GPUMonitorWidget(QGroupBox):
    """GPU监控组件"""
    def __init__(self):
        super().__init__("GPU监控")
        self.monitor_thread = MonitorThread(update_interval=0.5)
        self.monitor_thread.stats_updated.connect(self._on_stats_updated)
        self.monitor_thread.server_config_needed.connect(self._update_server_config)
        self._monitor_initialized = False  # 添加初始化标志
        self.init_ui()
    
    def _update_server_config(self):
        """响应监控线程的服务器配置请求"""
        try:
            active_server = db_manager.get_active_gpu_server()
            if active_server and not self._monitor_initialized:  # 只在未初始化时初始化
                gpu_monitor.init_monitor()
                self._monitor_initialized = True
            self.monitor_thread.set_active_server(active_server)
        except Exception as e:
            logger.error(f"获取活动服务器配置失败: {e}")
            self.monitor_thread.set_active_server(None)
    
    def init_ui(self):
        """初始化UI"""
        layout = QVBoxLayout()
        
        # 服务器选择区域
        server_layout = QHBoxLayout()
        self.server_selector = QComboBox()
        self.server_selector.currentIndexChanged.connect(self.on_server_changed)
        self.refresh_button = QPushButton("刷新")
        self.refresh_button.clicked.connect(self.refresh_servers)
        self.add_button = QPushButton("添加")
        self.add_button.clicked.connect(self.add_server)
        
        server_layout.addWidget(QLabel("选择服务器:"))
        server_layout.addWidget(self.server_selector)
        server_layout.addWidget(self.refresh_button)
        server_layout.addWidget(self.add_button)
        layout.addLayout(server_layout)
        
        # 提示标签
        self.hint_label = QLabel()
        self.hint_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.hint_label.setStyleSheet("color: #666666;")
        layout.addWidget(self.hint_label)
        
        # 监控信息显示区域（分为左右两栏）
        info_layout = QHBoxLayout()
        
        # 左侧 GPU 信息
        gpu_group = QGroupBox("GPU信息")
        gpu_layout = QFormLayout()
        
        # GPU型号信息
        self.gpu_info_label = QLabel("未连接")
        gpu_layout.addRow("GPU型号:", self.gpu_info_label)
        
        # GPU利用率
        self.gpu_util_label = QLabel("0%")
        gpu_layout.addRow("GPU利用率:", self.gpu_util_label)
        
        # 显存使用率
        self.memory_util_label = QLabel("0%")
        gpu_layout.addRow("显存使用率:", self.memory_util_label)
        
        # 温度
        self.temp_label = QLabel("0°C")
        gpu_layout.addRow("温度:", self.temp_label)
        
        # 功率使用
        self.power_label = QLabel("0W")
        gpu_layout.addRow("功率使用:", self.power_label)
        
        gpu_group.setLayout(gpu_layout)
        info_layout.addWidget(gpu_group)
        
        # 右侧系统信息
        system_group = QGroupBox("系统信息")
        system_layout = QFormLayout()
        
        # CPU使用率
        self.cpu_util_label = QLabel("0%")
        system_layout.addRow("CPU使用率:", self.cpu_util_label)
        
        # 系统内存使用率
        self.memory_util_sys_label = QLabel("0%")
        system_layout.addRow("内存使用率:", self.memory_util_sys_label)
        
        # 磁盘使用率
        self.disk_util_label = QLabel("0%")
        system_layout.addRow("磁盘使用率:", self.disk_util_label)
        
        # 网络使用率
        self.network_recv_label = QLabel("0 B/s")
        system_layout.addRow("网络接收:", self.network_recv_label)
        
        self.network_send_label = QLabel("0 B/s")
        system_layout.addRow("网络发送:", self.network_send_label)
        
        system_group.setLayout(system_layout)
        info_layout.addWidget(system_group)
        
        layout.addLayout(info_layout)
        
        # 状态信息
        self.status_label = QLabel()
        layout.addWidget(self.status_label)
        
        self.setLayout(layout)
        
        # 加载服务器列表
        self.refresh_servers()
    
    def refresh_servers(self):
        """刷新服务器列表"""
        try:
            self.server_selector.clear()
            servers = db_manager.get_gpu_servers()
            
            if not servers:
                self.show_no_servers_hint()
                return
            
            for server in servers:
                self.server_selector.addItem(
                    f"{server['name']} ({server['host']})", 
                    server
                )
                
            # 选择激活的服务器
            active_server = db_manager.get_active_gpu_server()
            if active_server:
                index = self.server_selector.findText(
                    f"{active_server['name']} ({active_server['host']})"
                )
                if index >= 0:
                    self.server_selector.setCurrentIndex(index)
                    # 启动监控
                    self.start_monitoring()
                else:
                    self.show_no_servers_hint()
            else:
                self.show_no_servers_hint()
        except Exception as e:
            logger.error(f"刷新服务器列表失败: {e}")
            self.show_no_servers_hint()
    
    def show_no_servers_hint(self):
        """显示无服务器配置的提示"""
        hint_text = '请点击"添加"按钮配置GPU服务器'
        self.hint_label.setText(hint_text)
        self.hint_label.show()  # 确保提示标签可见
        
        # 隐藏监控界面
        self.gpu_info_label.hide()
        self.gpu_util_label.hide()
        self.memory_util_label.hide()
        self.temp_label.hide()
        self.power_label.hide()
        self.cpu_util_label.hide()
        self.memory_util_sys_label.hide()
        self.disk_util_label.hide()
        self.network_recv_label.hide()
        self.network_send_label.hide()
        
        self.status_label.setText("状态: 未配置")
        self.status_label.setStyleSheet("color: #666666")  # 使用灰色表示未配置状态
    
    def show_monitor_ui(self):
        """显示监控界面"""
        self.hint_label.hide()
        self.gpu_info_label.show()
        self.gpu_util_label.show()
        self.memory_util_label.show()
        self.temp_label.show()
        self.power_label.show()
        self.cpu_util_label.show()
        self.memory_util_sys_label.show()
        self.disk_util_label.show()
        self.network_recv_label.show()
        self.network_send_label.show()
        self.status_label.setText("状态: 已连接")
        self.status_label.setStyleSheet("color: green")
    
    def add_server(self):
        """添加服务器配置"""
        from src.gui.settings.gpu_settings import ServerEditDialog
        dialog = ServerEditDialog(parent=self)
        if dialog.exec():
            self.refresh_servers()
    
    def on_server_changed(self, index: int):
        """服务器选择改变时的处理"""
        if index >= 0:
            server_data = self.server_selector.currentData()
            if server_data:
                try:
                    db_manager.set_gpu_server_active(server_data["name"])
                    # 立即检查 GPU 状态
                    stats = gpu_monitor.get_stats()
                    if stats:
                        self.show_monitor_ui()
                        self.error_count = 0  # 重置错误计数
                    else:
                        self.show_no_servers_hint()
                except Exception as e:
                    logger.error(f"设置活动服务器失败: {e}")
                    self.show_no_servers_hint()
    
    def start_monitoring(self):
        """开始监控"""
        self.monitor_thread.start()
    
    def _format_size(self, size_mb: float) -> str:
        """格式化显存大小显示"""
        if size_mb >= 1024:
            return f"{size_mb/1024:.1f} GB"
        return f"{size_mb:.0f} MB"
    
    def _format_network_speed(self, bytes_per_sec: float) -> str:
        """格式化网络速度显示"""
        if bytes_per_sec >= 1024 * 1024 * 1024:
            return f"{bytes_per_sec / (1024 * 1024 * 1024):.1f} GB/s"
        elif bytes_per_sec >= 1024 * 1024:
            return f"{bytes_per_sec / (1024 * 1024):.1f} MB/s"
        elif bytes_per_sec >= 1024:
            return f"{bytes_per_sec / 1024:.1f} KB/s"
        else:
            return f"{bytes_per_sec:.1f} B/s"

    def _on_stats_updated(self, stats):
        """处理监控数据更新"""
        if not stats:
            self.show_no_servers_hint()
            return
        
        try:
            # 更新GPU信息
            self.gpu_info_label.setText(stats.gpu_info or "未知型号")
            
            # 更新GPU利用率
            self.gpu_util_label.setText(f"{stats.gpu_util:.1f}%")
            
            # 更新显存使用率
            memory_util = stats.gpu_memory_util
            self.memory_util_label.setText(
                f"{memory_util:.1f}% ({self._format_size(stats.memory_used)}/{self._format_size(stats.memory_total)})"
            )
            
            # 更新温度
            self.temp_label.setText(f"{stats.temperature:.1f}°C")
            
            # 更新功率使用
            if stats.power_limit > 0:
                self.power_label.setText(
                    f"{stats.power_usage:.1f}W/{stats.power_limit:.1f}W ({(stats.power_usage / stats.power_limit) * 100:.1f}%)"
                )
            else:
                self.power_label.setText("N/A")
            
            # 更新CPU使用率
            self.cpu_util_label.setText(f"{stats.cpu_util:.1f}%")
            
            # 更新系统内存使用率
            self.memory_util_sys_label.setText(f"{stats.memory_util:.1f}%")
            
            # 更新磁盘使用率
            self.disk_util_label.setText(f"{stats.disk_util:.1f}%")
            
            # 更新网络使用率
            if stats.network_io:
                recv_speed = stats.network_io.get('receive', 0)
                send_speed = stats.network_io.get('transmit', 0)
                self.network_recv_label.setText(self._format_network_speed(recv_speed))
                self.network_send_label.setText(self._format_network_speed(send_speed))
            else:
                self.network_recv_label.setText("N/A")
                self.network_send_label.setText("N/A")
            
            self.status_label.setText("状态: 正常")
            self.status_label.setStyleSheet("color: green")
            self.error_count = 0
            
            # 显示监控UI
            self.show_monitor_ui()
            
        except Exception as e:
            logger.error(f"更新UI失败: {e}")
            self.show_no_servers_hint()
    
    def closeEvent(self, event):
        """窗口关闭事件"""
        self.monitor_thread.stop()
        self.monitor_thread.wait()
        super().closeEvent(event)

class TestProgressWidget(QGroupBox):
    """测试进度组件"""
    def __init__(self):
        super().__init__("测试进度")
        self.init_ui()
    
    def init_ui(self):
        """初始化UI"""
        layout = QVBoxLayout()
        
        # 进度条
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        layout.addWidget(self.progress_bar)
        
        # 详细信息
        self.detail_text = QTextEdit()
        self.detail_text.setReadOnly(True)
        self.detail_text.setMaximumHeight(100)
        self.detail_text.setPlaceholderText("测试运行时将在此显示详细进度信息...")  # 添加提示文本
        layout.addWidget(self.detail_text)
        
        self.setLayout(layout)

class TestThread(QThread):
    """测试线程"""
    progress_updated = pyqtSignal(TestProgress)
    result_received = pyqtSignal(str, APIResponse)
    test_finished = pyqtSignal()
    test_error = pyqtSignal(str)
    
    def __init__(self, model_config: dict, tasks: List[TestTask], test_task_id: str):
        super().__init__()
        self.model_config = model_config
        self.tasks = tasks
        self.test_task_id = test_task_id
        self.test_manager = TestManager()
        # 连接信号
        self.test_manager.result_received.connect(self.result_received)
    
    def run(self):
        """运行测试线程"""
        try:
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

class TestInfoWidget(QGroupBox):
    """实时测试信息显示组件"""
    def __init__(self):
        super().__init__("测试信息")
        self.init_ui()
        
    def init_ui(self):
        """初始化UI"""
        layout = QVBoxLayout()
        
        # 创建测试信息表格
        info_group = QGroupBox("测试实时数据")
        info_layout = QVBoxLayout()
        
        self.info_table = QTableWidget()
        self.info_table.setColumnCount(8)
        self.info_table.setHorizontalHeaderLabels([
            "数据集",
            "完成/总数",
            "成功率",
            "平均响应时间",
            "平均生成速度",
            "当前速度",
            "总字符数",
            "平均TPS"
        ])
        
        # 设置表格属性
        header = self.info_table.horizontalHeader()
        # 设置所有列先自适应内容
        header.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        
        # 设置特定列的宽度策略
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)  # 数据集名称列自适应剩余空间
        # 为其他列设置最小宽度，确保数据显示完整
        min_widths = {
            1: 100,  # 完成/总数
            2: 80,   # 成功率
            3: 120,  # 平均响应时间
            4: 120,  # 平均生成速度
            5: 100,  # 当前速度
            6: 100,  # 总字符数
            7: 100   # 平均TPS
        }
        for col, width in min_widths.items():
            self.info_table.setColumnWidth(col, width)
        
        info_layout.addWidget(self.info_table)
        info_group.setLayout(info_layout)
        layout.addWidget(info_group)
        
        # 错误信息显示区域
        error_group = QGroupBox("错误信息")
        error_layout = QVBoxLayout()
        self.error_text = QTextEdit()
        self.error_text.setReadOnly(True)
        self.error_text.setMaximumHeight(60)  # 减小高度
        self.error_text.setPlaceholderText("测试过程中的错误信息将在此显示...")
        error_layout.addWidget(self.error_text)
        error_group.setLayout(error_layout)
        layout.addWidget(error_group)
        
        # 设置布局间距
        layout.setSpacing(10)  # 增加组件之间的间距
        self.setLayout(layout)
    
    def update_dataset_info(self, dataset_name: str, stats: dict):
        """更新数据集测试信息"""
        # 查找数据集行
        found = False
        for row in range(self.info_table.rowCount()):
            if self.info_table.item(row, 0).text() == dataset_name:
                found = True
                break
        
        # 如果没找到，添加新行
        if not found:
            row = self.info_table.rowCount()
            self.info_table.insertRow(row)
            self.info_table.setItem(row, 0, QTableWidgetItem(dataset_name))
        
        # 更新统计信息
        completion = f"{stats['successful']}/{stats['total']}"
        self.info_table.setItem(row, 1, QTableWidgetItem(completion))
        
        success_rate = (stats['successful'] / stats['total'] * 100) if stats['total'] > 0 else 0
        self.info_table.setItem(row, 2, QTableWidgetItem(f"{success_rate:.1f}%"))
        
        avg_time = stats['total_time'] / stats['successful'] if stats['successful'] > 0 else 0
        self.info_table.setItem(row, 3, QTableWidgetItem(f"{avg_time:.1f}s"))
        
        avg_speed = stats['total_chars'] / stats['total_time'] if stats['total_time'] > 0 else 0
        self.info_table.setItem(row, 4, QTableWidgetItem(f"{avg_speed:.1f}字/秒"))
        
        current_speed = stats.get('current_speed', 0)
        self.info_table.setItem(row, 5, QTableWidgetItem(f"{current_speed:.1f}字/秒"))
        
        self.info_table.setItem(row, 6, QTableWidgetItem(str(stats['total_chars'])))
        
        avg_tps = stats['total_tokens'] / stats['total_time'] if stats['total_time'] > 0 else 0
        self.info_table.setItem(row, 7, QTableWidgetItem(f"{avg_tps:.1f}"))
    
    def add_error(self, error_msg: str):
        """添加错误信息"""
        self.error_text.append(error_msg)
    
    def clear(self):
        """清空所有信息"""
        self.info_table.setRowCount(0)
        self.error_text.clear()

class TestTab(QWidget):
    """测试标签页"""
    def __init__(self):
        super().__init__()
        self.test_manager = TestManager()
        self.test_thread = None
        self.current_test_id = None
        self.current_test_records = None  # 添加记录缓存
        self.init_ui()
        self.connect_settings_signals()
        self.load_datasets()
        self.load_models()
        
        # 连接测试管理器的信号
        self.test_manager.progress_updated.connect(self._on_progress_updated)
        logger.info("已连接进度更新信号")
    
    def _init_test_records(self, test_task_id: str, model_config: dict, selected_datasets: dict):
        """初始化测试记录"""
        try:
            # 计算实际任务数量 - 使用每个数据集的实际并发数
            total_tasks = 0
            logger.info(f"初始化测试记录，计算总任务数...")

            records = {
                "test_task_id": test_task_id,
                "session_name": test_task_id,
                "model_name": model_config["name"],
                "concurrency": self.concurrency_spin.value(),
                "datasets": {},
                "start_time": time.time(),
                "successful_tasks": 0,
                "failed_tasks": 0,
                "total_tokens": 0,
                "total_chars": 0,
                "total_time": 0,
                "avg_response_time": 0,
                "avg_generation_speed": 0,
                "avg_tps": 0,
                "status": "running"
            }
            
            # 计算总权重
            total_weight = sum(weight for _, weight in selected_datasets.values())
            
            # 初始化每个数据集的统计信息
            for dataset_name, (prompts, weight) in selected_datasets.items():
                # 计算每个数据集的实际并发数
                dataset_concurrency = max(1, int((weight / total_weight) * self.concurrency_spin.value()))
                dataset_tasks = dataset_concurrency  # 每个并发对应一个任务
                total_tasks += dataset_tasks
                
                logger.info(f"初始化数据集 {dataset_name} 的统计信息，并发数: {dataset_concurrency}，任务数: {dataset_tasks}")
                records["datasets"][dataset_name] = {
                    "total": dataset_tasks,  # 使用实际任务数
                    "successful": 0,
                    "failed": 0,
                    "total_time": 0,
                    "total_tokens": 0,
                    "total_chars": 0,
                    "avg_response_time": 0,
                    "avg_generation_speed": 0,
                    "current_speed": 0,
                    "weight": weight,
                    "concurrency": dataset_concurrency
                }
            
            # 设置总任务数
            records["total_tasks"] = total_tasks
            logger.info(f"总任务数设置为: {total_tasks}")
            
            # 保存到本地缓存
            self.current_test_records = records
            
            # 同步到 results_tab
            results_tab = self._find_results_tab()
            if results_tab:
                results_tab.current_records = records
                logger.info(f"测试记录初始化完成: {test_task_id}")
            else:
                logger.error("未找到 results_tab,无法保存初始测试记录")
            
            return records
        except Exception as e:
            logger.error(f"初始化测试记录时出错: {e}", exc_info=True)
            raise
    
    def _sync_test_records(self):
        """同步测试记录"""
        try:
            if not self.current_test_records:
                logger.warning("没有当前测试记录可同步")
                return
            
            results_tab = self._find_results_tab()
            if results_tab:
                # 确保数据一致性
                if not hasattr(results_tab, 'current_records') or not results_tab.current_records:
                    logger.info("results_tab 中无记录,执行完整同步")
                    results_tab.current_records = self.current_test_records
                else:
                    # 更新关键字段
                    for key in [
                        "test_task_id", "session_name", "model_name", "concurrency",
                        "total_tasks", "successful_tasks", "failed_tasks",
                        "total_tokens", "total_chars", "total_time", "datasets",
                        "status", "avg_response_time", "avg_generation_speed",
                        "current_speed", "avg_tps", "start_time", "end_time"
                    ]:
                        if key in self.current_test_records:
                            results_tab.current_records[key] = self.current_test_records[key]
                
                # 保存记录
                results_tab._save_test_records()
                logger.debug("测试记录已同步到 results_tab")
            else:
                logger.warning("未找到 results_tab,无法同步测试记录")
        except Exception as e:
            logger.error(f"同步测试记录时出错: {e}", exc_info=True)
    
    def init_ui(self):
        """初始化UI"""
        layout = QVBoxLayout()
        
        # 创建控制面板
        control_layout = QHBoxLayout()
        
        # 左侧面板（数据集和模型选择）
        left_panel = QVBoxLayout()
        
        # 模型选择
        model_group = QGroupBox("模型选择")
        model_layout = QFormLayout()
        self.model_combo = QComboBox()
        model_layout.addRow("选择模型:", self.model_combo)
        model_group.setLayout(model_layout)
        left_panel.addWidget(model_group)
        
        # 数据集选择
        dataset_group = QGroupBox("数据集选择")
        dataset_layout = QVBoxLayout()
        
        # 添加提示标签
        hint_label = QLabel("选择数据集并设置权重 (1-10) ：")
        dataset_layout.addWidget(hint_label)
        
        self.dataset_list = QListWidget()
        self.dataset_list.setSelectionMode(QAbstractItemView.SelectionMode.MultiSelection)
        dataset_layout.addWidget(self.dataset_list)
        
        dataset_group.setLayout(dataset_layout)
        left_panel.addWidget(dataset_group)
        
        # 并发设置
        concurrency_group = QGroupBox("并发设置")
        concurrency_layout = QFormLayout()
        
        self.concurrency_spin = QSpinBox()
        self.concurrency_spin.setRange(1, config.get("test.max_concurrency", 10))
        self.concurrency_spin.setValue(config.get("test.default_concurrency", 1))
        concurrency_layout.addRow("总并发数:", self.concurrency_spin)
        
        concurrency_group.setLayout(concurrency_layout)
        left_panel.addWidget(concurrency_group)
        
        # 控制按钮
        button_layout = QHBoxLayout()
        
        self.start_button = QPushButton("开始测试")
        self.start_button.clicked.connect(self.start_test)
        button_layout.addWidget(self.start_button)
        
        self.stop_button = QPushButton("停止测试")
        self.stop_button.clicked.connect(self.stop_test)
        self.stop_button.setEnabled(False)
        button_layout.addWidget(self.stop_button)
        
        left_panel.addLayout(button_layout)
        
        # 右侧面板（GPU监控和测试进度）
        right_panel = QVBoxLayout()
        
        # 添加GPU监控
        self.gpu_monitor = GPUMonitorWidget()
        right_panel.addWidget(self.gpu_monitor)
        
        # 添加测试进度组件
        progress_group = QGroupBox("测试进度")
        progress_layout = QVBoxLayout()
        
        # 进度条
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        progress_layout.addWidget(self.progress_bar)
        
        # 进度信息显示区域
        self.detail_text = QTextEdit()
        self.detail_text.setReadOnly(True)
        self.detail_text.setMaximumHeight(60)  # 减小高度
        self.detail_text.setPlaceholderText("测试进行中...")
        progress_layout.addWidget(self.detail_text)
        
        progress_group.setLayout(progress_layout)
        right_panel.addWidget(progress_group)
        
        # 组装控制面板
        control_layout.addLayout(left_panel, 1)  # 左侧面板占比更大
        control_layout.addLayout(right_panel, 1)  # 右侧面板占比相等
        layout.addLayout(control_layout)
        
        # 添加测试信息显示
        self.test_info = TestInfoWidget()
        layout.addWidget(self.test_info)
        
        self.setLayout(layout)
        
        # 启动GPU监控
        self.gpu_monitor.start_monitoring()
    
    def connect_settings_signals(self):
        """连接设置更新信号"""
        try:
            # 查找主窗口
            main_window = self.window()
            if main_window:
                # 查找设置标签页
                settings_tab = main_window.findChild(QWidget, "settings_tab")
                if settings_tab:
                    # 查找模型设置组件
                    model_settings = settings_tab.findChild(QWidget, "model_settings")
                    if model_settings:
                        model_settings.model_updated.connect(self.load_models)
                        logger.info("成功连接模型更新信号")
                    else:
                        logger.warning("未找到模型设置组件")
                else:
                    logger.warning("未找到设置标签页")
            else:
                logger.warning("未找到主窗口")
        except Exception as e:
            logger.error(f"连接设置信号失败: {e}")
    
    def load_datasets(self):
        """加载数据集"""
        for name, prompts in DATASETS.items():
            item = QListWidgetItem()
            widget = DatasetListItem(name)
            item.setSizeHint(widget.sizeHint())
            self.dataset_list.addItem(item)
            self.dataset_list.setItemWidget(item, widget)
    
    def load_models(self):
        """加载模型配置"""
        try:
            # 清空当前列表
            self.model_combo.clear()
            
            # 从数据库获取模型配置
            models = db_manager.get_model_configs()
            if models:
                for model in models:
                    self.model_combo.addItem(model["name"])
                logger.info(f"已加载 {len(models)} 个模型配置")
            else:
                logger.warning("未找到模型配置")
        except Exception as e:
            logger.error(f"加载模型配置失败: {e}")
            QMessageBox.critical(self, "错误", f"加载模型配置失败：{e}")
    
    def get_selected_model(self) -> dict:
        """获取选中的模型配置"""
        model_name = self.model_combo.currentText()
        if not model_name:
            return None
            
        models = db_manager.get_model_configs()
        return next((m for m in models if m["name"] == model_name), None)
    
    def get_selected_datasets(self) -> dict:
        """获取选中的数据集及其权重"""
        logger.info("开始获取选中的数据集...")
        selected_datasets = {}
        
        try:
            # 获取所有数据集
            all_datasets = {d["name"]: d["prompts"] for d in db_manager.get_datasets()}
            
            # 遍历数据集列表
            for i in range(self.dataset_list.count()):
                item = self.dataset_list.item(i)
                if not item:
                    logger.warning(f"列表项 {i} 为空")
                    continue
                
                # 检查数据集是否在UI中被选中
                if not item.isSelected():
                    logger.info(f"数据集项 {i} 未被选中，跳过")
                    continue
                
                dataset_widget = self.dataset_list.itemWidget(item)
                if not dataset_widget:
                    logger.warning(f"列表项 {i} 的widget为空")
                    continue
                
                weight = dataset_widget.get_weight()
                logger.info(f"数据集项 {i}: weight = {weight}")
                
                if weight > 0:  # 如果权重大于0，表示选中
                    dataset_name = dataset_widget.dataset_name
                    if dataset_name in all_datasets:
                        prompts = all_datasets[dataset_name]
                        # 使用权重作为并发数
                        selected_datasets[dataset_name] = (prompts, weight)
                        logger.info(f"添加数据集: {dataset_name}, prompts数量: {len(prompts)}, 并发数: {weight}")
                    else:
                        logger.warning(f"数据集 {dataset_name} 未在数据库中找到")
            
            logger.info(f"最终选中的数据集: {selected_datasets}")
            return selected_datasets
        except Exception as e:
            logger.error(f"获取选中数据集失败: {e}")
            QMessageBox.critical(self, "错误", f"获取选中数据集失败：{e}")
            return {}
    
    def start_test(self):
        """开始测试"""
        try:
            # 检查是否已经在运行
            if self.test_thread and self.test_thread.isRunning():
                QMessageBox.warning(self, "警告", "测试已在运行中")
                return
            
            # 获取选中的模型配置
            model_config = self.get_selected_model()
            if not model_config:
                QMessageBox.warning(self, "警告", "请选择模型")
                return
            
            # 获取选中的数据集
            selected_datasets = self.get_selected_datasets()
            if not selected_datasets:
                QMessageBox.warning(self, "警告", "请选择至少一个数据集")
                return
            
            # 生成测试任务ID
            test_task_id = time.strftime("test_%Y%m%d_%H%M%S")
            self.current_test_id = test_task_id
            
            # 初始化测试记录
            self._init_test_records(test_task_id, model_config, selected_datasets)
            
            logger.info(f"选中的模型配置: {model_config}")
            logger.info(f"最终选中的数据集: {selected_datasets}")
            
            # 获取并发设置
            concurrency = self.concurrency_spin.value()
            logger.info(f"设置的总并发数: {concurrency}")
            
            # 计算总权重
            total_weight = sum(weight for _, weight in selected_datasets.values())
            logger.info(f"总权重: {total_weight}")
            
            # 根据权重分配并发数
            tasks = []
            for dataset_name, (prompts, weight) in selected_datasets.items():
                # 计算分配的并发数
                dataset_concurrency = max(1, int((weight / total_weight) * concurrency))
                logger.info(f"数据集 {dataset_name} 分配的并发数: {dataset_concurrency}")
                
                # 创建测试任务
                task = TestTask(
                    dataset_name=dataset_name,
                    prompts=prompts,
                    weight=weight,
                    concurrency=dataset_concurrency
                )
                tasks.append(task)
                logger.info(f"创建测试任务: dataset={dataset_name}, prompts={len(prompts)}, weight={weight}, concurrency={dataset_concurrency}")
            
            # 创建测试线程
            self.test_thread = TestThread(
                model_config,
                tasks,
                test_task_id
            )
            self.test_thread.progress_updated.connect(self._on_progress_updated)
            self.test_thread.result_received.connect(self._on_result_received)
            self.test_thread.test_finished.connect(self._on_test_finished)
            self.test_thread.test_error.connect(self._on_test_error)
            logger.info("测试线程已创建，信号已连接")
            
            # 更新UI状态
            self.start_button.setEnabled(False)
            self.stop_button.setEnabled(True)
            self.test_info.clear()
            
            # 启动测试线程
            self.test_thread.start()
            logger.info("测试线程开始运行")
            
        except Exception as e:
            logger.error(f"启动测试失败: {e}", exc_info=True)
            QMessageBox.critical(self, "错误", f"启动测试失败: {e}")
    
    def stop_test(self):
        """停止测试"""
        if self.test_manager.running:
            self.test_manager.stop_test()
    
    def _on_progress_updated(self, progress: TestProgress):
        """处理进度更新"""
        try:
            # 更新进度条
            self.progress_bar.setValue(int(progress.progress_percentage))
            
            # 更新详细信息文本
            detail_text = (
                f"测试进行中...\n"
                f"当前进度: {progress.progress_percentage:.1f}%\n"
                f"实时速度: {progress.avg_generation_speed:.1f} 字符/秒\n"
                f"平均响应: {progress.avg_response_time:.2f}s"
            )
            
            self.detail_text.setText(detail_text)
            
            # 更新数据集统计信息
            for dataset_name, stats in progress.dataset_stats.items():
                self.test_info.update_dataset_info(dataset_name, stats)
                
            # 如果有错误信息，添加到错误显示区域
            if progress.last_error:
                self.test_info.add_error(progress.last_error)
                
            logger.debug(f"[DEBUG] 更新进度: {progress.progress_percentage:.1f}%, 错误: {progress.last_error}")
            
        except Exception as e:
            logger.error(f"[ERROR] 更新进度显示时发生错误: {e}", exc_info=True)

    def _find_results_tab(self):
        """查找results_tab组件"""
        try:
            # 遍历所有父窗口直到找到主窗口
            parent = self.parent()
            while parent and not isinstance(parent, QMainWindow):
                parent = parent.parent()
            
            if parent:
                # 查找所有标签页
                tab_widget = parent.findChild(QTabWidget)
                if tab_widget:
                    # 遍历所有标签页找到results_tab
                    for i in range(tab_widget.count()):
                        tab = tab_widget.widget(i)
                        if isinstance(tab, ResultsTab):
                            logger.debug("成功找到results_tab组件")
                            return tab
            
            logger.error("未找到results_tab组件")
            return None
        except Exception as e:
            logger.error(f"查找results_tab组件时出错: {e}")
            return None

    def _on_result_received(self, dataset_name: str, response: APIResponse):
        """处理结果接收"""
        try:
            logger.debug(f"收到API响应结果: dataset={dataset_name}, success={response.success}")
            
            if not self.current_test_records:
                logger.error("当前测试记录不存在,无法处理结果")
                return
            
            # 更新数据集统计信息
            if dataset_name not in self.current_test_records["datasets"]:
                logger.warning(f"数据集 {dataset_name} 不存在于记录中,正在初始化...")
                self.current_test_records["datasets"][dataset_name] = {
                    "total": 1,  # 初始化为1，因为这是第一个任务
                    "successful": 0,
                    "failed": 0,
                    "total_time": 0,
                    "total_tokens": 0,
                    "total_chars": 0,
                    "avg_response_time": 0,
                    "avg_generation_speed": 0,
                    "current_speed": 0,
                    "weight": 1
                }
            
            dataset_stats = self.current_test_records["datasets"][dataset_name]
            
            # 更新统计数据
            if response.success:
                dataset_stats["successful"] += 1
                dataset_stats["total_time"] += response.duration
                dataset_stats["total_tokens"] += response.total_tokens
                dataset_stats["total_chars"] += response.total_chars
                
                # 更新平均值
                if dataset_stats["successful"] > 0:
                    dataset_stats["avg_response_time"] = dataset_stats["total_time"] / dataset_stats["successful"]
                    if dataset_stats["total_time"] > 0:
                        dataset_stats["avg_generation_speed"] = dataset_stats["total_chars"] / dataset_stats["total_time"]
                        dataset_stats["current_speed"] = response.total_chars / response.duration
                
                # 更新总体统计
                self.current_test_records["successful_tasks"] += 1
                self.current_test_records["total_tokens"] += response.total_tokens
                self.current_test_records["total_chars"] += response.total_chars
                self.current_test_records["total_time"] += response.duration
            else:
                dataset_stats["failed"] += 1
                self.current_test_records["failed_tasks"] += 1
            
            # 更新总体平均值
            if self.current_test_records["successful_tasks"] > 0:
                total_time = self.current_test_records["total_time"]
                if total_time > 0:
                    self.current_test_records["avg_response_time"] = total_time / self.current_test_records["successful_tasks"]
                    self.current_test_records["avg_generation_speed"] = self.current_test_records["total_chars"] / total_time
                    self.current_test_records["current_speed"] = self.current_test_records["avg_generation_speed"]
                    self.current_test_records["avg_tps"] = self.current_test_records["total_tokens"] / total_time
            
            # 定期同步(每10条结果同步一次)
            total_processed = (self.current_test_records["successful_tasks"] + 
                             self.current_test_records["failed_tasks"])
            if total_processed % 10 == 0:
                self._sync_test_records()
            
            # 更新UI显示
            self.test_info.update_dataset_info(dataset_name, dataset_stats)
            if not response.success:
                self.test_info.add_error(f"数据集 {dataset_name} 错误: {response.error_msg}")
            
        except Exception as e:
            logger.error(f"处理测试结果时出错: {e}", exc_info=True)

    def _on_test_finished(self):
        """处理测试完成"""
        try:
            logger.info("测试完成回调被触发")
            
            if self.current_test_records:
                # 更新状态和结束时间
                self.current_test_records["status"] = "completed"
                self.current_test_records["end_time"] = time.time()
                
                # 更新总体统计
                total_time = self.current_test_records["end_time"] - self.current_test_records["start_time"]
                self.current_test_records["total_time"] = total_time
                
                # 计算各数据集的平均值
                dataset_stats = self.current_test_records.get("datasets", {})
                valid_datasets = [stats for stats in dataset_stats.values() if stats["successful"] > 0]
                
                if valid_datasets:
                    # 计算所有数据集平均响应时间的平均值
                    avg_response_times = [stats["avg_response_time"] for stats in valid_datasets]
                    self.current_test_records["avg_response_time"] = sum(avg_response_times) / len(avg_response_times)
                    
                    # 计算所有数据集平均生成速度的平均值
                    avg_generation_speeds = [stats["avg_generation_speed"] for stats in valid_datasets]
                    self.current_test_records["avg_generation_speed"] = sum(avg_generation_speeds) / len(avg_generation_speeds)
                    
                    # 计算所有数据集平均TPS的平均值
                    avg_tps_values = [
                        stats["total_tokens"] / stats["total_time"] 
                        for stats in valid_datasets 
                        if stats["total_time"] > 0
                    ]
                    if avg_tps_values:
                        self.current_test_records["avg_tps"] = sum(avg_tps_values) / len(avg_tps_values)
                    else:
                        self.current_test_records["avg_tps"] = 0
                else:
                    # 如果没有成功的数据集，所有平均值设为0
                    self.current_test_records["avg_response_time"] = 0
                    self.current_test_records["avg_generation_speed"] = 0
                    self.current_test_records["avg_tps"] = 0
                
                # 最后一次同步并保存
                results_tab = self._find_results_tab()
                if results_tab:
                    results_tab.current_records = self.current_test_records
                    results_tab._save_test_records()
                    # 刷新记录列表
                    results_tab._load_history_records()
                else:
                    logger.error("未找到results_tab，无法保存最终测试记录")
            
            # 更新UI状态
            self.start_button.setEnabled(True)
            self.stop_button.setEnabled(False)
            
            # 清理测试线程
            if self.test_thread:
                logger.info("正在清理测试线程...")
                self.test_thread.quit()
                if not self.test_thread.wait(5000):
                    logger.warning("测试线程未能正常退出")
                    self.test_thread.terminate()
                else:
                    logger.info("测试线程已正常退出")
                self.test_thread = None
            
            # 清理当前记录
            self.current_test_records = None
            logger.info("测试完成处理结束")
            
        except Exception as e:
            logger.error(f"处理测试完成时出错: {e}", exc_info=True)

    def _on_test_error(self, error_msg: str):
        """处理测试错误"""
        try:
            logger.error(f"测试执行出错: {error_msg}")
            
            if self.current_test_records:
                # 更新状态和错误信息
                self.current_test_records["status"] = "error"
                self.current_test_records["error_message"] = error_msg
                self.current_test_records["end_time"] = time.time()
                
                # 保存错误状态
                self._sync_test_records()
            
            # 更新UI状态
            self.start_button.setEnabled(True)
            self.stop_button.setEnabled(False)
            
            # 显示错误信息
            QMessageBox.critical(self, "测试错误", f"测试执行出错: {error_msg}")
            
            # 清理测试线程
            if self.test_thread:
                logger.info("正在清理测试线程...")
                self.test_thread.quit()
                if not self.test_thread.wait(5000):
                    logger.warning("测试线程未能正常退出")
                    self.test_thread.terminate()
                else:
                    logger.info("测试线程已正常退出")
                self.test_thread = None
            
            # 清理当前记录
            self.current_test_records = None
            
        except Exception as e:
            logger.error(f"处理测试错误时出错: {e}", exc_info=True)
