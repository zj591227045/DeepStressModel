"""
跑分标签页模块
"""
import os
import uuid
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
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QFileDialog
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QFont
from src.utils.config import config
from src.utils.logger import setup_logger
from src.gui.i18n.language_manager import LanguageManager
from src.gui.widgets.gpu_monitor import GPUMonitorWidget
from src.gui.widgets.test_progress import TestProgressWidget  # 导入测试进度组件
from src.gui.benchmark_history_tab import BenchmarkHistoryTab
from src.engine.benchmark_manager import BenchmarkManager
from src.data.db_manager import db_manager  # 导入数据库管理器

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
        
        # 设置进度回调函数
        self.benchmark_manager.set_progress_callback(self._on_progress)
    
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
    
    def _on_progress(self, progress):
        """进度回调处理"""
        self.progress_updated.emit(progress)


class BenchmarkTab(QWidget):
    """跑分标签页"""

    def __init__(self):
        super().__init__()
        
        # 获取语言管理器实例
        self.language_manager = LanguageManager()
        
        # 初始化跑分管理器
        self.benchmark_manager = BenchmarkManager()
        
        # 初始化成员变量
        self.benchmark_thread = None
        self.device_id = self._generate_device_id()
        
        # 初始化界面
        self.init_ui()
        
        # 更新界面文本
        self.update_ui_text()
        
        # 连接语言变更信号
        self.language_manager.language_changed.connect(self.update_ui_text)
    
    def _generate_device_id(self):
        """生成设备唯一ID"""
        # 从配置中读取设备ID，如果不存在则生成新的
        device_id = config.get("benchmark.device_id", None)
        if not device_id:
            # 生成基于硬件信息的唯一ID
            device_id = str(uuid.uuid4())
            # 保存到配置
            config.set("benchmark.device_id", device_id)
        return device_id
    
    def init_ui(self):
        """初始化UI"""
        main_layout = QVBoxLayout(self)
        
        # 创建标签页容器
        self.tab_widget = QTabWidget()
        
        # 创建测试标签页
        self.test_tab = self._create_test_tab()
        self.tab_widget.addTab(self.test_tab, "跑分测试")
        
        # 创建历史记录标签页
        self.history_tab = BenchmarkHistoryTab()
        self.tab_widget.addTab(self.history_tab, "历史记录")
        
        # 添加标签页容器到主布局
        main_layout.addWidget(self.tab_widget)
    
    def _create_test_tab(self):
        """创建测试标签页"""
        test_tab = QWidget()
        test_layout = QVBoxLayout(test_tab)
        
        # 创建水平分割器
        splitter = QSplitter(Qt.Orientation.Horizontal)
        
        # 左侧：控制面板
        control_panel = QWidget()
        control_layout = QVBoxLayout(control_panel)
        
        # 用户配置区域
        user_config = self._create_user_config()
        control_layout.addWidget(user_config)
        
        # 数据集管理区域
        dataset_manager = self._create_dataset_manager()
        control_layout.addWidget(dataset_manager)
        
        # 模型配置区域（复用测试标签页的模型选择）
        model_config = self._create_model_config()
        control_layout.addWidget(model_config)
        
        # 测试控制按钮
        control_buttons = self._create_control_buttons()
        control_layout.addWidget(control_buttons)
        
        # 测试进度窗口
        self.progress_widget = TestProgressWidget()
        control_layout.addWidget(self.progress_widget)
        
        # 添加弹性空间
        control_layout.addStretch()
        
        # 右侧：监控面板
        monitor_panel = QWidget()
        monitor_layout = QVBoxLayout(monitor_panel)
        
        # GPU监控（复用现有的GPU监控组件）
        self.gpu_monitor = GPUMonitorWidget()
        monitor_layout.addWidget(self.gpu_monitor)
        
        # 性能指标图表
        performance_charts = self._create_performance_charts()
        monitor_layout.addWidget(performance_charts)
        
        # 添加左右面板到分割器
        splitter.addWidget(control_panel)
        splitter.addWidget(monitor_panel)
        
        # 设置分割比例
        splitter.setSizes([300, 700])  # 左侧300像素，右侧700像素
        
        # 添加分割器到测试标签页布局
        test_layout.addWidget(splitter)
        
        # 启动GPU监控
        self.gpu_monitor.start_monitoring()
        
        return test_tab
    
    def _create_user_config(self):
        """创建用户配置组件"""
        group_box = QGroupBox()
        layout = QFormLayout(group_box)
        
        # 用户昵称输入
        self.nickname_input = QLineEdit()
        self.nickname_input.setText(config.get("benchmark.nickname", ""))
        self.nickname_input.textChanged.connect(self._on_nickname_changed)
        
        # 运行模式选择
        self.mode_select = QComboBox()
        self.mode_select.addItems(["在线模式", "离线模式"])
        self.mode_select.setCurrentIndex(config.get("benchmark.mode", 0))
        self.mode_select.currentIndexChanged.connect(self._on_mode_changed)
        
        # 添加到布局
        layout.addRow("昵称:", self.nickname_input)
        layout.addRow("运行模式:", self.mode_select)
        
        return group_box
    
    def _create_dataset_manager(self):
        """创建数据集管理组件"""
        group_box = QGroupBox()
        layout = QVBoxLayout(group_box)
        
        # 当前数据集信息显示
        self.dataset_info = QLabel("未加载数据集")
        layout.addWidget(self.dataset_info)
        
        # 按钮布局
        button_layout = QHBoxLayout()
        
        # 在线模式：更新按钮
        self.update_button = QPushButton("更新数据集")
        self.update_button.clicked.connect(self._update_dataset)
        button_layout.addWidget(self.update_button)
        
        # 离线模式：上传按钮
        self.upload_button = QPushButton("上传数据集")
        self.upload_button.clicked.connect(self._upload_dataset)
        button_layout.addWidget(self.upload_button)
        
        layout.addLayout(button_layout)
        
        # 根据当前模式更新UI
        self._update_mode_ui()
        
        return group_box
    
    def _create_model_config(self):
        """创建模型配置组件（复用测试标签页的模型选择）"""
        group_box = QGroupBox("模型配置")
        layout = QVBoxLayout(group_box)
        
        # 模型选择区域
        model_layout = QHBoxLayout()
        
        # 添加模型选择下拉框（复用测试标签页的模型选择）
        self.model_combo = QComboBox()
        model_layout.addWidget(self.model_combo)
        
        # 添加刷新按钮
        self.refresh_btn = QPushButton("刷新")
        self.refresh_btn.clicked.connect(self.load_models)
        model_layout.addWidget(self.refresh_btn)
        
        layout.addLayout(model_layout)
        
        # 参数量输入区域
        param_layout = QFormLayout()
        
        # 参数量输入框
        self.param_input = QLineEdit()
        self.param_input.setPlaceholderText("例如：7")
        param_layout.addRow("参数量(B):", self.param_input)
        
        layout.addLayout(param_layout)
        
        # 精度选择区域
        precision_layout = QFormLayout()
        
        # 模型精度选择
        self.precision_combo = QComboBox()
        self.precision_combo.addItems(["FP16", "FP32", "BF16", "INT8", "INT4", "AWQ"])
        precision_layout.addRow("精度:", self.precision_combo)
        
        # 框架配置
        self.framework_input = QLineEdit()
        precision_layout.addRow("框架配置:", self.framework_input)
        
        layout.addLayout(precision_layout)
        
        # 加载模型列表
        self.load_models()
        
        return group_box
    
    def _create_control_buttons(self):
        """创建控制按钮组件"""
        group_box = QGroupBox()
        layout = QHBoxLayout(group_box)
        
        # 开始测试按钮
        self.start_button = QPushButton("开始跑分")
        self.start_button.clicked.connect(self.start_benchmark)
        layout.addWidget(self.start_button)
        
        # 停止测试按钮
        self.stop_button = QPushButton("停止跑分")
        self.stop_button.clicked.connect(self.stop_benchmark)
        self.stop_button.setEnabled(False)
        layout.addWidget(self.stop_button)
        
        return group_box
    
    def _create_performance_charts(self):
        """创建性能指标图表组件"""
        group_box = QGroupBox()
        layout = QVBoxLayout(group_box)
        
        # 创建标签页容器
        tab_widget = QTabWidget()
        
        # TPS图表标签页
        tps_tab = QWidget()
        tps_layout = QVBoxLayout(tps_tab)
        self.tps_chart = QLabel("TPS图表将在此显示")
        tps_layout.addWidget(self.tps_chart)
        tab_widget.addTab(tps_tab, "Token生成速度")
        
        # 延迟图表标签页
        latency_tab = QWidget()
        latency_layout = QVBoxLayout(latency_tab)
        self.latency_chart = QLabel("延迟图表将在此显示")
        latency_layout.addWidget(self.latency_chart)
        tab_widget.addTab(latency_tab, "请求延迟")
        
        # 内存使用图表标签页
        memory_tab = QWidget()
        memory_layout = QVBoxLayout(memory_tab)
        self.memory_chart = QLabel("内存使用图表将在此显示")
        memory_layout.addWidget(self.memory_chart)
        tab_widget.addTab(memory_tab, "内存使用")
        
        layout.addWidget(tab_widget)
        
        return group_box
    
    def load_models(self):
        """加载模型列表（复用测试标签页的模型加载逻辑）"""
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
        """获取选中的模型配置（复用测试标签页的获取模型逻辑）"""
        model_name = self.model_combo.currentText()
        if not model_name:
            return None
            
        models = db_manager.get_model_configs()
        return next((m for m in models if m["name"] == model_name), None)
    
    def _on_nickname_changed(self, text):
        """昵称变更处理"""
        config.set("benchmark.nickname", text)
    
    def _on_mode_changed(self, index):
        """运行模式变更处理"""
        config.set("benchmark.mode", index)
        self._update_mode_ui()
    
    def _update_mode_ui(self):
        """根据运行模式更新UI"""
        is_online = self.mode_select.currentIndex() == 0
        
        # 更新按钮可见性
        self.update_button.setVisible(is_online)
        self.upload_button.setVisible(not is_online)
    
    def _update_dataset(self):
        """更新数据集（在线模式）"""
        try:
            # 调用数据集更新逻辑
            self.benchmark_manager.update_dataset()
            
            # 更新数据集信息显示
            dataset_info = self.benchmark_manager.get_dataset_info()
            self.dataset_info.setText(f"数据集版本: {dataset_info['version']}")
            
            QMessageBox.information(self, "更新成功", "数据集更新成功")
        except Exception as e:
            logger.error(f"更新数据集错误: {str(e)}")
            QMessageBox.warning(self, "更新失败", f"数据集更新失败: {str(e)}")
    
    def _upload_dataset(self):
        """上传数据集（离线模式）"""
        try:
            # 打开文件选择对话框
            file_path, _ = QFileDialog.getOpenFileName(
                self,
                "选择数据集文件",
                "",
                "数据集文件 (*.bin *.dat *.zip);;所有文件 (*)"
            )
            
            if not file_path:
                # 用户取消了选择
                return
            
            # 调用数据集上传逻辑
            self.benchmark_manager.upload_dataset(file_path)
            
            # 更新数据集信息显示
            dataset_info = self.benchmark_manager.get_dataset_info()
            self.dataset_info.setText(f"数据集版本: {dataset_info['version']}")
            
            QMessageBox.information(self, "上传成功", "数据集上传成功")
        except Exception as e:
            logger.error(f"上传数据集错误: {str(e)}")
            QMessageBox.warning(self, "上传失败", f"数据集上传失败: {str(e)}")
    
    def start_benchmark(self):
        """开始跑分测试"""
        # 检查是否已加载数据集
        if not self.benchmark_manager.is_dataset_loaded():
            QMessageBox.warning(self, "无法开始", "请先加载或更新数据集")
            return
        
        # 获取选中的模型配置
        selected_model = self.get_selected_model()
        if not selected_model:
            QMessageBox.warning(self, "无法开始", "请先选择一个模型")
            return
        
        # 获取参数量
        model_params = self.param_input.text().strip()
        if not model_params:
            QMessageBox.warning(self, "无法开始", "请输入模型参数量")
            return
        
        try:
            # 尝试将参数量转换为浮点数
            model_params = float(model_params)
        except ValueError:
            QMessageBox.warning(self, "无法开始", "模型参数量必须是数字")
            return
        
        # 获取配置信息
        config = {
            "device_id": self.device_id,
            "nickname": self.nickname_input.text(),
            "mode": "online" if self.mode_select.currentIndex() == 0 else "offline",
            "model": selected_model["name"],
            "model_config": selected_model,  # 添加完整的模型配置
            "model_params": model_params,  # 添加模型参数量
            "precision": self.precision_combo.currentText(),
            "framework_config": self.framework_input.text()
        }
        
        # 重置进度显示
        self.progress_widget.reset()
        
        # 创建并启动测试线程
        self.benchmark_thread = BenchmarkThread(self.benchmark_manager, config)
        self.benchmark_thread.progress_updated.connect(self._on_progress_updated)
        self.benchmark_thread.test_finished.connect(self._on_test_finished)
        self.benchmark_thread.test_error.connect(self._on_test_error)
        self.benchmark_thread.start()
        
        # 更新UI状态
        self.start_button.setEnabled(False)
        self.stop_button.setEnabled(True)
    
    def stop_benchmark(self):
        """停止跑分测试"""
        if self.benchmark_thread and self.benchmark_thread.isRunning():
            self.benchmark_thread.stop()
            self.benchmark_thread.wait(5000)  # 等待最多5秒
        
        # 更新UI状态
        self.start_button.setEnabled(True)
        self.stop_button.setEnabled(False)
    
    def _on_progress_updated(self, progress):
        """进度更新处理"""
        # 更新进度显示
        self.progress_widget.update_progress(progress)
    
    def _on_test_finished(self, result):
        """测试完成处理"""
        # 处理测试结果
        QMessageBox.information(self, "测试完成", "跑分测试已完成")
        
        # 更新UI状态
        self.start_button.setEnabled(True)
        self.stop_button.setEnabled(False)
        
        # 刷新历史记录
        self.history_tab.load_history()
        
        # 切换到历史记录标签页
        self.tab_widget.setCurrentIndex(1)
    
    def _on_test_error(self, error_msg):
        """测试错误处理"""
        QMessageBox.critical(self, "测试错误", f"跑分测试出错: {error_msg}")
        
        # 更新UI状态
        self.start_button.setEnabled(True)
        self.stop_button.setEnabled(False)
    
    def update_ui_text(self):
        """更新UI文本"""
        # 更新标签页标题
        self.tab_widget.setTabText(0, self.tr("benchmark_test"))
        self.tab_widget.setTabText(1, self.tr("history"))
        
        # 更新按钮文本
        self.refresh_btn.setText(self.tr("refresh_model"))
        self.start_button.setText(self.tr("start_benchmark"))
        self.stop_button.setText(self.tr("stop_benchmark"))
        self.update_button.setText(self.tr("update_dataset"))
        self.upload_button.setText(self.tr("upload_dataset"))
        
        # 更新历史记录标签页文本
        self.history_tab.update_ui_text()
    
    def tr(self, key):
        """翻译文本"""
        return self.language_manager.get_text(key)
    
    def closeEvent(self, event):
        """窗口关闭事件"""
        # 停止测试线程
        self.stop_benchmark()
        
        # 停止GPU监控
        self.gpu_monitor.stop_monitoring()
        
        event.accept() 