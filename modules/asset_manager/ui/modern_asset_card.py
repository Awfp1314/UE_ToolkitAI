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


class ImportIconButton(QPushButton):
    """导入按钮 - 用 QPainter 绘制箭头+托盘图标，颜色跟随主题"""
    
    def __init__(self, size=36, parent=None):
        super().__init__(parent)
        self._size = size
        self.setFixedSize(size, size)
    
    def paintEvent(self, event):
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        
        # 获取按钮文字颜色（跟随 QSS 主题）
        color = self.palette().buttonText().color()
        pen = painter.pen()
        pen.setColor(color)
        pen.setWidthF(1.8)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        painter.setPen(pen)
        
        s = self._size
        cx = s / 2  # 中心 x
        
        # 箭头竖线（从上往下）
        top_y = s * 0.22
        mid_y = s * 0.55
        painter.drawLine(int(cx), int(top_y), int(cx), int(mid_y))
        
        # 箭头头部（V 形）
        arrow_w = s * 0.18
        arrow_top = mid_y - s * 0.15
        painter.drawLine(int(cx - arrow_w), int(arrow_top), int(cx), int(mid_y))
        painter.drawLine(int(cx + arrow_w), int(arrow_top), int(cx), int(mid_y))
        
        # 底部托盘（U 形凹槽）
        tray_y = s * 0.72
        tray_left = s * 0.25
        tray_right = s * 0.75
        tray_bottom = s * 0.72
        # 左竖线
        painter.drawLine(int(tray_left), int(tray_y - s * 0.1), int(tray_left), int(tray_bottom))
        # 底横线
        painter.drawLine(int(tray_left), int(tray_bottom), int(tray_right), int(tray_bottom))
        # 右竖线
        painter.drawLine(int(tray_right), int(tray_y - s * 0.1), int(tray_right), int(tray_bottom))
        
        painter.end()


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
        self._progress_step = 1.0 / (duration_ms / 33.33)  # 30fps
        self._timer.start(33)  # 30fps，视觉上足够流畅
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
            radius = 0.0 if self.objectName() == "PreviewButton" else 8.0
            
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
        
        # 设置对象名称以便应用 QSS 样式
        self.setObjectName("ModernThumbnailWidget")
    
    def update_colors(self, bg_color: str, text_color: str):
        """更新颜色（用于主题切换）
        
        Args:
            bg_color: 背景颜色
            text_color: 文本颜色
        """
        self.bg_color = bg_color
        self.text_color = text_color
        self.update()
    
    def setPixmap(self, pixmap: QPixmap):
        """设置图片（确保填充整个容器）"""
        if pixmap and not pixmap.isNull():
            # 确保图片填充整个容器
            target_w = self.width()
            target_h = self.height()
            
            # 如果传入的 pixmap 尺寸不匹配，重新缩放
            if pixmap.width() != target_w or pixmap.height() != target_h:
                self._pixmap = pixmap.scaled(
                    target_w, target_h,
                    Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                    Qt.TransformationMode.SmoothTransformation
                )
            else:
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
        
        # 使用当前主题的背景颜色
        painter.fillRect(0, 0, w, h, QColor(self.bg_color))
        
        if self._pixmap and not self._pixmap.isNull():
            pixmap_size = self._pixmap.size()
            px_w = pixmap_size.width()
            px_h = pixmap_size.height()
            
            # 计算居中位置（如果图片大于容器，会被裁剪）
            x = (w - px_w) // 2
            y = (h - px_h) // 2
            
            # 绘制图片（超出部分会被 clipPath 裁剪）
            painter.drawPixmap(x, y, self._pixmap)
        elif self._text:
            painter.setPen(QColor(self.text_color))
            font = painter.font()
            # 根据文本内容调整字体大小
            if "\n" in self._text:
                # 多行文本（如"未设置\n缩略图"）使用较小字体
                font.setPixelSize(16)
                font.setWeight(400)
            else:
                # 单行文本（如表情符号）使用较大字体
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
    detail_requested = pyqtSignal(str)  # 发送资产名称，请求显示详情
    import_requested = pyqtSignal(str)  # 发送资产名称，请求导入
    export_requested = pyqtSignal(str)  # 发送资产名称，请求导出

    def __init__(self, name: str, category: str, size: str,
                 thumbnail_path: Optional[str] = None, asset_type: str = "资源包",
                 created_time: str = "", has_document: bool = False,
                 theme: str = "dark", defer_thumbnail: bool = False,
                 asset_path: Optional[str] = None, engine_min_version: str = "",
                 package_type = None,
                 parent=None):
        super().__init__(parent)
        # 立即隐藏，避免在初始化过程中显示为独立窗口
        self.hide()
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
        self.engine_min_version = engine_min_version  # 引擎最低版本
        self.package_type = package_type  # 包装类型（用于版本徽标格式化和类型显示）
        self._is_hovered = False

        self.setObjectName("AssetCard")
        self.setMouseTracking(True)  # 启用鼠标跟踪
        self.asset_id = None  # 资产ID，用于详情查询
        
        # 确保能接收鼠标事件
        self.setAttribute(Qt.WidgetAttribute.WA_Hover, True)
        self.setFocusPolicy(Qt.FocusPolicy.ClickFocus)
        
        # 确保不作为独立窗口显示
        if parent is None:
            self.setWindowFlags(Qt.WindowType.Widget)

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
    
    def mousePressEvent(self, event: Optional[QMouseEvent]) -> None:
        """鼠标按下事件 - 记录按下位置"""
        if event and event.button() == Qt.MouseButton.LeftButton:
            self._press_pos = event.position().toPoint()
            logger.debug(f"[ModernCard-{self.name}] 鼠标按下: pos=({self._press_pos.x()}, {self._press_pos.y()})")
        super().mousePressEvent(event)
    
    def mouseReleaseEvent(self, event: Optional[QMouseEvent]) -> None:
        """鼠标释放事件 - 检查是否为有效点击"""
        if event and event.button() == Qt.MouseButton.LeftButton:
            # 获取释放位置
            release_pos = event.position().toPoint()
            logger.debug(f"[ModernCard-{self.name}] 鼠标释放: pos=({release_pos.x()}, {release_pos.y()})")
            
            # 检查是否有按下位置记录
            if not hasattr(self, '_press_pos'):
                logger.debug(f"[ModernCard-{self.name}] 没有按下位置记录，忽略")
                super().mouseReleaseEvent(event)
                return
            
            # 检查按下和释放位置是否接近（避免拖拽误触）
            press_pos = self._press_pos
            distance = ((release_pos.x() - press_pos.x()) ** 2 + (release_pos.y() - press_pos.y()) ** 2) ** 0.5
            if distance > 10:  # 超过10像素认为是拖拽
                logger.debug(f"[ModernCard-{self.name}] 拖拽距离{distance:.1f}px，忽略")
                super().mouseReleaseEvent(event)
                return
            
            # 检查是否在按钮上
            is_on_button = False
            
            if hasattr(self, 'preview_btn') and self.preview_btn.isVisible():
                btn_geo = self.preview_btn.geometry()
                if btn_geo.contains(release_pos):
                    is_on_button = True
                    logger.debug(f"[ModernCard-{self.name}] 释放在预览按钮上")
            
            if hasattr(self, 'import_btn') and self.import_btn.isVisible() and not is_on_button:
                btn_geo = self.import_btn.geometry()
                if btn_geo.contains(release_pos):
                    is_on_button = True
                    logger.debug(f"[ModernCard-{self.name}] 释放在导入按钮上")
            
            # 如果不在按钮上，触发详情请求
            if not is_on_button:
                logger.info(f"[ModernCard-{self.name}] 触发详情请求")
                self.detail_requested.emit(self.name)
                event.accept()
                return
            else:
                logger.debug(f"[ModernCard-{self.name}] 释放在按钮上，不触发详情")
        else:
            # 备用检测：任何鼠标释放都记录
            logger.debug(f"[ModernCard-{self.name}] 鼠标释放事件: button={event.button() if event else 'None'}")
        
        super().mouseReleaseEvent(event)
    
    def event(self, e):
        """事件过滤 - 捕获所有事件用于调试"""
        if e.type() == e.Type.MouseButtonPress:
            logger.debug(f"[ModernCard-{self.name}] 捕获到MouseButtonPress事件")
        elif e.type() == e.Type.MouseButtonRelease:
            logger.debug(f"[ModernCard-{self.name}] 捕获到MouseButtonRelease事件")
        return super().event(e)

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
        radius = 0.0

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
            width=212, height=153, radius=0,  # 直角样式
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
                border-radius: 0px;
                padding: 5px 12px;
            }
        """)

        self.category_label.setTextInteractionFlags(Qt.TextInteractionFlag.NoTextInteraction)
        self.category_label.setCursor(Qt.CursorShape.ArrowCursor)
        self.category_label.setFixedSize(self.category_label.sizeHint())
        # 定位到左下角，距离左边10px，距离底部10px
        self.category_label.move(10, 153 - 10 - self.category_label.height())

        # 引擎版本徽标 - 右上角
        from ..utils.ue_version_detector import UEVersionDetector
        version_detector = UEVersionDetector()
        # 传入 package_type 以正确格式化版本（插件不显示+号）
        pkg_type = getattr(self, 'package_type', None)
        version_badge = version_detector.format_version_badge(self.engine_min_version, pkg_type)
        
        self.version_label = QLabel(version_badge, thumbnail_container)
        self.version_label.setObjectName("VersionLabel")
        self.version_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.version_label.setTextInteractionFlags(Qt.TextInteractionFlag.NoTextInteraction)
        self.version_label.setCursor(Qt.CursorShape.ArrowCursor)
        
        # 样式：蓝色版本徽标
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
        # 定位到右上角
        self.version_label.move(212 - 10 - self.version_label.width(), 10)
        
        # 资产类型徽标 - 右下角
        from ..logic.asset_model import PackageType
        type_text = "资源包"  # 默认值
        if pkg_type:
            if hasattr(pkg_type, 'display_name'):
                type_text = pkg_type.display_name
            elif isinstance(pkg_type, str):
                # 如果是字符串，尝试转换为枚举
                try:
                    type_text = PackageType(pkg_type).display_name
                except (ValueError, AttributeError):
                    type_text = pkg_type
        
        self.type_label = QLabel(type_text, thumbnail_container)
        self.type_label.setObjectName("TypeLabel")
        self.type_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.type_label.setTextInteractionFlags(Qt.TextInteractionFlag.NoTextInteraction)
        self.type_label.setCursor(Qt.CursorShape.ArrowCursor)
        
        # 样式：橙色类型徽标
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
        # 定位到右下角
        self.type_label.move(212 - 10 - self.type_label.width(), 153 - 10 - self.type_label.height())

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

        # 大小信息 - 居中显示
        size_layout = QHBoxLayout()
        size_layout.addStretch()
        self.size_label = QLabel(f"💾 {self.asset_size}")
        self.size_label.setObjectName("InfoValueLabel")
        self.size_label.setTextInteractionFlags(Qt.TextInteractionFlag.NoTextInteraction)
        self.size_label.setCursor(Qt.CursorShape.ArrowCursor)
        size_layout.addWidget(self.size_label)
        size_layout.addStretch()
        content_layout.addLayout(size_layout)

        content_layout.addSpacing(8)

        # 底部按钮行
        button_layout = QHBoxLayout()
        button_layout.setSpacing(8)

        # 预览按钮（透明样式，带边框轮廓）
        self.preview_btn = ProgressButton("▶  预览资产")
        self.preview_btn.setObjectName("PreviewButton")
        self.preview_btn.setFixedHeight(36)
        self.preview_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.preview_btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.preview_btn.setAttribute(Qt.WidgetAttribute.WA_Hover, True)  # 启用悬停属性
        self.preview_btn.clicked.connect(lambda: self.preview_clicked.emit(self.name))
        button_layout.addWidget(self.preview_btn)

        # 导入按钮
        self.import_btn = ImportIconButton(36)
        self.import_btn.setObjectName("ImportButton")
        self.import_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.import_btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.import_btn.setAttribute(Qt.WidgetAttribute.WA_Hover, True)  # 启用悬停属性
        self.import_btn.setToolTip("导入资产")
        self.import_btn.clicked.connect(lambda: self.import_requested.emit(self.name))
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
        """显示默认占位符"""
        # 显示"未设置缩略图"文字提示
        self.thumbnail_label.setText("未设置\n缩略图")

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

        # 导出资产（压缩）
        export_action = QAction("📤 导出资产（压缩）", self)
        export_action.triggered.connect(lambda: self.export_requested.emit(self.name))
        menu.addAction(export_action)

        # 分割线
        menu.addSeparator()

        # 检查是否有文档，如果有则添加"删除文档"选项
        if self._has_document():
            delete_doc_action = QAction("📄 删除文档", self)
            delete_doc_action.triggered.connect(self._on_delete_document)
            menu.addAction(delete_doc_action)

        # 删除资产
        delete_action = QAction("🗑️ 删除资产", self)
        delete_action.triggered.connect(lambda: self.delete_requested.emit(self.name))
        menu.addAction(delete_action)

        # 创建事件过滤器来处理自动关闭
        event_filter = MenuEventFilter(menu, self)

        # 在鼠标位置显示菜单
        menu.exec(self.mapToGlobal(position))
    
    def _has_document(self) -> bool:
        """检查资产是否有文档"""
        try:
            # 需要从父组件获取 logic 引用
            parent_widget = self.parent()
            while parent_widget:
                if hasattr(parent_widget, 'logic') and parent_widget.logic:
                    logic = parent_widget.logic
                    if hasattr(logic, 'documents_dir') and logic.documents_dir:
                        # 检查 .docx 文档是否存在
                        if hasattr(self, 'asset_id') and self.asset_id:
                            doc_path = logic.documents_dir / f"{self.asset_id}.docx"
                            return doc_path.exists()
                    break
                parent_widget = parent_widget.parent()
        except Exception as e:
            logger.error(f"检查文档存在性失败: {e}")
        return False
    
    def _on_delete_document(self):
        """删除文档"""
        try:
            # 获取 logic 引用
            parent_widget = self.parent()
            logic = None
            while parent_widget:
                if hasattr(parent_widget, 'logic') and parent_widget.logic:
                    logic = parent_widget.logic
                    break
                parent_widget = parent_widget.parent()
            
            if not logic or not hasattr(logic, 'documents_dir') or not logic.documents_dir:
                logger.error("无法获取文档目录")
                return
            
            if not hasattr(self, 'asset_id') or not self.asset_id:
                logger.error("资产ID未设置")
                return
            
            # 导入确认对话框
            from PyQt6.QtWidgets import QMessageBox
            
            # 显示确认对话框
            reply = QMessageBox.question(
                self,
                "确认删除",
                f"确定要删除资产 \"{self.name}\" 的文档吗？\n\n此操作不可恢复！",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No
            )
            
            if reply != QMessageBox.StandardButton.Yes:
                return
            
            # 删除文档文件
            doc_path = logic.documents_dir / f"{self.asset_id}.docx"
            
            if doc_path.exists():
                doc_path.unlink()
                logger.info(f"已删除文档: {doc_path}")
                QMessageBox.information(self, "删除成功", "文档已删除")
            else:
                QMessageBox.warning(self, "删除失败", "未找到文档文件")
                
        except Exception as e:
            logger.error(f"删除文档失败: {e}", exc_info=True)
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.warning(self, "错误", f"删除文档失败：{e}")

    def update_theme(self, theme: str):
        """更新主题

        Args:
            theme: 主题名称 ("dark" 或 "light")
        """
        self.theme = theme
        
        # 更新缩略图背景颜色
        if theme == "light":
            self.thumbnail_label.update_colors('#f5f5f5', '#cccccc')
        else:
            self.thumbnail_label.update_colors('#323232', '#707070')
        
        # 触发重绘以应用新主题
        self.update()

    def load_thumbnail(self):
        """加载缩略图（支持延迟加载）"""
        logger.debug(f"[缩略图加载] 资产: {self.name}")
        logger.debug(f"[缩略图加载] 缩略图路径: {self.thumbnail_path}")

        if self.thumbnail_path and Path(self.thumbnail_path).exists():
            logger.debug(f"[缩略图加载] 缩略图文件存在，开始加载")
            pixmap = QPixmap(str(self.thumbnail_path))
            if not pixmap.isNull():
                target_w, target_h = 212, 153
                scaled_pixmap = pixmap.scaled(
                    target_w, target_h,
                    Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                    Qt.TransformationMode.SmoothTransformation
                )
                self.thumbnail_label.setPixmap(scaled_pixmap)
                logger.debug(f"[缩略图加载] 成功加载缩略图: {self.name}")
            else:
                logger.warning(f"[缩略图加载] QPixmap 加载失败（isNull）: {self.thumbnail_path}")
                self._show_default_icon()
        else:
            if self.thumbnail_path:
                logger.warning(f"[缩略图加载] 缩略图文件不存在: {self.thumbnail_path}")
            else:
                logger.debug(f"[缩略图加载] 无缩略图路径")
            self._show_default_icon()


class CompactAssetCard(QFrame):
    """简略资产卡片组件 - 紧凑设计"""

    preview_clicked = pyqtSignal(str)  # 发送资产名称
    edit_info_requested = pyqtSignal(str)
    open_path_requested = pyqtSignal(str)
    delete_requested = pyqtSignal(str)
    detail_requested = pyqtSignal(str)  # 发送资产名称，请求显示详情
    import_requested = pyqtSignal(str)  # 发送资产名称，请求导入
    export_requested = pyqtSignal(str)  # 发送资产名称，请求导出

    def __init__(self, name: str, category: str = "",
                 thumbnail_path: Optional[str] = None, asset_type: str = "资源包",
                 theme: str = "dark", defer_thumbnail: bool = False,
                 asset_path: Optional[str] = None, engine_min_version: str = "",
                 package_type = None, asset_size: str = "",
                 parent=None):
        super().__init__(parent)
        # 立即隐藏，避免在初始化过程中显示为独立窗口
        self.hide()
        self.name = name
        self.category = category
        self.thumbnail_path = thumbnail_path
        self.asset_type = asset_type
        self.theme = theme
        self.defer_thumbnail = defer_thumbnail  # 是否延迟加载缩略图
        self.asset_path = asset_path  # 资产路径
        self.engine_min_version = engine_min_version  # 引擎最低版本
        self.package_type = package_type  # 包装类型（用于版本徽标格式化和类型显示）
        self.asset_size = asset_size  # 资产大小
        self._is_hovered = False

        self.setObjectName("CompactAssetCard")
        self.setMouseTracking(True)  # 启用鼠标跟踪
        self.asset_id = None  # 资产ID，用于详情查询
        
        # 确保能接收鼠标事件
        self.setAttribute(Qt.WidgetAttribute.WA_Hover, True)
        self.setFocusPolicy(Qt.FocusPolicy.ClickFocus)
        
        # 确保不作为独立窗口显示
        if parent is None:
            self.setWindowFlags(Qt.WindowType.Widget)
        
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
    
    def mousePressEvent(self, event: Optional[QMouseEvent]) -> None:
        """鼠标按下事件 - 记录按下位置"""
        if event and event.button() == Qt.MouseButton.LeftButton:
            self._press_pos = event.position().toPoint()
            logger.debug(f"[CompactCard-{self.name}] 鼠标按下: pos=({self._press_pos.x()}, {self._press_pos.y()})")
        super().mousePressEvent(event)
    
    def mouseReleaseEvent(self, event: Optional[QMouseEvent]) -> None:
        """鼠标释放事件 - 检查是否为有效点击"""
        if event and event.button() == Qt.MouseButton.LeftButton:
            # 获取释放位置
            release_pos = event.position().toPoint()
            logger.debug(f"[CompactCard-{self.name}] 鼠标释放: pos=({release_pos.x()}, {release_pos.y()})")
            
            # 检查是否有按下位置记录
            if not hasattr(self, '_press_pos'):
                logger.debug(f"[CompactCard-{self.name}] 没有按下位置记录，忽略")
                super().mouseReleaseEvent(event)
                return
            
            # 检查按下和释放位置是否接近（避免拖拽误触）
            press_pos = self._press_pos
            distance = ((release_pos.x() - press_pos.x()) ** 2 + (release_pos.y() - press_pos.y()) ** 2) ** 0.5
            if distance > 10:  # 超过10像素认为是拖拽
                logger.debug(f"[CompactCard-{self.name}] 拖拽距离{distance:.1f}px，忽略")
                super().mouseReleaseEvent(event)
                return
            
            # 检查是否在按钮上
            is_on_button = False
            
            if hasattr(self, 'preview_btn') and self.preview_btn.isVisible():
                btn_geo = self.preview_btn.geometry()
                if btn_geo.contains(release_pos):
                    is_on_button = True
                    logger.debug(f"[CompactCard-{self.name}] 释放在预览按钮上")
            
            if hasattr(self, 'import_btn') and self.import_btn.isVisible() and not is_on_button:
                btn_geo = self.import_btn.geometry()
                if btn_geo.contains(release_pos):
                    is_on_button = True
                    logger.debug(f"[CompactCard-{self.name}] 释放在导入按钮上")
            
            # 如果不在按钮上，触发详情请求
            if not is_on_button:
                logger.info(f"[CompactCard-{self.name}] 触发详情请求")
                self.detail_requested.emit(self.name)
                event.accept()
                return
            else:
                logger.debug(f"[CompactCard-{self.name}] 释放在按钮上，不触发详情")
        else:
            # 备用检测：任何鼠标释放都记录
            logger.debug(f"[CompactCard-{self.name}] 鼠标释放事件: button={event.button() if event else 'None'}")
        
        super().mouseReleaseEvent(event)

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
        radius = 0.0

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
            width=172, height=115, radius=0,  # 直角样式
            bg_color=colors['thumbnail_bg'],
            text_color=colors['thumbnail_text'],
            parent=thumbnail_container
        )
        self.thumbnail_label.setCursor(Qt.CursorShape.ArrowCursor)
        self.thumbnail_label.move(0, 0)

        # 如果不延迟加载，立即加载缩略图
        if not self.defer_thumbnail:
            self.load_thumbnail()

        # 分类标签 - 放在缩略图左下角（和详细视图一致）
        self.category_label = QLabel(self.category, thumbnail_container)
        self.category_label.setObjectName("CompactCategoryLabel")
        self.category_label.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        
        # 应用样式（使用内联样式以确保在自定义paintEvent下正常显示）
        self.category_label.setStyleSheet("""
            QLabel {
                color: #b0b0b0;
                font-size: 10px;
                font-weight: 400;
                background-color: #000000;
                border-radius: 0px;
                padding: 3px 8px;
            }
        """)
        
        self.category_label.setTextInteractionFlags(Qt.TextInteractionFlag.NoTextInteraction)
        self.category_label.setCursor(Qt.CursorShape.ArrowCursor)
        self.category_label.setFixedSize(self.category_label.sizeHint())
        # 定位到左下角，距离左边8px，距离底部8px
        self.category_label.move(8, 115 - 8 - self.category_label.height())

        # 大小信息 - 放在缩略图右下角（替换原来的版本徽标位置）
        if self.asset_size:
            self.size_label = QLabel(self.asset_size, thumbnail_container)
            self.size_label.setObjectName("SizeLabel")
            self.size_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.size_label.setTextInteractionFlags(Qt.TextInteractionFlag.NoTextInteraction)
            self.size_label.setCursor(Qt.CursorShape.ArrowCursor)
            
            # 样式：半透明黑色背景
            self.size_label.setStyleSheet("""
                QLabel {
                    color: #ffffff;
                    font-size: 10px;
                    font-weight: bold;
                    background-color: rgba(0, 0, 0, 0.7);
                    border-radius: 3px;
                    padding: 2px 5px;
                }
            """)
            
            self.size_label.setFixedSize(self.size_label.sizeHint())
            # 定位到右下角
            self.size_label.move(172 - 8 - self.size_label.width(), 115 - 8 - self.size_label.height())

        layout.addWidget(thumbnail_container)

        # 内容区域
        content_widget = QWidget()
        content_widget.setObjectName("ContentWidget")
        content_layout = QVBoxLayout(content_widget)
        content_layout.setContentsMargins(10, 10, 10, 8)  # 增加上边距，防止名称溢出到缩略图
        content_layout.setSpacing(4)  # 减少间距

        # 名称
        self.name_label = QLabel(self.name)
        self.name_label.setObjectName("NameLabel")
        self.name_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.name_label.setWordWrap(True)
        self.name_label.setTextInteractionFlags(Qt.TextInteractionFlag.NoTextInteraction)
        self.name_label.setCursor(Qt.CursorShape.ArrowCursor)
        self.name_label.setMaximumHeight(32)  # 限制名称标签最大高度
        content_layout.addWidget(self.name_label)

        # 徽标行 - 版本和类型水平排列（左对齐）
        from ..utils.ue_version_detector import UEVersionDetector
        from ..logic.asset_model import PackageType
        
        badge_layout = QHBoxLayout()
        badge_layout.setSpacing(6)
        # 移除居中的 addStretch()，改为左对齐
        
        # 版本徽标
        version_detector = UEVersionDetector()
        pkg_type = getattr(self, 'package_type', None)
        version_badge = version_detector.format_version_badge(self.engine_min_version, pkg_type)
        
        self.version_label = QLabel(version_badge)
        self.version_label.setObjectName("VersionBadge")
        self.version_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.version_label.setTextInteractionFlags(Qt.TextInteractionFlag.NoTextInteraction)
        self.version_label.setCursor(Qt.CursorShape.ArrowCursor)
        
        # 样式：蓝色版本徽标
        self.version_label.setStyleSheet("""
            QLabel {
                color: #ffffff;
                font-size: 10px;
                font-weight: bold;
                background-color: rgba(0, 122, 204, 0.85);
                border-radius: 3px;
                padding: 2px 5px;
            }
        """)
        badge_layout.addWidget(self.version_label)
        
        # 类型徽标
        type_text = "资源包"  # 默认值
        if pkg_type:
            if hasattr(pkg_type, 'display_name'):
                type_text = pkg_type.display_name
            elif isinstance(pkg_type, str):
                try:
                    type_text = PackageType(pkg_type).display_name
                except (ValueError, AttributeError):
                    type_text = pkg_type
        
        self.type_label = QLabel(type_text)
        self.type_label.setObjectName("TypeBadge")
        self.type_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.type_label.setTextInteractionFlags(Qt.TextInteractionFlag.NoTextInteraction)
        self.type_label.setCursor(Qt.CursorShape.ArrowCursor)
        
        # 样式：橙色类型徽标
        self.type_label.setStyleSheet("""
            QLabel {
                color: #ffffff;
                font-size: 10px;
                font-weight: bold;
                background-color: rgba(255, 152, 0, 0.85);
                border-radius: 3px;
                padding: 2px 5px;
            }
        """)
        badge_layout.addWidget(self.type_label)
        badge_layout.addStretch()  # 右侧留白
        
        content_layout.addLayout(badge_layout)

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
        self.import_btn = ImportIconButton(28)
        self.import_btn.setObjectName("ImportButton")
        self.import_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.import_btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.import_btn.setAttribute(Qt.WidgetAttribute.WA_Hover, True)  # 启用悬停属性
        self.import_btn.setToolTip("导入资产")
        self.import_btn.clicked.connect(lambda: self.import_requested.emit(self.name))
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
        """显示默认占位符"""
        # 显示"未设置缩略图"文字提示
        self.thumbnail_label.setText("未设置\n缩略图")

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

        # 导出资产（压缩）
        export_action = QAction("📤 导出资产（压缩）", self)
        export_action.triggered.connect(lambda: self.export_requested.emit(self.name))
        menu.addAction(export_action)

        menu.addSeparator()

        # 检查是否有文档，如果有则添加"删除文档"选项
        if self._has_document():
            delete_doc_action = QAction("📄 删除文档", self)
            delete_doc_action.triggered.connect(self._on_delete_document)
            menu.addAction(delete_doc_action)

        delete_action = QAction("🗑️ 删除资产", self)
        delete_action.triggered.connect(lambda: self.delete_requested.emit(self.name))
        menu.addAction(delete_action)

        event_filter = MenuEventFilter(menu, self)
        menu.exec(self.mapToGlobal(position))
    
    def _has_document(self) -> bool:
        """检查资产是否有文档"""
        try:
            # 需要从父组件获取 logic 引用
            parent_widget = self.parent()
            while parent_widget:
                if hasattr(parent_widget, 'logic') and parent_widget.logic:
                    logic = parent_widget.logic
                    if hasattr(logic, 'documents_dir') and logic.documents_dir:
                        # 检查 .docx 文档是否存在
                        if hasattr(self, 'asset_id') and self.asset_id:
                            doc_path = logic.documents_dir / f"{self.asset_id}.docx"
                            return doc_path.exists()
                    break
                parent_widget = parent_widget.parent()
        except Exception as e:
            logger.error(f"检查文档存在性失败: {e}")
        return False
    
    def _on_delete_document(self):
        """删除文档"""
        try:
            # 获取 logic 引用
            parent_widget = self.parent()
            logic = None
            while parent_widget:
                if hasattr(parent_widget, 'logic') and parent_widget.logic:
                    logic = parent_widget.logic
                    break
                parent_widget = parent_widget.parent()
            
            if not logic or not hasattr(logic, 'documents_dir') or not logic.documents_dir:
                logger.error("无法获取文档目录")
                return
            
            if not hasattr(self, 'asset_id') or not self.asset_id:
                logger.error("资产ID未设置")
                return
            
            # 导入确认对话框
            from PyQt6.QtWidgets import QMessageBox
            
            # 显示确认对话框
            reply = QMessageBox.question(
                self,
                "确认删除",
                f"确定要删除资产 \"{self.name}\" 的文档吗？\n\n此操作不可恢复！",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No
            )
            
            if reply != QMessageBox.StandardButton.Yes:
                return
            
            # 删除文档文件
            doc_path = logic.documents_dir / f"{self.asset_id}.docx"
            
            if doc_path.exists():
                doc_path.unlink()
                logger.info(f"已删除文档: {doc_path}")
                QMessageBox.information(self, "删除成功", "文档已删除")
            else:
                QMessageBox.warning(self, "删除失败", "未找到文档文件")
                
        except Exception as e:
            logger.error(f"删除文档失败: {e}", exc_info=True)
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.warning(self, "错误", f"删除文档失败：{e}")

    def update_theme(self, theme: str):
        """更新主题

        Args:
            theme: 主题名称 ("dark" 或 "light")
        """
        self.theme = theme
        
        # 更新缩略图背景颜色
        if theme == "light":
            self.thumbnail_label.update_colors('#f5f5f5', '#cccccc')
        else:
            self.thumbnail_label.update_colors('#323232', '#707070')
        
        # 触发重绘以应用新主题
        self.update()

    def load_thumbnail(self):
        """加载缩略图（支持延迟加载）"""
        logger.debug(f"[紧凑卡片-缩略图加载] 资产: {self.name}")
        logger.debug(f"[紧凑卡片-缩略图加载] 缩略图路径: {self.thumbnail_path}")

        if self.thumbnail_path and Path(self.thumbnail_path).exists():
            logger.debug(f"[紧凑卡片-缩略图加载] 缩略图文件存在，开始加载")
            pixmap = QPixmap(str(self.thumbnail_path))
            if not pixmap.isNull():
                target_w, target_h = 172, 115
                scaled_pixmap = pixmap.scaled(
                    target_w, target_h,
                    Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                    Qt.TransformationMode.SmoothTransformation
                )
                self.thumbnail_label.setPixmap(scaled_pixmap)
                logger.debug(f"[紧凑卡片-缩略图加载] 成功加载缩略图: {self.name}")
            else:
                logger.warning(f"[紧凑卡片-缩略图加载] QPixmap 加载失败（isNull）: {self.thumbnail_path}")
                self._show_default_icon()
        else:
            if self.thumbnail_path:
                logger.warning(f"[紧凑卡片-缩略图加载] 缩略图文件不存在: {self.thumbnail_path}")
            else:
                logger.debug(f"[紧凑卡片-缩略图加载] 无缩略图路径")
            self._show_default_icon()
