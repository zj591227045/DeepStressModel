"""
现代化按钮组件
提供美观、响应式的按钮控件
"""

from PyQt6.QtWidgets import QPushButton, QGraphicsDropShadowEffect
from PyQt6.QtCore import Qt, QPropertyAnimation, QEasingCurve, QPoint
from PyQt6.QtGui import QColor
from src.gui.design_system import ColorPalette, Typography, Spacing, StyleSheet


class ModernButton(QPushButton):
    """现代化按钮组件"""
    
    def __init__(
        self,
        text: str = "",
        variant: str = "primary",
        size: str = "base",
        icon = None,
        parent = None
    ):
        """初始化按钮
        
        Args:
            text: 按钮文本
            variant: 按钮样式变体，可选值：primary, secondary, text
            size: 按钮大小，可选值：sm, base, lg
            icon: 按钮图标
            parent: 父组件
        """
        super().__init__(text, parent)
        
        self.variant = variant
        self.size = size
        if icon:
            self.setIcon(icon)
            
        self.setup_ui()
        self.setup_animations()
        
    def setup_ui(self):
        """设置UI样式"""
        # 基础样式
        self.setStyleSheet(
            StyleSheet.create_button_style(
                self.variant,
                self.isEnabled()
            )
        )
        
        # 设置大小
        sizes = {
            "sm": (Spacing.SPACE["base"], Spacing.SPACE["lg"]),
            "base": (Spacing.SPACE["lg"], Spacing.SPACE["xl"]),
            "lg": (Spacing.SPACE["xl"], Spacing.SPACE["2xl"])
        }
        vertical, horizontal = sizes.get(self.size, sizes["base"])
        self.setMinimumHeight(vertical * 2 + Typography.FONT_SIZE["base"])
        
        # 添加阴影效果
        if self.variant == "primary":
            shadow = QGraphicsDropShadowEffect(self)
            shadow.setBlurRadius(20)
            shadow.setXOffset(0)
            shadow.setYOffset(4)
            shadow.setColor(QColor(ColorPalette.PRIMARY).darker(150))
            self.setGraphicsEffect(shadow)
        
    def setup_animations(self):
        """设置动画效果"""
        # 悬停动画
        self.hover_animation = QPropertyAnimation(self, b"pos")
        self.hover_animation.setDuration(200)
        self.hover_animation.setEasingCurve(QEasingCurve.Type.InOutCubic)
        
    def enterEvent(self, event):
        """鼠标进入事件"""
        if self.isEnabled():
            # 上移动画
            pos = self.pos()
            self.hover_animation.setStartValue(pos)
            new_pos = QPoint(pos.x(), pos.y() - 2)
            self.hover_animation.setEndValue(new_pos)
            self.hover_animation.start()
            
        super().enterEvent(event)
        
    def leaveEvent(self, event):
        """鼠标离开事件"""
        if self.isEnabled():
            # 恢复位置
            pos = self.pos()
            self.hover_animation.setStartValue(pos)
            new_pos = QPoint(pos.x(), pos.y() + 2)
            self.hover_animation.setEndValue(new_pos)
            self.hover_animation.start()
            
        super().leaveEvent(event)
        
    def setEnabled(self, enabled: bool):
        """设置按钮启用状态
        
        Args:
            enabled: 是否启用
        """
        super().setEnabled(enabled)
        # 更新样式
        self.setStyleSheet(
            StyleSheet.create_button_style(
                self.variant,
                enabled
            )
        ) 