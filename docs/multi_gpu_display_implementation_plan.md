# 多GPU显示功能实现规划

## 1. 需求概述

当前系统只能显示单个GPU的监控信息，需要增强功能支持多GPU的同时显示。具体需求如下：

- 支持单GPU/多GPU显示模式切换
- 单GPU模式默认以当前布局显示GPU0
- 在单GPU模式下可以选择显示哪个GPU的详细信息
- 多GPU模式下可以同时查看最多8个GPU的实时状态
- 保持界面的美观，不过多影响当前的布局

## 2. 实现方案

采用混合模式实现多GPU显示功能：

- 添加GPU切换下拉菜单或标签栏，可以选择查看单个GPU或所有GPU
- 单GPU模式：保持当前布局，显示选定GPU的详细信息
- 多GPU模式：使用网格布局，每个GPU显示为一个小卡片，显示关键指标

### 2.1 数据获取层改进

修改`gpu_monitor.py`中的`get_stats`方法，使其能够获取所有GPU的信息：

```python
def get_stats(self) -> Optional[GPUStats]:
    """获取所有GPU统计信息"""
    try:
        # 获取所有GPU信息
        nvidia_smi = self._execute_command("nvidia-smi --query-gpu=index,utilization.gpu,memory.used,memory.total,temperature.gpu,power.draw,power.limit,name --format=csv,noheader,nounits")
        if not nvidia_smi:
            raise Exception("无法获取GPU信息")
        
        # 解析多GPU数据
        gpu_data_lines = nvidia_smi.strip().split('\n')
        gpus = []
        
        for line in gpu_data_lines:
            data = line.split(',')
            if len(data) < 8:  # 包含index字段，所以是8个字段
                continue
                
            gpu_index = int(data[0])
            gpu_util = float(data[1])
            memory_used = float(data[2])
            memory_total = float(data[3])
            temperature = float(data[4])
            power_usage = float(data[5]) if data[5].strip() != 'N/A' else 0.0
            power_limit = float(data[6]) if data[6].strip() != 'N/A' else 0.0
            gpu_info = data[7].strip()
            
            gpus.append({
                'index': gpu_index,
                'util': gpu_util,
                'memory_used': memory_used,
                'memory_total': memory_total,
                'temperature': temperature,
                'power_usage': power_usage,
                'power_limit': power_limit,
                'info': gpu_info
            })
        
        # 获取系统信息（与原代码相同）
        cpu_command = "top -bn1 | grep 'Cpu(s)' | awk '{print $2}'"
        cpu_output = self._execute_command(cpu_command)
        cpu_util = float(cpu_output) if cpu_output else 0.0
        
        memory_command = "free | grep Mem | awk '{print $3/$2 * 100.0}'"
        memory_output = self._execute_command(memory_command)
        memory_util = float(memory_output) if memory_output else 0.0
        
        disk_command = "df / | tail -1 | awk '{print $5}' | sed 's/%//'"
        disk_output = self._execute_command(disk_command)
        disk_util = float(disk_output) if disk_output else 0.0
        
        network_io = self._get_network_speed()
        
        cpu_info_command = "cat /proc/cpuinfo | grep 'model name' | head -n1 | cut -d':' -f2"
        cpu_info = self._execute_command(cpu_info_command) or "未知CPU"
        
        total_memory_command = "free -g | grep Mem | awk '{print $2}'"
        total_memory_output = self._execute_command(total_memory_command)
        total_memory = int(total_memory_output) if total_memory_output else 0
        
        return GPUStats(
            gpus=gpus,  # 新的多GPU数据结构
            cpu_util=cpu_util,
            memory_util=memory_util,
            disk_util=disk_util,
            network_io=network_io,
            cpu_info=cpu_info.strip(),
            gpu_count=len(gpus),
            total_memory=total_memory
        )
    except Exception as e:
        logger.error(f"获取GPU统计信息失败: {e}")
        return None
```

### 2.2 数据结构改进

修改`GPUStats`类，支持多GPU数据：

