# -*- coding: utf-8 -*-

"""
试用对话框 - 首次启动时显示

供用户选择：
- 试用 7 天
- 输入激活码
"""

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QWidget, QApplication
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QIcon, QDesktopServices
from PyQt6.QtCore import QUrl
from core.logger import get_logger

logger = get_logger(__name__)


class TrialDialog(QDialog):
    """首次启动弹窗"""

    RESULT_TRIAL = 1       # 选择试用
    RESULT_ACTIVATE = 2    # 选择输入激活码
    RESULT_CANCEL = 0      # 关闭/取消

    def __init__(self, parent=None, purchase_link=""):
        super().__init__(parent)
        self.result_action = self.RESULT_CANCEL
        self._purchase_link = purchase_link
        self._init_ui()

    def _init_ui(self):
        """初始化界面"""
        from pathlib import Path
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
        self.setFixedSize(420, 240)

        self.setStyleSheet(self._get_inline_styles())

        # 主容器
        main_container = QWidget()
        main_container.setObjectName("TrialDialogContainer")

        container_layout = QVBoxLayout(main_container)
        container_layout.setContentsMargins(0, 0, 0, 0)
        container_layout.setSpacing(0)

        # === 标题栏 ===
        title_bar = QWidget()
        title_bar.setObjectName("TrialDialogTitleBar")
        title_bar.setFixedHeight(50)
        title_bar_layout = QHBoxLayout(title_bar)
        title_bar_layout.setContentsMargins(24, 0, 16, 0)

        title_label = QLabel("欢迎使用 UE Toolkit")
        title_label.setObjectName("TrialDialogTitle")
        title_bar_layout.addWidget(title_label)

        title_bar_layout.addStretch()

        close_btn = QPushButton("✕")
        close_btn.setObjectName("TrialDialogXButton")
        close_btn.setFixedSize(28, 28)
        close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        close_btn.clicked.connect(self._on_cancel)
        title_bar_layout.addWidget(close_btn)

        container_layout.addWidget(title_bar)

        # === 内容区 ===
        content = QWidget()
        content.setObjectName("TrialDialogContent")
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(24, 20, 24, 12)
        content_layout.setSpacing(8)

        desc_label = QLabel("感谢您选择 UE Toolkit，请选择使用方式：")
        desc_label.setObjectName("TrialDialogMessage")
        desc_label.setWordWrap(True)
        content_layout.addWidget(desc_label)

        # 购买链接
        if self._purchase_link:
            buy_label = QLabel('<a href="#" style="color: #4a9eff; text-decoration: none;">前往购买激活码 →</a>')
            buy_label.setObjectName("TrialDialogBuyLink")
            buy_label.setCursor(Qt.CursorShape.PointingHandCursor)
            buy_label.setStyleSheet("font-size: 12px; background: transparent; margin-top: 4px;")
            buy_label.linkActivated.connect(self._on_buy_clicked)
            content_layout.addWidget(buy_label)

        content_layout.addStretch()
        container_layout.addWidget(content)

        # === 底部按钮栏 ===
        button_bar = QWidget()
        button_bar.setObjectName("TrialDialogButtonBar")
        button_bar.setFixedHeight(60)
        button_layout = QHBoxLayout(button_bar)
        button_layout.setContentsMargins(24, 0, 24, 0)
        button_layout.setSpacing(10)

        button_layout.addStretch()

        activate_btn = QPushButton("输入激活码")
        activate_btn.setObjectName("TrialDialogSecondaryButton")
        activate_btn.setFixedSize(110, 36)
        activate_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        activate_btn.clicked.connect(self._on_activate)
        button_layout.addWidget(activate_btn)

        trial_btn = QPushButton("试用 7 天")
        trial_btn.setObjectName("TrialDialogPrimaryButton")
        trial_btn.setFixedSize(100, 36)
        trial_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        trial_btn.clicked.connect(self._on_trial)
        button_layout.addWidget(trial_btn)

        container_layout.addWidget(button_bar)

        # 设置主布局
        dialog_layout = QVBoxLayout(self)
        dialog_layout.setContentsMargins(0, 0, 0, 0)
        dialog_layout.addWidget(main_container)

    # --- 事件处理 ---

    def _on_trial(self):
        """选择试用"""
        self.result_action = self.RESULT_TRIAL
        logger.info("用户选择：试用 7 天")
        self.accept()

    def _on_activate(self):
        """选择输入激活码"""
        self.result_action = self.RESULT_ACTIVATE
        logger.info("用户选择：输入激活码")
        self.accept()

    def _on_buy_clicked(self):
        """打开购买链接"""
        if self._purchase_link:
            QDesktopServices.openUrl(QUrl(self._purchase_link))

    def _on_cancel(self):
        """取消"""
        self.result_action = self.RESULT_CANCEL
        logger.info("用户取消试用对话框")
        self.reject()

    def showEvent(self, event):
        """显示时居中到屏幕"""
        super().showEvent(event)
        self._center_on_screen()

    def _center_on_screen(self):
        """居中到屏幕（启动阶段可能没有父窗口）"""
        screen = QApplication.primaryScreen()
        if screen:
            screen_geo = screen.availableGeometry()
            x = screen_geo.x() + (screen_geo.width() - self.width()) // 2
            y = screen_geo.y() + (screen_geo.height() - self.height()) // 2
            self.move(x, y)

    # --- 样式 ---

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
            #TrialDialogContainer {
                background: #f5f5f5;
                border: 1px solid rgba(0, 0, 0, 0.12);
                border-radius: 0px;
            }
            #TrialDialogTitleBar {
                background: #eeeeee;
                border-bottom: 1px solid rgba(0, 0, 0, 0.08);
            }
            #TrialDialogTitle {
                color: #1a1a1a;
                font-size: 16px;
                font-weight: 600;
                background: transparent;
            }
            #TrialDialogXButton {
                background: transparent;
                color: rgba(0, 0, 0, 0.5);
                border: none;
                border-radius: 6px;
                font-size: 14px;
                font-weight: 300;
            }
            #TrialDialogXButton:hover {
                background: rgba(0, 0, 0, 0.08);
                color: #000000;
            }
            #TrialDialogContent { background: transparent; }
            #TrialDialogMessage {
                color: rgba(0, 0, 0, 0.55);
                font-size: 13px;
                background: transparent;
            }
            #TrialDialogButtonBar {
                background: #eeeeee;
                border-top: 1px solid rgba(0, 0, 0, 0.06);
            }
            #TrialDialogSecondaryButton {
                background: rgba(0, 0, 0, 0.05);
                border: none; border-radius: 8px;
                color: rgba(0, 0, 0, 0.6);
                font-size: 13px; font-weight: 500;
            }
            #TrialDialogSecondaryButton:hover {
                background: rgba(0, 0, 0, 0.08);
                color: #000000;
            }
            #TrialDialogSecondaryButton:pressed { background: rgba(0, 0, 0, 0.12); }
            #TrialDialogPrimaryButton {
                background: #4a9eff;
                border: none; border-radius: 8px;
                color: #ffffff;
                font-size: 13px; font-weight: 600;
            }
            #TrialDialogPrimaryButton:hover { background: #5aa9ff; }
            #TrialDialogPrimaryButton:pressed { background: #3a8eef; }
        """

    def _get_dark_styles(self):
        return """
            #TrialDialogContainer {
                background: #1c1c1c;
                border: 1px solid rgba(255, 255, 255, 0.15);
                border-radius: 0px;
            }
            #TrialDialogTitleBar {
                background: #252525;
                border-bottom: 1px solid rgba(255, 255, 255, 0.1);
            }
            #TrialDialogTitle {
                color: #ffffff;
                font-size: 16px;
                font-weight: 600;
                background: transparent;
            }
            #TrialDialogXButton {
                background: transparent;
                color: rgba(255, 255, 255, 0.7);
                border: none;
                border-radius: 6px;
                font-size: 14px;
                font-weight: 300;
            }
            #TrialDialogXButton:hover {
                background: rgba(255, 255, 255, 0.15);
                color: #ffffff;
            }
            #TrialDialogContent { background: transparent; }
            #TrialDialogMessage {
                color: rgba(255, 255, 255, 0.55);
                font-size: 13px;
                background: transparent;
            }
            #TrialDialogButtonBar {
                background: #252525;
                border-top: 1px solid rgba(255, 255, 255, 0.08);
            }
            #TrialDialogSecondaryButton {
                background: rgba(255, 255, 255, 0.05);
                border: none; border-radius: 8px;
                color: rgba(255, 255, 255, 0.7);
                font-size: 13px; font-weight: 500;
            }
            #TrialDialogSecondaryButton:hover {
                background: rgba(255, 255, 255, 0.08);
                color: #ffffff;
            }
            #TrialDialogSecondaryButton:pressed { background: rgba(255, 255, 255, 0.12); }
            #TrialDialogPrimaryButton {
                background: #4a9eff;
                border: none; border-radius: 8px;
                color: #ffffff;
                font-size: 13px; font-weight: 600;
            }
            #TrialDialogPrimaryButton:hover { background: #5aa9ff; }
            #TrialDialogPrimaryButton:pressed { background: #3a8eef; }
        """
