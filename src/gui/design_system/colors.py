"""
颜色系统模块
定义应用的颜色方案
"""

class ColorPalette:
    """颜色调色板"""
    
    # 主题色
    PRIMARY = "#1890ff"  # 主色
    PRIMARY_LIGHT = "#40a9ff"  # 主色-浅色
    PRIMARY_DARK = "#096dd9"  # 主色-深色
    
    # 状态色
    SUCCESS = "#52c41a"  # 成功
    WARNING = "#faad14"  # 警告
    ERROR = "#f5222d"  # 错误
    INFO = "#1890ff"  # 信息
    
    # 中性色
    TEXT = "#000000"  # 文本
    TEXT_SECONDARY = "#666666"  # 次要文本
    TEXT_DISABLED = "#999999"  # 禁用文本
    BORDER = "#d9d9d9"  # 边框
    BACKGROUND = "#f5f5f5"  # 背景
    WHITE = "#ffffff"  # 白色
    
    # 功能色
    LINK = "#1890ff"  # 链接
    LINK_HOVER = "#40a9ff"  # 链接悬停
    LINK_ACTIVE = "#096dd9"  # 链接激活 