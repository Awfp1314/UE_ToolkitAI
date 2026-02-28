# -*- coding: utf-8 -*-

"""
桌面悬浮窗 — 类似 360 加速球
独立的顶层圆形窗口，支持拖拽、靠边吸附、自动收起/展开、快捷菜单
"""

import sys
import json
from pathlib import Path

from PyQt6.QtWidgets import QWidget, QApplication
from PyQt6.QtCore import (
    Qt, QPoint, QTimer, QPropertyAnimation, QEasingCurve,
    pyqtSignal, QRect, QSize
)
from PyQt6.QtGui import (
    QPainter, QColor, QPen, QIcon, QCursor, QMouseEvent,
    QPainterPath, QPixmap
)

from core.logger import get_logger

logger = get_logger(__name__)


# ============================================================================
# 配置文件路径
# ============================================================================

def _get_general_settings_path() -> Path:
    """获取 general_settings.json 路径"""
    import os
    appdata = os.environ.get("APPDATA", "")
    return Path(appdata) / "ue_toolkit" / "user_data" / "general_settings.json"


def _load_general_settings() -> dict:
    """加载通用设置"""
    path = _get_general_settings_path()
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}


def _save_general_settings(data: dict):
    """保存通用设置"""
    path = _get_general_settings_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


# ============================================================================
# FloatingQuickMenu — 左键快捷菜单
# ============================================================================

