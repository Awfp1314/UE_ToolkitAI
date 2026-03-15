#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
批量添加资产进度对话框
显示批量添加资产的进度
"""

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QLabel, 
    QProgressBar, QPushButton, QHBoxLayout
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont

from core.logger import get_logger

logger = get_logger(__name__)


class BatchAddProgressDialog(QDialog):
    """批量添加资产进度对话框"""
    
    def __init__(self, total_count: int, parent=None):
        super().__init__(parent)
        self.total_count = total_count
        self.setWindowTitle("批量添加资产")
        self.setFixedSize(500, 220)
        self.setWindowFlags(Qt.WindowType.Dialog | Qt.WindowType.WindowTitleHint)
        self.setModal(True)
        
        self._init_ui()
    
    def _init_ui(self):
        """初始化UI"""
        layout = QVBoxLayout(self)
        layout.setSpacing(15)
        layout.setContentsMargins(30, 30, 30, 30)
        
        # 标题
        title_text = f"正在批量添加资产 (0/{self.total_count})"
        self.title_label = QLabel(title_text)
        title_font = QFont()
        title_font.setPointSize(12)
        title_font.setBold(True)
        self.title_label.setFont(title_font)
        self.title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.title_label)
        
        # 当前资产名称标签
        self.asset_label = QLabel("准备中...")
        self.asset_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.asset_label.setStyleSheet("color: #666666; font-size: 12px;")
        layout.addWidget(self.asset_label)
        
        # 状态标签（显示当前操作）
        self.status_label = QLabel("")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_label.setStyleSheet("color: #888888; font-size: 11px;")
        self.status_label.setWordWrap(True)
        layout.addWidget(self.status_label)
        
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
        
        # 停止按钮
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        
        self.stop_btn = QPushButton("⏹ 停止")
        self.stop_btn.setObjectName("CancelButton")
        self.stop_btn.setFixedSize(100, 35)
        self.stop_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        button_layout.addWidget(self.stop_btn)
        
        button_layout.addStretch()
        layout.addLayout(button_layout)
    
    def update_progress(self, current: int, total: int, message: str):
        """更新进度
        
        Args:
            current: 当前进度（第几个资产）
            total: 总数
            message: 状态消息（资产名称）
        """
        # 更新标题
        self.title_label.setText(f"正在批量添加资产 ({current}/{total})")
        
        # 更新当前资产名称
        self.asset_label.setText(f"正在添加: {message}")
        
        # 更新进度条
        if total > 0:
            progress = int((current / total) * 100)
            self.progress_bar.setValue(progress)
    
    def show_complete(self, success_count: int, fail_count: int):
        """显示完成状态
        
        Args:
            success_count: 成功数量
            fail_count: 失败数量
        """
        self.title_label.setText("批量添加完成")
        
        if fail_count == 0:
            self.asset_label.setText(f"✅ 成功添加 {success_count} 个资产！")
            self.asset_label.setStyleSheet("color: #4CAF50; font-weight: bold; font-size: 12px;")
        else:
            self.asset_label.setText(f"⚠️ 成功 {success_count} 个，失败 {fail_count} 个")
            self.asset_label.setStyleSheet("color: #e6a817; font-weight: bold; font-size: 12px;")
        
        self.status_label.setText("")
        self.progress_bar.setValue(100)
        
        # 隐藏停止按钮
        self.stop_btn.hide()
        
        # 延迟关闭
        from PyQt6.QtCore import QTimer
        QTimer.singleShot(1500, self.accept)
