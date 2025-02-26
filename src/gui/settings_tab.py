"""
设置标签页模块
"""
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox,
    QPushButton, QMessageBox, QSplitter
)
from PyQt6.QtCore import Qt
from src.utils.logger import setup_logger
from src.gui.settings.model_settings import ModelSettingsWidget
from src.gui.settings.dataset_settings import DatasetSettingsWidget
from src.gui.settings.gpu_settings import GPUSettingsWidget

logger = setup_logger("settings")

class SettingsTab(QWidget):
    """设置标签页"""
    def __init__(self):
        super().__init__()
        self.setObjectName("settings_tab")  # 设置对象名称
        self.init_ui()
    
    def init_ui(self):
        """初始化UI"""
        # 创建主布局
        layout = QVBoxLayout()
        
        # 创建水平分割器
        splitter = QSplitter(Qt.Orientation.Horizontal)
        
        # 创建左侧面板（包含模型和GPU服务器设置）
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(0, 0, 0, 0)
        
        # 添加模型设置
        self.model_settings = ModelSettingsWidget()
        self.model_settings.setObjectName("model_settings")  # 设置对象名称
        self.model_settings.setMaximumHeight(400)  # 限制高度
        left_layout.addWidget(self.model_settings)
        
        # 添加GPU服务器设置
        self.gpu_settings = GPUSettingsWidget()
        left_layout.addWidget(self.gpu_settings)
        
        # 创建右侧面板（数据集设置）
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(0, 0, 0, 0)
        
        # 添加数据集设置
        self.dataset_settings = DatasetSettingsWidget()
        right_layout.addWidget(self.dataset_settings)
        
        # 将面板添加到分割器
        splitter.addWidget(left_panel)
        splitter.addWidget(right_panel)
        
        # 设置分割器的初始大小比例（左:右 = 1:1）
        splitter.setSizes([500, 500])
        
        # 将分割器添加到主布局
        layout.addWidget(splitter)
        
        # 添加重置按钮
        reset_layout = QHBoxLayout()
        reset_layout.addStretch()
        
        reset_button = QPushButton("重置所有设置")
        reset_button.clicked.connect(self.reset_all_settings)
        reset_layout.addWidget(reset_button)
        
        layout.addLayout(reset_layout)
        self.setLayout(layout)
    
    def reset_all_settings(self):
        """重置所有设置"""
        reply = QMessageBox.question(
            self,
            "确认重置",
            "确定要重置所有设置吗？这将清除所有自定义配置并恢复默认设置。",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            logger.info("用户确认重置所有设置")
            try:
                # 重置各个设置页面
                self.model_settings.reset_settings()
                self.dataset_settings.reset_settings()
                self.gpu_settings.reset_settings()
                
                QMessageBox.information(self, "成功", "所有设置已重置为默认值")
                logger.info("所有设置已重置")
            except Exception as e:
                QMessageBox.critical(self, "错误", f"重置设置时出错：{e}")
                logger.error(f"重置设置失败: {e}")
