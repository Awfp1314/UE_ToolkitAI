# -*- coding: utf-8 -*-

"""
确认对话框（用于重要操作）
"""

from PyQt6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton
from PyQt6.QtCore import Qt, QPoint
from PyQt6.QtGui import QMouseEvent


class ConfirmDialog(QDialog):
    """确认对话框（用于重要操作）"""
    
    def __init__(self, title: str, message: str, details: str = "", parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.drag_position = QPoint()
        self._init_ui(message, details)
    
    def _init_ui(self, message: str, details: str):
        """初始化UI"""
        self.setMinimumWidth(450)
        self.setObjectName("ConfirmDialog")
        
        # 去掉标题栏
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog)
        
        layout = QVBoxLayout()
        layout.setSpacing(15)
        layout.setContentsMargins(25, 25, 25, 25)
        
        message_label = QLabel(message)
        message_label.setObjectName("ConfirmDialogMessage")
        message_label.setWordWrap(True)
        layout.addWidget(message_label)
        
        # 详细信息
        if details:
            details_label = QLabel(details)
            details_label.setObjectName("ConfirmDialogDetails")
            details_label.setWordWrap(True)
            details_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            layout.addWidget(details_label)
        
        layout.addSpacing(10)
        
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        
        cancel_btn = QPushButton("取消")
        cancel_btn.setObjectName("ConfirmDialogCancelButton")
        cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(cancel_btn)
        
        ok_btn = QPushButton("确认")
        ok_btn.setObjectName("ConfirmDialogOkButton")
        ok_btn.clicked.connect(self.accept)
        ok_btn.setDefault(True)
        button_layout.addWidget(ok_btn)
        
        layout.addLayout(button_layout)
        self.setLayout(layout)
    
    def mousePressEvent(self, event: QMouseEvent):
        """鼠标按下事件 - 用于拖拽"""
        if event.button() == Qt.MouseButton.LeftButton:
            self.drag_position = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()
    
    def mouseMoveEvent(self, event: QMouseEvent):
        """鼠标移动事件 - 实现拖拽"""
        if event.buttons() == Qt.MouseButton.LeftButton:
            self.move(event.globalPosition().toPoint() - self.drag_position)
            event.accept()
    
    def showEvent(self, event):
        """显示事件 - 居中显示"""
        super().showEvent(event)
        self.center_on_parent()
    
    def center_on_parent(self):
        """在父窗口上居中显示"""
        if self.parent():
            # 获取父窗口
            parent = self.parent()
            
            # 需要向上查找到顶层窗口
            top_window = parent
            while top_window.parent():
                top_window = top_window.parent()
            
            # 获取顶层窗口的全局位置和大小
            parent_geo = top_window.geometry()
            parent_pos = top_window.pos()
            
            # 获取对话框大小
            dialog_width = self.width()
            dialog_height = self.height()
            
            # 计算居中位置（全局坐标）
            x = parent_pos.x() + (parent_geo.width() - dialog_width) // 2
            y = parent_pos.y() + (parent_geo.height() - dialog_height) // 2
            
            self.move(x, y)
        else:
            # 如果没有父窗口，居中到屏幕
            from PyQt6.QtWidgets import QApplication
            screen = QApplication.primaryScreen().availableGeometry()
            x = screen.x() + (screen.width() - self.width()) // 2
            y = screen.y() + (screen.height() - self.height()) // 2
            self.move(x, y)

