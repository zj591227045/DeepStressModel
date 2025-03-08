"""
测试信息显示组件模块
"""
from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QGroupBox,
    QTextEdit,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView
)
from src.gui.i18n.language_manager import LanguageManager
from src.utils.logger import setup_logger

# 设置日志记录器
logger = setup_logger("test_info")


class TestInfoWidget(QWidget):
    """实时测试信息显示组件"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.language_manager = LanguageManager()
        self.init_ui()
        self.update_ui_text()
        
        # 连接语言改变信号
        self.language_manager.language_changed.connect(self.update_ui_text)
    
    def update_ui_text(self):
        """更新UI文本"""
        self.info_group.setTitle(self.tr('test_info'))
        self.error_group.setTitle(self.tr('error'))
        
        # 更新表格头
        self.info_table.setHorizontalHeaderLabels([
            self.tr('dataset'),
            self.tr('completion_total'),
            self.tr('success_rate'),
            self.tr('avg_response_time'),
            self.tr('avg_generation_speed'),
            self.tr('current_speed'),
            self.tr('total_chars'),
            self.tr('avg_tps')
        ])
        
        # 更新错误文本框占位符
        self.error_text.setPlaceholderText(self.tr('error_info_placeholder'))
    
    def tr(self, key):
        """翻译文本"""
        return self.language_manager.get_text(key)
        
    def init_ui(self):
        layout = QVBoxLayout()
        
        # Info group
        self.info_group = QGroupBox(self.tr('test_info'))
        info_layout = QVBoxLayout()
        
        # Info table
        self.info_table = QTableWidget()
        self.info_table.setColumnCount(8)
        
        # 设置表格属性
        header = self.info_table.horizontalHeader()
        # 设置所有列先自适应内容
        header.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        
        # 设置特定列的宽度策略
        header.setSectionResizeMode(
            0, QHeaderView.ResizeMode.Stretch)  # 数据集名称列自适应剩余空间
        # 为其他列设置最小宽度，确保数据显示完整
        min_widths = {
            1: 100,  # 完成/总数
            2: 80,   # 成功率
            3: 120,  # 平均响应时间
            4: 120,  # 平均生成速度
            5: 100,  # 当前速度
            6: 100,  # 总字符数
            7: 100   # 平均TPS
        }
        for col, width in min_widths.items():
            self.info_table.setColumnWidth(col, width)
        
        info_layout.addWidget(self.info_table)
        self.info_group.setLayout(info_layout)
        
        # Error group
        self.error_group = QGroupBox(self.tr('error'))
        error_layout = QVBoxLayout()
        
        self.error_text = QTextEdit()
        self.error_text.setReadOnly(True)
        self.error_text.setMaximumHeight(60)  # 减小高度
        self.error_text.setPlaceholderText(self.tr('error_info_placeholder'))
        error_layout.addWidget(self.error_text)
        self.error_group.setLayout(error_layout)
        
        layout.addWidget(self.info_group)
        layout.addWidget(self.error_group)
        
        # 设置布局间距
        layout.setSpacing(10)  # 增加组件之间的间距
        self.setLayout(layout)
    
    def update_dataset_info(self, dataset_name: str, stats: dict):
        """更新数据集测试信息"""
        # 查找数据集行
        found = False
        for row in range(self.info_table.rowCount()):
            if self.info_table.item(row, 0).text() == dataset_name:
                found = True
                break
        
        # 如果没找到，添加新行
        if not found:
            row = self.info_table.rowCount()
            self.info_table.insertRow(row)
            self.info_table.setItem(row, 0, QTableWidgetItem(dataset_name))
        
        # 更新统计信息
        completion = f"{stats['successful']}/{stats['total']}"
        self.info_table.setItem(row, 1, QTableWidgetItem(completion))
        
        success_rate = (
            stats['successful'] /
            stats['total'] *
            100) if stats['total'] > 0 else 0
        self.info_table.setItem(
            row, 2, QTableWidgetItem(f"{success_rate:.1f}%"))

        avg_time = stats['total_time'] / \
            stats['successful'] if stats['successful'] > 0 else 0
        self.info_table.setItem(row, 3, QTableWidgetItem(f"{avg_time:.1f}s"))
        
        avg_speed = stats['total_chars'] / \
            stats['total_time'] if stats['total_time'] > 0 else 0
        self.info_table.setItem(
            row, 4, QTableWidgetItem(f"{avg_speed:.1f}字/秒"))
        
        current_speed = stats.get('current_speed', 0)
        self.info_table.setItem(
            row, 5, QTableWidgetItem(f"{current_speed:.1f}字/秒"))
        
        self.info_table.setItem(
            row, 6, QTableWidgetItem(str(stats['total_chars'])))
        
        # 获取平均TPS值，如果不存在则使用0
        avg_tps = stats.get('avg_tps', 0)
        self.info_table.setItem(row, 7, QTableWidgetItem(f"{avg_tps:.1f}"))
    
    def add_error(self, error_msg: str):
        """添加错误信息"""
        self.error_text.append(error_msg)
    
    def clear(self):
        """清空所有信息"""
        self.info_table.setRowCount(0)
        self.error_text.clear() 