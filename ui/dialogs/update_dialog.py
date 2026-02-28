# -*- coding: utf-8 -*-

"""
更新提示对话框

现代化设计的更新提示对话框，支持：
- 显示新版本号和更新日志
- 立即更新（打开浏览器）
- 稍后提醒
- 跳过此版本
- 强制更新模式
- 隐私政策链接

完全符合项目主题风格
"""

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
    QPushButton, QWidget, QTextEdit, QGraphicsDropShadowEffect
)
from PyQt6.QtCore import Qt, QUrl
from PyQt6.QtGui import QDesktopServices
from core.logger import get_logger

logger = get_logger(__name__)


class UpdateDialog(QDialog):
    """更新提示对话框"""
    
    RESULT_UPDATE = 1  # 立即更新
    RESULT_LATER = 2  # 稍后提醒
    RESULT_SKIP = 3  # 跳过此版本
    
    def __init__(self, version_info: dict, force_update: bool = False, parent=None):
        """
        初始化更新对话框
        
        Args:
            version_info: 版本信息字典，包含 version, download_url, changelog 等
            force_update: 是否强制更新
            parent: 父窗口
        """
        super().__init__(parent)
        self.version_info = version_info
        self.force_update = force_update
        self.result_action = self.RESULT_LATER
        self.init_ui()
        
    def init_ui(self):
        """初始化界面"""
        # 设置窗口图标
        from pathlib import Path
        from PyQt6.QtGui import QIcon
        icon_path = Path(__file__).parent.parent.parent / "resources" / "tubiao.ico"
        if icon_path.exists():
            self.setWindowIcon(QIcon(str(icon_path)))
        
        # 无边框，透明背景
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint | 
            Qt.WindowType.Dialog
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setModal(True)
        self.setFixedSize(600, 500)
        
        # 应用内联样式
        self.setStyleSheet(self._get_inline_styles())
        
        # 主容器
        main_container = QWidget()
        main_container.setObjectName("UpdateDialogContainer")
        
        # 添加阴影效果
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(30)
        shadow.setColor(Qt.GlobalColor.black)
        shadow.setOffset(0, 4)
        main_container.setGraphicsEffect(shadow)
        
        main_layout = QVBoxLayout(main_container)
        main_layout.setContentsMargins(30, 30, 30, 30)
        main_layout.setSpacing(20)
        
        # 图标 + 标题行
        header_layout = QHBoxLayout()
        header_layout.setSpacing(12)
        
        # 图标
        icon_label = QLabel("🎉" if not self.force_update else "⚠️")
        icon_label.setObjectName("UpdateDialogIcon")
        icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        header_layout.addWidget(icon_label)
        
        # 标题
        title_text = "发现新版本" if not self.force_update else "重要更新"
        title_label = QLabel(title_text)
        title_label.setObjectName("UpdateDialogTitle")
        header_layout.addWidget(title_label)
        header_layout.addStretch()
        
        main_layout.addLayout(header_layout)
        
        # 版本信息
        version = self.version_info.get('version', 'Unknown')
        version_label = QLabel(f"最新版本：{version}")
        version_label.setObjectName("UpdateDialogVersion")
        main_layout.addWidget(version_label)
        
        # 更新日志标题
        changelog_title = QLabel("更新内容：")
        changelog_title.setObjectName("UpdateDialogChangelogTitle")
        main_layout.addWidget(changelog_title)
        
        # 更新日志内容（使用 TextEdit 显示）
        # 优先使用 changelog_summary，如果没有则使用 changelog_full，最后才是 changelog
        changelog = (
            self.version_info.get('changelog_summary') or 
            self.version_info.get('changelog_full') or 
            self.version_info.get('changelog') or 
            '暂无更新说明'
        )
        self.changelog_text = QTextEdit()
        self.changelog_text.setObjectName("UpdateDialogChangelog")
        self.changelog_text.setPlainText(changelog)
        self.changelog_text.setReadOnly(True)
        self.changelog_text.setMinimumHeight(150)
        main_layout.addWidget(self.changelog_text)
        
        # 隐私政策链接
        privacy_layout = QHBoxLayout()
        privacy_label = QLabel("查看")
        privacy_label.setObjectName("UpdateDialogPrivacyText")
        
        privacy_link = QLabel('<a href="#" style="color: #4a9eff; text-decoration: none;">隐私政策</a>')
        privacy_link.setObjectName("UpdateDialogPrivacyLink")
        privacy_link.setOpenExternalLinks(False)
        privacy_link.linkActivated.connect(self._on_privacy_clicked)
        privacy_link.setCursor(Qt.CursorShape.PointingHandCursor)
        
        privacy_layout.addWidget(privacy_label)
        privacy_layout.addWidget(privacy_link)
        privacy_layout.addStretch()
        
        main_layout.addLayout(privacy_layout)
        
        main_layout.addSpacing(10)
        
        # 按钮布局
        button_layout = QHBoxLayout()
        button_layout.setSpacing(12)
        
        # 根据是否强制更新显示不同的按钮
        if not self.force_update:
            # 跳过此版本按钮
            skip_btn = QPushButton("跳过此版本")
            skip_btn.setObjectName("UpdateDialogSkipButton")
            skip_btn.setMinimumHeight(44)
            skip_btn.setMinimumWidth(110)
            skip_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            skip_btn.clicked.connect(self._on_skip_clicked)
            button_layout.addWidget(skip_btn)
            
            # 稍后提醒按钮
            later_btn = QPushButton("稍后提醒")
            later_btn.setObjectName("UpdateDialogLaterButton")
            later_btn.setMinimumHeight(44)
            later_btn.setMinimumWidth(110)
            later_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            later_btn.clicked.connect(self._on_later_clicked)
            button_layout.addWidget(later_btn)
        else:
            # 强制更新模式下显示提示文本和退出按钮
            force_label = QLabel("此更新为重要安全更新，建议立即更新")
            force_label.setObjectName("UpdateDialogForceText")
            button_layout.addWidget(force_label)
            
            button_layout.addStretch()
            
            # 退出程序按钮
            quit_btn = QPushButton("退出程序")
            quit_btn.setObjectName("UpdateDialogLaterButton")
            quit_btn.setMinimumHeight(44)
            quit_btn.setMinimumWidth(110)
            quit_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            quit_btn.clicked.connect(self._on_quit_clicked)
            button_layout.addWidget(quit_btn)
        
        # 立即更新按钮（主要）
        update_btn = QPushButton("立即更新")
        update_btn.setObjectName("UpdateDialogUpdateButton")
        update_btn.setMinimumHeight(44)
        update_btn.setMinimumWidth(120)
        update_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        update_btn.clicked.connect(self._on_update_clicked)
        button_layout.addWidget(update_btn)
        
        main_layout.addLayout(button_layout)
        
        # 设置主布局
        container_layout = QVBoxLayout(self)
        container_layout.setContentsMargins(0, 0, 0, 0)
        container_layout.addWidget(main_container)

    def _on_update_clicked(self):
        """处理"立即更新"按钮"""
        self.result_action = self.RESULT_UPDATE
        logger.info(f"用户选择：立即更新到版本 {self.version_info.get('version')}")
        
        # 跳转到网站首页，用户在网站上选择下载方式
        from core.server_config import get_server_base_url
        website_url = get_server_base_url()
        
        try:
            QDesktopServices.openUrl(QUrl(website_url))
            logger.info(f"Opening website: {website_url}")
        except Exception as e:
            logger.error(f"Failed to open website: {e}")
        
        if self.force_update:
            # 强制更新模式：不关闭对话框，用户无法绕过
            # 对话框保持打开，用户只能去网站下载更新
            pass
        else:
            self.accept()
        
    def _on_later_clicked(self):
        """处理"稍后提醒"按钮"""
        self.result_action = self.RESULT_LATER
        logger.info("用户选择：稍后提醒")
        self.reject()
        
    def _on_skip_clicked(self):
        """处理"跳过此版本"按钮"""
        self.result_action = self.RESULT_SKIP
        logger.info(f"用户选择：跳过版本 {self.version_info.get('version')}")
        self.accept()
    
    def _on_quit_clicked(self):
        """处理"退出程序"按钮（强制更新模式）"""
        logger.info("用户选择：退出程序（强制更新未完成）")
        import sys
        sys.exit(0)
    
    def closeEvent(self, event):
        """拦截关闭事件，强制更新时不允许关闭"""
        if self.force_update:
            event.ignore()
        else:
            super().closeEvent(event)
    
    def keyPressEvent(self, event):
        """拦截按键事件，强制更新时不允许 ESC 关闭"""
        if self.force_update and event.key() == Qt.Key.Key_Escape:
            event.ignore()
        else:
            super().keyPressEvent(event)
        
    def _on_privacy_clicked(self):
        """处理隐私政策链接点击"""
        logger.info("Opening privacy policy")
        # 打开隐私政策页面（可以是本地文件或网页）
        from core.server_config import get_server_base_url
        privacy_url = f"{get_server_base_url()}/privacy"
        try:
            QDesktopServices.openUrl(QUrl(privacy_url))
        except Exception as e:
            logger.error(f"Failed to open privacy policy: {e}")
        
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
    def show_update_dialog(version_info: dict, force_update: bool = False, parent=None):
        """
        静态方法：显示更新对话框并返回用户选择
        
        Args:
            version_info: 版本信息字典
            force_update: 是否强制更新
            parent: 父窗口
            
        Returns:
            result_action: RESULT_UPDATE, RESULT_LATER, 或 RESULT_SKIP
        """
        dialog = UpdateDialog(version_info, force_update, parent)
        dialog.exec()
        return dialog.result_action
    
    def _get_inline_styles(self):
        """获取内联样式 - 完全符合项目主题"""
        try:
            from core.utils.style_system import get_current_theme
            is_light = get_current_theme() == "modern_light"
        except Exception:
            is_light = False
        
        if is_light:
            return """
                #UpdateDialogContainer {
                    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #f5f5f5, stop:1 #eeeeee);
                    border: 1px solid rgba(0, 0, 0, 0.12);
                    border-radius: 16px;
                }
                #UpdateDialogIcon { font-size: 32px; color: #4a9eff; background: transparent; }
                #UpdateDialogTitle { color: #1a1a1a; font-size: 18px; font-weight: 600; background: transparent; }
                #UpdateDialogVersion { color: #4a9eff; font-size: 16px; font-weight: 500; background: transparent; }
                #UpdateDialogChangelogTitle { color: rgba(0, 0, 0, 0.8); font-size: 14px; font-weight: 500; background: transparent; }
                #UpdateDialogChangelog {
                    background: rgba(0, 0, 0, 0.03); border: 1px solid rgba(0, 0, 0, 0.08);
                    border-radius: 8px; color: rgba(0, 0, 0, 0.7); font-size: 13px; padding: 12px;
                }
                #UpdateDialogChangelog:focus { border-color: rgba(74, 158, 255, 0.3); }
                #UpdateDialogPrivacyText { color: rgba(0, 0, 0, 0.5); font-size: 12px; background: transparent; }
                #UpdateDialogPrivacyLink { color: #4a9eff; font-size: 12px; background: transparent; }
                #UpdateDialogPrivacyLink:hover { color: #3a8eef; }
                #UpdateDialogForceText { color: #ef4444; font-size: 13px; font-weight: 500; background: transparent; }
                #UpdateDialogSkipButton {
                    background: rgba(0, 0, 0, 0.05); border: 1px solid rgba(0, 0, 0, 0.12);
                    border-radius: 10px; color: rgba(0, 0, 0, 0.6); font-size: 14px; font-weight: 500; padding: 10px 20px;
                }
                #UpdateDialogSkipButton:hover { background: rgba(0, 0, 0, 0.08); color: rgba(0, 0, 0, 0.8); }
                #UpdateDialogSkipButton:pressed { background: rgba(0, 0, 0, 0.12); }
                #UpdateDialogLaterButton {
                    background: rgba(0, 0, 0, 0.05); border: 1px solid rgba(0, 0, 0, 0.12);
                    border-radius: 10px; color: rgba(0, 0, 0, 0.7); font-size: 14px; font-weight: 500; padding: 10px 20px;
                }
                #UpdateDialogLaterButton:hover { background: rgba(0, 0, 0, 0.1); color: rgba(0, 0, 0, 0.9); }
                #UpdateDialogLaterButton:pressed { background: rgba(0, 0, 0, 0.15); }
                #UpdateDialogUpdateButton {
                    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #4a9eff, stop:1 #5aa9ff);
                    border: none; border-radius: 10px; color: #ffffff; font-size: 14px; font-weight: 600; padding: 10px 20px;
                }
                #UpdateDialogUpdateButton:hover { background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #5aa9ff, stop:1 #6bb6ff); }
                #UpdateDialogUpdateButton:pressed { background: #3a8eef; }
            """
        return """
            /* 主容器 - 使用项目的背景渐变 */
            #UpdateDialogContainer {
                background: qlineargradient(
                    x1:0, y1:0, x2:0, y2:1,
                    stop:0 #252525,
                    stop:1 #2c2c2c
                );
                border: 1px solid rgba(255, 255, 255, 0.2);
                border-radius: 16px;
            }
            
            /* 图标 - 使用项目主色调 */
            #UpdateDialogIcon {
                font-size: 32px;
                color: #4a9eff;
                background: transparent;
            }
            
            /* 标题 - 使用项目文本色 */
            #UpdateDialogTitle {
                color: #ffffff;
                font-size: 18px;
                font-weight: 600;
                background: transparent;
            }
            
            /* 版本号 - 使用项目主色调 */
            #UpdateDialogVersion {
                color: #4a9eff;
                font-size: 16px;
                font-weight: 500;
                background: transparent;
            }
            
            /* 更新日志标题 */
            #UpdateDialogChangelogTitle {
                color: rgba(255, 255, 255, 0.9);
                font-size: 14px;
                font-weight: 500;
                background: transparent;
            }
            
            /* 更新日志内容 */
            #UpdateDialogChangelog {
                background: rgba(255, 255, 255, 0.05);
                border: 1px solid rgba(255, 255, 255, 0.1);
                border-radius: 8px;
                color: rgba(255, 255, 255, 0.8);
                font-size: 13px;
                padding: 12px;
                line-height: 1.6;
            }
            
            #UpdateDialogChangelog:focus {
                border-color: rgba(74, 158, 255, 0.3);
            }
            
            /* 隐私政策文本 */
            #UpdateDialogPrivacyText {
                color: rgba(255, 255, 255, 0.6);
                font-size: 12px;
                background: transparent;
            }
            
            /* 隐私政策链接 */
            #UpdateDialogPrivacyLink {
                color: #4a9eff;
                font-size: 12px;
                background: transparent;
            }
            
            #UpdateDialogPrivacyLink:hover {
                color: #5aa9ff;
            }
            
            /* 强制更新提示文本 */
            #UpdateDialogForceText {
                color: #fca5a5;
                font-size: 13px;
                font-weight: 500;
                background: transparent;
            }
            
            /* 跳过此版本按钮 */
            #UpdateDialogSkipButton {
                background: rgba(255, 255, 255, 0.08);
                border: 1px solid rgba(255, 255, 255, 0.15);
                border-radius: 10px;
                color: rgba(255, 255, 255, 0.7);
                font-size: 14px;
                font-weight: 500;
                padding: 10px 20px;
            }
            
            #UpdateDialogSkipButton:hover {
                background: rgba(255, 255, 255, 0.12);
                border-color: rgba(255, 255, 255, 0.25);
                color: rgba(255, 255, 255, 0.85);
            }
            
            #UpdateDialogSkipButton:pressed {
                background: rgba(255, 255, 255, 0.15);
            }
            
            /* 稍后提醒按钮 */
            #UpdateDialogLaterButton {
                background: rgba(255, 255, 255, 0.08);
                border: 1px solid rgba(255, 255, 255, 0.15);
                border-radius: 10px;
                color: rgba(255, 255, 255, 0.8);
                font-size: 14px;
                font-weight: 500;
                padding: 10px 20px;
            }
            
            #UpdateDialogLaterButton:hover {
                background: rgba(255, 255, 255, 0.15);
                border-color: rgba(255, 255, 255, 0.25);
                color: rgba(255, 255, 255, 0.95);
            }
            
            #UpdateDialogLaterButton:pressed {
                background: rgba(255, 255, 255, 0.20);
            }
            
            /* 立即更新按钮（主要） - 使用项目主色调 */
            #UpdateDialogUpdateButton {
                background: qlineargradient(
                    x1:0, y1:0, x2:1, y2:0,
                    stop:0 #4a9eff,
                    stop:1 #5aa9ff
                );
                border: none;
                border-radius: 10px;
                color: #ffffff;
                font-size: 14px;
                font-weight: 600;
                padding: 10px 20px;
            }
            
            #UpdateDialogUpdateButton:hover {
                background: qlineargradient(
                    x1:0, y1:0, x2:1, y2:0,
                    stop:0 #5aa9ff,
                    stop:1 #6bb6ff
                );
            }
            
            #UpdateDialogUpdateButton:pressed {
                background: #3a8eef;
            }
        """