```python
class GPUStats:
    """GPU统计数据类"""
    def __init__(
        self,
        gpus: List[Dict] = None,  # 多GPU数据列表
        cpu_util: float = 0.0,    # CPU使用率
        memory_util: float = 0.0,  # 系统内存使用率
        disk_util: float = 0.0,    # 磁盘使用率
        network_io: Dict[str, float] = None,  # 网络IO统计
        timestamp: float = None,
        cpu_info: str = "",       # CPU型号信息
        gpu_count: int = 0,       # GPU数量
        total_memory: int = 0     # 系统总内存(GB)
    ):
        self.gpus = gpus or []    # 多GPU数据
        self.cpu_util = cpu_util 
        self._memory_util = memory_util     # %
        self.disk_util = disk_util         # %
        self.network_io = network_io or {}  # 包含上传下载速度
        self.timestamp = timestamp or time.time()
        self.cpu_info = cpu_info           # CPU型号
        self.gpu_count = gpu_count         # GPU数量
        self.total_memory = total_memory   # 系统总内存
    
    # 为了兼容现有代码，提供属性访问方法
    @property
    def gpu_util(self) -> float:
        """第一个GPU的利用率"""
        return self.gpus[0]['util'] if self.gpus else 0.0
    
    @property
    def memory_used(self) -> float:
        """第一个GPU的已用显存"""
        return self.gpus[0]['memory_used'] if self.gpus else 0.0
    
    @property
    def memory_total(self) -> float:
        """第一个GPU的总显存"""
        return self.gpus[0]['memory_total'] if self.gpus else 0.0
    
    @property
    def temperature(self) -> float:
        """第一个GPU的温度"""
        return self.gpus[0]['temperature'] if self.gpus else 0.0
    
    @property
    def power_usage(self) -> float:
        """第一个GPU的功率使用"""
        return self.gpus[0]['power_usage'] if self.gpus else 0.0
    
    @property
    def power_limit(self) -> float:
        """第一个GPU的功率限制"""
        return self.gpus[0]['power_limit'] if self.gpus else 0.0
    
    @property
    def gpu_info(self) -> str:
        """第一个GPU的型号信息"""
        return self.gpus[0]['info'] if self.gpus else ""
    
    @property
    def gpu_memory_util(self) -> float:
        """第一个GPU的显存使用率"""
        if not self.gpus:
            return 0.0
        gpu = self.gpus[0]
        return (gpu['memory_used'] / gpu['memory_total']) * 100 if gpu['memory_total'] > 0 else 0
    
    @property
    def memory_util(self) -> float:
        """系统内存使用率"""
        return self._memory_util
    
    @memory_util.setter
    def memory_util(self, value: float):
        """设置系统内存使用率"""
        self._memory_util = value
    
    def get_gpu(self, index: int) -> Dict:
        """获取指定索引的GPU数据"""
        if 0 <= index < len(self.gpus):
            return self.gpus[index]
        return None
    
    def get_gpu_memory_util(self, index: int) -> float:
        """获取指定GPU的显存使用率"""
        gpu = self.get_gpu(index)
        if not gpu:
            return 0.0
        return (gpu['memory_used'] / gpu['memory_total']) * 100 if gpu['memory_total'] > 0 else 0
```

### 2.3 UI改进实现

创建一个新的`MultiGPUMonitorWidget`组件，支持单GPU/多GPU切换显示：

