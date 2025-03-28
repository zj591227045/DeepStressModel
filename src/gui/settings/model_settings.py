"""
模型设置界面模块
"""
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox,
    QLabel, QLineEdit, QSpinBox, QDoubleSpinBox,
    QPushButton, QListWidget, QMessageBox, QFormLayout,
    QDialog, QTextEdit, QFileDialog, QComboBox
)
from PyQt6.QtCore import Qt, pyqtSignal
from src.utils.logger import setup_logger
from src.data.db_manager import db_manager
from src.gui.i18n.language_manager import LanguageManager

logger = setup_logger("model_settings")

class ModelEditDialog(QDialog):
    """模型编辑对话框"""
    def __init__(self, model_data=None, parent=None):
        super().__init__(parent)
        self.model_data = model_data
        self.language_manager = LanguageManager()
        self.init_ui()
        if model_data:
            self.load_model_data()
    
    def init_ui(self):
        """初始化UI"""
        self.setWindowTitle(self.tr('edit_model') if self.model_data else self.tr('add_model'))
        layout = QFormLayout()
        layout.setSpacing(10)
        
        # 名称输入
        self.name_input = QLineEdit()
        layout.addRow(self.tr('name') + ":", self.name_input)
        
        # API地址输入
        self.api_url_input = QLineEdit()
        layout.addRow(self.tr('api_url') + ":", self.api_url_input)
        
        # API密钥输入
        self.api_key_input = QLineEdit()
        self.api_key_input.setEchoMode(QLineEdit.EchoMode.Password)
        layout.addRow(self.tr('api_key') + ":", self.api_key_input)
        
        # 模型名称输入
        self.model_input = QLineEdit()
        layout.addRow(self.tr('model_name') + ":", self.model_input)
        
        # 最大Token数输入
        self.max_tokens_input = QSpinBox()
        self.max_tokens_input.setRange(1, 100000)
        self.max_tokens_input.setValue(2048)
        layout.addRow(self.tr('max_tokens') + ":", self.max_tokens_input)
        
        # 温度输入
        self.temperature_input = QDoubleSpinBox()
        self.temperature_input.setRange(0, 2)
        self.temperature_input.setSingleStep(0.1)
        self.temperature_input.setValue(0.7)
        layout.addRow("Temperature:", self.temperature_input)
        
        # Top P输入
        self.top_p_input = QDoubleSpinBox()
        self.top_p_input.setRange(0, 1)
        self.top_p_input.setSingleStep(0.1)
        self.top_p_input.setValue(0.9)
        layout.addRow(self.tr('top_p') + ":", self.top_p_input)
        
        # 按钮
        button_box = QHBoxLayout()
        save_btn = QPushButton(self.tr('save'))
        save_btn.clicked.connect(self.accept)
        cancel_btn = QPushButton(self.tr('cancel'))
        cancel_btn.clicked.connect(self.reject)
        button_box.addWidget(save_btn)
        button_box.addWidget(cancel_btn)
        layout.addRow("", button_box)
        
        self.setLayout(layout)
    
    def load_model_data(self):
        """加载模型数据"""
        self.name_input.setText(self.model_data.get("name", ""))
        self.api_url_input.setText(self.model_data.get("api_url", ""))
        self.api_key_input.setText(self.model_data.get("api_key", ""))
        self.model_input.setText(self.model_data.get("model", ""))
        self.max_tokens_input.setValue(self.model_data.get("max_tokens", 2048))
        self.temperature_input.setValue(self.model_data.get("temperature", 0.7))
        self.top_p_input.setValue(self.model_data.get("top_p", 0.9))
    
    def get_model_data(self) -> dict:
        """获取模型数据"""
        return {
            "name": self.name_input.text().strip(),
            "api_url": self.api_url_input.text().strip(),
            "api_key": self.api_key_input.text().strip(),
            "model": self.model_input.text().strip(),
            "max_tokens": self.max_tokens_input.value(),
            "temperature": self.temperature_input.value(),
            "top_p": self.top_p_input.value()
        }
    
    def tr(self, key):
        """翻译文本"""
        return self.language_manager.get_text(key)

