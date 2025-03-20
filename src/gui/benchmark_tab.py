"""
跑分标签页模块
"""
import os
import uuid
import asyncio
import time
import platform
import subprocess
import paramiko
import json
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
    QFileDialog,
    QSizePolicy,
    QSpinBox,
    QRadioButton,
    QTextEdit,
    QDialog,
    QDialogButtonBox,
    QCheckBox,
    QProgressBar,
    QProgressDialog,
    QApplication
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QSize, QEventLoop
from PyQt6.QtGui import QFont, QIcon
from src.utils.config import config
from src.utils.logger import setup_logger
from src.gui.i18n.language_manager import LanguageManager
from src.gui.widgets.gpu_monitor import GPUMonitorWidget
from src.gui.widgets.test_progress import TestProgressWidget  # 导入测试进度组件
from src.gui.benchmark_history_tab import BenchmarkHistoryTab
from src.benchmark.integration import benchmark_integration  # 导入跑分模块集成
from src.data.db_manager import db_manager  # 导入数据库管理器
from datetime import datetime

# 设置日志记录器
logger = setup_logger("benchmark_tab")


class BenchmarkThread(QThread):
    """跑分测试线程"""
    progress_updated = pyqtSignal(dict)  # 进度更新信号
    test_finished = pyqtSignal(dict)  # 测试完成信号
    test_error = pyqtSignal(str)  # 测试错误信号
    
    def __init__(self, config):
        super().__init__()
        self.config = config
        self.running = False
        
        # 添加测试参数成员变量
        self.model_name = ""
        self.api_url = ""
        self.model_params = {}
        self.concurrency = 1
        self.test_mode = 1  # 默认为联网模式
        
        # 连接信号
        logger.debug("正在连接benchmark_integration信号到BenchmarkThread")
        
        # 定义进度更新处理函数，添加调试日志
        def on_progress_updated(progress_data):
            logger.debug(f"BenchmarkThread: 收到进度更新，转发信号. 数据键: {list(progress_data.keys() if isinstance(progress_data, dict) else ['非字典数据'])}")
            self.progress_updated.emit(progress_data)
            
        # 定义测试完成处理函数，添加调试日志
        def on_test_finished(result_data):
            logger.debug(f"BenchmarkThread: 收到测试完成信号，转发信号. 数据键: {list(result_data.keys() if isinstance(result_data, dict) else ['非字典数据'])}")
            logger.debug(f"BenchmarkThread: 框架信息存在: {'framework_info' in result_data}, 值: {result_data.get('framework_info')}")
            logger.debug(f"BenchmarkThread: result对象id: {id(result_data)}")
            self.test_finished.emit(result_data)
            
        # 定义测试错误处理函数，添加调试日志
        def on_test_error(error_msg):
            logger.debug(f"BenchmarkThread: 收到测试错误信号，转发信号: {error_msg}")
            self.test_error.emit(error_msg)
        
        # 连接信号
        benchmark_integration.progress_updated.connect(on_progress_updated)
        benchmark_integration.test_finished.connect(on_test_finished)
        benchmark_integration.test_error.connect(on_test_error)
    
    def set_test_parameters(self, model, api_url, model_params, concurrency, test_mode, api_timeout):
        """设置测试参数"""
        self.model_name = model
        self.api_url = api_url
        self.model_params = model_params
        self.concurrency = concurrency
        self.test_mode = test_mode
        self.api_timeout = api_timeout
        logger.debug(f"已设置测试参数: 模型={model}, API={api_url}, 并发数={concurrency}, 模式={test_mode}, API超时={api_timeout}")
    
    def run(self):
        """运行跑分测试"""
        self.running = True
        logger.debug("BenchmarkThread: 开始执行跑分测试")
        try:
            # 创建测试配置
            test_config = {
                "model": self.model_name,
                "api_url": self.api_url,
                "model_params": self.model_params,
                "concurrency": self.concurrency,
                "test_mode": self.test_mode,
                "api_timeout": self.api_timeout
            }
            
            # 执行跑分测试
            benchmark_integration.run_benchmark(test_config)
            logger.debug("BenchmarkThread: 跑分测试执行完成")
        except Exception as e:
            logger.error(f"BenchmarkThread: 跑分测试错误: {str(e)}")
            if self.running:
                self.test_error.emit(str(e))
        finally:
            self.running = False
            logger.debug("BenchmarkThread: 线程执行完毕")
    
    def stop(self):
        """停止测试"""
        logger.debug("BenchmarkThread: 正在停止测试")
        self.running = False
        benchmark_integration.stop_benchmark()


class ResultWorker(QThread):
    """结果处理工作线程，用于加密和上传测试结果"""
    
    # 定义信号
    progress_updated = pyqtSignal(int)  # 进度更新信号
    finished_signal = pyqtSignal(dict)  # 完成信号
    error_signal = pyqtSignal(str)      # 错误信号
    
    def __init__(self, test_mode, integration, should_upload=False):
        """
        初始化结果处理工作线程
        
        Args:
            test_mode: 测试模式，0=联网模式，1=离线模式
            integration: BenchmarkIntegration实例
            should_upload: 是否应该上传结果（联网模式下使用）
        """
        super().__init__()
        self.test_mode = test_mode
        self.integration = integration
        self.should_upload = should_upload
        
    def run(self):
        """运行处理逻辑"""
        try:
            # 检查benchmark_manager的测试结果
            logger.info("ResultWorker: 开始结果处理线程")
            if hasattr(self.integration, 'benchmark_manager') and hasattr(self.integration.benchmark_manager, 'latest_test_result'):
                latest_result = self.integration.benchmark_manager.latest_test_result
                logger.info(f"ResultWorker: benchmark_manager.latest_test_result中framework_info存在: {'framework_info' in latest_result}")
                if 'framework_info' in latest_result:
                    logger.info(f"ResultWorker: latest_test_result中的framework_info: {latest_result['framework_info']}")
            else:
                logger.warning("ResultWorker: benchmark_manager.latest_test_result不存在")
            
            # 模拟初始进度更新
            for i in range(0, 90, 5):
                self.progress_updated.emit(i)
                time.sleep(0.05)  # 短暂延迟，使进度显示更平滑
            
            # 检查结果中是否已有加密文件路径
            encrypt_result = {}
            latest_result = self.integration.benchmark_manager.latest_test_result
            
            if "encrypted_path" in latest_result and os.path.exists(latest_result["encrypted_path"]):
                logger.info(f"ResultWorker: 使用已存在的加密文件: {latest_result['encrypted_path']}")
                encrypt_result = {
                    "status": "success",
                    "message": "使用已存在的加密文件",
                    "encrypted_path": latest_result["encrypted_path"],
                    "original_path": latest_result.get("result_path", "")
                }
            else:
                # 需要加密并保存记录
                logger.info("ResultWorker: 开始加密测试记录")
                encrypt_result = self.integration.encrypt_result()
                
                # 将加密文件路径添加到测试结果中，以便后续使用
                if encrypt_result.get("status") == "success" and "encrypted_path" in encrypt_result:
                    self.integration.benchmark_manager.latest_test_result["encrypted_path"] = encrypt_result["encrypted_path"]
            
            # 如果是联网模式且用户选择上传
            if self.test_mode == 0 and self.should_upload:
                logger.info("ResultWorker: 联网模式，开始上传加密测试记录")
                upload_result = self.integration.upload_result()
                
                # 将上传结果合并到加密结果中
                if upload_result:
                    encrypt_result.update({
                        "upload_status": upload_result.get("status", "error"),
                        "upload_message": upload_result.get("message", "未知错误"),
                        "upload_id": upload_result.get("upload_id", ""),
                        "upload_result": upload_result
                    })
            
            # 完成进度更新
            self.progress_updated.emit(100)
            
            # 检查加密结果
            logger.info(f"ResultWorker: 加密结果状态: {encrypt_result.get('status', '未知')}")
            if encrypt_result.get('status') == 'error':
                logger.error(f"ResultWorker: 加密错误: {encrypt_result.get('message', '未知错误')}")
            
            # 发送完成信号
            self.finished_signal.emit(encrypt_result)
            
        except Exception as e:
            logger.error(f"处理测试结果时出错: {str(e)}")
            self.error_signal.emit(str(e))


