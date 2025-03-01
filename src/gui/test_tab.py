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
from src.gui.i18n.language_manager import LanguageManager
from typing import List, Dict

logger = setup_logger("test_tab")

class DatasetListItem(QWidget):
    """数据集列表项"""
    def __init__(self, dataset_name: str, parent=None):
        super().__init__(parent)
        self.dataset_name = dataset_name
        self.language_manager = LanguageManager()
        self.init_ui()
        
        # 连接语言改变信号
        self.language_manager.language_changed.connect(self.update_ui_text)
        logger.info(f"创建数据集列表项: {dataset_name}")
    
    def init_ui(self):
        """初始化UI"""
        layout = QHBoxLayout()
        layout.setContentsMargins(5, 2, 5, 2)
        layout.setSpacing(10)  # 增加组件之间的间距
        
        # 数据集名称标签
        self.name_label = QLabel(self.tr(self.dataset_name))
        self.name_label.setMinimumWidth(100)  # 设置最小宽度确保名称显示完整
        layout.addWidget(self.name_label)
        
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
        self.weight_label = QLabel(f"{self.tr('weight')}: 1")
        self.weight_label.setFixedWidth(80)  # 设置固定宽度
        self.weight_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)  # 右对齐
        
        layout.addWidget(self.weight_slider, 1)  # 设置stretch factor为1，允许滑块拉伸
        layout.addWidget(self.weight_label)
        
        self.setLayout(layout)
        logger.info(f"数据集 {self.dataset_name} 初始化完成，默认权重: 1")
    
    def tr(self, key):
        """翻译文本"""
        return self.language_manager.get_text(key)
    
    def update_ui_text(self):
        """更新UI文本"""
        self.name_label.setText(self.tr(self.dataset_name))
        self.weight_label.setText(f"{self.tr('weight')}: {self.weight_slider.value()}")
    
    def _on_weight_changed(self, value):
        """权重值变更处理"""
        self.weight_label.setText(f"{self.tr('weight')}: {value}")
    
    def get_weight(self) -> int:
        """获取权重值"""
        return self.weight_slider.value()

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
        super().__init__()
        self.language_manager = LanguageManager()
        self.monitor_thread = MonitorThread(update_interval=0.5)
        self.monitor_thread.stats_updated.connect(self._on_stats_updated)
        self.monitor_thread.server_config_needed.connect(self._update_server_config)
        self._monitor_initialized = False
        self.init_ui()
        self.update_ui_text()
        
        # 连接语言改变信号
        self.language_manager.language_changed.connect(self.update_ui_text)
    
    def update_ui_text(self):
        """更新UI文本"""
        self.setTitle(self.tr('gpu_monitor'))
        
        # 更新服务器选择区域
        self.server_label.setText(self.tr('select_server') + ':')
        self.refresh_button.setText(self.tr('refresh'))
        self.add_button.setText(self.tr('add'))
        
        # 更新GPU信息区域
        self.gpu_group.setTitle(self.tr('gpu_info'))
        self.gpu_info_label.setText(self.tr('not_connected'))
        self.gpu_model_row.setText(self.tr('gpu_model') + ':')
        self.gpu_util_row.setText(self.tr('gpu_utilization') + ':')
        self.memory_util_row.setText(self.tr('memory_usage') + ':')
        self.temp_row.setText(self.tr('temperature') + ':')
        self.power_row.setText(self.tr('power_usage') + ':')
        
        # 更新系统信息区域
        self.system_group.setTitle(self.tr('system_info'))
        self.cpu_util_row.setText(self.tr('cpu_usage') + ':')
        self.memory_util_sys_row.setText(self.tr('memory_usage_sys') + ':')
        self.disk_util_row.setText(self.tr('disk_usage') + ':')
        self.network_recv_row.setText(self.tr('network_receive') + ':')
        self.network_send_row.setText(self.tr('network_send') + ':')
    
    def tr(self, key):
        """翻译文本"""
        return self.language_manager.get_text(key)
    
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
        self.server_label = QLabel()
        self.server_selector = QComboBox()
        self.server_selector.currentIndexChanged.connect(self.on_server_changed)
        self.refresh_button = QPushButton()
        self.refresh_button.clicked.connect(self.refresh_servers)
        self.add_button = QPushButton()
        self.add_button.clicked.connect(self.add_server)
        
        server_layout.addWidget(self.server_label)
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
        self.gpu_group = QGroupBox()
        gpu_layout = QFormLayout()
        
        # GPU型号信息
        self.gpu_info_label = QLabel()
        self.gpu_model_row = QLabel()
        gpu_layout.addRow(self.gpu_model_row, self.gpu_info_label)
        
        # GPU利用率
        self.gpu_util_label = QLabel("0%")
        self.gpu_util_row = QLabel()
        gpu_layout.addRow(self.gpu_util_row, self.gpu_util_label)
        
        # 显存使用率
        self.memory_util_label = QLabel("0%")
        self.memory_util_row = QLabel()
        gpu_layout.addRow(self.memory_util_row, self.memory_util_label)
        
        # 温度
        self.temp_label = QLabel("0°C")
        self.temp_row = QLabel()
        gpu_layout.addRow(self.temp_row, self.temp_label)
        
        # 功率使用
        self.power_label = QLabel("0W")
        self.power_row = QLabel()
        gpu_layout.addRow(self.power_row, self.power_label)
        
        self.gpu_group.setLayout(gpu_layout)
        info_layout.addWidget(self.gpu_group)
        
        # 右侧系统信息
        self.system_group = QGroupBox()
        system_layout = QFormLayout()
        
        # CPU使用率
        self.cpu_util_label = QLabel("0%")
        self.cpu_util_row = QLabel()
        system_layout.addRow(self.cpu_util_row, self.cpu_util_label)
        
        # 系统内存使用率
        self.memory_util_sys_label = QLabel("0%")
        self.memory_util_sys_row = QLabel()
        system_layout.addRow(self.memory_util_sys_row, self.memory_util_sys_label)
        
        # 磁盘使用率
        self.disk_util_label = QLabel("0%")
        self.disk_util_row = QLabel()
        system_layout.addRow(self.disk_util_row, self.disk_util_label)
        
        # 网络使用率
        self.network_recv_label = QLabel("0 B/s")
        self.network_recv_row = QLabel()
        system_layout.addRow(self.network_recv_row, self.network_recv_label)
        
        self.network_send_label = QLabel("0 B/s")
        self.network_send_row = QLabel()
        system_layout.addRow(self.network_send_row, self.network_send_label)
        
        self.system_group.setLayout(system_layout)
        info_layout.addWidget(self.system_group)
        
        layout.addLayout(info_layout)
        
        # 状态信息
        self.status_label = QLabel()
        layout.addWidget(self.status_label)
        
        self.setLayout(layout)
        
        # 更新所有文本
        self.update_ui_text()
        
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
        self.hint_label.setText(self.tr('please_add_gpu_server'))
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
        
        self.status_label.setText(self.tr('status_not_configured'))
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
        self.status_label.setText(self.tr('status_connected'))
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
                    # 设置为活动服务器
                    db_manager.set_gpu_server_active(server_data["name"])
                    # 重置监控状态
                    self._monitor_initialized = False
                    # 立即更新服务器配置
                    self._update_server_config()
                    # 检查 GPU 状态
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
        if bytes_per_sec < 1024:  # B/s
            return f"{bytes_per_sec:.1f} B/s"
        elif bytes_per_sec < 1024 * 1024:  # KB/s
            return f"{bytes_per_sec/1024:.1f} KB/s"
        elif bytes_per_sec < 1024 * 1024 * 1024:  # MB/s
            return f"{bytes_per_sec/(1024*1024):.1f} MB/s"
        else:  # GB/s
            return f"{bytes_per_sec/(1024*1024*1024):.1f} GB/s"

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
    """测试进度显示组件"""
    def __init__(self):
        super().__init__()
        self.language_manager = LanguageManager()
        self.setObjectName("test_progress_widget")
        self.init_ui()
        self.update_ui_text()
        
        # 连接语言改变信号
        self.language_manager.language_changed.connect(self.update_ui_text)
    
    def update_ui_text(self):
        """更新UI文本"""
        self.setTitle(self.tr('test_progress'))
    
    def tr(self, key):
        """翻译文本"""
        return self.language_manager.get_text(key)
    
    def init_ui(self):
        """初始化UI"""
        layout = QVBoxLayout()
        
        # 添加状态标签
        self.status_label = QLabel(self.tr('status_not_started'))
        self.status_label.setStyleSheet("font-weight: bold;")
        layout.addWidget(self.status_label)
        
        # 添加进度条
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        layout.addWidget(self.progress_bar)
        
        # 添加详细信息文本框
        self.detail_text = QTextEdit()
        self.detail_text.setReadOnly(True)
        self.detail_text.setMaximumHeight(60)  # 减小高度
        self.detail_text.setPlaceholderText(self.tr('test_progress_placeholder'))
        layout.addWidget(self.detail_text)
        
        self.setLayout(layout)

