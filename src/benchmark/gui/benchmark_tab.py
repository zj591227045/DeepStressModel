"""
跑分标签页模块
"""
from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QGroupBox,
    QLabel,
    QComboBox,
    QPushButton,
    QFormLayout,
    QLineEdit,
    QSplitter,
    QMessageBox,
    QFileDialog
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from src.utils.logger import setup_logger
from src.utils.config import config

# 设置日志记录器
logger = setup_logger("benchmark_tab")

class BenchmarkThread(QThread):
    """跑分测试线程"""
    progress_updated = pyqtSignal(dict)  # 进度更新信号
    test_finished = pyqtSignal(dict)  # 测试完成信号
    test_error = pyqtSignal(str)  # 测试错误信号
    
    def __init__(self, benchmark_manager, config):
        super().__init__()
        self.benchmark_manager = benchmark_manager
        self.config = config
        self.running = False
    
    def run(self):
        """运行跑分测试"""
        self.running = True
        try:
            # 执行跑分测试
            result = self.benchmark_manager.run_benchmark(self.config)
            if self.running:  # 确保没有被中途停止
                self.test_finished.emit(result)
        except Exception as e:
            logger.error(f"跑分测试错误: {str(e)}")
            if self.running:
                self.test_error.emit(str(e))
        finally:
            self.running = False
    
    def stop(self):
        """停止测试"""
        self.running = False
        self.benchmark_manager.stop_benchmark()

