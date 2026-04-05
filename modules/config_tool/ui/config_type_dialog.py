# -*- coding: utf-8 -*-

"""
配置类型选择对话框

参考 add_asset_dialog.py 的样式，提供两个选项卡：
- 项目设置：包含项目的所有配置文件
- 编辑器偏好：包含编辑器个人设置
"""

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QWidget, QFrame
)
from PyQt6.QtCore import Qt, pyqtSignal, QPoint, QEvent
from PyQt6.QtGui import QCursor

from core.logger import get_logger
from ..logic.config_model import ConfigType

logger = get_logger(__name__)


class ConfigTypeOption(QFrame):
    """配置类型选项卡片"""
    
    clicked = pyqtSignal()
    
    def __init__(self, icon: str, title: str, description: str, parent=None):
        super().__init__(parent)
        self.setObjectName("ConfigTypeOption")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedHeight(80)
        self._is_hovered = False
        self._is_selected = False
        
        self._init_ui(icon, title, description)
    
    def _init_ui(self, icon: str, title: str, description: str):
        """初始化UI"""
        layout = QHBoxLayout(self)
        layout.setContentsMargins(20, 15, 20, 15)
        layout.setSpacing(15)
        
        # 图标
        icon_label = QLabel(icon)
        icon_label.setObjectName("ConfigTypeIcon")
        icon_label.setFixedSize(40, 40)
        icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(icon_label)
        
        # 文本区域
        text_layout = QVBoxLayout()
        text_layout.setSpacing(5)
        
        title_label = QLabel(title)
        title_label.setObjectName("ConfigTypeTitle")
        text_layout.addWidget(title_label)
        
        desc_label = QLabel(description)
        desc_label.setObjectName("ConfigTypeDescription")
        desc_label.setWordWrap(True)
        text_layout.addWidget(desc_label)
        
        layout.addLayout(text_layout, 1)
    
    def set_selected(self, selected: bool):
        """设置选中状态"""
        self._is_selected = selected
        # 使用动态属性来改变样式
        self.setProperty("selected", selected)
        self.style().unpolish(self)
        self.style().polish(self)
        self.update()
    
    def enterEvent(self, event):
        """鼠标进入"""
        self._is_hovered = True
        self.update()
        super().enterEvent(event)
    
    def leaveEvent(self, event):
        """鼠标离开"""
        self._is_hovered = False
        self.update()
        super().leaveEvent(event)
    
    def mousePressEvent(self, event):
        """鼠标按下"""
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(event)


