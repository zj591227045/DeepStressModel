"""
测试标签页模块
"""
import asyncio
import time
import uuid
import os
from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QGroupBox,
    QLabel,
    QComboBox,
    QSpinBox,
    QPushButton,
    QProgressBar,
    QTextEdit,
    QListWidget,
    QAbstractItemView,
    QListWidgetItem,
    QSlider,
    QMessageBox,
    QGridLayout,
    QSizePolicy,
    QFormLayout,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QTabWidget,
    QMainWindow,
    QStackedWidget,
    QSplitter,
    QLineEdit,
    QCheckBox,
    QFileDialog,
    QMenu)
from PyQt6.QtCore import Qt, QTimer, QThread, pyqtSignal
from PyQt6.QtGui import QFont, QAction
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

    # 数据集名称映射字典，将中文名映射到翻译键
    DATASET_NAME_MAP = {
        "数学问题": "math_qa",
        "逻辑问题": "logic_qa",
        "基础问答": "basic_qa",
        "代码生成": "code_gen",
        "文本生成": "text_gen"
    }

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
        self.name_label = QLabel(self.get_translated_name())
        self.name_label.setMinimumWidth(100)  # 设置最小宽度确保名称显示完整
        layout.addWidget(self.name_label)
        
        # 权重滑块
        self.weight_slider = QSlider(Qt.Orientation.Horizontal)
        self.weight_slider.setRange(1, 10)  # 设置权重范围1-10
        self.weight_slider.setValue(1)  # 默认权重为1
        self.weight_slider.setMinimumWidth(200)  # 设置最小宽度
        self.weight_slider.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Fixed)  # 水平方向自适应
        self.weight_slider.setTickPosition(
            QSlider.TickPosition.TicksBelow)  # 在下方显示刻度
        self.weight_slider.setTickInterval(1)  # 主刻度间隔为1
        self.weight_slider.valueChanged.connect(self._on_weight_changed)
        
        # 权重值显示标签
        self.weight_label = QLabel(f"{self.tr('weight')}: 1")
        self.weight_label.setFixedWidth(80)  # 设置固定宽度
        self.weight_label.setAlignment(
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)  # 右对齐
        
        layout.addWidget(self.weight_slider, 1)  # 设置stretch factor为1，允许滑块拉伸
        layout.addWidget(self.weight_label)
        
        self.setLayout(layout)
        logger.info(f"数据集 {self.dataset_name} 初始化完成，默认权重: 1")
    
    def tr(self, key):
        """翻译文本"""
        return self.language_manager.get_text(key)
    
    def get_translated_name(self):
        """获取翻译后的数据集名称"""
        # 如果数据集名称在映射字典中，使用对应的翻译键
        if self.dataset_name in self.DATASET_NAME_MAP:
            return self.tr(self.DATASET_NAME_MAP[self.dataset_name])
        # 否则直接使用原名称
        return self.dataset_name
    
    def update_ui_text(self):
        """更新UI文本"""
        self.name_label.setText(self.get_translated_name())
        self.weight_label.setText(
            f"{self.tr('weight')}: {self.weight_slider.value()}")
    
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
    
    def get_last_stats(self):
        """获取最近一次的统计数据"""
        return self._last_stats
    
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
                logger.error(f"监控线程错误: {e}")
            time.sleep(self.update_interval)
    
    def stop(self):
        """停止线程"""
        self.running = False


