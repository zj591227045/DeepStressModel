"""
主窗口模块
"""
from PyQt6.QtWidgets import (
    QMainWindow, QTabWidget, QWidget, QVBoxLayout, QHBoxLayout,
    QMessageBox, QMenuBar, QMenu, QComboBox, QLabel
)
from PyQt6.QtGui import QAction
from PyQt6.QtCore import Qt
from src.utils.config import config
from src.utils.logger import setup_logger
from src.gui.test_tab import TestTab
from src.gui.settings_tab import SettingsTab
from src.gui.results_tab import ResultsTab
from src.gui.i18n.language_manager import LanguageManager

logger = setup_logger("gui")

class MainWindow(QMainWindow):
    """主窗口类"""
    def __init__(self):
        super().__init__()
        self.language_manager = LanguageManager()
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
        
        # 创建菜单栏
        self.create_menu_bar()
        
        # 创建中央部件
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # 创建布局
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        
        # 创建顶部工具栏区域
        top_bar = QWidget()
        top_layout = QHBoxLayout(top_bar)
        top_layout.setContentsMargins(5, 5, 5, 5)
        
        # 添加弹簧
        top_layout.addStretch()
        
        # 创建语言选择区域
        lang_widget = QWidget()
        lang_layout = QHBoxLayout(lang_widget)
        lang_layout.setContentsMargins(0, 0, 0, 0)
        
        # 添加语言标签
        lang_label = QLabel(self.tr('language') + ":")
        lang_layout.addWidget(lang_label)
        
        # 创建语言选择下拉框
        self.lang_combo = QComboBox()
        for lang_code, lang_name in self.language_manager.available_languages.items():
            self.lang_combo.addItem(lang_name, lang_code)
        # 设置当前语言
        current_lang = self.language_manager.current_language
        index = self.lang_combo.findData(current_lang)
        if index >= 0:
            self.lang_combo.setCurrentIndex(index)
        self.lang_combo.currentIndexChanged.connect(self._on_language_changed)
        lang_layout.addWidget(self.lang_combo)
        
        top_layout.addWidget(lang_widget)
        main_layout.addWidget(top_bar)
        
        # 创建标签页
        self.tab_widget = QTabWidget()
        main_layout.addWidget(self.tab_widget)
        
        # 添加标签页
        self.test_tab = TestTab()
        self.settings_tab = SettingsTab()
        self.results_tab = ResultsTab()
        
        # 将标签页添加到tab_widget
        self.tab_widget.addTab(self.test_tab, "")
        self.tab_widget.addTab(self.settings_tab, "")
        self.tab_widget.addTab(self.results_tab, "")
        
        # 更新UI文本
        self.update_ui_text()
        
        logger.info("主窗口初始化完成")
    
    def create_menu_bar(self):
        """创建菜单栏"""
        menubar = self.menuBar()
        
        # 文件菜单
        file_menu = menubar.addMenu(self.tr('file'))
        exit_action = QAction(self.tr('exit'), self)
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)
    
    def _on_language_changed(self, index):
        """语言选择改变时的处理"""
        lang_code = self.lang_combo.itemData(index)
        if lang_code:
            self.change_language(lang_code)
    
    def change_language(self, language_code):
        """切换语言"""
        self.language_manager.set_language(language_code)
        self.update_ui_text()
    
    def update_ui_text(self):
        """更新UI文本"""
        self.tab_widget.setTabText(0, self.tr('test'))
        self.tab_widget.setTabText(1, self.tr('settings'))
        self.tab_widget.setTabText(2, self.tr('results'))
        
        # 更新菜单栏文本
        menubar = self.menuBar()
        menubar.clear()
        self.create_menu_bar()
    
    def tr(self, key):
        """翻译文本"""
        return self.language_manager.get_text(key)
    
    def connect_signals(self):
        """连接信号"""
        # 连接测试标签页的信号到记录标签页
        self.test_tab.test_manager.result_received.connect(self.results_tab.add_result)
        # 连接语言改变信号
        self.language_manager.language_changed.connect(self.update_ui_text)
        logger.info("信号连接完成")
    
    def closeEvent(self, event):
        """窗口关闭事件"""
        logger.info("窗口关闭事件被触发")
        reply = QMessageBox.question(
            self,
            self.tr('exit'),
            self.tr('Are you sure to exit?'),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            logger.info("用户确认退出程序")
            # 保存窗口大小和语言设置
            config.set("window.width", self.width())
            config.set("window.height", self.height())
            config.set("app.language", self.language_manager.current_language)
            
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
