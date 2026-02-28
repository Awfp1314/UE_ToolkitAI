# -*- coding: utf-8 -*-

"""
图标工具模块
提供图标加载和圆角处理功能
"""

from pathlib import Path
from PyQt6.QtGui import QPixmap, QPainter, QPainterPath, QIcon, QImage
from PyQt6.QtCore import Qt, QRectF


def get_icon_path() -> Path:
    """获取图标文件路径
    
    优先使用 PNG 格式（支持透明圆角），如果不存在则使用 ICO 格式
    
    Returns:
        图标文件路径
    """
    base_path = Path(__file__).parent.parent / "resources"
    
    # 优先使用 PNG 格式
    png_path = base_path / "tubiao.png"
    if png_path.exists():
        return png_path
    
    # 回退到 ICO 格式
    ico_path = base_path / "tubiao.ico"
    if ico_path.exists():
        return ico_path
    
    return png_path  # 返回 PNG 路径（即使不存在，让调用方处理）


def create_rounded_pixmap(pixmap: QPixmap, radius: int = None) -> QPixmap:
    """将 QPixmap 处理成圆角
    
    Args:
        pixmap: 原始图片
        radius: 圆角半径，默认为图片宽度的 20%
        
    Returns:
        圆角处理后的 QPixmap
    """
    if pixmap.isNull():
        return pixmap
    
    size = pixmap.size()
    width = size.width()
    height = size.height()
    
    # 默认圆角半径为宽度的 20%
    if radius is None:
        radius = int(min(width, height) * 0.2)
    
    # 创建透明背景的目标图片
    rounded = QPixmap(size)
    rounded.fill(Qt.GlobalColor.transparent)
    
    # 使用 QPainter 绘制圆角图片
    painter = QPainter(rounded)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
    
    # 创建圆角路径
    path = QPainterPath()
    path.addRoundedRect(QRectF(0, 0, width, height), radius, radius)
    
    # 设置裁剪区域
    painter.setClipPath(path)
    
    # 绘制原图
    painter.drawPixmap(0, 0, pixmap)
    painter.end()
    
    return rounded


def load_icon(size: int = None, rounded: bool = True, radius: int = None) -> QPixmap:
    """加载应用图标
    
    Args:
        size: 目标尺寸（正方形），None 表示原始大小
        rounded: 是否应用圆角效果
        radius: 圆角半径，None 表示自动计算
        
    Returns:
        处理后的 QPixmap
    """
    icon_path = get_icon_path()
    
    if not icon_path.exists():
        return QPixmap()
    
    pixmap = QPixmap(str(icon_path))
    
    if pixmap.isNull():
        return pixmap
    
    # 缩放到目标尺寸
    if size is not None:
        pixmap = pixmap.scaled(
            size, size,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation
        )
    
    # 应用圆角效果
    if rounded:
        pixmap = create_rounded_pixmap(pixmap, radius)
    
    return pixmap


def load_app_icon(rounded: bool = True) -> QIcon:
    """加载应用程序图标（用于窗口图标和任务栏）
    
    Args:
        rounded: 是否应用圆角效果
        
    Returns:
        QIcon 对象，包含多个尺寸
    """
    icon = QIcon()
    icon_path = get_icon_path()
    
    if not icon_path.exists():
        return icon
   