class FloatingQuickMenu(QWidget):
    """悬浮窗快捷菜单 — 显示程序功能板块"""

    module_clicked = pyqtSignal(int)

    MODULES = [
        {"name": "我的工程", "icon": "📁", "index": 0},
        {"name": "资产库",   "icon": "📦", "index": 1},
        {"name": "AI 助手",  "icon": "🤖", "index": 2},
        {"name": "工程配置", "icon": "⚙️", "index": 3},
        {"name": "作者推荐", "icon": "⭐", "index": 4},
    ]

    ITEM_HEIGHT = 40
    MENU_WIDTH = 160
    PADDING = 8

    def __init__(self, theme: str = "dark", parent=None):
        super().__init__(parent)
        self._theme = theme
        self._hover_index = -1

        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
            | Qt.WindowType.Popup
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setMouseTracking(True)

        menu_h = len(self.MODULES) * self.ITEM_HEIGHT + self.PADDING * 2
        self.setFixedSize(self.MENU_WIDTH, menu_h)

    # --- 绘制 ---
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # 背景
        if self._theme == "dark":
            bg = QColor("#2b2b2b")
            text_color = QColor("#e0e0e0")
            hover_bg = QColor("#3c3c3c")
            border_color = QColor("#555")
        else:
            bg = QColor("#ffffff")
            text_color = QColor("#333333")
            hover_bg = QColor("#f0f0f0")
            border_color = QColor("#ccc")

        # 圆角矩形背景
        painter.setBrush(bg)
        painter.setPen(QPen(border_color, 1))
        painter.drawRoundedRect(self.rect().adjusted(1, 1, -1, -1), 8, 8)

        # 绘制菜单项
        for i, mod in enumerate(self.MODULES):
            y = self.PADDING + i * self.ITEM_HEIGHT

            # hover 高亮
            if i == self._hover_index:
                painter.setBrush(hover_bg)
                painter.setPen(Qt.PenStyle.NoPen)
                if i == 0:
                    painter.drawRoundedRect(QRect(2, y, self.MENU_WIDTH - 4, self.ITEM_HEIGHT), 6, 6)
                elif i == len(self.MODULES) - 1:
                    painter.drawRoundedRect(QRect(2, y, self.MENU_WIDTH - 4, self.ITEM_HEIGHT), 6, 6)
                else:
                    painter.drawRect(QRect(2, y, self.MENU_WIDTH - 4, self.ITEM_HEIGHT))

            # 图标 + 文字
            painter.setPen(text_color)
            font = painter.font()
            font.setPixelSize(14)
            painter.setFont(font)
            text = f"  {mod['icon']}  {mod['name']}"
            painter.drawText(QRect(8, y, self.MENU_WIDTH - 16, self.ITEM_HEIGHT),
                             Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
                             text)

    def mouseMoveEvent(self, event):
        y = event.position().y() - self.PADDING
        index = int(y // self.ITEM_HEIGHT)
        if 0 <= index < len(self.MODULES):
            self._hover_index = index
        else:
            self._hover_index = -1
        self.update()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            y = event.position().y() - self.PADDING
            index = int(y // self.ITEM_HEIGHT)
            if 0 <= index < len(self.MODULES):
                self.module_clicked.emit(self.MODULES[index]["index"])
                self.hide()

    def leaveEvent(self, event):
        self._hover_index = -1
        self.update()
        # 鼠标离开菜单后关闭
        QTimer.singleShot(300, self._check_close)

    def _check_close(self):
        if not self.underMouse():
            self.hide()

    def set_theme(self, theme: str):
        self._theme = theme
        self.update()


# ============================================================================
# FloatingContextMenu — 右键上下文菜单（鼠标离开自动关闭）
# ============================================================================

class FloatingContextMenu(QWidget):
    """悬浮窗右键菜单 — 鼠标离开自动收起"""

    action_triggered = pyqtSignal(str)  # 发射动作 key

    ITEM_HEIGHT = 36
    SEPARATOR_HEIGHT = 9
    MENU_WIDTH = 170
    PADDING = 6

    def __init__(self, theme: str = "dark", parent=None):
        super().__init__(parent)
        self._theme = theme
        self._hover_index = -1
        self._items: list[dict] = []  # {"key", "text", "checkable", "checked", "separator"}

        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
            | Qt.WindowType.Popup
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setMouseTracking(True)

    def set_items(self, items: list[dict]):
        """设置菜单项列表，每项: {key, text, checkable?, checked?, separator?}"""
        self._items = items
        total_h = self.PADDING * 2
        for item in items:
            total_h += self.SEPARATOR_HEIGHT if item.get("separator") else self.ITEM_HEIGHT
        self.setFixedSize(self.MENU_WIDTH, total_h)

    def _item_y(self, target_index: int) -> int:
        y = self.PADDING
        for i, item in enumerate(self._items):
            if i == target_index:
                return y
            y += self.SEPARATOR_HEIGHT if item.get("separator") else self.ITEM_HEIGHT
        return y

    def _hit_test(self, mouse_y: float) -> int:
        y = self.PADDING
        for i, item in enumerate(self._items):
            h = self.SEPARATOR_HEIGHT if item.get("separator") else self.ITEM_HEIGHT
            if y <= mouse_y < y + h:
                return -1 if item.get("separator") else i
            y += h
        return -1

    # --- 绘制 ---
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        if self._theme == "dark":
            bg = QColor("#2b2b2b")
            text_color = QColor("#e0e0e0")
            hover_bg = QColor("#3c3c3c")
            border_color = QColor("#555")
            sep_color = QColor("#444")
        else:
            bg = QColor("#ffffff")
            text_color = QColor("#333333")
            hover_bg = QColor("#f0f0f0")
            border_color = QColor("#ccc")
            sep_color = QColor("#ddd")

        painter.setBrush(bg)
        painter.setPen(QPen(border_color, 1))
        painter.drawRoundedRect(self.rect().adjusted(1, 1, -1, -1), 8, 8)

        font = painter.font()
        font.setPixelSize(13)
        painter.setFont(font)

        y = self.PADDING
        for i, item in enumerate(self._items):
            if item.get("separator"):
                painter.setPen(QPen(sep_color, 1))
                sy = y + self.SEPARATOR_HEIGHT // 2
                painter.drawLine(10, sy, self.MENU_WIDTH - 10, sy)
                y += self.SEPARATOR_HEIGHT
                continue

            # hover
            if i == self._hover_index:
                painter.setBrush(hover_bg)
                painter.setPen(Qt.PenStyle.NoPen)
                r = QRect(2, y, self.MENU_WIDTH - 4, self.ITEM_HEIGHT)
                if i == 0 or (i > 0 and self._items[i - 1].get("separator")):
                    painter.drawRoundedRect(r, 6, 6)
                elif i == len(self._items) - 1:
                    painter.drawRoundedRect(r, 6, 6)
                else:
                    painter.drawRect(r)

            painter.setPen(text_color)
            label = item.get("text", "")
            if item.get("checkable") and item.get("checked"):
                label = "✓ " + label
            painter.drawText(
                QRect(12, y, self.MENU_WIDTH - 24, self.ITEM_HEIGHT),
                Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
                label,
            )
            y += self.ITEM_HEIGHT

    def mouseMoveEvent(self, event):
        idx = self._hit_test(event.position().y())
        self._hover_index = idx
        self.update()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            idx = self._hit_test(event.position().y())
            if idx >= 0:
                key = self._items[idx].get("key", "")
                if key:
                    self.action_triggered.emit(key)
                self.hide()

    def leaveEvent(self, event):
        self._hover_index = -1
        self.update()
        QTimer.singleShot(300, self._check_close)

    def _check_close(self):
        if not self.underMouse():
            self.hide()

    def set_theme(self, theme: str):
        self._theme = theme
        self.update()


# ============================================================================
# FloatingWidget — 悬浮窗主体
# ============================================================================

class FloatingWidget(QWidget):
    """桌面悬浮窗 — 类似 360 加速球"""

    # 信号
    module_selected = pyqtSignal(int)       # 快捷菜单选择模块
    theme_toggle_requested = pyqtSignal()   # 请求切换主题
    autostart_changed = pyqtSignal(bool)    # 开机自启状态变化
    floating_close_requested = pyqtSignal() # 请求关闭悬浮窗

    # 常量
    DIAMETER = 50
    COLLAPSE_DELAY = 500        # 收起延迟 ms
    ANIMATION_DURATION = 200    # 收起/展开动画 ms
    SNAP_ANIMATION_DURATION = 300  # 吸附动画 ms
    DRAG_THRESHOLD = 5          # 拖拽判定阈值 px
    COLLAPSE_RATIO = 0.5        # 收起时露出比例

    def __init__(self, main_window=None, parent=None):
        super().__init__(parent)
        self._main_window = main_window
        self._theme = "dark"

        # 状态
        self._snapped_edge = "right"  # left / right / top
        self._is_collapsed = False
        self._is_dragging = False
        self._drag_start_pos = None
        self._drag_start_global = None

        # 窗口属性
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFixedSize(self.DIAMETER, self.DIAMETER)
        self.setMouseTracking(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        # 加载图标
        self._icon = self._load_icon()

        # 收起定时器
        self._collapse_timer = QTimer(self)
        self._collapse_timer.setSingleShot(True)
        self._collapse_timer.timeout.connect(self._collapse)

        # 位置动画
        self._pos_animation = QPropertyAnimation(self, b"pos")
        self._pos_animation.setEasingCurve(QEasingCurve.Type.OutCubic)

        # 快捷菜单
        self._quick_menu = FloatingQuickMenu(theme=self._theme)
        self._quick_menu.module_clicked.connect(self._on_module_clicked)
        self._quick_menu.hide()

        # 右键菜单
        self._context_menu = FloatingContextMenu(theme=self._theme)
        self._context_menu.action_triggered.connect(self._on_context_action)
        self._context_menu.hide()

        # 恢复位置
        self.restore_position()

        logger.info("悬浮窗已创建")

    # ------------------------------------------------------------------
    # 图标加载
    # ------------------------------------------------------------------
    def _load_icon(self) -> QIcon:
        """加载程序图标"""
        icon_path = Path(__file__).parent.parent / "resources" / "tubiao.ico"
        if icon_path.exists():
            return QIcon(str(icon_path))
        return QIcon()

    # ------------------------------------------------------------------
    # 外观绘制 (Req 1.1 ~ 1.5)
    # ------------------------------------------------------------------
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)

        # 1. 阴影
        shadow_color = QColor(0, 0, 0, 40)
        painter.setBrush(shadow_color)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(2, 2, self.DIAMETER - 2, self.DIAMETER - 2)

        # 2. 圆形裁剪区域
        circle_x, circle_y = 1, 1
        circle_d = self.DIAMETER - 4
        clip_path = QPainterPath()
        clip_path.addEllipse(float(circle_x), float(circle_y),
                             float(circle_d), float(circle_d))

        # 3. 图标裁剪成圆形填满
        if not self._icon.isNull():
            painter.save()
            painter.setClipPath(clip_path)
            pixmap = self._icon.pixmap(256, 256)
            painter.drawPixmap(circle_x, circle_y, circle_d, circle_d, pixmap)
            painter.restore()
        else:
            # fallback: 纯色圆
            painter.setBrush(QColor("#4a9eff"))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawEllipse(circle_x, circle_y, circle_d, circle_d)

        # 4. 边框
        if self._theme == "dark":
            border_color = QColor("#555")
        else:
            border_color = QColor("#ccc")
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.setPen(QPen(border_color, 1))
        painter.drawEllipse(circle_x, circle_y, circle_d, circle_d)

    def set_theme(self, theme: str):
        """切换主题 ('dark' / 'light')"""
        self._theme = theme
        self._quick_menu.set_theme(theme)
        self._context_menu.set_theme(theme)
        self.update()

    # ------------------------------------------------------------------
    # 拖拽 (Req 2.1, 2.3)
    # ------------------------------------------------------------------
    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_start_pos = event.globalPosition().toPoint()
            self._drag_start_global = self.pos()
            self._is_dragging = False
            # 拖拽中取消收起
            self._collapse_timer.stop()

    def mouseMoveEvent(self, event):
        if self._drag_start_pos is not None and event.buttons() & Qt.MouseButton.LeftButton:
            delta = event.globalPosition().toPoint() - self._drag_start_pos
            if not self._is_dragging:
                if (abs(delta.x()) > self.DRAG_THRESHOLD
                        or abs(delta.y()) > self.DRAG_THRESHOLD):
                    self._is_dragging = True
                    # 如果处于收起状态，先展开
                    if self._is_collapsed:
                        self._is_collapsed = False
            if self._is_dragging:
                self.move(self._drag_start_global + delta)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            if self._is_dragging:
                # 拖拽结束 → 吸附
                self._snap_to_nearest_edge()
                self._is_dragging = False
            else:
                # 点击 → 快捷菜单
                self._show_quick_menu()
            self._drag_start_pos = None
            self._drag_start_global = None

    # ------------------------------------------------------------------
    # 靠边吸附 (Req 2.2, 2.3, 2.4, 2.5)
    # ------------------------------------------------------------------
    def _get_current_screen(self):
        """获取悬浮窗当前所在屏幕"""
        center = self.geometry().center()
        screen = QApplication.screenAt(center)
        if screen is None:
            screen = QApplication.primaryScreen()
        return screen

    def _snap_to_nearest_edge(self):
        """吸附到最近的屏幕边缘（左/右/上）"""
        screen = self._get_current_screen()
        if screen is None:
            return
        geo = screen.availableGeometry()
        center = self.geometry().center()

        dist_left = center.x() - geo.left()
        dist_right = geo.right() - center.x()
        dist_top = center.y() - geo.top()

        min_dist = min(dist_left, dist_right, dist_top)

        if min_dist == dist_left:
            target_x = geo.left()
            target_y = self.y()
            self._snapped_edge = "left"
        elif min_dist == dist_right:
            target_x = geo.right() - self.DIAMETER
            target_y = self.y()
            self._snapped_edge = "right"
        else:
            target_x = self.x()
            target_y = geo.top()
            self._snapped_edge = "top"

        # Y 轴边界限制
        target_y = max(geo.top(), min(target_y, geo.bottom() - self.DIAMETER))
        # X 轴边界限制（top 吸附时）
        target_x = max(geo.left(), min(target_x, geo.right() - self.DIAMETER))

        self._animate_to(target_x, target_y, self.SNAP_ANIMATION_DURATION)
        self.save_position()

    def _animate_to(self, x: int, y: int, duration: int):
        """动画移动到目标位置"""
        self._pos_animation.stop()
        self._pos_animation.setDuration(duration)
        self._pos_animation.setStartValue(self.pos())
        self._pos_animation.setEndValue(QPoint(x, y))
        self._pos_animation.start()

    # ------------------------------------------------------------------
    # 自动收起/展开 (Req 3.1 ~ 3.5)
    # ------------------------------------------------------------------
    def enterEvent(self, event):
        """鼠标进入 → 取消收起 → 展开"""
        self._collapse_timer.stop()
        self._expand()

    def leaveEvent(self, event):
        """鼠标离开 → 启动收起定时器"""
        if (not self._is_dragging
                and not self._quick_menu.isVisible()
                and not self._context_menu.isVisible()):
            self._collapse_timer.start(self.COLLAPSE_DELAY)

    def _collapse(self):
        """收起到屏幕边缘（只露出一半）"""
        if self._is_collapsed or self._is_dragging:
            return

        half = int(self.DIAMETER * self.COLLAPSE_RATIO)
        screen = self._get_current_screen()
        if screen is None:
            return
        screen_geo = screen.availableGeometry()

        if self._snapped_edge == "left":
            target_x = screen_geo.left() - half
            target_y = self.y()
        elif self._snapped_edge == "right":
            target_x = screen_geo.right() - self.DIAMETER + half
            target_y = self.y()
        else:  # top
            target_x = self.x()
            target_y = screen_geo.top() - half

        self._animate_to(target_x, target_y, self.ANIMATION_DURATION)
        self._is_collapsed = True

    def _expand(self):
        """从屏幕边缘展开"""
        if not self._is_collapsed:
            return

        screen = self._get_current_screen()
        if screen is None:
            return
        screen_geo = screen.availableGeometry()

        if self._snapped_edge == "left":
            target_x = screen_geo.left()
            target_y = self.y()
        elif self._snapped_edge == "right":
            target_x = screen_geo.right() - self.DIAMETER
            target_y = self.y()
        else:  # top
            target_x = self.x()
            target_y = screen_geo.top()

        self._animate_to(target_x, target_y, self.ANIMATION_DURATION)
        self._is_collapsed = False

    # ------------------------------------------------------------------
    # 左键快捷菜单 (Req 4.1 ~ 4.9)
    # ------------------------------------------------------------------
    def _show_quick_menu(self):
        """弹出快捷菜单"""
        self._collapse_timer.stop()
        pos = self._get_menu_position(
            self._quick_menu.MENU_WIDTH,
            self._quick_menu.height()
        )
        self._quick_menu.move(pos)
        self._quick_menu.show()

    def _get_menu_position(self, menu_w: int, menu_h: int) -> QPoint:
        """根据吸附边缘计算菜单弹出位置"""
        gap = 4
        if self._snapped_edge == "left":
            x = self.x() + self.DIAMETER + gap
            y = self.y() - menu_h // 2 + self.DIAMETER // 2
        elif self._snapped_edge == "right":
            x = self.x() - menu_w - gap
            y = self.y() - menu_h // 2 + self.DIAMETER // 2
        else:  # top
            x = self.x() - menu_w // 2 + self.DIAMETER // 2
            y = self.y() + self.DIAMETER + gap

        # 确保不超出屏幕
        screen = self._get_current_screen()
        if screen:
            sg = screen.availableGeometry()
            x = max(sg.left(), min(x, sg.right() - menu_w))
            y = max(sg.top(), min(y, sg.bottom() - menu_h))

        return QPoint(x, y)

    def _on_module_clicked(self, index: int):
        """快捷菜单点击模块"""
        self.module_selected.emit(index)
        # 菜单关闭后重新启动收起定时器
        self._collapse_timer.start(self.COLLAPSE_DELAY)

    # ------------------------------------------------------------------
    # 右键上下文菜单 (Req 5.1 ~ 5.6)
    # ------------------------------------------------------------------
    def contextMenuEvent(self, event):
        self._collapse_timer.stop()
        self._show_context_menu(event.globalPos())

    def _show_context_menu(self, pos: QPoint):
        """右键菜单 — 使用自定义 widget，鼠标离开自动关闭"""
        autostart_on = self._is_autostart_enabled()
        theme_text = "☀️ 浅色模式" if self._theme == "dark" else "🌙 深色模式"

        items = [
            {"key": "open", "text": "📂 打开主窗口"},
            {"separator": True},
            {"key": "theme", "text": theme_text},
            {"key": "autostart", "text": "🚀 开机自启", "checkable": True, "checked": autostart_on},
            {"separator": True},
            {"key": "close_float", "text": "👁 关闭悬浮窗"},
            {"key": "exit", "text": "❌ 退出程序"},
        ]
        self._context_menu.set_items(items)
        self._context_menu.set_theme(self._theme)

        menu_pos = self._get_menu_position(
            self._context_menu.MENU_WIDTH,
            self._context_menu.height(),
        )
        self._context_menu.move(menu_pos)
        self._context_menu.show()

    def _on_context_action(self, key: str):
        """右键菜单动作分发"""
        if key == "open":
            self._open_main_window()
        elif key == "theme":
            self._toggle_theme()
        elif key == "autostart":
            current = self._is_autostart_enabled()
            self._toggle_autostart(not current)
        elif key == "close_float":
            self._close_floating_widget()
        elif key == "exit":
            self._exit_application()
        self._collapse_timer.start(self.COLLAPSE_DELAY)

    def _open_main_window(self):
        if self._main_window:
            self._main_window.show()
            self._main_window.activateWindow()
            self._main_window.raise_()

    def _toggle_theme(self):
        self.theme_toggle_requested.emit()

    def _toggle_autostart(self, checked: bool):
        self._set_autostart_registry(checked)
        self.autostart_changed.emit(checked)

    def _close_floating_widget(self):
        self.floating_close_requested.emit()
        self.hide()
    def _exit_application(self):
        QApplication.quit()

    # ------------------------------------------------------------------
    # 开机自启 — Windows 注册表 (Req 5.4)
    # ------------------------------------------------------------------
    AUTOSTART_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
    AUTOSTART_NAME = "UEToolkit"

    def _is_autostart_enabled(self) -> bool:
        try:
            import winreg
            key = winreg.OpenKey(
                winreg.HKEY_CURRENT_USER, self.AUTOSTART_KEY,
                0, winreg.KEY_READ
            )
            winreg.QueryValueEx(key, self.AUTOSTART_NAME)
            winreg.CloseKey(key)
            return True
        except Exception:
            return False

    @staticmethod
    def _set_autostart_registry(enabled: bool):
        try:
            import winreg
            key = winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                FloatingWidget.AUTOSTART_KEY,
                0, winreg.KEY_SET_VALUE
            )
            if enabled:
                exe_path = sys.executable
                winreg.SetValueEx(
                    key, FloatingWidget.AUTOSTART_NAME,
                    0, winreg.REG_SZ, f'"{exe_path}"'
                )
            else:
                try:
                    winreg.DeleteValue(key, FloatingWidget.AUTOSTART_NAME)
                except FileNotFoundError:
                    pass
            winreg.CloseKey(key)
        except Exception as e:
            logger.error(f"设置开机自启失败: {e}")

    # ------------------------------------------------------------------
    # 位置持久化 (Req 7.1 ~ 7.3)
    # ------------------------------------------------------------------
    def save_position(self):
        """保存位置和吸附边缘到配置文件"""
        try:
            settings = _load_general_settings()
            settings["floating_widget_position"] = {
                "x": self.x(),
                "y": self.y(),
                "snapped_edge": self._snapped_edge,
            }
            _save_general_settings(settings)
        except Exception as e:
            logger.error(f"保存悬浮窗位置失败: {e}")

    def restore_position(self):
        """从配置文件恢复位置"""
        try:
            settings = _load_general_settings()
            pos_data = settings.get("floating_widget_position")
            if pos_data:
                x = pos_data.get("x")
                y = pos_data.get("y")
                edge = pos_data.get("snapped_edge", "right")

                if x is not None and y is not None:
                    # 验证位置是否在屏幕范围内
                    if self._is_position_valid(x, y):
                        self.move(x, y)
                        self._snapped_edge = edge
                        # 启动后延迟自动收起（先吸附到正确边缘位置再收起）
                        QTimer.singleShot(300, self._initial_snap_and_collapse)
                        return

            # 默认位置：主屏幕右侧中间
            self._move_to_default()
            QTimer.singleShot(300, self._initial_snap_and_collapse)
        except Exception as e:
            logger.error(f"恢复悬浮窗位置失败: {e}")
            self._move_to_default()
            QTimer.singleShot(300, self._initial_snap_and_collapse)

    def _initial_snap_and_collapse(self):
        """启动时先确保吸附到边缘，然后自动收起"""
        # 先确保在正确的边缘位置
        screen = self._get_current_screen()
        if screen is None:
            return
        geo = screen.availableGeometry()

        if self._snapped_edge == "left":
            target_x = geo.left()
            target_y = max(geo.top(), min(self.y(), geo.bottom() - self.DIAMETER))
        elif self._snapped_edge == "right":
            target_x = geo.right() - self.DIAMETER
            target_y = max(geo.top(), min(self.y(), geo.bottom() - self.DIAMETER))
        else:  # top
            target_x = max(geo.left(), min(self.x(), geo.right() - self.DIAMETER))
            target_y = geo.top()

        self.move(target_x, target_y)

        # 如果鼠标不在悬浮窗上，延迟收起
        if not self.underMouse():
            QTimer.singleShot(self.COLLAPSE_DELAY, self._collapse)

    def _is_position_valid(self, x: int, y: int) -> bool:
        """检查位置是否在任意屏幕范围内"""
        point = QPoint(x + self.DIAMETER // 2, y + self.DIAMETER // 2)
        for screen in QApplication.screens():
            if screen.availableGeometry().contains(point):
                return True
        return False

    def _move_to_default(self):
        """移动到默认位置（主屏幕右侧中间）"""
        screen = QApplication.primaryScreen()
        if screen:
            geo = screen.availableGeometry()
            x = geo.right() - self.DIAMETER
            y = geo.top() + (geo.height() - self.DIAMETER) // 2
            self.move(x, y)
            self._snapped_edge = "right"

    # ------------------------------------------------------------------
    # 多显示器支持 (Req 8.1 ~ 8.3)
    # ------------------------------------------------------------------
    # _get_current_screen() 已在吸附部分实现
    # 所有吸附和收起/展开逻辑均基于 _get_current_screen().availableGeometry()
