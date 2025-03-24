"""
GPU监控设置界面模块
"""
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox,
    QLabel, QLineEdit, QSpinBox, QPushButton,
    QListWidget, QMessageBox, QFormLayout,
    QDialog, QCheckBox, QDoubleSpinBox, QListWidgetItem,
    QPushButton,QTabWidget,QFileDialog
)
from PyQt6.QtGui import QAction
from PyQt6.QtCore import Qt, pyqtSignal
from src.utils.logger import setup_logger
from src.utils.config import config
from src.monitor.gpu_monitor import GPUMonitorManager
from src.data.db_manager import db_manager
from src.monitor.gpu_monitor import gpu_monitor
from src.gui.i18n.language_manager import LanguageManager

logger = setup_logger("gpu_settings")

class ServerEditDialog(QDialog):
    """服务器编辑对话框"""
    def __init__(self, server_data=None, parent=None):
        super().__init__(parent)
        self.server_data = server_data
        self.language_manager = LanguageManager()
        self.setWindowTitle(self.tr('edit_server') if server_data else self.tr('add_server'))
        self.init_ui()
        if server_data:
            self.load_server_data()
    
    def init_ui(self):
        """初始化UI"""
        layout = QFormLayout()
        layout.setSpacing(10)
        
        # 服务器名称
        self.name_input = QLineEdit()
        layout.addRow(self.tr('server_name') + ":", self.name_input)
        
        # 主机地址
        self.host_input = QLineEdit()
        layout.addRow(self.tr('host') + ":", self.host_input)
        
        # 端口
        self.port_input = QSpinBox()
        self.port_input.setRange(1, 65535)  # 有效的端口范围
        self.port_input.setValue(22)  # 默认端口
        layout.addRow(self.tr('port') + ":", self.port_input)
        
        # 用户名
        self.username_input = QLineEdit()
        layout.addRow(self.tr('username') + ":", self.username_input)

        
        # 认证方式
        tab_layout = QTabWidget()
        
        # 密码
        self.password_input = QLineEdit()
        self.password_input.setEchoMode(QLineEdit.EchoMode.Password)
        tab_layout.addTab(self.password_input, self.tr('pwd_auth'))

        # 私钥文件路径
        self.pkey_path_btn = QPushButton()
        self.pkey_path_btn.setText(self.tr('sel_pkey_file'))  # 设置按钮文本
        self.pkey_path_btn.clicked.connect(self.get_pkey_path)
        
        tab_layout.addTab(self.pkey_path_btn, self.tr('pkey_auth'))
        layout.addRow(self.tr('auth_mode') + ":", tab_layout)
        
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

    def get_pkey_path(self):
        """获取私钥文件路径"""
        file_dialog = QFileDialog()
        file_dialog.setFileMode(QFileDialog.FileMode.ExistingFile)
        file_dialog.setNameFilter("All Files (*.*)")
        if file_dialog.exec():
            self.pkey_path_btn.setText(file_dialog.selectedFiles()[0])
        
    
    def load_server_data(self):
        """加载服务器数据"""
        self.name_input.setText(self.server_data.get("name", ""))
        self.host_input.setText(self.server_data.get("host", ""))
        self.port_input.setValue(self.server_data.get("port", 22))
        self.username_input.setText(self.server_data.get("username", ""))
        self.password_input.setText(self.server_data.get("password", ""))
        self.pkey_path_btn.setText(self.server_data.get("pkey_path", ""))
    
    def get_server_data(self) -> dict:
        """获取服务器数据"""
        return {
            "name": self.name_input.text().strip(),
            "host": self.host_input.text().strip(),
            "port": self.port_input.value(),
            "username": self.username_input.text().strip(),
            "password": self.password_input.text().strip(),
            "pkey_path": self.pkey_path_btn.text().strip(),
        }
    
    def tr(self, key):
        """翻译文本"""
        return self.language_manager.get_text(key)
    
    def test_connection(self):
        """测试服务器连接"""
        try:
            data = self.get_server_data()
            monitor = GPUMonitorManager()
            monitor.setup_monitor(data["host"], data["username"], data["password"], data["port"], data["pkey_path"])
            stats = monitor.get_stats()
            
            if stats:
                QMessageBox.information(
                    self,
                    self.tr('success'),
                    self.tr('test_connection_success')
                )
                logger.info(f"服务器连接测试成功: {data['host']}:{data['port']}")
            else:
                QMessageBox.warning(
                    self,
                    self.tr('warning'),
                    self.tr('test_connection_no_gpu')
                )
                logger.warning(f"服务器GPU信息获取失败: {data['host']}:{data['port']}")
        except Exception as e:
            logger.error(f"服务器连接测试失败: {e}")
            QMessageBox.critical(
                self,
                self.tr('error'),
                f"{self.tr('test_connection_failed')}: {e}"
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
                    self.tr('error'),
                    self.tr('save_server_failed')
                )
        except Exception as e:
            logger.error(f"保存服务器配置失败: {e}")
            QMessageBox.critical(
                self,
                self.tr('error'),
                f"{self.tr('save_server_failed')}: {e}"
            )