class BenchmarkTab(QWidget):
    """跑分标签页"""

    def __init__(self):
        super().__init__()
        
        # 初始化成员变量
        self.benchmark_manager = None
        self.benchmark_thread = None
        self.device_id = self._generate_device_id()
        
        # 初始化界面
        self.init_ui()
        
        logger.info("跑分标签页初始化完成")
    
    def init_ui(self):
        """初始化界面"""
        # 创建主布局
        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(10)
        
        # 创建设备信息组
        device_group = QGroupBox("设备信息")
        device_layout = QFormLayout()
        
        self.device_id_edit = QLineEdit(self.device_id)
        self.device_id_edit.setReadOnly(True)
        device_layout.addRow("设备ID:", self.device_id_edit)
        
        self.nickname_edit = QLineEdit(config.get("benchmark.nickname", ""))
        device_layout.addRow("设备名称:", self.nickname_edit)
        
        device_group.setLayout(device_layout)
        main_layout.addWidget(device_group)
        
        # 创建数据集组
        dataset_group = QGroupBox("数据集")
        dataset_layout = QVBoxLayout()
        
        dataset_info_layout = QFormLayout()
        self.dataset_version_label = QLabel("未加载")
        dataset_info_layout.addRow("数据集版本:", self.dataset_version_label)
        
        self.dataset_date_label = QLabel("未知")
        dataset_info_layout.addRow("发布日期:", self.dataset_date_label)
        
        dataset_layout.addLayout(dataset_info_layout)
        
        dataset_buttons_layout = QHBoxLayout()
        self.update_dataset_button = QPushButton("更新数据集")
        self.update_dataset_button.clicked.connect(self.on_update_dataset)
        dataset_buttons_layout.addWidget(self.update_dataset_button)
        
        self.upload_dataset_button = QPushButton("上传本地数据集")
        self.upload_dataset_button.clicked.connect(self.on_upload_dataset)
        dataset_buttons_layout.addWidget(self.upload_dataset_button)
        
        dataset_layout.addLayout(dataset_buttons_layout)
        dataset_group.setLayout(dataset_layout)
        main_layout.addWidget(dataset_group)
        
        # 创建测试配置组
        test_config_group = QGroupBox("测试配置")
        test_config_layout = QFormLayout()
        
        self.model_combo = QComboBox()
        self.model_combo.addItems(["llama-3-8b", "llama-3-70b", "自定义"])
        test_config_layout.addRow("模型:", self.model_combo)
        
        self.precision_combo = QComboBox()
        self.precision_combo.addItems(["fp16", "fp32", "int8", "int4"])
        test_config_layout.addRow("精度:", self.precision_combo)
        
        test_config_group.setLayout(test_config_layout)
        main_layout.addWidget(test_config_group)
        
        # 创建测试控制组
        test_control_group = QGroupBox("测试控制")
        test_control_layout = QVBoxLayout()
        
        self.start_test_button = QPushButton("开始测试")
        self.start_test_button.clicked.connect(self.on_start_test)
        test_control_layout.addWidget(self.start_test_button)
        
        self.stop_test_button = QPushButton("停止测试")
        self.stop_test_button.clicked.connect(self.on_stop_test)
        self.stop_test_button.setEnabled(False)
        test_control_layout.addWidget(self.stop_test_button)
        
        test_control_group.setLayout(test_control_layout)
        main_layout.addWidget(test_control_group)
        
        # 创建测试进度组
        progress_group = QGroupBox("测试进度")
        progress_layout = QVBoxLayout()
        
        self.progress_label = QLabel("就绪")
        progress_layout.addWidget(self.progress_label)
        
        progress_group.setLayout(progress_layout)
        main_layout.addWidget(progress_group)
        
        # 创建结果组
        result_group = QGroupBox("测试结果")
        result_layout = QFormLayout()
        
        self.throughput_label = QLabel("0")
        result_layout.addRow("吞吐量 (tokens/s):", self.throughput_label)
        
        self.latency_label = QLabel("0")
        result_layout.addRow("延迟 (ms):", self.latency_label)
        
        self.total_time_label = QLabel("0")
        result_layout.addRow("总时间 (s):", self.total_time_label)
        
        result_group.setLayout(result_layout)
        main_layout.addWidget(result_group)
        
        # 设置主布局
        self.setLayout(main_layout)
    
    def set_benchmark_manager(self, benchmark_manager):
        """设置跑分管理器"""
        self.benchmark_manager = benchmark_manager
        self.update_dataset_info()
    
    def update_dataset_info(self):
        """更新数据集信息"""
        if self.benchmark_manager:
            dataset_info = self.benchmark_manager.get_dataset_info()
            self.dataset_version_label.setText(dataset_info.get("version", "未知"))
            self.dataset_date_label.setText(dataset_info.get("created_at", "未知"))
    
    def on_update_dataset(self):
        """更新数据集按钮点击事件"""
        if not self.benchmark_manager:
            QMessageBox.warning(self, "警告", "跑分管理器未初始化")
            return
        
        try:
            if self.benchmark_manager.update_dataset():
                self.update_dataset_info()
                QMessageBox.information(self, "成功", "数据集更新成功")
            else:
                QMessageBox.warning(self, "警告", "数据集更新失败")
        except Exception as e:
            logger.error(f"更新数据集失败: {str(e)}")
            QMessageBox.critical(self, "错误", f"更新数据集失败: {str(e)}")
    
    def on_upload_dataset(self):
        """上传本地数据集按钮点击事件"""
        if not self.benchmark_manager:
            QMessageBox.warning(self, "警告", "跑分管理器未初始化")
            return
        
        try:
            file_path, _ = QFileDialog.getOpenFileName(self, "选择数据集文件", "", "JSON文件 (*.json)")
            if file_path:
                if self.benchmark_manager.upload_dataset(file_path):
                    self.update_dataset_info()
                    QMessageBox.information(self, "成功", "数据集上传成功")
                else:
                    QMessageBox.warning(self, "警告", "数据集上传失败")
        except Exception as e:
            logger.error(f"上传数据集失败: {str(e)}")
            QMessageBox.critical(self, "错误", f"上传数据集失败: {str(e)}")
    
    def on_start_test(self):
        """开始测试按钮点击事件"""
        if not self.benchmark_manager:
            QMessageBox.warning(self, "警告", "跑分管理器未初始化")
            return
        
        if not self.benchmark_manager.is_dataset_loaded():
            QMessageBox.warning(self, "警告", "请先加载数据集")
            return
        
        # 收集测试配置
        test_config = {
            "device_id": self.device_id,
            "nickname": self.nickname_edit.text(),
            "model": self.model_combo.currentText(),
            "precision": self.precision_combo.currentText(),
            "framework_config": {}
        }
        
        # 创建并启动测试线程
        self.benchmark_thread = BenchmarkThread(self.benchmark_manager, test_config)
        self.benchmark_thread.progress_updated.connect(self.on_progress_updated)
        self.benchmark_thread.test_finished.connect(self.on_test_finished)
        self.benchmark_thread.test_error.connect(self.on_test_error)
        
        self.benchmark_thread.start()
        
        # 更新UI状态
        self.start_test_button.setEnabled(False)
        self.stop_test_button.setEnabled(True)
        self.progress_label.setText("测试进行中...")
    
    def on_stop_test(self):
        """停止测试按钮点击事件"""
        if self.benchmark_thread and self.benchmark_thread.isRunning():
            self.benchmark_thread.stop()
            self.benchmark_thread.wait()
            
            # 更新UI状态
            self.start_test_button.setEnabled(True)
            self.stop_test_button.setEnabled(False)
            self.progress_label.setText("测试已停止")
    
    def on_progress_updated(self, progress):
        """测试进度更新事件"""
        # 更新进度信息
        self.progress_label.setText(f"进度: {progress.get('progress', 0):.2f}%")
        
        # 更新实时指标
        self.throughput_label.setText(f"{progress.get('throughput', 0):.2f}")
        self.latency_label.setText(f"{progress.get('latency', 0):.2f}")
        self.total_time_label.setText(f"{progress.get('total_time', 0):.2f}")
    
    def on_test_finished(self, result):
        """测试完成事件"""
        # 更新UI状态
        self.start_test_button.setEnabled(True)
        self.stop_test_button.setEnabled(False)
        self.progress_label.setText("测试完成")
        
        # 更新结果
        metrics = result.get("metrics", {})
        self.throughput_label.setText(f"{metrics.get('throughput', 0):.2f}")
        self.latency_label.setText(f"{metrics.get('latency', 0):.2f}")
        self.total_time_label.setText(f"{result.get('total_duration', 0):.2f}")
        
        # 显示结果对话框
        QMessageBox.information(self, "测试完成", "跑分测试已完成，结果已保存")
    
    def on_test_error(self, error_msg):
        """测试错误事件"""
        # 更新UI状态
        self.start_test_button.setEnabled(True)
        self.stop_test_button.setEnabled(False)
        self.progress_label.setText("测试失败")
        
        # 显示错误对话框
        QMessageBox.critical(self, "测试错误", f"跑分测试失败: {error_msg}")
    
    def _generate_device_id(self):
        """生成设备ID"""
        # 从配置中获取设备ID，如果不存在则生成一个新的
        device_id = config.get("benchmark.device_id", "")
        if not device_id:
            import uuid
            device_id = str(uuid.uuid4())
            config.set("benchmark.device_id", device_id)
        return device_id 