# -*- coding: utf-8 -*-

"""
配置卡片组件

参考 modern_asset_card.py 的布局：
- 缩略图区域（显示配置图标）
- 版本徽标（蓝色，右上角）
- 类型徽标（橙色，左下角）
- 配置名称和描述
- 创建时间、文件数量、总大小
- 应用和删除按钮
"""

from pathlib import Path
from datetime import datetime
from typing import Optional

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QFrame
)
from PyQt6.QtCore import Qt, pyqtSignal, QRectF
from PyQt6.QtGui import QPainter, QPainterPath, QColor, QLinearGradient, QEnterEvent, QMouseEvent

from core.logger import get_logger
from ..logic.config_model import ConfigTemplate, ConfigType

logger = get_logger(__name__)


def format_size(size_bytes: int) -> str:
    """格式化文件大小"""
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    elif size_bytes < 1024 * 1024 * 1024:
        return f"{size_bytes / (1024 * 1024):.1f} MB"
    else:
        return f"{size_bytes / (1024 * 1024 * 1024):.2f} GB"


def format_time(dt: datetime) -> str:
    """格式化时间"""
    return dt.strftime("%Y-%m-%d")


class ModernThumbnailWidget(QWidget):
    """现代化缩略图容器"""

    def __init__(self, width: int, height: int, radius: int = 0,
                 bg_color: str = "#2c2c2c", text_color: str = "#b0b0b0", parent=None):
        super().__init__(parent)
        self.setFixedSize(width, height)
        self.radius = radius
        self.bg_color = bg_color
        self.text_color = text_color
        self._text = ""
        
        self.setObjectName("ModernThumbnailWidget")
    
    def update_colors(self, bg_color: str, text_color: str):
        """更新颜色（用于主题切换）"""
        self.bg_color = bg_color
        self.text_color = text_color
        self.update()
    
    def setText(self, text: str):
        """设置文本"""
        self._text = text
        self.update()

    def paintEvent(self, event):
        """绘制现代化缩略图"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)
        
        widget_rect = self.rect()
        w = widget_rect.width()
        h = widget_rect.height()
        
        # 创建圆角路径
        path = QPainterPath()
        path.addRoundedRect(QRectF(0.0, 0.0, float(w), float(h)), 
                           float(self.radius), float(self.radius))
        
        painter.setClipPath(path)
        
        # 使用当前主题的背景颜色
        painter.fillRect(0, 0, w, h, QColor(self.bg_color))
        
        if self._text:
            painter.setPen(QColor(self.text_color))
            font = painter.font()
            font.setPixelSize(48)
            font.setWeight(300)
            painter.setFont(font)
            painter.drawText(widget_rect, 
                           int(Qt.AlignmentFlag.AlignCenter), 
                           self._text)
        
        painter.end()


class ConfigCard(QFrame):
    """配置卡片组件"""

    apply_clicked = pyqtSignal(str)  # 发送配置名称
    delete_clicked = pyqtSignal(str)  # 发送配置名称

    def __init__(self, template: ConfigTemplate, theme: str = "dark", parent=None):
        super().__init__(parent)
        self.hide()
        self.template = template
        self.theme = theme
        self._is_hovered = False

        self.setObjectName("ConfigCard")
        self.setMouseTracking(True)
        self.setAttribute(Qt.WidgetAttribute.WA_Hover, True)
        self.setFocusPolicy(Qt.FocusPolicy.ClickFocus)
        
        if parent is None:
            self.setWindowFlags(Qt.WindowType.Widget)

        self._init_ui()

    def enterEvent(self, event: Optional[QEnterEvent]) -> None:
        """鼠标进入事件"""
        if event:
            self._update_hover_state(event.position().toPoint())
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:
        """鼠标离开事件"""
        self._is_hovered = False
        self.update()
        super().leaveEvent(event)

    def mouseMoveEvent(self, event: Optional[QMouseEvent]) -> None:
        """鼠标移动事件"""
        if event:
            self._update_hover_state(event.position().toPoint())
        super().mouseMoveEvent(event)

    def _update_hover_state(self, pos):
        """更新悬停状态"""
        is_over_button = self._is_mouse_over_button(pos)
        new_hover_state = not is_over_button

        if new_hover_state != self._is_hovered:
            self._is_hovered = new_hover_state
            self.update()
            if hasattr(self, 'apply_btn'):
                self.apply_btn.update()
            if hasattr(self, 'delete_btn'):
                self.delete_btn.update()

    def _is_mouse_over_button(self, pos):
        """检查鼠标是否在按钮区域"""
        if not hasattr(self, 'apply_btn') or not hasattr(self, 'delete_btn'):
            return False

        apply_rect = self.apply_btn.geometry()
        delete_rect = self.delete_btn.geometry()

        if apply_rect.contains(pos) or delete_rect.contains(pos):
            return True

        # 检查是否在两个按钮之间的间隙中
        if (apply_rect.top() <= pos.y() <= apply_rect.bottom() or
            delete_rect.top() <= pos.y() <= delete_rect.bottom()):
            if apply_rect.right() <= pos.x() <= delete_rect.left():
                return True

        return False

    def paintEvent(self, event):
        """自定义绘制 - 绘制平滑的圆角边框"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        rect = self.rect()
        radius = 0.0

        # 创建渐变
        gradient = QLinearGradient(0, 0, rect.width(), rect.height())

        if self._is_hovered:
            # 悬停状态的渐变
            if self.theme == "light":
                gradient.setColorAt(0, QColor("#ffffff"))
                gradient.setColorAt(0.3, QColor("#fefefe"))
                gradient.setColorAt(0.7, QColor("#fcfcfc"))
                gradient.setColorAt(1, QColor("#fafafa"))
            else:
                gradient.setColorAt(0, QColor("#424242"))
                gradient.setColorAt(0.3, QColor("#3c3c3c"))
                gradient.setColorAt(0.7, QColor("#363636"))
                gradient.setColorAt(1, QColor("#323232"))
        else:
            # 正常状态的渐变
            if self.theme == "light":
                gradient.setColorAt(0, QColor("#ffffff"))
                gradient.setColorAt(0.3, QColor("#ffffff"))
                gradient.setColorAt(0.7, QColor("#fefefe"))
                gradient.setColorAt(1, QColor("#fdfdfd"))
            else:
                gradient.setColorAt(0, QColor("#383838"))
                gradient.setColorAt(0.3, QColor("#323232"))
                gradient.setColorAt(0.7, QColor("#2c2c2c"))
                gradient.setColorAt(1, QColor("#282828"))

        # 绘制圆角矩形背景
        path = QPainterPath()
        path.addRoundedRect(QRectF(rect), radius, radius)
        painter.fillPath(path, gradient)

        # 绘制边框
        from PyQt6.QtGui import QPen
        if self._is_hovered:
            if self.theme == "light":
                pen = QPen(QColor(0, 0, 0, 102))
            else:
                pen = QPen(QColor(255, 255, 255, 153))
        else:
            if self.theme == "light":
                pen = QPen(QColor("#e8e8e8"))
            else:
                pen = QPen(QColor("#454545"))

        pen.setWidth(2)
        painter.setPen(pen)
        painter.drawRoundedRect(QRectF(rect).adjusted(1, 1, -1, -1), radius, radius)

        painter.end()

        if hasattr(self, 'apply_btn'):
            self.apply_btn.update()
        if hasattr(self, 'delete_btn'):
            self.delete_btn.update()
    
    def _init_ui(self):
        """初始化UI"""
        self.setFixedSize(220, 314)

        # 根据主题设置颜色
        if self.theme == "light":
            colors = {
                'thumbnail_bg': '#f5f5f5',
                'thumbnail_text': '#cccccc',
            }
        else:
            colors = {
                'thumbnail_bg': '#323232',
                'thumbnail_text': '#707070',
            }

        layout = QVBoxLayout()
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(0)

        # 缩略图容器
        thumbnail_container = QWidget()
        thumbnail_container.setObjectName("ThumbnailContainer")
        thumbnail_container.setFixedSize(212, 153)

        self.thumbnail_label = ModernThumbnailWidget(
            width=212, height=153, radius=0,
            bg_color=colors['thumbnail_bg'],
            text_color=colors['thumbnail_text'],
            parent=thumbnail_container
        )
        self.thumbnail_label.setCursor(Qt.CursorShape.ArrowCursor)
        self.thumbnail_label.move(0, 0)
        
        # 设置配置图标
        icon = "⚙️" if self.template.type == ConfigType.EDITOR_PREFERENCES else "📋"
        self.thumbnail_label.setText(icon)

        # 版本徽标 - 右上角（蓝色）
        version_badge = self.template.config_version
        self.version_label = QLabel(version_badge, thumbnail_container)
        self.version_label.setObjectName("VersionLabel")
        self.version_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.version_label.setTextInteractionFlags(Qt.TextInteractionFlag.NoTextInteraction)
        self.version_label.setCursor(Qt.CursorShape.ArrowCursor)
        
        self.version_label.setStyleSheet("""
            QLabel {
                color: #ffffff;
                font-size: 11px;
                font-weight: bold;
                background-color: rgba(0, 122, 204, 0.85);
                border-radius: 3px;
                padding: 3px 6px;
            }
        """)
        
        self.version_label.setFixedSize(self.version_label.sizeHint())
        self.version_label.move(212 - 10 - self.version_label.width(), 10)
        
        # 类型徽标 - 左下角（橙色）
        type_text = self.template.type.display_name
        self.type_label = QLabel(type_text, thumbnail_container)
        self.type_label.setObjectName("TypeLabel")
        self.type_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.type_label.setTextInteractionFlags(Qt.TextInteractionFlag.NoTextInteraction)
        self.type_label.setCursor(Qt.CursorShape.ArrowCursor)
        
        self.type_label.setStyleSheet("""
            QLabel {
                color: #ffffff;
                font-size: 11px;
                font-weight: bold;
                background-color: rgba(255, 152, 0, 0.85);
                border-radius: 3px;
                padding: 3px 6px;
            }
        """)
        
        self.type_label.setFixedSize(self.type_label.sizeHint())
        self.type_label.move(10, 153 - 10 - self.type_label.height())

        layout.addWidget(thumbnail_container)

        # 内容区域
        content_widget = QWidget()
        content_widget.setObjectName("ContentWidget")
        content_layout = QVBoxLayout(content_widget)
        content_layout.setContentsMargins(12, 10, 12, 12)
        content_layout.setSpacing(6)

        # 名称
        self.name_label = QLabel(self.template.name)
        self.name_label.setObjectName("NameLabel")
        self.name_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.name_label.setWordWrap(True)
        self.name_label.setTextInteractionFlags(Qt.TextInteractionFlag.NoTextInteraction)
        self.name_label.setCursor(Qt.CursorShape.ArrowCursor)
        self.name_label.setMaximumHeight(40)
        content_layout.addWidget(self.name_label)

        content_layout.addSpacing(6)

        # 渐变分割线
        separator = QFrame()
        separator.setObjectName("Separator")
        separator.setFixedHeight(1)
        content_layout.addWidget(separator)

        content_layout.addSpacing(6)

        # 信息行 - 大小
        size_layout = QHBoxLayout()
        size_layout.addStretch()
        size_text = format_size(self.template.total_size)
        self.size_label = QLabel(f"💾 {size_text}")
        self.size_label.setObjectName("InfoValueLabel")
        self.size_label.setTextInteractionFlags(Qt.TextInteractionFlag.NoTextInteraction)
        self.size_label.setCursor(Qt.CursorShape.ArrowCursor)
        size_layout.addWidget(self.size_label)
        size_layout.addStretch()
        content_layout.addLayout(size_layout)

        # 信息行 - 文件数量
        files_layout = QHBoxLayout()
        files_layout.addStretch()
        self.files_label = QLabel(f"📄 {self.template.file_count} 个文件")
        self.files_label.setObjectName("InfoValueLabel")
        self.files_label.setTextInteractionFlags(Qt.TextInteractionFlag.NoTextInteraction)
        self.files_label.setCursor(Qt.CursorShape.ArrowCursor)
        files_layout.addWidget(self.files_label)
        files_layout.addStretch()
        content_layout.addLayout(files_layout)

        # 信息行 - 创建时间
        time_layout = QHBoxLayout()
        time_layout.addStretch()
        time_text = format_time(self.template.created_at)
        self.time_label = QLabel(f"📅 {time_text}")
        self.time_label.setObjectName("InfoValueLabel")
        self.time_label.setTextInteractionFlags(Qt.TextInteractionFlag.NoTextInteraction)
        self.time_label.setCursor(Qt.CursorShape.ArrowCursor)
        time_layout.addWidget(self.time_label)
        time_layout.addStretch()
        content_layout.addLayout(time_layout)

        content_layout.addSpacing(8)

        # 底部按钮行
        button_layout = QHBoxLayout()
        button_layout.setSpacing(8)

        # 应用按钮
        self.apply_btn = QPushButton("应用")
        self.apply_btn.setObjectName("PreviewButton")
        self.apply_btn.setFixedHeight(36)
        self.apply_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.apply_btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.apply_btn.setAttribute(Qt.WidgetAttribute.WA_Hover, True)
        self.apply_btn.clicked.connect(lambda: self.apply_clicked.emit(self.template.name))
        button_layout.addWidget(self.apply_btn, 1)

        # 删除按钮
        self.delete_btn = QPushButton("删除")
        self.delete_btn.setObjectName("ImportButton")
        self.delete_btn.setFixedSize(36, 36)
        self.delete_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.delete_btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.delete_btn.setAttribute(Qt.WidgetAttribute.WA_Hover, True)
        self.delete_btn.clicked.connect(lambda: self.delete_clicked.emit(self.template.name))
        button_layout.addWidget(self.delete_btn)

        content_layout.addLayout(button_layout)

        layout.addWidget(content_widget)
        self.setLayout(layout)