class GPUSettingsWidget(QWidget):
    """GPU监控设置组件"""
    settings_updated = pyqtSignal()  # 设置更新信号
    
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
        
        # 创建服务器列表组
        self.server_group = QGroupBox()
        group_layout = QVBoxLayout()
        group_layout.setSpacing(5)  # 减小间距
        
        # 添加按钮栏
        button_layout = QHBoxLayout()
        
        self.add_btn = QPushButton()
        self.add_btn.clicked.connect(self.add_server)
        button_layout.addWidget(self.add_btn)
        
        self.edit_btn = QPushButton()
        self.edit_btn.clicked.connect(self.edit_server)
        button_layout.addWidget(self.edit_btn)
        
        self.delete_btn = QPushButton()
        self.delete_btn.clicked.connect(self.delete_server)
        button_layout.addWidget(self.delete_btn)
        
        self.test_btn = QPushButton()
        self.test_btn.clicked.connect(self.test_server)
        button_layout.addWidget(self.test_btn)
        
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
        
        self.server_group.setLayout(group_layout)
        layout.addWidget(self.server_group)
        
        self.setLayout(layout)
        
        # 加载服务器列表
        self.load_settings()
    
    def update_ui_text(self):
        """更新UI文本"""
        self.server_group.setTitle(self.tr('gpu_server'))
        self.add_btn.setText(self.tr('add'))
        self.edit_btn.setText(self.tr('edit'))
        self.delete_btn.setText(self.tr('delete'))
        self.test_btn.setText(self.tr('test_connection'))
    
    def tr(self, key):
        """翻译文本"""
        return self.language_manager.get_text(key)
    
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
                self.details_label.setText(self.tr('no_servers_hint'))
        except Exception as e:
            logger.error(f"加载GPU服务器设置失败: {e}")
            QMessageBox.critical(self, self.tr('error'), f"{self.tr('error')}: {e}")
    
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
        <b>{self.tr('host')}：</b> {server.get('host', 'N/A')}<br>
        <b>{self.tr('username')}：</b> {server.get('username', 'N/A')}<br>
        <b>{self.tr('server_status')}：</b> {self.tr('status_connected') if server.get('active', False) else self.tr('status_not_configured')}
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
                            self.tr('test_connection_success'),
                            f"{self.tr('test_connection_success')}\n\n"
                            f"{self.tr('gpu_model')}: {stats.gpu_info}\n"
                            f"{self.tr('gpu_count')}: {stats.gpu_count}\n"
                            f"{self.tr('memory_usage')}: {stats.memory_total/1024:.1f}GB"
                        )
                        self.load_settings()
                        self.settings_updated.emit()
                        logger.info(f"GPU服务器连接测试成功: {server['name']}")
                    else:
                        raise Exception(self.tr('test_connection_no_gpu'))
        except Exception as e:
            logger.error(f"GPU服务器连接测试失败: {e}")
            QMessageBox.critical(self, self.tr('error'), f"{self.tr('test_connection_failed')}: {e}")
    
    def reset_settings(self):
        """重置设置"""
        try:
            db_manager.reset_gpu_servers()
            self.load_settings()
            self.settings_updated.emit()
            logger.info("重置GPU服务器设置成功")
        except Exception as e:
            logger.error(f"重置GPU服务器设置失败: {e}")
            QMessageBox.critical(self, self.tr('error'), f"{self.tr('error')}: {e}") 