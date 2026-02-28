# -*- coding: utf-8 -*-

"""
AI助手聊天输入框 - ChatGPT风格
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTextEdit, 
    QPushButton, QFrame, QGraphicsDropShadowEffect, QSizePolicy,
    QMenu, QLabel
)
from PyQt6.QtCore import Qt, QSize, pyqtSignal, QPropertyAnimation, QEasingCurve, pyqtProperty, QPoint
from PyQt6.QtGui import QPainter, QColor, QTextOption, QAction, QIcon
from PyQt6.QtSvg import QSvgRenderer
from pathlib import Path


class AttachmentTag(QFrame):
    """附件标签组件"""
    removed = pyqtSignal()  # 移除信号
    
    def __init__(self, text: str, tag_type: str = "asset", parent=None):
        super().__init__(parent)
        self.tag_type = tag_type
        self.setObjectName("AttachmentTag")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 4, 4, 4)
        layout.setSpacing(4)
        
        # 图标
        icon = "📦" if tag_type == "asset" else "⚙️"
        icon_label = QLabel(icon)
        icon_label.setStyleSheet("font-size: 12px;")
        layout.addWidget(icon_label)
        
        # 文本
        self.text_label = QLabel(text)
        self.text_label.setObjectName("AttachmentTagText")
        layout.addWidget(self.text_label)
        
        # 删除按钮
        close_btn = QPushButton("×")
        close_btn.setObjectName("AttachmentTagClose")
        close_btn.setFixedSize(16, 16)
        close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        close_btn.clicked.connect(self._on_remove)
        layout.addWidget(close_btn)
        
        # 设置样式
        self._apply_style()
    
    def _apply_style(self):
        """应用样式"""
        from core.utils.style_system import get_current_theme
        current_theme = get_current_theme()
        is_light = current_theme == "modern_light"
        
        if is_light:
            self.setStyleSheet("""
                QFrame#AttachmentTag {
                    background-color: #E8F4FD;
                    border: 1px solid #B8D4E8;
                    border-radius: 12px;
                }
                QLabel#AttachmentTagText {
                    color: #1976D2;
                    font-size: 12px;
                }
                QPushButton#AttachmentTagClose {
                    background-color: transparent;
                    border: none;
                    color: #1976D2;
                    font-size: 14px;
                    font-weight: bold;
                }
                QPushButton#AttachmentTagClose:hover {
                    color: #D32F2F;
                }
            """)
        else:
            self.setStyleSheet("""
                QFrame#AttachmentTag {
                    background-color: #1E3A5F;
                    border: 1px solid #2E5A8F;
                    border-radius: 12px;
                }
                QLabel#AttachmentTagText {
                    color: #64B5F6;
                    font-size: 12px;
                }
                QPushButton#AttachmentTagClose {
                    background-color: transparent;
                    border: none;
                    color: #64B5F6;
                    font-size: 14px;
                    font-weight: bold;
                }
                QPushButton#AttachmentTagClose:hover {
                    color: #EF5350;
                }
            """)
    
    def _on_remove(self):
        """移除标签"""
        self.removed.emit()
        self.deleteLater()


class AnimatedCircleButton(QPushButton):
    """带动画的圆形按钮"""
    
    def __init__(self, icon_path=None, is_primary=False, parent=None):
        super().__init__(parent)
        self.setFixedSize(32, 32)
        self.icon_path = icon_path
        if icon_path and Path(icon_path).exists():
            self.svg_renderer = QSvgRenderer(icon_path)
        else:
            self.svg_renderer = None
        
        self.is_primary = is_primary
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        
        # 背景透明度动画
        self._bg_opacity = 0.0
        self.bg_anim = QPropertyAnimation(self, b"bgOpacity")
        self.bg_anim.setDuration(150)
        self.bg_anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        
        # 设置ObjectName以关联QSS
        if is_primary:
            self.setObjectName("ChatSendButton")
        else:
            self.setObjectName("ChatAddButton")
    
    def setEnabled(self, enabled):
        """重写setEnabled以触发重绘"""
        super().setEnabled(enabled)
        self.update()
        
    @pyqtProperty(float)
    def bgOpacity(self):
        return self._bg_opacity
    
    @bgOpacity.setter
    def bgOpacity(self, value):
        self._bg_opacity = value
        self.update()
    
    def enterEvent(self, event):
        """鼠标进入"""
        self.bg_anim.stop()
        self.bg_anim.setStartValue(self._bg_opacity)
        self.bg_anim.setEndValue(0.5)
        self.bg_anim.start()
        super().enterEvent(event)
    
    def leaveEvent(self, event):
        """鼠标离开"""
        self.bg_anim.stop()
        self.bg_anim.setStartValue(self._bg_opacity)
        self.bg_anim.setEndValue(0.0)
        self.bg_anim.start()
        super().leaveEvent(event)
    
    def paintEvent(self, event):
        """绘制按钮"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # 获取当前样式表中定义的背景色
        from core.utils.style_system import get_current_theme
        current_theme = get_current_theme()
        is_light_theme = current_theme == "modern_light"
        
        # 根据状态和主题选择背景色
        if not self.isEnabled():
            # 禁用状态
            bg_color = QColor("#DCDCDC") if is_light_theme else QColor("#646464")
        elif self.is_primary:
            # 发送按钮
            base_color = QColor("#000000") if is_light_theme else QColor("#FFFFFF")
            hover_color = QColor("#202123") if is_light_theme else QColor("#F0F0F0")
            # 混合背景色和悬停色
            bg_color = QColor(
                int(base_color.red() * (1 - self._bg_opacity) + hover_color.red() * self._bg_opacity),
                int(base_color.green() * (1 - self._bg_opacity) + hover_color.green() * self._bg_opacity),
                int(base_color.blue() * (1 - self._bg_opacity) + hover_color.blue() * self._bg_opacity)
            )
        else:
            # 添加按钮 - 悬停时显示灰色背景
            if self._bg_opacity > 0:
                bg_color = QColor(128, 128, 128, int(255 * self._bg_opacity * 0.2))
            else:
                bg_color = QColor(0, 0, 0, 0)
        
        # 绘制圆形背景
        painter.setBrush(bg_color)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(0, 0, 32, 32)
        
        # 绘制SVG图标
        if self.svg_renderer:
            icon_size = 16
            icon_x = (32 - icon_size) / 2
            icon_y = (32 - icon_size) / 2
            
            painter.save()
            from PyQt6.QtCore import QRectF
            icon_rect = QRectF(icon_x, icon_y, icon_size, icon_size)
            self.svg_renderer.render(painter, icon_rect)
            painter.restore()