```python
class MultiGPUMonitorWidget(QGroupBox):
    """多GPU监控组件"""
    def __init__(self):
        super().__init__()
        self.language_manager = LanguageManager()
        self.monitor_thread = MonitorThread(update_interval=0.5)
        self.monitor_thread.stats_updated.connect(self._on_stats_updated)
        self.monitor_thread.server_config_needed.connect(self._update_server_config)
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
        main_layout.addLayout(server_layout)
        
        # 显示模式切换区域
        mode_layout = QHBoxLayout()
        self.mode_label = QLabel(self.tr('display_mode') + ":")
        self.mode_combo = QComboBox()
        self.mode_combo.addItem(self.tr('single_gpu'), "single")
        self.mode_combo.addItem(self.tr('multi_gpu'), "multi")
        self.mode_combo.currentIndexChanged.connect(self._on_mode_changed)
        
        # GPU选择下拉框（单GPU模式使用）
        self.gpu_selector_label = QLabel(self.tr('select_gpu') + ":")
        self.gpu_selector = QComboBox()
        self.gpu_selector.currentIndexChanged.connect(self._on_gpu_changed)
        
        mode_layout.addWidget(self.mode_label)
        mode_layout.addWidget(self.mode_combo)
        mode_layout.addWidget(self.gpu_selector_label)
        mode_layout.addWidget(self.gpu_selector)
        mode_layout.addStretch()
        main_layout.addLayout(mode_layout)
        
        # 提示标签
        self.hint_label = QLabel()
        self.hint_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.hint_label.setStyleSheet("color: #666666;")
        main_layout.addWidget(self.hint_label)
        
        # 创建堆叠布局，用于切换单GPU和多GPU视图
        self.stacked_layout = QStackedWidget()
        
        # 单GPU视图
        self.single_gpu_widget = QWidget()
        single_gpu_layout = QVBoxLayout(self.single_gpu_widget)
        
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
        
        single_gpu_layout.addLayout(info_layout)
        
        # 多GPU视图
        self.multi_gpu_widget = QWidget()
        multi_gpu_layout = QVBoxLayout(self.multi_gpu_widget)
        
        # GPU网格布局
        self.gpu_grid_widget = QWidget()
        self.gpu_grid_layout = QGridLayout(self.gpu_grid_widget)
        self.gpu_grid_layout.setSpacing(10)  # 设置卡片间距
        
        # 系统信息（在多GPU模式下也显示）
        self.system_group_multi = QGroupBox()
        system_layout_multi = QGridLayout()  # 使用网格布局代替表单布局
        
        # CPU使用率
        cpu_widget = QGroupBox(self.tr('cpu_usage'))
        cpu_layout = QVBoxLayout()
        self.cpu_util_label_multi = QLabel("0%")
        self.cpu_util_label_multi.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.cpu_util_label_multi.setStyleSheet("font-size: 16px; font-weight: bold;")
        cpu_layout.addWidget(self.cpu_util_label_multi)
        cpu_widget.setLayout(cpu_layout)
        
        # 系统内存使用率
        mem_widget = QGroupBox(self.tr('memory_usage_sys'))
        mem_layout = QVBoxLayout()
        self.memory_util_sys_label_multi = QLabel("0%")
        self.memory_util_sys_label_multi.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.memory_util_sys_label_multi.setStyleSheet("font-size: 16px; font-weight: bold;")
        mem_layout.addWidget(self.memory_util_sys_label_multi)
        mem_widget.setLayout(mem_layout)
        
        # 磁盘使用率
        disk_widget = QGroupBox(self.tr('disk_usage'))
        disk_layout = QVBoxLayout()
        self.disk_util_label_multi = QLabel("0%")
        self.disk_util_label_multi.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.disk_util_label_multi.setStyleSheet("font-size: 16px; font-weight: bold;")
        disk_layout.addWidget(self.disk_util_label_multi)
        disk_widget.setLayout(disk_layout)
        
        # 磁盘IO延时
        disk_io_widget = QGroupBox(self.tr('disk_io_latency'))
        disk_io_layout = QVBoxLayout()
        self.disk_io_label_multi = QLabel("0ms")
        self.disk_io_label_multi.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.disk_io_label_multi.setStyleSheet("font-size: 16px; font-weight: bold;")
        disk_io_layout.addWidget(self.disk_io_label_multi)
        disk_io_widget.setLayout(disk_io_layout)
        
        # 网络接收
        net_recv_widget = QGroupBox(self.tr('network_receive'))
        net_recv_layout = QVBoxLayout()
        self.network_recv_label_multi = QLabel("0 B/s")
        self.network_recv_label_multi.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.network_recv_label_multi.setStyleSheet("font-size: 16px; font-weight: bold;")
        net_recv_layout.addWidget(self.network_recv_label_multi)
        net_recv_widget.setLayout(net_recv_layout)
        
        # 网络发送
        net_send_widget = QGroupBox(self.tr('network_send'))
        net_send_layout = QVBoxLayout()
        self.network_send_label_multi = QLabel("0 B/s")
        self.network_send_label_multi.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.network_send_label_multi.setStyleSheet("font-size: 16px; font-weight: bold;")
        net_send_layout.addWidget(self.network_send_label_multi)
        net_send_widget.setLayout(net_send_layout)
        
        # 在网格布局中放置各个系统信息组件，每行2个
        system_layout_multi.addWidget(cpu_widget, 0, 0)
        system_layout_multi.addWidget(mem_widget, 0, 1)
        system_layout_multi.addWidget(disk_widget, 1, 0)
        system_layout_multi.addWidget(disk_io_widget, 1, 1)
        system_layout_multi.addWidget(net_recv_widget, 2, 0)
        system_layout_multi.addWidget(net_send_widget, 2, 1)
        
        self.system_group_multi.setLayout(system_layout_multi)
        
        multi_gpu_layout.addWidget(self.gpu_grid_widget)
        multi_gpu_layout.addWidget(self.system_group_multi)
        
        # 添加到堆叠布局
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
```

