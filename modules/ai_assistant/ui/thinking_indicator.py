# -*- coding: utf-8 -*-
"""
思考中动画指示器
显示"正在思考"或"调用XX工具"
"""

from PyQt6.QtWidgets import QWidget, QHBoxLayout, QLabel, QGraphicsOpacityEffect
from PyQt6.QtCore import Qt, QTimer, QPropertyAnimation, QEasingCurve, QRectF, pyqtProperty
from PyQt6.QtGui import QPainter, QColor


class CircleWidget(QWidget):
    """呼吸式圆形动画"""
    def __init__(self, parent=None, theme="dark"):
        super().__init__(parent)
        self.setFixedSize(20, 30)
        self._scale = 1.0
        self.parent_indicator = parent
        self.theme = theme
    
    def paintEvent(self, event):
        """绘制圆形"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        color = "#E0E0E0" if self.theme == "dark" else "#565869"
        painter.setBrush(QColor(color))
        painter.setPen(Qt.PenStyle.NoPen)
        
        scale = self.parent_indicator._scale if self.parent_indicator else 1.0
        
        radius = 5 * scale
        center_x = self.width() / 2
        center_y = self.height() / 2
        rect = QRectF(center_x - radius, center_y - radius, radius * 2, radius * 2)
        painter.drawEllipse(rect)


class ThinkingIndicator(QWidget):
    """思考中动画指示器（呼吸式圆形 + 文字）"""
    
    def __init__(self, parent=None, theme="dark"):
        super().__init__(parent)
        self._scale = 1.0
        self.theme = theme
        
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        layout.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        
        # 圆形
        self.circle_widget = CircleWidget(self, theme=theme)
        layout.addWidget(self.circle_widget, 0, Qt.AlignmentFlag.AlignVCenter)
        
        # 文字容器
        self.text_container = QWidget()
        self.text_container.setVisible(False)
        text_layout = QHBoxLayout(self.text_container)
        text_layout.setContentsMargins(0, 0, 0, 0)
        text_layout.setSpacing(2)
        
        text_color = "#E0E0E0" if theme == "dark" else "#565869"
        
        self.char_labels = []
        self.char_opacity_effects = []
        self.char_animations = []
        
        characters = ["正", "在", "思", "考"]
        for char in characters:
            label = QLabel(char)
            label.setStyleSheet(f"""
                font-family: "Microsoft YaHei UI", sans-serif;
                font-size: 18px;
                font-weight: 500;
                color: {text_color};
            """)
            label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            
            opacity_effect = QGraphicsOpacityEffect(label)
            opacity_effect.setOpacity(0.3)
            label.setGraphicsEffect(opacity_effect)
            
            self.char_labels.append(label)
            self.char_opacity_effects.append(opacity_effect)
            text_layout.addWidget(label)
        
        layout.addWidget(self.text_container, 0, Qt.AlignmentFlag.AlignVCenter)
        
        # 4秒后显示文字
        self.show_text_timer = QTimer(self)
        self.show_text_timer.setSingleShot(True)
        self.show_text_timer.timeout.connect(self._show_thinking_text)
        self.show_text_timer.start(4000)
        
        # 缩放动画
        self.scale_anim_forward = QPropertyAnimation(self, b"scale")
        self.scale_anim_forward.setStartValue(1.0)
        self.scale_anim_forward.setEndValue(1.5)
        self.scale_anim_forward.setDuration(800)
        self.scale_anim_forward.setEasingCurve(QEasingCurve.Type.InOutQuad)
        
        self.scale_anim_backward = QPropertyAnimation(self, b"scale")
        self.scale_anim_backward.setStartValue(1.5)
        self.scale_anim_backward.setEndValue(1.0)
        self.scale_anim_backward.setDuration(800)
        self.scale_anim_backward.setEasingCurve(QEasingCurve.Type.InOutQuad)
        
        self.scale_anim_forward.finished.connect(self.scale_anim_backward.start)
        self.scale_anim_backward.finished.connect(self.scale_anim_forward.start)
        
        # 启动缩放动画
        self.scale_anim_forward.start()
    
    def _show_thinking_text(self):
        """显示文字并启动动画"""
        self.text_container.setVisible(True)
        self._start_text_animation()
    
    def _start_text_animation(self):
        """文字淡入淡出动画 - 波浪式"""
        stagger_delay = 250
        fade_duration = 500
        
        for i, opacity_effect in enumerate(self.char_opacity_effects):
            fade_in = QPropertyAnimation(opacity_effect, b"opacity")
            fade_in.setStartValue(0.3)
            fade_in.setEndValue(1.0)
            fade_in.setDuration(fade_duration)
            fade_in.setEasingCurve(QEasingCurve.Type.InOutSine)
            
            fade_out = QPropertyAnimation(opacity_effect, b"opacity")
            fade_out.setStartValue(1.0)
            fade_out.setEndValue(0.3)
            fade_out.setDuration(fade_duration)
            fade_out.setEasingCurve(QEasingCurve.Type.InOutSine)
            
            def create_animation_loop(fade_in_anim, fade_out_anim, delay):
                fade_in_anim.finished.connect(fade_out_anim.start)
                fade_out_anim.finished.connect(fade_in_anim.start)
                QTimer.singleShot(delay, fade_in_anim.start)
            
            delay = i * stagger_delay
            create_animation_loop(fade_in, fade_out, delay)
            self.char_animations.append((fade_in, fade_out))
    
    def get_scale(self):
        return self._scale
    
    def set_scale(self, value):
        self._scale = value
        self.circle_widget.update()
    
    scale = pyqtProperty(float, get_scale, set_scale)
    
    def update_text(self, text: str):
        """动态更新显示的文字
        
        Args:
            text: 新的文字内容
        """
        # 停止4秒延迟定时器（如果正在运行）
        if self.show_text_timer and self.show_text_timer.isActive():
            self.show_text_timer.stop()
        
        # 停止现有的字符动画
        for fade_in, fade_out in self.char_animations:
            fade_in.stop()
            fade_out.stop()
        
        # 清空现有的字符标签
        for label in self.char_labels:
            label.deleteLater()
        
        self.char_labels.clear()
        self.char_opacity_effects.clear()
        self.char_animations.clear()
        
        text_color = "#E0E0E0" if self.theme == "dark" else "#565869"
        text_layout = self.text_container.layout()
        
        # 创建新的字符标签
        characters = list(text)
        for char in characters:
            label = QLabel(char)
            label.setStyleSheet(f"""
                font-family: "Microsoft YaHei UI", sans-serif;
                font-size: 18px;
                font-weight: 500;
                color: {text_color};
            """)
            label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            
            opacity_effect = QGraphicsOpacityEffect(label)
            opacity_effect.setOpacity(0.3)
            label.setGraphicsEffect(opacity_effect)
            
            self.char_labels.append(label)
            self.char_opacity_effects.append(opacity_effect)
            text_layout.addWidget(label)
        
        # 立即显示文字容器
        self.text_container.setVisible(True)
        # 启动文字动画
        self._start_text_animation()
    
    def stop(self):
        """停止所有动画"""
        # 停止缩放动画并断开信号连接
        try:
            self.scale_anim_forward.finished.disconnect()
        except:
            pass
        try:
            self.scale_anim_backward.finished.disconnect()
        except:
            pass
        
        self.scale_anim_forward.stop()
        self.scale_anim_backward.stop()
        
        # 停止文字显示定时器
        if self.show_text_timer and self.show_text_timer.isActive():
            self.show_text_timer.stop()
        
        # 停止所有字符动画并断开信号连接
        for fade_in, fade_out in self.char_animations:
            try:
                fade_in.finished.disconnect()
            except:
                pass
            try:
                fade_out.finished.disconnect()
            except:
                pass
            fade_in.stop()
            fade_out.stop()
        
        # 清空动画列表
        self.char_animations.clear()
