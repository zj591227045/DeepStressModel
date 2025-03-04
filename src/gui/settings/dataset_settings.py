"""
数据集设置界面模块
"""
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox,
    QLabel, QLineEdit, QSpinBox, QPushButton,
    QListWidget, QMessageBox, QFormLayout,
    QDialog, QTextEdit, QFileDialog, QComboBox
)
from PyQt6.QtCore import Qt, pyqtSignal
from src.utils.logger import setup_logger
from src.data.db_manager import db_manager
from src.data.test_datasets import DATASETS  # 导入内置数据集
from src.gui.i18n.language_manager import LanguageManager

logger = setup_logger("dataset_settings")

class DatasetEditDialog(QDialog):
    """数据集编辑对话框"""
    def __init__(self, dataset_data=None, parent=None):
        super().__init__(parent)
        self.dataset_data = dataset_data
        self.language_manager = LanguageManager()
        self.init_ui()
        if dataset_data:
            self.load_dataset_data()
    
    def init_ui(self):
        """初始化UI"""
        self.setWindowTitle(self.tr('edit_dataset') if self.dataset_data else self.tr('add_dataset'))
        layout = QVBoxLayout()
        
        # 创建表单
        form_layout = QFormLayout()
        
        # 名称
        self.name_edit = QLineEdit()
        form_layout.addRow(self.tr('dataset_name') + ":", self.name_edit)
        
        # 类型
        self.category_combo = QComboBox()
        self.category_combo.addItems([
            self.tr('math_qa'),
            self.tr('logic_qa'),
            self.tr('basic_qa'),
            self.tr('code_gen'),
            self.tr('text_gen')
        ])
        form_layout.addRow(self.tr('dataset_type') + ":", self.category_combo)
        
        # 提示词列表
        self.prompts_edit = QTextEdit()
        self.prompts_edit.setPlaceholderText(self.tr('example_prompts'))
        form_layout.addRow(self.tr('prompt_count') + ":", self.prompts_edit)
        
        layout.addLayout(form_layout)
        
        # 按钮
        button_layout = QHBoxLayout()
        save_button = QPushButton(self.tr('save'))
        save_button.clicked.connect(self.accept)
        cancel_button = QPushButton(self.tr('cancel'))
        cancel_button.clicked.connect(self.reject)
        
        button_layout.addWidget(save_button)
        button_layout.addWidget(cancel_button)
        layout.addLayout(button_layout)
        
        self.setLayout(layout)
    
    def load_dataset_data(self):
        """加载数据集数据"""
        self.name_edit.setText(self.dataset_data["name"])
        self.category_combo.setCurrentText(self.dataset_data.get("category", "其他"))
        self.prompts_edit.setPlainText("\n".join(self.dataset_data["prompts"]))
    
    def get_dataset_data(self) -> dict:
        """获取数据集数据"""
        prompts = [p.strip() for p in self.prompts_edit.toPlainText().split("\n") if p.strip()]
        return {
            "name": self.name_edit.text(),
            "category": self.category_combo.currentText(),
            "prompts": prompts,
            "is_builtin": False  # 用户创建的数据集默认非内置
        }
    
    def tr(self, key):
        """翻译文本"""
        return self.language_manager.get_text(key)

