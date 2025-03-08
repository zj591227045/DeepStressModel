"""
测试进度显示组件模块
"""
from PyQt6.QtWidgets import (
    QGroupBox,
    QVBoxLayout,
    QLabel,
    QProgressBar,
    QTextEdit
)
from src.gui.i18n.language_manager import LanguageManager
from src.utils.logger import setup_logger

# 设置日志记录器
logger = setup_logger("test_progress")


class TestProgressWidget(QGroupBox):
    """测试进度显示组件"""

    def __init__(self):
        super().__init__()
        self.language_manager = LanguageManager()
        self.setObjectName("test_progress_widget")
        self.init_ui()
        self.update_ui_text()
        
        # 连接语言改变信号
        self.language_manager.language_changed.connect(self.update_ui_text)
    
    def update_ui_text(self):
        """更新UI文本"""
        self.setTitle(self.tr('test_progress'))
    
    def tr(self, key):
        """翻译文本"""
        return self.language_manager.get_text(key)
    
    def init_ui(self):
        """初始化UI"""
        layout = QVBoxLayout()
        
        # 添加状态标签
        self.status_label = QLabel(self.tr('status_not_started'))
        self.status_label.setStyleSheet("font-weight: bold;")
        layout.addWidget(self.status_label)
        
        # 添加进度条
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        layout.addWidget(self.progress_bar)
        
        # 添加详细信息文本框
        self.detail_text = QTextEdit()
        self.detail_text.setReadOnly(True)
        self.detail_text.setMaximumHeight(60)  # 减小高度
        self.detail_text.setPlaceholderText(
            self.tr('test_progress_placeholder'))
        layout.addWidget(self.detail_text)
        
        self.setLayout(layout) 