"""
日志管理模块，提供统一的日志记录功能
"""
import logging
import sys
from pathlib import Path
from logging.handlers import RotatingFileHandler
from .config import DATA_DIR

# 创建logs目录
LOGS_DIR = DATA_DIR / "logs"
LOGS_DIR.mkdir(exist_ok=True)

# 日志格式
LOG_FORMAT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

# 保存所有创建的日志记录器
_loggers = {}

def setup_logger(name: str) -> logging.Logger:
    """
    设置并返回一个命名的日志记录器
    
    Args:
        name: 日志记录器名称
        
    Returns:
        logging.Logger: 配置好的日志记录器
    """
    # 如果已经创建过，直接返回
    if name in _loggers:
        return _loggers[name]
    
    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)
    
    # 如果已经有处理器，不重复添加
    if logger.handlers:
        _loggers[name] = logger
        return logger
    
    # 创建格式化器
    formatter = logging.Formatter(LOG_FORMAT, DATE_FORMAT)
    
    # 控制台处理器
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    
    # 文件处理器
    file_handler = RotatingFileHandler(
        LOGS_DIR / f"{name}.log",
        maxBytes=10*1024*1024,  # 10MB
        backupCount=5,
        encoding="utf-8"
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    
    # 保存日志记录器引用
    _loggers[name] = logger
    
    return logger

def set_debug_mode(enable: bool = True):
    """
    启用或禁用调试模式
    
    Args:
        enable: 是否启用调试模式，默认为True
    """
    level = logging.DEBUG if enable else logging.INFO
    
    # 设置所有日志记录器的级别
    for logger_name, logger in _loggers.items():
        logger.setLevel(level)
        
        # 更新控制台处理器的级别
        for handler in logger.handlers:
            if isinstance(handler, logging.StreamHandler) and not isinstance(handler, RotatingFileHandler):
                handler.setLevel(level)
        
        if enable:
            logger.debug(f"已启用调试模式: {logger_name}")

# 创建默认日志记录器
logger = setup_logger("deepstress")
