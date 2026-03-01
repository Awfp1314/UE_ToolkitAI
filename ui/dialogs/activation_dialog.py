# -*- coding: utf-8 -*-

"""
激活码输入对话框

供用户输入卡密激活码并获取验证反馈。
"""

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QWidget, QLineEdit, QApplication
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QIcon, QDesktopServices
from PyQt6.QtCore import QUrl
from core.logger import get_logger

logger = get_logger(__name__)


class ActivationDialog(QDialog):
    """激活码输入弹窗"""

    RESULT_ACTIVATED = 1   # 激活成功
    RESULT_CANCEL = 0      # 取消

    def __init__(self, parent=None, purchase_link="", upgrade_mode=False):
        super().__init__(parent)
        self.result_action = self.RESULT_CANCEL
        self._activation_key = ""
        self._purchase_link = purchase_link
        self._upgrade_mode = upgrade_mode
        self._init_ui()

    def _init_ui(self):
        """初始化界面"""
        from pathlib import Path
        icon_path = Path(__file__).parent.parent.parent / "resources" / "tubiao.ico"
        if icon_path.exists():
            self.setWindowIcon(QIcon(str(icon_path)))

        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.Dialog
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setModal(True)
        self.setFixedSize(440, 310)

        self.setStyleSheet(self._get_inline_styles())

        # 主容器
        main_container = QWidget()
        main_container.setObjectName("ActivationDialogContainer")

        container_layout = QVBoxLayout(main_container)
        container_layout.setContentsMargins(0, 0, 0, 0)
        container_layout.setSpacing(0)

        # === 标题栏 ===
        title_bar = QWidget()
        title_bar.setObjectName("ActivationDialogTitleBar")
        title_bar.setFixedHeight(50)
        title_bar_layout = QHBoxLayout(title_bar)
        title_bar_layout.setContentsMargins(24, 0, 16, 0)

        title_label = QLabel("升级到永久版" if self._upgrade_mode else "激活 UE Toolkit")
        title_label.setObjectName("ActivationDialogTitle")
        title_bar_layout.addWidget(title_label)

        title_bar_layout.addStretch()

        close_btn = QPushButton("✕")
        close_btn.setObjectName("ActivationDialogXButton")
        close_btn.setFixedSize(28, 28)
        close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        close_btn.clicked.connect(self._on_cancel)
        title_bar_layout.addWidget(close_btn)

        container_layout.addWidget(title_bar)

        # === 内容区 ===
        content = QWidget()
        content.setObjectName("ActivationDialogContent")
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(24, 16, 24, 8)
        content_layout.setSpacing(12)

        input_label = QLabel("请输入永久激活码：" if self._upgrade_mode else "请输入激活码：")
        input_label.setObjectName("ActivationDialogMessage")
        content_layout.addWidget(input_label)

        self.key_input = QLineEdit()
        self.key_input.setObjectName("ActivationDialogInput")
        self.key_input.setPlaceholderText("XXXX-XXXX-XXXX-XXXX")
        self.key_input.setFixedHeight(36)
        content_layout.addWidget(self.key_input)

        self.status_label = QLabel("")
        self.status_label.setObjectName("ActivationDialogStatus")
        self.status_label.setWordWrap(True)
        self.status_label.setFixedHeight(20)
        content_layout.addWidget(self.status_label)

        # 购买链接
        if self._purchase_link:
            buy_label = QLabel('没有激活码？<a href="#" style="color: #4a9eff; text-decoration: none;">去购买 →</a>')
            buy_label.setObjectName("ActivationDialogBuyLink")
            buy_label.setCursor(Qt.CursorShape.PointingHandCursor)
            buy_label.linkActivated.connect(self._on_buy_clicked)
            content_layout.addWidget(buy_label)

        # 进群领码提示
        QQ_GROUP_NUMBER = "1048699469"
        group_row = QHBoxLayout()
        group_row.setSpacing(6)
        group_hint = QLabel(f"进群领免费激活码：{QQ_GROUP_NUMBER}")
        group_hint.setObjectName("ActivationDialogGroupHint")
        group_row.addWidget(group_hint)

        copy_group_btn = QPushButton("复制")
        copy_group_btn.setObjectName("ActivationDialogCopyGroupBtn")
        copy_group_btn.setFixedSize(42, 22)
        copy_group_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._copy_group_btn = copy_group_btn
        copy_group_btn.clicked.connect(self._on_copy_group)
        group_row.addWidget(copy_group_btn)
        group_row.addStretch()
        content_layout.addLayout(group_row)

        content_layout.addStretch()
        container_layout.addWidget(content)

        # === 底部按钮栏 ===
        button_bar = QWidget()
        button_bar.setObjectName("ActivationDialogButtonBar")
        button_bar.setFixedHeight(60)
        button_layout = QHBoxLayout(button_bar)
        button_layout.setContentsMargins(24, 0, 24, 0)
        button_layout.setSpacing(10)

        button_layout.addStretch()

        cancel_btn = QPushButton("取消")
        cancel_btn.setObjectName("ActivationDialogCancelButton")
        cancel_btn.setFixedSize(80, 36)
        cancel_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        cancel_btn.clicked.connect(self._on_cancel)
        button_layout.addWidget(cancel_btn)

        self.activate_btn = QPushButton("激活")
        self.activate_btn.setObjectName("ActivationDialogPrimaryButton")
        self.activate_btn.setFixedSize(80, 36)
        self.activate_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.activate_btn.clicked.connect(self._on_activate)
        button_layout.addWidget(self.activate_btn)

        container_layout.addWidget(button_bar)

        # 设置主布局
        dialog_layout = QVBoxLayout(self)
        dialog_layout.setContentsMargins(0, 0, 0, 0)
        dialog_layout.addWidget(main_container)

    # --- 公共方法 ---

    def get_activation_key(self) -> str:
        """获取用户输入的激活码"""
        return self._activation_key

    def set_status(self, message: str, is_error: bool = False):
        """设置状态反馈信息"""
        self.status_label.setText(message)
        if is_error:
            self.status_label.setStyleSheet("color: #ef4444; font-size: 12px; background: transparent;")
        else:
            self.status_label.setStyleSheet("color: #22c55e; font-size: 12px; background: transparent;")

    def set_loading(self, loading: bool):
        """设置激活按钮的加载状态"""
        if loading:
            self.activate_btn.setText("验证中...")
            self.activate_btn.setEnabled(False)
            self.key_input.setEnabled(False)
        else:
            self.activate_btn.setText("激活")
            self.activate_btn.setEnabled(True)
            self.key_input.setEnabled(True)

    # --- 事件处理 ---

    def _on_activate(self):
        """点击激活"""
        key = self.key_input.text().strip()
        if not key:
            self.set_status("请输入激活码", is_error=True)
            return
        self._activation_key = key
        self.result_action = self.RESULT_ACTIVATED
        logger.info("用户提交激活码")
        self.accept()

    def _on_buy_clicked(self):
        """打开购买链接"""
        if self._purchase_link:
            QDesktopServices.openUrl(QUrl(self._purchase_link))

    def _on_copy_group(self):
        """复制群号到剪贴板"""
        QQ_GROUP_NUMBER = "1048699469"
        clipboard = QApplication.clipboard()
        if clipboard:
            clipboard.setText(QQ_GROUP_NUMBER)
            self._copy_group_btn.setText("✅")
            from PyQt6.QtCore import QTimer
            QTimer.singleShot(1500, lambda: self._copy_group_btn.setText("复制"))

    def _on_cancel(self):
        """取消"""
        self.result_action = self.RESULT_CANCEL
        logger.info("用户取消激活对话框")
        self.reject()

    def showEvent(self, event):
        """显示时居中到屏幕"""
        super().showEvent(event)
        self._center_on_screen()

    def _center_on_screen(self):
        """居中到屏幕"""
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
            #ActivationDialogContainer {
                background: #f5f5f5;
                border: 1px solid rgba(0, 0, 0, 0.12);
                border-radius: 0px;
            }
            #ActivationDialogTitleBar {
                background: #eeeeee;
                border-bottom: 1px solid rgba(0, 0, 0, 0.08);
            }
            #ActivationDialogTitle {
                color: #1a1a1a;
                font-size: 16px;
                font-weight: 600;
                background: transparent;
            }
            #ActivationDialogXButton {
                background: transparent;
                color: rgba(0, 0, 0, 0.5);
                border: none;
                border-radius: 6px;
                font-size: 14px;
                font-weight: 300;
            }
            #ActivationDialogXButton:hover {
                background: rgba(0, 0, 0, 0.08);
                color: #000000;
            }
            #ActivationDialogContent { background: transparent; }
            #ActivationDialogMessage {
                color: rgba(0, 0, 0, 0.55);
                font-size: 13px;
                background: transparent;
            }
            #ActivationDialogInput {
                background: #ffffff;
                border: 1px solid rgba(0, 0, 0, 0.15);
                border-radius: 6px;
                padding: 0 10px;
                color: #1a1a1a;
                font-size: 14px;
                font-family: Consolas, monospace;
            }
            #ActivationDialogInput:focus {
                border: 1px solid #4a9eff;
            }
            #ActivationDialogStatus {
                font-size: 12px;
                background: transparent;
            }
            #ActivationDialogButtonBar {
                background: #eeeeee;
                border-top: 1px solid rgba(0, 0, 0, 0.06);
            }
            #ActivationDialogCancelButton {
                background: rgba(0, 0, 0, 0.05);
                border: none; border-radius: 8px;
                color: rgba(0, 0, 0, 0.6);
                font-size: 13px; font-weight: 500;
            }
            #ActivationDialogCancelButton:hover {
                background: rgba(0, 0, 0, 0.08);
                color: #000000;
            }
            #ActivationDialogCancelButton:pressed { background: rgba(0, 0, 0, 0.12); }
            #ActivationDialogPrimaryButton {
                background: #4a9eff;
                border: none; border-radius: 8px;
                color: #ffffff;
                font-size: 13px; font-weight: 600;
            }
            #ActivationDialogPrimaryButton:hover { background: #5aa9ff; }
            #ActivationDialogPrimaryButton:pressed { background: #3a8eef; }
            #ActivationDialogPrimaryButton:disabled {
                background: rgba(74, 158, 255, 0.4);
                color: rgba(255, 255, 255, 0.6);
            }
            #ActivationDialogBuyLink {
                font-size: 12px;
                color: rgba(0, 0, 0, 0.5);
                background: transparent;
            }
            #ActivationDialogGroupHint {
                font-size: 12px;
                color: rgba(0, 0, 0, 0.4);
                background: transparent;
            }
            #ActivationDialogCopyGroupBtn {
                font-size: 11px;
                background: rgba(74, 158, 255, 0.1);
                color: #4a9eff;
                border: none;
                border-radius: 4px;
            }
            #ActivationDialogCopyGroupBtn:hover {
                background: rgba(74, 158, 255, 0.2);
            }
        """

    def _get_dark_styles(self):
        return """
            #ActivationDialogContainer {
                background: #1c1c1c;
                border: 1px solid rgba(255, 255, 255, 0.15);
                border-radius: 0px;
            }
            #ActivationDialogTitleBar {
                background: #252525;
                border-bottom: 1px solid rgba(255, 255, 255, 0.1);
            }
            #ActivationDialogTitle {
                color: #ffffff;
                font-size: 16px;
                font-weight: 600;
                background: transparent;
            }
            #ActivationDialogXButton {
                background: transparent;
                color: rgba(255, 255, 255, 0.7);
                border: none;
                border-radius: 6px;
                font-size: 14px;
                font-weight: 300;
            }
            #ActivationDialogXButton:hover {
                background: rgba(255, 255, 255, 0.15);
                color: #ffffff;
            }
            #ActivationDialogContent { background: transparent; }
            #ActivationDialogMessage {
                color: rgba(255, 255, 255, 0.55);
                font-size: 13px;
                background: transparent;
            }
            #ActivationDialogInput {
                background: rgba(255, 255, 255, 0.06);
                border: 1px solid rgba(255, 255, 255, 0.15);
                border-radius: 6px;
                padding: 0 10px;
                color: #ffffff;
                font-size: 14px;
                font-family: Consolas, monospace;
            }
            #ActivationDialogInput:focus {
                border: 1px solid #4a9eff;
            }
            #ActivationDialogStatus {
                font-size: 12px;
                background: transparent;
            }
            #ActivationDialogButtonBar {
                background: #252525;
                border-top: 1px solid rgba(255, 255, 255, 0.08);
            }
            #ActivationDialogCancelButton {
                background: rgba(255, 255, 255, 0.05);
                border: none; border-radius: 8px;
                color: rgba(255, 255, 255, 0.7);
                font-size: 13px; font-weight: 500;
            }
            #ActivationDialogCancelButton:hover {
                background: rgba(255, 255, 255, 0.08);
                color: #ffffff;
            }
            #ActivationDialogCancelButton:pressed { background: rgba(255, 255, 255, 0.12); }
            #ActivationDialogPrimaryButton {
                background: #4a9eff;
                border: none; border-radius: 8px;
                color: #ffffff;
                font-size: 13px; font-weight: 600;
            }
            #ActivationDialogPrimaryButton:hover { background: #5aa9ff; }
            #ActivationDialogPrimaryButton:pressed { background: #3a8eef; }
            #ActivationDialogPrimaryButton:disabled {
                background: rgba(74, 158, 255, 0.4);
                color: rgba(255, 255, 255, 0.6);
            }
            #ActivationDialogBuyLink {
                font-size: 12px;
                color: rgba(255, 255, 255, 0.5);
                background: transparent;
            }
            #ActivationDialogGroupHint {
                font-size: 12px;
                color: rgba(255, 255, 255, 0.4);
                background: transparent;
            }
            #ActivationDialogCopyGroupBtn {
                font-size: 11px;
                background: rgba(74, 158, 255, 0.15);
                color: #4a9eff;
                border: none;
                border-radius: 4px;
            }
            #ActivationDialogCopyGroupBtn:hover {
                background: rgba(74, 158, 255, 0.25);
            }
        """
