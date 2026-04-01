# -*- coding: utf-8 -*-

"""
问题反馈对话框
"""

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QTextEdit, QLineEdit
)
from modules.asset_manager.ui.message_dialog import MessageDialog
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont
import requests
import json


class FeedbackDialog(QDialog):
    """问题反馈对话框"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("问题反馈")
        self.setFixedSize(500, 400)
        self.setWindowFlags(Qt.WindowType.Dialog | Qt.WindowType.WindowCloseButtonHint)
        
        self.init_ui()
        
    def init_ui(self):
        """初始化UI"""
        # 设置窗口图标
        from pathlib import Path
        from PyQt6.QtGui import QIcon
        icon_path = Path(__file__).parent.parent.parent / "resources" / "tubiao.ico"
        if icon_path.exists():
            self.setWindowIcon(QIcon(str(icon_path)))
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)
        
        # 标题
        title_label = QLabel("问题反馈")
        title_font = QFont()
        title_font.setPointSize(14)
        title_font.setBold(True)
        title_label.setFont(title_font)
        layout.addWidget(title_label)
        
        # 说明文字
        desc_label = QLabel("请描述您遇到的问题或建议，我们会尽快处理")
        desc_label.setStyleSheet("color: #888;")
        layout.addWidget(desc_label)
        
        # 问题描述
        problem_label = QLabel("问题描述:")
        layout.addWidget(problem_label)
        
        self.problem_text = QTextEdit()
        self.problem_text.setPlaceholderText("请详细描述您遇到的问题或建议...")
        self.problem_text.setMinimumHeight(200)
        layout.addWidget(self.problem_text)
        
        # 按钮区域
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        
        cancel_btn = QPushButton("取消")
        cancel_btn.setFixedWidth(80)
        cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(cancel_btn)
        
        submit_btn = QPushButton("提交")
        submit_btn.setFixedWidth(80)
        submit_btn.setDefault(True)
        submit_btn.clicked.connect(self.submit_feedback)
        button_layout.addWidget(submit_btn)
        
        layout.addLayout(button_layout)
        
        # 应用样式
        try:
            from core.utils.style_system import get_current_theme
            is_light = get_current_theme() == "modern_light"
        except Exception:
            is_light = False
        
        if is_light:
            self.setStyleSheet("""
                QDialog {
                    background-color: #f5f5f5;
                    color: #1a1a1a;
                }
                QLabel {
                    color: #1a1a1a;
                }
                QTextEdit {
                    background-color: #ffffff;
                    border: 1px solid rgba(0, 0, 0, 0.12);
                    border-radius: 4px;
                    padding: 8px;
                    color: #1a1a1a;
                }
                QTextEdit:focus {
                    border: 1px solid #7c3aed;
                }
                QPushButton {
                    background-color: #7c3aed;
                    color: white;
                    border: none;
                    border-radius: 4px;
                    padding: 8px 16px;
                    font-weight: bold;
                }
                QPushButton:hover {
                    background-color: #8b5cf6;
                }
                QPushButton:pressed {
                    background-color: #6d28d9;
                }
            """)
        else:
            self.setStyleSheet("""
                QDialog {
                    background-color: #1e1e1e;
                    color: #ffffff;
                }
                QLabel {
                    color: #ffffff;
                }
                QTextEdit {
                    background-color: #2d2d2d;
                    border: 1px solid #3d3d3d;
                    border-radius: 4px;
                    padding: 8px;
                    color: #ffffff;
                }
                QTextEdit:focus {
                    border: 1px solid #7c3aed;
                }
                QPushButton {
                    background-color: #7c3aed;
                    color: white;
                    border: none;
                    border-radius: 4px;
                    padding: 8px 16px;
                    font-weight: bold;
                }
                QPushButton:hover {
                    background-color: #8b5cf6;
                }
                QPushButton:pressed {
                    background-color: #6d28d9;
                }
            """)
    
    def submit_feedback(self):
        """提交反馈"""
        problem = self.problem_text.toPlainText().strip()
        
        if not problem:
            MessageDialog("提示", "请输入问题描述", "warning", parent=self).exec()
            return
        
        # 发送到服务器
        try:
            print(f"正在提交反馈到服务器...")
            
            from core.server_config import get_server_base_url
            feedback_url = f"{get_server_base_url()}/api/feedback"
            
            response = requests.post(
                feedback_url,
                json={
                    "content": problem
                },
                timeout=5
            )
            
            print(f"响应状态码: {response.status_code}")
            print(f"响应内容: {response.text}")
            
            if response.status_code == 200:
                result = response.json()
                if result.get('success'):
                    MessageDialog("成功", "感谢您的反馈！我们会尽快处理", "success", parent=self).exec()
                    self.accept()
                else:
                    error_msg = result.get('error', '未知错误')
                    MessageDialog("失败", f"提交失败: {error_msg}", "warning", parent=self).exec()
            else:
                try:
                    error_data = response.json()
                    error_msg = error_data.get('error', response.text)
                except:
                    error_msg = response.text
                MessageDialog("失败", f"提交失败 ({response.status_code}): {error_msg}", "warning", parent=self).exec()
        except requests.exceptions.ConnectionError as e:
            print(f"连接错误: {e}")
            MessageDialog("连接错误", "无法连接到服务器，请确保服务器正在运行", "error", parent=self).exec()
        except requests.exceptions.Timeout as e:
            print(f"超时错误: {e}")
            MessageDialog("超时", "请求超时，请稍后重试", "warning", parent=self).exec()
        except Exception as e:
            print(f"未知错误: {type(e).__name__}: {e}")
            import traceback
            traceback.print_exc()
            MessageDialog("错误", f"提交失败: {str(e)}", "error", parent=self).exec()
