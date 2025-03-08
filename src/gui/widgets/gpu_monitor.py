"""
GPU监控组件模块
"""
import time
from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QGroupBox,
    QLabel,
    QComboBox,
    QPushButton,
    QProgressBar,
    QSizePolicy,
    QFormLayout,
    QStackedWidget,
    QGridLayout,
    QLineEdit,
    QMessageBox
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QFont
from src.utils.logger import setup_logger
from src.monitor.gpu_monitor import gpu_monitor
from src.gui.i18n.language_manager import LanguageManager

# 设置日志记录器
logger = setup_logger("gpu_monitor")


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
            font.setPointSize(10)  # 增加字体大小为20pt
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

        # 多GPU视图系统信息组
        self.system_group_multi.setTitle(self.tr('system_info'))

        # 更新提示文本
        if not self.server_selector.count():
            self.hint_label.setText(self.tr('no_servers_hint'))
        else:
            self.hint_label.setText("") 

    def tr(self, key):
        """翻译文本"""
        return self.language_manager.get_text(key)

    def _update_server_config(self):
        """响应监控线程的服务器配置请求"""
        try:
            from src.data.db_manager import db_manager
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

        from src.data.db_manager import db_manager
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
            from src.data.db_manager import db_manager
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
            from src.data.db_manager import db_manager
            from src.gui.settings.gpu_settings import ServerEditDialog
            dialog = ServerEditDialog(parent=self)
            if dialog.exec():
                try:
                    server_data = dialog.get_server_data()
                    if db_manager.add_gpu_server(server_data):
                        self.refresh_servers()
                        logger.info("添加GPU服务器成功: " + server_data['name'])
                except Exception as e:
                    logger.error("添加GPU服务器失败: " + str(e))
                    QMessageBox.critical(self, self.tr('error'), "添加GPU服务器失败：" + str(e))
        except Exception as e:
            logger.error("打开添加服务器对话框失败: " + str(e))
            QMessageBox.critical(self, self.tr('error'), "打开添加服务器对话框失败：" + str(e))
    
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
                "{:.1f}W/{:.1f}W ({:.1f}%)".format(
                    gpu['power_usage'],
                    gpu['power_limit'],
                    (gpu['power_usage'] / gpu['power_limit']) * 100
                )
            )
        else:
            self.power_label.setText("{:.1f}W".format(gpu['power_usage']))

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