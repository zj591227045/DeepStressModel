"""
GPU监控设置界面模块
"""
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox,
    QLabel, QLineEdit, QSpinBox, QPushButton,
    QListWidget, QMessageBox, QFormLayout,
    QDialog, QCheckBox, QDoubleSpinBox, QListWidgetItem
)
from PyQt6.QtCore import Qt, pyqtSignal
from src.utils.logger import setup_logger
from src.utils.config import config
from src.monitor.gpu_monitor import GPUMonitorManager
from src.data.db_manager import db_manager
from src.monitor.gpu_monitor import gpu_monitor

logger = setup_logger("gpu_settings")

class ServerEditDialog(QDialog):
    """服务器编辑对话框"""
    def __init__(self, server_data=None, parent=None):
        super().__init__(parent)
        self.server_data = server_data
        self.setWindowTitle("编辑服务器" if server_data else "添加服务器")
        self.init_ui()
        if server_data:
            self.load_server_data()
    
    def init_ui(self):
        """初始化UI"""
        layout = QFormLayout()
        layout.setSpacing(10)
        
        # 名称输入
        self.name_input = QLineEdit()
        layout.addRow("配置名称:", self.name_input)
        
        # 主机地址输入
        self.host_input = QLineEdit()
        layout.addRow("主机地址:", self.host_input)
        
        # 用户名输入
        self.username_input = QLineEdit()
        layout.addRow("用户名:", self.username_input)
        
        # 密码输入
        self.password_input = QLineEdit()
        self.password_input.setEchoMode(QLineEdit.EchoMode.Password)
        layout.addRow("密码:", self.password_input)
        
        # 按钮
        button_box = QHBoxLayout()
        save_btn = QPushButton("保存")
        save_btn.clicked.connect(self.accept)
        cancel_btn = QPushButton("取消")
        cancel_btn.clicked.connect(self.reject)
        button_box.addWidget(save_btn)
        button_box.addWidget(cancel_btn)
        layout.addRow("", button_box)
        
        self.setLayout(layout)
    
    def load_server_data(self):
        """加载服务器数据"""
        self.name_input.setText(self.server_data.get("name", ""))
        self.host_input.setText(self.server_data.get("host", ""))
        self.username_input.setText(self.server_data.get("username", ""))
        self.password_input.setText(self.server_data.get("password", ""))
    
    def get_server_data(self) -> dict:
        """获取服务器数据"""
        return {
            "name": self.name_input.text().strip(),
            "host": self.host_input.text().strip(),
            "username": self.username_input.text().strip(),
            "password": self.password_input.text().strip()
        }
    
    def test_connection(self):
        """测试服务器连接"""
        try:
            data = self.get_server_data()
            monitor = GPUMonitorManager()
            monitor.setup_remote(data["host"], data["username"], data["password"])
            stats = monitor.get_stats()
            
            if stats:
                QMessageBox.information(
                    self,
                    "成功",
                    "连接测试成功！已成功获取GPU信息。"
                )
                logger.info(f"服务器连接测试成功: {data['host']}")
            else:
                QMessageBox.warning(
                    self,
                    "警告",
                    "连接成功但无法获取GPU信息，请检查服务器是否安装NVIDIA驱动。"
                )
                logger.warning(f"服务器GPU信息获取失败: {data['host']}")
        except Exception as e:
            logger.error(f"服务器连接测试失败: {e}")
            QMessageBox.critical(
                self,
                "错误",
                f"连接测试失败：{e}"
            )
    
    def accept(self):
        """保存服务器配置"""
        try:
            server_data = self.get_server_data()
            if db_manager.add_gpu_server(server_data):
                # 设置为活动服务器
                db_manager.set_gpu_server_active(server_data["name"])
                super().accept()
            else:
                QMessageBox.critical(
                    self,
                    "错误",
                    "保存服务器配置失败"
                )
        except Exception as e:
            logger.error(f"保存服务器配置失败: {e}")
            QMessageBox.critical(
                self,
                "错误",
                f"保存服务器配置失败：{e}"
            )