class TestThread(QThread):
    """测试线程"""
    progress_updated = pyqtSignal(TestProgress)
    result_received = pyqtSignal(str, APIResponse)
    test_finished = pyqtSignal()
    test_error = pyqtSignal(str)
    
    def __init__(self, model_name: str, tasks: List[TestTask], test_task_id: str):
        super().__init__()
        # 在主线程中获取模型配置
        try:
            models = db_manager.get_model_configs()
            self.model_config = next((m for m in models if m["name"] == model_name), None)
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

class TestInfoWidget(QWidget):
    """实时测试信息显示组件"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.language_manager = LanguageManager()
        self.init_ui()
        self.update_ui_text()
        
        # 连接语言改变信号
        self.language_manager.language_changed.connect(self.update_ui_text)
    
    def update_ui_text(self):
        """更新UI文本"""
        self.info_group.setTitle(self.tr('test_info'))
        self.error_group.setTitle(self.tr('error'))
        
        # 更新表格头
        self.info_table.setHorizontalHeaderLabels([
            self.tr('dataset'),
            self.tr('completion_total'),
            self.tr('success_rate'),
            self.tr('avg_response_time'),
            self.tr('avg_generation_speed'),
            self.tr('current_speed'),
            self.tr('total_chars'),
            self.tr('avg_tps')
        ])
        
        # 更新错误文本框占位符
        self.error_text.setPlaceholderText(self.tr('error_info_placeholder'))
    
    def tr(self, key):
        """翻译文本"""
        return self.language_manager.get_text(key)
        
    def init_ui(self):
        layout = QVBoxLayout()
        
        # Info group
        self.info_group = QGroupBox(self.tr('test_info'))
        info_layout = QVBoxLayout()
        
        # Info table
        self.info_table = QTableWidget()
        self.info_table.setColumnCount(8)
        
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
        self.info_group.setLayout(info_layout)
        
        # Error group
        self.error_group = QGroupBox(self.tr('error'))
        error_layout = QVBoxLayout()
        
        self.error_text = QTextEdit()
        self.error_text.setReadOnly(True)
        self.error_text.setMaximumHeight(60)  # 减小高度
        self.error_text.setPlaceholderText(self.tr('error_info_placeholder'))
        error_layout.addWidget(self.error_text)
        self.error_group.setLayout(error_layout)
        
        layout.addWidget(self.info_group)
        layout.addWidget(self.error_group)
        
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
        
        # 获取语言管理器实例
        self.language_manager = LanguageManager()
        
        # 初始化成员变量
        self.test_thread = None
        self.test_task_id = None
        self.model_config = None
        self.selected_datasets = {}
        self.test_manager = TestManager()  # 添加test_manager实例
        
        # 初始化UI
        self.init_ui()
        
        # 连接语言变更信号
        self.language_manager.language_changed.connect(self.update_ui_text)
        
        # 加载初始数据
        self.load_models()
        self.load_datasets()
        
        # 连接测试管理器的信号
        self.test_manager.progress_updated.connect(self._on_progress_updated)
        logger.info("已连接进度更新信号")
    
    def update_ui_text(self):
        """更新所有UI文本"""
        # 更新标题文本
        self.model_group.setTitle(self.tr('model_group'))
        self.dataset_group.setTitle(self.tr('dataset_group'))
        self.concurrency_group.setTitle(self.tr('concurrency_group'))
        
        # 更新按钮文本
        self.refresh_btn.setText(self.tr('refresh_btn'))
        self.start_btn.setText(self.tr('start_test'))
        self.stop_btn.setText(self.tr('stop_test'))
        
        # 更新并发设置标签
        self.total_concurrency_label.setText(self.tr('total_concurrency'))
        
        # 更新其他组件的文本
        self.gpu_monitor.update_ui_text()
        self.progress_widget.update_ui_text()
        self.info_widget.update_ui_text()
    
    def tr(self, key):
        """翻译文本"""
        return self.language_manager.get_text(key)
    
    def _clear_test_state(self):
        """清除测试状态"""
        try:
            # 清理UI状态
            self.progress_widget.status_label.setText(self.tr('status_not_started'))
            self.progress_widget.status_label.setStyleSheet("font-weight: bold;")
            self.progress_widget.progress_bar.setValue(0)
            self.progress_widget.detail_text.clear()
            self.progress_widget.detail_text.setPlaceholderText(self.tr('test_progress_placeholder'))
            
            # 清理测试信息
            self.info_widget.clear()
            
            # 更新按钮状态
            self.start_btn.setEnabled(True)
            self.stop_btn.setEnabled(False)
            
            # 清理测试记录
            self.current_test_records = None
            
            logger.debug("测试状态已清除")
            
        except Exception as e:
            logger.error(f"清除测试状态失败: {e}", exc_info=True)
    
    def _init_test_records(self, test_task_id: str, model_config: dict, selected_datasets: dict):
        """初始化测试记录"""
        try:
            # 计算总权重
            total_weight = sum(weight for _, weight in selected_datasets.values())
            total_concurrency = self.concurrency_spinbox.value()
            logger.info(f"初始化测试记录: 总权重={total_weight}, 总并发数={total_concurrency}")

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
                "log_file": os.path.join("data", "logs", "tests", f"{test_task_id}.log")
            }
            
            # 初始化每个数据集的统计信息
            total_tasks = 0  # 重置总任务数
            for dataset_name, (prompts, weight) in selected_datasets.items():
                # 计算每个数据集的实际并发数
                dataset_concurrency = max(1, int((weight / total_weight) * total_concurrency))
                # 使用并发数作为该数据集的任务数
                dataset_tasks = dataset_concurrency
                total_tasks += dataset_tasks
                
                logger.info(f"数据集 {dataset_name} 配置: 权重={weight}, 并发数={dataset_concurrency}, 任务数={dataset_tasks}")
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
    
    def _sync_test_records(self):
        """同步测试记录到数据库"""
        try:
            if not self.current_test_records:
                logger.warning("没有当前测试记录可同步")
                return
            
            # 确保所有必要字段都存在
            required_fields = {
                "test_task_id": self.current_test_id,
                "session_name": self.current_test_id,
                "start_time": time.time(),
                "status": "running",
                "total_tasks": 0,
                "successful_tasks": 0,
                "failed_tasks": 0,
                "total_tokens": 0,
                "total_chars": 0,
                "total_time": 0.0,
                "avg_response_time": 0.0,
                "avg_generation_speed": 0.0,
                "current_speed": 0.0,
                "avg_tps": 0.0
            }
            
            for key, default_value in required_fields.items():
                if key not in self.current_test_records:
                    self.current_test_records[key] = default_value
            
            # 更新结束时间
            if self.current_test_records["status"] in ["completed", "error"]:
                self.current_test_records["end_time"] = time.time()
            
            # 同步到 results_tab
            results_tab = self._find_results_tab()
            if results_tab:
                # 确保数据一致性
                if not hasattr(results_tab, 'current_records') or not results_tab.current_records:
                    results_tab.current_records = self.current_test_records.copy()
                else:
                    # 更新关键字段
                    for key in [
                        "test_task_id", "session_name", "model_name", "model_config",
                        "concurrency", "total_tasks", "successful_tasks", "failed_tasks",
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
                logger.error("未找到 results_tab，无法保存测试记录")
                
        except Exception as e:
            logger.error(f"同步测试记录时出错: {e}", exc_info=True)
    
    def init_ui(self):
        """初始化UI"""
        layout = QVBoxLayout()
        
        # 创建上半部分布局
        top_layout = QHBoxLayout()
        
        # 创建左侧面板
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(0, 0, 0, 0)
        
        # 创建模型选择组
        self.model_group = QGroupBox(self.tr('model_group'))
        model_layout = QHBoxLayout()
        
        # 添加模型选择下拉框
        self.model_combo = QComboBox()
        model_layout.addWidget(self.model_combo)
        
        # 添加刷新按钮
        self.refresh_btn = QPushButton(self.tr('refresh_btn'))
        self.refresh_btn.clicked.connect(self.load_models)
        model_layout.addWidget(self.refresh_btn)
        
        self.model_group.setLayout(model_layout)
        left_layout.addWidget(self.model_group)
        
        # 创建数据集选择组
        self.dataset_group = QGroupBox(self.tr('dataset_group'))
        dataset_layout = QVBoxLayout()
        
        # 数据集列表
        self.dataset_list = QListWidget()
        # 设置多选模式
        self.dataset_list.setSelectionMode(QAbstractItemView.SelectionMode.MultiSelection)
        dataset_layout.addWidget(self.dataset_list)
        
        self.dataset_group.setLayout(dataset_layout)
        left_layout.addWidget(self.dataset_group)
        
        # 创建并发设置组
        self.concurrency_group = QGroupBox(self.tr('concurrency_group'))
        concurrency_layout = QHBoxLayout()
        
        self.total_concurrency_label = QLabel(self.tr('total_concurrency'))
        concurrency_layout.addWidget(self.total_concurrency_label)
        
        self.concurrency_spinbox = QSpinBox()
        self.concurrency_spinbox.setRange(1, 100)
        self.concurrency_spinbox.setValue(1)
        concurrency_layout.addWidget(self.concurrency_spinbox)
        
        self.concurrency_group.setLayout(concurrency_layout)
        left_layout.addWidget(self.concurrency_group)
        
        # 添加开始/停止按钮
        button_layout = QHBoxLayout()
        self.start_btn = QPushButton(self.tr('start_test'))
        self.start_btn.clicked.connect(self.start_test)
        button_layout.addWidget(self.start_btn)
        
        self.stop_btn = QPushButton(self.tr('stop_test'))
        self.stop_btn.clicked.connect(self.stop_test)
        self.stop_btn.setEnabled(False)
        button_layout.addWidget(self.stop_btn)
        
        left_layout.addLayout(button_layout)
        
        # 创建右侧面板
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(0, 0, 0, 0)
        
        # 添加 GPU 监控组件
        self.gpu_monitor = GPUMonitorWidget()
        right_layout.addWidget(self.gpu_monitor)
        
        # 添加测试进度组件
        self.progress_widget = TestProgressWidget()
        right_layout.addWidget(self.progress_widget)
        
        # 将左右面板添加到上半部分布局
        top_layout.addWidget(left_panel)
        top_layout.addWidget(right_panel)
        
        # 添加上半部分布局到主布局
        layout.addLayout(top_layout)
        
        # 添加测试信息区域
        self.info_widget = TestInfoWidget()
        layout.addWidget(self.info_widget)
        
        self.setLayout(layout)
        
        # 加载数据
        self.load_datasets()
        self.load_models()
        
        # 更新状态
        self.progress_widget.status_label.setText(self.tr('status_not_started'))
        self.progress_widget.detail_text.setPlaceholderText(self.tr('test_progress_placeholder'))
        
        # 清除测试状态
        self._clear_test_state()
    
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
                    
                    # 查找GPU设置组件
                    gpu_settings = settings_tab.findChild(QWidget, "gpu_settings")
                    if gpu_settings:
                        gpu_settings.settings_updated.connect(self._on_gpu_settings_updated)
                        logger.info("成功连接GPU设置更新信号")
                    else:
                        logger.warning("未找到GPU设置组件")
                else:
                    logger.warning("未找到设置标签页")
            else:
                logger.warning("未找到主窗口")
        except Exception as e:
            logger.error(f"连接设置信号失败: {e}")

    def _on_gpu_settings_updated(self):
        """处理GPU设置更新"""
        try:
            logger.info("GPU设置已更新，正在刷新监控...")
            if hasattr(self, 'gpu_monitor'):
                # 重新初始化GPU监控
                self.gpu_monitor._monitor_initialized = False
                self.gpu_monitor._update_server_config()
        except Exception as e:
            logger.error(f"更新GPU监控失败: {e}")
    
    def load_datasets(self):
        """加载数据集列表"""
        try:
            # 清空现有列表
            self.dataset_list.clear()
            
            # 加载数据集
            datasets = db_manager.get_datasets()
            for dataset in datasets:
                logger.info(f"数据集 {dataset['name']} 初始化完成，默认权重: {dataset.get('weight', 1)}")
                
                # 创建列表项
                list_item = QListWidgetItem(self.dataset_list)
                self.dataset_list.addItem(list_item)
                
                # 创建数据集列表项
                logger.info(f"创建数据集列表项: {dataset['name']}")
                list_widget = DatasetListItem(dataset['name'])
                list_item.setSizeHint(list_widget.sizeHint())  # 设置合适的大小
                self.dataset_list.setItemWidget(list_item, list_widget)
            
            logger.info("数据集列表加载完成")
            
        except Exception as e:
            logger.error(f"加载数据集列表失败: {e}", exc_info=True)
            QMessageBox.critical(self, self.tr('error'), f"加载数据集列表失败: {e}")
    
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
            
            # 遍历所有列表项
            for i in range(self.dataset_list.count()):
                item = self.dataset_list.item(i)
                if not item:
                    continue
                
                # 检查是否被选中
                if not item.isSelected():
                    continue
                
                # 获取对应的 DatasetListItem widget
                dataset_widget = self.dataset_list.itemWidget(item)
                if not dataset_widget:
                    continue
                
                weight = dataset_widget.get_weight()
                dataset_name = dataset_widget.dataset_name
                
                if weight > 0 and dataset_name in all_datasets:
                    prompts = all_datasets[dataset_name]
                    selected_datasets[dataset_name] = (prompts, weight)
                    logger.info(f"添加数据集: {dataset_name}, prompts数量: {len(prompts)}, 权重: {weight}")
            
            logger.info(f"最终选中的数据集: {list(selected_datasets.keys())}")
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
            
            # 清理上一次测试的状态
            self._clear_test_state()
            
            # 更新状态为开始测试
            self.progress_widget.status_label.setText("状态: 开始测试")
            self.progress_widget.status_label.setStyleSheet("font-weight: bold; color: blue;")
            
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
            
            # 获取并发设置
            total_concurrency = self.concurrency_spinbox.value()
            logger.info(f"设置的总并发数: {total_concurrency}")
            
            # 计算总权重
            total_weight = sum(weight for _, weight in selected_datasets.values())
            logger.info(f"总权重: {total_weight}")
            
            # 初始化测试记录
            self._init_test_records(test_task_id, model_config, selected_datasets)
            
            # 根据权重分配并发数并创建测试任务
            tasks = []
            for dataset_name, (prompts, weight) in selected_datasets.items():
                # 计算分配的并发数
                dataset_concurrency = max(1, int((weight / total_weight) * total_concurrency))
                logger.info(f"数据集 {dataset_name} 配置: 权重={weight}, 并发数={dataset_concurrency}")
                
                # 创建测试任务 - 使用并发数作为任务数
                task = TestTask(
                    dataset_name=dataset_name,
                    prompts=prompts,
                    weight=weight,
                    concurrency=dataset_concurrency
                )
                tasks.append(task)
                logger.info(f"创建测试任务: dataset={dataset_name}, 并发数={dataset_concurrency}")
            
            # 创建测试线程
            self.test_thread = TestThread(
                model_config["name"],  # 只传入模型名称
                tasks,
                test_task_id
            )
            
            # 连接信号
            self.test_thread.progress_updated.connect(self._on_progress_updated)
            self.test_thread.result_received.connect(self._on_result_received)
            self.test_thread.test_finished.connect(self._on_test_finished)
            self.test_thread.test_error.connect(self._on_test_error)
            logger.info("测试线程已创建，信号已连接")
            
            # 更新UI状态
            self.start_btn.setEnabled(False)
            self.stop_btn.setEnabled(True)
            self.info_widget.clear()
            
            # 初始化每个数据集的显示状态
            for dataset_name, dataset_stats in self.current_test_records["datasets"].items():
                self.info_widget.update_dataset_info(dataset_name, {
                    "total": dataset_stats["total"],
                    "successful": 0,
                    "failed": 0,
                    "total_time": 0.0,
                    "total_tokens": 0,
                    "total_chars": 0,
                    "avg_response_time": 0.0,
                    "avg_generation_speed": 0.0,
                    "current_speed": 0.0
                })
            
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
            # 计算总体进度百分比
            total = progress.total_tasks
            completed = progress.successful_tasks + progress.failed_tasks
            if total > 0:
                percentage = int((completed / total) * 100)
                self.progress_widget.progress_bar.setValue(percentage)
            
            # 更新状态标签
            status_text = f"{self.tr('completed')}: {completed}/{total}"
            self.progress_widget.status_label.setText(status_text)
            
            # 更新统计信息
            if self.current_test_records:
                self.current_test_records["successful_tasks"] = progress.successful_tasks
                self.current_test_records["failed_tasks"] = progress.failed_tasks
                
                # 只在每10个任务完成时同步一次记录
                if completed % 10 == 0:
                    self._sync_test_records()
                    
        except Exception as e:
            # 只记录错误，不影响测试继续进行
            logger.error(f"更新进度时出错: {e}")

    def _on_test_finished(self):
        """测试完成时的处理"""
        try:
            if self.current_test_records:
                # 更新状态为已完成
                self.current_test_records["status"] = "completed"
                self.current_test_records["end_time"] = time.time()
                
                # 同步最终记录
                self._sync_test_records()
            
            self._clear_test_state()
            self.progress_widget.status_label.setText(self.tr('test_complete'))
            
            # 显示完成对话框
            QMessageBox.information(
                self,
                self.tr('complete'),
                self.tr('test_completed_msg')
            )
            
            logger.info("测试已完成")
                
        except Exception as e:
            logger.error(f"处理测试完成时出错: {e}", exc_info=True)
    
    def _on_test_error(self, error_msg: str):
        """测试出错时的处理"""
        self._clear_test_state()
        QMessageBox.critical(
            self,
            self.tr('error'),
            error_msg
        )
        logger.error(f"测试出错: {error_msg}")

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
        """处理测试结果"""
        try:
            if not self.current_test_records:
                return
            
            dataset_stats = self.current_test_records["datasets"].get(dataset_name)
            if not dataset_stats:
                return
                
            if response.success:
                dataset_stats["successful"] += 1
                dataset_stats["total_tokens"] += response.total_tokens
                dataset_stats["total_chars"] += response.total_chars
                
                # 更新平均值
                if dataset_stats["successful"] > 0:
                    # 计算实际耗时
                    current_time = time.time()
                    dataset_stats["total_time"] = current_time - dataset_stats["start_time"]
                    
                    if dataset_stats["total_time"] > 0:
                        # 考虑并发数计算平均生成速度
                        dataset_stats["avg_generation_speed"] = (
                            dataset_stats["total_chars"] / dataset_stats["total_time"] / 
                            dataset_stats["concurrency"]  # 除以并发数
                        )
                        # 当前速度仍然使用单次响应的速度
                        dataset_stats["current_speed"] = (
                            response.total_chars / response.duration
                            if response.duration > 0 else 0
                        )
                        # 考虑并发数计算TPS
                        dataset_stats["avg_tps"] = (
                            dataset_stats["total_tokens"] / dataset_stats["total_time"] / 
                            dataset_stats["concurrency"]  # 除以并发数
                        )
                
                # 更新总体统计
                self.current_test_records["successful_tasks"] += 1
                self.current_test_records["total_tokens"] += response.total_tokens
                self.current_test_records["total_chars"] += response.total_chars
                
                # 计算总体实际耗时和平均值
                current_time = time.time()
                self.current_test_records["total_time"] = current_time - self.current_test_records["start_time"]
                
                if self.current_test_records["successful_tasks"] > 0:
                    if self.current_test_records["total_time"] > 0:
                        # 考虑总并发数计算总体平均生成速度
                        self.current_test_records["avg_generation_speed"] = (
                            self.current_test_records["total_chars"] / 
                            self.current_test_records["total_time"] / 
                            self.current_test_records["concurrency"]  # 除以总并发数
                        )
                        # 当前速度仍然使用单次响应的速度
                        self.current_test_records["current_speed"] = (
                            response.total_chars / response.duration
                            if response.duration > 0 else 0
                        )
                        # 考虑总并发数计算总体TPS
                        self.current_test_records["avg_tps"] = (
                            self.current_test_records["total_tokens"] / 
                            self.current_test_records["total_time"] / 
                            self.current_test_records["concurrency"]  # 除以总并发数
                        )
            else:
                dataset_stats["failed"] += 1
                self.current_test_records["failed_tasks"] += 1
            
            # 更新信息显示
            self.info_widget.update_dataset_info(dataset_name, dataset_stats)
            
        except Exception as e:
            # 只记录错误，不影响测试继续进行
            logger.error(f"处理测试结果时出错: {e}")

    def _on_dataset_clicked(self, item):
        """处理数据集列表项的点击事件"""
        # 切换选择状态
        item.setSelected(not item.isSelected())
