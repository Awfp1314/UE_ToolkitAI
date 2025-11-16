# -*- coding: utf-8 -*-

"""
现代化资产卡片组件

设计理念：
- 大胆的视觉层次
- 流畅的动画效果
- 清晰的信息架构
- 现代化的交互体验
"""

from pathlib import Path
from datetime import datetime
from typing import Optional
import logging
import subprocess
import sys

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QFrame, QMenu, QApplication
)
from PyQt6.QtCore import Qt, pyqtSignal, QTimer, QObject, QEvent, QRectF
from PyQt6.QtGui import QPixmap, QPainter, QPainterPath, QColor, QAction, QCursor, QEnterEvent, QMouseEvent

logger = logging.getLogger(__name__)


class ProgressButton(QPushButton):
    """带进度条的按钮组件
    
    支持两种模式：
    1. 自动模式：调用 start_progress(duration_ms) 自动从 0-100% 填充
    2. 手动模式：调用 set_progress(value) 手动设置进度，可关联实际任务进度
    """
    
    progress_finished = pyqtSignal()  # 进度完成信号
    progress_changed = pyqtSignal(float)  # 进度变化信号（0.0-1.0）
    
    def __init__(self, text="", parent=None):
        super().__init__(text, parent)
        self._progress = 0.0  # 进度值 0.0 - 1.0
        self._is_loading = False
        self._auto_mode = False  # 是否自动进度模式
        self._timer = QTimer()
        self._timer.timeout.connect(self._update_progress)
        
    def start_progress(self, duration_ms=2000):
        """开始自动进度动画（自动模式）
        
        Args:
            duration_ms: 进度条完成所需时间（毫秒）
        """
        self._progress = 0.0
        self._is_loading = True
        self._auto_mode = True
        self._progress_step = 1.0 / (duration_ms / 16.67)
        self._timer.start(16)  # 约60fps
        self.update()
        
    def set_progress(self, progress: float):
        """手动设置进度（手动模式 - 用于关联实际任务）
        
        Args:
            progress: 进度值 0.0-1.0
        """
        self._auto_mode = False
        self._timer.stop()
        self._progress = max(0.0, min(1.0, progress))
        self._is_loading = self._progress < 1.0
        
        if self._progress >= 1.0:
            self._progress = 1.0
            self._is_loading = False
            self.progress_finished.emit()
        
        self.progress_changed.emit(self._progress)
        self.update()
        
    def stop_progress(self):
        """停止进度动画"""
        self._timer.stop()
        self._is_loading = False
        self._progress = 0.0
        self._auto_mode = False
        self.update()
        
    def reset_progress(self):
        """重置进度"""
        self.stop_progress()
        
    def get_progress(self) -> float:
        """获取当前进度"""
        return self._progress
    
    def update_button_text(self, text: str):
        """更新按钮文本
        
        Args:
            text: 新的按钮文本
        """
        self.setText(text)
    
    def _update_progress(self):
        """更新进度（仅自动模式）"""
        if not self._auto_mode:
            return
            
        if self._progress < 1.0:
            self._progress += self._progress_step
            if self._progress >= 1.0:
                self._progress = 1.0
                self._timer.stop()
                self._is_loading = False
                self._auto_mode = False
                self.progress_finished.emit()
            self.progress_changed.emit(self._progress)
            self.update()
    
    def paintEvent(self, a0):
        """自定义绘制 - 绘制进度条"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        rect = self.rect()
        
        # 如果有进度，绘制进度条背景
        if self._progress > 0:
            # 获取圆角半径（从 ObjectName 判断）
            radius = 10.0 if self.objectName() == "PreviewButton" else 8.0
            
            # 计算进度条宽度
            progress_width = rect.width() * self._progress
            
            # 创建进度条路径
            from PyQt6.QtGui import QLinearGradient
            progress_rect = QRectF(0, 0, progress_width, rect.height())
            path = QPainterPath()
            path.addRoundedRect(progress_rect, radius, radius)
            
            # 绘制进度条渐变（从左到右）
            gradient = QLinearGradient(0, 0, progress_width, 0)
            # 使用半透明的白色作为进度条颜色
            gradient.setColorAt(0, QColor(255, 255, 255, 40))
            gradient.setColorAt(1, QColor(255, 255, 255, 60))
            
            painter.fillPath(path, gradient)
        
        painter.end()
        
        # 调用父类的 paintEvent 来绘制按钮文本和边框
        super().paintEvent(a0)


def format_size(size_bytes):
    """格式化文件大小"""
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    elif size_bytes < 1024 * 1024 * 1024:
        return f"{size_bytes / (1024 * 1024):.1f} MB"
    else:
        return f"{size_bytes / (1024 * 1024 * 1024):.2f} GB"


def format_time(time_str):
    """格式化时间"""
    try:
        dt = datetime.fromisoformat(time_str)
        return dt.strftime("%Y-%m-%d")
    except:
        return ""


class MenuEventFilter(QObject):
    """菜单事件过滤器 - 监听全局事件实现自动关闭"""
    
    def __init__(self, menu: QMenu, card_widget=None):
        super().__init__()
        self.menu = menu
        self.card_widget = card_widget
        self.mouse_was_inside = True
        
        # 安装到应用程序级别，捕获所有事件
        app = QApplication.instance()
        if app:
            app.installEventFilter(self)
        
        # 启动定时器，持续检测鼠标位置
        self.check_timer = QTimer()
        self.check_timer.timeout.connect(self._check_mouse_position)
        self.check_timer.start(50)
        
    def eventFilter(self, a0: Optional[QObject], a1: Optional[QEvent]) -> bool:
        """全局事件过滤器"""
        obj = a0
        event = a1
        try:
            if not self.menu or not self.menu.isVisible():
                return False
        except RuntimeError:
            return False
        
        if event and event.type() == QEvent.Type.MouseButtonPress:
            click_pos = QCursor.pos()
            menu_rect = self.menu.rect()
            menu_global_pos = self.menu.mapToGlobal(menu_rect.topLeft())
            menu_global_rect = menu_rect.translated(menu_global_pos)
            
            if not menu_global_rect.contains(click_pos):
                self._close_menu()
                return False
        elif event and event.type() == QEvent.Type.WindowDeactivate:
            if obj == self.menu:
                self._close_menu()
        
        return False
    
    def _check_mouse_position(self):
        """定时检测鼠标位置"""
        try:
            if not self.menu or not self.menu.isVisible():
                self.check_timer.stop()
                return
        except RuntimeError:
            self.check_timer.stop()
            return
        
        cursor_pos = QCursor.pos()
        menu_rect = self.menu.rect()
        menu_global_pos = self.menu.mapToGlobal(menu_rect.topLeft())
        menu_global_rect = menu_rect.translated(menu_global_pos)
        
        mouse_inside = menu_global_rect.contains(cursor_pos)
        
        if self.mouse_was_inside and not mouse_inside:
            self._close_menu()
        
        if mouse_inside:
            self.mouse_was_inside = True
    
    def _close_menu(self):
        """关闭菜单"""
        try:
            if self.menu and self.menu.isVisible():
                if hasattr(self, 'check_timer'):
                    self.check_timer.stop()
                
                app = QApplication.instance()
                if app:
                    app.removeEventFilter(self)
                
                self.menu.hide()
                self.menu.deleteLater()
                self.menu = None
                
                if self.card_widget:
                    self.card_widget.setAttribute(Qt.WidgetAttribute.WA_UnderMouse, False)
                    self.card_widget.update()
        except RuntimeError:
            if hasattr(self, 'check_timer'):
                self.check_timer.stop()
            self.menu = None


class ModernThumbnailWidget(QWidget):
    """现代化缩略图容器"""

    def __init__(self, width: int, height: int, radius: int = 16,
                 bg_color: str = "#2c2c2c", text_color: str = "#b0b0b0", parent=None):
        super().__init__(parent)
        self.setFixedSize(width, height)
        self.radius = radius
        self.bg_color = bg_color
        self.text_color = text_color
        self._pixmap = None
        self._text = ""
    
    def setPixmap(self, pixmap: QPixmap):
        """设置图片"""
        if pixmap and not pixmap.isNull():
            self._pixmap = pixmap
        else:
            self._pixmap = None
        self._text = ""
        self.update()
    
    def setText(self, text: str):
        """设置文本（无图片时）"""
        self._text = text
        self._pixmap = None
        self.update()

    def paintEvent(self, a0):
        """绘制现代化缩略图"""
        event = a0
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)
        
        widget_rect = self.rect()
        w = widget_rect.width()
        h = widget_rect.height()
        
        # 创建圆角路径
        path = QPainterPath()
        path.addRoundedRect(QRectF(0.0, 0.0, float(w), float(h)), 
                           float(self.radius), float(self.radius))
        
        painter.setClipPath(path)
        painter.fillRect(0, 0, w, h, QColor(self.bg_color))
        
        if self._pixmap and not self._pixmap.isNull():
            pixmap_size = self._pixmap.size()
            px_w = pixmap_size.width()
            px_h = pixmap_size.height()
            
            x = (w - px_w) // 2
            y = (h - px_h) // 2
            
            painter.drawPixmap(x, y, self._pixmap)
        elif self._text:
            painter.setPen(QColor(self.text_color))
            font = painter.font()
            font.setPixelSize(32)
            font.setWeight(300)
            painter.setFont(font)
            painter.drawText(widget_rect, 
                           int(Qt.AlignmentFlag.AlignCenter | Qt.TextFlag.TextWordWrap), 
                           self._text)
        
        painter.end()


class ModernAssetCard(QFrame):
    """现代化资产卡片组件"""

    preview_clicked = pyqtSignal(str)  # 发送资产名称
    edit_info_requested = pyqtSignal(str)
    open_path_requested = pyqtSignal(str)
    delete_requested = pyqtSignal(str)

    def __init__(self, name: str, category: str, size: str,
                 thumbnail_path: Optional[str] = None, asset_type: str = "资源包",
                 created_time: str = "", has_document: bool = False,
                 theme: str = "dark", defer_thumbnail: bool = False,
                 asset_path: Optional[str] = None, parent=None):
        super().__init__(parent)
        self.name = name
        self.category = category
        self.asset_size = size
        self.thumbnail_path = thumbnail_path
        self.asset_type = asset_type
        self.created_time = created_time
        self.has_document = has_document
        self.theme = theme
        self.defer_thumbnail = defer_thumbnail  # 是否延迟加载缩略图
        self.asset_path = asset_path  # 资产路径
        self._is_hovered = False

        self.setObjectName("AssetCard")
        self.setMouseTracking(True)  # 启用鼠标跟踪

        self._init_ui()

    def enterEvent(self, a0: Optional[QEnterEvent]) -> None:  # type: ignore[override]
        """鼠标进入事件"""
        if a0:
            self._update_hover_state(a0.position().toPoint())
        super().enterEvent(a0)

    def leaveEvent(self, a0: Optional[QEvent]) -> None:
        """鼠标离开事件"""
        self._is_hovered = False
        self.update()
        super().leaveEvent(a0)

    def mouseMoveEvent(self, a0: Optional[QMouseEvent]) -> None:
        """鼠标移动事件 - 实时更新悬停状态"""
        if a0:
            self._update_hover_state(a0.position().toPoint())
        super().mouseMoveEvent(a0)

    def _update_hover_state(self, pos):
        """更新悬停状态 - 只在非按钮区域悬停时激活"""
        is_over_button = self._is_mouse_over_button(pos)
        new_hover_state = not is_over_button

        # 只在状态改变时才更新
        if new_hover_state != self._is_hovered:
            self._is_hovered = new_hover_state
            # 只重绘卡片背景，不影响子控件
            self.update()
            # 强制刷新按钮状态
            if hasattr(self, 'preview_btn'):
                self.preview_btn.update()
            if hasattr(self, 'import_btn'):
                self.import_btn.update()

    def _is_mouse_over_button(self, pos):
        """检查鼠标是否在按钮区域（包括按钮之间的间隙）"""
        if not hasattr(self, 'preview_btn') or not hasattr(self, 'import_btn'):
            return False

        preview_rect = self.preview_btn.geometry()
        import_rect = self.import_btn.geometry()

        # 检查是否在预览按钮上
        if preview_rect.contains(pos):
            return True

        # 检查是否在导入按钮上
        if import_rect.contains(pos):
            return True

        # 检查是否在两个按钮之间的间隙中（同一水平线）
        # 如果鼠标的 Y 坐标在按钮的垂直范围内，且 X 坐标在两个按钮之间
        if (preview_rect.top() <= pos.y() <= preview_rect.bottom() or
            import_rect.top() <= pos.y() <= import_rect.bottom()):
            # 检查 X 坐标是否在两个按钮之间
            if preview_rect.right() <= pos.x() <= import_rect.left():
                return True

        return False

    def paintEvent(self, a0):
        """自定义绘制 - 绘制平滑的圆角边框"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        rect = self.rect()
        radius = 20.0

        from PyQt6.QtGui import QLinearGradient, QPen

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
                # 增强对比度：使用更白的背景
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

        # 绘制边框（使用抗锯齿）
        if self._is_hovered:
            if self.theme == "light":
                pen = QPen(QColor(0, 0, 0, 102))  # rgba(0, 0, 0, 0.4)
            else:
                pen = QPen(QColor(255, 255, 255, 153))  # rgba(255, 255, 255, 0.6)
        else:
            if self.theme == "light":
                pen = QPen(QColor("#e8e8e8"))
            else:
                pen = QPen(QColor("#454545"))

        pen.setWidth(2)
        painter.setPen(pen)
        painter.drawRoundedRect(QRectF(rect).adjusted(1, 1, -1, -1), radius, radius)

        painter.end()

        # 确保按钮在卡片重绘后仍然保持正确的悬停状态
        # 通过调用 update() 强制按钮重新评估其悬停状态
        if hasattr(self, 'preview_btn'):
            self.preview_btn.update()
        if hasattr(self, 'import_btn'):
            self.import_btn.update()
    
    def _init_ui(self):
        """初始化UI"""
        self.setFixedSize(220, 314)

        # 根据主题设置颜色（仅用于 ModernThumbnailWidget）
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
        layout.setContentsMargins(4, 4, 4, 4)  # 增加边距以适应边框
        layout.setSpacing(0)

        # 缩略图容器
        thumbnail_container = QWidget()
        thumbnail_container.setObjectName("ThumbnailContainer")
        thumbnail_container.setFixedSize(212, 153)

        self.thumbnail_label = ModernThumbnailWidget(
            width=212, height=153, radius=16,  # 圆角从13改为16，与卡片圆角协调
            bg_color=colors['thumbnail_bg'],
            text_color=colors['thumbnail_text'],
            parent=thumbnail_container
        )
        self.thumbnail_label.setCursor(Qt.CursorShape.ArrowCursor)
        self.thumbnail_label.move(0, 0)

        # 如果不延迟加载，立即加载缩略图
        if not self.defer_thumbnail:
            self.load_thumbnail()

        # 分类标签 - 放在缩略图左下角（纯展示，不可交互）
        self.category_label = QLabel(self.category, thumbnail_container)
        self.category_label.setObjectName("CategoryLabel")
        self.category_label.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)

        # 应用样式（使用内联样式以确保在自定义paintEvent下正常显示）
        # 样式值来自主题配置：asset_category_bg 和 asset_category_text
        self.category_label.setStyleSheet("""
            QLabel {
                color: #b0b0b0;
                font-size: 12px;
                font-weight: 400;
                background-color: #000000;
                border-radius: 4px;
                padding: 5px 12px;
            }
        """)

        self.category_label.setTextInteractionFlags(Qt.TextInteractionFlag.NoTextInteraction)
        self.category_label.setCursor(Qt.CursorShape.ArrowCursor)
        self.category_label.setFixedSize(self.category_label.sizeHint())
        # 定位到左下角，距离左边10px，距离底部10px
        self.category_label.move(10, 153 - 10 - self.category_label.height())

        # 资产类型图标
        asset_type_icon = "📦" if self.asset_type == "资源包" else "📄"
        self.type_label = QLabel(asset_type_icon, thumbnail_container)
        self.type_label.setObjectName("TypeLabel")
        self.type_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.type_label.setTextInteractionFlags(Qt.TextInteractionFlag.NoTextInteraction)
        self.type_label.setCursor(Qt.CursorShape.ArrowCursor)
        self.type_label.setFixedSize(24, 24)
        self.type_label.move(212 - 10 - 24, 153 - 10 - 24)

        layout.addWidget(thumbnail_container)

        # 内容区域
        content_widget = QWidget()
        content_widget.setObjectName("ContentWidget")
        content_layout = QVBoxLayout(content_widget)
        content_layout.setContentsMargins(12, 10, 12, 12)
        content_layout.setSpacing(6)

        # 名称
        self.name_label = QLabel(self.name)
        self.name_label.setObjectName("NameLabel")
        self.name_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.name_label.setWordWrap(True)
        self.name_label.setTextInteractionFlags(Qt.TextInteractionFlag.NoTextInteraction)
        self.name_label.setCursor(Qt.CursorShape.ArrowCursor)
        content_layout.addWidget(self.name_label)

        content_layout.addSpacing(6)

        # 渐变分割线
        separator = QFrame()
        separator.setObjectName("Separator")
        separator.setFixedHeight(1)
        content_layout.addWidget(separator)

        content_layout.addSpacing(6)

        # 大小行
        size_layout = QHBoxLayout()
        size_layout.setSpacing(6)
        size_title = QLabel("💾 大小：")
        size_title.setObjectName("InfoTitleLabel")
        size_title.setTextInteractionFlags(Qt.TextInteractionFlag.NoTextInteraction)
        size_title.setCursor(Qt.CursorShape.ArrowCursor)
        size_layout.addWidget(size_title)

        self.size_label = QLabel(self.asset_size)
        self.size_label.setObjectName("InfoValueLabel")
        self.size_label.setTextInteractionFlags(Qt.TextInteractionFlag.NoTextInteraction)
        self.size_label.setCursor(Qt.CursorShape.ArrowCursor)
        size_layout.addWidget(self.size_label)
        size_layout.addStretch()
        content_layout.addLayout(size_layout)

        # 添加时间行
        if self.created_time:
            time_layout = QHBoxLayout()
            time_layout.setSpacing(6)
            time_title = QLabel("📅 添加时间：")
            time_title.setObjectName("InfoTitleLabel")
            time_title.setTextInteractionFlags(Qt.TextInteractionFlag.NoTextInteraction)
            time_title.setCursor(Qt.CursorShape.ArrowCursor)
            time_layout.addWidget(time_title)

            self.time_label = QLabel(self.created_time)
            self.time_label.setObjectName("InfoValueLabel")
            self.time_label.setTextInteractionFlags(Qt.TextInteractionFlag.NoTextInteraction)
            self.time_label.setCursor(Qt.CursorShape.ArrowCursor)
            time_layout.addWidget(self.time_label)
            time_layout.addStretch()
            content_layout.addLayout(time_layout)

        # 文档行
        doc_layout = QHBoxLayout()
        doc_layout.setSpacing(6)
        doc_title = QLabel("📝 文档：")
        doc_title.setObjectName("InfoTitleLabel")
        doc_title.setTextInteractionFlags(Qt.TextInteractionFlag.NoTextInteraction)
        doc_title.setCursor(Qt.CursorShape.ArrowCursor)
        doc_layout.addWidget(doc_title)

        doc_text = "有" if self.has_document else "无"
        self.doc_label = QLabel(doc_text)
        self.doc_label.setObjectName("InfoValueLabel")
        self.doc_label.setTextInteractionFlags(Qt.TextInteractionFlag.NoTextInteraction)
        self.doc_label.setCursor(Qt.CursorShape.ArrowCursor)
        doc_layout.addWidget(self.doc_label)
        doc_layout.addStretch()
        content_layout.addLayout(doc_layout)

        content_layout.addSpacing(4)

        # 底部按钮行
        button_layout = QHBoxLayout()
        button_layout.setSpacing(8)

        # 预览按钮（透明样式，带边框轮廓）
        self.preview_btn = ProgressButton("▶  预览资产")
        self.preview_btn.setObjectName("PreviewButton")
        self.preview_btn.setFixedHeight(32)
        self.preview_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.preview_btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.preview_btn.setAttribute(Qt.WidgetAttribute.WA_Hover, True)  # 启用悬停属性
        self.preview_btn.clicked.connect(lambda: self.preview_clicked.emit(self.name))
        button_layout.addWidget(self.preview_btn)

        # 导入按钮
        self.import_btn = QPushButton("📥")
        self.import_btn.setObjectName("ImportButton")
        self.import_btn.setFixedSize(32, 32)
        self.import_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.import_btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.import_btn.setAttribute(Qt.WidgetAttribute.WA_Hover, True)  # 启用悬停属性
        self.import_btn.setToolTip("导入资产")
        button_layout.addWidget(self.import_btn)

        content_layout.addLayout(button_layout)

        layout.addWidget(content_widget)
        self.setLayout(layout)

        # 确保按钮在最上层
        self.preview_btn.raise_()
        self.import_btn.raise_()

        # 启用右键菜单
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self._show_context_menu)

    def _show_default_icon(self):
        """显示默认图标"""
        icon_text = "📦" if self.asset_type == "资源包" else "📄"
        self.thumbnail_label.setText(icon_text)

    def _open_asset_location(self):
        """打开资产所在文件夹"""
        import time
        start_time = time.time()
        logger.info(f"[性能] 开始打开资产位置: {self.name}")

        if not self.asset_path:
            logger.warning(f"资产路径未设置: {self.name}")
            return

        logger.info(f"[性能] 路径检查完成，耗时: {(time.time() - start_time)*1000:.2f}ms")

        try:
            popen_start = time.time()
            # Windows: 使用 os.startfile 更快
            if sys.platform == "win32":
                import os
                # 使用 os.startfile 打开文件夹
                os.startfile(self.asset_path)
                logger.info(f"[性能] os.startfile 调用完成，耗时: {(time.time() - popen_start)*1000:.2f}ms")
            elif sys.platform == "darwin":
                # macOS: 使用 open -R 命令
                subprocess.Popen(['open', '-R', self.asset_path])
                logger.info(f"[性能] Popen调用完成，耗时: {(time.time() - popen_start)*1000:.2f}ms")
            else:
                # Linux: 使用 xdg-open
                subprocess.Popen(['xdg-open', self.asset_path])
                logger.info(f"[性能] Popen调用完成，耗时: {(time.time() - popen_start)*1000:.2f}ms")

            logger.info(f"[性能] 总耗时: {(time.time() - start_time)*1000:.2f}ms")
            logger.info(f"打开资产所在位置: {self.asset_path}")

        except Exception as e:
            logger.error(f"打开资产所在位置失败: {e}", exc_info=True)

    def _show_context_menu(self, position):
        """显示右键菜单"""
        menu = QMenu(self)
        menu.setObjectName("AssetCardMenu")

        # 编辑信息
        edit_action = QAction("✏️ 编辑信息", self)
        edit_action.triggered.connect(lambda: self.edit_info_requested.emit(self.name))
        menu.addAction(edit_action)

        # 打开资产所在路径
        open_path_action = QAction("📁 打开资产所在路径", self)
        def open_location():
            import time
            click_time = time.time()
            logger.info(f"[性能] 菜单项被点击")
            logger.info(f"[性能] 准备调用 _open_asset_location")
            self._open_asset_location()  # 直接调用，不用QTimer
            logger.info(f"[性能] _open_asset_location 调用完成，总耗时: {(time.time() - click_time)*1000:.2f}ms")
        open_path_action.triggered.connect(open_location)
        menu.addAction(open_path_action)

        # 分割线
        menu.addSeparator()

        # 删除资产
        delete_action = QAction("🗑️ 删除资产", self)
        delete_action.triggered.connect(lambda: self.delete_requested.emit(self.name))
        menu.addAction(delete_action)

        # 创建事件过滤器来处理自动关闭
        # event_filter = MenuEventFilter(menu, self)  # 暂时禁用，测试性能

        # 在鼠标位置显示菜单
        menu.exec(self.mapToGlobal(position))

    def update_theme(self, theme: str):
        """更新主题

        Args:
            theme: 主题名称 ("dark" 或 "light")
        """
        self.theme = theme
        # 触发重绘以应用新主题
        self.update()

    def load_thumbnail(self):
        """加载缩略图（支持延迟加载）"""
        if self.thumbnail_path and Path(self.thumbnail_path).exists():
            pixmap = QPixmap(str(self.thumbnail_path))
            if not pixmap.isNull():
                target_w, target_h = 212, 153
                scaled_pixmap = pixmap.scaled(
                    target_w, target_h,
                    Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                    Qt.TransformationMode.SmoothTransformation
                )
                self.thumbnail_label.setPixmap(scaled_pixmap)
            else:
                self._show_default_icon()
        else:
            self._show_default_icon()


