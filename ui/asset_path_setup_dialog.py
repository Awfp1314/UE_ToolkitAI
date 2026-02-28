# -*- coding: utf-8 -*-
"""
资产库路径设置弹窗
"""

from pathlib import Path
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, 
    QLabel, QPushButton, QLineEdit, QFileDialog, QWidget
)
from PyQt6.QtCore import Qt, pyqtSignal, QPoint
from PyQt6.QtGui import QMouseEvent

from core.logger import get_logger


class AssetPathSetupDialog(QDialog):
    """资产库路径设置弹窗 - 自定义标题栏"""
    
    path_confirmed = pyqtSignal(str)  # 路径确认信号
    
    def __init__(self, parent=None, current_path: str = ""):
        super().__init__(parent)
        self.current_path = current_path
        self.drag_position = QPoint()  # 用于拖动窗口
        self.logger = get_logger(__name__)
        self.setup_ui()
        
    def setup_ui(self):
        """设置UI"""
        # 设置窗口图标
        from PyQt6.QtGui import QIcon
        icon_path = Path(__file__).parent.parent / "resources" / "tubiao.ico"
        if icon_path.exists():
            self.setWindowIcon(QIcon(str(icon_path)))
        
        self.setModal(True)
        self.setFixedSize(600, 380)
        
        # 无边框 + 透明背景
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        
        # 设置ObjectName
        self.setObjectName("AssetPathSetupDialog")
        
        # 创建容器
        container = QWidget()
        container.setObjectName("AssetPathSetupDialogContainer")
        
        # 容器主布局
        container_layout = QVBoxLayout()
        container_layout.setSpacing(0)
        container_layout.setContentsMargins(1, 1, 1, 1)  # 留出1px边距以显示容器边框
        
        # ===== 自定义标题栏 =====
        title_bar = QWidget()
        title_bar.setObjectName("AssetPathSetupDialogTitleBar")
        title_bar.setFixedHeight(50)
        title_bar_layout = QHBoxLayout()
        title_bar_layout.setContentsMargins(20, 0, 20, 0)
        title_bar_layout.setSpacing(10)
        
        # 图标
        title_icon = QLabel("📁")
        title_icon.setObjectName("AssetPathSetupDialogTitleIcon")
        title_bar_layout.addWidget(title_icon)
        
        # 标题
        title_label = QLabel("设置资产库路径")
        title_label.setObjectName("AssetPathSetupDialogTitleLabel")
        title_bar_layout.addWidget(title_label)
        title_bar_layout.addStretch()
        
        title_bar.setLayout(title_bar_layout)
        container_layout.addWidget(title_bar)
        
        # ===== 内容区域 =====
        content_widget = QWidget()
        content_widget.setObjectName("AssetPathSetupDialogContent")
        content_layout = QVBoxLayout()
        content_layout.setContentsMargins(30, 20, 30, 25)
        content_layout.setSpacing(15)
        
        # 描述文字
        desc_label = QLabel(
            "检测到资产库路径未设置或不存在，请选择一个文件夹作为资产库存储位置。\n"
            "资产库用于管理你的 UE 资产文件，包括模型、贴图、蓝图等。"
        )
        desc_label.setObjectName("AssetPathSetupDialogDescription")
        desc_label.setWordWrap(True)
        content_layout.addWidget(desc_label)
        
        # 路径标签
        path_label = QLabel("资产库路径")
        path_label.setObjectName("AssetPathSetupDialogLabel")
        content_layout.addWidget(path_label)
        
        # 路径输入行
        path_input_layout = QHBoxLayout()
        path_input_layout.setSpacing(10)
        
        # 路径输入框
        self.path_input = QLineEdit()
        self.path_input.setObjectName("AssetPathSetupDialogInput")
        self.path_input.setPlaceholderText("请选择资产库存储路径...")
        self.path_input.setText(self.current_path)
        self.path_input.textChanged.connect(self._on_path_changed)
        path_input_layout.addWidget(self.path_input)
        
        # 浏览按钮
        self.browse_button = QPushButton("浏览")
        self.browse_button.setObjectName("AssetPathSetupDialogBrowseBtn")
        self.browse_button.setFixedWidth(90)
        self.browse_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.browse_button.clicked.connect(self._browse_path)
        path_input_layout.addWidget(self.browse_button)
        
        content_layout.addLayout(path_input_layout)
        
        # 提示信息
        self.hint_label = QLabel("💡 建议选择一个专门的文件夹，避免与其他文件混淆")
        self.hint_label.setObjectName("AssetPathSetupDialogHint")
        content_layout.addWidget(self.hint_label)
        
        content_layout.addStretch()
        
        # 底部按钮区域
        button_layout = QHBoxLayout()
        button_layout.setSpacing(10)
        button_layout.addStretch()
        
        # 确认按钮（居中显示）
        self.confirm_button = QPushButton("确认")
        self.confirm_button.setObjectName("AssetPathSetupDialogConfirmBtn")
        self.confirm_button.setFixedSize(120, 36)
        self.confirm_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.confirm_button.clicked.connect(self._on_confirm)
        self.confirm_button.setEnabled(False)  # 初始禁用
        button_layout.addWidget(self.confirm_button)
        button_layout.addStretch()
        
        content_layout.addLayout(button_layout)
        
        content_widget.setLayout(content_layout)
        container_layout.addWidget(content_widget, 1)
        
        # 设置容器布局
        container.setLayout(container_layout)
        
        # 对话框布局
        dialog_layout = QVBoxLayout()
        dialog_layout.setContentsMargins(0, 0, 0, 0)
        dialog_layout.addWidget(container)
        self.setLayout(dialog_layout)
        
    def _browse_path(self):
        """浏览文件夹"""
        start_dir = self.path_input.text() or str(Path.home())
        folder = QFileDialog.getExistingDirectory(
            self,
            "选择资产库文件夹",
            start_dir,
            QFileDialog.Option.ShowDirsOnly | QFileDialog.Option.DontResolveSymlinks
        )
        
        if folder:
            self.path_input.setText(folder)
    
    def _on_path_changed(self, text: str):
        """路径改变时的处理"""
        # 检查路径是否有效
        is_valid = bool(text.strip())
        self.confirm_button.setEnabled(is_valid)
        
        # 更新提示信息
        if text.strip():
            path = Path(text)
            if path.exists():
                self.hint_label.setText("✅ 路径有效")
                self.hint_label.setProperty("valid", True)
            else:
                self.hint_label.setText("⚠️ 路径不存在，将自动创建")
                self.hint_label.setProperty("valid", False)
        else:
            self.hint_label.setText("💡 建议选择一个专门的文件夹，避免与其他文件混淆")
            self.hint_label.setProperty("valid", False)
        
        # 刷新样式
        self.hint_label.style().unpolish(self.hint_label)
        self.hint_label.style().polish(self.hint_label)
    
    def _on_confirm(self):
        """确认按钮点击"""
        path = self.path_input.text().strip()
        if path:
            self.path_confirmed.emit(path)
            self.accept()
    
    def get_selected_path(self) -> str:
        """获取选择的路径"""
        return self.path_input.text().strip()
    
    def mousePressEvent(self, event: QMouseEvent):
        """鼠标按下事件 - 记录拖动起始位置"""
        if event.button() == Qt.MouseButton.LeftButton:
            self.drag_position = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()
    
    def mouseMoveEvent(self, event: QMouseEvent):
        """鼠标移动事件 - 实现窗口拖动"""
        if event.buttons() == Qt.MouseButton.LeftButton and not self.drag_position.isNull():
            self.move(event.globalPosition().toPoint() - self.drag_position)
            event.accept()
