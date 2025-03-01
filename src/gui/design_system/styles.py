"""
样式系统模块
提供组件样式生成方法
"""

from .colors import ColorPalette
from .typography import Typography
from .spacing import Spacing

class StyleSheet:
    """样式表生成器"""
    
    @staticmethod
    def create_button_style(variant: str = "primary", enabled: bool = True) -> str:
        """生成按钮样式
        
        Args:
            variant: 按钮变体，可选值：primary, secondary, text
            enabled: 是否启用
            
        Returns:
            str: 样式表字符串
        """
        if not enabled:
            return f"""
                QPushButton {{
                    background-color: {ColorPalette.BACKGROUND};
                    color: {ColorPalette.TEXT_DISABLED};
                    border: 1px solid {ColorPalette.BORDER};
                    border-radius: {Spacing.RADIUS["base"]}px;
                    padding: {Spacing.PADDING["base"]}px {Spacing.PADDING["lg"]}px;
                    font-family: {Typography.FONT_FAMILY["base"]};
                    font-size: {Typography.FONT_SIZE["base"]}px;
                }}
            """
            
        if variant == "primary":
            return f"""
                QPushButton {{
                    background-color: {ColorPalette.PRIMARY};
                    color: {ColorPalette.WHITE};
                    border: none;
                    border-radius: {Spacing.RADIUS["base"]}px;
                    padding: {Spacing.PADDING["base"]}px {Spacing.PADDING["lg"]}px;
                    font-family: {Typography.FONT_FAMILY["base"]};
                    font-size: {Typography.FONT_SIZE["base"]}px;
                }}
                QPushButton:hover {{
                    background-color: {ColorPalette.PRIMARY_LIGHT};
                }}
                QPushButton:pressed {{
                    background-color: {ColorPalette.PRIMARY_DARK};
                }}
            """
        elif variant == "secondary":
            return f"""
                QPushButton {{
                    background-color: {ColorPalette.WHITE};
                    color: {ColorPalette.PRIMARY};
                    border: 1px solid {ColorPalette.PRIMARY};
                    border-radius: {Spacing.RADIUS["base"]}px;
                    padding: {Spacing.PADDING["base"]}px {Spacing.PADDING["lg"]}px;
                    font-family: {Typography.FONT_FAMILY["base"]};
                    font-size: {Typography.FONT_SIZE["base"]}px;
                }}
                QPushButton:hover {{
                    background-color: {ColorPalette.PRIMARY_LIGHT};
                    color: {ColorPalette.WHITE};
                    border: none;
                }}
                QPushButton:pressed {{
                    background-color: {ColorPalette.PRIMARY_DARK};
                    color: {ColorPalette.WHITE};
                    border: none;
                }}
            """
        else:  # text
            return f"""
                QPushButton {{
                    background-color: transparent;
                    color: {ColorPalette.PRIMARY};
                    border: none;
                    padding: {Spacing.PADDING["base"]}px {Spacing.PADDING["lg"]}px;
                    font-family: {Typography.FONT_FAMILY["base"]};
                    font-size: {Typography.FONT_SIZE["base"]}px;
                }}
                QPushButton:hover {{
                    color: {ColorPalette.PRIMARY_LIGHT};
                }}
                QPushButton:pressed {{
                    color: {ColorPalette.PRIMARY_DARK};
                }}
            """
    
    @staticmethod
    def create_input_style(variant: str = "default", enabled: bool = True) -> str:
        """生成输入框样式
        
        Args:
            variant: 输入框变体，可选值：default, error
            enabled: 是否启用
            
        Returns:
            str: 样式表字符串
        """
        if not enabled:
            return f"""
                QLineEdit {{
                    background-color: {ColorPalette.BACKGROUND};
                    color: {ColorPalette.TEXT_DISABLED};
                    border: 1px solid {ColorPalette.BORDER};
                    border-radius: {Spacing.RADIUS["base"]}px;
                    padding: {Spacing.PADDING["base"]}px;
                    font-family: {Typography.FONT_FAMILY["base"]};
                    font-size: {Typography.FONT_SIZE["base"]}px;
                }}
            """
            
        if variant == "error":
            return f"""
                QLineEdit {{
                    background-color: {ColorPalette.WHITE};
                    color: {ColorPalette.TEXT};
                    border: 1px solid {ColorPalette.ERROR};
                    border-radius: {Spacing.RADIUS["base"]}px;
                    padding: {Spacing.PADDING["base"]}px;
                    font-family: {Typography.FONT_FAMILY["base"]};
                    font-size: {Typography.FONT_SIZE["base"]}px;
                }}
                QLineEdit:focus {{
                    border: 2px solid {ColorPalette.ERROR};
                }}
            """
        else:  # default
            return f"""
                QLineEdit {{
                    background-color: {ColorPalette.WHITE};
                    color: {ColorPalette.TEXT};
                    border: 1px solid {ColorPalette.BORDER};
                    border-radius: {Spacing.RADIUS["base"]}px;
                    padding: {Spacing.PADDING["base"]}px;
                    font-family: {Typography.FONT_FAMILY["base"]};
                    font-size: {Typography.FONT_SIZE["base"]}px;
                }}
                QLineEdit:focus {{
                    border: 2px solid {ColorPalette.PRIMARY};
                }}
            """ 