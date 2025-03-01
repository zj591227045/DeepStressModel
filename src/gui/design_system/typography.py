"""
排版系统模块
定义文字相关的样式
"""

class Typography:
    """排版系统"""
    
    # 字体
    FONT_FAMILY = {
        "base": "Microsoft YaHei, -apple-system, BlinkMacSystemFont, Segoe UI, Roboto, Helvetica Neue, Arial, sans-serif",
        "code": "Consolas, Monaco, Andale Mono, Ubuntu Mono, monospace"
    }
    
    # 字号（单位：像素）
    FONT_SIZE = {
        "xs": 12,
        "sm": 14,
        "base": 16,
        "lg": 18,
        "xl": 20,
        "2xl": 24,
        "3xl": 30,
        "4xl": 36,
        "5xl": 48
    }
    
    # 行高
    LINE_HEIGHT = {
        "none": 1,
        "tight": 1.25,
        "snug": 1.375,
        "normal": 1.5,
        "relaxed": 1.625,
        "loose": 2
    }
    
    # 字重
    FONT_WEIGHT = {
        "thin": 100,
        "extralight": 200,
        "light": 300,
        "normal": 400,
        "medium": 500,
        "semibold": 600,
        "bold": 700,
        "extrabold": 800,
        "black": 900
    }
    
    # 字间距
    LETTER_SPACING = {
        "tighter": "-0.05em",
        "tight": "-0.025em",
        "normal": "0em",
        "wide": "0.025em",
        "wider": "0.05em",
        "widest": "0.1em"
    } 