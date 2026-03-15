# -*- coding: utf-8 -*-

"""
压缩包密码输入对话框
"""

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
    QLineEdit, QPushButton, QWidget
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QIcon

from core.logger import get_logger

logger = get_logger(__name__)


class PasswordDialog(QDialog):
    """压缩包密码输入对话框"""
    
    def __init__(self, archive_name: str, error_message: str = "", parent=None):
        """初始化对话框
        
        Args:
            archive_name: 压缩包文件名
            error_message: 错误提示信息（密码错误时显示）
            parent: 父窗口
        """
        super().__init__(parent)
        self.password = None
        self._setup_ui(archive_name, error_message)
    
    def _setup_ui(self, archive_name: str, error_message: str):
        """设置UI"""
        self.setWindowTitle("输入解压密码")
        self.setModal(True)
        self.setFixedWidth(400)
        
        layout = QVBoxLayout()
        layout.setSpacing(15)
        layout.setContentsMargins(20, 20, 20, 20)
        
        # 提示信息
        info_label = QLabel(f"压缩包需要密码才能解压：\n{archive_name}")
        info_label.setWordWrap(True)
        layout.addWidget(info_label)
        
        # 错误提示（如果有）
        if error_message:
            error_label = QLabel(f"❌ {error_message}")
            error_label.setStyleSheet("color: #f44336; font-weight: bold;")
            error_label.setWordWrap(True)
            layout.addWidget(error_label)
        
        # 密码输入框
        self.password_input = QLineEdit()
        self.password_input.setPlaceholderText("请输入解压密码")
        self.password_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.password_input.setMinimumHeight(38)
        self.password_input.returnPressed.connect(self._on_ok_clicked)
        layout.addWidget(self.password_input)
        
        # 按钮
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        
        cancel_btn = QPushButton("取消")
        cancel_btn.setObjectName("CancelButton")
        cancel_btn.setFixedWidth(100)
        cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(cancel_btn)
        
        ok_btn = QPushButton("确定")
        ok_btn.setObjectName("SaveButton")
        ok_btn.setFixedWidth(100)
        ok_btn.clicked.connect(self._on_ok_clicked)
        ok_btn.setDefault(True)
        button_layout.addWidget(ok_btn)
        
        layout.addLayout(button_layout)
        
        self.setLayout(layout)
        
        # 焦点设置到密码输入框
        self.password_input.setFocus()
    
    def _on_ok_clicked(self):
        """点击确定按钮"""
        password = self.password_input.text().strip()
        if not password:
            return
        
        self.password = password
        self.accept()
    
    def get_password(self) -> str:
        """获取用户输入的密码
        
        Returns:
            密码字符串，用户取消则返回空字符串
        """
        return self.password or ""