### 2.4 事件处理与数据更新

实现显示模式切换、GPU选择和数据更新功能：

```python
def _on_mode_changed(self, index):
    """显示模式改变处理"""
    mode = self.mode_combo.itemData(index)
    self.display_mode = mode
    
    if mode == "single":
        self.stacked_layout.setCurrentIndex(0)
        self.gpu_selector_label.setVisible(True)
        self.gpu_selector.setVisible(True)
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
    layout = QVBoxLayout()
    
    # GPU型号
    info_label = QLabel()
    info_label.setWordWrap(True)
    layout.addWidget(info_label)
    
    # GPU利用率
    util_layout = QHBoxLayout()
    util_label = QLabel(self.tr('gpu_utilization') + ":")
    util_value = QLabel("0%")
    util_layout.addWidget(util_label)
    util_layout.addWidget(util_value)
    layout.addLayout(util_layout)
    
    util_progress = QProgressBar()
    util_progress.setRange(0, 100)
    layout.addWidget(util_progress)
    
    # 显存使用率
    mem_layout = QHBoxLayout()
    mem_label = QLabel(self.tr('memory_usage') + ":")
    mem_value = QLabel("0%")
    mem_layout.addWidget(mem_label)
    mem_layout.addWidget(mem_value)
    layout.addLayout(mem_layout)
    
    mem_progress = QProgressBar()
    mem_progress.setRange(0, 100)
    layout.addWidget(mem_progress)
    
    # 温度
    temp_layout = QHBoxLayout()
    temp_label = QLabel(self.tr('temperature') + ":")
    temp_value = QLabel("0°C")
    temp_layout.addWidget(temp_label)
    temp_layout.addWidget(temp_value)
    layout.addLayout(temp_layout)
    
    card.setLayout(layout)
    
    # 存储组件引用
    card_data = {
        'widget': card,
        'info_label': info_label,
        'util_value': util_value,
        'util_progress': util_progress,
        'mem_value': mem_value,
        'mem_progress': mem_progress,
        'temp_value': temp_value
    }
    
    return card_data

def _update_gpu_cards(self, stats):
    """更新GPU卡片显示"""
    if not stats or not stats.gpus:
        return
        
    # 确保有足够的GPU卡片
    while len(self.gpu_cards) < len(stats.gpus):
        card_data = self._create_gpu_card(len(self.gpu_cards))
        self.gpu_cards.append(card_data)
        
        # 添加到网格布局
        row = len(self.gpu_cards) // 4  # 每行最多4个
        col = len(self.gpu_cards) % 4
        self.gpu_grid_layout.addWidget(card_data['widget'], row, col)
    
    # 更新GPU卡片数据
    for i, gpu in enumerate(stats.gpus):
        if i >= len(self.gpu_cards):
            break
            
        card = self.gpu_cards[i]
        card['info_label'].setText(gpu['info'])
        
        # 更新利用率
        util = gpu['util']
        card['util_value'].setText(f"{util:.1f}%")
        card['util_progress'].setValue(int(util))
        
        # 更新利用率进度条颜色
        self._set_progress_bar_color(card['util_progress'], util)
        
        # 更新显存
        memory_util = (gpu['memory_used'] / gpu['memory_total']) * 100 if gpu['memory_total'] > 0 else 0
        memory_text = f"{memory_util:.1f}% ({self._format_size(gpu['memory_used'])}/{self._format_size(gpu['memory_total'])})"
        card['mem_value'].setText(memory_text)
        card['mem_progress'].setValue(int(memory_util))
        
        # 更新显存进度条颜色
        self._set_progress_bar_color(card['mem_progress'], memory_util)
        
        # 更新温度
        temp = gpu['temperature']
        card['temp_value'].setText(f"{temp:.1f}°C")
        
        # 设置温度文字颜色
        if temp >= 80:
            card['temp_value'].setStyleSheet("color: red;")
        elif temp >= 70:
            card['temp_value'].setStyleSheet("color: orange;")
        else:
            card['temp_value'].setStyleSheet("color: green;")
        
        # 显示卡片
        card['widget'].setVisible(True)
    
    # 隐藏多余的卡片
    for i in range(len(stats.gpus), len(self.gpu_cards)):
        self.gpu_cards[i]['widget'].setVisible(False)

def _set_progress_bar_color(self, progress_bar, value):
    """设置进度条颜色"""
    style = ""
    if value >= 90:
        style = """
        QProgressBar::chunk {
            background-color: #FF5252; /* 红色 */
        }
        """
    elif value >= 70:
        style = """
        QProgressBar::chunk {
            background-color: #FFA726; /* 橙色 */
        }
        """
    else:
        style = """
        QProgressBar::chunk {
            background-color: #66BB6A; /* 绿色 */
        }
        """
    progress_bar.setStyleSheet(style)

def _update_single_gpu_view(self):
    """更新单GPU视图"""
    stats = self.monitor_thread.get_last_stats()
    if not stats or not stats.gpus or self.current_gpu_index >= len(stats.gpus):
        return
    
    gpu = stats.gpus[self.current_gpu_index]
    
    # 更新GPU信息
    self.gpu_info_label.setText(gpu['info'])
    
    # 更新GPU利用率
    util = gpu['util']
    self.gpu_util_label.setText(f"{util:.1f}%")
    
    # 更新显存使用率
    memory_util = (gpu['memory_used'] / gpu['memory_total']) * 100 if gpu['memory_total'] > 0 else 0
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
        self.power_label.setText("N/A")

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
                gpu_name = stats.gpus[i]['info'] if i < len(stats.gpus) else f"GPU {i}"
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
        
        self.status_label.setText("状态: 正常")
        self.status_label.setStyleSheet("color: green")
        
        # 显示监控UI
        self.show_monitor_ui()
        
    except Exception as e:
        logger.error(f"更新UI失败: {e}")
        self.status_label.setText(f"状态: 错误 - {str(e)}")
        self.status_label.setStyleSheet("color: red")

def _update_system_info(self, stats):
    """更新系统信息"""
    # 单GPU模式下的系统信息
    self.cpu_util_label.setText(f"{stats.cpu_util:.1f}%")
    self.memory_util_sys_label.setText(f"{stats.memory_util:.1f}%")
    self.disk_util_label.setText(f"{stats.disk_util:.1f}%")
    
    if stats.network_io:
        recv_speed = stats.network_io.get('receive', 0)
        send_speed = stats.network_io.get('transmit', 0)
        self.network_recv_label.setText(self._format_network_speed(recv_speed))
        self.network_send_label.setText(self._format_network_speed(send_speed))
    else:
        self.network_recv_label.setText("N/A")
        self.network_send_label.setText("N/A")
    
    # 多GPU模式下的系统信息
    self.cpu_util_label_multi.setText(f"{stats.cpu_util:.1f}%")
    self.memory_util_sys_label_multi.setText(f"{stats.memory_util:.1f}%")
    self.disk_util_label_multi.setText(f"{stats.disk_util:.1f}%")
    
    # 更新磁盘IO延时（假设从stats中获取，如果没有该字段则显示默认值）
    disk_io_latency = stats.disk_io_latency if hasattr(stats, 'disk_io_latency') else 0
    self.disk_io_label_multi.setText(f"{disk_io_latency:.1f}ms")
    
    if stats.network_io:
        self.network_recv_label_multi.setText(self._format_network_speed(recv_speed))
        self.network_send_label_multi.setText(self._format_network_speed(send_speed))
    else:
        self.network_recv_label_multi.setText("N/A")
        self.network_send_label_multi.setText("N/A")
```

