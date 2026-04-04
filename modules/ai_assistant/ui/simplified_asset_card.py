# -*- coding: utf-8 -*-

"""
简化资产卡片组件 - 用于AI助手聊天界面

基于 ModernAssetCard，但移除右键菜单，只保留预览和导入按钮
"""

from pathlib import Path
from typing import Optional
import logging

from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFrame
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QPixmap, QPainter, QPainterPath, QColor, QLinearGradient, QPen

logger = logging.getLogger(__name__)


class SimplifiedThumbnailWidget(QWidget):
    """简化缩略图容器"""

    def __init__(self, width: int, height: int, radius: int = 16,
                 bg_color: str = "#2c2c2c", text_color: str = "#b0b0b0", parent=None):
        super().__init__(parent)
        self.setFixedSize(width, height)
        self.radius = radius
        self.bg_color = bg_color
        self.text_color = text_color
        self._pixmap = None
        self._text = ""
        
        self.setObjectName("SimplifiedThumbnailWidget")
    
    def update_colors(self, bg_color: str, text_color: str):
        """更新颜色（用于主题切换）"""
        self.bg_color = bg_color
        self.text_color = text_color
        self.update()
    
    def setPixmap(self, pixmap: QPixmap):
        """设置图片"""
        if pixmap and not pixmap.isNull():
            target_w = self.width()
            target_h = self.height()
            
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

    def paintEvent(self, event):
        """绘制缩略图"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
        
        widget_rect = self.rect()
        w = widget_rect.width()
        h = widget_rect.height()
        
        # 创建圆角路径
        path = QPainterPath()
        path.addRoundedRect(0.0, 0.0, float(w), float(h), 
                           float(self.radius), float(self.radius))
        
        painter.setClipPath(path)
        painter.fillRect(0, 0, w, h, QColor(self.bg_color))
        
        if self._pixmap and not self._pixmap.isNull():
            px_w = self._pixmap.width()
            px_h = self._pixmap.height()
            x = (w - px_w) // 2
            y = (h - px_h) // 2
            painter.drawPixmap(x, y, self._pixmap)
        elif self._text:
            painter.setPen(QColor(self.text_color))
            font = painter.font()
            font.setPixelSize(14)
            painter.setFont(font)
            painter.drawText(widget_rect, 
                           int(Qt.AlignmentFlag.AlignCenter), 
                           self._text)
        
        painter.end()


class SimplifiedAssetCard(QFrame):
    """简化资产卡片 - 用于AI聊天界面，无右键菜单"""

    preview_clicked = pyqtSignal(str)  # 发送资产名称
    import_clicked = pyqtSignal(str)  # 发送资产名称

    def __init__(self, name: str, category: str, size: str,
                 thumbnail_path: Optional[str] = None,
                 theme: str = "dark",
                 parent=None):
        super().__init__(parent)
        self.name = name
        self.category = category
        self.asset_size = size
        self.thumbnail_path = thumbnail_path
        self.theme = theme

        self.setObjectName("SimplifiedAssetCard")
        self.setFixedSize(180, 240)
        
        self._init_ui()
    
    def _init_ui(self):
        """初始化UI"""
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
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        # 缩略图
        self.thumbnail_label = SimplifiedThumbnailWidget(
            width=164, height=120, radius=8,
            bg_color=colors['thumbnail_bg'],
            text_color=colors['thumbnail_text']
        )
        self.load_thumbnail()
        layout.addWidget(self.thumbnail_label)

        # 名称
        self.name_label = QLabel(self.name)
        self.name_label.setObjectName("SimplifiedAssetName")
        self.name_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.name_label.setWordWrap(True)
        self.name_label.setMaximumHeight(40)
        layout.addWidget(self.name_label)

        # 分类和大小
        info_layout = QHBoxLayout()
        self.category_label = QLabel(self.category)
        self.category_label.setObjectName("SimplifiedAssetCategory")
        self.size_label = QLabel(self.asset_size)
        self.size_label.setObjectName("SimplifiedAssetSize")
        info_layout.addWidget(self.category_label)
        info_layout.addStretch()
        info_layout.addWidget(self.size_label)
        layout.addLayout(info_layout)

        # 按钮
        button_layout = QHBoxLayout()
        button_layout.setSpacing(8)

        self.preview_btn = QPushButton("预览")
        self.preview_btn.setObjectName("SimplifiedPreviewButton")
        self.preview_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.preview_btn.clicked.connect(lambda: self.preview_clicked.emit(self.name))
        button_layout.addWidget(self.preview_btn)

        self.import_btn = QPushButton("导入")
        self.import_btn.setObjectName("SimplifiedImportButton")
        self.import_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.import_btn.clicked.connect(lambda: self.import_clicked.emit(self.name))
        button_layout.addWidget(self.import_btn)

        layout.addLayout(button_layout)
        self.setLayout(layout)
    
    def load_thumbnail(self):
        """加载缩略图"""
        if self.thumbnail_path and Path(self.thumbnail_path).exists():
            pixmap = QPixmap(str(self.thumbnail_path))
            if not pixmap.isNull():
                self.thumbnail_label.setPixmap(pixmap)
            else:
                self.thumbnail_label.setText("无缩略图")
        else:
            self.thumbnail_label.setText("无缩略图")
    
    def paintEvent(self, event):
        """自定义绘制 - 绘制卡片背景"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        rect = self.rect()
        radius = 8.0

        # 绘制背景
        gradient = QLinearGradient(0, 0, rect.width(), rect.height())
        if self.theme == "light":
            gradient.setColorAt(0, QColor("#ffffff"))
            gradient.setColorAt(1, QColor("#f8f8f8"))
        else:
            gradient.setColorAt(0, QColor("#2c2c2c"))
            gradient.setColorAt(1, QColor("#242424"))

        path = QPainterPath()
        path.addRoundedRect(0.0, 0.0, float(rect.width()), float(rect.height()), radius, radius)
        painter.fillPath(path, gradient)

        # 绘制边框
        pen = QPen(QColor("#454545") if self.theme == "dark" else QColor("#e0e0e0"))
        pen.setWidth(1)
        painter.setPen(pen)
        painter.drawRoundedRect(rect.adjusted(0, 0, -1, -1), radius, radius)

        painter.end()
