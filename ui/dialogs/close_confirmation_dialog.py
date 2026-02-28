# -*- coding: utf-8 -*-

"""
关闭确认对话框 - 现代化重新设计

更简洁、更美观的关闭确认对话框，支持：
- 直接关闭程序
- 最小化到托盘
- 取消操作
- 记住用户选择
"""

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QWidget, QCheckBox, QGraphicsDropShadowEffect
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPainter, QColor, QPen, QPainterPath
from core.logger import get_logger

logger = get_logger(__name__)


class CustomCheckBox(QCheckBox):
    """自定义复选框，选中时显示对勾"""

    def __init__(self, text="", parent=None):
        super().__init__(text, parent)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)

    def paintEvent(self, event):
        """重写绘制事件以绘制对勾"""
        super().paintEvent(event)

        if self.isChecked():
            painter = QPainter(self)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)

            from PyQt6.QtWidgets import QStyleOptionButton
            option = QStyleOptionButton()
            option.initFrom(self)

            indicator_rect = self.style().subElementRect(
                self.style().SubElement.SE_CheckBoxIndicator,
                option,
                self
            )

            painter.setPen(QPen(QColor(255, 255, 255), 2, Qt.PenStyle.SolidLine))

            path = QPainterPath()
            x = indicator_rect.x() + 4
            y = indicator_rect.y() + 4
            w = indicator_rect.width() - 8
            h = indicator_rect.height() - 8

            path.moveTo(x + w * 0.2, y + h * 0.5)
            path.lineTo(x + w * 0.4, y + h * 0.7)
            path.lineTo(x + w * 0.8, y + h * 0.3)

            painter.drawPath(path)
            painter.end()


