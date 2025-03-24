"""
DeepStressModel 程序入口
"""
import sys
import argparse
import logging
from PyQt6.QtWidgets import QApplication
from src.gui.main_window import MainWindow
from src.utils.logger import setup_logger, set_debug_mode

logger = setup_logger("main")

def main():
    """程序入口函数"""
    try:
        # 解析命令行参数
        parser = argparse.ArgumentParser(description="DeepStressModel - GPU压力测试工具")
        parser.add_argument("--debug", action="store_true", help="启用调试模式，显示详细日志")
        args = parser.parse_args()
        
        # 如果启用调试模式，设置所有日志记录器为DEBUG级别
        if args.debug:
            set_debug_mode(True)
            logger.debug("调试模式已启用")
        
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
