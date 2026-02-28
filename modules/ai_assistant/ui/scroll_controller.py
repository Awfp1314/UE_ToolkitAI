# -*- coding: utf-8 -*-

"""
滚动控制器 — 管理聊天区域的自动滚动行为
"""

import time
from PyQt6.QtWidgets import QScrollArea
from PyQt6.QtCore import QTimer


class ScrollController:
    def __init__(self, scroll_area: QScrollArea, debounce_ms: int = 10):
        self.scroll_area = scroll_area
        self.auto_scroll_enabled = True
        self.debounce_ms = debounce_ms
        self._user_initiated_scroll_up = False
        self._scrollbar = None  # 由 chat_window 设置（monkey-patched scrollbar）
        
        self.scroll_debounce_timer = QTimer()
        self.scroll_debounce_timer.timeout.connect(self._do_scroll)
        self.scroll_debounce_timer.setSingleShot(True)
    
    def request_scroll_to_bottom(self):
        """请求滚动到底部（防抖动）"""
        if self._user_initiated_scroll_up:
            return
        if not self.scroll_debounce_timer.isActive():
            self.scroll_debounce_timer.start(self.debounce_ms)
    
    def on_user_scroll(self, value):
        """scrollbar valueChanged — 不做任何事，标记只由 wheelEvent 控制"""
        pass
    
    def notify_user_wheel_up(self):
        """用户向上滚轮"""
        self._user_initiated_scroll_up = True
        if self.scroll_debounce_timer.isActive():
            self.scroll_debounce_timer.stop()
        # 启用 scrollbar 阻断
        if self._scrollbar and hasattr(self._scrollbar, '_block_programmatic'):
            self._scrollbar._block_programmatic = True
    
    def notify_user_scrolled_to_bottom(self):
        """用户主动向下滚到底部"""
        self._user_initiated_scroll_up = False
        if self._scrollbar and hasattr(self._scrollbar, '_block_programmatic'):
            self._scrollbar._block_programmatic = False
    
    def _do_scroll(self):
        """执行滚动到底部"""
        if self._user_initiated_scroll_up:
            return
        
        self.scroll_area.widget().updateGeometry()
        sb = self._scrollbar or self.scroll_area.verticalScrollBar()
        
        # 使用 _allow_next 绕过阻断
        if hasattr(sb, '_allow_next'):
            sb._allow_next = True
        if hasattr(sb, '_original_setValue'):
            sb._original_setValue(sb.maximum())
        else:
            sb.setValue(sb.maximum())
    
    def force_scroll_to_bottom(self):
        """强制滚动到底部（忽略所有限制）"""
        self._user_initiated_scroll_up = False
        sb = self._scrollbar or self.scroll_area.verticalScrollBar()
        if hasattr(sb, '_block_programmatic'):
            sb._block_programmatic = False
        if hasattr(sb, '_original_setValue'):
            sb._original_setValue(sb.maximum())
        else:
            sb.setValue(sb.maximum())
    
    def enable_auto_scroll(self):
        if not self._user_initiated_scroll_up:
            self.auto_scroll_enabled = True
    
    def disable_auto_scroll(self):
        self.auto_scroll_enabled = False

    def reset_for_new_response(self):
        """新的 AI 回复开始时重置"""
        self._user_initiated_scroll_up = False
        if self._scrollbar and hasattr(self._scrollbar, '_block_programmatic'):
            self._scrollbar._block_programmatic = False