class CloseConfirmationDialog(QDialog):
    """关闭确认对话框"""

    RESULT_CLOSE = 1
    RESULT_MINIMIZE = 2
    RESULT_CANCEL = 0

    def __init__(self, parent=None):
        super().__init__(parent)
        self.result_action = self.RESULT_CANCEL
        self.remember_choice = False
        self.init_ui()

    def init_ui(self):
        """初始化界面"""
        from pathlib import Path
        from PyQt6.QtGui import QIcon
        icon_path = Path(__file__).parent.parent.parent / "resources" / "tubiao.ico"
        if icon_path.exists():
            self.setWindowIcon(QIcon(str(icon_path)))

        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.Dialog |
            Qt.WindowType.WindowStaysOnTopHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setModal(True)
        self.setFixedSize(400, 220)

        self.setStyleSheet(self._get_inline_styles())

        # 主容器
        main_container = QWidget()
        main_container.setObjectName("CloseDialogContainer")

        container_layout = QVBoxLayout(main_container)
        container_layout.setContentsMargins(0, 0, 0, 0)
        container_layout.setSpacing(0)

        # === 标题栏 ===
        title_bar = QWidget()
        title_bar.setObjectName("CloseDialogTitleBar")
        title_bar.setFixedHeight(50)
        title_bar_layout = QHBoxLayout(title_bar)
        title_bar_layout.setContentsMargins(24, 0, 16, 0)

        title_label = QLabel("关闭程序")
        title_label.setObjectName("CloseDialogTitle")
        title_bar_layout.addWidget(title_label)

        title_bar_layout.addStretch()

        close_btn = QPushButton("✕")
        close_btn.setObjectName("CloseDialogXButton")
        close_btn.setFixedSize(28, 28)
        close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        close_btn.clicked.connect(self._on_cancel_clicked)
        title_bar_layout.addWidget(close_btn)

        container_layout.addWidget(title_bar)

        # === 内容区 ===
        content = QWidget()
        content.setObjectName("CloseDialogContent")
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(24, 16, 24, 8)
        content_layout.setSpacing(12)

        message_label = QLabel("选择关闭方式")
        message_label.setObjectName("CloseDialogMessage")
        content_layout.addWidget(message_label)

        self.remember_checkbox = CustomCheckBox("记住我的选择")
        self.remember_checkbox.setObjectName("CloseDialogCheckbox")
        self.remember_checkbox.setCursor(Qt.CursorShape.PointingHandCursor)
        content_layout.addWidget(self.remember_checkbox)

        container_layout.addWidget(content)

        # === 底部按钮栏 ===
        button_bar = QWidget()
        button_bar.setObjectName("CloseDialogButtonBar")
        button_bar.setFixedHeight(60)
        button_layout = QHBoxLayout(button_bar)
        button_layout.setContentsMargins(24, 0, 24, 0)
        button_layout.setSpacing(10)

        button_layout.addStretch()

        cancel_btn = QPushButton("取消")
        cancel_btn.setObjectName("CloseDialogCancelButton")
        cancel_btn.setFixedSize(80, 36)
        cancel_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        cancel_btn.clicked.connect(self._on_cancel_clicked)
        button_layout.addWidget(cancel_btn)

        minimize_btn = QPushButton("最小化")
        minimize_btn.setObjectName("CloseDialogMinimizeButton")
        minimize_btn.setFixedSize(90, 36)
        minimize_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        minimize_btn.clicked.connect(self._on_minimize_clicked)
        button_layout.addWidget(minimize_btn)

        close_action_btn = QPushButton("退出")
        close_action_btn.setObjectName("CloseDialogCloseButton")
        close_action_btn.setFixedSize(80, 36)
        close_action_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        close_action_btn.clicked.connect(self._on_close_clicked)
        button_layout.addWidget(close_action_btn)

        container_layout.addWidget(button_bar)

        # 设置主布局
        dialog_layout = QVBoxLayout(self)
        dialog_layout.setContentsMargins(0, 0, 0, 0)
        dialog_layout.addWidget(main_container)

    def _on_close_clicked(self):
        """直接关闭"""
        self.result_action = self.RESULT_CLOSE
        self.remember_choice = self.remember_checkbox.isChecked()
        logger.info(f"用户选择：直接关闭 (记住选择: {self.remember_choice})")
        self.accept()

    def _on_minimize_clicked(self):
        """最小化到托盘"""
        self.result_action = self.RESULT_MINIMIZE
        self.remember_choice = self.remember_checkbox.isChecked()
        logger.info(f"用户选择：最小化到托盘 (记住选择: {self.remember_choice})")
        self.accept()

    def _on_cancel_clicked(self):
        """取消"""
        self.result_action = self.RESULT_CANCEL
        self.remember_choice = False
        logger.info("用户取消关闭操作")
        self.reject()

    def center_on_parent(self):
        """居中显示在父窗口"""
        if self.parent():
            parent_geometry = self.parent().frameGeometry()
            x = parent_geometry.x() + (parent_geometry.width() - self.width()) // 2
            y = parent_geometry.y() + (parent_geometry.height() - self.height()) // 2
            self.move(x, y)

    def showEvent(self, event):
        """显示事件"""
        super().showEvent(event)
        self.center_on_parent()

    @staticmethod
    def ask_close_action(parent=None):
        """静态方法：显示对话框并返回用户选择"""
        dialog = CloseConfirmationDialog(parent)
        dialog.exec()
        return dialog.result_action, dialog.remember_choice

    def _get_inline_styles(self):
        """获取内联样式 - 根据当前主题返回对应样式"""
        try:
            from core.utils.style_system import get_current_theme
            is_light = get_current_theme() == "modern_light"
        except Exception:
            is_light = False
        
        if is_light:
            return self._get_light_styles()
        return self._get_dark_styles()
    
    def _get_light_styles(self):
        return """
            #CloseDialogContainer {
                background: #f5f5f5;
                border: 1px solid rgba(0, 0, 0, 0.12);
                border-radius: 0px;
            }
            #CloseDialogTitleBar {
                background: #eeeeee;
                border-bottom: 1px solid rgba(0, 0, 0, 0.08);
            }
            #CloseDialogTitle {
                color: #1a1a1a;
                font-size: 16px;
                font-weight: 600;
                background: transparent;
            }
            #CloseDialogXButton {
                background: transparent;
                color: rgba(0, 0, 0, 0.5);
                border: none;
                border-radius: 6px;
                font-size: 14px;
                font-weight: 300;
            }
            #CloseDialogXButton:hover {
                background: rgba(0, 0, 0, 0.08);
                color: #000000;
            }
            #CloseDialogContent { background: transparent; }
            #CloseDialogMessage {
                color: rgba(0, 0, 0, 0.55);
                font-size: 13px;
                background: transparent;
            }
            #CloseDialogCheckbox {
                color: rgba(0, 0, 0, 0.55);
                font-size: 13px;
                spacing: 8px;
            }
            #CloseDialogCheckbox::indicator {
                width: 16px; height: 16px;
                border-radius: 0px;
                border: 1px solid rgba(0, 0, 0, 0.2);
                background: rgba(0, 0, 0, 0.05);
            }
            #CloseDialogCheckbox::indicator:hover {
                border-color: rgba(74, 158, 255, 0.6);
                background: rgba(74, 158, 255, 0.1);
            }
            #CloseDialogCheckbox::indicator:checked {
                background: #4a9eff;
                border-color: #4a9eff;
            }
            #CloseDialogButtonBar {
                background: #eeeeee;
                border-top: 1px solid rgba(0, 0, 0, 0.06);
            }
            #CloseDialogCancelButton {
                background: rgba(0, 0, 0, 0.05);
                border: none; border-radius: 8px;
                color: rgba(0, 0, 0, 0.6);
                font-size: 13px; font-weight: 500;
            }
            #CloseDialogCancelButton:hover {
                background: rgba(0, 0, 0, 0.08);
                color: #000000;
            }
            #CloseDialogCancelButton:pressed { background: rgba(0, 0, 0, 0.12); }
            #CloseDialogMinimizeButton {
                background: #4a9eff;
                border: none; border-radius: 8px;
                color: #ffffff;
                font-size: 13px; font-weight: 600;
            }
            #CloseDialogMinimizeButton:hover { background: #5aa9ff; }
            #CloseDialogMinimizeButton:pressed { background: #3a8eef; }
            #CloseDialogCloseButton {
                background: rgba(239, 68, 68, 0.1);
                border: none; border-radius: 8px;
                color: #ef4444;
                font-size: 13px; font-weight: 600;
            }
            #CloseDialogCloseButton:hover {
                background: rgba(239, 68, 68, 0.18);
                color: #dc2626;
            }
            #CloseDialogCloseButton:pressed { background: rgba(239, 68, 68, 0.25); }
        """
    
    def _get_dark_styles(self):
        return """
            /* 主容器 */
            #CloseDialogContainer {
                background: #1c1c1c;
                border: 1px solid rgba(255, 255, 255, 0.15);
                border-radius: 0px;
            }

            /* 标题栏 */
            #CloseDialogTitleBar {
                background: #252525;
                border-bottom: 1px solid rgba(255, 255, 255, 0.1);
            }

            /* 标题 */
            #CloseDialogTitle {
                color: #ffffff;
                font-size: 16px;
                font-weight: 600;
                background: transparent;
            }

            /* 关闭 X 按钮 */
            #CloseDialogXButton {
                background: transparent;
                color: rgba(255, 255, 255, 0.7);
                border: none;
                border-radius: 6px;
                font-size: 14px;
                font-weight: 300;
            }

            #CloseDialogXButton:hover {
                background: rgba(255, 255, 255, 0.15);
                color: #ffffff;
            }

            /* 内容区 */
            #CloseDialogContent {
                background: transparent;
            }

            /* 消息文本 */
            #CloseDialogMessage {
                color: rgba(255, 255, 255, 0.55);
                font-size: 13px;
                background: transparent;
            }

            /* 复选框 */
            #CloseDialogCheckbox {
                color: rgba(255, 255, 255, 0.55);
                font-size: 13px;
                spacing: 8px;
            }

            #CloseDialogCheckbox::indicator {
                width: 16px;
                height: 16px;
                border-radius: 0px;
                border: 1px solid rgba(255, 255, 255, 0.2);
                background: rgba(255, 255, 255, 0.05);
            }

            #CloseDialogCheckbox::indicator:hover {
                border-color: rgba(74, 158, 255, 0.6);
                background: rgba(74, 158, 255, 0.1);
            }

            #CloseDialogCheckbox::indicator:checked {
                background: #4a9eff;
                border-color: #4a9eff;
            }

            /* 底部按钮栏 */
            #CloseDialogButtonBar {
                background: #252525;
                border-top: 1px solid rgba(255, 255, 255, 0.08);
            }

            /* 取消按钮 - 次要 */
            #CloseDialogCancelButton {
                background: rgba(255, 255, 255, 0.05);
                border: none;
                border-radius: 8px;
                color: rgba(255, 255, 255, 0.7);
                font-size: 13px;
                font-weight: 500;
            }

            #CloseDialogCancelButton:hover {
                background: rgba(255, 255, 255, 0.08);
                color: #ffffff;
            }

            #CloseDialogCancelButton:pressed {
                background: rgba(255, 255, 255, 0.12);
            }

            /* 最小化按钮 - 主要操作 */
            #CloseDialogMinimizeButton {
                background: #4a9eff;
                border: none;
                border-radius: 8px;
                color: #ffffff;
                font-size: 13px;
                font-weight: 600;
            }

            #CloseDialogMinimizeButton:hover {
                background: #5aa9ff;
            }

            #CloseDialogMinimizeButton:pressed {
                background: #3a8eef;
            }

            /* 退出按钮 - 危险操作 */
            #CloseDialogCloseButton {
                background: rgba(239, 68, 68, 0.1);
                border: none;
                border-radius: 8px;
                color: #f87171;
                font-size: 13px;
                font-weight: 600;
            }

            #CloseDialogCloseButton:hover {
                background: rgba(239, 68, 68, 0.18);
                color: #fca5a5;
            }

            #CloseDialogCloseButton:pressed {
                background: rgba(239, 68, 68, 0.25);
            }
        """
