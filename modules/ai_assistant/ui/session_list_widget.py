# -*- coding: utf-8 -*-

"""
会话列表侧边栏 - 浮动抽屉式

功能：
- 新建对话
- 会话列表（按时间分组：今天、昨天、更早）
- 切换、删除、重命名会话
- 可收起/展开
"""

import time
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QScrollArea, QFrame, QLineEdit,
    QSizePolicy, QMenu, QApplication,
)
from PyQt6.QtCore import Qt, pyqtSignal, QPropertyAnimation, QEasingCurve, QSize
from PyQt6.QtGui import QCursor


class SessionItemWidget(QWidget):
    """单个会话项"""

    clicked = pyqtSignal(str)          # session_id
    delete_requested = pyqtSignal(str)  # session_id
    rename_requested = pyqtSignal(str, str)  # session_id, new_title

    def __init__(self, session_id: str, title: str, is_active: bool = False,
                 theme: str = "dark", parent=None):
        super().__init__(parent)
        self.session_id = session_id
        self._title = title
        self._is_active = is_active
        self._theme = theme
        self._editing = False
        self.setFixedHeight(38)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._init_ui()
        self._apply_style()

    def _init_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 4, 12, 4)  # 增加右边距
        layout.setSpacing(8)

        # 标题
        self.title_label = QLabel(self._title)
        self.title_label.setObjectName("SessionItemTitle")
        # 设置最大宽度，避免占据所有空间
        self.title_label.setMaximumWidth(180)
        # 文本过长时显示省略号
        self.title_label.setTextFormat(Qt.TextFormat.PlainText)
        from PyQt6.QtGui import QFontMetrics
        self.title_label.setWordWrap(False)
        layout.addWidget(self.title_label)

        # 编辑框（默认隐藏）
        self.edit_input = QLineEdit()
        self.edit_input.setObjectName("SessionItemEdit")
        self.edit_input.setFixedHeight(26)
        self.edit_input.hide()
        self.edit_input.returnPressed.connect(self._finish_rename)
        layout.addWidget(self.edit_input)

        layout.addStretch()  # 添加弹性空间

        # 更多按钮（hover 时显示）
        self.more_btn = QPushButton("⋯")
        self.more_btn.setObjectName("SessionMoreBtn")
        self.more_btn.setFixedSize(28, 28)  # 增大按钮尺寸
        self.more_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.more_btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.more_btn.clicked.connect(self._show_context_menu)
        self.more_btn.hide()
        layout.addWidget(self.more_btn)

    def _apply_style(self):
        is_dark = self._theme == "dark"
        if self._is_active:
            bg = "rgba(255,255,255,0.12)" if is_dark else "rgba(0,0,0,0.08)"
            text_color = "#ffffff" if is_dark else "#1a1a1a"
        else:
            bg = "transparent"
            text_color = "rgba(255,255,255,0.7)" if is_dark else "rgba(0,0,0,0.65)"

        hover_bg = "rgba(255,255,255,0.08)" if is_dark else "rgba(0,0,0,0.05)"

        self.setStyleSheet(f"""
            SessionItemWidget {{
                background: {bg};
                border-radius: 8px;
            }}
            SessionItemWidget:hover {{
                background: {hover_bg if not self._is_active else bg};
            }}
        """)
        self.title_label.setStyleSheet(f"""
            color: {text_color};
            font-size: 13px;
            background: transparent;
        """)
        # 设置文本省略
        from PyQt6.QtGui import QFontMetrics
        fm = self.title_label.fontMetrics()
        elided_text = fm.elidedText(self._title, Qt.TextElideMode.ElideRight, 180)
        self.title_label.setText(elided_text)
        self.title_label.setToolTip(self._title)  # 完整标题显示在 tooltip 中
        
        self.edit_input.setStyleSheet(f"""
            background: {'#2a2a2a' if is_dark else '#ffffff'};
            color: {text_color};
            border: 1px solid {'#555' if is_dark else '#ccc'};
            border-radius: 4px;
            padding: 2px 6px;
            font-size: 13px;
        """)
        self.more_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent;
                color: {'rgba(255,255,255,0.6)' if is_dark else 'rgba(0,0,0,0.5)'};
                border: none;
                font-size: 18px;
                border-radius: 4px;
            }}
            QPushButton:hover {{
                background: {'rgba(255,255,255,0.15)' if is_dark else 'rgba(0,0,0,0.1)'};
                color: {'rgba(255,255,255,0.9)' if is_dark else 'rgba(0,0,0,0.8)'};
            }}
        """)

    def set_active(self, active: bool):
        self._is_active = active
        self._apply_style()

    def set_theme(self, theme: str):
        self._theme = theme
        self._apply_style()

    def enterEvent(self, event):
        if not self._editing:
            self.more_btn.show()
            self.more_btn.raise_()  # 确保按钮在最上层
        super().enterEvent(event)

    def leaveEvent(self, event):
        if not self._editing:
            self.more_btn.hide()
        super().leaveEvent(event)

    def mousePressEvent(self, event):
        if not self._editing:
            self.clicked.emit(self.session_id)
        super().mousePressEvent(event)

    def _show_context_menu(self):
        menu = QMenu(self)
        is_dark = self._theme == "dark"
        menu.setStyleSheet(f"""
            QMenu {{
                background: {'#2a2a2a' if is_dark else '#ffffff'};
                color: {'#e0e0e0' if is_dark else '#333333'};
                border: 1px solid {'#404040' if is_dark else '#d0d0d0'};
                border-radius: 6px;
                padding: 4px;
            }}
            QMenu::item {{
                padding: 6px 20px;
                border-radius: 4px;
            }}
            QMenu::item:selected {{
                background: {'rgba(255,255,255,0.1)' if is_dark else 'rgba(0,0,0,0.06)'};
            }}
        """)

        rename_action = menu.addAction("✏️ 重命名")
        delete_action = menu.addAction("🗑️ 删除")

        action = menu.exec(QCursor.pos())
        if action == rename_action:
            self._start_rename()
        elif action == delete_action:
            self.delete_requested.emit(self.session_id)

    def _start_rename(self):
        self._editing = True
        self.title_label.hide()
        self.more_btn.hide()
        self.edit_input.setText(self._title)
        self.edit_input.show()
        self.edit_input.setFocus()
        self.edit_input.selectAll()

    def _finish_rename(self):
        new_title = self.edit_input.text().strip()
        self._editing = False
        self.edit_input.hide()
        self.title_label.show()
        if new_title and new_title != self._title:
            self._title = new_title
            self.title_label.setText(new_title)
            self.rename_requested.emit(self.session_id, new_title)


class SessionListWidget(QWidget):
    """会话列表侧边栏（浮动抽屉）"""

    session_switched = pyqtSignal(str)    # session_id
    new_session_requested = pyqtSignal()
    session_deleted = pyqtSignal(str)     # session_id
    session_renamed = pyqtSignal(str, str)  # session_id, new_title

    PANEL_WIDTH = 240

    def __init__(self, theme: str = "dark", parent=None):
        super().__init__(parent)
        self._theme = theme
        self._session_items: dict = {}  # session_id -> SessionItemWidget
        self._current_session_id = None
        self._bg_color = "#1e1e1e" if theme == "dark" else "#f5f5f5"
        self.setFixedWidth(self.PANEL_WIDTH)
        self._init_ui()
        self._apply_style()

    def paintEvent(self, event):
        """手动绘制不透明背景（WA_TranslucentBackground 下 stylesheet 背景不生效）"""
        from PyQt6.QtGui import QPainter, QColor
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.fillRect(self.rect(), QColor(self._bg_color))
        painter.end()
        super().paintEvent(event)

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 12)
        layout.setSpacing(8)

        # 顶部行：右侧关闭按钮
        from PyQt6.QtWidgets import QHBoxLayout
        top_row = QHBoxLayout()
        top_row.setContentsMargins(0, 0, 0, 0)
        top_row.addStretch()
        self.close_btn = QPushButton("☰")
        self.close_btn.setFixedSize(32, 32)
        self.close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.close_btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.close_btn.setToolTip("收起侧边栏")
        top_row.addWidget(self.close_btn)
        layout.addLayout(top_row)

        # 新建对话按钮
        self.new_chat_btn = QPushButton("＋  新对话")
        self.new_chat_btn.setObjectName("NewChatButton")
        self.new_chat_btn.setFixedHeight(38)
        self.new_chat_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.new_chat_btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.new_chat_btn.clicked.connect(self.new_session_requested.emit)
        layout.addWidget(self.new_chat_btn)

        layout.addSpacing(4)

        # 会话列表滚动区域
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.scroll_area.setObjectName("SessionScrollArea")

        self.list_container = QWidget()
        self.list_layout = QVBoxLayout(self.list_container)
        self.list_layout.setContentsMargins(0, 0, 0, 0)
        self.list_layout.setSpacing(2)
        self.list_layout.addStretch()

        self.scroll_area.setWidget(self.list_container)
        layout.addWidget(self.scroll_area, 1)

    def _apply_style(self):
        is_dark = self._theme == "dark"
        bg = "#1e1e1e" if is_dark else "#f5f5f5"
        border_color = "#333333" if is_dark else "#e0e0e0"
        btn_bg = "rgba(255,255,255,0.08)" if is_dark else "rgba(0,0,0,0.05)"
        btn_hover = "rgba(255,255,255,0.15)" if is_dark else "rgba(0,0,0,0.1)"
        btn_text = "#e0e0e0" if is_dark else "#333333"

        # 更新 paintEvent 用的背景色
        self._bg_color = bg

        self.setStyleSheet(f"""
            SessionListWidget {{
                border-right: 1px solid {border_color};
            }}
        """)
        self.new_chat_btn.setStyleSheet(f"""
            QPushButton {{
                background: {btn_bg};
                color: {btn_text};
                border: 1px dashed {'#555' if is_dark else '#ccc'};
                border-radius: 8px;
                font-size: 14px;
                font-weight: 500;
            }}
            QPushButton:hover {{
                background: {btn_hover};
                border-style: solid;
            }}
        """)
        self.close_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent;
                color: {btn_text};
                border: none;
                border-radius: 6px;
                font-size: 16px;
            }}
            QPushButton:hover {{
                background: {btn_hover};
            }}
        """)
        self.scroll_area.setStyleSheet(f"""
            QScrollArea {{
                background: transparent;
                border: none;
            }}
            QWidget {{
                background: transparent;
            }}
            QScrollBar:vertical {{
                width: 4px;
                background: transparent;
            }}
            QScrollBar::handle:vertical {{
                background: {'rgba(255,255,255,0.15)' if is_dark else 'rgba(0,0,0,0.12)'};
                border-radius: 2px;
                min-height: 30px;
            }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
                height: 0px;
            }}
        """)

    def set_theme(self, theme: str):
        self._theme = theme
        self._apply_style()
        for item in self._session_items.values():
            item.set_theme(theme)

    def refresh_sessions(self, sessions, current_session_id: str = None):
        """刷新会话列表"""
        self._current_session_id = current_session_id

        # 清空旧的
        for item in self._session_items.values():
            self.list_layout.removeWidget(item)
            item.deleteLater()
        self._session_items.clear()

        # 移除旧的分组标签
        while self.list_layout.count() > 1:  # 保留最后的 stretch
            item = self.list_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        if not sessions:
            return

        # 按时间分组
        now = time.time()
        today_start = now - (now % 86400)  # 今天 00:00
        yesterday_start = today_start - 86400

        groups = {"今天": [], "昨天": [], "更早": []}
        for s in sessions:
            if s.updated_at >= today_start:
                groups["今天"].append(s)
            elif s.updated_at >= yesterday_start:
                groups["昨天"].append(s)
            else:
                groups["更早"].append(s)

        insert_idx = 0
        for group_name in ["今天", "昨天", "更早"]:
            group_sessions = groups[group_name]
            if not group_sessions:
                continue

            # 分组标签
            label = QLabel(group_name)
            label.setObjectName("SessionGroupLabel")
            is_dark = self._theme == "dark"
            label.setStyleSheet(f"""
                color: {'rgba(255,255,255,0.4)' if is_dark else 'rgba(0,0,0,0.35)'};
                font-size: 11px;
                font-weight: 600;
                padding: 8px 12px 4px 12px;
                background: transparent;
            """)
            self.list_layout.insertWidget(insert_idx, label)
            insert_idx += 1

            for s in group_sessions:
                is_active = (s.session_id == current_session_id)
                item = SessionItemWidget(
                    session_id=s.session_id,
                    title=s.title,
                    is_active=is_active,
                    theme=self._theme,
                )
                item.clicked.connect(self._on_item_clicked)
                item.delete_requested.connect(self.session_deleted.emit)
                item.rename_requested.connect(self.session_renamed.emit)

                self._session_items[s.session_id] = item
                self.list_layout.insertWidget(insert_idx, item)
                insert_idx += 1

    def set_active_session(self, session_id: str):
        """高亮指定会话"""
        self._current_session_id = session_id
        for sid, item in self._session_items.items():
            item.set_active(sid == session_id)

    def _on_item_clicked(self, session_id: str):
        if session_id != self._current_session_id:
            self.set_active_session(session_id)
            self.session_switched.emit(session_id)
