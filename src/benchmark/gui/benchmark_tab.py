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
from src.monitor.gpu_monitor import gpu_monitor  # 导入GPU监控器实例

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
                # 先检查是否存在result，并且不是error状态
                if not result or result.get("status") == "error":
                    error_msg = result.get("message", "未知错误") if result else "测试未返回结果"
                    logger.error(f"测试失败: {error_msg}")
                    self.test_error.emit(error_msg)
                    return
                
                # 检查测试结果中的任务状态
                if "results" in result:
                    # 获取所有测试任务的状态
                    all_tasks = result.get("results", [])
                    
                    if all_tasks:  # 确保有测试任务
                        # 计算成功任务数
                        successful_tasks = sum(1 for r in all_tasks if r.get("status") == "success")
                        
                        # 当成功任务数为0且总任务数大于0时，认为所有任务都失败
                        if successful_tasks == 0 and len(all_tasks) > 0:
                            # 所有任务都失败，触发错误信号
                            failed_count = len(all_tasks)
                            
                            # 尝试获取错误原因，首先检查是否有error_type字段
                            error_info = {}
                            error_messages = {}
                            
                            for task in all_tasks:
                                # 检查不同可能的错误字段名
                                error_type = None
                                error_msg = None
                                
                                # 检查error_type字段
                                if "error_type" in task:
                                    error_type = task["error_type"]
                                # 检查error字段
                                elif "error" in task:
                                    if isinstance(task["error"], str):
                                        error_type = task["error"].split(':')[0] if ':' in task["error"] else task["error"]
                                    else:
                                        error_type = str(type(task["error"]).__name__)
                                # 检查exception_type字段
                                elif "exception_type" in task:
                                    error_type = task["exception_type"]
                                
                                # 如果找到了错误类型，记录它
                                if error_type:
                                    error_info[error_type] = error_info.get(error_type, 0) + 1
                                
                                # 尝试获取错误消息
                                if "message" in task:
                                    error_msg = task["message"]
                                elif "error_message" in task:
                                    error_msg = task["error_message"]
                                elif "exception" in task:
                                    error_msg = str(task["exception"])
                                
                                if error_msg:
                                    error_messages[error_msg] = error_messages.get(error_msg, 0) + 1
                            
                            # 获取最常见的错误类型
                            most_common_error = "未知错误类型"
                            if error_info:
                                most_common_error = max(error_info.items(), key=lambda x: x[1])[0]
                            
                            # 获取最常见的错误消息
                            most_common_msg = ""
                            if error_messages:
                                most_common_msg = max(error_messages.items(), key=lambda x: x[1])[0]
                                # 截断过长的错误消息
                                if len(most_common_msg) > 100:
                                    most_common_msg = most_common_msg[:100] + "..."
                            
                            error_desc = f"{most_common_error}"
                            if most_common_msg:
                                error_desc += f": {most_common_msg}"
                            
                            # 检查是否是连接错误
                            if "ClientConnectorError" in most_common_error or "Connection" in most_common_error:
                                error_desc = f"API连接失败: {error_desc}"
                            
                            error_msg = f"所有测试任务均失败（共{failed_count}个任务）。常见错误: {error_desc}。请检查API连接或模型配置。"
                            logger.error(f"测试失败: {error_msg}")
                            
                            # 确保记录到日志中，以便调试
                            logger.debug(f"原始错误信息统计: {error_info}")
                            logger.debug(f"原始错误消息统计: {error_messages}")
                            
                            self.test_error.emit(error_msg)
                            return
                
                # 正常情况下触发测试完成信号
                logger.info("测试完成，发送test_finished信号")
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
        
        # 初始化GPU监控器
        self._init_gpu_monitor()
        
        # 初始化界面
        self.init_ui()
        
        logger.info("跑分标签页初始化完成")
    
    def _init_gpu_monitor(self):
        """初始化GPU监控器"""
        try:
            # 确保GPU监控器已初始化
            gpu_monitor.init_monitor()
            
            # 尝试获取数据，检查是否连接成功
            stats = gpu_monitor.get_stats()
            if stats:
                logger.info("GPU监控器连接成功")
            else:
                logger.warning("GPU监控器连接失败或未获取到数据")
        except Exception as e:
            logger.error(f"初始化GPU监控器失败: {str(e)}")
    
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