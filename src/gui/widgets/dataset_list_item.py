"""
数据集列表项组件模块
"""
from PyQt6.QtWidgets import (
    QWidget,
    QHBoxLayout,
    QLabel,
    QSlider,
    QSizePolicy
)
from PyQt6.QtCore import Qt
from src.gui.i18n.language_manager import LanguageManager
from src.utils.logger import setup_logger

# 设置日志记录器
logger = setup_logger("dataset_list_item")


class DatasetListItem(QWidget):
    """数据集列表项"""

    # 数据集名称映射字典，将中文名映射到翻译键
    DATASET_NAME_MAP = {
        "数学问题": "math_qa",
        "逻辑问题": "logic_qa",
        "基础问答": "basic_qa",
        "代码生成": "code_gen",
        "文本生成": "text_gen"
    }

    def __init__(self, dataset_name: str, parent=None):
        super().__init__(parent)
        self.dataset_name = dataset_name
        self.language_manager = LanguageManager()
        self.init_ui()
        
        # 连接语言改变信号
        self.language_manager.language_changed.connect(self.update_ui_text)
        logger.info(f"创建数据集列表项: {dataset_name}")
    
    def init_ui(self):
        """初始化UI"""
        layout = QHBoxLayout()
        layout.setContentsMargins(5, 2, 5, 2)
        layout.setSpacing(10)  # 增加组件之间的间距
        
        # 数据集名称标签
        self.name_label = QLabel(self.get_translated_name())
        self.name_label.setMinimumWidth(100)  # 设置最小宽度确保名称显示完整
        layout.addWidget(self.name_label)
        
        # 权重滑块
        self.weight_slider = QSlider(Qt.Orientation.Horizontal)
        self.weight_slider.setRange(1, 10)  # 设置权重范围1-10
        self.weight_slider.setValue(1)  # 默认权重为1
        self.weight_slider.setMinimumWidth(200)  # 设置最小宽度
        self.weight_slider.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Fixed)  # 水平方向自适应
        self.weight_slider.setTickPosition(
            QSlider.TickPosition.TicksBelow)  # 在下方显示刻度
        self.weight_slider.setTickInterval(1)  # 主刻度间隔为1
        self.weight_slider.valueChanged.connect(self._on_weight_changed)
        
        # 权重值显示标签
        self.weight_label = QLabel(f"{self.tr('weight')}: 1")
        self.weight_label.setFixedWidth(80)  # 设置固定宽度
        self.weight_label.setAlignment(
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)  # 右对齐
        
        layout.addWidget(self.weight_slider, 1)  # 设置stretch factor为1，允许滑块拉伸
        layout.addWidget(self.weight_label)
        
        self.setLayout(layout)
        logger.info(f"数据集 {self.dataset_name} 初始化完成，默认权重: 1")
    
    def tr(self, key):
        """翻译文本"""
        return self.language_manager.get_text(key)
    
    def get_translated_name(self):
        """获取翻译后的数据集名称"""
        # 如果数据集名称在映射字典中，使用对应的翻译键
        if self.dataset_name in self.DATASET_NAME_MAP:
            return self.tr(self.DATASET_NAME_MAP[self.dataset_name])
        # 否则直接使用原名称
        return self.dataset_name
    
    def update_ui_text(self):
        """更新UI文本"""
        self.name_label.setText(self.get_translated_name())
        self.weight_label.setText(
            f"{self.tr('weight')}: {self.weight_slider.value()}")
    
    def _on_weight_changed(self, value):
        """权重值变更处理"""
        self.weight_label.setText(f"{self.tr('weight')}: {value}")
    
    def get_weight(self) -> int:
        """获取权重值"""
        return self.weight_slider.value() 