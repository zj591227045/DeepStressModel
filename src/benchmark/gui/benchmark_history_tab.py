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
    QGroupBox,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QMessageBox,
    QFileDialog,
    QSplitter
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont
from src.utils.logger import setup_logger

# 设置日志记录器
logger = setup_logger("benchmark_history_tab")

class BenchmarkHistoryTab(QWidget):
    """跑分历史记录标签页"""

    def __init__(self):
        super().__init__()
        
        # 初始化成员变量
        self.result_dir = os.path.join(os.getcwd(), "data", "benchmark", "results")
        self.results = []
        
        # 初始化界面
        self.init_ui()
        
        # 加载历史记录
        self.load_history()
        
        logger.info("跑分历史记录标签页初始化完成")
    
    def init_ui(self):
        """初始化界面"""
        # 创建主布局
        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(10)
        
        # 创建控制按钮组
        control_layout = QHBoxLayout()
        
        self.refresh_button = QPushButton("刷新")
        self.refresh_button.clicked.connect(self.load_history)
        control_layout.addWidget(self.refresh_button)
        
        self.export_button = QPushButton("导出")
        self.export_button.clicked.connect(self.export_result)
        control_layout.addWidget(self.export_button)
        
        self.delete_button = QPushButton("删除")
        self.delete_button.clicked.connect(self.delete_result)
        control_layout.addWidget(self.delete_button)
        
        control_layout.addStretch()
        main_layout.addLayout(control_layout)
        
        # 创建历史记录表格
        self.history_table = QTableWidget()
        self.history_table.setColumnCount(6)
        self.history_table.setHorizontalHeaderLabels(["日期", "模型", "精度", "吞吐量", "延迟", "总时间"])
        self.history_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.history_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.history_table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.history_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.history_table.itemSelectionChanged.connect(self.on_selection_changed)
        main_layout.addWidget(self.history_table)
        
        # 创建详情组
        details_group = QGroupBox("详细信息")
        details_layout = QVBoxLayout()
        
        self.details_label = QLabel("选择一条记录查看详情")
        details_layout.addWidget(self.details_label)
        
        details_group.setLayout(details_layout)
        main_layout.addWidget(details_group)
        
        # 设置主布局
        self.setLayout(main_layout)
    
    def load_history(self):
        """加载历史记录"""
        try:
            # 清空表格
            self.history_table.setRowCount(0)
            self.results = []
            
            # 确保结果目录存在
            if not os.path.exists(self.result_dir):
                os.makedirs(self.result_dir, exist_ok=True)
                return
            
            # 加载所有结果文件
            for filename in os.listdir(self.result_dir):
                if filename.startswith("benchmark_result_") and filename.endswith(".json"):
                    file_path = os.path.join(self.result_dir, filename)
                    try:
                        with open(file_path, 'r', encoding='utf-8') as f:
                            result = json.load(f)
                            result["file_path"] = file_path
                            self.results.append(result)
                    except Exception as e:
                        logger.error(f"加载结果文件失败: {file_path}, 错误: {str(e)}")
            
            # 按日期排序
            self.results.sort(key=lambda x: x.get("end_time", ""), reverse=True)
            
            # 填充表格
            for i, result in enumerate(self.results):
                self.history_table.insertRow(i)
                
                # 日期
                end_time = result.get("end_time", "")
                if end_time:
                    try:
                        dt = datetime.fromisoformat(end_time)
                        date_str = dt.strftime("%Y-%m-%d %H:%M:%S")
                    except:
                        date_str = end_time
                else:
                    date_str = "未知"
                self.history_table.setItem(i, 0, QTableWidgetItem(date_str))
                
                # 模型
                self.history_table.setItem(i, 1, QTableWidgetItem(result.get("model", "未知")))
                
                # 精度
                self.history_table.setItem(i, 2, QTableWidgetItem(result.get("precision", "未知")))
                
                # 指标
                metrics = result.get("metrics", {})
                self.history_table.setItem(i, 3, QTableWidgetItem(f"{metrics.get('throughput', 0):.2f}"))
                self.history_table.setItem(i, 4, QTableWidgetItem(f"{metrics.get('latency', 0):.2f}"))
                self.history_table.setItem(i, 5, QTableWidgetItem(f"{result.get('total_duration', 0):.2f}"))
            
            logger.info(f"加载了 {len(self.results)} 条历史记录")
        except Exception as e:
            logger.error(f"加载历史记录失败: {str(e)}")
            QMessageBox.critical(self, "错误", f"加载历史记录失败: {str(e)}")
    
    def on_selection_changed(self):
        """选择变更事件"""
        selected_rows = self.history_table.selectionModel().selectedRows()
        if selected_rows:
            row = selected_rows[0].row()
            if 0 <= row < len(self.results):
                result = self.results[row]
                self.show_details(result)
    
    def show_details(self, result):
        """显示详细信息"""
        try:
            # 构建详情文本
            details = []
            details.append(f"设备ID: {result.get('device_id', '未知')}")
            details.append(f"设备名称: {result.get('nickname', '未知')}")
            details.append(f"数据集版本: {result.get('dataset_version', '未知')}")
            details.append(f"模型: {result.get('model', '未知')}")
            details.append(f"精度: {result.get('precision', '未知')}")
            
            # 时间信息
            start_time = result.get("start_time", "")
            end_time = result.get("end_time", "")
            if start_time and end_time:
                details.append(f"开始时间: {start_time}")
                details.append(f"结束时间: {end_time}")
                details.append(f"总时间: {result.get('total_duration', 0):.2f} 秒")
            
            # 性能指标
            metrics = result.get("metrics", {})
            details.append(f"吞吐量: {metrics.get('throughput', 0):.2f} tokens/s")
            details.append(f"延迟: {metrics.get('latency', 0):.2f} ms")
            
            # 设置详情文本
            self.details_label.setText("\n".join(details))
        except Exception as e:
            logger.error(f"显示详情失败: {str(e)}")
            self.details_label.setText(f"显示详情失败: {str(e)}")
    
    def export_result(self):
        """导出结果"""
        try:
            selected_rows = self.history_table.selectionModel().selectedRows()
            if not selected_rows:
                QMessageBox.warning(self, "警告", "请先选择一条记录")
                return
            
            row = selected_rows[0].row()
            if 0 <= row < len(self.results):
                result = self.results[row]
                
                # 选择保存路径
                file_path, _ = QFileDialog.getSaveFileName(self, "导出结果", "", "JSON文件 (*.json)")
                if not file_path:
                    return
                
                # 导出结果
                with open(file_path, 'w', encoding='utf-8') as f:
                    json.dump(result, f, ensure_ascii=False, indent=2)
                
                QMessageBox.information(self, "成功", f"结果已导出到: {file_path}")
        except Exception as e:
            logger.error(f"导出结果失败: {str(e)}")
            QMessageBox.critical(self, "错误", f"导出结果失败: {str(e)}")
    
    def delete_result(self):
        """删除结果"""
        try:
            selected_rows = self.history_table.selectionModel().selectedRows()
            if not selected_rows:
                QMessageBox.warning(self, "警告", "请先选择一条记录")
                return
            
            row = selected_rows[0].row()
            if 0 <= row < len(self.results):
                result = self.results[row]
                file_path = result.get("file_path", "")
                
                # 确认删除
                reply = QMessageBox.question(self, "确认", "确定要删除选中的记录吗？", 
                                            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
                if reply != QMessageBox.StandardButton.Yes:
                    return
                
                # 删除文件
                if file_path and os.path.exists(file_path):
                    os.remove(file_path)
                
                # 重新加载历史记录
                self.load_history()
                
                QMessageBox.information(self, "成功", "记录已删除")
        except Exception as e:
            logger.error(f"删除结果失败: {str(e)}")
            QMessageBox.critical(self, "错误", f"删除结果失败: {str(e)}") 