class GPUSettingsWidget(QWidget):
    """GPU监控设置组件"""
    settings_updated = pyqtSignal()  # 设置更新信号
    
    def __init__(self):
        super().__init__()
        self.init_ui()
    
    def init_ui(self):
        """初始化UI"""
        layout = QVBoxLayout()
        layout.setContentsMargins(5, 5, 5, 5)  # 减小边距
        
        # 创建服务器列表组
        group = QGroupBox("GPU服务器")
        group_layout = QVBoxLayout()
        group_layout.setSpacing(5)  # 减小间距
        
        # 添加按钮栏
        button_layout = QHBoxLayout()
        
        add_btn = QPushButton("添加")
        add_btn.clicked.connect(self.add_server)
        button_layout.addWidget(add_btn)
        
        edit_btn = QPushButton("编辑")
        edit_btn.clicked.connect(self.edit_server)
        button_layout.addWidget(edit_btn)
        
        delete_btn = QPushButton("删除")
        delete_btn.clicked.connect(self.delete_server)
        button_layout.addWidget(delete_btn)
        
        test_btn = QPushButton("测试")
        test_btn.clicked.connect(self.test_server)
        button_layout.addWidget(test_btn)
        
        group_layout.addLayout(button_layout)
        
        # 添加服务器列表
        self.server_list = QListWidget()
        self.server_list.currentRowChanged.connect(self.on_server_selected)
        group_layout.addWidget(self.server_list)
        
        # 添加详情区域
        self.details_label = QLabel()
        self.details_label.setWordWrap(True)
        self.details_label.setTextFormat(Qt.TextFormat.RichText)
        self.details_label.setStyleSheet("QLabel { background-color: #f0f0f0; padding: 5px; border-radius: 3px; }")
        group_layout.addWidget(self.details_label)
        
        group.setLayout(group_layout)
        layout.addWidget(group)
        
        self.setLayout(layout)
        
        # 加载服务器列表
        self.load_settings()
    
    def load_settings(self):
        """加载设置"""
        try:
            self.server_list.clear()
            servers = db_manager.get_gpu_servers()
            active_server = db_manager.get_active_gpu_server()
            
            for server in servers:
                item = server["name"]
                if active_server and server["name"] == active_server["name"]:
                    item = f"✓ {item}"
                self.server_list.addItem(item)
            
            if self.server_list.count() > 0:
                self.server_list.setCurrentRow(0)
            else:
                self.details_label.setText("暂无服务器配置")
        except Exception as e:
            logger.error(f"加载GPU服务器设置失败: {e}")
            QMessageBox.critical(self, "错误", f"加载GPU服务器设置失败：{e}")
    
    def on_server_selected(self, row: int):
        """服务器选择变更处理"""
        if row >= 0:
            try:
                servers = db_manager.get_gpu_servers()
                server_name = self.server_list.item(row).text().replace("✓ ", "")
                server = next((s for s in servers if s["name"] == server_name), None)
                if server:
                    self.show_server_details(server)
            except Exception as e:
                logger.error(f"获取服务器详情失败: {e}")
    
    def show_server_details(self, server: dict):
        """显示服务器详情"""
        details = f"""
        <b>主机地址：</b> {server.get('host', 'N/A')}<br>
        <b>用户名：</b> {server.get('username', 'N/A')}<br>
        <b>状态：</b> {'活动' if server.get('active', False) else '未激活'}
        """
        self.details_label.setText(details)
    
    def add_server(self):
        """添加服务器"""
        dialog = ServerEditDialog(parent=self)
        if dialog.exec():
            try:
                server_data = dialog.get_server_data()
                if db_manager.add_gpu_server(server_data):
                    self.load_settings()
                    self.settings_updated.emit()
                    logger.info(f"添加GPU服务器成功: {server_data['name']}")
            except Exception as e:
                logger.error(f"添加GPU服务器失败: {e}")
                QMessageBox.critical(self, "错误", f"添加GPU服务器失败：{e}")
    
    def edit_server(self):
        """编辑服务器"""
        current_row = self.server_list.currentRow()
        if current_row < 0:
            return
        
        try:
            servers = db_manager.get_gpu_servers()
            server_name = self.server_list.item(current_row).text().replace("✓ ", "")
            server = next((s for s in servers if s["name"] == server_name), None)
            if server:
                dialog = ServerEditDialog(server, parent=self)
                if dialog.exec():
                    server_data = dialog.get_server_data()
                    if db_manager.add_gpu_server(server_data):
                        self.load_settings()
                        self.settings_updated.emit()
                        logger.info(f"编辑GPU服务器成功: {server_data['name']}")
        except Exception as e:
            logger.error(f"编辑GPU服务器失败: {e}")
            QMessageBox.critical(self, "错误", f"编辑GPU服务器失败：{e}")
    
    def delete_server(self):
        """删除服务器"""
        current_row = self.server_list.currentRow()
        if current_row < 0:
            return
        
        server_name = self.server_list.item(current_row).text().replace("✓ ", "")
        msg = "确定要删除服务器配置\"{}\"吗？".format(server_name)
        
        reply = QMessageBox.question(
            self, 
            "确认删除", 
            msg,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            try:
                db_manager.delete_gpu_server(server_name)
                self.load_settings()
                self.settings_updated.emit()
                logger.info(f"删除GPU服务器成功: {server_name}")
            except Exception as e:
                logger.error(f"删除GPU服务器失败: {e}")
                QMessageBox.critical(self, "错误", f"删除GPU服务器失败：{e}")
    
    def test_server(self):
        """测试服务器连接"""
        current_row = self.server_list.currentRow()
        if current_row < 0:
            return
        
        try:
            servers = db_manager.get_gpu_servers()
            server_name = self.server_list.item(current_row).text().replace("✓ ", "")
            server = next((s for s in servers if s["name"] == server_name), None)
            if server:
                # 设置为活动服务器
                if db_manager.set_gpu_server_active(server["name"]):
                    # 初始化GPU监控
                    gpu_monitor.init_monitor()
                    # 获取GPU状态
                    stats = gpu_monitor.get_stats()
                    if stats:
                        QMessageBox.information(
                            self,
                            "连接成功",
                            f"成功连接到GPU服务器\n\n"
                            f"GPU型号: {stats.gpu_info}\n"
                            f"GPU数量: {stats.gpu_count}\n"
                            f"显存大小: {stats.memory_total/1024:.1f}GB"
                        )
                        self.load_settings()
                        self.settings_updated.emit()
                        logger.info(f"GPU服务器连接测试成功: {server['name']}")
                    else:
                        raise Exception("无法获取GPU状态")
        except Exception as e:
            logger.error(f"GPU服务器连接测试失败: {e}")
            QMessageBox.critical(self, "错误", f"连接失败：{e}")
    
    def reset_settings(self):
        """重置设置"""
        try:
            db_manager.reset_gpu_servers()
            self.load_settings()
            self.settings_updated.emit()
            logger.info("重置GPU服务器设置成功")
        except Exception as e:
            logger.error(f"重置GPU服务器设置失败: {e}") 