class ModelSettingsWidget(QWidget):
    """模型设置组件"""
    model_updated = pyqtSignal()  # 模型更新信号
    
    def __init__(self):
        super().__init__()
        self.language_manager = LanguageManager()
        self.init_ui()
        self.update_ui_text()
        
        # 连接语言改变信号
        self.language_manager.language_changed.connect(self.update_ui_text)
    
    def init_ui(self):
        """初始化UI"""
        layout = QVBoxLayout()
        layout.setContentsMargins(5, 5, 5, 5)  # 减小边距
        
        # 创建模型列表组
        self.model_group = QGroupBox()
        group_layout = QVBoxLayout()
        group_layout.setSpacing(5)  # 减小间距
        
        # 添加按钮栏
        button_layout = QHBoxLayout()
        
        self.add_btn = QPushButton()
        self.add_btn.clicked.connect(self.add_model)
        button_layout.addWidget(self.add_btn)
        
        self.edit_btn = QPushButton()
        self.edit_btn.clicked.connect(self.edit_model)
        button_layout.addWidget(self.edit_btn)
        
        self.delete_btn = QPushButton()
        self.delete_btn.clicked.connect(self.delete_model)
        button_layout.addWidget(self.delete_btn)
        
        group_layout.addLayout(button_layout)
        
        # 添加模型列表
        self.model_list = QListWidget()
        self.model_list.currentRowChanged.connect(self.on_model_selected)
        group_layout.addWidget(self.model_list)
        
        # 添加详情区域
        self.details_label = QLabel()
        self.details_label.setWordWrap(True)
        self.details_label.setTextFormat(Qt.TextFormat.RichText)
        self.details_label.setStyleSheet("QLabel { background-color: #f0f0f0; padding: 5px; border-radius: 3px; }")
        group_layout.addWidget(self.details_label)
        
        self.model_group.setLayout(group_layout)
        layout.addWidget(self.model_group)
        
        # 添加通用配置组
        self.common_group = QGroupBox()
        common_layout = QFormLayout()
        common_layout.setSpacing(10)
        
        # 超时设置
        self.timeout_spin = QSpinBox()
        self.timeout_spin.setRange(1, 300)  # 1-300秒
        self.timeout_spin.setValue(db_manager.get_config("test.timeout", 15))
        self.timeout_spin.valueChanged.connect(self.save_common_settings)
        self.timeout_label = QLabel()
        common_layout.addRow(self.timeout_label, self.timeout_spin)
        
        # 重试次数设置
        self.retry_spin = QSpinBox()
        self.retry_spin.setRange(0, 10)  # 0-10次
        self.retry_spin.setValue(db_manager.get_config("test.retry_count", 1))
        self.retry_spin.valueChanged.connect(self.save_common_settings)
        self.retry_label = QLabel()
        common_layout.addRow(self.retry_label, self.retry_spin)
        
        self.common_group.setLayout(common_layout)
        layout.addWidget(self.common_group)
        
        self.setLayout(layout)
        
        # 加载模型列表
        self.load_models()
    
    def update_ui_text(self):
        """更新UI文本"""
        self.model_group.setTitle(self.tr('model_config'))
        self.add_btn.setText(self.tr('add'))
        self.edit_btn.setText(self.tr('edit'))
        self.delete_btn.setText(self.tr('delete'))
        self.common_group.setTitle(self.tr('common_config'))
        self.timeout_label.setText(self.tr('request_timeout'))
        self.retry_label.setText(self.tr('retry_count'))
        
        # 如果没有模型，更新提示文本
        if self.model_list.count() == 0:
            self.details_label.setText(self.tr('no_models'))
    
    def tr(self, key):
        """翻译文本"""
        return self.language_manager.get_text(key)
    
    def load_models(self):
        """加载模型列表"""
        try:
            self.model_list.clear()
            models = db_manager.get_model_configs()
            for model in models:
                self.model_list.addItem(model["name"])
            
            if self.model_list.count() > 0:
                self.model_list.setCurrentRow(0)
            else:
                self.details_label.setText(self.tr('no_models'))
        except Exception as e:
            logger.error(f"加载模型列表失败: {e}")
            QMessageBox.critical(self, self.tr('error'), f"{self.tr('error')}: {e}")
    
    def on_model_selected(self, row: int):
        """模型选择变更处理"""
        if row >= 0:
            try:
                models = db_manager.get_model_configs()
                model = next((m for m in models if m["name"] == self.model_list.item(row).text()), None)
                if model:
                    self.show_model_details(model)
            except Exception as e:
                logger.error(f"获取模型详情失败: {e}")
    
    def show_model_details(self, model: dict):
        """显示模型详情"""
        details = f"""
        <b>{self.tr('api_url')}：</b> {model.get('api_url', 'N/A')}<br>
        <b>{self.tr('model_name')}：</b> {model.get('model', 'N/A')}<br>
        <b>{self.tr('max_tokens')}：</b> {model.get('max_tokens', 'N/A')}<br>
        <b>Temperature：</b> {model.get('temperature', 'N/A')}<br>
        <b>{self.tr('top_p')}：</b> {model.get('top_p', 'N/A')}
        """
        self.details_label.setText(details)
    
    def add_model(self):
        """添加模型"""
        dialog = ModelEditDialog(parent=self)
        if dialog.exec():
            model_data = dialog.get_model_data()
            if db_manager.add_model_config(model_data):
                self.load_models()
                self.model_updated.emit()
                logger.info(f"添加模型配置成功: {model_data['name']}")
            else:
                QMessageBox.critical(self, "错误", "添加模型配置失败")
    
    def edit_model(self):
        """编辑模型"""
        current_item = self.model_list.currentItem()
        if not current_item:
            return
        
        model_name = current_item.text()
        models = db_manager.get_model_configs()
        model_data = next((m for m in models if m["name"] == model_name), None)
        
        if model_data:
            dialog = ModelEditDialog(model_data, parent=self)
            if dialog.exec():
                new_data = dialog.get_model_data()
                if new_data["name"] != model_name:
                    # 如果名称改变了，删除旧配置并添加新配置
                    if db_manager.delete_model_config(model_name) and db_manager.add_model_config(new_data):
                        self.load_models()
                        self.model_updated.emit()
                        logger.info(f"更新模型配置成功: {new_data['name']}")
                    else:
                        QMessageBox.critical(self, "错误", "更新模型配置失败")
                else:
                    # 如果名称没变，直接更新配置
                    if db_manager.update_model_config(new_data):
                        self.load_models()
                        self.model_updated.emit()
                        logger.info(f"更新模型配置成功: {new_data['name']}")
                    else:
                        QMessageBox.critical(self, "错误", "更新模型配置失败")
    
    def delete_model(self):
        """删除模型"""
        current_item = self.model_list.currentItem()
        if not current_item:
            return
        
        model_name = current_item.text()
        reply = QMessageBox.question(
            self,
            self.tr('confirm_delete'),
            self.tr('confirm_delete_model'),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            if db_manager.delete_model_config(model_name):
                self.load_models()
                self.model_updated.emit()
                logger.info(f"删除模型配置成功: {model_name}")
            else:
                QMessageBox.critical(self, self.tr('error'), self.tr('save_server_failed'))
    
    def reset_settings(self):
        """重置设置"""
        try:
            db_manager.reset_model_configs()
            self.load_models()
            self.model_updated.emit()
            logger.info("重置模型配置成功")
        except Exception as e:
            logger.error(f"重置模型配置失败: {e}")
            raise

    def save_common_settings(self):
        """保存通用配置"""
        try:
            db_manager.set_config("test.timeout", self.timeout_spin.value())
            db_manager.set_config("test.retry_count", self.retry_spin.value())
            logger.info("保存通用配置成功")
        except Exception as e:
            logger.error(f"保存通用配置失败: {e}")
            QMessageBox.critical(self, "错误", f"保存通用配置失败：{e}") 