class BenchmarkTab(QWidget):
    """跑分标签页"""

    def __init__(self, parent=None):
        """
        初始化跑分标签页
        
        Args:
            parent: 父窗口
        """
        super().__init__(parent)
        
        # 初始化成员变量
        self.is_testing = False
        self._result_processed = False  # 添加结果处理标志位
        
        # 获取语言管理器实例
        self.language_manager = LanguageManager()
        
        # 初始化成员变量
        self.benchmark_thread = None
        self.device_id = self._generate_device_id()
        self.config = config  # 保存配置对象引用
        self.test_thread = None
        self.test_task_id = None
        self.dataset_updated = False  # 添加 dataset_updated 属性
        
        logger.info("开始从数据库加载跑分设置")
        
        # 从数据库加载设置
        self._load_settings_from_db()
        
        logger.info(f"从数据库加载设置完成，当前测试模式: {self.test_mode} ({'联网模式' if self.test_mode == 0 else '离线模式'})")
        
        # 初始化界面
        self.init_ui()
        
        # 更新界面文本
        self.update_ui_text()
    
    def _generate_device_id(self):
        """生成设备ID"""
        # 从数据库获取设备ID
        settings = db_manager.get_benchmark_settings()
        device_id = settings.get("device_id", "")
        
        if not device_id:
            # 生成新的设备ID
            device_id = str(uuid.uuid4())
            # 保存到数据库，默认使用联网模式(0)
            db_manager.save_benchmark_settings({
                "device_id": device_id,
                "device_name": "未命名设备",
                "is_enabled": True,
                "mode": 0  # 默认为联网模式
            })
        
        return device_id
    
    def _load_settings_from_db(self):
        """从数据库加载设置"""
        settings = db_manager.get_benchmark_settings()
        logger.info(f"从数据库获取的设置: {settings}")
        
        if settings:
            # 设置设备ID
            self.device_id = settings.get("device_id", self.device_id)
            
            # 获取测试模式，默认为联网模式(0)
            self.test_mode = settings.get("mode", 0)
            logger.info(f"从数据库加载的测试模式: {self.test_mode}")
            
            # 更新配置
            config.set("benchmark.mode", self.test_mode)
            
            # 如果有API密钥，设置到benchmark_integration
            api_key = settings.get("api_key", "")
            device_name = settings.get("device_name", "未命名设备")
            if api_key:
                benchmark_integration.set_api_key(api_key, self.device_id, device_name)
        else:
            # 如果没有保存的设置，默认为联网模式
            logger.info("数据库中没有设置，使用默认联网模式(0)")
            self.test_mode = 0
            config.set("benchmark.mode", self.test_mode)
    
    def _register_device_if_needed(self):
        """如果需要，注册设备"""
        # 获取API密钥
        api_key = config.get("benchmark.api_key", "")
        if not api_key and self.mode_select.currentIndex() == 0:  # 联网模式
            # 获取昵称
            nickname = self.nickname_input.text()
            if not nickname:
                nickname = "未命名设备"
            
            # 注册设备
            benchmark_integration.register_device(nickname, self._on_register_result)
    
    def _on_register_result(self, success, message):
        """设备注册结果处理"""
        if success:
            QMessageBox.information(self, "注册成功", message)
        else:
            QMessageBox.warning(self, "注册失败", message)
    
    def init_ui(self):
        """初始化界面"""
        # 创建主布局
        main_layout = QVBoxLayout()
        
        # 创建顶部工具栏
        toolbar_layout = QHBoxLayout()
        
        # 添加跑分基础设置按钮
        self.settings_button = QPushButton("跑分基础设置")
        self.settings_button.clicked.connect(self._show_settings_dialog)
        toolbar_layout.addWidget(self.settings_button)
        
        # 添加访问服务器按钮
        self.server_link_button = QPushButton("visit_server")
        self.server_link_button.clicked.connect(self._open_server_link)
        toolbar_layout.addWidget(self.server_link_button)
        
        # 添加说明标签
        toolbar_layout.addStretch()
        self.status_label = QLabel()
        self._update_status_label()  # 更新状态文本
        toolbar_layout.addWidget(self.status_label)
        
        main_layout.addLayout(toolbar_layout)
        
        # 创建主内容区域
        content_splitter = QSplitter(Qt.Orientation.Horizontal)
        
        # 创建左侧布局（模型选择、数据集选择、并发设置、开始测试按钮）
        left_layout = QVBoxLayout()
        
        # 模型选择
        model_select_group = QGroupBox("模型选择")
        model_select_layout = QHBoxLayout()
        
        # 模型下拉框
        self.model_combo = QComboBox()
        self.model_combo.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        model_select_layout.addWidget(self.model_combo)
        
        # 刷新按钮
        refresh_button = QPushButton("刷新")
        refresh_button.setIcon(QIcon.fromTheme("view-refresh", QIcon(":/icons/refresh.png")))
        refresh_button.setIconSize(QSize(16, 16))
        refresh_button.setCursor(Qt.CursorShape.PointingHandCursor)
        refresh_button.setStyleSheet("""
            QPushButton {
                background-color: #2196F3;
                color: white;
                border: none;
                padding: 4px 8px;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #0b7dda;
            }
            QPushButton:pressed {
                background-color: #0a69b7;
            }
        """)
        refresh_button.clicked.connect(self.load_models)
        model_select_layout.addWidget(refresh_button)
        
        model_select_group.setLayout(model_select_layout)
        left_layout.addWidget(model_select_group)
        
        # 数据集选择
        dataset_group = QGroupBox("数据集选择")
        dataset_layout = QVBoxLayout()
        
        # 添加数据集信息显示区域
        self.dataset_info_text = QTextEdit()
        self.dataset_info_text.setReadOnly(True)
        self.dataset_info_text.setMaximumHeight(120)
        self.dataset_info_text.setPlaceholderText("数据集信息将在这里显示")
        dataset_layout.addWidget(self.dataset_info_text)
        
        # 添加数据集操作按钮
        button_layout = QHBoxLayout()
        
        # 添加获取数据集按钮（联网模式）
        self.dataset_download_button = QPushButton("获取数据集")
        self.dataset_download_button.clicked.connect(self._get_offline_package)  # 直接连接到方法
        button_layout.addWidget(self.dataset_download_button)
        
        # 添加上传数据集按钮（离线模式）
        self.dataset_upload_button = QPushButton("上传数据集")
        self.dataset_upload_button.clicked.connect(self._load_offline_package)
        button_layout.addWidget(self.dataset_upload_button)
        
        dataset_layout.addLayout(button_layout)
        
        # 设置布局
        dataset_group.setLayout(dataset_layout)
        left_layout.addWidget(dataset_group)
        
        # 并发设置
        concurrency_group = QGroupBox("并发设置")
        concurrency_layout = QHBoxLayout()
        
        # 添加并发数显示（改为显示标签而不是可编辑的spinbox）
        concurrency_layout.addWidget(QLabel("并发数:"))
        self.concurrency_label = QLabel("0")  # 初始值为0，后续根据数据集自动设置
        concurrency_layout.addWidget(self.concurrency_label)
        
        # 添加说明标签
        concurrency_info = QLabel("(自动设置为数据集记录数)")
        concurrency_info.setStyleSheet("color: gray; font-size: 11px;")
        concurrency_layout.addWidget(concurrency_info)

        # 添加弹性空间，使状态指示器靠右显示
        concurrency_layout.addStretch()
        
        # 添加测试状态指示器
        concurrency_layout.addWidget(QLabel("测试状态:"))
        self.test_status_label = QLabel("就绪")
        self.test_status_label.setStyleSheet("color: green; font-weight: bold;")
        concurrency_layout.addWidget(self.test_status_label)

        concurrency_group.setLayout(concurrency_layout)
        left_layout.addWidget(concurrency_group)
        
        # 测试控制
        test_control_group = QGroupBox("测试控制")
        test_control_layout = QVBoxLayout()
        
        # 添加开始按钮
        self.start_button = QPushButton("开始跑分测试")
        self.start_button.setIcon(QIcon.fromTheme("media-playback-start", QIcon(":/icons/start.png")))
        self.start_button.setIconSize(QSize(16, 16))
        self.start_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.start_button.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
            QPushButton:pressed {
                background-color: #3d8b40;
            }
            QPushButton:disabled {
                background-color: #cccccc;
                color: #666666;
            }
        """)
        self.start_button.clicked.connect(self.start_benchmark)
        
        # 添加停止按钮 (替换原有的复选框)
        self.stop_button = QPushButton("停止测试")
        self.stop_button.setIcon(QIcon.fromTheme("media-playback-stop", QIcon(":/icons/stop.png")))
        self.stop_button.setIconSize(QSize(16, 16))
        self.stop_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.stop_button.setStyleSheet("""
            QPushButton {
                background-color: #f44336;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #d32f2f;
            }
            QPushButton:pressed {
                background-color: #b71c1c;
            }
            QPushButton:disabled {
                background-color: #cccccc;
                color: #666666;
            }
        """)
        self.stop_button.clicked.connect(self.stop_benchmark)
        self.stop_button.setEnabled(False)  # 初始状态禁用
        
        # 将开始和停止按钮放在同一行
        buttons_layout = QHBoxLayout()
        buttons_layout.addWidget(self.start_button)
        buttons_layout.addWidget(self.stop_button)
        test_control_layout.addLayout(buttons_layout)
        
        # 添加API超时设置选项
        timeout_layout = QHBoxLayout()
        timeout_layout.addWidget(QLabel("API超时设置(秒):"))
        self.api_timeout_spin = QSpinBox()
        self.api_timeout_spin.setMinimum(30)  # 最小30秒
        self.api_timeout_spin.setMaximum(600)  # 最大600秒（10分钟）
        self.api_timeout_spin.setValue(120)  # 默认120秒
        self.api_timeout_spin.setToolTip("设置API请求的超时时间，超过此时间未收到响应将视为超时")
        timeout_layout.addWidget(self.api_timeout_spin)
        test_control_layout.addLayout(timeout_layout)
        
        test_control_group.setLayout(test_control_layout)
        left_layout.addWidget(test_control_group)
        
        # 创建左侧容器
        left_container = QWidget()
        left_container.setLayout(left_layout)
        
        # 创建右侧布局（GPU监控、测试进度、测试结果）
        right_layout = QVBoxLayout()
        
        # 添加GPU监控
        gpu_monitor_group = QGroupBox("GPU监控")
        gpu_monitor_layout = QVBoxLayout()
        
        # 添加GPU监控组件
        self.gpu_monitor = GPUMonitorWidget()
        gpu_monitor_layout.addWidget(self.gpu_monitor)
        
        gpu_monitor_group.setLayout(gpu_monitor_layout)
        right_layout.addWidget(gpu_monitor_group)
        
        # 添加测试信息 - 使用进度条和状态标签
        test_info_group = QGroupBox("测试进度")
        test_info_layout = QVBoxLayout()
        
        # 添加总耗时标签
        time_layout = QHBoxLayout()
        time_layout.addWidget(QLabel("总耗时:"))
        self.total_time_label = QLabel("0秒")
        time_layout.addWidget(self.total_time_label)
        time_layout.addStretch()
        test_info_layout.addLayout(time_layout)
        
        # 添加详细的测试进度信息
        self.test_progress_text = QTextEdit()
        self.test_progress_text.setReadOnly(True)
        self.test_progress_text.setMaximumHeight(100)
        self.test_progress_text.setPlaceholderText("测试进度信息将在这里显示...")
        test_info_layout.addWidget(self.test_progress_text)
        
        # 添加进度条
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        test_info_layout.addWidget(self.progress_bar)
        
        test_info_group.setLayout(test_info_layout)
        right_layout.addWidget(test_info_group)
        
        # 创建右侧容器
        right_container = QWidget()
        right_container.setLayout(right_layout)
        
        # 添加左右两侧到分割器
        content_splitter.addWidget(left_container)
        content_splitter.addWidget(right_container)
        content_splitter.setSizes([400, 600])  # 设置初始大小
        
        main_layout.addWidget(content_splitter)
        
        # 添加测试结果表格
        result_group = QGroupBox("测试结果")
        result_layout = QVBoxLayout()
        
        # 创建表格
        self.result_table = QTableWidget()
        self.result_table.setColumnCount(9)
        self.result_table.setHorizontalHeaderLabels([
            "会话ID", "数据集名称", "成功/总数", "成功率", "平均响应时间", "平均生成速度", "总字符数", "总时间", "平均输出TPS"
        ])
        self.result_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        result_layout.addWidget(self.result_table)
        
        result_group.setLayout(result_layout)
        main_layout.addWidget(result_group)
        
        # 添加错误信息区域
        error_group = QGroupBox("错误")
        error_layout = QVBoxLayout()
        
        self.error_text = QTextEdit()
        self.error_text.setReadOnly(True)
        self.error_text.setPlaceholderText("测试过程中的错误信息将在此显示...")
        error_layout.addWidget(self.error_text)
        
        error_group.setLayout(error_layout)
        main_layout.addWidget(error_group)
        
        # 设置主布局
        self.setLayout(main_layout)
        
        # 加载模型列表
        self.load_models()
        
        # 初始化UI状态
        self._update_mode_ui()
        
        # 更新数据集按钮可见性
        self._update_dataset_buttons()
        
        # 更新状态标签
        self._update_status_label()
    
    def _create_user_config(self):
        """创建用户配置组件"""
        # 创建分组框
        group_box = QGroupBox("用户配置")
        
        # 创建布局
        layout = QFormLayout()
        
        # 添加昵称输入
        self.nickname_input = QLineEdit()
        self.nickname_input.setObjectName("nickname_input")  # 设置对象名称
        settings = db_manager.get_benchmark_settings()
        self.nickname_input.setText(settings.get("device_name", "未命名设备"))
        self.nickname_input.textChanged.connect(self._on_nickname_changed)
        self.nickname_input.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)  # 水平方向自适应
        layout.addRow("设备名称:", self.nickname_input)
        
        # 添加API密钥输入和清除按钮
        api_key_layout = QHBoxLayout()
        
        # API密钥输入框
        self.api_key_input = QLineEdit()
        self.api_key_input.setObjectName("api_key_input")  # 设置对象名称
        self.api_key_input.setEchoMode(QLineEdit.EchoMode.Password)  # 密码模式，不显示明文
        
        # 从数据库获取API密钥
        if settings:
            saved_api_key = settings.get("api_key", "")
            if saved_api_key:
                self.api_key_input.setText(saved_api_key)
                self.api_key_input.setPlaceholderText("")
            else:
                self.api_key_input.setPlaceholderText("请输入API密钥")
        
        self.api_key_input.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)  # 水平方向自适应
        self.api_key_input.setEnabled(True)
        self.api_key_input.setStyleSheet("QLineEdit { background-color: white; color: black; }")
        self.api_key_input.setReadOnly(False)  # 确保不是只读的
        api_key_layout.addWidget(self.api_key_input)
        
        # 添加清除按钮
        clear_button = QPushButton("清除")
        clear_button.setObjectName("clear_button")  # 设置对象名称
        clear_button.setFixedWidth(60)  # 设置固定宽度
        clear_button.setCursor(Qt.CursorShape.PointingHandCursor)
        clear_button.setStyleSheet("""
            QPushButton {
                background-color: #f44336;
                color: white;
                border: none;
                padding: 4px 8px;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #e53935;
            }
            QPushButton:pressed {
                background-color: #d32f2f;
            }
        """)
        clear_button.clicked.connect(self._clear_api_key)
        api_key_layout.addWidget(clear_button)
        
        # 将API密钥布局添加到表单
        layout.addRow("API密钥:", api_key_layout)
        
        # 添加模式选择
        self.mode_select = QComboBox()
        self.mode_select.setObjectName("mode_select")  # 设置对象名称
        self.mode_select.addItem("联网模式")
        self.mode_select.addItem("离线模式")
        self.mode_select.setCurrentIndex(settings.get("mode", 0) if settings else 0)  # 从数据库获取默认值
        self.mode_select.currentIndexChanged.connect(self._on_mode_changed)
        layout.addRow("运行模式:", self.mode_select)
        
        # 添加控制按钮
        button_layout = QHBoxLayout()
        
        # 创建启用跑分模块按钮
        self.enable_button = QPushButton("启用跑分模块")
        self.enable_button.setObjectName("enable_button")  # 设置对象名称
        self.enable_button.clicked.connect(self._enable_benchmark_module)
        button_layout.addWidget(self.enable_button)
        
        # 创建禁用跑分模块按钮
        self.disable_button = QPushButton("禁用跑分模块")
        self.disable_button.setObjectName("disable_button")  # 设置对象名称
        self.disable_button.clicked.connect(self._disable_benchmark_module)
        button_layout.addWidget(self.disable_button)
        
        # 添加按钮布局到表单
        layout.addRow("", button_layout)
        
        # 设置布局
        group_box.setLayout(layout)
        
        return group_box
    
    def _create_dataset_manager(self):
        """创建数据集管理器部分"""
        # 创建数据集管理器组
        dataset_group = QGroupBox("数据集管理")
        layout = QVBoxLayout()
        
        # 创建按钮布局
        button_layout = QHBoxLayout()
        
        # 创建获取数据集按钮
        self.dataset_download_button = QPushButton("获取数据集")
        self.dataset_download_button.clicked.connect(self._get_offline_package)  # 直接连接到方法
        button_layout.addWidget(self.dataset_download_button)
        
        # 添加上传数据集按钮（离线模式）
        self.dataset_upload_button = QPushButton("上传数据集")
        self.dataset_upload_button.clicked.connect(self._load_offline_package)
        button_layout.addWidget(self.dataset_upload_button)
        
        layout.addLayout(button_layout)
        
        # 设置布局
        dataset_group.setLayout(layout)
        
        return dataset_group
    
    def _create_model_config(self):
        """创建模型配置组件"""
        # 创建分组框
        group_box = QGroupBox("模型配置")
        
        # 创建布局
        layout = QFormLayout()
        
        # 添加精度选择
        self.precision_combo = QComboBox()
        self.precision_combo.addItem("FP32")
        self.precision_combo.addItem("FP16")
        self.precision_combo.addItem("INT8")
        layout.addRow("精度:", self.precision_combo)
        
        # 添加参数量输入
        self.params_input = QLineEdit()
        self.params_input.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)  # 水平方向自适应
        layout.addRow("参数量(M):", self.params_input)
        
        # 添加框架配置输入
        self.framework_input = QLineEdit()
        self.framework_input.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)  # 水平方向自适应
        layout.addRow("框架配置:", self.framework_input)
        
        # 添加按钮
        button_layout = QHBoxLayout()
        self.model_config_button = QPushButton("保存配置")
        button_layout.addWidget(self.model_config_button)
        layout.addRow("", button_layout)
        
        # 设置布局
        group_box.setLayout(layout)
        
        return group_box
    
    def _enable_benchmark_module(self):
        """启用跑分模块"""
        # 禁用按钮，防止重复点击
        self.enable_button.setEnabled(False)
        self.enable_button.setText("正在启用...")
        
        # 获取昵称
        nickname = self.nickname_input.text()
        if not nickname:
            nickname = "未命名设备"
        
        # 获取API密钥
        api_key = self.api_key_input.text()
        
        # 验证API密钥
        if not api_key:
            QMessageBox.warning(self, "警告", "请输入API密钥")
            self.enable_button.setEnabled(True)
            self.enable_button.setText("启用跑分模块")
            return
        
        # 保存设置到数据库
        settings = {
            "device_id": self.device_id,
            "api_key": api_key,
            "device_name": nickname,
            "is_enabled": True,
            "mode": self.mode_select.currentIndex()
        }
        if not db_manager.save_benchmark_settings(settings):
            QMessageBox.critical(self, "错误", "保存设置失败")
            self.enable_button.setEnabled(True)
            self.enable_button.setText("启用跑分模块")
            return
        
        # 设置API密钥到benchmark_integration
        benchmark_integration.set_api_key(api_key, self.device_id, nickname)
        
        # 更新状态标签
        self._update_status_label()
        
        # 更新模式UI
        self._update_mode_ui()
        
        # 显示成功消息
        QMessageBox.information(self, "成功", "跑分模块已启用")
        
        # 恢复按钮状态
        self.enable_button.setEnabled(True)
        self.enable_button.setText("启用跑分模块")
    
    def _disable_benchmark_module(self):
        """禁用跑分模块"""
        # 禁用按钮，防止重复点击
        self.disable_button.setEnabled(False)
        self.disable_button.setText("正在禁用...")
        
        # 保存设置到数据库
        settings = db_manager.get_benchmark_settings()
        if settings:
            settings["is_enabled"] = False
            if not db_manager.save_benchmark_settings(settings):
                QMessageBox.critical(self, "错误", "保存设置失败")
                self.disable_button.setEnabled(True)
                self.disable_button.setText("禁用跑分模块")
                return
        
        # 禁用跑分模块
        benchmark_integration.disable_benchmark_module(self._on_disable_result)
    
    def _on_disable_result(self, success, message):
        """禁用跑分模块结果处理"""
        # 恢复按钮状态
        self.disable_button.setEnabled(True)
        self.disable_button.setText("禁用跑分模块")
        
        if success:
            # 设置跑分模块已禁用标志
            settings = db_manager.get_benchmark_settings()
            if settings:
                settings["is_enabled"] = False
                db_manager.save_benchmark_settings(settings)
            # 更新状态标签
            self._update_status_label()
            # 更新模式UI
            self._update_mode_ui()
            # 显示成功消息
            QMessageBox.information(self, "成功", message)
        else:
            # 显示错误消息
            QMessageBox.warning(self, "警告", message)
    
    def load_models(self):
        """加载模型列表"""
        try:
            # 清空模型下拉框
            self.model_combo.clear()
            
            # 从数据库中加载模型列表而不是从配置中加载
            models = db_manager.get_model_configs()
            for model in models:
                if "name" in model:
                    self.model_combo.addItem(model["name"])
            
            logger.info(f"加载了 {self.model_combo.count()} 个模型")
        except Exception as e:
            logger.error(f"加载模型列表失败: {str(e)}")
    
    def get_selected_model(self) -> dict:
        """获取选中的模型配置"""
        if self.model_combo.count() == 0 or self.model_combo.currentIndex() < 0:
            return {}
        
        # 获取选中的模型名称
        model_name = self.model_combo.currentText()
        
        # 从数据库中获取模型信息而不是从配置中获取
        models = db_manager.get_model_configs()
        model = next((m for m in models if m["name"] == model_name), None)
        
        # 如果没有找到匹配的模型，返回基本信息
        return model if model else {"name": model_name}
    
    def _on_nickname_changed(self, text):
        """昵称变更处理"""
        # 保存到数据库
        settings = db_manager.get_benchmark_settings()
        if settings:
            settings["device_name"] = text
            db_manager.save_benchmark_settings(settings)
    
    def _on_mode_changed(self):
        """模式切换处理"""
        # 获取当前选择的模式
        mode = self.mode_select.currentIndex()  # 0=联网模式，1=离线模式
        logger.info(f"模式切换: {'联网模式' if mode == 0 else '离线模式'}")
        
        # 更新成员变量
        self.test_mode = mode
        
        # 保存设置到数据库
        settings = db_manager.get_benchmark_settings() or {}
        settings["mode"] = mode
        db_manager.save_benchmark_settings(settings)
        
        # 更新配置
        config.set("benchmark.mode", mode)
        
        # 更新benchmark_integration的测试模式
        if hasattr(benchmark_integration, 'benchmark_manager'):
            # 调用benchmark_manager的set_test_mode方法
            try:
                benchmark_integration.benchmark_manager.set_test_mode(mode)
                logger.info(f"测试模式已更新为: {mode} ({'联网模式' if mode == 0 else '离线模式'})")
            except Exception as e:
                logger.error(f"更新测试模式时出错: {str(e)}")
        else:
            logger.error("无法更新测试模式：benchmark_manager不存在")
        
        # 更新UI状态
        self._update_mode_ui()
        
        # 更新数据集按钮状态和可见性
        self._update_dataset_buttons()
    
    def _update_mode_ui(self):
        """根据模式更新UI"""
        # 从数据库获取设置
        settings = db_manager.get_benchmark_settings()
        mode = settings.get("mode", 0)
        is_enabled = settings.get("is_enabled", True)
        api_key = settings.get("api_key", "")
        
        can_test = bool(is_enabled and (mode == 1 or (mode == 0 and api_key)))
        self.start_button.setEnabled(can_test)
        self.stop_button.setEnabled(can_test)
    
    def _update_status_label(self):
        """更新状态标签"""
        # 从数据库获取设置
        settings = db_manager.get_benchmark_settings()
        is_enabled = settings.get("is_enabled", True)
        mode = settings.get("mode", 0)
        api_key = settings.get("api_key", "")
        
        # 构建状态文本
        if is_enabled:
            if mode == 0:  # 联网模式
                if api_key:
                    status_text = f"跑分模式: 已启用 | API密钥: 已配置 | 运行模式: 联网模式"
                else:
                    status_text = f"跑分模式: 已启用 | API密钥: 未配置 | 运行模式: 联网模式"
            else:  # 离线模式
                status_text = f"跑分模式: 已启用 | 运行模式: 离线模式"
        else:
            status_text = "跑分模式: 未启用"
        
        # 设置状态文本
        self.status_label.setText(status_text)
    
    def _clear_api_key(self):
        """清除API密钥"""
        # 清空输入框
        self.api_key_input.clear()
        
        # 从数据库中清除API密钥
        settings = db_manager.get_benchmark_settings()
        if settings:
            settings["api_key"] = ""
            db_manager.save_benchmark_settings(settings)
        
        # 如果已经设置了API密钥到benchmark_integration，也需要清除
        if hasattr(benchmark_integration, 'set_api_key'):
            benchmark_integration.set_api_key("", self.device_id, self.nickname_input.text())
        
        # 更新状态标签
        self._update_status_label()
        
        # 显示提示消息
        QMessageBox.information(self, "成功", "API密钥已清除")

    def _get_offline_package(self):
        """获取离线测试数据包"""
        try:
            # 检查API密钥
            api_key = config.get("benchmark.api_key")
            logger.debug(f"当前API密钥状态: {'已设置' if api_key else '未设置'}")
            if not api_key:
                QMessageBox.warning(self, "错误", "请先配置API密钥")
                return
            
            # 禁用按钮
            self.dataset_download_button.setEnabled(False)
            self.dataset_download_button.setText("正在获取...")
            
            # 重置状态
            if hasattr(benchmark_integration, 'running') and benchmark_integration.running:
                logger.warning("有正在进行的操作，先停止它")
                benchmark_integration.stop_benchmark()
            
            # 定义回调函数
            def on_package_received(success: bool, message: str = None, package: dict = None):
                try:
                    # 恢复按钮状态
                    self.dataset_download_button.setEnabled(True)
                    self.dataset_download_button.setText("获取数据集")
                    
                    if success:
                        logger.info(f"离线包获取成功，开始解密流程")
                        if package:
                            logger.debug(f"离线包内容: {package.keys() if isinstance(package, dict) else type(package)}")
                        
                        # 更新数据集信息显示
                        self._update_dataset_info_display()
                        
                        # 检查数据集是否成功加载
                        dataset_info = benchmark_integration.get_dataset_info()
                        logger.debug(f"数据集信息: {dataset_info if isinstance(dataset_info, dict) else type(dataset_info)}")
                        
                        # 判断数据集是否加载成功（兼容返回布尔值或字典的情况）
                        if dataset_info and (isinstance(dataset_info, dict) or dataset_info is True):
                            # 设置数据集已更新标志
                            self.dataset_updated = True
                            QMessageBox.information(self, "获取成功", "数据集获取并解密成功")
                            # 启用开始测试按钮
                            self.start_button.setEnabled(True)
                        else:
                            QMessageBox.warning(self, "解密失败", "数据集获取成功但解密失败，请检查API密钥是否正确")
                    else:
                        error_msg = message or "未知错误"
                        logger.error(f"离线包获取失败: {error_msg}")
                        QMessageBox.warning(self, "获取失败", error_msg)
                except Exception as e:
                    logger.error(f"回调处理异常: {str(e)}")
                    QMessageBox.warning(self, "处理失败", f"数据处理失败: {str(e)}")
                finally:
                    # 确保按钮状态恢复
                    self.dataset_download_button.setEnabled(True)
                    self.dataset_download_button.setText("获取数据集")
            
            # 发起获取离线包请求
            logger.info(f"开始获取离线包，使用API密钥: {api_key[:4]}...")
            # 调用benchmark_integration获取离线包方法，传入ID为1的数据集（默认数据集）
            benchmark_integration.get_offline_package(1, on_package_received)
        
        except Exception as e:
            logger.error(f"获取离线包出错: {str(e)}")
            QMessageBox.warning(self, "错误", f"获取离线包失败: {str(e)}")
            # 确保按钮状态恢复
            self.dataset_download_button.setEnabled(True)
            self.dataset_download_button.setText("获取数据集")

    def _load_offline_package(self):
        """加载离线包"""
        try:
            # 检查API密钥
            api_key = config.get("benchmark.api_key", "")
            if not api_key:
                QMessageBox.warning(self, "错误", "请先配置API密钥")
                return
            
            # 打开文件选择对话框
            file_path, _ = QFileDialog.getOpenFileName(
                self,
                "选择离线包文件",
                "",
                "JSON文件 (*.json);;所有文件 (*)"
            )
            
            if not file_path:
                return
            
            # 禁用按钮，防止重复点击
            self.dataset_upload_button.setEnabled(False)
            self.dataset_upload_button.setText("正在加载...")
            
            # 定义回调函数
            def on_package_loaded(success: bool, message: str):
                # 恢复按钮状态
                self.dataset_upload_button.setEnabled(True)
                self.dataset_upload_button.setText("上传数据集")
                
                if success:
                    # 更新数据集信息显示
                    self._update_dataset_info_display()
                    # 设置数据集已更新标志
                    self.dataset_updated = True
                    QMessageBox.information(self, "加载成功", "数据集加载成功")
                else:
                    QMessageBox.warning(self, "加载失败", message)
            
            # 加载离线包
            benchmark_integration.load_offline_package(file_path, callback=on_package_loaded)
            
        except Exception as e:
            # 恢复按钮状态
            self.dataset_upload_button.setEnabled(True)
            self.dataset_upload_button.setText("上传数据集")
            
            error_msg = str(e)
            logger.error(f"加载数据集错误: {error_msg}")
            QMessageBox.warning(self, "加载失败", f"数据集加载失败: {error_msg}")

    def _update_dataset_info_display(self):
        """更新数据集信息显示"""
        dataset_info = benchmark_integration.get_dataset_info()
        if not dataset_info:
            self.dataset_info_text.setText("未加载数据集")
            return
        
        logger.debug(f"更新数据集信息显示，数据集信息: {dataset_info}")
        
        # 构建信息文本
        info_text = ""
        
        # 获取元数据信息
        metadata = dataset_info.get('metadata', {})
        logger.debug(f"元数据信息: {metadata}")
        
        # 获取文件大小 - 使用实际大小或元数据中的大小
        file_size = dataset_info.get('size', 0)
        logger.debug(f"文件大小: {file_size} 字节")
        
        # 计算并格式化数据集大小
        dataset_size = file_size / 1024  # 转换为KB
        size_text = f"{dataset_size:.2f} KB" if dataset_size < 1024 else f"{dataset_size/1024:.2f} MB"
        
        # 处理下载时间
        download_time = metadata.get('download_time', int(time.time() * 1000))
        download_time_str = datetime.fromtimestamp(download_time/1000).strftime('%Y-%m-%d %H:%M:%S')
        
        # 获取离线包格式版本
        package_format = metadata.get('package_format', '3.0')
        
        # 构建信息文本
        info_text = "数据集信息:\n"
        info_text += f"dataset_name: {metadata.get('dataset_name', dataset_info.get('名称', '未知'))}\n"
        info_text += f"dataset_version: {metadata.get('dataset_version', dataset_info.get('版本', '未知'))}\n"
        info_text += f"package_format: {package_format}\n"
        info_text += f"download_time: {download_time_str}\n"
        info_text += f"大小: {size_text}\n"
        
        # 添加记录数
        if "记录数" in dataset_info:
            record_count = dataset_info["记录数"]
            info_text += f"记录数: {record_count}\n"
            # 更新并发数标签显示
            self.concurrency_label.setText(str(record_count))
        
        # 添加描述
        if "描述" in dataset_info:
            info_text += f"描述: {dataset_info['描述']}\n"
        
        # 添加创建时间
        if "created_at" in dataset_info:
            # 尝试格式化ISO时间字符串
            try:
                created_at = dataset_info["created_at"]
                if isinstance(created_at, str) and 'T' in created_at:
                    # ISO格式的日期时间
                    date_part = created_at.split('T')[0]
                    time_part = created_at.split('T')[1].split('.')[0] if '.' in created_at.split('T')[1] else created_at.split('T')[1]
                    info_text += f"创建时间: {date_part} {time_part}\n"
                else:
                    info_text += f"创建时间: {created_at}\n"
            except:
                info_text += f"创建时间: {dataset_info.get('created_at', '未知')}\n"
        
        # 添加到期时间
        if "expires_at" in dataset_info:
            # 尝试格式化ISO时间字符串
            try:
                expires_at = dataset_info["expires_at"]
                if isinstance(expires_at, str) and 'T' in expires_at:
                    # ISO格式的日期时间
                    date_part = expires_at.split('T')[0]
                    time_part = expires_at.split('T')[1].split('.')[0] if '.' in expires_at.split('T')[1] else expires_at.split('T')[1]
                    info_text += f"到期时间: {date_part} {time_part}\n"
                else:
                    info_text += f"到期时间: {expires_at}\n"
            except:
                info_text += f"到期时间: {dataset_info.get('expires_at', '未知')}\n"
        
        # 设置信息文本
        self.dataset_info_text.setText(info_text)
        
        # 启用数据集相关按钮
        self._update_dataset_buttons()

    def _on_test_start(self):
        """
        开始测试时的处理函数
        """
        # 获取当前模式
        mode = config.get("benchmark.mode", 0)  # 0=联网模式，1=离线模式
        
        # 检查API密钥
        if mode == 0 and not config.get("benchmark.api_key"):
            QMessageBox.warning(self, "警告", "联网模式下需要配置API密钥")
            return
    
    def start_benchmark(self):
        """开始跑分测试"""
        try:
            # 重置结果处理标志
            self._result_processed = False
            
            logger.info("开始跑分测试...")
            
            # 检查是否已经在测试中
            if self.is_testing:
                QMessageBox.warning(self, "警告", "测试已在进行中")
                return
            
            # 检查数据集是否已加载
            if not self.dataset_updated:
                QMessageBox.warning(self, "警告", "请先更新或上传测试数据集")
                logger.warning("无法开始测试：未更新或上传测试数据集")
                return
                
            # 获取选择的模型
            model_config = self.get_selected_model()
            if not model_config:
                QMessageBox.warning(self, "警告", "请先选择模型")
                logger.warning("无法开始测试：未选择模型")
                return
            
            # 获取API地址 - 使用模型配置中的API URL或配置中的默认值
            api_url = model_config.get("api_url", "")
            if not api_url:
                api_url = config.get("benchmark.api_url", "http://localhost:8083/v1")
                
            # 获取并发数 - 使用数据集记录数
            dataset_info = benchmark_integration.get_dataset_info()
            if isinstance(dataset_info, dict) and "记录数" in dataset_info:
                concurrency = int(dataset_info["记录数"])
            else:
                # 如果无法获取记录数，使用默认值1
                concurrency = 1
                
            logger.debug(f"使用数据集记录数作为并发数: {concurrency}")
            
            # 获取API超时设置
            api_timeout = self.api_timeout_spin.value()
            logger.debug(f"API超时设置: {api_timeout}秒")
            
            # 从数据库获取当前测试模式
            settings = db_manager.get_benchmark_settings()
            test_mode = settings.get("mode", 0) if settings else 0
            logger.info(f"使用测试模式: {test_mode} ({'联网模式' if test_mode == 0 else '离线模式'})")
            
            # 更新UI状态 - 设置为测试中
            self.is_testing = True
            self.update_ui_buttons()
            
            # 生成更用户友好的会话ID
            import time
            current_time = int(time.time())
            time_str = time.strftime("%m-%d-%H-%M", time.localtime(current_time))
            
            # 生成短随机部分，确保唯一性
            import random
            import string
            random_id = ''.join(random.choice(string.hexdigits.lower()) for _ in range(4))
            
            # 最终格式: MM-DD-HH-MM-xxxx (例如: 03-15-19-50-a7f3)
            self.test_task_id = f"{time_str}-{random_id}"
            
            logger.debug(f"生成测试任务ID: {self.test_task_id}")
            
            # 创建测试线程
            self.test_thread = BenchmarkThread(self.config)
            
            # 连接信号
            self.test_thread.progress_updated.connect(self.on_progress_updated)
            self.test_thread.test_finished.connect(self.on_test_finished)
            self.test_thread.test_error.connect(self.on_test_error)
            
            # 设置测试参数并启动线程
            self.test_thread.set_test_parameters(
                model=model_config["name"], 
                api_url=api_url,
                model_params=model_config, 
                concurrency=concurrency,
                test_mode=test_mode,
                api_timeout=api_timeout
            )
            self.test_thread.start()  # 直接启动线程，不传递参数
            
            # 更新UI - 会在progress回调中更新
            self.progress_bar.setValue(0)
            self.status_label.setText("测试进行中...")
            self.test_progress_text.setText("测试开始中，等待结果...")
            self.is_testing = True
            self.update_ui_buttons()
            
            # 更新测试状态指示器
            self.test_status_label.setText("运行中")
            self.test_status_label.setStyleSheet("color: blue; font-weight: bold;")
            
            logger.info(f"测试已启动：模型={model_config['name']}, API={api_url}, 并发数={concurrency}")
        except Exception as e:
            logger.error(f"启动测试失败: {str(e)}")
            QMessageBox.critical(self, "错误", f"启动测试失败: {str(e)}")
            self.is_testing = False
            self.update_ui_buttons()
    
    def stop_benchmark(self):
        """
        停止基准测试
        """
        logger.debug("停止基准测试")
        
        if hasattr(self, 'benchmark_thread') and self.benchmark_thread.isRunning():
            self.benchmark_thread.stop()
            logger.debug("已发送停止信号到测试线程")
        
        if hasattr(self, 'test_thread') and self.test_thread and self.test_thread.isRunning():
            self.test_thread.stop()
            logger.debug("已发送停止信号到测试线程")
        
        # 更新UI状态
        self.is_testing = False
        self.update_ui_buttons()
        self.status_label.setText("测试状态: 已停止")
        
        # 更新测试状态指示器
        self.test_status_label.setText("已停止")
        self.test_status_label.setStyleSheet("color: orange; font-weight: bold;")
    
    def on_progress_updated(self, progress_data):
        """
        处理进度更新 (从BenchmarkThread接收的信号)
        """
        self._on_progress_updated(progress_data)
    
    def on_test_finished(self, result):
        """处理测试完成"""
        try:
            logger.info("基准测试完成")
            logger.info(f"测试结果初始状态 - framework_info存在: {'framework_info' in result}, 值类型: {type(result.get('framework_info', None)).__name__}")
            
            # 获取框架信息
            framework_info = self._get_framework_info()
            if framework_info:
                logger.info(f"检测到框架信息: {framework_info}")
                logger.info(f"更新前的framework_info: {result.get('framework_info')}")
                # 确保result有framework_info键，无论它是否为None
                result["framework_info"] = framework_info
                logger.info(f"更新后的framework_info: {result['framework_info']}")
                logger.info(f"result对象id: {id(result)}")
                
                # 更新原始结果文件，而不是创建新文件
                if "result_path" in result and result["result_path"]:
                    from src.benchmark.utils.result_handler import result_handler
                    logger.info(f"更新原始结果文件: {result['result_path']}")
                    # 使用update_result方法而不是save_result，避免创建新文件
                    result_handler.update_result(result["result_path"], {"framework_info": framework_info})
                else:
                    logger.warning("无法更新原始结果文件，因为result_path不存在")
            else:
                logger.warning("未能获取框架信息")
            
            # 显示模型信息对话框
            model_info = self._show_model_info_dialog(framework_info)
            if model_info:
                # 更新结果中的模型信息
                if "model_info" not in result:
                    result["model_info"] = {}
                logger.info(f"更新前的model_info: {result.get('model_info')}")
                result["model_info"].update(model_info)
                logger.info(f"更新后的model_info: {result.get('model_info')}")
                
                # 更新原始结果文件中的model_info
                if "result_path" in result and result["result_path"]:
                    from src.benchmark.utils.result_handler import result_handler
                    # 使用update_result方法更新model_info
                    result_handler.update_result(result["result_path"], {"model_info": result["model_info"]})
            
            # 确保benchmark_manager.latest_test_result也被更新
            if hasattr(benchmark_integration, 'benchmark_manager'):
                logger.info("更新benchmark_manager.latest_test_result")
                benchmark_integration.benchmark_manager.latest_test_result = result
                if 'framework_info' in result and result['framework_info']:
                    logger.info(f"确保latest_test_result中包含framework_info: {result['framework_info']}")
            
            # 更新UI状态
            self.is_testing = False
            self.update_ui_buttons()
            
            # 保存最新的测试结果
            self.latest_test_result = result
            
            # 根据当前模式显示不同的对话框
            should_upload = False
            
            # 首先询问是否要加密测试记录
            encrypt_reply = QMessageBox.question(
                self,
                "测试完成",
                "是否要加密测试记录？",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.Yes
            )
            
            # 如果用户选择加密，并且是联网模式，再询问是否上传到服务器
            if encrypt_reply == QMessageBox.StandardButton.Yes:
                if self.test_mode == 0:  # 联网模式
                    upload_reply = QMessageBox.question(
                        self,
                        "上传确认",
                        "检测到您正在使用联网模式。是否同时将加密测试记录上传到服务器？",
                        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                        QMessageBox.StandardButton.Yes
                    )
                    should_upload = upload_reply == QMessageBox.StandardButton.Yes
                
                logger.info(f"开始加密测试记录，是否上传: {should_upload}")
                # 创建结果处理线程
                self.result_worker = ResultWorker(self.test_mode, benchmark_integration, should_upload)
                self.result_worker.progress_updated.connect(self._on_encryption_progress)
                self.result_worker.finished_signal.connect(self._on_encryption_finished)
                self.result_worker.error_signal.connect(self._on_encryption_error)
                
                # 启动加密和上传过程
                self.result_worker.start()
            
        except Exception as e:
            logger.error(f"处理测试完成时出错: {str(e)}")
            QMessageBox.critical(
                self,
                "错误",
                f"处理测试结果时出错: {str(e)}"
            )

    def save_config(self):
        """
        保存配置
        """
        # 保存当前模式
        mode = config.get("benchmark.mode", 0)  # 0=联网模式，1=离线模式
        config.set("benchmark.mode", mode)
        
        # 其他代码保持不变... 

    def _open_server_link(self):
        """打开服务器网站"""
        try:
            import webbrowser
            server_url = config.get("benchmark.server_url", "http://localhost:8083")
            # 确保URL以http://或https://开头
            if not server_url.startswith("http://") and not server_url.startswith("https://"):
                server_url = "http://" + server_url
            webbrowser.open(server_url)
            logger.info(f"已打开服务器网站: {server_url}")
        except Exception as e:
            logger.error(f"打开服务器网站失败: {str(e)}")
            QMessageBox.critical(self, "错误", f"打开服务器网站失败: {str(e)}")

    def _show_settings_dialog(self):
        """显示用户配置对话框"""
        try:
            # 创建对话框
            dialog = QDialog(self)
            dialog.setWindowTitle("跑分基础设置")
            dialog.setMinimumWidth(400)
            
            # 创建布局
            layout = QVBoxLayout(dialog)
            
            # 创建用户配置组件
            user_config = self._create_user_config()
            layout.addWidget(user_config)
            
            # 添加确定和取消按钮
            button_box = QDialogButtonBox(
                QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
            )
            button_box.accepted.connect(dialog.accept)
            button_box.rejected.connect(dialog.reject)
            layout.addWidget(button_box)
            
            # 确保API密钥输入框是启用的
            api_key_input = dialog.findChild(QLineEdit, "api_key_input")
            if api_key_input:
                api_key_input.setEnabled(True)
                api_key_input.setStyleSheet("QLineEdit { background-color: white; color: black; }")
                api_key_input.setReadOnly(False)
            
            # 获取昵称输入框
            nickname_input = dialog.findChild(QLineEdit, "nickname_input")
            
            # 获取运行模式选择框
            mode_select = dialog.findChild(QComboBox, "mode_select")
            
            # 显示对话框并等待用户响应
            if dialog.exec() == QDialog.DialogCode.Accepted:
                try:
                    # 获取设置值
                    nickname = nickname_input.text() if nickname_input else "未命名设备"
                    api_key = api_key_input.text() if api_key_input else ""
                    mode = mode_select.currentIndex() if mode_select else 0
                    
                    # 保存设置到数据库
                    settings = {
                        "device_id": self.device_id,
                        "api_key": api_key,
                        "device_name": nickname,
                        "is_enabled": True,
                        "mode": mode
                    }
                    
                    if db_manager.save_benchmark_settings(settings):
                        # 设置API密钥到benchmark_integration
                        benchmark_integration.set_api_key(api_key, self.device_id, nickname)
                        
                        # 更新状态标签
                        self._update_status_label()
                        
                        # 更新模式UI
                        self._update_mode_ui()
                        
                        # 显示成功消息
                        QMessageBox.information(self, "成功", "设置已保存")
                        
                        # 记录日志
                        logger.info("跑分基础设置已保存")
                    else:
                        QMessageBox.critical(self, "错误", "保存设置失败")
                        logger.error("保存跑分基础设置失败")
                
                except Exception as e:
                    QMessageBox.critical(self, "错误", f"保存设置时出错: {str(e)}")
                    logger.error(f"保存设置时出错: {str(e)}")
        
        except Exception as e:
            QMessageBox.critical(self, "错误", f"显示设置对话框时出错: {str(e)}")
            logger.error(f"显示设置对话框时出错: {str(e)}")

    def _update_dataset_buttons(self):
        """根据当前模式更新按钮显示状态"""
        # 从数据库获取当前模式
        settings = db_manager.get_benchmark_settings()
        if settings:
            mode = settings.get("mode", 0)  # 默认为联网模式(0)
        else:
            mode = 0  # 默认为联网模式
        
        # 保存到配置中
        config.set("benchmark.mode", mode)
        
        # 添加跟踪日志
        logger.info(f"_update_dataset_buttons: 当前模式={mode}，联网模式按钮将设为可见={mode == 0}，离线模式按钮将设为可见={mode == 1}")
        
        # 根据模式设置按钮的可见性
        self.dataset_download_button.setVisible(mode == 0)  # 联网模式显示下载按钮
        self.dataset_upload_button.setVisible(mode == 1)    # 离线模式显示上传按钮
        
        # 确保按钮在相应模式下可用
        self.dataset_download_button.setEnabled(mode == 0 and not self.is_testing)
        self.dataset_upload_button.setEnabled(mode == 1 and not self.is_testing)

    def update_ui_text(self):
        """更新UI文本"""
        # 更新按钮文本
        self.start_button.setText("开始测试")
        self.stop_button.setText("停止测试")
        self.settings_button.setText("设置")
        self.server_link_button.setText("打开服务器")
        
        # 更新标签文本
        if hasattr(self, 'model_label'):
            self.model_label.setText("选择模型:")
        
        # 更新数据集按钮
        if hasattr(self, 'dataset_download_button'):
            self.dataset_download_button.setText("获取数据集")
        if hasattr(self, 'dataset_upload_button'):
            self.dataset_upload_button.setText("上传数据集")
        
        # 更新模式选择
        if hasattr(self, 'mode_select'):
            # 保存当前索引
            current_index = self.mode_select.currentIndex()
            # 清空并重新添加项目
            self.mode_select.clear()
            self.mode_select.addItem("联网模式")
            self.mode_select.addItem("离线模式")
            # 恢复之前的选择
            if current_index >= 0 and current_index < self.mode_select.count():
                self.mode_select.setCurrentIndex(current_index)
        
        # 更新启用/禁用按钮
        if hasattr(self, 'enable_button'):
            self.enable_button.setText("启用")
        if hasattr(self, 'disable_button'):
            self.disable_button.setText("禁用")
        
        # 更新表格头
        if hasattr(self, 'result_table'):
            self.result_table.setHorizontalHeaderLabels([
                "会话ID",
                "数据集名称", 
                "成功/总数", 
                "成功率", 
                "平均响应时间", 
                "平均生成速度", 
                "总字符数", 
                "总时间", 
                "平均输出TPS"
            ])

    def update_ui_buttons(self):
        """更新UI按钮状态"""
        # 根据是否正在测试更新按钮状态
        self.start_button.setEnabled(not self.is_testing and self.dataset_updated)
        self.stop_button.setEnabled(self.is_testing)
        
        # 更新数据集按钮状态
        self._update_dataset_buttons()
        
        # 更新模型选择是否启用
        self.model_combo.setEnabled(not self.is_testing)

    def _on_progress_updated(self, progress_data):
        """
        处理进度更新的内部方法
        """
        try:
            # 获取进度信息
            progress = progress_data.get("progress", 0)
            status = progress_data.get("status", "未知")
            
            # 处理数据集进度
            if "datasets" in progress_data and progress_data["datasets"]:
                datasets = progress_data["datasets"]
                
                # 清空结果表格
                self.result_table.setRowCount(0)
                
                # 总进度计算变量
                total_completed = 0
                total_items = 0
                
                # 更新测试进度文本框
                progress_text = ""
                
                # 遍历所有数据集
                for dataset_name, dataset_stats in datasets.items():
                    # 获取数据集进度信息
                    completed = dataset_stats.get("completed", 0)  # 已成功完成的任务数
                    total = dataset_stats.get("total", 0)  # 总任务数
                    failed_count = dataset_stats.get("failed_count", 0)  # 失败任务数（含超时）
                    timeout_count = dataset_stats.get("timeout_count", 0)  # 超时任务数
                    error_count = dataset_stats.get("error_count", 0)  # 错误任务数
                    success_rate = dataset_stats.get("success_rate", 0)
                    avg_response_time = dataset_stats.get("avg_response_time", 0)
                    avg_generation_speed = dataset_stats.get("avg_generation_speed", 0)
                    total_time = dataset_stats.get("total_time", 0)
                    total_duration = dataset_stats.get("total_duration", 0)  # 新增字段
                    
                    # 更新进度文本信息
                    progress_text += f"数据集: {dataset_name}\n"
                    progress_text += f"进度: {completed}/{total} (成功完成/总数 {(completed/total*100) if total > 0 else 0:.1f}%)\n"
                    progress_text += f"状态: {status}\n"
                    if isinstance(success_rate, (int, float)):
                        progress_text += f"当前成功率: {success_rate*100 if success_rate <= 1 else success_rate:.2f}%\n"
                    if failed_count > 0:
                        progress_text += f"失败任务: {failed_count} (超时: {timeout_count}, 错误: {error_count})\n"
                    if isinstance(avg_response_time, (int, float)):
                        progress_text += f"平均响应时间: {avg_response_time:.2f}秒\n"
                    progress_text += f"已用时间: {total_duration:.1f}秒\n"
                    
                    # 设置进度文本
                    self.test_progress_text.setText(progress_text)
                    
                    # 使用可用的耗时字段
                    duration = total_duration if total_duration > 0 else total_time
                    
                    # 累计总进度
                    total_completed += completed
                    total_items += total if total > 0 else 0
                    
                    # 格式化值
                    if isinstance(success_rate, (int, float)):
                        # 检查成功率是否已经是百分比形式（>1）或小数形式（<=1）
                        if success_rate <= 1:
                            success_rate_text = f"{success_rate * 100:.2f}%"
                        else:
                            success_rate_text = f"{success_rate:.2f}%"
                    else:
                        success_rate_text = str(success_rate)
                    avg_response_time_text = f"{avg_response_time:.2f}s" if isinstance(avg_response_time, (int, float)) else str(avg_response_time)
                    avg_generation_speed_text = f"{avg_generation_speed:.2f} 字符/秒" if isinstance(avg_generation_speed, (int, float)) else str(avg_generation_speed)
                    
                    # 格式化耗时
                    if isinstance(duration, (int, float)):
                        if duration < 60:
                            duration_text = f"{duration:.2f}秒"
                        elif duration < 3600:
                            minutes = int(duration / 60)
                            seconds = duration % 60
                            duration_text = f"{minutes}分{seconds:.2f}秒"
                        else:
                            hours = int(duration / 3600)
                            minutes = int((duration % 3600) / 60)
                            seconds = duration % 60
                            duration_text = f"{hours}时{minutes}分{seconds:.2f}秒"
                    else:
                        duration_text = str(duration)
                    
                    # 添加到结果表格
                    row = self.result_table.rowCount()
                    self.result_table.insertRow(row)
                    
                    # 设置表格内容
                    session_id = self.test_task_id if hasattr(self, 'test_task_id') else "未知会话"
                    
                    # 直接使用session_id，不再需要格式转换
                    # 因为session_id已经是用户友好的格式了: MM-DD-HH-MM-xxxx
                    
                    self.result_table.setItem(row, 0, QTableWidgetItem(session_id))  # 会话ID
                    self.result_table.setItem(row, 1, QTableWidgetItem(dataset_name))  # 数据集名称
                    self.result_table.setItem(row, 2, QTableWidgetItem(f"{completed}/{total}"))  # 成功完成/总数
                    self.result_table.setItem(row, 3, QTableWidgetItem(success_rate_text))
                    
                    # 在结果表格中添加失败信息（如果有）
                    if failed_count > 0:
                        self.result_table.setItem(row, 4, QTableWidgetItem(f"{avg_response_time_text} (失败: {failed_count})"))  # 平均响应时间+失败数
                    else:
                        self.result_table.setItem(row, 4, QTableWidgetItem(avg_response_time_text))  # 平均响应时间
                        
                    self.result_table.setItem(row, 5, QTableWidgetItem(avg_generation_speed_text))  # 平均生成速度
                    
                    # 计算总字符数（如果可用）
                    total_chars = dataset_stats.get('total_chars', 0)
                    self.result_table.setItem(row, 6, QTableWidgetItem(str(total_chars)))  # 总字符数
                    
                    self.result_table.setItem(row, 7, QTableWidgetItem(duration_text))  # 总时间
                    
                    # 平均TPS（如果可用）
                    avg_tps = dataset_stats.get('output_tps', dataset_stats.get('avg_tps', 0))  # 优先使用输出TPS，如果没有则用平均TPS
                    self.result_table.setItem(row, 8, QTableWidgetItem(f"{avg_tps:.2f}"))  # 平均输出TPS
                
                # 计算总进度百分比
                if total_items > 0:
                    percentage = int((total_completed / total_items) * 100)
                    # 更新进度条
                    self.progress_bar.setValue(percentage)
                    # 更新进度文本
                    self.status_label.setText(f"进度: {percentage}% (成功完成: {total_completed}/{total_items})")
                    
                    # 更新详细信息
                    detail_text = f"成功完成测试项: {total_completed}/{total_items}\n"
                    detail_text += f"状态: {status}\n"
                    self.status_label.setText(detail_text)
            
            # 处理可能的错误信息
            if "error" in progress_data:
                error_msg = progress_data["error"]
                self.error_text.append(f"错误: {error_msg}")
            
            # 确保UI更新
            QApplication.processEvents()
            
        except Exception as e:
            logger.error(f"处理进度更新时出错: {str(e)}")
            self.error_text.append(f"处理进度更新错误: {str(e)}")

    def _handle_result_upload(self, result):
        """
        处理测试结果上传
        
        Args:
            result: 上传/加密结果
        """
        try:
            # 如果result是None，表示加密或上传过程被中断
            if result is None:
                QMessageBox.warning(self, "操作已取消", "加密或上传过程已取消。")
                return
            
            status = result.get("status", "error")
            
            if status == "success":
                # 成功
                ui_message = result.get("ui_message", "操作成功")
                ui_detail = result.get("ui_detail", "")
                
                # 显示成功对话框
                success_dialog = QMessageBox(self)
                success_dialog.setWindowTitle(ui_message)
                success_dialog.setText(ui_detail)
                success_dialog.setIcon(QMessageBox.Icon.Information)
                
                # 如果是离线模式的加密成功，添加一个"打开文件位置"按钮
                if "encrypted_path" in result:
                    encrypted_path = result.get("encrypted_path", "")
                    if encrypted_path and os.path.exists(encrypted_path):
                        # 添加打开文件位置的按钮
                        open_button = success_dialog.addButton("打开保存位置", QMessageBox.ButtonRole.ActionRole)
                        success_dialog.setDefaultButton(open_button)
                        
                        # 显示对话框
                        success_dialog.exec()
                        
                        # 如果点击了打开按钮
                        if success_dialog.clickedButton() == open_button:
                            # 打开文件所在目录
                            dir_path = os.path.dirname(encrypted_path)
                            
                            try:
                                # 根据平台选择打开方式
                                if platform.system() == "Windows":
                                    os.startfile(dir_path)
                                elif platform.system() == "Darwin":  # macOS
                                    subprocess.Popen(["open", dir_path])
                                else:  # Linux
                                    subprocess.Popen(["xdg-open", dir_path])
                            except Exception as e:
                                logger.error(f"无法打开目录: {str(e)}")
                                QMessageBox.warning(self, "警告", f"无法打开保存位置: {str(e)}")
                    else:
                        # 普通显示
                        success_dialog.exec()
                else:
                    # 普通显示
                    success_dialog.exec()
                
            else:
                # 失败
                ui_message = result.get("ui_message", "操作失败")
                ui_detail = result.get("ui_detail", "未知错误")
                error_msg = result.get("message", "未知错误")
                
                # 创建错误对话框
                error_dialog = QMessageBox(self)
                error_dialog.setWindowTitle(ui_message)
                error_dialog.setText(ui_detail)
                if error_msg:
                    error_dialog.setDetailedText(error_msg)
                error_dialog.setIcon(QMessageBox.Icon.Critical)
                
                # 如果可以重试
                if result.get("can_retry", False):
                    retry_button = error_dialog.addButton("重试", QMessageBox.ButtonRole.AcceptRole)
                    cancel_button = error_dialog.addButton("取消", QMessageBox.ButtonRole.RejectRole)
                    error_dialog.setDefaultButton(retry_button)
                    
                    # 显示对话框
                    error_dialog.exec()
                    
                    # 如果点击了重试按钮
                    if error_dialog.clickedButton() == retry_button:
                        # 重试加密和上传过程
                        should_upload = self.test_mode == 0
                        logger.info(f"重试加密和上传过程，是否上传: {should_upload}")
                        
                        # 创建结果处理线程
                        self.result_worker = ResultWorker(self.test_mode, benchmark_integration, should_upload)
                        self.result_worker.progress_updated.connect(self._on_encryption_progress)
                        self.result_worker.finished_signal.connect(self._on_encryption_finished)
                        self.result_worker.error_signal.connect(self._on_encryption_error)
                        
                        # 启动加密和上传过程
                        self.result_worker.start()
                        return
                else:
                    # 普通显示
                    error_dialog.exec()
        except Exception as e:
            logger.error(f"显示上传/加密结果时出错: {str(e)}")
            QMessageBox.critical(self, "错误", f"显示结果时出错: {str(e)}")

    def on_test_error(self, error_msg):
        """
        处理测试错误事件
        
        Args:
            error_msg: 错误信息
        """
        try:
            # 更新UI状态
            self.is_testing = False
            self.update_ui_buttons()
            
            # 更新状态标签
            self.status_label.setText("测试状态: 出错")
            
            # 更新测试状态指示器
            self.test_status_label.setText("出错")
            self.test_status_label.setStyleSheet("color: red; font-weight: bold;")
            
            # 在错误文本框中显示错误信息
            self.error_text.append(f"测试出错: {error_msg}")
            
            # 显示错误对话框
            QMessageBox.critical(self, "测试错误", f"测试过程中出错: {error_msg}")
            
            # 记录错误日志
            logger.error(f"测试出错: {error_msg}")
        except Exception as e:
            logger.error(f"处理测试错误事件时出错: {str(e)}")
            QMessageBox.critical(self, "错误", f"处理测试错误事件时出错: {str(e)}")

    def _get_framework_info(self):
        """
        通过SSH连接到GPU服务器获取框架信息
        """
        try:
            logger.info("开始获取框架信息...")
            import paramiko
            
            # 创建SSH客户端
            ssh = paramiko.SSHClient()
            ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            
            try:
                # 连接到GPU服务器
                logger.info("正在连接GPU服务器...")
                ssh.connect('10.255.0.75', username='root', password='P@$$2023?!')
                logger.info("GPU服务器连接成功")
                
                # 步骤1: 获取所有GPU进程
                logger.info("执行nvidia-smi pmon命令...")
                stdin, stdout, stderr = ssh.exec_command('nvidia-smi pmon -c 1')
                pmon_output = stdout.read().decode()
                logger.debug(f"nvidia-smi输出: {pmon_output}")
                
                # 解析输出找到所有GPU进程
                gpu_pids = []
                for line in pmon_output.split('\n'):
                    if line and not line.startswith('#') and not line.startswith('GPU'):
                        parts = line.split()
                        if len(parts) >= 2:  # 确保有足够的列以获取PID
                            pid = parts[1]
                            command = parts[-1] if len(parts) > 2 else ""
                            gpu_pids.append((pid, command))
                
                if not gpu_pids:
                    logger.warning("未找到GPU进程")
                    return None
                
                logger.info(f"找到GPU进程: {gpu_pids}")
                
                # 步骤2: 检查进程名称，直接识别已知框架
                for pid, command in gpu_pids:
                    if command.lower() == "ollama":
                        logger.info(f"检测到Ollama进程: {pid}")
                        return {
                            'framework': 'Ollama',
                            'pid': pid
                        }
                    elif "llama.cpp" in command.lower() or "llama-cpp" in command.lower():
                        logger.info(f"检测到llama.cpp进程: {pid}")
                        return {
                            'framework': 'llama.cpp',
                            'pid': pid
                        }
                
                # 步骤3: 对于Python进程，获取详细信息和父进程
                for pid, command in gpu_pids:
                    if "python" in command.lower():
                        logger.info(f"检测到Python进程: {pid}，获取详细信息")
                        
                        # 获取进程详细信息
                        stdin, stdout, stderr = ssh.exec_command(f'ps -ef | grep {pid}')
                        ps_output = stdout.read().decode()
                        logger.debug(f"进程{pid}详细信息: {ps_output}")
                        
                        # 分析进程命令行
                        for line in ps_output.split('\n'):
                            if str(pid) in line and 'grep' not in line:
                                logger.debug(f"分析命令行: {line}")
                                
                                # 检查命令行是否包含框架信息
                                cmd_lower = line.lower()
                                if 'vllm' in cmd_lower:
                                    logger.info(f"从命令行检测到vLLM框架: {pid}")
                                    return self._parse_vllm_info(line)
                                elif 'sglang' in cmd_lower:
                                    logger.info(f"从命令行检测到SGLang框架: {pid}")
                                    return {
                                        'framework': 'SGLang',
                                        'raw_command': line.strip(),
                                        'pid': pid
                                    }
                                
                                # 如果直接检查命令行没找到，获取父进程
                                parent_pid = None
                                parts = line.split()
                                if len(parts) >= 3:
                                    parent_pid = parts[2]
                                    logger.info(f"获取进程{pid}的父进程: {parent_pid}")
                                    
                                    if parent_pid and parent_pid != "1":
                                        stdin, stdout, stderr = ssh.exec_command(f'ps -ef | grep {parent_pid}')
                                        parent_output = stdout.read().decode()
                                        logger.debug(f"父进程{parent_pid}详细信息: {parent_output}")
                                        
                                        # 分析父进程命令行
                                        for parent_line in parent_output.split('\n'):
                                            if str(parent_pid) in parent_line and 'grep' not in parent_line:
                                                parent_cmd_lower = parent_line.lower()
                                                
                                                if 'vllm' in parent_cmd_lower:
                                                    logger.info(f"从父进程命令行检测到vLLM框架: {parent_pid}")
                                                    return self._parse_vllm_info(parent_line)
                                                elif 'sglang' in parent_cmd_lower:
                                                    logger.info(f"从父进程命令行检测到SGLang框架: {parent_pid}")
                                                    return {
                                                        'framework': 'SGLang',
                                                        'raw_command': parent_line.strip(),
                                                        'pid': parent_pid
                                                    }
                
                # 如果未能识别框架，返回None
                logger.warning("未能识别框架类型")
                return None
                
            except Exception as e:
                logger.error(f"执行SSH命令失败: {str(e)}")
                return None
            
            finally:
                ssh.close()
                logger.info("SSH连接已关闭")
                
        except Exception as e:
            logger.error(f"获取框架信息时出错: {str(e)}")
            return None
    
    def _parse_vllm_info(self, cmd_line):
        """
        解析vLLM命令行，提取模型信息
        """
        try:
            import shlex
            
            framework_info = {
                'framework': 'vLLM',
                'raw_command': cmd_line.strip()
            }
            
            # 解析命令行参数
            args = shlex.split(cmd_line)
            for i, arg in enumerate(args):
                if i + 1 < len(args):
                    if arg == '--model':
                        framework_info['model_path'] = args[i + 1]
                    elif arg == '--served-model-name':
                        framework_info['model_name'] = args[i + 1]
                    elif arg == '--dtype':
                        framework_info['dtype'] = args[i + 1]
                    elif arg == '--gpu-memory-utilization':
                        try:
                            framework_info['gpu_mem_util'] = float(args[i + 1])
                        except:
                            framework_info['gpu_mem_util'] = args[i + 1]
                    elif arg == '--max-model-len':
                        try:
                            framework_info['max_seq_len'] = int(args[i + 1])
                        except:
                            framework_info['max_seq_len'] = args[i + 1]
            
            return framework_info
            
        except Exception as e:
            logger.error(f"解析vLLM信息失败: {str(e)}")
            return {
                'framework': 'vLLM',
                'raw_command': cmd_line.strip(),
                'error': str(e)
            }

    def _show_model_info_dialog(self, framework_info):
        """显示模型信息输入对话框"""
        try:
            dialog = QDialog(self)
            dialog.setWindowTitle("模型信息")
            dialog.setMinimumWidth(500)
            
            layout = QFormLayout(dialog)
            
            # 框架信息部分
            framework_section = QGroupBox("框架信息")
            framework_layout = QFormLayout()
            
            # 框架类型设置
            framework_combo = QComboBox()
            framework_options = ["Ollama", "llama.cpp", "vLLM", "SGLang", "Xinference", "赤兔", "其他"]
            framework_combo.addItems(framework_options)
            
            # 框架命令行展示
            cmd_text = QTextEdit()
            cmd_text.setReadOnly(True)
            cmd_text.setMaximumHeight(60)
            
            # 根据检测到的框架信息自动填充
            detected_framework = None
            if framework_info and isinstance(framework_info, dict):
                framework_name = framework_info.get('framework', '')
                logger.info(f"显示框架信息: {framework_name}")
                
                if framework_name:
                    detected_framework = framework_name
                    for i, option in enumerate(framework_options):
                        if option.lower() == framework_name.lower():
                            framework_combo.setCurrentIndex(i)
                            break
                
                # 显示原始命令
                if 'raw_command' in framework_info:
                    cmd_text.setPlainText(framework_info['raw_command'])
                
                # 如果是vLLM，显示额外信息
                if framework_name == 'vLLM' and 'model_name' in framework_info:
                    model_info_text = f"模型名称: {framework_info.get('model_name', '')}\n"
                    if 'dtype' in framework_info:
                        model_info_text += f"数据类型: {framework_info.get('dtype', '')}\n"
                    if 'gpu_mem_util' in framework_info:
                        model_info_text += f"GPU内存使用率: {framework_info.get('gpu_mem_util', '')}\n"
                    if 'max_seq_len' in framework_info:
                        model_info_text += f"最大序列长度: {framework_info.get('max_seq_len', '')}\n"
                    cmd_text.setPlainText(model_info_text)
            
            # 添加框架选择和命令显示到布局
            detected_label = QLabel(f"检测到的框架: {detected_framework if detected_framework else '未检测到'}")
            framework_layout.addRow(detected_label)
            framework_layout.addRow("框架类型:", framework_combo)
            framework_layout.addRow("框架详情:", cmd_text)
            framework_section.setLayout(framework_layout)
            layout.addRow(framework_section)
            
            # 模型信息部分
            model_section = QGroupBox("模型信息")
            model_layout = QFormLayout()
            
            # 从数据库获取当前选中的模型配置
            model_config = self.get_selected_model()
            
            # 模型名称（不可编辑）
            model_name = model_config.get("model", "") if model_config else ""
            model_name_input = QLineEdit(model_name)
            model_name_input.setReadOnly(True)
            model_layout.addRow("模型名称:", model_name_input)
            
            # 参数量输入
            params_input = QLineEdit()
            if model_config and "params" in model_config:
                params_input.setText(str(model_config["params"]))
            model_layout.addRow("参数量(B):", params_input)
            
            # 量化方式选择
            quant_combo = QComboBox()
            quant_options = ["FP32", "FP16", "INT8", "INT4"]
            quant_combo.addItems(quant_options)
            
            # 如果检测到了vLLM且有dtype信息，自动选择量化方式
            if detected_framework == 'vLLM' and framework_info and 'dtype' in framework_info:
                dtype = framework_info['dtype'].lower()
                if dtype == 'float16' or dtype == 'half':
                    quant_combo.setCurrentText("FP16")
                elif dtype == 'float32':
                    quant_combo.setCurrentText("FP32")
                elif dtype == 'int8':
                    quant_combo.setCurrentText("INT8")
                elif dtype == 'int4':
                    quant_combo.setCurrentText("INT4")
            elif model_config and "quantization" in model_config:
                quant_combo.setCurrentText(model_config["quantization"])
            
            model_layout.addRow("量化方式:", quant_combo)
            model_section.setLayout(model_layout)
            layout.addRow(model_section)
            
            # 添加确定和取消按钮
            button_box = QDialogButtonBox(
                QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
            )
            button_box.accepted.connect(dialog.accept)
            button_box.rejected.connect(dialog.reject)
            layout.addRow(button_box)
            
            if dialog.exec() == QDialog.DialogCode.Accepted:
                return {
                    "framework": framework_combo.currentText(),
                    "model_name": model_name,
                    "params": float(params_input.text()) if params_input.text() else None,
                    "quantization": quant_combo.currentText()
                }
            return None
            
        except Exception as e:
            logger.error(f"显示模型信息对话框时出错: {str(e)}")
            return None

    def _on_encryption_progress(self, progress):
        """处理加密进度更新"""
        try:
            # 更新进度条
            self.progress_bar.setValue(progress)
            # 更新状态文本
            self.status_label.setText(f"加密进度: {progress}%")
        except Exception as e:
            logger.error(f"更新加密进度时出错: {str(e)}")
    
    def _on_encryption_finished(self, result):
        """处理加密完成"""
        try:
            # 重置进度条
            self.progress_bar.setValue(0)
            # 更新状态文本
            self.status_label.setText("就绪")
            # 处理加密结果
            self._handle_result_upload(result)
        except Exception as e:
            logger.error(f"处理加密完成时出错: {str(e)}")
            QMessageBox.critical(self, "错误", f"处理加密结果时出错: {str(e)}")
    
    def _on_encryption_error(self, error_msg):
        """处理加密错误"""
        try:
            # 重置进度条
            self.progress_bar.setValue(0)
            # 更新状态文本
            self.status_label.setText("加密失败")
            # 显示错误信息
            self.error_text.append(f"加密错误: {error_msg}")
            QMessageBox.critical(self, "加密错误", f"加密过程出错: {error_msg}")
        except Exception as e:
            logger.error(f"处理加密错误时出错: {str(e)}")
            QMessageBox.critical(self, "错误", f"处理加密错误时出错: {str(e)}")