## 3. UI布局示意图

### 3.1 单GPU模式

```
+------------------------------------------+
| 服务器: [选择服务器▼] [刷新] [添加]      |
| 显示模式: [单GPU ▼] GPU: [GPU 0: RTX3090▼]|
+------------------------------------------+
|                                          |
| +----------------+  +------------------+ |
| |   GPU信息      |  |    系统信息      | |
| | 型号: RTX 3090 |  | CPU使用率: 25%   | |
| | 利用率: 85%    |  | 内存使用率: 40%  | |
| | 显存: 10GB/24GB|  | 磁盘使用率: 65%  | |
| | 温度: 72°C     |  | 网络接收: 2MB/s  | |
| | 功率: 250W/350W|  | 网络发送: 1MB/s  | |
| +----------------+  +------------------+ |
|                                          |
| 状态: 正常                               |
+------------------------------------------+
```

### 3.2 多GPU模式

```
+------------------------------------------+
| 服务器: [选择服务器▼] [刷新] [添加]      |
| 显示模式: [多GPU ▼]                      |
+------------------------------------------+
|                                          |
| +----------+  +----------+  +----------+  +----------+ |
| |  GPU 0   |  |  GPU 1   |  |  GPU 2   |  |  GPU 3   | |
| | RTX 3090 |  | RTX 3090 |  | RTX 3090 |  | RTX 3090 | |
| | 利用率:85%|  | 利用率:65%|  | 利用率:10%|  | 利用率:95%| |
| | [====== ] |  | [====   ] |  | [=      ] |  | [=======] | |
| | 显存:42%  |  | 显存:38%  |  | 显存:25%  |  | 显存:60%  | |
| | [===    ] |  | [===    ] |  | [==     ] |  | [====   ] | |
| | 温度:75°C |  | 温度:70°C |  | 温度:65°C |  | 温度:82°C | |
| +----------+  +----------+  +----------+  +----------+ |
|                                          |
| +----------+  +----------+  +----------+  +----------+ |
| |  GPU 4   |  |  GPU 5   |  |  GPU 6   |  |  GPU 7   | |
| | RTX 3090 |  | RTX 3090 |  | RTX 3090 |  | RTX 3090 | |
| | 利用率:5% |  | 利用率:45%|  | 利用率:30%|  | 利用率:50%| |
| | [       ] |  | [===    ] |  | [==     ] |  | [===    ] | |
| | 显存:20%  |  | 显存:35%  |  | 显存:15%  |  | 显存:40%  | |
| | [=      ] |  | [==     ] |  | [=      ] |  | [===    ] | |
| | 温度:60°C |  | 温度:68°C |  | 温度:63°C |  | 温度:72°C | |
| +----------+  +----------+  +----------+  +----------+ |
|                                          |
| +------------------+  +------------------+ |
| | CPU使用率: 25%    |  | 内存使用率: 40%   | |
| +------------------+  +------------------+ |
| +------------------+  +------------------+ |
| | 磁盘使用率: 65%   |  | 磁盘IO延时: 5ms  | |
| +------------------+  +------------------+ |
| +------------------+  +------------------+ |
| | 网络接收: 2MB/s   |  | 网络发送: 1MB/s  | |
| +------------------+  +------------------+ |
|                                          |
| 状态: 正常                               |
+------------------------------------------+
```

