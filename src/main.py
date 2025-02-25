"""
DeepStressModel 程序入口
"""
import sys
from PyQt6.QtWidgets import QApplication
from src.gui.main_window import MainWindow
from src.utils.logger import setup_logger

logger = setup_logger("main")

def main():
    """程序入口函数"""
    try:
        # 创建应用程序实例
        app = QApplication(sys.argv)
        
        # 创建主窗口
        window = MainWindow()
        window.show()
        
        logger.info("程序启动成功")
        
        # 进入事件循环
        sys.exit(app.exec())
    except Exception as e:
        logger.error(f"程序启动失败: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
