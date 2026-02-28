# -*- coding: utf-8 -*-

"""
用户消息气泡组件 - ChatGPT风格
遵循QSS迁移规范，使用ObjectName关联样式
"""

from PyQt6.QtWidgets import (
    QWidget, QLabel, QVBoxLayout, QHBoxLayout, QPushButton, 
    QGraphicsOpacityEffect, QApplication
)
from PyQt6.QtCore import Qt, QPropertyAnimation, QEasingCurve, QSize, QTimer
from PyQt6.QtGui import QPainter, QColor, QPen, QPainterPath, QIcon, QPixmap


class CopyButton(QPushButton):
    """复制按钮 - 带淡入淡出效果"""
    
    # 类级别的图标缓存，避免重复创建
    _icon_cache = {}
    _check_icon_cache = {}  # 对钩图标缓存
    
    def __init__(self, theme: str = "dark", parent=None):
        super().__init__(parent)
        self.theme = theme
        self.setFixedSize(28, 28)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setObjectName("UserMessageCopyButton")  # 设置ObjectName关联QSS
        
        # 创建不透明度效果
        self.opacity_effect = QGraphicsOpacityEffect(self)
        self.opacity_effect.setOpacity(0.0)
        self.setGraphicsEffect(self.opacity_effect)
        
        # 创建复制图标
        self.update_icon()
        
        # 淡入淡出动画
        self.fade_animation = QPropertyAnimation(self.opacity_effect, b"opacity")
        self.fade_animation.setDuration(200)
        self.fade_animation.setEasingCurve(QEasingCurve.Type.InOutQuad)
        
        # 恢复图标的定时器
        self.restore_timer = QTimer()
        self.restore_timer.setSingleShot(True)
        self.restore_timer.timeout.connect(self.restore_copy_icon)
    
    def update_icon(self):
        """根据主题更新图标（使用缓存）"""
        # 检查缓存中是否已有该主题的图标
        if self.theme not in self._icon_cache:
            # 缓存中没有，创建新图标并缓存
            self._icon_cache[self.theme] = self._create_copy_icon()
        
        # 从缓存中获取图标
        self.setIcon(self._icon_cache[self.theme])
        self.setIconSize(QSize(20, 20))
    
    def _create_copy_icon(self):
        """创建复制图标（两个重叠的圆角正方形）"""
        # 使用更大的画布以获得更清晰的渲染
        size = 48
        pixmap = QPixmap(size, size)
        pixmap.fill(Qt.GlobalColor.transparent)
        
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        
        # 设置颜色和画笔
        color = QColor("#ececf1") if self.theme == "dark" else QColor("#2c2c2c")
        pen = QPen(color, 2.0)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        
        # 方块大小和位置
        box_size = 20
        corner_radius = 3
        offset = 7  # 两个矩形的偏移量
        
        # 绘制后面的方块（右下）- 只绘制右边和下边的L形
        back_x = 9 + offset
        back_y = 9 + offset
        
        path = QPainterPath()
        # 从右边中间开始，向上到右上角
        path.moveTo(back_x + box_size, back_y + box_size / 2)
        path.lineTo(back_x + box_size, back_y + corner_radius)
        # 右上角圆角
        path.arcTo(back_x + box_size - corner_radius * 2, back_y, 
                   corner_radius * 2, corner_radius * 2, 0, 90)
        # 移动到右下角（不绘制上边）
        path.moveTo(back_x + box_size, back_y + box_size / 2)
        path.lineTo(back_x + box_size, back_y + box_size - corner_radius)
        # 右下角圆角
        path.arcTo(back_x + box_size - corner_radius * 2, back_y + box_size - corner_radius * 2,
                   corner_radius * 2, corner_radius * 2, 0, -90)
        # 下边
        path.lineTo(back_x + corner_radius, back_y + box_size)
        # 左下角圆角
        path.arcTo(back_x, back_y + box_size - corner_radius * 2,
                   corner_radius * 2, corner_radius * 2, -90, -90)
        painter.drawPath(path)
        
        # 绘制前面的方块（左上）- 完整绘制
        painter.drawRoundedRect(10, 10, box_size, box_size, corner_radius, corner_radius)
        
        painter.end()
        return QIcon(pixmap)
    
    def _create_check_icon(self):
        """创建对钩图标"""
        size = 48
        pixmap = QPixmap(size, size)
        pixmap.fill(Qt.GlobalColor.transparent)
        
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        
        # 设置颜色和画笔（与复制按钮颜色一致）
        color = QColor("#ececf1") if self.theme == "dark" else QColor("#2c2c2c")
        pen = QPen(color, 3.0)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        painter.setPen(pen)
        
        # 绘制对钩
        path = QPainterPath()
        # 对钩的短边（左下到中间）
        path.moveTo(16, 26)
        path.lineTo(21, 31)
        # 对钩的长边（中间到右上）
        path.lineTo(32, 17)
        
        painter.drawPath(path)
        painter.end()
        return QIcon(pixmap)
    
    def show_check_icon(self):
        """显示对钩图标"""
        # 检查缓存中是否已有该主题的对钩图标
        if self.theme not in self._check_icon_cache:
            self._check_icon_cache[self.theme] = self._create_check_icon()
        
        # 设置对钩图标
        self.setIcon(self._check_icon_cache[self.theme])
        self.setIconSize(QSize(20, 20))
        
        # 2秒后恢复复制图标
        self.restore_timer.start(2000)
    
    def restore_copy_icon(self):
        """恢复复制图标"""
        self.update_icon()
    
    def fade_in(self):
        """淡入"""
        self.fade_animation.stop()
        self.fade_animation.setStartValue(self.opacity_effect.opacity())
        self.fade_animation.setEndValue(1.0)
        self.fade_animation.start()
    
    def fade_out(self):
        """淡出"""
        self.fade_animation.stop()
        self.fade_animation.setStartValue(self.opacity_effect.opacity())
        self.fade_animation.setEndValue(0.0)
        self.fade_animation.start()
    
    def set_theme(self, theme: str):
        """切换主题"""
        # 如果主题没变，直接返回
        if self.theme == theme:
            return
        
        self.theme = theme
        self.update_icon()


