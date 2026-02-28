# -*- coding: utf-8 -*-

"""
试用到期对话框

试用结束后弹出，引导用户进群领取激活码或手动输入激活码。
"""

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QWidget, QLineEdit, QApplication
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QIcon, QDesktopServices, QGuiApplication
from PyQt6.QtCore import QUrl
from core.logger import get_logger

logger = get_logger(__name__)

# TODO: 替换为真实的 QQ 群号
QQ_GROUP_NUMBER = "1048699469"


class TrialExpiredDialog(QDialog):
    """试用到期弹窗 — 引导进群 + 激活码输入"""

    RESULT_ACTIVATED = 1
    RESULT_CANCEL = 0
    RESULT_START_TRIAL = "start_trial"

    def __init__(self, parent=None, purchase_link="", first_use=False):
        super().__init__(parent)
        self.result_action = self.RESULT_CANCEL
        self._activation_key = ""
        self._purchase_link = purchase_link
        self._first_use = first_use
        self._init_ui()

    def _init_ui(self):
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
        self.setFixedSize(460, 360)
        self.setStyleSheet(self._get_inline_styles())

        # 主容器
        main_container = QWidget()
        main_container.setObjectName("ExpiredDialogContainer")
        container_layout = QVBoxLayout(main_container)
        container_layout.setContentsMargins(0, 0, 0, 0)
        container_layout.setSpacing(0)

        # === 标题栏 ===
        title_bar = QWidget()
        title_bar.setObjectName("ExpiredDialogTitleBar")
        title_bar.setFixedHeight(50)
        tb_layout = QHBoxLayout(title_bar)
        tb_layout.setContentsMargins(24, 0, 16, 0)

        title_label = QLabel("欢迎使用" if self._first_use else "试用已结束")
        title_label.setObjectName("ExpiredDialogTitle")
        tb_layout.addWidget(title_label)
        tb_layout.addStretch()

        close_btn = QPushButton("✕")
        close_btn.setObjectName("ExpiredDialogXButton")
        close_btn.setFixedSize(28, 28)
        close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        close_btn.clicked.connect(self._on_cancel)
        tb_layout.addWidget(close_btn)
        container_layout.addWidget(title_bar)

        # === 内容区 ===
        content = QWidget()
        content.setObjectName("ExpiredDialogContent")
        c_layout = QVBoxLayout(content)
        c_layout.setContentsMargins(24, 16, 24, 8)
        c_layout.setSpacing(10)

        # 提示文案
        if self._first_use:
            msg = QLabel(
                "欢迎使用 UE Toolkit！您可以开始 7 天免费试用，或输入激活码直接激活。\n"
                "加入官方交流群可每日免费领取激活码。"
            )
        else:
            msg = QLabel(
                "本工具标价 ¥199，加入官方交流群即可每日免费领取激活码继续使用。"
            )
        msg.setObjectName("ExpiredDialogMessage")
        msg.setWordWrap(True)
        c_layout.addWidget(msg)

        # QQ 群号（可复制）
        group_row = QHBoxLayout()
        group_row.setSpacing(8)
        group_label = QLabel(f"QQ 群号：{QQ_GROUP_NUMBER}")
        group_label.setObjectName("ExpiredDialogGroupLabel")
        group_row.addWidget(group_label)

        copy_btn = QPushButton("复制群号")
        copy_btn.setObjectName("ExpiredDialogCopyBtn")
        copy_btn.setFixedSize(72, 26)
        copy_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        copy_btn.clicked.connect(self._copy_group_number)
        group_row.addWidget(copy_btn)
        group_row.addStretch()
        c_layout.addLayout(group_row)

        # 购买链接
        if self._purchase_link:
            buy_label = QLabel('没有激活码？<a href="#" style="color: #4a9eff; text-decoration: none;">去购买 →</a>')
            buy_label.setObjectName("ExpiredDialogBuyLink")
            buy_label.setCursor(Qt.CursorShape.PointingHandCursor)
            buy_label.linkActivated.connect(self._on_buy_clicked)
            c_layout.addWidget(buy_label)

        # 分隔
        sep = QLabel("— 已有激活码？在下方输入 —")
        sep.setObjectName("ExpiredDialogSep")
        sep.setAlignment(Qt.AlignmentFlag.AlignCenter)
        c_layout.addWidget(sep)

        # 激活码输入
        self.key_input = QLineEdit()
        self.key_input.setObjectName("ExpiredDialogInput")
        self.key_input.setPlaceholderText("XXXX-XXXX-XXXX-XXXX")
        self.key_input.setFixedHeight(36)
        c_layout.addWidget(self.key_input)

        self.status_label = QLabel("")
        self.status_label.setObjectName("ExpiredDialogStatus")
        self.status_label.setFixedHeight(18)
        c_layout.addWidget(self.status_label)

        c_layout.addStretch()
        container_layout.addWidget(content)

        # === 底部按钮栏 ===
        button_bar = QWidget()
        button_bar.setObjectName("ExpiredDialogButtonBar")
        button_bar.setFixedHeight(60)
        btn_layout = QHBoxLayout(button_bar)
        btn_layout.setContentsMargins(24, 0, 24, 0)
        btn_layout.setSpacing(10)
        btn_layout.addStretch()

        quit_btn = QPushButton("退出")
        quit_btn.setObjectName("ExpiredDialogSecondaryBtn")
        quit_btn.setFixedSize(80, 36)
        quit_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        quit_btn.clicked.connect(self._on_cancel)
        btn_layout.addWidget(quit_btn)

        if self._first_use:
            trial_btn = QPushButton("开始试用")
            trial_btn.setObjectName("ExpiredDialogTrialBtn")
            trial_btn.setFixedSize(100, 36)
            trial_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            trial_btn.clicked.connect(self._on_start_trial)
            btn_layout.addWidget(trial_btn)

        activate_btn = QPushButton("激活")
        activate_btn.setObjectName("ExpiredDialogPrimaryBtn")
        activate_btn.setFixedSize(80, 36)
        activate_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        activate_btn.clicked.connect(self._on_activate)
        btn_layout.addWidget(activate_btn)

        container_layout.addWidget(button_bar)

        # 主布局
        dialog_layout = QVBoxLayout(self)
        dialog_layout.setContentsMargins(0, 0, 0, 0)
        dialog_layout.addWidget(main_container)

    # --- 公共方法 ---

    def get_activation_key(self) -> str:
        return self._activation_key

    # --- 事件 ---

    def _copy_group_number(self):
        clipboard = QGuiApplication.clipboard()
        if clipboard:
            clipboard.setText(QQ_GROUP_NUMBER)
            self.status_label.setText("已复制群号到剪贴板")
            self.status_label.setStyleSheet(
                "color: #22c55e; font-size: 12px; background: transparent;"
            )

    def _on_buy_clicked(self):
        """打开购买链接"""
        if self._purchase_link:
            QDesktopServices.openUrl(QUrl(self._purchase_link))

    def _on_activate(self):
        key = self.key_input.text().strip()
        if not key:
            self.status_label.setText("请输入激活码")
            self.status_label.setStyleSheet(
                "color: #ef4444; font-size: 12px; background: transparent;"
            )
            return
        self._activation_key = key
        self.result_action = self.RESULT_ACTIVATED
        self.accept()

    def _on_start_trial(self):
        self.result_action = self.RESULT_START_TRIAL
        self.accept()

    def _on_cancel(self):
        self.result_action = self.RESULT_CANCEL
        self.reject()

    def showEvent(self, event):
        super().showEvent(event)
        screen = QApplication.primaryScreen()
        if screen:
            geo = screen.availableGeometry()
            self.move(
                geo.x() + (geo.width() - self.width()) // 2,
                geo.y() + (geo.height() - self.height()) // 2,
            )

    # --- 样式 ---

    def _get_inline_styles(self):
        try:
            from core.utils.style_system import get_current_theme
            is_light = get_current_theme() == "modern_light"
        except Exception:
            is_light = False
        return self._get_light_styles() if is_light else self._get_dark_styles()

    def _get_dark_styles(self):
        return """
            #ExpiredDialogContainer {
                background: #1c1c1c;
                border: 1px solid rgba(255,255,255,0.15);
                border-radius: 0px;
            }
            #ExpiredDialogTitleBar {
                background: #252525;
                border-bottom: 1px solid rgba(255,255,255,0.1);
            }
            #ExpiredDialogTitle {
                color: #ff6b6b; font-size: 16px; font-weight: 600; background: transparent;
            }
            #ExpiredDialogXButton {
                background: transparent; color: rgba(255,255,255,0.7);
                border: none; border-radius: 6px; font-size: 14px;
            }
            #ExpiredDialogXButton:hover {
                background: rgba(255,255,255,0.15); color: #fff;
            }
            #ExpiredDialogContent { background: transparent; }
            #ExpiredDialogMessage {
                color: rgba(255,255,255,0.75); font-size: 13px; background: transparent;
                line-height: 1.6;
            }
            #ExpiredDialogGroupLabel {
                color: #4a9eff; font-size: 14px; font-weight: 600; background: transparent;
            }
            #ExpiredDialogCopyBtn {
                background: rgba(74,158,255,0.15); border: none; border-radius: 4px;
                color: #4a9eff; font-size: 12px;
            }
            #ExpiredDialogCopyBtn:hover { background: rgba(74,158,255,0.25); }
            #ExpiredDialogBuyLink {
                color: rgba(255,255,255,0.5); font-size: 12px; background: transparent;
            }
            #ExpiredDialogSep {
                color: rgba(255,255,255,0.3); font-size: 12px; background: transparent;
                margin: 4px 0;
            }
            #ExpiredDialogInput {
                background: rgba(255,255,255,0.06);
                border: 1px solid rgba(255,255,255,0.15); border-radius: 6px;
                padding: 0 10px; color: #fff; font-size: 14px;
                font-family: Consolas, monospace;
            }
            #ExpiredDialogInput:focus { border: 1px solid #4a9eff; }
            #ExpiredDialogStatus { font-size: 12px; background: transparent; }
            #ExpiredDialogButtonBar {
                background: #252525; border-top: 1px solid rgba(255,255,255,0.08);
            }
            #ExpiredDialogSecondaryBtn {
                background: rgba(255,255,255,0.05); border: none; border-radius: 8px;
                color: rgba(255,255,255,0.7); font-size: 13px;
            }
            #ExpiredDialogSecondaryBtn:hover {
                background: rgba(255,255,255,0.08); color: #fff;
            }
            #ExpiredDialogPrimaryBtn {
                background: #4a9eff; border: none; border-radius: 8px;
                color: #fff; font-size: 13px; font-weight: 600;
            }
            #ExpiredDialogPrimaryBtn:hover { background: #5aa9ff; }
            #ExpiredDialogPrimaryBtn:pressed { background: #3a8eef; }
            #ExpiredDialogTrialBtn {
                background: rgba(34,197,94,0.15); border: none; border-radius: 8px;
                color: #22c55e; font-size: 13px; font-weight: 600;
            }
            #ExpiredDialogTrialBtn:hover { background: rgba(34,197,94,0.25); }
            #ExpiredDialogTrialBtn:pressed { background: rgba(34,197,94,0.35); }
        """

    def _get_light_styles(self):
        return """
            #ExpiredDialogContainer {
                background: #f5f5f5;
                border: 1px solid rgba(0,0,0,0.12);
                border-radius: 0px;
            }
            #ExpiredDialogTitleBar {
                background: #eee;
                border-bottom: 1px solid rgba(0,0,0,0.08);
            }
            #ExpiredDialogTitle {
                color: #dc2626; font-size: 16px; font-weight: 600; background: transparent;
            }
            #ExpiredDialogXButton {
                background: transparent; color: rgba(0,0,0,0.5);
                border: none; border-radius: 6px; font-size: 14px;
            }
            #ExpiredDialogXButton:hover {
                background: rgba(0,0,0,0.08); color: #000;
            }
            #ExpiredDialogContent { background: transparent; }
            #ExpiredDialogMessage {
                color: rgba(0,0,0,0.65); font-size: 13px; background: transparent;
            }
            #ExpiredDialogGroupLabel {
                color: #2563eb; font-size: 14px; font-weight: 600; background: transparent;
            }
            #ExpiredDialogCopyBtn {
                background: rgba(37,99,235,0.1); border: none; border-radius: 4px;
                color: #2563eb; font-size: 12px;
            }
            #ExpiredDialogCopyBtn:hover { background: rgba(37,99,235,0.18); }
            #ExpiredDialogBuyLink {
                color: rgba(0,0,0,0.5); font-size: 12px; background: transparent;
            }
            #ExpiredDialogSep {
                color: rgba(0,0,0,0.3); font-size: 12px; background: transparent;
            }
            #ExpiredDialogInput {
                background: #fff; border: 1px solid rgba(0,0,0,0.15); border-radius: 6px;
                padding: 0 10px; color: #1a1a1a; font-size: 14px;
                font-family: Consolas, monospace;
            }
            #ExpiredDialogInput:focus { border: 1px solid #2563eb; }
            #ExpiredDialogStatus { font-size: 12px; background: transparent; }
            #ExpiredDialogButtonBar {
                background: #eee; border-top: 1px solid rgba(0,0,0,0.06);
            }
            #ExpiredDialogSecondaryBtn {
                background: rgba(0,0,0,0.05); border: none; border-radius: 8px;
                color: rgba(0,0,0,0.6); font-size: 13px;
            }
            #ExpiredDialogSecondaryBtn:hover {
                background: rgba(0,0,0,0.08); color: #000;
            }
            #ExpiredDialogPrimaryBtn {
                background: #2563eb; border: none; border-radius: 8px;
                color: #fff; font-size: 13px; font-weight: 600;
            }
            #ExpiredDialogPrimaryBtn:hover { background: #3b82f6; }
            #ExpiredDialogPrimaryBtn:pressed { background: #1d4ed8; }
            #ExpiredDialogTrialBtn {
                background: rgba(22,163,74,0.12); border: none; border-radius: 8px;
                color: #16a34a; font-size: 13px; font-weight: 600;
            }
            #ExpiredDialogTrialBtn:hover { background: rgba(22,163,74,0.2); }
            #ExpiredDialogTrialBtn:pressed { background: rgba(22,163,74,0.3); }
        """
