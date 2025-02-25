"""
测试标签页模块
"""
import asyncio
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox,
    QLabel, QComboBox, QSpinBox, QPushButton,
    QProgressBar, QTextEdit, QListWidget, QAbstractItemView,
    QListWidgetItem, QSlider, QMessageBox, QGridLayout, QSizePolicy
)
from PyQt6.QtCore import Qt, QTimer, QThread, pyqtSignal
from src.utils.config import config
from src.utils.logger import setup_logger
from src.monitor.gpu_monitor import gpu_manager
from src.engine.test_manager import TestManager, TestTask, TestProgress
from src.gui.results_tab import ResultsTab
from src.data.test_datasets import DATASETS

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

class GPUMonitorWidget(QGroupBox):
    """GPU监控组件"""
    def __init__(self):
        super().__init__("系统监控")
        self.init_ui()
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_stats)
        self.error_count = 0  # 添加错误计数器
        self.max_error_logs = 5  # 最大错误日志次数
    
    def init_ui(self):
        """初始化UI"""
        layout = QVBoxLayout()
        
        # 硬件信息
        hw_group = QGroupBox("硬件信息")
        hw_layout = QGridLayout()
        
        # CPU信息
        hw_layout.addWidget(QLabel("CPU型号:"), 0, 0)
        self.cpu_info_label = QLabel("获取中...")
        hw_layout.addWidget(self.cpu_info_label, 0, 1, 1, 3)
        
        # GPU信息
        hw_layout.addWidget(QLabel("GPU型号:"), 1, 0)
        self.gpu_info_label = QLabel("获取中...")
        hw_layout.addWidget(self.gpu_info_label, 1, 1, 1, 2)
        
        hw_layout.addWidget(QLabel("GPU数量:"), 1, 3)
        self.gpu_count_label = QLabel("0")
        hw_layout.addWidget(self.gpu_count_label, 1, 4)
        
        # 内存信息
        hw_layout.addWidget(QLabel("系统内存:"), 2, 0)
        self.total_memory_label = QLabel("0 GB")
        hw_layout.addWidget(self.total_memory_label, 2, 1)
        
        hw_group.setLayout(hw_layout)
        layout.addWidget(hw_group)
        
        # GPU信息
        gpu_group = QGroupBox("GPU状态")
        gpu_layout = QGridLayout()
        
        # GPU使用率
        gpu_layout.addWidget(QLabel("GPU使用率:"), 0, 0)
        self.gpu_util_label = QLabel("0%")
        gpu_layout.addWidget(self.gpu_util_label, 0, 1)
        
        # 显存使用率
        gpu_layout.addWidget(QLabel("显存使用率:"), 0, 2)
        self.memory_util_label = QLabel("0%")
        gpu_layout.addWidget(self.memory_util_label, 0, 3)
        
        # GPU温度
        gpu_layout.addWidget(QLabel("GPU温度:"), 1, 0)
        self.temp_label = QLabel("0°C")
        gpu_layout.addWidget(self.temp_label, 1, 1)
        
        # 风扇转速
        gpu_layout.addWidget(QLabel("风扇转速:"), 1, 2)
        self.fan_speed_label = QLabel("0%")
        gpu_layout.addWidget(self.fan_speed_label, 1, 3)
        
        # 功率使用
        gpu_layout.addWidget(QLabel("功率使用:"), 2, 0)
        self.power_label = QLabel("0W / 0W")
        gpu_layout.addWidget(self.power_label, 2, 1)
        
        gpu_group.setLayout(gpu_layout)
        layout.addWidget(gpu_group)
        
        # 系统信息
        sys_group = QGroupBox("系统状态")
        sys_layout = QGridLayout()
        
        # CPU使用率
        sys_layout.addWidget(QLabel("CPU使用率:"), 0, 0)
        self.cpu_util_label = QLabel("0%")
        sys_layout.addWidget(self.cpu_util_label, 0, 1)
        
        # 内存使用率
        sys_layout.addWidget(QLabel("内存使用率:"), 0, 2)
        self.sys_memory_util_label = QLabel("0%")
        sys_layout.addWidget(self.sys_memory_util_label, 0, 3)
        
        # 磁盘使用率
        sys_layout.addWidget(QLabel("磁盘使用率:"), 1, 0)
        self.disk_util_label = QLabel("0%")
        sys_layout.addWidget(self.disk_util_label, 1, 1)
        
        # 磁盘IO
        sys_layout.addWidget(QLabel("磁盘IO:"), 1, 2)
        self.disk_io_label = QLabel("读: 0 MB/s, 写: 0 MB/s")
        sys_layout.addWidget(self.disk_io_label, 1, 3)
        
        # 磁盘延迟
        sys_layout.addWidget(QLabel("磁盘延迟:"), 2, 0)
        self.disk_latency_label = QLabel("0ms")
        sys_layout.addWidget(self.disk_latency_label, 2, 1)
        
        sys_group.setLayout(sys_layout)
        layout.addWidget(sys_group)
        
        self.setLayout(layout)
    
    def start_monitoring(self):
        """开始监控"""
        self.timer.start(2000)  # 每2秒更新一次
    
    def _format_size(self, size_kb: float) -> str:
        """格式化大小显示"""
        if size_kb < 1024:
            return f"{size_kb:.1f} KB/s"
        else:
            return f"{size_kb/1024:.1f} MB/s"
    
    def update_stats(self):
        """更新统计信息"""
        stats = gpu_manager.get_stats()
        if not stats:
            self.error_count += 1
            if self.error_count <= self.max_error_logs:
                logger.error("获取GPU统计数据失败")
            return
        
        self.error_count = 0  # 重置错误计数器
        
        try:
            # 更新硬件信息
            self.cpu_info_label.setText(stats.cpu_info or "未知")
            self.gpu_info_label.setText(stats.gpu_info or "未知")
            self.gpu_count_label.setText(str(stats.gpu_count))
            self.total_memory_label.setText(f"{stats.total_memory} GB")
            
            # 更新GPU信息
            self.gpu_util_label.setText(f"{stats.gpu_util:.1f}%")
            self.memory_util_label.setText(f"{stats.gpu_memory_util:.1f}%")
            self.temp_label.setText(f"{stats.temperature:.1f}°C")
            self.fan_speed_label.setText(f"{stats.fan_speed:.1f}%")
            self.power_label.setText(f"{stats.power_usage:.1f}W / {stats.power_limit:.1f}W")
            
            # 更新系统信息
            self.cpu_util_label.setText(f"{stats.cpu_util:.1f}%")
            self.sys_memory_util_label.setText(f"{stats.memory_util:.1f}%")
            self.disk_util_label.setText(f"{stats.disk_util:.1f}%")
            
            # 更新磁盘IO信息
            if stats.disk_io:
                read_speed = self._format_size(stats.disk_io["read"])
                write_speed = self._format_size(stats.disk_io["write"])
                self.disk_io_label.setText(f"读: {read_speed}, 写: {write_speed}")
                self.disk_latency_label.setText(f"{stats.disk_io.get('await', 0.0):.1f}ms")
            
        except Exception as e:
            self.error_count += 1
            if self.error_count <= self.max_error_logs:
                logger.error(f"更新GPU统计数据显示失败: {e}")

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
        self.test_manager.progress_updated.connect(self._on_progress_updated)  # 添加进度更新信号连接
        self.test_manager.result_received.connect(self.results_tab.add_result)
        
        self.load_models()
    
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
        self.model_selector = QComboBox()
        model_layout.addWidget(self.model_selector)
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
        
        # 加载数据集
        self.load_datasets()
        
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
        models = config.get("models", {})
        if not models:
            logger.warning("未找到模型配置")
            return
        
        self.model_selector.clear()
        for model_name in models.keys():
            self.model_selector.addItem(model_name)
    
    def get_selected_model(self) -> dict:
        """获取选中的模型配置"""
        model_name = self.model_selector.currentText()
        models = config.get("models", {})
        return models.get(model_name)
    
    def get_selected_datasets(self) -> dict:
        """获取选中的数据集及其权重"""
        logger.info("开始获取选中的数据集...")
        selected_datasets = {}
        
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
                prompts = DATASETS[dataset_name]
                # 使用权重作为并发数
                selected_datasets[dataset_name] = (prompts, weight)
                logger.info(f"添加数据集: {dataset_name}, prompts数量: {len(prompts)}, 并发数: {weight}")
        
        logger.info(f"最终选中的数据集: {selected_datasets}")
        return selected_datasets
    
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