class DatasetSettingsWidget(QWidget):
    """数据集设置组件"""
    dataset_updated = pyqtSignal()  # 数据集更新信号
    
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
        
        # 创建数据集列表组
        self.dataset_group = QGroupBox()
        group_layout = QVBoxLayout()
        group_layout.setSpacing(5)  # 减小间距
        
        # 添加按钮栏
        button_layout = QHBoxLayout()
        
        self.add_btn = QPushButton()
        self.add_btn.clicked.connect(self.add_dataset)
        button_layout.addWidget(self.add_btn)
        
        self.edit_btn = QPushButton()
        self.edit_btn.clicked.connect(self.edit_dataset)
        button_layout.addWidget(self.edit_btn)
        
        self.delete_btn = QPushButton()
        self.delete_btn.clicked.connect(self.delete_dataset)
        button_layout.addWidget(self.delete_btn)
        
        self.import_btn = QPushButton()
        self.import_btn.clicked.connect(self.import_dataset)
        button_layout.addWidget(self.import_btn)
        
        self.export_btn = QPushButton()
        self.export_btn.clicked.connect(self.export_dataset)
        button_layout.addWidget(self.export_btn)
        
        group_layout.addLayout(button_layout)
        
        # 添加数据集列表
        self.dataset_list = QListWidget()
        self.dataset_list.currentRowChanged.connect(self.on_dataset_selected)
        group_layout.addWidget(self.dataset_list)
        
        # 添加详情区域
        self.details_label = QLabel()
        self.details_label.setWordWrap(True)
        self.details_label.setTextFormat(Qt.TextFormat.RichText)
        self.details_label.setStyleSheet("QLabel { background-color: #f0f0f0; padding: 5px; border-radius: 3px; }")
        group_layout.addWidget(self.details_label)
        
        self.dataset_group.setLayout(group_layout)
        layout.addWidget(self.dataset_group)
        
        self.setLayout(layout)
        
        # 加载数据集列表
        self.load_datasets()
    
    def update_ui_text(self):
        """更新UI文本"""
        self.dataset_group.setTitle(self.tr('dataset_config'))
        self.add_btn.setText(self.tr('add'))
        self.edit_btn.setText(self.tr('edit'))
        self.delete_btn.setText(self.tr('delete'))
        self.import_btn.setText(self.tr('import'))
        self.export_btn.setText(self.tr('export'))
        
        # 如果没有数据集，更新提示文本
        if self.dataset_list.count() == 0:
            self.details_label.setText(self.tr('no_datasets'))
    
    def tr(self, key):
        """翻译文本"""
        return self.language_manager.get_text(key)
    
    def load_datasets(self):
        """加载数据集列表"""
        try:
            self.dataset_list.clear()
            datasets = db_manager.get_datasets()
            for dataset in datasets:
                self.dataset_list.addItem(dataset["name"])
            
            if self.dataset_list.count() > 0:
                self.dataset_list.setCurrentRow(0)
            else:
                self.details_label.setText(self.tr('no_datasets'))
        except Exception as e:
            logger.error(f"加载数据集列表失败: {e}")
            QMessageBox.critical(self, self.tr('error'), f"{self.tr('error')}: {e}")
    
    def on_dataset_selected(self, row: int):
        """数据集选择变更处理"""
        if row >= 0:
            try:
                datasets = db_manager.get_datasets()
                dataset = next((d for d in datasets if d["name"] == self.dataset_list.item(row).text()), None)
                if dataset:
                    self.show_dataset_details(dataset)
            except Exception as e:
                logger.error(f"获取数据集详情失败: {e}")
    
    def show_dataset_details(self, dataset: dict):
        """显示数据集详情"""
        prompts = dataset.get("prompts", [])
        details = f"""
        <b>{self.tr('dataset_name')}：</b> {dataset.get('name', 'N/A')}<br>
        <b>{self.tr('dataset_type')}：</b> {self.tr(dataset.get('category', 'N/A'))}<br>
        <b>{self.tr('prompt_count')}：</b> {len(prompts)}<br>
        <b>{self.tr('example_prompts')}：</b><br>
        {prompts[0] if prompts else 'N/A'}<br>
        {prompts[1] if len(prompts) > 1 else ''}
        """
        self.details_label.setText(details)
    
    def add_dataset(self):
        """添加数据集"""
        dialog = DatasetEditDialog(parent=self)
        if dialog.exec():
            try:
                dataset_data = dialog.get_dataset_data()
                if db_manager.add_dataset(dataset_data):
                    self.load_datasets()
                    self.dataset_updated.emit()
                    logger.info(f"添加数据集成功: {dataset_data['name']}")
            except Exception as e:
                logger.error(f"添加数据集失败: {e}")
                QMessageBox.critical(self, "错误", f"添加数据集失败：{e}")
    
    def edit_dataset(self):
        """编辑数据集"""
        current_row = self.dataset_list.currentRow()
        if current_row < 0:
            return
        
        try:
            datasets = db_manager.get_datasets()
            dataset = next((d for d in datasets if d["name"] == self.dataset_list.item(current_row).text()), None)
            if dataset:
                dialog = DatasetEditDialog(dataset, parent=self)
                if dialog.exec():
                    dataset_data = dialog.get_dataset_data()
                    if db_manager.add_dataset(dataset_data):
                        self.load_datasets()
                        self.dataset_updated.emit()
                        logger.info(f"编辑数据集成功: {dataset_data['name']}")
        except Exception as e:
            logger.error(f"编辑数据集失败: {e}")
            QMessageBox.critical(self, "错误", f"编辑数据集失败：{e}")
    
    def delete_dataset(self):
        """删除数据集"""
        current_row = self.dataset_list.currentRow()
        if current_row < 0:
            return
        
        dataset_name = self.dataset_list.item(current_row).text()
        msg = "确定要删除数据集\"{}\"吗？".format(dataset_name)
        
        reply = QMessageBox.question(
            self, 
            "确认删除", 
            msg,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            try:
                db_manager.delete_dataset(dataset_name)
                self.load_datasets()
                self.dataset_updated.emit()
                logger.info(f"删除数据集成功: {dataset_name}")
            except Exception as e:
                logger.error(f"删除数据集失败: {e}")
                QMessageBox.critical(self, "错误", f"删除数据集失败：{e}")
    
    def import_dataset(self):
        """导入数据集"""
        try:
            # 先选择内置数据集或从文件导入
            dialog = QDialog(self)
            dialog.setWindowTitle(self.tr('import_dataset'))
            layout = QVBoxLayout()
            
            # 添加选择框
            combo = QComboBox()
            combo.addItems([
                self.tr('import_builtin'),
                self.tr('import_file')
            ])
            layout.addWidget(combo)
            
            # 添加按钮
            button_box = QHBoxLayout()
            ok_btn = QPushButton(self.tr('confirm'))
            ok_btn.clicked.connect(dialog.accept)
            cancel_btn = QPushButton(self.tr('cancel'))
            cancel_btn.clicked.connect(dialog.reject)
            button_box.addWidget(ok_btn)
            button_box.addWidget(cancel_btn)
            layout.addLayout(button_box)
            
            dialog.setLayout(layout)
            
            if dialog.exec():
                if combo.currentIndex() == 0:
                    # 从内置数据集导入
                    self._import_builtin_dataset()
                else:
                    # 从文件导入
                    self._import_from_file()
        except Exception as e:
            logger.error(f"导入数据集失败: {e}")
            QMessageBox.critical(self, self.tr('error'), f"{self.tr('error')}: {e}")
    
    def _import_builtin_dataset(self):
        """从内置数据集导入"""
        try:
            # 选择内置数据集
            dialog = QDialog(self)
            dialog.setWindowTitle(self.tr('select_builtin_dataset'))
            layout = QVBoxLayout()
            
            # 添加数据集列表
            combo = QComboBox()
            for name in DATASETS.keys():
                combo.addItem(name)
            layout.addWidget(combo)
            
            # 添加按钮
            button_box = QHBoxLayout()
            ok_btn = QPushButton(self.tr('import'))
            ok_btn.clicked.connect(dialog.accept)
            cancel_btn = QPushButton(self.tr('cancel'))
            cancel_btn.clicked.connect(dialog.reject)
            button_box.addWidget(ok_btn)
            button_box.addWidget(cancel_btn)
            layout.addLayout(button_box)
            
            dialog.setLayout(layout)
            
            if dialog.exec():
                dataset_name = combo.currentText()
                dataset_data = {
                    "name": dataset_name,
                    "prompts": DATASETS[dataset_name]
                }
                if db_manager.add_dataset(dataset_data):
                    self.load_datasets()
                    self.dataset_updated.emit()
                    logger.info(f"导入内置数据集成功: {dataset_name}")
        except Exception as e:
            logger.error(f"导入内置数据集失败: {e}")
            QMessageBox.critical(self, self.tr('error'), f"{self.tr('error')}: {e}")
    
    def _import_from_file(self):
        """从文件导入数据集"""
        try:
            file_path, _ = QFileDialog.getOpenFileName(
                self,
                self.tr('select_dataset_file'),
                "",
                f"{self.tr('text_file')} (*.txt);;{self.tr('all_files')} (*.*)"
            )
            
            if file_path:
                with open(file_path, "r", encoding="utf-8") as f:
                    prompts = [line.strip() for line in f if line.strip()]
                
                if prompts:
                    dataset_name = file_path.split("/")[-1].split(".")[0]
                    dataset_data = {
                        "name": dataset_name,
                        "prompts": prompts
                    }
                    if db_manager.add_dataset(dataset_data):
                        self.load_datasets()
                        self.dataset_updated.emit()
                        logger.info(f"从文件导入数据集成功: {dataset_name}")
                else:
                    raise Exception(self.tr('file_empty'))
        except Exception as e:
            logger.error(f"从文件导入数据集失败: {e}")
            QMessageBox.critical(self, self.tr('error'), f"{self.tr('error')}: {e}")
    
    def export_dataset(self):
        """导出数据集"""
        current_row = self.dataset_list.currentRow()
        if current_row < 0:
            return
        
        try:
            datasets = db_manager.get_datasets()
            dataset = next((d for d in datasets if d["name"] == self.dataset_list.item(current_row).text()), None)
            if dataset:
                file_path, _ = QFileDialog.getSaveFileName(
                    self,
                    self.tr('export_dataset'),
                    f"{dataset['name']}.txt",
                    f"{self.tr('text_file')} (*.txt);;{self.tr('all_files')} (*.*)"
                )
                
                if file_path:
                    with open(file_path, "w", encoding="utf-8") as f:
                        f.write("\n".join(dataset["prompts"]))
                    logger.info(f"导出数据集成功: {dataset['name']}")
        except Exception as e:
            logger.error(f"导出数据集失败: {e}")
            QMessageBox.critical(self, self.tr('error'), f"{self.tr('error')}: {e}")
    
    def reset_settings(self):
        """重置设置"""
        try:
            db_manager.reset_datasets()
            self.load_datasets()
            self.dataset_updated.emit()
            logger.info("重置数据集设置成功")
        except Exception as e:
            logger.error(f"重置数据集设置失败: {e}") 