# -*- coding: utf-8 -*-

"""
激活引导对话框

当用户点击付费模块时显示，引导用户激活或查看授权状态。
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

# QQ 群号
QQ_GROUP_NUMBER = "1048699469"


class ActivationGuideDialog(QDialog):
    """激活引导对话框 - 引导用户激活付费功能"""

    RESULT_ACTIVATED = 1   # 激活成功
    RESULT_CANCEL = 0      # 取消

    def __init__(self, parent=None, purchase_link="", license_status="none"):
        """
        Args:
            parent: 父窗口
            purchase_link: 购买链接
            license_status: 当前授权状态 ("none", "expired")
        """
        super().__init__(parent)
        self.result_action = self.RESULT_CANCEL
        self._activation_key = ""
        self._purchase_link = purchase_link
        self._license_status = license_status
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
        self.setFixedSize(460, 380)

        self.setStyleSheet(self._get_inline_styles())

        # 主容器
        main_container = QWidget()
        main_container.setObjectName("ActivationGuideContainer")

        container_layout = QVBoxLayout(main_container)
        container_layout.setContentsMargins(0, 0, 0, 0)
        container_layout.setSpacing(0)

        # === 标题栏 ===
        title_bar = QWidget()
        title_bar.setObjectName("ActivationGuideTitleBar")
        title_bar.setFixedHeight(50)
        title_bar_layout = QHBoxLayout(title_bar)
        title_bar_layout.setContentsMargins(24, 0, 16, 0)

        if self._license_status == "expired":
            title_text = "授权已过期"
        else:
            title_text = "解锁高级功能"
        
        title_label = QLabel(title_text)
        title_label.setObjectName("ActivationGuideTitle")
        title_bar_layout.addWidget(title_label)

        title_bar_layout.addStretch()

        close_btn = QPushButton("✕")
        close_btn.setObjectName("ActivationGuideXButton")
        close_btn.setFixedSize(28, 28)
        close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        close_btn.clicked.connect(self._on_cancel)
        title_bar_layout.addWidget(close_btn)

        container_layout.addWidget(title_bar)

        # === 内容区 ===
        content = QWidget()
        content.setObjectName("ActivationGuideContent")
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(24, 20, 24, 8)
        content_layout.setSpacing(12)

        # 功能说明
        if self._license_status == "expired":
            desc_text = "您的授权已过期，需要重新激活才能继续使用高级功能。"
        else:
            desc_text = "AI 助手和配置工具是高级功能，需要激活后才能使用。\n基础功能（我的工程、资产管理、站点推荐）永久免费。"
        
        desc_label = QLabel(desc_text)
        desc_label.setObjectName("ActivationGuideDesc")
        desc_label.setWordWrap(True)
        content_layout.addWidget(desc_label)

        # 价格说明
        price_label = QLabel("本工具标价 ¥199，加入官方交流群可每日免费领取激活码。")
        price_label.setObjectName("ActivationGuidePrice")
        price_label.setWordWrap(True)
        content_layout.addWidget(price_label)

        # QQ 群号（可复制）
        group_row = QHBoxLayout()
        group_row.setSpacing(8)
        group_label = QLabel(f"QQ 群号：{QQ_GROUP_NUMBER}")
        group_label.setObjectName("ActivationGuideGroupLabel")
        group_row.addWidget(group_label)

        self.copy_btn = QPushButton("复制群号")
        self.copy_btn.setObjectName("ActivationGuideCopyBtn")
        self.copy_btn.setFixedSize(72, 26)
        self.copy_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.copy_btn.clicked.connect(self._copy_group_number)
        group_row.addWidget(self.copy_btn)
        group_row.addStretch()
        content_layout.addLayout(group_row)

        # 购买链接
        if self._purchase_link:
            buy_label = QLabel('没有激活码？<a href="#" style="color: #4a9eff; text-decoration: none;">去购买 →</a>')
            buy_label.setObjectName("ActivationGuideBuyLink")
            buy_label.setCursor(Qt.CursorShape.PointingHandCursor)
            buy_label.linkActivated.connect(self._on_buy_clicked)
            content_layout.addWidget(buy_label)

        # 分隔
        sep = QLabel("— 已有激活码？在下方输入 —")
        sep.setObjectName("ActivationGuideSep")
        sep.setAlignment(Qt.AlignmentFlag.AlignCenter)
        content_layout.addWidget(sep)

        # 激活码输入
        self.key_input = QLineEdit()
        self.key_input.setObjectName("ActivationGuideInput")
        self.key_input.setPlaceholderText("XXXX-XXXX-XXXX-XXXX")
        self.key_input.setFixedHeight(36)
        content_layout.addWidget(self.key_input)

        self.status_label = QLabel("")
        self.status_label.setObjectName("ActivationGuideStatus")
        self.status_label.setFixedHeight(18)
        content_layout.addWidget(self.status_label)

        content_layout.addStretch()
        container_layout.addWidget(content)

        # === 底部按钮栏 ===
        button_bar = QWidget()
        button_bar.setObjectName("ActivationGuideButtonBar")
        button_bar.setFixedHeight(60)
        button_layout = QHBoxLayout(button_bar)
        button_layout.setContentsMargins(24, 0, 24, 0)
        button_layout.setSpacing(10)

        button_layout.addStretch()

        cancel_btn = QPushButton("稍后再说")
        cancel_btn.setObjectName("ActivationGuideSecondaryBtn")
        cancel_btn.setFixedSize(90, 36)
        cancel_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        cancel_btn.clicked.connect(self._on_cancel)
        button_layout.addWidget(cancel_btn)

        self.activate_btn = QPushButton("激活")
        self.activate_btn.setObjectName("ActivationGuidePrimaryBtn")
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

    def _copy_group_number(self):
        """复制群号到剪贴板"""
        clipboard = QApplication.clipboard()
        if clipboard:
            clipboard.setText(QQ_GROUP_NUMBER)
            self.copy_btn.setText("✅ 已复制")
            from PyQt6.QtCore import QTimer
            QTimer.singleShot(1500, lambda: self.copy_btn.setText("复制群号"))

    def _on_buy_clicked(self):
        """打开购买链接"""
        if self._purchase_link:
            QDesktopServices.openUrl(QUrl(self._purchase_link))

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

    def _on_cancel(self):
        """取消"""
        self.result_action = self.RESULT_CANCEL
        logger.info("用户取消激活引导对话框")
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

    def _get_dark_styles(self):
        return """
            #ActivationGuideContainer {
                background: #1c1c1c;
                border: 1px solid rgba(255,255,255,0.15);
                border-radius: 0px;
            }
            #ActivationGuideTitleBar {
                background: #252525;
                border-bottom: 1px solid rgba(255,255,255,0.1);
            }
            #ActivationGuideTitle {
                color: #4a9eff; font-size: 16px; font-weight: 600; background: transparent;
            }
            #ActivationGuideXButton {
                background: transparent; color: rgba(255,255,255,0.7);
                border: none; border-radius: 6px; font-size: 14px;
            }
            #ActivationGuideXButton:hover {
                background: rgba(255,255,255,0.15); color: #fff;
            }
            #ActivationGuideContent { background: transparent; }
            #ActivationGuideDesc {
                color: rgba(255,255,255,0.75); font-size: 13px; background: transparent;
                line-height: 1.6;
            }
            #ActivationGuidePrice {
                color: rgba(255,255,255,0.65); font-size: 13px; background: transparent;
                line-height: 1.6;
            }
            #ActivationGuideGroupLabel {
                color: #4a9eff; font-size: 14px; font-weight: 600; background: transparent;
            }
            #ActivationGuideCopyBtn {
                background: rgba(74,158,255,0.15); border: none; border-radius: 4px;
                color: #4a9eff; font-size: 12px;
            }
            #ActivationGuideCopyBtn:hover { background: rgba(74,158,255,0.25); }
            #ActivationGuideBuyLink {
                color: rgba(255,255,255,0.5); font-size: 12px; background: transparent;
            }
            #ActivationGuideSep {
                color: rgba(255,255,255,0.3); font-size: 12px; background: transparent;
                margin: 4px 0;
            }
            #ActivationGuideInput {
                background: rgba(255,255,255,0.06);
                border: 1px solid rgba(255,255,255,0.15); border-radius: 6px;
                padding: 0 10px; color: #fff; font-size: 14px;
                font-family: Consolas, monospace;
            }
            #ActivationGuideInput:focus { border: 1px solid #4a9eff; }
            #ActivationGuideStatus { font-size: 12px; background: transparent; }
            #ActivationGuideButtonBar {
                background: #252525; border-top: 1px solid rgba(255,255,255,0.08);
            }
            #ActivationGuideSecondaryBtn {
                background: rgba(255,255,255,0.05); border: none; border-radius: 8px;
                color: rgba(255,255,255,0.7); font-size: 13px;
            }
            #ActivationGuideSecondaryBtn:hover {
                background: rgba(255,255,255,0.08); color: #fff;
            }
            #ActivationGuidePrimaryBtn {
                background: #4a9eff; border: none; border-radius: 8px;
                color: #fff; font-size: 13px; font-weight: 600;
            }
            #ActivationGuidePrimaryBtn:hover { background: #5aa9ff; }
            #ActivationGuidePrimaryBtn:pressed { background: #3a8eef; }
            #ActivationGuidePrimaryBtn:disabled {
                background: rgba(74, 158, 255, 0.4);
                color: rgba(255, 255, 255, 0.6);
            }
        """

    def _get_light_styles(self):
        return """
            #ActivationGuideContainer {
                background: #f5f5f5;
                border: 1px solid rgba(0,0,0,0.12);
                border-radius: 0px;
            }
            #ActivationGuideTitleBar {
                background: #eee;
                border-bottom: 1px solid rgba(0,0,0,0.08);
            }
            #ActivationGuideTitle {
                color: #2563eb; font-size: 16px; font-weight: 600; background: transparent;
            }
            #ActivationGuideXButton {
                background: transparent; color: rgba(0,0,0,0.5);
                border: none; border-radius: 6px; font-size: 14px;
            }
            #ActivationGuideXButton:hover {
                background: rgba(0,0,0,0.08); color: #000;
            }
            #ActivationGuideContent { background: transparent; }
            #ActivationGuideDesc {
                color: rgba(0,0,0,0.65); font-size: 13px; background: transparent;
                line-height: 1.6;
            }
            #ActivationGuidePrice {
                color: rgba(0,0,0,0.55); font-size: 13px; background: transparent;
                line-height: 1.6;
            }
            #ActivationGuideGroupLabel {
                color: #2563eb; font-size: 14px; font-weight: 600; background: transparent;
            }
            #ActivationGuideCopyBtn {
                background: rgba(37,99,235,0.1); border: none; border-radius: 4px;
                color: #2563eb; font-size: 12px;
            }
            #ActivationGuideCopyBtn:hover { background: rgba(37,99,235,0.18); }
            #ActivationGuideBuyLink {
                color: rgba(0,0,0,0.5); font-size: 12px; background: transparent;
            }
            #ActivationGuideSep {
                color: rgba(0,0,0,0.3); font-size: 12px; background: transparent;
                margin: 4px 0;
            }
            #ActivationGuideInput {
                background: #fff; border: 1px solid rgba(0,0,0,0.15); border-radius: 6px;
                padding: 0 10px; color: #1a1a1a; font-size: 14px;
                font-family: Consolas, monospace;
            }
            #ActivationGuideInput:focus { border: 1px solid #2563eb; }
            #ActivationGuideStatus { font-size: 12px; background: transparent; }
            #ActivationGuideButtonBar {
                background: #eee; border-top: 1px solid rgba(0,0,0,0.06);
            }
            #ActivationGuideSecondaryBtn {
                background: rgba(0,0,0,0.05); border: none; border-radius: 8px;
                color: rgba(0,0,0,0.6); font-size: 13px;
            }
            #ActivationGuideSecondaryBtn:hover {
                background: rgba(0,0,0,0.08); color: #000;
            }
            #ActivationGuidePrimaryBtn {
                background: #2563eb; border: none; border-radius: 8px;
                color: #fff; font-size: 13px; font-weight: 600;
            }
            #ActivationGuidePrimaryBtn:hover { background: #3b82f6; }
            #ActivationGuidePrimaryBtn:pressed { background: #1d4ed8; }
            #ActivationGuidePrimaryBtn:disabled {
                background: rgba(37, 99, 235, 0.4);
                color: rgba(255, 255, 255, 0.6);
            }
        """
