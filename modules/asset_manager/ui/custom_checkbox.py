# -*- coding: utf-8 -*-

"""
自定义复选框 - 带对勾标记
"""

from PyQt6.QtWidgets import QCheckBox
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPainter, QColor, QPen, QPainterPath


class CustomCheckBox(QCheckBox):
    """自定义复选框，选中时显示对勾"""
    
    def __init__(self, text="", parent=None):
        super().__init__(text, parent)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
    
    def paintEvent(self, event):
        """重写绘制事件以绘制对勾"""
        super().paintEvent(event)
        
        if self.isChecked():
            painter = QPainter(self)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            
            # 获取indicator的矩形区域
            from PyQt6.QtWidgets import QStyleOptionButton
            option = QStyleOptionButton()
            option.initFrom(self)
            
            indicator_rect = self.style().subElementRect(
                self.style().SubElement.SE_CheckBoxIndicator,
                option,
                self
            )
            
            # 绘制白色对勾
            painter.setPen(QPen(QColor(255, 255, 255), 2, Qt.PenStyle.SolidLine))
            
            # 对勾的路径
            path = QPainterPath()
            x = indicator_rect.x() + 4
            y = indicator_rect.y() + 4
            w = indicator_rect.width() - 8
            h = indicator_rect.height() - 8
            
            # 绘制对勾符号 ✓
            path.moveTo(x + w * 0.2, y + h * 0.5)
            path.lineTo(x + w * 0.4, y + h * 0.7)
            path.lineTo(x + w * 0.8, y + h * 0.3)
            
            painter.drawPath(path)
            painter.end()
