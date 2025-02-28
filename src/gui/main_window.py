"""
主窗口模块
"""
from PyQt6.QtWidgets import (
    QMainWindow, QTabWidget, QWidget, QVBoxLayout,
    QMessageBox
)
from PyQt6.QtCore import Qt
from src.utils.config import config
from src.utils.logger import setup_logger
from src.gui.test_tab import TestTab
from src.gui.settings_tab import SettingsTab
from src.gui.results_tab import ResultsTab

logger = setup_logger("gui")

class MainWindow(QMainWindow):
    """主窗口类"""
    def __init__(self):
        super().__init__()
        self.init_ui()
        self.connect_signals()
    
    def init_ui(self):
        """初始化UI"""
        # 设置窗口属性
        self.setWindowTitle(config.get("window.title", "DeepStressModel"))
        self.resize(
            config.get("window.width", 1200),
            config.get("window.height", 800)
        )
        
        # 创建中央部件
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # 创建布局
        layout = QVBoxLayout(central_widget)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # 创建标签页
        self.tab_widget = QTabWidget()
        layout.addWidget(self.tab_widget)
        
        # 添加标签页
        self.test_tab = TestTab()
        self.settings_tab = SettingsTab()
        self.results_tab = ResultsTab()
        
        self.tab_widget.addTab(self.test_tab, "测试")
        self.tab_widget.addTab(self.settings_tab, "设置")
        self.tab_widget.addTab(self.results_tab, "记录")
        
        logger.info("主窗口初始化完成")
    
    def connect_signals(self):
        """连接信号"""
        # 连接测试标签页的信号到记录标签页
        self.test_tab.test_manager.result_received.connect(self.results_tab.add_result)
        logger.info("信号连接完成")
    
    def closeEvent(self, event):
        """窗口关闭事件"""
        logger.info("窗口关闭事件被触发")
        reply = QMessageBox.question(
            self,
            "确认退出",
            "确定要退出程序吗？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            logger.info("用户确认退出程序")
            # 保存窗口大小
            config.set("window.width", self.width())
            config.set("window.height", self.height())
            
            # 确保测试线程已经停止
            if hasattr(self.test_tab, 'test_thread') and self.test_tab.test_thread:
                logger.info("正在停止测试线程...")
                self.test_tab.stop_test()
                self.test_tab.test_thread.wait(5000)  # 等待最多5秒
            
            logger.info("程序即将退出")
            event.accept()
        else:
            logger.info("用户取消退出")
            event.ignore()