class CompactAssetCard(QFrame):
    """简略资产卡片组件 - 紧凑设计"""

    preview_clicked = pyqtSignal(str)  # 发送资产名称
    edit_info_requested = pyqtSignal(str)
    open_path_requested = pyqtSignal(str)
    delete_requested = pyqtSignal(str)

    def __init__(self, name: str, category: str = "",
                 thumbnail_path: Optional[str] = None, asset_type: str = "资源包",
                 theme: str = "dark", defer_thumbnail: bool = False,
                 asset_path: Optional[str] = None, parent=None):
        super().__init__(parent)
        self.name = name
        self.category = category
        self.thumbnail_path = thumbnail_path
        self.asset_type = asset_type
        self.theme = theme
        self.defer_thumbnail = defer_thumbnail  # 是否延迟加载缩略图
        self.asset_path = asset_path  # 资产路径
        self._is_hovered = False

        self.setObjectName("CompactAssetCard")
        self.setMouseTracking(True)  # 启用鼠标跟踪
        self._init_ui()

    def enterEvent(self, a0: Optional[QEnterEvent]) -> None:  # type: ignore[override]
        """鼠标进入事件"""
        if a0:
            self._update_hover_state(a0.position().toPoint())
        super().enterEvent(a0)

    def leaveEvent(self, a0: Optional[QEvent]) -> None:
        """鼠标离开事件"""
        self._is_hovered = False
        self.update()
        super().leaveEvent(a0)

    def mouseMoveEvent(self, a0: Optional[QMouseEvent]) -> None:
        """鼠标移动事件 - 实时更新悬停状态"""
        if a0:
            self._update_hover_state(a0.position().toPoint())
        super().mouseMoveEvent(a0)

    def _update_hover_state(self, pos):
        """更新悬停状态 - 只在非按钮区域悬停时激活"""
        is_over_button = self._is_mouse_over_button(pos)
        new_hover_state = not is_over_button

        # 只在状态改变时才更新
        if new_hover_state != self._is_hovered:
            self._is_hovered = new_hover_state
            # 只重绘卡片背景，不影响子控件
            self.update()
            # 强制刷新按钮状态
            if hasattr(self, 'preview_btn'):
                self.preview_btn.update()
            if hasattr(self, 'import_btn'):
                self.import_btn.update()

    def _is_mouse_over_button(self, pos):
        """检查鼠标是否在按钮区域（包括按钮之间的间隙）"""
        if not hasattr(self, 'preview_btn') or not hasattr(self, 'import_btn'):
            return False

        preview_rect = self.preview_btn.geometry()
        import_rect = self.import_btn.geometry()

        # 检查是否在预览按钮上
        if preview_rect.contains(pos):
            return True

        # 检查是否在导入按钮上
        if import_rect.contains(pos):
            return True

        # 检查是否在两个按钮之间的间隙中（同一水平线）
        # 如果鼠标的 Y 坐标在按钮的垂直范围内，且 X 坐标在两个按钮之间
        if (preview_rect.top() <= pos.y() <= preview_rect.bottom() or
            import_rect.top() <= pos.y() <= import_rect.bottom()):
            # 检查 X 坐标是否在两个按钮之间
            if preview_rect.right() <= pos.x() <= import_rect.left():
                return True

        return False

    def paintEvent(self, a0):
        """自定义绘制 - 绘制平滑的圆角边框"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        rect = self.rect()
        radius = 16.0

        # 绘制背景渐变
        from PyQt6.QtGui import QLinearGradient, QPen
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
                # 增强对比度：使用更白的背景
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

        # 绘制边框（使用抗锯齿）
        if self._is_hovered:
            if self.theme == "light":
                pen = QPen(QColor(0, 0, 0, 102))  # rgba(0, 0, 0, 0.4)
            else:
                pen = QPen(QColor(255, 255, 255, 153))  # rgba(255, 255, 255, 0.6)
        else:
            if self.theme == "light":
                pen = QPen(QColor("#e8e8e8"))
            else:
                pen = QPen(QColor("#454545"))

        pen.setWidth(2)
        painter.setPen(pen)
        painter.drawRoundedRect(QRectF(rect).adjusted(1, 1, -1, -1), radius, radius)

        painter.end()

        # 确保按钮在卡片重绘后仍然保持正确的悬停状态
        # 通过调用 update() 强制按钮重新评估其悬停状态
        if hasattr(self, 'preview_btn'):
            self.preview_btn.update()
        if hasattr(self, 'import_btn'):
            self.import_btn.update()
    
    def _init_ui(self):
        """初始化UI - 紧凑设计"""
        self.setFixedSize(180, 200)  # 从 240 降低到 200

        # 根据主题设置颜色（仅用于 ModernThumbnailWidget）
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
        layout.setContentsMargins(4, 4, 4, 4)  # 增加边距以适应边框
        layout.setSpacing(0)

        # 缩略图容器
        thumbnail_container = QWidget()
        thumbnail_container.setObjectName("ThumbnailContainer")
        thumbnail_container.setFixedSize(172, 115)

        self.thumbnail_label = ModernThumbnailWidget(
            width=172, height=115, radius=12,  # 圆角从13改为12，与卡片圆角协调
            bg_color=colors['thumbnail_bg'],
            text_color=colors['thumbnail_text'],
            parent=thumbnail_container
        )
        self.thumbnail_label.setCursor(Qt.CursorShape.ArrowCursor)
        self.thumbnail_label.move(0, 0)

        # 如果不延迟加载，立即加载缩略图
        if not self.defer_thumbnail:
            self.load_thumbnail()

        # 资产类型图标
        asset_type_icon = "📦" if self.asset_type == "资源包" else "📄"
        self.type_label = QLabel(asset_type_icon, thumbnail_container)
        self.type_label.setObjectName("TypeLabel")
        self.type_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.type_label.setTextInteractionFlags(Qt.TextInteractionFlag.NoTextInteraction)
        self.type_label.setCursor(Qt.CursorShape.ArrowCursor)
        self.type_label.setFixedSize(20, 20)
        self.type_label.move(172 - 8 - 20, 115 - 8 - 20)

        layout.addWidget(thumbnail_container)

        # 内容区域
        content_widget = QWidget()
        content_widget.setObjectName("ContentWidget")
        content_layout = QVBoxLayout(content_widget)
        content_layout.setContentsMargins(10, 6, 10, 8)  # 减少上下边距
        content_layout.setSpacing(6)  # 减少间距

        # 名称
        self.name_label = QLabel(self.name)
        self.name_label.setObjectName("NameLabel")
        self.name_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.name_label.setWordWrap(True)
        self.name_label.setTextInteractionFlags(Qt.TextInteractionFlag.NoTextInteraction)
        self.name_label.setCursor(Qt.CursorShape.ArrowCursor)
        self.name_label.setMaximumHeight(40)  # 限制名称标签最大高度
        content_layout.addWidget(self.name_label)

        # 移除 addStretch()，减少空白

        # 底部按钮行
        button_layout = QHBoxLayout()
        button_layout.setSpacing(6)

        # 预览按钮
        self.preview_btn = ProgressButton("▶  预览资产")
        self.preview_btn.setObjectName("PreviewButton")
        self.preview_btn.setFixedHeight(28)
        self.preview_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.preview_btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.preview_btn.setAttribute(Qt.WidgetAttribute.WA_Hover, True)  # 启用悬停属性
        self.preview_btn.clicked.connect(lambda: self.preview_clicked.emit(self.name))
        button_layout.addWidget(self.preview_btn)

        # 导入按钮
        self.import_btn = QPushButton("📥")
        self.import_btn.setObjectName("ImportButton")
        self.import_btn.setFixedSize(28, 28)
        self.import_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.import_btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.import_btn.setAttribute(Qt.WidgetAttribute.WA_Hover, True)  # 启用悬停属性
        self.import_btn.setToolTip("导入资产")
        button_layout.addWidget(self.import_btn)

        content_layout.addLayout(button_layout)

        layout.addWidget(content_widget)
        self.setLayout(layout)

        # 确保按钮在最上层
        self.preview_btn.raise_()
        self.import_btn.raise_()

        # 启用右键菜单
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self._show_context_menu)

    def _show_default_icon(self):
        """显示默认图标"""
        icon_text = "📦" if self.asset_type == "资源包" else "📄"
        self.thumbnail_label.setText(icon_text)

    def _open_asset_location(self):
        """打开资产所在文件夹"""
        if not self.asset_path:
            logger.warning(f"资产路径未设置: {self.name}")
            return

        try:
            # Windows: 使用 os.startfile 更快
            if sys.platform == "win32":
                import os
                os.startfile(self.asset_path)
            elif sys.platform == "darwin":
                # macOS: 使用 open -R 命令
                subprocess.Popen(['open', '-R', self.asset_path])
            else:
                # Linux: 使用 xdg-open
                subprocess.Popen(['xdg-open', self.asset_path])

            logger.info(f"打开资产所在位置: {self.asset_path}")

        except Exception as e:
            logger.error(f"打开资产所在位置失败: {e}", exc_info=True)

    def _show_context_menu(self, position):
        """显示右键菜单"""
        menu = QMenu(self)
        menu.setObjectName("AssetCardMenu")

        edit_action = QAction("✏️ 编辑信息", self)
        edit_action.triggered.connect(lambda: self.edit_info_requested.emit(self.name))
        menu.addAction(edit_action)

        open_path_action = QAction("📁 打开资产所在路径", self)
        def open_location():
            import time
            click_time = time.time()
            logger.info(f"[性能] 菜单项被点击")
            logger.info(f"[性能] 准备调用 _open_asset_location")
            self._open_asset_location()  # 直接调用，不用QTimer
            logger.info(f"[性能] _open_asset_location 调用完成，总耗时: {(time.time() - click_time)*1000:.2f}ms")
        open_path_action.triggered.connect(open_location)
        menu.addAction(open_path_action)

        menu.addSeparator()

        delete_action = QAction("🗑️ 删除资产", self)
        delete_action.triggered.connect(lambda: self.delete_requested.emit(self.name))
        menu.addAction(delete_action)

        # event_filter = MenuEventFilter(menu, self)  # 暂时禁用，测试性能
        menu.exec(self.mapToGlobal(position))

    def update_theme(self, theme: str):
        """更新主题

        Args:
            theme: 主题名称 ("dark" 或 "light")
        """
        self.theme = theme
        # 触发重绘以应用新主题
        self.update()

    def load_thumbnail(self):
        """加载缩略图（支持延迟加载）"""
        if self.thumbnail_path and Path(self.thumbnail_path).exists():
            pixmap = QPixmap(str(self.thumbnail_path))
            if not pixmap.isNull():
                target_w, target_h = 172, 115
                scaled_pixmap = pixmap.scaled(
                    target_w, target_h,
                    Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                    Qt.TransformationMode.SmoothTransformation
                )
                self.thumbnail_label.setPixmap(scaled_pixmap)
            else:
                self._show_default_icon()
        else:
            self._show_default_icon()
