# -*- coding: utf-8 -*-

"""
配置工具占位 UI - 功能开发中提示页面
"""

from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont


class ConfigToolPlaceholderUI(QWidget):
    """配置工具占位 UI"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.init_ui()
    
    def init_ui(self):
        """初始化UI"""
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        # 图标
        icon_label = QLabel("⚙️")
        icon_font = QFont()
        icon_font.setPointSize(72)
        icon_label.setFont(icon_font)
        icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(icon_label)
        
        # 标题
        title_label = QLabel("工程配置")
        title_font = QFont()
        title_font.setPointSize(24)
        title_font.setBold(True)
        title_label.setFont(title_font)
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title_label)
        
        # 提示信息
        info_label = QLabel("功能开发中，敬请期待...")
        info_font = QFont()
        info_font.setPointSize(14)
        info_label.setFont(info_font)
        info_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        info_label.setStyleSheet("color: rgba(255, 255, 255, 0.6);")
        layout.addWidget(info_label)
        
        # 详细说明
        detail_label = QLabel(
            "工程配置工具将帮助您管理虚幻引擎项目的各项配置。\n"
            "目前正在开发中，请稍后再试。"
        )
        detail_font = QFont()
        detail_font.setPointSize(12)
        detail_label.setFont(detail_font)
        detail_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        detail_label.setStyleSheet("color: rgba(255, 255, 255, 0.4);")
        detail_label.setWordWrap(True)
        layout.addWidget(detail_label)
        
        # 设置布局边距
        layout.setContentsMargins(50, 50, 50, 50)
        layout.setSpacing(20)