class UserMessageBubble(QWidget):
    """用户消息气泡 - ChatGPT风格"""
    
    MAX_CHARS_PER_LINE = 250  # 每行最大汉字数，用于换行宽度计算
    
    def __init__(self, message: str, theme: str = "dark", parent=None):
        super().__init__(parent)
        self.message = message
        self.theme = theme
        self.init_ui()
    
    def init_ui(self):
        """初始化UI（参考旧项目布局）"""
        # 主布局：垂直布局
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        # 气泡容器：水平布局（关键！）
        bubble_container = QWidget()
        bubble_container_layout = QHBoxLayout(bubble_container)
        bubble_container_layout.setContentsMargins(0, 0, 0, 0)
        bubble_container_layout.setSpacing(0)
        
        # 左侧弹性空间（让气泡右对齐）
        bubble_container_layout.addStretch(1)
        
        # 消息标签容器
        label_container = QWidget()
        label_layout = QVBoxLayout(label_container)
        label_layout.setContentsMargins(0, 0, 0, 35)  # 底部留35px给按钮
        label_layout.setSpacing(0)
        
        # 手动处理文本换行：每24个汉字插入换行
        wrapped_text = self._wrap_text_by_length(self.message, 24)
        
        # 消息标签
        self.message_label = QLabel(wrapped_text)
        self.message_label.setObjectName("UserMessageLabel")
        # 禁用WordWrap，使用手动换行
        self.message_label.setWordWrap(False)
        self.message_label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        
        # 设置高质量字体渲染（抗锯齿）
        from PyQt6.QtGui import QFont
        font = self.message_label.font()
        font.setHintingPreference(QFont.HintingPreference.PreferFullHinting)
        font.setStyleStrategy(QFont.StyleStrategy.PreferAntialias | QFont.StyleStrategy.PreferQuality)
        self.message_label.setFont(font)
        
        # 设置光标为文本选择样式
        self.message_label.setCursor(Qt.CursorShape.IBeamCursor)
        
        # 安装事件过滤器以保持光标状态
        self.message_label.installEventFilter(self)
        
        label_layout.addWidget(self.message_label)
        bubble_container_layout.addWidget(label_container)
        
        main_layout.addWidget(bubble_container)
        
        # 复制按钮（浮动在右下角）
        self.copy_btn = CopyButton(theme=self.theme, parent=self)
        self.copy_btn.clicked.connect(self.copy_message)
        self.copy_btn.raise_()
    
    def _wrap_text_by_length(self, text: str, max_chars: int) -> str:
        """手动换行：每max_chars个字符插入换行符
        
        Args:
            text: 原始文本
            max_chars: 每行最大字符数
            
        Returns:
            处理后的文本（带换行符）
        """
        if len(text) <= max_chars:
            return text
        
        lines = []
        current_pos = 0
        while current_pos < len(text):
            # 取max_chars个字符
            line = text[current_pos:current_pos + max_chars]
            lines.append(line)
            current_pos += max_chars
        
        return '\n'.join(lines)
    
    def resizeEvent(self, event):
        """调整大小时更新复制按钮位置"""
        super().resizeEvent(event)
        # 将复制按钮放在右下角，紧贴底部
        btn_x = self.width() - self.copy_btn.width() - 8
        btn_y = self.height() - self.copy_btn.height()  # 紧贴底部
        self.copy_btn.move(btn_x, btn_y)
    
    def enterEvent(self, event):
        """鼠标进入时淡入复制按钮"""
        super().enterEvent(event)
        self.copy_btn.fade_in()
    
    def leaveEvent(self, event):
        """鼠标离开时淡出复制按钮"""
        super().leaveEvent(event)
        self.copy_btn.fade_out()
    
    def eventFilter(self, obj, event):
        """事件过滤器：确保光标始终为IBeam"""
        if obj == self.message_label:
            # 鼠标进入时确保光标是IBeam
            if event.type() == event.Type.Enter:
                obj.setCursor(Qt.CursorShape.IBeamCursor)
            # 鼠标移动时确保光标是IBeam
            elif event.type() == event.Type.MouseMove:
                if obj.cursor().shape() != Qt.CursorShape.IBeamCursor:
                    obj.setCursor(Qt.CursorShape.IBeamCursor)
        return super().eventFilter(obj, event)
    
    def copy_message(self):
        """复制消息到剪贴板"""
        clipboard = QApplication.clipboard()
        clipboard.setText(self.message)
        print(f"已复制: {self.message[:20]}...")
        
        # 显示对钩图标反馈
        self.copy_btn.show_check_icon()
    
    def set_theme(self, theme: str):
        """切换主题"""
        # 如果主题没变，直接返回
        if self.theme == theme:
            return
        
        self.theme = theme
        self.copy_btn.set_theme(theme)
        # 主题切换时不需要重新计算宽度
    
    def _update_max_width(self):
        """根据MAX_CHARS_PER_LINE限制气泡宽度"""
        from PyQt6.QtGui import QFontMetrics
        fm = QFontMetrics(self.message_label.font())
        # 使用设定的最大汉字数计算宽度
        text_width = fm.horizontalAdvance("测" * self.MAX_CHARS_PER_LINE)
        padding = 40  # QLabel 样式左右padding + 额外边距
        label_max_width = text_width + padding
        
        # 设置最大宽度（允许自动换行）
        self.message_label.setMaximumWidth(label_max_width)
        # 不限制整体宽度，让其根据内容自适应
        # self.setMaximumWidth(label_max_width + self.copy_btn.width() + 16)
    
    def _insert_zero_width_spaces(self, text: str) -> str:
        """在连续的数字、字母之间插入零宽空格，允许换行"""
        # 如果文本很短，不需要处理
        if len(text) < 20:
            return text
        
        import re
        # 零宽空格字符
        zwsp = '\u200b'
        
        # 对于超长文本（>2000字符），限制处理范围以提高性能
        if len(text) > 2000:
            # 只处理前2000个字符，避免性能问题
            processed_part = re.sub(r'([a-zA-Z0-9]{5})', r'\1' + zwsp, text[:2000])
            return processed_part + text[2000:]
        
        # 使用正则表达式，更高效：每5个连续的字母数字字符后插入零宽空格
        # 这样可以减少零宽空格的数量，提高性能
        return re.sub(r'([a-zA-Z0-9]{5})', r'\1' + zwsp, text)