## 4. 实现步骤

1. 修改`GPUStats`类，支持多GPU数据结构
2. 修改`GPUMonitor.get_stats()`方法，获取所有GPU的信息
3. 创建新的`MultiGPUMonitorWidget`组件，替换原有的`GPUMonitorWidget`
4. 在`TestTab`中使用新的组件
5. 实现显示模式切换和GPU选择功能
6. 实现单GPU和多GPU两种视图的布局和数据更新
7. 添加进度条和状态指示的颜色变化，增强可视化效果

## 5. 多语言支持

需要在语言配置文件中添加以下翻译项：

```
"display_mode": "显示模式",
"single_gpu": "单GPU模式",
"multi_gpu": "多GPU模式",
"select_gpu": "选择GPU",
"disk_io_latency": "磁盘IO延时"
```

## 6. 预期效果

1. 用户可以灵活切换单GPU/多GPU显示模式
2. 单GPU模式下能查看选定GPU的详细信息
3. 多GPU模式下能同时监控多个GPU的关键指标
4. 用色和进度条清晰展示各项指标的状态等级
5. 保持界面美观且布局合理，不会过度影响当前UI

## 7. 风险和限制

1. 对于GPU数量非常多（>8）的服务器，可能需要额外的分页机制
2. 网格布局在窗口较小时可能导致卡片过小，影响可读性
3. 需要确保向后兼容性，不影响现有功能

## 8. 未来扩展可能

1. 添加GPU状态历史数据图表，直观显示性能变化
2. 支持GPU卡片的折叠/展开详情功能
3. 添加GPU使用情况告警与通知功能
4. 支持多服务器的GPU监控切换 