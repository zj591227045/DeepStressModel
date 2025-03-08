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
    QMenu,
    QRadioButton,
    QButtonGroup)
from PyQt6.QtCore import Qt, QTimer, QThread, pyqtSignal
from PyQt6.QtGui import QFont, QAction
from typing import List, Dict
from src.utils.config import config
from src.utils.logger import setup_logger
from src.monitor.gpu_monitor import gpu_monitor
from src.engine.test_manager import TestManager, TestTask, TestProgress
from src.engine.api_client import APIResponse
from src.data.test_datasets import DATASETS
from src.data.db_manager import db_manager
from src.data.dataset_manager import DatasetManager
from src.gui.results_tab import ResultsTab
from src.gui.i18n.language_manager import LanguageManager
from src.gui.widgets.gpu_monitor import GPUMonitorWidget
from src.gui.widgets.test_info import TestInfoWidget
from src.gui.widgets.test_progress import TestProgressWidget
from src.gui.widgets.test_thread import TestThread
from src.gui.widgets.dataset_list_item import DatasetListItem
from src.gui.widgets.test_records_manager import TestRecordsManager
from src.gui.widgets.test_executor import TestExecutor

# 设置日志记录器
logger = setup_logger("test_tab")


class TestTab(QWidget):
    """测试标签页"""

    def __init__(self):
        super().__init__()
        
        # 获取语言管理器实例
        self.language_manager = LanguageManager()
        
        # 初始化测试记录管理器
        self.records_manager = TestRecordsManager()
        
        # 初始化测试执行器
        self.test_executor = TestExecutor()
        
        # 初始化成员变量
        self.test_task_id = None
        self.model_config = None
        self.selected_datasets = {}
        self.test_manager = TestManager()  # 添加test_manager实例
        
        # 初始化界面
        self.init_ui()
        
        # 更新界面文本
        self.update_ui_text()
        
        # 加载数据集和模型
        self.load_datasets()
        self.load_models()
        
        # 初始化API调用方式
        self._init_api_call_mode()
        
        # 连接语言变更信号
        self.language_manager.language_changed.connect(self.update_ui_text)
        
        # 连接测试管理器的信号
        self.test_manager.progress_updated.connect(self._on_progress_updated)
        
        # 连接测试执行器的信号
        self.test_executor.progress_updated.connect(self._on_progress_updated)
        self.test_executor.result_received.connect(self._on_result_received)
        self.test_executor.test_finished.connect(self._on_test_finished)
        self.test_executor.test_error.connect(self._on_test_error)
        
        logger.info("已连接进度更新信号")
        
        # 启动GPU监控
        self.gpu_monitor.start_monitoring()
    
    def __del__(self):
        """析构函数，确保在对象销毁时停止所有线程"""
        try:
            # 停止GPU监控线程
            if hasattr(self, 'gpu_monitor'):
                self.gpu_monitor.stop_monitoring()
            
            # 停止测试线程
            if hasattr(self, 'test_thread') and self.test_thread and self.test_thread.isRunning():
                self.test_thread.quit()
                self.test_thread.wait(1000)  # 等待最多1秒
        except Exception as e:
            logger.error(f"停止线程时出错: {e}")
    
    def closeEvent(self, event):
        """窗口关闭事件处理"""
        try:
            # 停止GPU监控线程
            if hasattr(self, 'gpu_monitor'):
                self.gpu_monitor.stop_monitoring()
            
            # 停止测试线程
            if hasattr(self, 'test_thread') and self.test_thread and self.test_thread.isRunning():
                self.test_thread.quit()
                self.test_thread.wait(1000)  # 等待最多1秒
        except Exception as e:
            logger.error(f"关闭窗口时停止线程出错: {e}")
        
        # 调用父类的 closeEvent
        super().closeEvent(event)
    
    def _init_api_call_mode(self):
        """初始化API调用方式"""
        # 从配置读取默认值，如果没有配置，则强制设置为流式输出(True)
        is_stream_mode = config.get('openai_api.stream_mode', True)
        
        # 确保流式输出为默认值
        if not is_stream_mode:
            is_stream_mode = True
            config.set('openai_api.stream_mode', True)
            logger.info("已将API调用方式默认设置为流式输出")
        
        # 设置单选按钮状态
        if is_stream_mode:
            self.stream_mode_radio.setChecked(True)
        else:
            self.direct_mode_radio.setChecked(True)
    
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
        self.api_call_mode_label.setText(self.tr('api_call_mode'))
        self.stream_mode_radio.setText(self.tr('stream_output'))
        self.direct_mode_radio.setText(self.tr('direct_output'))
        
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
            self.records_manager.clear_test_state()
            
            logger.debug("测试状态已清除")
            
        except Exception as e:
            logger.error(f"清除测试状态失败: {e}", exc_info=True)
    
    def _sync_test_records(self):
        """同步测试记录到结果标签页"""
        try:
            # 查找结果标签页
            results_tab = self._find_results_tab()
            
            # 使用记录管理器同步测试记录
            self.records_manager.sync_test_records(results_tab)
                
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
        
        # 添加API调用方式选择器
        self.api_call_mode_label = QLabel()
        self.api_call_mode_label.setText(self.tr('api_call_mode'))
        concurrency_layout.addWidget(self.api_call_mode_label)
        
        self.api_call_mode_group = QButtonGroup(self)
        self.stream_mode_radio = QRadioButton(self.tr('stream_output'))
        self.direct_mode_radio = QRadioButton(self.tr('direct_output'))
        self.stream_mode_radio.setChecked(True)  # 默认选择流式输出
        self.api_call_mode_group.addButton(self.stream_mode_radio)
        self.api_call_mode_group.addButton(self.direct_mode_radio)
        
        api_mode_layout = QHBoxLayout()
        api_mode_layout.addWidget(self.stream_mode_radio)
        api_mode_layout.addWidget(self.direct_mode_radio)
        concurrency_layout.addLayout(api_mode_layout)
        
        # 连接信号
        self.api_call_mode_group.buttonClicked.connect(self._on_api_call_mode_changed)
        
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
                self.gpu_monitor.refresh_servers()
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
                logger.info("数据集 " + dataset['name'] + " 初始化完成，默认权重: " + str(dataset.get('weight', 1)))
                
                # 创建列表项
                list_item = QListWidgetItem(self.dataset_list)
                self.dataset_list.addItem(list_item)
                
                # 创建数据集列表项
                logger.info("创建数据集列表项: " + dataset['name'])
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
                    logger.info("添加数据集: " + dataset_name + ", prompts数量: " + str(len(prompts)) + ", 权重: " + str(weight))
            
            logger.info("最终选中的数据集: " + str(list(selected_datasets.keys())))
            return selected_datasets
            
        except Exception as e:
            logger.error(f"获取选中数据集失败: {e}")
            QMessageBox.critical(self, "错误", f"获取选中数据集失败：{e}")
            return {}
    
    def start_test(self):
        """开始测试"""
        try:
            # 检查是否已经在运行
            if self.test_executor.is_test_running():
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
            self.test_task_id = test_task_id
            
            # 获取并发设置
            total_concurrency = self.concurrency_spinbox.value()
            logger.info(f"设置的总并发数: {total_concurrency}")
            
            # 初始化测试记录
            records = self.records_manager.init_test_records(
                test_task_id, model_config, selected_datasets, total_concurrency)
            
            # 计算总权重
            total_weight = sum(
                weight for _,
                weight in selected_datasets.values())
            logger.info(f"总权重: {total_weight}")
            
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
            
            # 更新UI状态
            self.start_btn.setEnabled(False)
            self.stop_btn.setEnabled(True)
            self.info_widget.clear()
            
            # 初始化每个数据集的显示状态
            for dataset_name, dataset_stats in records["datasets"].items():
                self.info_widget.update_dataset_info(
                    dataset_name, dataset_stats)
            
            # 启动测试
            success = self.test_executor.start_test(
                model_config["name"],
                tasks,
                test_task_id
            )
            
            if not success:
                QMessageBox.critical(self, "错误", "启动测试失败")
                self._clear_test_state()
                return
            
            logger.info("测试线程开始运行")
            
        except Exception as e:
            logger.error(f"启动测试失败: {e}", exc_info=True)
            QMessageBox.critical(self, "错误", f"启动测试失败: {e}")
            self._clear_test_state()
    
    def stop_test(self):
        """停止测试"""
        try:
            if not self.test_executor.is_test_running():
                logger.warning("没有正在运行的测试")
                return
            
            # 停止测试
            self.test_executor.stop_test()
            
            # 更新UI状态
            self.progress_widget.status_label.setText("状态: 已停止")
            self.progress_widget.status_label.setStyleSheet(
                "font-weight: bold; color: red;")
            self.start_btn.setEnabled(True)
            self.stop_btn.setEnabled(False)
            
            logger.info("测试已手动停止")
        except Exception as e:
            logger.error(f"停止测试失败: {e}", exc_info=True)
    
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
            status_text = self.tr('completed') + ": " + str(completed) + "/" + str(total)
            self.progress_widget.status_label.setText(status_text)
            
            # 更新统计信息
            current_records = self.records_manager.current_test_records
            if current_records:
                current_records["successful_tasks"] = progress.successful_tasks
                current_records["failed_tasks"] = progress.failed_tasks
                
                # 只在每10个任务完成时同步一次记录
                if completed % 10 == 0:
                    self._sync_test_records()
            
            # 更新详细信息
            detail_text = ""
            # 添加测试任务ID
            detail_text += self.tr('test_task_id') + ": " + progress.test_task_id + "\n"
            
            # 添加完成情况
            detail_text += self.tr('completed') + ": " + str(completed) + "/" + str(total) + "\n"
            
            # 添加成功率
            if total > 0:
                success_rate = (progress.successful_tasks / total) * 100
                detail_text += self.tr('success_rate') + f": {success_rate:.1f}%\n"
            
            # 添加平均响应时间
            detail_text += self.tr('avg_response_time') + f": {progress.avg_response_time:.2f}s\n"
            
            # 添加平均生成速度
            detail_text += self.tr('avg_generation_speed') + f": {progress.avg_generation_speed:.1f}字/秒\n"
            
            # 添加当前速度
            detail_text += self.tr('current_speed') + f": {progress.current_speed:.1f}字/秒\n"
            
            # 添加平均TPS
            detail_text += self.tr('avg_tps') + f": {progress.avg_tps:.1f}\n"
            
            # 添加最后一次错误信息
            if progress.last_error:
                detail_text += self.tr('last_error') + ": " + progress.last_error
            
            self.progress_widget.detail_text.setText(detail_text)
            
        except Exception as e:
            logger.error(f"更新进度时出错: {e}", exc_info=True)

    def _on_test_finished(self):
        """测试完成处理"""
        try:
            # 获取当前测试记录
            current_records = self.records_manager.current_test_records
            if not current_records:
                return
            
            # 更新测试状态
            current_records["status"] = "completed"
            
            # 更新UI状态
            self.progress_widget.status_label.setText("状态: 已完成")
            self.progress_widget.status_label.setStyleSheet(
                "font-weight: bold; color: green;")
            self.progress_widget.progress_bar.setValue(100)
            self.start_btn.setEnabled(True)
            self.stop_btn.setEnabled(False)
            
            # 同步测试记录
            self._sync_test_records()
            
            logger.info("测试已完成")
            
        except Exception as e:
            logger.error(f"处理测试完成时出错: {e}", exc_info=True)
    
    def _on_test_error(self, error_msg: str):
        """测试错误处理"""
        try:
            # 获取当前测试记录
            current_records = self.records_manager.current_test_records
            if not current_records:
                return
            
            # 更新测试状态
            current_records["status"] = "error"
            
            # 更新UI状态
            self.progress_widget.status_label.setText(f"状态: 错误 - {error_msg}")
            self.progress_widget.status_label.setStyleSheet(
                "font-weight: bold; color: red;")
            self.start_btn.setEnabled(True)
            self.stop_btn.setEnabled(False)
            
            # 添加错误信息
            self.info_widget.add_error(error_msg)
            
            # 同步测试记录
            self._sync_test_records()
            
            logger.error(f"测试出错: {error_msg}")
            
        except Exception as e:
            logger.error(f"处理测试错误时出错: {e}", exc_info=True)

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
            # 获取当前测试记录
            current_records = self.records_manager.current_test_records
            if not current_records:
                return
            
            dataset_stats = current_records["datasets"].get(dataset_name)
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
                current_records["successful_tasks"] += 1
                current_records["total_tokens"] += response.total_tokens
                current_records["total_chars"] += response.total_chars
                
                # 计算总体实际耗时和平均值
                current_time = time.time()
                current_records["total_time"] = current_time - \
                    current_records["start_time"]
                
                if current_records["successful_tasks"] > 0:
                    if current_records["total_time"] > 0:
                        # 考虑总并发数计算总体平均生成速度
                        current_records["avg_generation_speed"] = (
                            current_records["total_chars"] / 
                            current_records["total_time"] / 
                            current_records["concurrency"]  # 除以总并发数
                        )
                        # 当前速度仍然使用单次响应的速度
                        current_records["current_speed"] = (
                            response.total_chars / response.duration
                            if response.duration > 0 else 0
                        )
                        # 考虑总并发数计算总体TPS
                        current_records["avg_tps"] = (
                            current_records["total_tokens"] / 
                            current_records["total_time"] / 
                            current_records["concurrency"]  # 除以总并发数
                        )
            else:
                dataset_stats["failed"] += 1
                current_records["failed_tasks"] += 1
            
            # 更新信息显示
            self.info_widget.update_dataset_info(dataset_name, dataset_stats)
            
        except Exception as e:
            # 只记录错误，不影响测试继续进行
            logger.error(f"处理测试结果时出错: {e}")

    def _on_dataset_clicked(self, item):
        """处理数据集列表项的点击事件"""
        # 切换选择状态
        item.setSelected(not item.isSelected())

    def _on_api_call_mode_changed(self, button):
        """当API调用方式改变时"""
        is_stream_mode = button == self.stream_mode_radio
        config.set('openai_api.stream_mode', is_stream_mode)
        
        # 打印配置以便验证
        current_value = config.get('openai_api.stream_mode', None)
        logger.info(f"API调用方式已更改为: {'流式输出' if is_stream_mode else '直接输出'}")
        logger.info(f"当前配置值: openai_api.stream_mode = {current_value}")
