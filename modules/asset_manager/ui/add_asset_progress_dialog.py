#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
添加资产进度对话框
显示添加资产的进度
"""

from PyQt6.QtWidgets import (
    QApplication, QDialog, QVBoxLayout, QLabel,
    QProgressBar
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont

from core.logger import get_logger

logger = get_logger(__name__)


class AddAssetProgressDialog(QDialog):
    """添加资产进度对话框"""
    
    def __init__(self, asset_name: str = "", parent=None):
        super().__init__(parent)
        self.asset_name = asset_name
        self.setWindowTitle("添加资产")
        self.setFixedSize(500, 200)
        self.setWindowFlags(Qt.WindowType.Dialog | Qt.WindowType.WindowTitleHint)
        self.setModal(True)
        
        self._init_ui()

    def showEvent(self, event):
        super().showEvent(event)
        host = self.parent().window() if self.parent() else None
        if host:
            geo = host.frameGeometry()
            self.move(
                geo.x() + (geo.width() - self.width()) // 2,
                geo.y() + (geo.height() - self.height()) // 2,
            )
            return
        screen = QApplication.primaryScreen()
        if screen:
            available = screen.availableGeometry()
            self.move(
                available.x() + (available.width() - self.width()) // 2,
                available.y() + (available.height() - self.height()) // 2,
            )

    def _init_ui(self):
        """初始化UI"""
        layout = QVBoxLayout(self)
        layout.setSpacing(15)
        layout.setContentsMargins(30, 30, 30, 30)
        
        # 标题
        title_text = f"正在添加资产: {self.asset_name}" if self.asset_name else "正在添加资产..."
        title_label = QLabel(title_text)
        title_font = QFont()
        title_font.setPointSize(12)
        title_font.setBold(True)
        title_label.setFont(title_font)
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title_label)
        
        # 状态标签
        self.status_label = QLabel("准备中...")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_label.setStyleSheet("color: #666666; font-size: 12px;")
        layout.addWidget(self.status_label)
        
        # 当前文件标签（显示正在处理的文件）
        self.file_label = QLabel("")
        self.file_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.file_label.setStyleSheet("color: #888888; font-size: 11px;")
        self.file_label.setWordWrap(True)
        layout.addWidget(self.file_label)
        
        # 进度条
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(True)
        self.progress_bar.setFixedHeight(25)
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                border: 2px solid #cccccc;
                border-radius: 5px;
                text-align: center;
                background-color: #f0f0f0;
            }
            QProgressBar::chunk {
                background-color: #4CAF50;
                border-radius: 3px;
            }
        """)
        layout.addWidget(self.progress_bar)
        
        layout.addStretch()
    
    def update_progress(self, current, total, message):
        """更新进度
        
        Args:
            current: 当前进度
            total: 总进度
            message: 状态消息
        """
        if total > 0:
            progress = int((current / total) * 100)
            self.progress_bar.setValue(progress)
        
        # 解析消息，如果包含文件名，分离显示
        if ":" in message:
            parts = message.split(":", 1)
            self.status_label.setText(parts[0] + ":")
            self.file_label.setText(parts[1].strip())
        else:
            self.status_label.setText(message)
            self.file_label.setText("")
        
        # 强制处理 UI 事件，确保进度条实时更新
        QApplication.processEvents()
        
        # 如果完成，更新标题和样式
        if current >= total:
            self.setWindowTitle("添加完成")
            self.status_label.setText("✅ 资产添加完成！")
            self.status_label.setStyleSheet("color: #4CAF50; font-weight: bold; font-size: 12px;")
            self.file_label.setText("")
            # 延迟关闭
            from PyQt6.QtCore import QTimer
            QTimer.singleShot(800, self.accept)