class AnimatedTextEdit(QTextEdit):
    """带动画的文本编辑框"""
    
    def __init__(self, input_box_parent=None):
        super().__init__()
        self._focused = False
        self.input_box_parent = input_box_parent
        
        # 设置ObjectName以关联QSS
        self.setObjectName("ChatInput")
        
        # 设置高质量字体渲染（抗锯齿）
        from PyQt6.QtGui import QFont
        font = self.font()
        font.setHintingPreference(QFont.HintingPreference.PreferFullHinting)
        font.setStyleStrategy(QFont.StyleStrategy.PreferAntialias | QFont.StyleStrategy.PreferQuality)
        self.setFont(font)
        
        # 设置文档边距来控制垂直间距（避免 placeholder 和实际文本位置不一致）
        self.document().setDocumentMargin(6)
        # 启用自动换行
        self.setLineWrapMode(QTextEdit.LineWrapMode.WidgetWidth)
        # 允许垂直方向扩展
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        # 垂直滚动条初始隐藏
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        
        # 连接文档内容变化信号，动态调整高度
        self.document().contentsChanged.connect(self._adjust_height)
    
    def _adjust_height(self):
        """根据内容动态调整高度"""
        text = self.toPlainText()
        
        # 如果文本为空，直接设置为最小高度
        if not text:
            self.setFixedHeight(36)
            self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
            return
        
        # 获取文档的实际高度
        doc_height = self.document().size().height()
        
        # 单行文本：blockCount 为 1 且文档高度在单行范围内
        # documentMargin(6)*2=12, 16px字号行高约22px, 单行 doc_height ≈ 34px
        if doc_height <= 36:
            self.setFixedHeight(36)
            self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
            return
        
        # 多行文本，根据文档高度计算
        new_height = int(doc_height) + 12  # 6px * 2
        new_height = max(36, min(new_height, 150))
        self.setFixedHeight(new_height)
        
        # 只在达到最大高度时显示滚动条
        if new_height >= 150:
            self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        else:
            self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
    
    def focusInEvent(self, event):
        """获得焦点"""
        self._focused = True
        super().focusInEvent(event)
    
    def focusOutEvent(self, event):
        """失去焦点"""
        self._focused = False
        super().focusOutEvent(event)
    
    def keyPressEvent(self, event):
        """处理按键事件"""
        # Enter发送，Shift+Enter换行
        if event.key() == Qt.Key.Key_Return or event.key() == Qt.Key.Key_Enter:
            if event.modifiers() == Qt.KeyboardModifier.ShiftModifier:
                # Shift+Enter：换行
                super().keyPressEvent(event)
            else:
                # Enter：发送消息
                if self.input_box_parent:
                    self.input_box_parent._on_send()
        else:
            super().keyPressEvent(event)


