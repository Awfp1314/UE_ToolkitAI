# -*- coding: utf-8 -*-

"""
消息对话框
提供与项目UI风格一致的消息提示对话框
"""

from PyQt6.QtWidgets import (
    QApplication, QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QWidget
)
from PyQt6.QtCore import Qt, QTimer, QPoint
from PyQt6.QtGui import QMouseEvent


class MessageDialog(QDialog):
    """统一风格的消息对话框"""

    def __init__(self, title, message, message_type="info", show_settings_button=False, parent=None):
        """初始化对话框

        Args:
            title: 对话框标题
            message: 消息内容
            message_type: 消息类型 ("info", "warning", "error", "success")
            show_settings_button: 是否显示"去设置"按钮
            parent: 父窗口
        """
        super().__init__(parent)
        self.title_text = title
        self.message_text = message
        self.message_type = message_type
        self.show_settings_button = show_settings_button
        self.drag_position = QPoint()
        self.goto_settings = False  # 是否点击了"去设置"

        self.setModal(True)
        self.setFixedSize(420, 200)

        # 无边框 + 透明背景支持
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        # 设置ObjectName
        self.setObjectName("MessageDialog")

        self._init_ui()

    def _init_ui(self):
        """初始化UI"""
        # 创建一个容器widget来承载所有内容
        container = QWidget()
        container.setObjectName("MessageDialogContainer")

        # 主布局
        main_layout = QVBoxLayout()
        main_layout.setSpacing(0)
        main_layout.setContentsMargins(0, 0, 0, 0)

        # 自定义标题栏
        title_bar = QWidget()
        title_bar.setObjectName("MessageDialogTitleBar")
        title_bar.setFixedHeight(45)
        title_bar_layout = QHBoxLayout()
        title_bar_layout.setSpacing(0)
        title_bar_layout.setContentsMargins(0, 0, 0, 0)

        # 图标 + 标题
        icon_label = QLabel(self._get_icon())
        icon_label.setObjectName("MessageDialogIcon")
        icon_label.setFixedWidth(50)
        icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title_bar_layout.addWidget(icon_label)

        title_label = QLabel(self.title_text)
        title_label.setObjectName("MessageDialogTitleLabel")
        title_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        title_bar_layout.addWidget(title_label, 1)

        title_bar.setLayout(title_bar_layout)
        main_layout.addWidget(title_bar)

        # 内容布局
        content_layout = QVBoxLayout()
        content_layout.setSpacing(20)
        content_layout.setContentsMargins(20, 20, 20, 20)

        # 消息标签
        message_label = QLabel(self.message_text)
        message_label.setObjectName("MessageDialogText")
        message_label.setWordWrap(True)
        message_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        content_layout.addWidget(message_label)

        # 按钮
        button_layout = QHBoxLayout()
        button_layout.setSpacing(10)
        button_layout.addStretch()

        if self.show_settings_button:
            # 显示"去设置"和"取消"按钮
            settings_btn = QPushButton("去设置")
            settings_btn.setObjectName("MessageDialogSettingsBtn")
            settings_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            settings_btn.setFixedSize(80, 32)
            settings_btn.clicked.connect(self._on_goto_settings)
            button_layout.addWidget(settings_btn)

            cancel_btn = QPushButton("取消")
            cancel_btn.setObjectName("MessageDialogCancelBtn")
            cancel_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            cancel_btn.setFixedSize(80, 32)
            cancel_btn.clicked.connect(self.reject)
            button_layout.addWidget(cancel_btn)
        else:
            # 只显示"确定"按钮
            ok_btn = QPushButton("确定")
            ok_btn.setObjectName("MessageDialogOkBtn")
            ok_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            ok_btn.setFixedSize(80, 32)
            ok_btn.clicked.connect(self.accept)
            button_layout.addWidget(ok_btn)

        button_layout.addStretch()

        content_layout.addLayout(button_layout)
        main_layout.addLayout(content_layout, 1)

        # 将主布局设置到容器
        container.setLayout(main_layout)

        # 对话框布局
        dialog_layout = QVBoxLayout()
        dialog_layout.setContentsMargins(0, 0, 0, 0)
        dialog_layout.addWidget(container)
        self.setLayout(dialog_layout)

    def _get_icon(self):
        """根据消息类型返回图标"""
        icons = {
            "info": "ℹ️",
            "warning": "⚠️",
            "error": "❌",
            "success": "✅"
        }
        return icons.get(self.message_type, "ℹ️")
    
    def _on_goto_settings(self):
        """点击"去设置"按钮"""
        self.goto_settings = True
        self.accept()

    def center_on_screen(self):
        """将对话框居中显示"""
        from core.logger import get_logger
        logger = get_logger(__name__)

        # 向上查找真正的主窗口
        main_window = None
        parent = self.parent()

        while parent:
            # 查找有窗口标志的顶层窗口
            if parent.isWindow() and parent.isVisible():
                main_window = parent
                break
            parent = parent.parent()

        if main_window:
            # 使用主窗口的屏幕坐标进行居中
            main_geo = main_window.frameGeometry()

            dialog_width = self.width()
            dialog_height = self.height()

            logger.info(f"主窗口几何: x={main_geo.x()}, y={main_geo.y()}, w={main_geo.width()}, h={main_geo.height()}")
            logger.info(f"对话框尺寸: w={dialog_width}, h={dialog_height}")

            # 计算对话框应该出现的位置（相对于主窗口居中）
            dialog_x = main_geo.x() + (main_geo.width() - dialog_width) // 2
            dialog_y = main_geo.y() + (main_geo.height() - dialog_height) // 2

            # 移动对话框到计算出的位置
            self.move(dialog_x, dialog_y)
            logger.info(f"对话框已居中到: ({dialog_x}, {dialog_y})")
        else:
            # 如果没有找到主窗口，相对于屏幕居中
            logger.info("未找到主窗口，使用屏幕居中")
            screen = QApplication.primaryScreen()
            if screen:
                screen_geo = screen.availableGeometry()
                dialog_x = (screen_geo.width() - self.width()) // 2
                dialog_y = (screen_geo.height() - self.height()) // 2
                self.move(dialog_x, dialog_y)
                logger.info(f"对话框相对屏幕居中: ({dialog_x}, {dialog_y})")

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

    def showEvent(self, event):
        """显示事件 - 在对话框显示时居中"""
        super().showEvent(event)
        # 在对话框真正显示后再居中
        self.center_on_screen()


def show_message(title, message, message_type="info", parent=None):
    """便捷函数：显示消息对话框
    
    Args:
        title: 对话框标题
        message: 消息内容
        message_type: 消息类型 ("info", "warning", "error", "success")
        parent: 父窗口
        
    Returns:
        对话框结果
    """
    dialog = MessageDialog(title, message, message_type, parent)
    return dialog.exec()
