"""
测试标签页模块
"""
import asyncio
import time
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox,
    QLabel, QComboBox, QSpinBox, QPushButton,
    QProgressBar, QTextEdit, QListWidget, QAbstractItemView,
    QListWidgetItem, QSlider, QMessageBox, QGridLayout, QSizePolicy, QFormLayout
)
from PyQt6.QtCore import Qt, QTimer, QThread, pyqtSignal
from src.utils.config import config
from src.utils.logger import setup_logger
from src.monitor.gpu_monitor import gpu_monitor
from src.engine.test_manager import TestManager, TestTask, TestProgress
from src.gui.results_tab import ResultsTab
from src.data.test_datasets import DATASETS
from src.data.db_manager import db_manager

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
    def __init__(self, manager: TestManager, model_config: dict, tasks: list):
        super().__init__()
        self.manager = manager
        self.model_config = model_config
        self.tasks = tasks
        logger.info("测试线程已创建")
    
    def run(self):
        """运行测试"""
        logger.info("测试线程开始运行")
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            logger.info("开始执行测试任务...")
            loop.run_until_complete(
                self.manager.run_test(self.model_config, self.tasks)
            )
            logger.info("测试任务执行完成")
        except Exception as e:
            logger.error(f"测试线程执行出错: {e}")
        finally:
            logger.info("正在关闭事件循环...")
            loop.close()
            logger.info("测试线程结束运行")