class ChatInputBox(QWidget):
    """聊天输入框组件"""
    
    send_signal = pyqtSignal(str, list)  # 发送消息信号，包含文本和附件列表
    add_asset_signal = pyqtSignal()  # 添加资产信号
    add_config_signal = pyqtSignal()  # 添加配置信号
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.icon_dir = Path(__file__).parent.parent.parent.parent / "resources" / "icons"
        self.attachments = []  # 附件列表 [{'type': 'asset'/'config', 'name': str, 'path': str, 'data': dict}]
        self.init_ui()
    
    def init_ui(self):
        """初始化UI"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        # 创建水平布局用于居中
        h_layout = QHBoxLayout()
        h_layout.setContentsMargins(0, 0, 0, 5)  # 上边距0px，下边距5px给阴影
        h_layout.addStretch(1)
        
        # 创建主容器（包含附件区和输入框）
        main_container = QWidget()
        main_container.setMaximumWidth(950)
        main_container.setMinimumWidth(800)
        main_layout = QVBoxLayout(main_container)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(4)
        
        # === 附件标签区域 ===
        self.attachments_container = QWidget()
        self.attachments_container.setObjectName("AttachmentsContainer")
        self.attachments_layout = QHBoxLayout(self.attachments_container)
        self.attachments_layout.setContentsMargins(14, 0, 14, 0)
        self.attachments_layout.setSpacing(8)
        self.attachments_layout.addStretch()
        self.attachments_container.hide()  # 初始隐藏
        main_layout.addWidget(self.attachments_container)
        
        # 创建输入框容器
        self.input_container = QFrame()
        self.input_container.setObjectName("ChatInputContainer")
        self.input_container.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        input_layout = QHBoxLayout(self.input_container)
        input_layout.setContentsMargins(14, 10, 14, 10)  # 左右边距增加到14px，避免按钮被圆角裁剪
        input_layout.setSpacing(0)
        
        # 获取图标路径
        icon_dir = Path(__file__).parent.parent.parent.parent / "resources" / "icons"
        
        # 根据当前主题选择图标
        from core.utils.style_system import get_current_theme
        current_theme = get_current_theme()
        is_light_theme = current_theme == "modern_light"
        
        # === 左侧：添加文件按钮 ===
        # 浅色主题：黑色加号，深色主题：白色加号
        plus_icon = "plus.svg" if is_light_theme else "plus_white.svg"
        self.add_file_btn = AnimatedCircleButton(str(icon_dir / plus_icon), is_primary=False)
        self.add_file_btn.setToolTip("添加文件")
        self.add_file_btn.clicked.connect(self._on_add_file)
        input_layout.addWidget(self.add_file_btn, 0, Qt.AlignmentFlag.AlignVCenter)
        input_layout.addSpacing(8)  # 按钮和输入框之间留8px间距
        
        # === 中间：输入框 ===
        self.input_edit = AnimatedTextEdit(input_box_parent=self)
        self.input_edit.setPlaceholderText("询问任何问题")
        self.input_edit.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        
        # 设置 placeholder 颜色（QTextEdit placeholder 不受 QSS color 控制）
        from PyQt6.QtGui import QPalette, QColor as _QColor
        _palette = self.input_edit.palette()
        is_light = get_current_theme() == "modern_light"
        _palette.setColor(QPalette.ColorRole.PlaceholderText, _QColor(160, 160, 160) if is_light else _QColor(128, 128, 128))
        self.input_edit.setPalette(_palette)
        # 初始化时调整一次高度
        self.input_edit._adjust_height()
        self.input_edit.textChanged.connect(self._on_text_changed)
        input_layout.addWidget(self.input_edit, 1)
        input_layout.addSpacing(8)  # 输入框和按钮之间留8px间距
        
        # === 右侧：发送按钮 ===
        # 浅色主题：黑色背景配白色箭头，深色主题：白色背景配黑色箭头
        arrow_icon = "arrow_up_white.svg" if is_light_theme else "arrow_up.svg"
        self.send_btn = AnimatedCircleButton(str(icon_dir / arrow_icon), is_primary=True)
        self.send_btn.setToolTip("发送")
        self.send_btn.clicked.connect(self._on_send)
        self.send_btn.setEnabled(False)
        input_layout.addWidget(self.send_btn, 0, Qt.AlignmentFlag.AlignVCenter)
        
        # 注意：不使用 QGraphicsDropShadowEffect，它会导致圆角容器出现像素残留
        
        main_layout.addWidget(self.input_container)
        
        h_layout.addWidget(main_container)
        h_layout.addStretch(1)
        
        layout.addLayout(h_layout)
    
    def _on_text_changed(self):
        """文本改变时的处理"""
        # 更新发送按钮状态
        self._update_send_button()
        
        # 动态调整高度（文档高度 + 上下 padding 8*2 = 16）
        doc_height = self.input_edit.document().size().height()
        new_height = min(max(40, int(doc_height) + 16), 150)
        
        # 使用动画调整高度
        if self.input_edit.height() != new_height:
            self.input_edit.setMaximumHeight(new_height)
            self.input_edit.setMinimumHeight(new_height)
            
            # 强制更新父容器布局
            self.input_container.updateGeometry()
            self.updateGeometry()
            
            # 高度超过40px时显示滚动条
            if new_height > 40:
                self.input_edit.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
            else:
                self.input_edit.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
    
    def _on_send(self):
        """发送消息"""
        text = self.input_edit.toPlainText().strip()
        if text or self.attachments:
            # 发送消息和附件
            self.send_signal.emit(text, self.attachments.copy())
            
            # 清空输入框
            self.input_edit.document().contentsChanged.disconnect(self.input_edit._adjust_height)
            self.input_edit.clear()
            self.input_edit.document().setDocumentMargin(6)
            self.input_edit.setFixedHeight(36)
            self.input_edit.document().contentsChanged.connect(self.input_edit._adjust_height)
            
            # 清空附件
            self._clear_attachments()
    
    def add_attachment(self, attachment_type: str, name: str, path: str, data: dict = None):
        """添加附件
        
        Args:
            attachment_type: 附件类型 ('asset' 或 'config')
            name: 显示名称
            path: 路径
            data: 附加数据（如资产的树形结构）
        """
        # 检查是否已存在
        for att in self.attachments:
            if att['path'] == path:
                return  # 已存在，不重复添加
        
        # 添加到列表
        attachment = {
            'type': attachment_type,
            'name': name,
            'path': path,
            'data': data or {}
        }
        self.attachments.append(attachment)
        
        # 创建标签
        tag = AttachmentTag(name, attachment_type)
        tag.removed.connect(lambda: self._remove_attachment(path))
        
        # 插入到 stretch 之前
        self.attachments_layout.insertWidget(self.attachments_layout.count() - 1, tag)
        
        # 显示附件区域
        self.attachments_container.show()
        
        # 更新发送按钮状态
        self._update_send_button()
    
    def _remove_attachment(self, path: str):
        """移除附件"""
        self.attachments = [a for a in self.attachments if a['path'] != path]
        
        # 如果没有附件了，隐藏附件区域
        if not self.attachments:
            self.attachments_container.hide()
        
        # 更新发送按钮状态
        self._update_send_button()
    
    def _clear_attachments(self):
        """清空所有附件"""
        self.attachments.clear()
        
        # 清空标签
        while self.attachments_layout.count() > 1:  # 保留 stretch
            item = self.attachments_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        
        # 隐藏附件区域
        self.attachments_container.hide()
    
    def _update_send_button(self):
        """更新发送按钮状态"""
        text = self.input_edit.toPlainText().strip()
        self.send_btn.setEnabled(bool(text) or bool(self.attachments))
    
    def _on_add_file(self):
        """添加文件 - 显示弹出菜单"""
        # 创建弹出菜单
        menu = QMenu(self)
        menu.setObjectName("ChatAddMenu")
        
        # 设置菜单样式
        from core.utils.style_system import get_current_theme
        current_theme = get_current_theme()
        is_light_theme = current_theme == "modern_light"
        
        if is_light_theme:
            menu.setStyleSheet("""
                QMenu {
                    background-color: #FFFFFF;
                    border: none;
                    border-radius: 8px;
                    padding: 4px 0px;
                }
                QMenu::item {
                    padding: 8px 16px;
                    color: #333333;
                    font-size: 13px;
                }
                QMenu::item:selected {
                    background-color: #F0F0F0;
                    color: #000000;
                }
                QMenu::icon {
                    padding-left: 8px;
                }
            """)
        else:
            menu.setStyleSheet("""
                QMenu {
                    background-color: #2D2D2D;
                    border: none;
                    border-radius: 8px;
                    padding: 4px 0px;
                }
                QMenu::item {
                    padding: 8px 16px;
                    color: #E0E0E0;
                    font-size: 13px;
                }
                QMenu::item:selected {
                    background-color: #404040;
                    color: #FFFFFF;
                }
                QMenu::icon {
                    padding-left: 8px;
                }
            """)
        
        # 添加"资产"选项
        asset_action = QAction("📦 资产", self)
        asset_action.triggered.connect(self._on_add_asset)
        menu.addAction(asset_action)
        
        # "配置"选项已移除
        # config_action = QAction("⚙️ 配置", self)
        # config_action.triggered.connect(self._on_add_config)
        # menu.addAction(config_action)
        
        # 在按钮上方显示菜单
        btn_pos = self.add_file_btn.mapToGlobal(QPoint(0, 0))
        menu_height = menu.sizeHint().height()
        menu.exec(QPoint(btn_pos.x(), btn_pos.y() - menu_height - 5))
    
    def _on_add_asset(self):
        """添加资产"""
        print("[DEBUG] 点击了添加资产")
        self.add_asset_signal.emit()
    
    def _on_add_config(self):
        """添加配置（已禁用）"""
        print("[DEBUG] 点击了添加配置")
        self.add_config_signal.emit()
    
    def update_theme(self):
        """主题切换时更新图标和颜色"""
        from core.utils.style_system import get_current_theme
        current_theme = get_current_theme()
        is_light_theme = current_theme == "modern_light"
        
        # 更新加号按钮图标
        plus_icon = "plus.svg" if is_light_theme else "plus_white.svg"
        plus_icon_path = str(self.icon_dir / plus_icon)
        if Path(plus_icon_path).exists():
            self.add_file_btn.icon_path = plus_icon_path
            self.add_file_btn.svg_renderer = QSvgRenderer(plus_icon_path)
            self.add_file_btn.update()
        
        # 更新发送按钮图标
        arrow_icon = "arrow_up_white.svg" if is_light_theme else "arrow_up.svg"
        arrow_icon_path = str(self.icon_dir / arrow_icon)
        if Path(arrow_icon_path).exists():
            self.send_btn.icon_path = arrow_icon_path
            self.send_btn.svg_renderer = QSvgRenderer(arrow_icon_path)
            self.send_btn.update()
        
        # 更新输入框 placeholder 颜色（QTextEdit placeholder 不受 QSS color 控制）
        from PyQt6.QtGui import QPalette, QColor
        palette = self.input_edit.palette()
        if is_light_theme:
            palette.setColor(QPalette.ColorRole.PlaceholderText, QColor(160, 160, 160))
        else:
            palette.setColor(QPalette.ColorRole.PlaceholderText, QColor(128, 128, 128))
        self.input_edit.setPalette(palette)
        
        # 强制刷新输入框容器样式（确保 QSS 背景色生效）
        self.input_container.style().unpolish(self.input_container)
        self.input_container.style().polish(self.input_container)
        self.input_container.update()