class GPUMonitorWidget(QGroupBox):
    """GPU监控组件"""

    def __init__(self):
        super().__init__()
        self.language_manager = LanguageManager()
        self.monitor_thread = MonitorThread(update_interval=0.5)
        self.monitor_thread.stats_updated.connect(self._on_stats_updated)
        self.monitor_thread.server_config_needed.connect(
            self._update_server_config)
        self._monitor_initialized = False
        self.current_gpu_index = 0  # 当前选中的GPU索引
        self.display_mode = "single"  # 显示模式：single或multi
        self.gpu_cards = []  # 存储GPU卡片组件
        self.init_ui()
        self.update_ui_text()
        
        # 连接语言改变信号
        self.language_manager.language_changed.connect(self.update_ui_text)
    
    def init_ui(self):
        """初始化UI"""
        main_layout = QVBoxLayout()
        main_layout.setSpacing(5)  # 减小组件间的间距
        main_layout.setContentsMargins(5, 5, 5, 5)  # 减小边距

        # 创建顶部控制区（服务器选择和模式切换）
        top_controls = QHBoxLayout()
        top_controls.setSpacing(5)
        
        # 服务器选择区域
        server_layout = QHBoxLayout()
        server_layout.setSpacing(2)
        self.server_label = QLabel()
        self.server_selector = QComboBox()
        self.server_selector.setMinimumWidth(150)  # 设置最小宽度，避免过窄
        self.server_selector.currentIndexChanged.connect(
            self.on_server_changed)
        self.refresh_button = QPushButton()
        self.refresh_button.setMaximumWidth(60)  # 限制按钮宽度
        self.refresh_button.clicked.connect(self.refresh_servers)
        self.add_button = QPushButton()
        self.add_button.setMaximumWidth(60)  # 限制按钮宽度
        self.add_button.clicked.connect(self.add_server)
        
        server_layout.addWidget(self.server_label)
        server_layout.addWidget(self.server_selector)
        server_layout.addWidget(self.refresh_button)
        server_layout.addWidget(self.add_button)
        top_controls.addLayout(server_layout, 3)  # 分配比例为3

        # 显示模式切换区域
        mode_layout = QHBoxLayout()
        mode_layout.setSpacing(2)
        self.mode_label = QLabel()
        self.mode_combo = QComboBox()
        self.mode_combo.addItem("", "single")  # 占位，将在update_ui_text中填充
        self.mode_combo.addItem("", "multi")
        self.mode_combo.currentIndexChanged.connect(self._on_mode_changed)

        # GPU选择下拉框（单GPU模式使用）
        self.gpu_selector_label = QLabel()
        self.gpu_selector = QComboBox()
        self.gpu_selector.currentIndexChanged.connect(self._on_gpu_changed)

        mode_layout.addWidget(self.mode_label)
        mode_layout.addWidget(self.mode_combo)
        mode_layout.addWidget(self.gpu_selector_label)
        mode_layout.addWidget(self.gpu_selector)
        top_controls.addLayout(mode_layout, 2)  # 分配比例为2

        main_layout.addLayout(top_controls)
        
        # 提示标签
        self.hint_label = QLabel()
        self.hint_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.hint_label.setStyleSheet("color: #666666;")
        self.hint_label.setWordWrap(True)  # 允许文本换行
        self.hint_label.setMaximumHeight(40)  # 限制高度
        main_layout.addWidget(self.hint_label)

        # 创建堆叠布局，用于切换单GPU和多GPU视图
        self.stacked_layout = QStackedWidget()

        # 单GPU视图
        self.single_gpu_widget = QWidget()
        single_gpu_layout = QVBoxLayout(self.single_gpu_widget)
        single_gpu_layout.setSpacing(5)
        single_gpu_layout.setContentsMargins(0, 0, 0, 0)  # 移除内边距
        
        # 监控信息显示区域（分为左右两栏）
        info_layout = QHBoxLayout()
        info_layout.setSpacing(10)
        
        # 左侧 GPU 信息
        self.gpu_group = QGroupBox()
        gpu_layout = QFormLayout()
        gpu_layout.setSpacing(8)  # 增加行距
        gpu_layout.setContentsMargins(8, 10, 8, 10)  # 增加内边距

        # 统一标签样式的函数
        def setup_label_style(label):
            label.setMinimumWidth(60)  # 设置最小宽度
            font = label.font()
            font.setPointSize(13)  # 增加字体大小为20pt
            label.setFont(font)
        
        # GPU型号信息
        self.gpu_info_label = QLabel()
        setup_label_style(self.gpu_info_label)
        self.gpu_model_row = QLabel()
        setup_label_style(self.gpu_model_row)
        gpu_layout.addRow(self.gpu_model_row, self.gpu_info_label)
        
        # GPU利用率
        self.gpu_util_label = QLabel("0%")
        setup_label_style(self.gpu_util_label)
        self.gpu_util_row = QLabel()
        setup_label_style(self.gpu_util_row)
        gpu_layout.addRow(self.gpu_util_row, self.gpu_util_label)
        
        # 显存使用率
        self.memory_util_label = QLabel("0%")
        setup_label_style(self.memory_util_label)
        self.memory_util_row = QLabel()
        setup_label_style(self.memory_util_row)
        gpu_layout.addRow(self.memory_util_row, self.memory_util_label)
        
        # 温度
        self.temp_label = QLabel("0°C")
        setup_label_style(self.temp_label)
        self.temp_row = QLabel()
        setup_label_style(self.temp_row)
        gpu_layout.addRow(self.temp_row, self.temp_label)
        
        # 功率使用
        self.power_label = QLabel("0W")
        setup_label_style(self.power_label)
        self.power_row = QLabel()
        setup_label_style(self.power_row)
        gpu_layout.addRow(self.power_row, self.power_label)
        
        self.gpu_group.setLayout(gpu_layout)
        info_layout.addWidget(self.gpu_group)
        
        # 右侧系统信息
        self.system_group = QGroupBox()
        system_layout = QFormLayout()
        system_layout.setSpacing(8)  # 保持与GPU信息相同的行距
        system_layout.setContentsMargins(8, 10, 8, 10)  # 保持与GPU信息相同的内边距
        
        # CPU使用率
        self.cpu_util_label = QLabel("0%")
        setup_label_style(self.cpu_util_label)
        self.cpu_util_row = QLabel()
        setup_label_style(self.cpu_util_row)
        system_layout.addRow(self.cpu_util_row, self.cpu_util_label)
        
        # 系统内存使用率
        self.memory_util_sys_label = QLabel("0%")
        setup_label_style(self.memory_util_sys_label)
        self.memory_util_sys_row = QLabel()
        setup_label_style(self.memory_util_sys_row)
        system_layout.addRow(
            self.memory_util_sys_row,
            self.memory_util_sys_label)
        
        # 磁盘使用率
        self.disk_util_label = QLabel("0%")
        setup_label_style(self.disk_util_label)
        self.disk_util_row = QLabel()
        setup_label_style(self.disk_util_row)
        system_layout.addRow(self.disk_util_row, self.disk_util_label)

        # 磁盘IO延时
        self.disk_io_label = QLabel("0ms")
        setup_label_style(self.disk_io_label)
        self.disk_io_row = QLabel()
        setup_label_style(self.disk_io_row)
        system_layout.addRow(self.disk_io_row, self.disk_io_label)
        
        # 网络使用率
        self.network_recv_label = QLabel("0 B/s")
        setup_label_style(self.network_recv_label)
        self.network_recv_row = QLabel()
        setup_label_style(self.network_recv_row)
        system_layout.addRow(self.network_recv_row, self.network_recv_label)
        
        self.network_send_label = QLabel("0 B/s")
        setup_label_style(self.network_send_label)
        self.network_send_row = QLabel()
        setup_label_style(self.network_send_row)
        system_layout.addRow(self.network_send_row, self.network_send_label)
        
        self.system_group.setLayout(system_layout)
        info_layout.addWidget(self.system_group)
        
        single_gpu_layout.addLayout(info_layout)

        # 多GPU视图
        self.multi_gpu_widget = QWidget()
        multi_gpu_layout = QVBoxLayout(self.multi_gpu_widget)
        multi_gpu_layout.setSpacing(5)
        multi_gpu_layout.setContentsMargins(0, 0, 0, 0)  # 移除内边距

        # GPU卡片容器（使用网格布局）
        self.gpu_cards_container = QWidget()
        self.gpu_cards_grid = QGridLayout(self.gpu_cards_container)
        self.gpu_cards_grid.setSpacing(5)
        self.gpu_cards_grid.setContentsMargins(0, 0, 0, 0)
        multi_gpu_layout.addWidget(self.gpu_cards_container, 2)  # 2倍比例

        # 系统信息（多GPU视图）
        self.system_group_multi = QGroupBox()
        system_layout_multi = QFormLayout()
        system_layout_multi.setSpacing(3)
        system_layout_multi.setContentsMargins(5, 5, 5, 5)

        # 使用两列布局来节省空间
        sys_grid = QGridLayout()
        sys_grid.setHorizontalSpacing(15)  # 水平间距
        sys_grid.setVerticalSpacing(3)     # 垂直间距

        # CPU使用率
        self.cpu_util_label_multi = QLabel("0%")
        sys_grid.addWidget(QLabel(self.tr('cpu_usage')), 0, 0)
        sys_grid.addWidget(self.cpu_util_label_multi, 0, 1)

        # 内存使用率
        self.memory_util_label_multi = QLabel("0%")
        sys_grid.addWidget(QLabel(self.tr('memory_usage_sys')), 0, 2)
        sys_grid.addWidget(self.memory_util_label_multi, 0, 3)

        # 磁盘使用率
        self.disk_util_label_multi = QLabel("0%")
        sys_grid.addWidget(QLabel(self.tr('disk_usage')), 1, 0)
        sys_grid.addWidget(self.disk_util_label_multi, 1, 1)

        # 磁盘IO延时
        self.disk_io_label_multi = QLabel("0ms")
        sys_grid.addWidget(QLabel(self.tr('disk_io_latency')), 1, 2)
        sys_grid.addWidget(self.disk_io_label_multi, 1, 3)

        # 网络接收
        self.network_recv_label_multi = QLabel("0 B/s")
        sys_grid.addWidget(QLabel(self.tr('network_receive')), 2, 0)
        sys_grid.addWidget(self.network_recv_label_multi, 2, 1)

        # 网络发送
        self.network_send_label_multi = QLabel("0 B/s")
        sys_grid.addWidget(QLabel(self.tr('network_send')), 2, 2)
        sys_grid.addWidget(self.network_send_label_multi, 2, 3)

        system_layout_multi.addRow(sys_grid)
        self.system_group_multi.setLayout(system_layout_multi)
        multi_gpu_layout.addWidget(self.system_group_multi, 1)  # 1倍比例

        self.stacked_layout.addWidget(self.single_gpu_widget)
        self.stacked_layout.addWidget(self.multi_gpu_widget)

        main_layout.addWidget(self.stacked_layout)
        
        # 状态信息
        self.status_label = QLabel()
        main_layout.addWidget(self.status_label)

        self.setLayout(main_layout)

        # 默认显示单GPU模式
        self.stacked_layout.setCurrentIndex(0)
        self.gpu_selector_label.setVisible(True)
        self.gpu_selector.setVisible(True)

    def update_ui_text(self):
        """更新UI文本"""
        # 设置组标题
        self.setTitle(self.tr('gpu_monitor'))

        # 服务器选择区域
        self.server_label.setText(self.tr('select_server'))
        self.refresh_button.setText(self.tr('refresh'))
        self.add_button.setText(self.tr('add'))

        # 显示模式区域
        self.mode_label.setText(self.tr('display_mode'))

        # 更新显示模式下拉框内容
        current_mode_index = self.mode_combo.currentIndex()
        self.mode_combo.setItemText(0, self.tr('single_gpu'))
        self.mode_combo.setItemText(1, self.tr('multi_gpu'))
        if current_mode_index >= 0:
            self.mode_combo.setCurrentIndex(current_mode_index)

        # GPU选择区域
        self.gpu_selector_label.setText(self.tr('select_gpu'))

        # GPU信息组
        self.gpu_group.setTitle(self.tr('gpu_info'))
        self.gpu_model_row.setText(self.tr('gpu_model'))
        self.gpu_util_row.setText(self.tr('gpu_utilization'))
        self.memory_util_row.setText(self.tr('memory_usage'))
        self.temp_row.setText(self.tr('temperature'))
        self.power_row.setText(self.tr('power_usage'))

        # 系统信息组
        self.system_group.setTitle(self.tr('system_info'))
        self.cpu_util_row.setText(self.tr('cpu_usage'))
        self.memory_util_sys_row.setText(self.tr('memory_usage_sys'))
        self.disk_util_row.setText(self.tr('disk_usage'))
        self.disk_io_row.setText(self.tr('disk_io_latency'))
        self.network_recv_row.setText(self.tr('network_receive'))
        self.network_send_row.setText(self.tr('network_send'))

        # 多GPU视图的系统信息组
        self.system_group_multi.setTitle(self.tr('system_info'))
        
        # 更新GPU卡片的文本
        for card in self.gpu_cards:
            if isinstance(card, dict) and 'widget' in card:
                card['util_row'].setText(self.tr('gpu_utilization') + ":")
                card['mem_row'].setText(self.tr('memory_usage') + ":")
                card['temp_row'].setText(self.tr('temperature') + ":")
                card['power_row'].setText(self.tr('power_usage') + ":")
        
        # 更新提示文本
        if not self._monitor_initialized:
            self.hint_label.setText(self.tr('please_add_gpu_server'))
            
        # 更新状态文本
        if hasattr(self, 'status_label'):
            current_text = self.status_label.text()
            if current_text.startswith('状态:'):
                self.status_label.setText(self.tr('status_normal'))

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

    def on_server_changed(self, index):
        """服务器改变处理"""
        if index < 0:
            return

        server_id = self.server_selector.itemData(index)
        if server_id:
            try:
                # 获取服务器名称然后设置为活跃
                servers = db_manager.get_gpu_servers()
                for server in servers:
                    if server.get('id') == server_id:
                        db_manager.set_gpu_server_active(
                            server.get('name', ''))
                        break

                self._monitor_initialized = False
                self._update_server_config()

                # 开始监控
                if not self.monitor_thread.isRunning():
                    self.monitor_thread.start()
            except Exception as e:
                logger.error(f"设置活动服务器失败: {e}")
                self.hint_label.setText(f"错误: {str(e)}")
    
    def refresh_servers(self):
        """刷新服务器列表"""
        try:
            self.server_selector.clear()
            servers = db_manager.get_gpu_servers()
            
            active_server = db_manager.get_active_gpu_server()
            active_index = -1

            for i, server in enumerate(servers):
                # 安全地获取名称，如果alias不存在则使用name或host
                display_name = server.get('host', '')
                if 'name' in server:
                    display_name = f"{display_name} ({server['name']})"
                self.server_selector.addItem(display_name, server.get('id'))
                if active_server and server.get(
                        'id') == active_server.get('id'):
                    active_index = i

            if active_index >= 0:
                self.server_selector.setCurrentIndex(active_index)
            elif servers:
                # 如果没有活动服务器但有服务器列表，选择第一个
                self.server_selector.setCurrentIndex(0)

            if not servers:
                    self.show_no_servers_hint()

        except Exception as e:
            logger.error(f"刷新服务器列表失败: {e}")
            self.hint_label.setText(self.tr('refresh_error') + f": {str(e)}")

    def add_server(self):
        """添加服务器处理"""
        try:
            from src.gui.components.dialog import show_server_dialog
            if show_server_dialog():
                self.refresh_servers()
        except Exception as e:
            logger.error(f"打开添加服务器对话框失败: {e}")
    
    def show_no_servers_hint(self):
        """显示无服务器提示"""
        self.hint_label.setText(self.tr('no_servers_hint'))
        self.stacked_layout.setVisible(False)
        self.status_label.setVisible(False)
        self.hint_label.setVisible(True)

    def show_monitor_ui(self):
        """显示监控UI"""
        self.hint_label.setVisible(False)
        self.stacked_layout.setVisible(True)
        self.status_label.setVisible(True)

    def _on_mode_changed(self, index):
        """显示模式改变处理"""
        mode = self.mode_combo.itemData(index)
        self.display_mode = mode

        if mode == "single":
            self.stacked_layout.setCurrentIndex(0)
            self.gpu_selector_label.setVisible(True)
            self.gpu_selector.setVisible(True)

            # 如果有GPU列表且未选中任何GPU，则默认选择GPU0
            if self.gpu_selector.count() > 0:
                if self.gpu_selector.currentIndex() < 0:
                    self.gpu_selector.setCurrentIndex(0)
                # 强制更新单GPU视图
                self._update_single_gpu_view()
        else:
            self.stacked_layout.setCurrentIndex(1)
            self.gpu_selector_label.setVisible(False)
            self.gpu_selector.setVisible(False)

    def _on_gpu_changed(self, index):
        """选择的GPU改变处理"""
        if index >= 0:
            self.current_gpu_index = index
            # 更新单GPU视图显示
            self._update_single_gpu_view()

    def _create_gpu_card(self, index):
        """创建GPU卡片组件"""
        card = QGroupBox(f"GPU {index}")
        # 设置大小策略，允许卡片在水平方向自适应调整
        card.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        layout = QVBoxLayout()
        layout.setContentsMargins(5, 10, 5, 10)  # 减小内边距提高空间利用率

        # GPU型号
        info_label = QLabel()
        info_label.setWordWrap(True)
        layout.addWidget(info_label)

        # GPU利用率 - 使用进度条替代文本标签
        util_layout = QHBoxLayout()
        util_row = QLabel(self.tr('gpu_utilization') + ":")
        util_row.setMinimumWidth(70)  # 设置最小宽度保证标签文字显示完整
        util_progress = QProgressBar()
        util_progress.setRange(0, 100)
        util_progress.setTextVisible(True)  # 显示百分比文本
        util_progress.setFormat("%v%")  # 设置显示格式
        util_progress.setMinimumWidth(120)  # 设置最小宽度
        util_progress.setMaximumHeight(20)  # 设置最大高度
        # 设置进度条的大小策略，允许在水平方向自适应调整
        util_progress.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        util_layout.addWidget(util_row)
        util_layout.addWidget(util_progress)
        layout.addLayout(util_layout)

        # 显存使用率 - 使用进度条替代文本标签
        mem_layout = QHBoxLayout()
        mem_row = QLabel(self.tr('memory_usage') + ":")
        mem_row.setMinimumWidth(70)  # 设置最小宽度保证标签文字显示完整
        mem_progress = QProgressBar()
        mem_progress.setRange(0, 100)
        mem_progress.setTextVisible(True)
        mem_progress.setFormat("%v%")
        mem_progress.setMinimumWidth(120)
        mem_progress.setMaximumHeight(20)
        # 设置进度条的大小策略，允许在水平方向自适应调整
        mem_progress.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        mem_layout.addWidget(mem_row)
        mem_layout.addWidget(mem_progress)
        # 移除mem_info标签，仅在进度条内显示百分比
        layout.addLayout(mem_layout)

        # 温度
        temp_layout = QHBoxLayout()
        temp_row = QLabel(self.tr('temperature') + ":")
        temp_row.setMinimumWidth(70)  # 设置最小宽度保证标签文字显示完整
        temp_value = QLabel("0°C")
        temp_layout.addWidget(temp_row)
        temp_layout.addWidget(temp_value)
        layout.addLayout(temp_layout)

        # 功率使用 - 使用进度条替代文本标签
        power_layout = QHBoxLayout()
        power_row = QLabel(self.tr('power_usage') + ":")
        power_row.setMinimumWidth(70)  # 设置最小宽度保证标签文字显示完整
        power_progress = QProgressBar()
        power_progress.setRange(0, 100)  # 初始范围设为0-100，后面会根据实际功率上限调整
        power_progress.setTextVisible(True)
        # 不设置格式，将在更新时动态设置
        power_progress.setMinimumWidth(120)
        power_progress.setMaximumHeight(20)
        # 设置进度条的大小策略，允许在水平方向自适应调整
        power_progress.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        power_layout.addWidget(power_row)
        power_layout.addWidget(power_progress)
        # 移除power_info标签，功率值和百分比都将在进度条内显示
        layout.addLayout(power_layout)

        card.setLayout(layout)

        # 存储组件引用
        card_data = {
            'widget': card,
            'info_label': info_label,
            'util_row': util_row,
            'util_progress': util_progress,  # 新的进度条引用
            'mem_row': mem_row,
            'mem_progress': mem_progress,  # 新的进度条引用
            'temp_row': temp_row,
            'temp_value': temp_value,
            'power_row': power_row,
            'power_progress': power_progress  # 新的进度条引用
        }

        return card_data

    def _update_gpu_cards(self, stats):
        """更新GPU卡片显示"""
        if not stats or not stats.gpus:
            # 如果没有GPU数据，隐藏所有卡片
            for card in self.gpu_cards:
                card['widget'].setVisible(False)
            return

        # 首先隐藏所有卡片
        for card in self.gpu_cards:
            card['widget'].setVisible(False)

        # 确保有足够的GPU卡片
        while len(self.gpu_cards) < len(stats.gpus):
            card_data = self._create_gpu_card(len(self.gpu_cards))
            self.gpu_cards.append(card_data)

            # 添加到网格布局
            row = len(self.gpu_cards) // 4  # 每行最多4个
            col = len(self.gpu_cards) % 4
            self.gpu_cards_grid.addWidget(card_data['widget'], row, col)

        # 更新GPU卡片数据
        for i, gpu in enumerate(stats.gpus):
            if i >= len(self.gpu_cards):
                break

            card = self.gpu_cards[i]
            
            # 更新GPU信息
            card['info_label'].setText(gpu['info'])

            # 更新GPU利用率 - 使用进度条
            util = gpu['util']
            card['util_progress'].setValue(int(util))
            # 根据利用率设置进度条颜色
            self._set_progress_bar_color(card['util_progress'], util)

            # 更新显存使用率 - 使用进度条
            memory_util = (gpu['memory_used'] / gpu['memory_total']) * 100 if gpu['memory_total'] > 0 else 0
            card['mem_progress'].setValue(int(memory_util))
            # 根据内存使用率设置进度条颜色
            self._set_progress_bar_color(card['mem_progress'], memory_util)

            # 更新温度
            temp = gpu['temperature']
            card['temp_value'].setText(f"{temp:.1f}°C")
            if temp >= 80:
                card['temp_value'].setStyleSheet("color: red;")
            elif temp >= 70:
                card['temp_value'].setStyleSheet("color: orange;")
            else:
                card['temp_value'].setStyleSheet("color: green;")

            # 更新功率使用 - 使用进度条
            if gpu['power_limit'] > 0:
                # 调整进度条的最大值为功率上限
                card['power_progress'].setMaximum(int(gpu['power_limit']))
                card['power_progress'].setValue(int(gpu['power_usage']))
                # 在进度条内同时显示功率值和百分比
                power_percent = (gpu['power_usage'] / gpu['power_limit']) * 100
                card['power_progress'].setFormat(f"{int(gpu['power_usage'])}W ({power_percent:.1f}%)")
                # 根据功率使用百分比设置进度条颜色
                self._set_progress_bar_color(card['power_progress'], power_percent)
            else:
                card['power_progress'].setMaximum(100)  # 如果没有功率上限，使用默认的100
                card['power_progress'].setValue(int(gpu['power_usage']))
                card['power_progress'].setFormat(f"{int(gpu['power_usage'])}W")

            # 显示当前卡片
            card['widget'].setVisible(True)

        # 隐藏多余的卡片（虽然在开始时已经全部隐藏，这里为了代码清晰再次确认）
        for i in range(len(stats.gpus), len(self.gpu_cards)):
            self.gpu_cards[i]['widget'].setVisible(False)

    def _set_progress_bar_color(self, progress_bar, value):
        """设置进度条颜色"""
        base_style = """
        QProgressBar {
            border: 1px solid #AAAAAA;
            border-radius: 3px;
            text-align: center;
            background: #F0F0F0;
        }
        """
        
        if value >= 90:
            style = base_style + """
            QProgressBar::chunk {
                background-color: #FF5252; /* 红色 - 危险 */
                border-radius: 2px;
            }
            """
            progress_bar.setStyleSheet(style)
        elif value >= 70:
            style = base_style + """
            QProgressBar::chunk {
                background-color: #FFA726; /* 橙色 - 警告 */
                border-radius: 2px;
            }
            """
            progress_bar.setStyleSheet(style)
        else:
            style = base_style + """
            QProgressBar::chunk {
                background-color: #66BB6A; /* 绿色 - 正常 */
                border-radius: 2px;
            }
            """
            progress_bar.setStyleSheet(style)

    def _update_single_gpu_view(self):
        """更新单GPU视图"""
        stats = self.monitor_thread.get_last_stats()
        if not stats or not stats.gpus or self.current_gpu_index >= len(
                stats.gpus):
            return
        
        gpu = stats.gpus[self.current_gpu_index]

            # 更新GPU信息
        self.gpu_info_label.setText(gpu['info'])
            
            # 更新GPU利用率
        util = gpu['util']
        self.gpu_util_label.setText(f"{util:.1f}%")
            
            # 更新显存使用率
        memory_util = (gpu['memory_used'] / gpu['memory_total']
                       ) * 100 if gpu['memory_total'] > 0 else 0
        self.memory_util_label.setText(
            f"{memory_util:.1f}% ({self._format_size(gpu['memory_used'])}/{self._format_size(gpu['memory_total'])})"
            )
            
            # 更新温度
        temp = gpu['temperature']
        self.temp_label.setText(f"{temp:.1f}°C")
            
            # 更新功率使用
        if gpu['power_limit'] > 0:
                self.power_label.setText(
                f"{gpu['power_usage']:.1f}W/{gpu['power_limit']:.1f}W ({(gpu['power_usage'] / gpu['power_limit']) * 100:.1f}%)"
                )
        else:
            self.power_label.setText(f"{gpu['power_usage']:.1f}W")

    def _on_stats_updated(self, stats):
        """处理监控数据更新"""
        if not stats:
            self.show_no_servers_hint()
            return

        try:
            # 更新GPU选择器
            if self.gpu_selector.count() != stats.gpu_count:
                self.gpu_selector.clear()
                for i in range(stats.gpu_count):
                    gpu_name = stats.gpus[i]['info'] if i < len(
                        stats.gpus) else f"GPU {i}"
                    self.gpu_selector.addItem(f"GPU {i}: {gpu_name}", i)

                # 确保current_gpu_index在有效范围内
                if self.current_gpu_index >= stats.gpu_count:
                    self.current_gpu_index = 0

                # 设置当前选中的GPU
                self.gpu_selector.setCurrentIndex(self.current_gpu_index)

            # 根据显示模式更新UI
            if self.display_mode == "single":
                self._update_single_gpu_view()
            else:
                self._update_gpu_cards(stats)
            
            # 更新系统信息（同时更新单GPU和多GPU模式下的系统信息）
            self._update_system_info(stats)

            self.status_label.setText(self.tr('status_normal'))
            self.status_label.setStyleSheet("color: green")
            
            # 显示监控UI
            self.show_monitor_ui()
            
        except Exception as e:
            logger.error(f"更新UI失败: {e}")
            self.status_label.setText(f"{self.tr('status_error')} - {str(e)}")
            self.status_label.setStyleSheet("color: red")

    def _update_system_info(self, stats):
        """更新系统信息"""
        # 单GPU模式下的系统信息
        self.cpu_util_label.setText(f"{stats.cpu_util:.1f}%")
        self.memory_util_sys_label.setText(f"{stats.memory_util:.1f}%")
        self.disk_util_label.setText(f"{stats.disk_util:.1f}%")
        self.disk_io_label.setText(f"{stats.disk_io_latency:.1f}ms")
            
        if stats.network_io:
            recv_speed = stats.network_io.get('receive_rate', 0.1)  # 默认至少0.1KB/s
            send_speed = stats.network_io.get('send_rate', 0.1)  # 默认至少0.1KB/s
            self.network_recv_label.setText(self._format_network_speed(recv_speed))
            self.network_send_label.setText(self._format_network_speed(send_speed))
        else:
            self.network_recv_label.setText("N/A")
            self.network_send_label.setText("N/A")
            
        # 多GPU模式下的系统信息
        self.cpu_util_label_multi.setText(f"{stats.cpu_util:.1f}%")
        self.memory_util_label_multi.setText(f"{stats.memory_util:.1f}%")
        self.disk_util_label_multi.setText(f"{stats.disk_util:.1f}%")
        self.disk_io_label_multi.setText(f"{stats.disk_io_latency:.1f}ms")

        if stats.network_io:
            self.network_recv_label_multi.setText(self._format_network_speed(recv_speed))
            self.network_send_label_multi.setText(self._format_network_speed(send_speed))
        else:
            self.network_recv_label_multi.setText("N/A")
            self.network_send_label_multi.setText("N/A")

    def _format_size(self, size_mb):
        """格式化显存大小显示"""
        if size_mb < 1024:
            return f"{size_mb:.0f}MB"
        else:
            return f"{size_mb / 1024:.1f}GB"

    def _format_network_speed(self, speed_kbs):
        """格式化网络速度显示

        Args:
            speed_kbs: 速度，单位为KB/s
        """
        if speed_kbs < 1.0:  # 小于1KB/s
            return f"{speed_kbs * 1000:.1f}B/s"
        elif speed_kbs < 1000.0:  # 小于1000KB/s，显示为KB/s
            return f"{speed_kbs:.1f}KB/s"
        else:  # 大于等于1000KB/s，显示为MB/s
            return f"{speed_kbs / 1000:.2f}MB/s"

    def start_monitoring(self):
        """启动监控"""
        if not self.monitor_thread.isRunning():
            self.monitor_thread.start()

    def stop_monitoring(self):
        """停止监控"""
        if self.monitor_thread.isRunning():
            self.monitor_thread.stop()
        self.monitor_thread.wait()


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
        self.detail_text.setPlaceholderText(
            self.tr('test_progress_placeholder'))
        layout.addWidget(self.detail_text)
        
        self.setLayout(layout)


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
        header.setSectionResizeMode(
            0, QHeaderView.ResizeMode.Stretch)  # 数据集名称列自适应剩余空间
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
        
        success_rate = (
            stats['successful'] /
            stats['total'] *
            100) if stats['total'] > 0 else 0
        self.info_table.setItem(
            row, 2, QTableWidgetItem(f"{success_rate:.1f}%"))

        avg_time = stats['total_time'] / \
            stats['successful'] if stats['successful'] > 0 else 0
        self.info_table.setItem(row, 3, QTableWidgetItem(f"{avg_time:.1f}s"))
        
        avg_speed = stats['total_chars'] / \
            stats['total_time'] if stats['total_time'] > 0 else 0
        self.info_table.setItem(
            row, 4, QTableWidgetItem(f"{avg_speed:.1f}字/秒"))
        
        current_speed = stats.get('current_speed', 0)
        self.info_table.setItem(
            row, 5, QTableWidgetItem(f"{current_speed:.1f}字/秒"))
        
        self.info_table.setItem(
            row, 6, QTableWidgetItem(str(stats['total_chars'])))
        
        # 获取平均TPS值，如果不存在则使用0
        avg_tps = stats.get('avg_tps', 0)
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
        self.model_group.setTitle(self.tr('model_selection'))
        self.dataset_group.setTitle(self.tr('dataset_selection'))
        self.concurrency_group.setTitle(self.tr('concurrency_settings'))
        
        # 更新按钮文本
        self.refresh_btn.setText(self.tr('refresh_model'))
        self.start_btn.setText(self.tr('start_test'))
        self.stop_btn.setText(self.tr('stop_test'))
        
        # 更新并发设置标签
        self.total_concurrency_label.setText(self.tr('total_concurrency'))
        
        # 更新其他组件的文本
        self.gpu_monitor.update_ui_text()
        self.progress_widget.update_ui_text()
        self.info_widget.update_ui_text()
        
        # 更新数据集列表项的文本
        for i in range(self.dataset_list.count()):
            item = self.dataset_list.item(i)
            if item:
                dataset_widget = self.dataset_list.itemWidget(item)
                if dataset_widget:
                    dataset_widget.update_ui_text()
    
    def tr(self, key):
        """翻译文本"""
        return self.language_manager.get_text(key)
    
    def _clear_test_state(self):
        """清除测试状态"""
        try:
            # 清理UI状态
            self.progress_widget.status_label.setText(
                self.tr('status_not_started'))
            self.progress_widget.status_label.setStyleSheet(
                "font-weight: bold;")
            self.progress_widget.progress_bar.setValue(0)
            self.progress_widget.detail_text.clear()
            self.progress_widget.detail_text.setPlaceholderText(
                self.tr('test_progress_placeholder'))
            
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
    
    def _init_test_records(
            self,
            test_task_id: str,
            model_config: dict,
            selected_datasets: dict):
        """初始化测试记录"""
        try:
            # 计算总权重
            total_weight = sum(
                weight for _,
                weight in selected_datasets.values())
            total_concurrency = self.concurrency_spinbox.value()
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
        self.model_group = QGroupBox()
        model_layout = QHBoxLayout()
        
        # 添加模型选择下拉框
        self.model_combo = QComboBox()
        model_layout.addWidget(self.model_combo)
        
        # 添加刷新按钮
        self.refresh_btn = QPushButton()
        self.refresh_btn.setText(self.tr('refresh_model'))
        self.refresh_btn.clicked.connect(self.load_models)
        model_layout.addWidget(self.refresh_btn)
        
        self.model_group.setLayout(model_layout)
        left_layout.addWidget(self.model_group)
        
        # 创建数据集选择组
        self.dataset_group = QGroupBox()
        dataset_layout = QVBoxLayout()
        
        # 数据集列表
        self.dataset_list = QListWidget()
        # 设置多选模式
        self.dataset_list.setSelectionMode(
            QAbstractItemView.SelectionMode.MultiSelection)
        dataset_layout.addWidget(self.dataset_list)
        
        self.dataset_group.setLayout(dataset_layout)
        left_layout.addWidget(self.dataset_group)
        
        # 创建并发设置组
        self.concurrency_group = QGroupBox()
        concurrency_layout = QHBoxLayout()
        
        self.total_concurrency_label = QLabel()
        self.total_concurrency_label.setText(self.tr('total_concurrency'))
        concurrency_layout.addWidget(self.total_concurrency_label)
        
        self.concurrency_spinbox = QSpinBox()
        self.concurrency_spinbox.setRange(1, 100)
        self.concurrency_spinbox.setValue(1)
        concurrency_layout.addWidget(self.concurrency_spinbox)
        
        self.concurrency_group.setLayout(concurrency_layout)
        left_layout.addWidget(self.concurrency_group)
        
        # 添加开始/停止按钮
        button_layout = QHBoxLayout()
        self.start_btn = QPushButton()
        self.start_btn.setText(self.tr('start_test'))
        self.start_btn.clicked.connect(self.start_test)
        button_layout.addWidget(self.start_btn)
        
        self.stop_btn = QPushButton()
        self.stop_btn.setText(self.tr('stop_test'))
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
        self.progress_widget.status_label.setText(
            self.tr('status_not_started'))
        self.progress_widget.detail_text.setPlaceholderText(
            self.tr('test_progress_placeholder'))
        
        
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
                    model_settings = settings_tab.findChild(
                        QWidget, "model_settings")
                    if model_settings:
                        model_settings.model_updated.connect(self.load_models)
                        logger.info("成功连接模型更新信号")
                    else:
                        logger.warning("未找到模型设置组件")
                    
                    # 查找GPU设置组件
                    gpu_settings = settings_tab.findChild(
                        QWidget, "gpu_settings")
                    if gpu_settings:
                        gpu_settings.settings_updated.connect(
                            self._on_gpu_settings_updated)
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
                logger.info(
                    f"数据集 {
                        dataset['name']} 初始化完成，默认权重: {
                        dataset.get(
                            'weight',
                            1)}")
                
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
            all_datasets = {d["name"]: d["prompts"]
                            for d in db_manager.get_datasets()}
            
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
                    logger.info(
                        f"添加数据集: {dataset_name}, prompts数量: {
                            len(prompts)}, 权重: {weight}")
            
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
            self.progress_widget.status_label.setStyleSheet(
                "font-weight: bold; color: blue;")
            
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
            total_weight = sum(
                weight for _,
                weight in selected_datasets.values())
            logger.info(f"总权重: {total_weight}")
            
            # 初始化测试记录
            self._init_test_records(
                test_task_id, model_config, selected_datasets)
            
            # 根据权重分配并发数并创建测试任务
            tasks = []
            for dataset_name, (prompts, weight) in selected_datasets.items():
                # 计算分配的并发数
                dataset_concurrency = max(
                    1, int((weight / total_weight) * total_concurrency))
                logger.info(
                    f"数据集 {dataset_name} 配置: 权重={weight}, 并发数={dataset_concurrency}")
                
                # 创建测试任务 - 使用并发数作为任务数
                task = TestTask(
                    dataset_name=dataset_name,
                    prompts=prompts,
                    weight=weight,
                    concurrency=dataset_concurrency
                )
                tasks.append(task)
                logger.info(
                    f"创建测试任务: dataset={dataset_name}, 并发数={dataset_concurrency}")
            
            # 创建测试线程
            self.test_thread = TestThread(
                model_config["name"],  # 只传入模型名称
                tasks,
                test_task_id
            )
            
            # 连接信号
            self.test_thread.progress_updated.connect(
                self._on_progress_updated)
            self.test_thread.result_received.connect(self._on_result_received)
            self.test_thread.test_finished.connect(self._on_test_finished)
            self.test_thread.test_error.connect(self._on_test_error)
            logger.info("测试线程已创建，信号已连接")
            
            # 更新UI状态
            self.start_btn.setEnabled(False)
            self.stop_btn.setEnabled(True)
            self.info_widget.clear()
            
            # 初始化每个数据集的显示状态
            for dataset_name, dataset_stats in self.current_test_records["datasets"].items(
            ):
                self.info_widget.update_dataset_info(
                    dataset_name, dataset_stats)
            
            # 启动测试线程
            self.test_thread.start()
            logger.info("测试线程开始运行")
            
        except Exception as e:
            logger.error(f"启动测试失败: {e}", exc_info=True)
    
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
            
            dataset_stats = self.current_test_records["datasets"].get(
                dataset_name)
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
                    dataset_stats["total_time"] = current_time - \
                        dataset_stats["start_time"]
                    
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
                self.current_test_records["total_time"] = current_time - \
                    self.current_test_records["start_time"]
                
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