class TestTab(QWidget):
    """测试标签页"""
    def __init__(self):
        super().__init__()
        self.test_manager = TestManager()
        self.test_thread = None
        self.selected_datasets = {}  # {dataset_name: (prompts, weight)}
        self.init_ui()
        
        # 连接信号
        self.test_manager.progress_updated.connect(self._on_progress_updated)
        self.test_manager.result_received.connect(self.results_tab.add_result)
        
        # 加载数据
        self.load_models()
        self.load_datasets()
        
        # 使用定时器延迟连接设置更新信号
        QTimer.singleShot(0, self.connect_settings_signals)
    
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
    
    def init_ui(self):
        """初始化UI"""
        layout = QVBoxLayout()
        
        # 控制区域
        control_layout = QHBoxLayout()
        
        # 左侧控制面板
        left_panel = QVBoxLayout()
        
        # 模型选择
        model_group = QGroupBox("模型选择")
        model_layout = QVBoxLayout()
        self.model_combo = QComboBox()
        model_layout.addWidget(self.model_combo)
        model_group.setLayout(model_layout)
        left_panel.addWidget(model_group)
        
        # 数据集选择
        dataset_group = QGroupBox("数据集选择")
        dataset_layout = QVBoxLayout()
        self.dataset_list = QListWidget()
        self.dataset_list.setSelectionMode(QAbstractItemView.SelectionMode.MultiSelection)
        dataset_layout.addWidget(QLabel("选择数据集并设置权重（1-10）："))
        dataset_layout.addWidget(self.dataset_list)
        dataset_group.setLayout(dataset_layout)
        left_panel.addWidget(dataset_group)
        
        # 并发设置
        concurrency_group = QGroupBox("并发设置")
        concurrency_layout = QHBoxLayout()
        concurrency_layout.addWidget(QLabel("总并发数:"))
        self.concurrency_spinbox = QSpinBox()
        self.concurrency_spinbox.setRange(1, 99999)  # 取消最大并发限制
        self.concurrency_spinbox.setValue(config.get("test.default_concurrency", 1))
        concurrency_layout.addWidget(self.concurrency_spinbox)
        concurrency_group.setLayout(concurrency_layout)
        left_panel.addWidget(concurrency_group)
        
        # 控制按钮
        button_layout = QHBoxLayout()
        self.start_button = QPushButton("开始测试")
        self.start_button.clicked.connect(self.start_test)
        self.stop_button = QPushButton("停止测试")
        self.stop_button.clicked.connect(self.stop_test)
        self.stop_button.setEnabled(False)
        button_layout.addWidget(self.start_button)
        button_layout.addWidget(self.stop_button)
        left_panel.addLayout(button_layout)
        
        control_layout.addLayout(left_panel)
        
        # 右侧监控面板
        right_panel = QVBoxLayout()
        
        # GPU监控
        self.gpu_monitor = GPUMonitorWidget()
        right_panel.addWidget(self.gpu_monitor)
        
        # 测试进度
        self.test_progress = TestProgressWidget()
        right_panel.addWidget(self.test_progress)
        
        control_layout.addLayout(right_panel)
        layout.addLayout(control_layout)
        
        # 结果显示
        self.results_tab = ResultsTab()
        layout.addWidget(self.results_tab)
        
        self.setLayout(layout)
        
        # 启动GPU监控
        self.gpu_monitor.start_monitoring()
    
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
        logger.info("开始测试...")
        
        # 获取选中的模型配置
        model_config = self.get_selected_model()
        if not model_config:
            logger.error("未选择模型")
            QMessageBox.warning(self, "错误", "请选择要测试的模型")
            return
        logger.info(f"选中的模型配置: {model_config}")
        
        # 获取选中的数据集
        dataset_tasks = self.get_selected_datasets()
        if not dataset_tasks:
            logger.error("未选择数据集")
            QMessageBox.warning(self, "错误", "请选择至少一个测试数据集")
            return
        logger.info(f"选中的数据集任务: {dataset_tasks}")
        
        # 获取总并发数
        total_concurrency = self.concurrency_spinbox.value()
        logger.info(f"设置的总并发数: {total_concurrency}")
        
        # 计算总权重
        total_weight = sum(weight for _, (_, weight) in dataset_tasks.items())
        logger.info(f"总权重: {total_weight}")
        
        # 创建测试任务列表
        tasks = []
        for dataset_name, (prompts, weight) in dataset_tasks.items():
            # 根据权重比例分配并发数
            dataset_concurrency = max(1, int((weight / total_weight) * total_concurrency))
            logger.info(f"数据集 {dataset_name} 分配的并发数: {dataset_concurrency}")
            
            task = TestTask(
                dataset_name=dataset_name,
                prompts=prompts,
                weight=weight,
                concurrency=dataset_concurrency  # 使用计算出的并发数
            )
            tasks.append(task)
            logger.info(f"创建测试任务: dataset={dataset_name}, prompts={len(prompts)}, "
                       f"weight={weight}, concurrency={dataset_concurrency}")
        
        # 更新UI状态
        self.start_button.setEnabled(False)
        self.stop_button.setEnabled(True)
        
        # 准备结果显示
        dataset_tasks_with_concurrency = {
            name: (prompts, task.concurrency)  # 使用计算后的并发数
            for (name, (prompts, _)), task in zip(dataset_tasks.items(), tasks)
        }
        self.results_tab.prepare_test(dataset_tasks_with_concurrency)
        
        # 创建并启动测试线程
        self.test_thread = TestThread(self.test_manager, model_config, tasks)
        self.test_thread.finished.connect(self.on_test_finished)
        self.test_thread.start()
        logger.info("测试线程已启动")
    
    def stop_test(self):
        """停止测试"""
        if self.test_manager.running:
            self.test_manager.stop_test()
    
    def on_test_finished(self):
        """测试完成回调"""
        logger.info("测试完成回调被触发")
        self.start_button.setEnabled(True)
        self.stop_button.setEnabled(False)
        
        if self.test_thread:
            logger.info("正在清理测试线程...")
            self.test_thread.quit()
            if not self.test_thread.wait(5000):  # 等待最多5秒
                logger.error("测试线程未能正常退出")
            else:
                logger.info("测试线程已正常退出")
            self.test_thread = None
        
        logger.info("测试完成处理结束")

    def _on_progress_updated(self, progress: TestProgress):
        """处理进度更新"""
        # 更新进度条
        self.test_progress.progress_bar.setValue(int(progress.progress_percentage))
        
        # 更新详细信息文本
        detail_text = (
            f"测试进行中...\n"
            f"当前进度: {progress.progress_percentage:.1f}%\n"
            f"实时速度: {progress.avg_generation_speed:.1f} 字符/秒\n"
            f"平均响应: {progress.avg_response_time:.2f}s"
        )
        
        # 如果有错误信息，添加到详细信息中
        if progress.last_error:
            detail_text += f"\n最近错误: {progress.last_error}"
            
        self.test_progress.detail_text.setText(detail_text)
