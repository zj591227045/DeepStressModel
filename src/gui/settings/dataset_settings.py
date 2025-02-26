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

logger = setup_logger("dataset_settings")

class DatasetEditDialog(QDialog):
    """数据集编辑对话框"""
    def __init__(self, dataset_data=None, parent=None):
        super().__init__(parent)
        self.dataset_data = dataset_data
        self.init_ui()
        if dataset_data:
            self.load_dataset_data()
    
    def init_ui(self):
        """初始化UI"""
        self.setWindowTitle("编辑数据集" if self.dataset_data else "添加数据集")
        layout = QVBoxLayout()
        
        # 创建表单
        form_layout = QFormLayout()
        
        # 名称
        self.name_edit = QLineEdit()
        form_layout.addRow("数据集名称:", self.name_edit)
        
        # 描述
        self.description_edit = QLineEdit()
        form_layout.addRow("描述:", self.description_edit)
        
        # 类别
        self.category_combo = QComboBox()
        self.category_combo.addItems(["问答", "文本生成", "代码生成", "其他"])
        form_layout.addRow("类别:", self.category_combo)
        
        # 提示词列表
        self.prompts_edit = QTextEdit()
        self.prompts_edit.setPlaceholderText("每行一个提示词...")
        form_layout.addRow("提示词列表:", self.prompts_edit)
        
        layout.addLayout(form_layout)
        
        # 按钮
        button_layout = QHBoxLayout()
        save_button = QPushButton("保存")
        save_button.clicked.connect(self.accept)
        cancel_button = QPushButton("取消")
        cancel_button.clicked.connect(self.reject)
        
        button_layout.addWidget(save_button)
        button_layout.addWidget(cancel_button)
        layout.addLayout(button_layout)
        
        self.setLayout(layout)
    
    def load_dataset_data(self):
        """加载数据集数据"""
        self.name_edit.setText(self.dataset_data["name"])
        self.description_edit.setText(self.dataset_data.get("description", ""))
        self.category_combo.setCurrentText(self.dataset_data.get("category", "其他"))
        self.prompts_edit.setPlainText("\n".join(self.dataset_data["prompts"]))
    
    def get_dataset_data(self) -> dict:
        """获取数据集数据"""
        prompts = [p.strip() for p in self.prompts_edit.toPlainText().split("\n") if p.strip()]
        return {
            "name": self.name_edit.text(),
            "description": self.description_edit.text(),
            "category": self.category_combo.currentText(),
            "prompts": prompts,
            "is_builtin": False  # 用户创建的数据集默认非内置
        }

class DatasetSettingsWidget(QWidget):
    """数据集设置组件"""
    dataset_updated = pyqtSignal()  # 数据集更新信号
    
    def __init__(self):
        super().__init__()
        self.init_ui()
    
    def init_ui(self):
        """初始化UI"""
        layout = QVBoxLayout()
        layout.setContentsMargins(5, 5, 5, 5)  # 减小边距
        
        # 创建数据集列表组
        group = QGroupBox("数据集配置")
        group_layout = QVBoxLayout()
        group_layout.setSpacing(5)  # 减小间距
        
        # 添加按钮栏
        button_layout = QHBoxLayout()
        
        add_btn = QPushButton("添加")
        add_btn.clicked.connect(self.add_dataset)
        button_layout.addWidget(add_btn)
        
        edit_btn = QPushButton("编辑")
        edit_btn.clicked.connect(self.edit_dataset)
        button_layout.addWidget(edit_btn)
        
        delete_btn = QPushButton("删除")
        delete_btn.clicked.connect(self.delete_dataset)
        button_layout.addWidget(delete_btn)
        
        import_btn = QPushButton("导入")
        import_btn.clicked.connect(self.import_dataset)
        button_layout.addWidget(import_btn)
        
        export_btn = QPushButton("导出")
        export_btn.clicked.connect(self.export_dataset)
        button_layout.addWidget(export_btn)
        
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
        
        group.setLayout(group_layout)
        layout.addWidget(group)
        
        self.setLayout(layout)
        
        # 加载数据集列表
        self.load_datasets()
    
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
                self.details_label.setText("暂无数据集")
        except Exception as e:
            logger.error(f"加载数据集列表失败: {e}")
            QMessageBox.critical(self, "错误", f"加载数据集列表失败：{e}")
    
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
        <b>数据集名称：</b> {dataset.get('name', 'N/A')}<br>
        <b>提示数量：</b> {len(prompts)}<br>
        <b>示例提示：</b><br>
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
            dialog.setWindowTitle("导入数据集")
            layout = QVBoxLayout()
            
            # 添加选择框
            combo = QComboBox()
            combo.addItem("从内置数据集导入")
            combo.addItem("从文件导入")
            layout.addWidget(combo)
            
            # 添加按钮
            button_box = QHBoxLayout()
            ok_btn = QPushButton("确定")
            ok_btn.clicked.connect(dialog.accept)
            cancel_btn = QPushButton("取消")
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
            QMessageBox.critical(self, "错误", f"导入数据集失败：{e}")
    
    def _import_builtin_dataset(self):
        """从内置数据集导入"""
        try:
            # 选择内置数据集
            dialog = QDialog(self)
            dialog.setWindowTitle("选择内置数据集")
            layout = QVBoxLayout()
            
            # 添加数据集列表
            combo = QComboBox()
            for name in DATASETS.keys():
                combo.addItem(name)
            layout.addWidget(combo)
            
            # 添加按钮
            button_box = QHBoxLayout()
            ok_btn = QPushButton("导入")
            ok_btn.clicked.connect(dialog.accept)
            cancel_btn = QPushButton("取消")
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
            QMessageBox.critical(self, "错误", f"导入内置数据集失败：{e}")
    
    def _import_from_file(self):
        """从文件导入数据集"""
        try:
            file_path, _ = QFileDialog.getOpenFileName(
                self,
                "选择数据集文件",
                "",
                "文本文件 (*.txt);;所有文件 (*.*)"
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
                    raise Exception("文件内容为空")
        except Exception as e:
            logger.error(f"从文件导入数据集失败: {e}")
            QMessageBox.critical(self, "错误", f"从文件导入数据集失败：{e}")
    
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
                    "导出数据集",
                    f"{dataset['name']}.txt",
                    "文本文件 (*.txt);;所有文件 (*.*)"
                )
                
                if file_path:
                    with open(file_path, "w", encoding="utf-8") as f:
                        f.write("\n".join(dataset["prompts"]))
                    logger.info(f"导出数据集成功: {dataset['name']}")
        except Exception as e:
            logger.error(f"导出数据集失败: {e}")
            QMessageBox.critical(self, "错误", f"导出数据集失败：{e}")
    
    def reset_settings(self):
        """重置设置"""
        try:
            db_manager.reset_datasets()
            self.load_datasets()
            self.dataset_updated.emit()
            logger.info("重置数据集设置成功")
        except Exception as e:
            logger.error(f"重置数据集设置失败: {e}") 