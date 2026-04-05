# -*- coding: utf-8 -*-

"""
配置信息输入对话框

用于输入配置名称和描述
- 配置名称：必填，不能为空或纯空白
- 配置描述：可选
"""

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QLineEdit, QTextEdit, QWidget
)
from PyQt6.QtCore import Qt, pyqtSignal, QPoint, QEvent
from PyQt6.QtGui import QCursor

from core.logger import get_logger

logger = get_logger(__name__)


class ConfigInfoDialog(QDialog):
    """配置信息输入对话框"""
    
    info_confirmed = pyqtSignal(str, str)  # (name, description)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.drag_position = QPoint()
        
        self._init_ui()
    
    def _init_ui(self):
        """初始化UI"""
        self.setModal(True)
        self.setFixedSize(500, 380)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setObjectName("ConfigInfoDialog")
        
        # 主容器
        container = QWidget()
        container.setObjectName("ConfigInfoDialogContainer")
        
        main_layout = QVBoxLayout()
        main_layout.setSpacing(0)
        main_layout.setContentsMargins(0, 0, 0, 0)
        
        # 标题栏
        main_layout.addWidget(self._create_title_bar())
        
        # 内容区域
        content_widget = QWidget()
        content_widget.setObjectName("ConfigInfoDialogContent")
        content_layout = QVBoxLayout(content_widget)
        content_layout.setContentsMargins(30, 25, 30, 30)
        content_layout.setSpacing(18)
        
        # 配置名称
        name_label = QLabel("配置名称 *")
        name_label.setObjectName("SectionLabel")
        content_layout.addWidget(name_label)
        
        self.name_input = QLineEdit()
        self.name_input.setObjectName("ConfigInfoInput")
        self.name_input.setPlaceholderText("输入配置名称...")
        self.name_input.setFixedHeight(36)
        self.name_input.textChanged.connect(self._on_name_changed)
        content_layout.addWidget(self.name_input)
        
        content_layout.addSpacing(5)
        
        # 配置描述
        desc_label = QLabel("配置描述（可选）")
        desc_label.setObjectName("SectionLabel")
        content_layout.addWidget(desc_label)
        
        self.desc_input = QTextEdit()
        self.desc_input.setObjectName("ConfigInfoTextEdit")
        self.desc_input.setPlaceholderText("输入配置描述...")
        self.desc_input.setFixedHeight(100)
        content_layout.addWidget(self.desc_input)
        
        # 错误提示
        self.error_label = QLabel("")
        self.error_label.setObjectName("ErrorLabel")
        self.error_label.setWordWrap(True)
        self.error_label.setFixedHeight(25)
        self.error_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        content_layout.addWidget(self.error_label)
        
        content_layout.addStretch()
        
        # 按钮区域
        button_layout = QHBoxLayout()
        button_layout.setSpacing(10)
        button_layout.addStretch()
        
        cancel_btn = QPushButton("取消")
        cancel_btn.setObjectName("CancelButton")
        cancel_btn.setFixedSize(80, 36)
        cancel_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        cancel_btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(cancel_btn)
        
        self.confirm_btn = QPushButton("确认")
        self.confirm_btn.setObjectName("ConfirmButton")
        self.confirm_btn.setFixedSize(80, 36)
        self.confirm_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.confirm_btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.confirm_btn.setEnabled(False)
        self.confirm_btn.clicked.connect(self._on_confirm_clicked)
        button_layout.addWidget(self.confirm_btn)
        
        content_layout.addLayout(button_layout)
        
        main_layout.addWidget(content_widget)
        container.setLayout(main_layout)
        
        dialog_layout = QVBoxLayout(self)
        dialog_layout.setContentsMargins(0, 0, 0, 0)
        dialog_layout.addWidget(container)
    
    def _create_title_bar(self):
        """创建标题栏"""
        title_bar = QWidget()
        title_bar.setObjectName("ConfigInfoDialogTitleBar")
        title_bar.setFixedHeight(50)
        
        layout = QHBoxLayout(title_bar)
        layout.setContentsMargins(25, 0, 25, 0)
        layout.setSpacing(10)
        
        title = QLabel("配置信息")
        title.setObjectName("ConfigInfoDialogTitleBarText")
        layout.addWidget(title)
        layout.addStretch()
        
        close_btn = QPushButton("✕")
        close_btn.setObjectName("ConfigInfoDialogCloseButton")
        close_btn.setFixedSize(32, 32)
        close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        close_btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        close_btn.clicked.connect(self._on_close_clicked)
        layout.addWidget(close_btn)
        
        # 使用事件过滤器而不是直接赋值
        title_bar.installEventFilter(self)
        return title_bar
    
    def eventFilter(self, obj, event):
        """事件过滤器 - 处理标题栏拖动"""
        if obj.objectName() == "ConfigInfoDialogTitleBar":
            if event.type() == QEvent.Type.MouseButtonPress:
                if event.button() == Qt.MouseButton.LeftButton:
                    self.drag_position = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
                    event.accept()
                    return True  # 拦截事件，防止传播到子控件
            elif event.type() == QEvent.Type.MouseMove:
                if event.buttons() == Qt.MouseButton.LeftButton and not self.drag_position.isNull():
                    self.move(event.globalPosition().toPoint() - self.drag_position)
                    event.accept()
                    return True  # 拦截事件
            elif event.type() == QEvent.Type.MouseButtonRelease:
                if event.button() == Qt.MouseButton.LeftButton:
                    self.drag_position = QPoint()  # 清空拖动位置
                    # 拖动结束后强制刷新样式
                    self.style().unpolish(self)
                    self.style().polish(self)
                    self.update()
                    # 刷新所有子控件的样式
                    for child in self.findChildren(QWidget):
                        child.style().unpolish(child)
                        child.style().polish(child)
                        child.update()
                    event.accept()
                    return True
        return super().eventFilter(obj, event)
    
    def _on_name_changed(self):
        """名称输入改变"""
        name = self.name_input.text().strip()
        
        # 清除错误提示
        self.error_label.setText("")
        
        # 验证名称
        is_valid = self._validate_name(name)
        self.confirm_btn.setEnabled(is_valid)
    
    def _validate_name(self, name: str) -> bool:
        """验证配置名称
        
        Args:
            name: 配置名称
            
        Returns:
            是否有效
        """
        if not name or not name.strip():
            return False
        
        if len(name) > 100:
            self.error_label.setText("配置名称不能超过 100 个字符")
            return False
        
        # 检查非法字符
        invalid_chars = '<>:"/\\|?*'
        if any(c in name for c in invalid_chars):
            self.error_label.setText(f"配置名称不能包含以下字符: {invalid_chars}")
            return False
        
        return True
    
    def _on_confirm_clicked(self):
        """确认按钮被点击"""
        name = self.name_input.text().strip()
        description = self.desc_input.toPlainText().strip()
        
        # 最终验证
        if not self._validate_name(name):
            return
        
        self.info_confirmed.emit(name, description)
        self.accept()
    
    def _on_close_clicked(self):
        """关闭按钮被点击"""
        self.reject()
    
    def showEvent(self, event):
        """显示事件 - 在窗口显示时居中"""
        super().showEvent(event)
        logger.info("ConfigInfoDialog showEvent 被调用")
        # 使用 QTimer 延迟到事件循环下一轮执行
        from PyQt6.QtCore import QTimer
        QTimer.singleShot(0, self._center_on_screen)
    
    def _center_on_screen(self):
        """居中到屏幕"""
        # 确保窗口已经显示并有正确的尺寸
        self.adjustSize()
        
        if self.parent():
            parent_geo = self.parent().geometry()
            x = parent_geo.x() + (parent_geo.width() - self.width()) // 2
            y = parent_geo.y() + (parent_geo.height() - self.height()) // 2
            self.move(x, y)
            logger.info(f"对话框居中到父窗口: ({x}, {y})")
        else:
            # 居中到屏幕
            screen = self.screen().geometry()
            x = (screen.width() - self.width()) // 2
            y = (screen.height() - self.height()) // 2
            self.move(x, y)
            logger.info(f"对话框居中到屏幕: ({x}, {y})")
    
    def get_config_info(self) -> tuple[str, str]:
        """获取配置信息
        
        Returns:
            (name, description)
        """
        return (
            self.name_input.text().strip(),
            self.desc_input.toPlainText().strip()
        )
