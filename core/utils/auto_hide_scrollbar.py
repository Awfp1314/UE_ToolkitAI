# -*- coding: utf-8 -*-

"""
自动隐藏滚动条工具

实现类似网页的滚动条自动隐藏效果
"""

from PyQt6.QtWidgets import QScrollArea, QScrollBar, QGraphicsOpacityEffect
from PyQt6.QtCore import QTimer, QPropertyAnimation, QEasingCurve, pyqtProperty


class AutoHideScrollBar(QScrollBar):
    """支持自动隐藏的滚动条"""
    
    def __init__(self, orientation, parent=None):
        super().__init__(orientation, parent)
        
        # 使用 QGraphicsOpacityEffect 实现透明度动画
        self._opacity_effect = QGraphicsOpacityEffect(self)
        self.setGraphicsEffect(self._opacity_effect)
        self._opacity_effect.setOpacity(0.0)  # 初始隐藏
        
        self._hide_timer = QTimer(self)
        self._hide_timer.timeout.connect(self._start_hide_animation)
        self._hide_timer.setSingleShot(True)
        
        self._animation = QPropertyAnimation(self._opacity_effect, b"opacity")
        self._animation.setDuration(300)
        self._animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        
        # 监听滚动事件
        self.valueChanged.connect(self._on_scroll)
        
        # 初始隐藏
        self._hide_timer.start(1000)
    
    def _on_scroll(self):
        """滚动时显示滚动条"""
        self._show()
        self._hide_timer.start(1000)  # 1秒后隐藏
    
    def _show(self):
        """显示滚动条"""
        self._animation.stop()
        self._animation.setStartValue(self._opacity_effect.opacity())
        self._animation.setEndValue(1.0)
        self._animation.start()
    
    def _start_hide_animation(self):
        """开始隐藏动画"""
        self._animation.stop()
        self._animation.setStartValue(self._opacity_effect.opacity())
        self._animation.setEndValue(0.0)
        self._animation.start()
    
    def enterEvent(self, event):
        """鼠标进入时显示"""
        super().enterEvent(event)
        self._hide_timer.stop()
        self._show()
    
    def leaveEvent(self, event):
        """鼠标离开时延迟隐藏"""
        super().leaveEvent(event)
        self._hide_timer.start(500)


def enable_auto_hide_scrollbar(scroll_area: QScrollArea):
    """
    为 QScrollArea 启用自动隐藏滚动条
    
    Args:
        scroll_area: QScrollArea 实例
    """
    # 替换垂直滚动条
    old_vbar = scroll_area.verticalScrollBar()
    new_vbar = AutoHideScrollBar(old_vbar.orientation(), scroll_area)
    new_vbar.setRange(old_vbar.minimum(), old_vbar.maximum())
    new_vbar.setValue(old_vbar.value())
    scroll_area.setVerticalScrollBar(new_vbar)
    
    # 替换水平滚动条
    old_hbar = scroll_area.horizontalScrollBar()
    new_hbar = AutoHideScrollBar(old_hbar.orientation(), scroll_area)
    new_hbar.setRange(old_hbar.minimum(), old_hbar.maximum())
    new_hbar.setValue(old_hbar.value())
    scroll_area.setHorizontalScrollBar(new_hbar)