class ConfigTypeDialog(QDialog):
    """配置类型选择对话框"""
    
    type_selected = pyqtSignal(ConfigType)  # 发送选中的配置类型
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.selected_type = None
        
        self._init_ui()
    
    def _init_ui(self):
        """初始化UI"""
        self.setModal(True)
        self.setFixedSize(500, 400)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setObjectName("ConfigTypeDialog")
        
        # 主容器
        container = QWidget()
        container.setObjectName("ConfigTypeDialogContainer")
        
        main_layout = QVBoxLayout()
        main_layout.setSpacing(0)
        main_layout.setContentsMargins(0, 0, 0, 0)
        
        # 标题栏
        main_layout.addWidget(self._create_title_bar())
        
        # 内容区域
        content_widget = QWidget()
        content_widget.setObjectName("ConfigTypeDialogContent")
        content_layout = QVBoxLayout(content_widget)
        content_layout.setContentsMargins(30, 25, 30, 30)
        content_layout.setSpacing(20)
        
        # 标题
        title = QLabel("📦 选择配置类型")
        title.setObjectName("ConfigTypeDialogTitle")
        content_layout.addWidget(title)
        
        content_layout.addSpacing(10)
        
        # 项目设置选项
        self.project_settings_option = ConfigTypeOption(
            "📋",
            "项目设置",
            "包含项目的所有配置文件（Config/Default*.ini）"
        )
        self.project_settings_option.clicked.connect(
            lambda: self._on_option_clicked(ConfigType.PROJECT_SETTINGS)
        )
        content_layout.addWidget(self.project_settings_option)
        
        content_layout.addSpacing(10)
        
        # 编辑器偏好选项
        self.editor_prefs_option = ConfigTypeOption(
            "⚙️",
            "编辑器偏好",
            "包含编辑器个人设置（EditorPerProjectUserSettings.ini）"
        )
        self.editor_prefs_option.clicked.connect(
            lambda: self._on_option_clicked(ConfigType.EDITOR_PREFERENCES)
        )
        content_layout.addWidget(self.editor_prefs_option)
        
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
        
        self.next_btn = QPushButton("下一步")
        self.next_btn.setObjectName("ConfirmButton")
        self.next_btn.setFixedSize(90, 36)
        self.next_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.next_btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.next_btn.setEnabled(False)
        self.next_btn.clicked.connect(self._on_next_clicked)
        button_layout.addWidget(self.next_btn)
        
        content_layout.addLayout(button_layout)
        
        main_layout.addWidget(content_widget)
        container.setLayout(main_layout)
        
        dialog_layout = QVBoxLayout(self)
        dialog_layout.setContentsMargins(0, 0, 0, 0)
        dialog_layout.addWidget(container)
    
    def _create_title_bar(self):
        """创建标题栏"""
        title_bar = QWidget()
        title_bar.setObjectName("ConfigTypeDialogTitleBar")
        title_bar.setFixedHeight(50)
        
        layout = QHBoxLayout(title_bar)
        layout.setContentsMargins(25, 0, 25, 0)
        layout.setSpacing(10)
        
        title = QLabel("配置工具")
        title.setObjectName("ConfigTypeDialogTitleBarText")
        layout.addWidget(title)
        layout.addStretch()
        
        close_btn = QPushButton("✕")
        close_btn.setObjectName("ConfigTypeDialogCloseButton")
        close_btn.setFixedSize(32, 32)
        close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        close_btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        close_btn.clicked.connect(self._on_close_clicked, Qt.ConnectionType.UniqueConnection)
        layout.addWidget(close_btn)
        
        return title_bar
    
    def _on_close_clicked(self):
        """关闭按钮被点击"""
        logger.info("配置类型对话框关闭按钮被点击")
        # 立即关闭对话框，防止事件传播
        self.reject()
        # 不需要额外处理，reject() 会关闭对话框
    
    def _on_option_clicked(self, config_type: ConfigType):
        """选项被点击"""
        self.selected_type = config_type
        
        # 更新选中状态
        self.project_settings_option.set_selected(config_type == ConfigType.PROJECT_SETTINGS)
        self.editor_prefs_option.set_selected(config_type == ConfigType.EDITOR_PREFERENCES)
        
        # 启用下一步按钮
        self.next_btn.setEnabled(True)
    
    def _on_next_clicked(self):
        """下一步按钮被点击"""
        if self.selected_type:
            self.type_selected.emit(self.selected_type)
            self.accept()
    
    def showEvent(self, event):
        """显示事件 - 在窗口显示时居中"""
        super().showEvent(event)
        logger.info("ConfigTypeDialog showEvent 被调用")
        # 在对话框显示时居中
        self._center_dialog()
    
    def _center_dialog(self):
        """居中到父窗口或屏幕"""
        self.adjustSize()
        
        if self.parent():
            # 使用 mapToGlobal 获取父窗口的全局坐标
            parent_global = self.parent().mapToGlobal(self.parent().rect().topLeft())
            x = parent_global.x() + (self.parent().width() - self.width()) // 2
            y = parent_global.y() + (self.parent().height() - self.height()) // 2
            self.move(x, y)
            logger.info(f"对话框居中到父窗口: ({x}, {y}), 对话框尺寸: {self.width()}x{self.height()}")
        else:
            # 居中到屏幕
            from PyQt6.QtWidgets import QApplication
            screen = QApplication.primaryScreen().availableGeometry()
            x = screen.x() + (screen.width() - self.width()) // 2
            y = screen.y() + (screen.height() - self.height()) // 2
            self.move(x, y)
            logger.info(f"对话框居中到屏幕: ({x}, {y}), 屏幕尺寸: {screen.width()}x{screen.height()}")
    
    def _center_on_screen(self):
        """兼容旧方法名"""
        self._center_dialog()
