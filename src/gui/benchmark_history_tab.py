"""
跑分历史记录标签页模块
"""
import os
import json
from datetime import datetime
from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QTableWidget,
    QTableWidgetItem,
    QPushButton,
    QLabel,
    QHeaderView,
    QMessageBox,
    QFileDialog,
    QGroupBox,
    QSplitter
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QFont
from src.utils.config import config
from src.utils.logger import setup_logger
from src.gui.i18n.language_manager import LanguageManager

# 设置日志记录器
logger = setup_logger("benchmark_history")


class BenchmarkHistoryTab(QWidget):
    """跑分历史记录标签页"""

    def __init__(self):
        super().__init__()
        
        # 获取语言管理器实例
        self.language_manager = LanguageManager()
        
        # 初始化成员变量
        self.result_dir = os.path.join(os.path.expanduser("~"), ".deepstressmodel", "benchmark_results")
        self.selected_result = None
        
        # 初始化界面
        self.init_ui()
        
        # 更新界面文本
        self.update_ui_text()
        
        # 加载历史记录
        self.load_history()
        
        # 连接语言变更信号
        self.language_manager.language_changed.connect(self.update_ui_text)
    
    def init_ui(self):
        """初始化UI"""
        main_layout = QVBoxLayout(self)
        
        # 创建水平分割器
        splitter = QSplitter(Qt.Orientation.Horizontal)
        
        # 左侧：历史记录表格
        history_panel = QWidget()
        history_layout = QVBoxLayout(history_panel)
        
        # 历史记录表格
        self.history_table = QTableWidget()
        self.history_table.setColumnCount(7)
        self.history_table.setHorizontalHeaderLabels([
            "测试时间", "数据集版本", "模型", "精度",
            "平均TPS", "平均延迟", "操作"
        ])
        self.history_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        self.history_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.history_table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.history_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.history_table.itemSelectionChanged.connect(self._on_selection_changed)
        history_layout.addWidget(self.history_table)
        
        # 按钮区域
        button_layout = QHBoxLayout()
        
        # 刷新按钮
        self.refresh_button = QPushButton("刷新")
        self.refresh_button.clicked.connect(self.load_history)
        button_layout.addWidget(self.refresh_button)
        
        # 导出按钮
        self.export_button = QPushButton("导出")
        self.export_button.clicked.connect(self._export_result)
        button_layout.addWidget(self.export_button)
        
        # 删除按钮
        self.delete_button = QPushButton("删除")
        self.delete_button.clicked.connect(self._delete_result)
        button_layout.addWidget(self.delete_button)
        
        # 上传按钮
        self.upload_button = QPushButton("上传")
        self.upload_button.clicked.connect(self._upload_result)
        button_layout.addWidget(self.upload_button)
        
        history_layout.addLayout(button_layout)
        
        # 右侧：详情面板
        detail_panel = QWidget()
        detail_layout = QVBoxLayout(detail_panel)
        
        # 详情标题
        self.detail_title = QLabel("详情")
        font = QFont()
        font.setPointSize(14)
        font.setBold(True)
        self.detail_title.setFont(font)
        detail_layout.addWidget(self.detail_title)
        
        # 基本信息
        basic_info = QGroupBox("基本信息")
        basic_layout = QVBoxLayout(basic_info)
        
        # 测试信息
        self.test_info = QLabel()
        self.test_info.setWordWrap(True)
        basic_layout.addWidget(self.test_info)
        
        # 系统信息
        self.system_info = QLabel()
        self.system_info.setWordWrap(True)
        basic_layout.addWidget(self.system_info)
        
        detail_layout.addWidget(basic_info)
        
        # 性能指标
        metrics_info = QGroupBox("性能指标")
        metrics_layout = QVBoxLayout(metrics_info)
        
        # 指标信息
        self.metrics_info = QLabel()
        self.metrics_info.setWordWrap(True)
        metrics_layout.addWidget(self.metrics_info)
        
        detail_layout.addWidget(metrics_info)
        
        # 添加弹性空间
        detail_layout.addStretch()
        
        # 添加左右面板到分割器
        splitter.addWidget(history_panel)
        splitter.addWidget(detail_panel)
        
        # 设置分割比例
        splitter.setSizes([500, 500])  # 左侧500像素，右侧500像素
        
        # 添加分割器到主布局
        main_layout.addWidget(splitter)
    
    def load_history(self):
        """加载历史记录"""
        # 清空表格
        self.history_table.setRowCount(0)
        
        # 确保结果目录存在
        if not os.path.exists(self.result_dir):
            os.makedirs(self.result_dir, exist_ok=True)
            return
        
        # 获取所有结果文件
        result_files = [f for f in os.listdir(self.result_dir) if f.endswith('.json')]
        result_files.sort(reverse=True)  # 按文件名倒序排列（最新的在前）
        
        # 加载结果
        for filename in result_files:
            filepath = os.path.join(self.result_dir, filename)
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    result = json.load(f)
                
                # 添加到表格
                row = self.history_table.rowCount()
                self.history_table.insertRow(row)
                
                # 测试时间
                start_time = datetime.fromisoformat(result.get('start_time', '')).strftime('%Y-%m-%d %H:%M:%S')
                self.history_table.setItem(row, 0, QTableWidgetItem(start_time))
                
                # 数据集版本
                self.history_table.setItem(row, 1, QTableWidgetItem(result.get('dataset_version', '')))
                
                # 模型
                self.history_table.setItem(row, 2, QTableWidgetItem(result.get('model', '')))
                
                # 精度
                self.history_table.setItem(row, 3, QTableWidgetItem(result.get('precision', '')))
                
                # 平均TPS
                metrics = result.get('metrics', {})
                tps = f"{metrics.get('throughput', 0):.2f}"
                self.history_table.setItem(row, 4, QTableWidgetItem(tps))
                
                # 平均延迟
                latency = f"{metrics.get('avg_latency', 0) * 1000:.2f} ms"
                self.history_table.setItem(row, 5, QTableWidgetItem(latency))
                
                # 操作按钮
                button_widget = QWidget()
                button_layout = QHBoxLayout(button_widget)
                button_layout.setContentsMargins(0, 0, 0, 0)
                
                view_button = QPushButton("查看")
                view_button.setProperty("filepath", filepath)
                view_button.clicked.connect(self._view_result)
                button_layout.addWidget(view_button)
                
                self.history_table.setCellWidget(row, 6, button_widget)
            except Exception as e:
                logger.error(f"加载结果文件失败: {filepath}, 错误: {str(e)}")
    
    def _on_selection_changed(self):
        """选择变更处理"""
        selected_items = self.history_table.selectedItems()
        if not selected_items:
            self._clear_detail()
            return
        
        # 获取选中行
        row = selected_items[0].row()
        
        # 获取操作按钮
        button_widget = self.history_table.cellWidget(row, 6)
        if not button_widget:
            self._clear_detail()
            return
        
        # 获取文件路径
        view_button = button_widget.findChild(QPushButton)
        if not view_button:
            self._clear_detail()
            return
        
        filepath = view_button.property("filepath")
        if not filepath or not os.path.exists(filepath):
            self._clear_detail()
            return
        
        # 加载结果
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                result = json.load(f)
            
            self.selected_result = result
            self._update_detail(result)
        except Exception as e:
            logger.error(f"加载结果文件失败: {filepath}, 错误: {str(e)}")
            self._clear_detail()
    
    def _view_result(self):
        """查看结果"""
        button = self.sender()
        if not button:
            return
        
        filepath = button.property("filepath")
        if not filepath or not os.path.exists(filepath):
            QMessageBox.warning(self, "错误", "结果文件不存在")
            return
        
        # 加载结果
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                result = json.load(f)
            
            self.selected_result = result
            self._update_detail(result)
        except Exception as e:
            logger.error(f"加载结果文件失败: {filepath}, 错误: {str(e)}")
            QMessageBox.warning(self, "错误", f"加载结果文件失败: {str(e)}")
    
    def _update_detail(self, result):
        """更新详情面板"""
        # 更新标题
        start_time = datetime.fromisoformat(result.get('start_time', '')).strftime('%Y-%m-%d %H:%M:%S')
        self.detail_title.setText(f"测试详情 - {start_time}")
        
        # 获取模型配置
        model_config = result.get('model_config', {})
        model_params = result.get('model_params', 0)
        
        model_info = ""
        if model_config:
            # 如果有详细的模型配置，显示更多信息
            model_info = f"""
            <b>模型:</b> {result.get('model', '')}<br>
            <b>参数量:</b> {model_params}B<br>
            <b>API类型:</b> {model_config.get('api_type', '未知')}<br>
            <b>端点:</b> {model_config.get('endpoint', '未知')}<br>
            <b>API密钥:</b> {'*' * 8 if model_config.get('api_key') else '未设置'}<br>
            """
        else:
            # 否则只显示基本信息
            model_info = f"""
            <b>模型:</b> {result.get('model', '')}<br>
            <b>参数量:</b> {model_params}B<br>
            """
        
        # 更新测试信息
        test_info = f"""
        <b>设备ID:</b> {result.get('device_id', '')}<br>
        <b>昵称:</b> {result.get('nickname', '')}<br>
        <b>数据集版本:</b> {result.get('dataset_version', '')}<br>
        {model_info}
        <b>精度:</b> {result.get('precision', '')}<br>
        <b>框架配置:</b> {result.get('framework_config', '')}<br>
        <b>测试时间:</b> {start_time}<br>
        <b>总用时:</b> {result.get('total_duration', 0):.2f} 秒
        """
        self.test_info.setText(test_info)
        
        # 更新系统信息
        system_info = result.get('system_info', {})
        gpu_info = system_info.get('gpu', [])
        gpu_text = ""
        for i, gpu in enumerate(gpu_info):
            gpu_text += f"<b>GPU {i+1}:</b> {gpu.get('name', '未知')} ({gpu.get('memory_total', 0)} MB)<br>"
        
        cpu_info = system_info.get('cpu', {})
        memory_info = system_info.get('memory', {})
        os_info = system_info.get('os', {})
        
        system_text = f"""
        {gpu_text}
        <b>CPU:</b> {cpu_info.get('model', '未知')} ({cpu_info.get('cores', 0)} 核 / {cpu_info.get('threads', 0)} 线程)<br>
        <b>内存:</b> {memory_info.get('total', 0) / (1024**3):.2f} GB<br>
        <b>操作系统:</b> {os_info.get('system', '未知')} {os_info.get('release', '')}
        """
        self.system_info.setText(system_text)
        
        # 更新性能指标
        metrics = result.get('metrics', {})
        metrics_text = f"""
        <b>平均延迟:</b> {metrics.get('avg_latency', 0) * 1000:.2f} ms<br>
        <b>吞吐量:</b> {metrics.get('throughput', 0):.2f} tokens/s<br>
        <b>字符生成速度:</b> {metrics.get('char_speed', 0):.2f} chars/s<br>
        <b>成功率:</b> {metrics.get('success_rate', 0) * 100:.2f}%
        """
        self.metrics_info.setText(metrics_text)
    
    def _clear_detail(self):
        """清空详情面板"""
        self.detail_title.setText("详情")
        self.test_info.setText("")
        self.system_info.setText("")
        self.metrics_info.setText("")
        self.selected_result = None
    
    def _export_result(self):
        """导出结果"""
        if not self.selected_result:
            QMessageBox.warning(self, "警告", "请先选择一个结果")
            return
        
        # 打开文件保存对话框
        filename = f"benchmark_{datetime.now().strftime('%Y%m%d%H%M%S')}.json"
        filepath, _ = QFileDialog.getSaveFileName(
            self, "导出结果", filename, "JSON文件 (*.json)"
        )
        
        if not filepath:
            return
        
        # 保存结果
        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(self.selected_result, f, ensure_ascii=False, indent=2)
            
            QMessageBox.information(self, "成功", f"结果已导出到: {filepath}")
        except Exception as e:
            logger.error(f"导出结果失败: {str(e)}")
            QMessageBox.warning(self, "错误", f"导出结果失败: {str(e)}")
    
    def _delete_result(self):
        """删除结果"""
        selected_items = self.history_table.selectedItems()
        if not selected_items:
            QMessageBox.warning(self, "警告", "请先选择一个结果")
            return
        
        # 获取选中行
        row = selected_items[0].row()
        
        # 获取操作按钮
        button_widget = self.history_table.cellWidget(row, 6)
        if not button_widget:
            return
        
        # 获取文件路径
        view_button = button_widget.findChild(QPushButton)
        if not view_button:
            return
        
        filepath = view_button.property("filepath")
        if not filepath or not os.path.exists(filepath):
            QMessageBox.warning(self, "错误", "结果文件不存在")
            return
        
        # 确认删除
        reply = QMessageBox.question(
            self, "确认删除", "确定要删除这个结果吗？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        
        if reply != QMessageBox.StandardButton.Yes:
            return
        
        # 删除文件
        try:
            os.remove(filepath)
            self.history_table.removeRow(row)
            self._clear_detail()
            QMessageBox.information(self, "成功", "结果已删除")
        except Exception as e:
            logger.error(f"删除结果失败: {str(e)}")
            QMessageBox.warning(self, "错误", f"删除结果失败: {str(e)}")
    
    def _upload_result(self):
        """上传结果"""
        if not self.selected_result:
            QMessageBox.warning(self, "警告", "请先选择一个结果")
            return
        
        # 确认上传
        reply = QMessageBox.question(
            self, "确认上传", "确定要上传这个结果到排行榜吗？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        
        if reply != QMessageBox.StandardButton.Yes:
            return
        
        # 模拟上传逻辑
        QMessageBox.information(self, "成功", "结果已上传到排行榜")
    
    def update_ui_text(self):
        """更新UI文本"""
        # 更新表格标题
        self.history_table.setHorizontalHeaderLabels([
            self.tr("test_time"),
            self.tr("dataset_version"),
            self.tr("model"),
            self.tr("precision"),
            self.tr("avg_tps"),
            self.tr("avg_latency"),
            self.tr("operations")
        ])
        
        # 更新按钮文本
        self.refresh_button.setText(self.tr("refresh"))
        self.export_button.setText(self.tr("export"))
        self.delete_button.setText(self.tr("delete"))
        self.upload_button.setText(self.tr("upload"))
        
        # 更新详情标题
        if self.selected_result:
            start_time = datetime.fromisoformat(self.selected_result.get('start_time', '')).strftime('%Y-%m-%d %H:%M:%S')
            self.detail_title.setText(f"{self.tr('detail')} - {start_time}")
        else:
            self.detail_title.setText(self.tr("detail"))
    
    def tr(self, key):
        """翻译文本"""
        return self.language_manager.get_text(key) 