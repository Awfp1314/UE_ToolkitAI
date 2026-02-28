# -*- coding: utf-8 -*-

"""
AI助手聊天窗口 - UI 层

仅负责：
- 组件初始化与布局
- 事件处理器
- UI 更新（气泡、滚动、主题）

业务逻辑委托给 ChatController。
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QScrollArea, QScrollBar, QLabel,
    QPushButton, QSizePolicy, QApplication,
)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QEvent
from modules.base_module_widget import BaseModuleWidget
from .chat_input import ChatInputBox
from .user_message_bubble import UserMessageBubble
from .ai_message_bubble import AIMessageBubble
from .thinking_indicator import ThinkingIndicator
from .scroll_controller import ScrollController
from .session_list_widget import SessionListWidget
from ..logic.chat_controller import ChatController


class _BlockableScrollBar(QScrollBar):
    """可阻断的 ScrollBar — 当 block_programmatic 为 True 时，
    只允许来自 ScrollController 的 setValue 调用"""
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.block_programmatic = False
        self._allow_next_set = False  # ScrollController 设置此标记来允许一次 setValue
    
    def setValue(self, value):
        if self.block_programmatic and not self._allow_next_set:
            return  # 吞掉
        self._allow_next_set = False
        super().setValue(value)
    
    def force_set_value(self, value):
        """由 ScrollController 调用，绕过阻断"""
        self._allow_next_set = True
        self.setValue(value)


class _ChatScrollArea(QScrollArea):
    """自定义 QScrollArea，拦截滚轮事件"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._scroll_controller = None
    
    def set_scroll_controller(self, controller):
        self._scroll_controller = controller
    
    def wheelEvent(self, event):
        """拦截滚轮事件"""
        delta = event.angleDelta().y()
        if self._scroll_controller:
            if delta > 0:
                self._scroll_controller.notify_user_wheel_up()
            elif delta < 0:
                super().wheelEvent(event)
                scrollbar = self.verticalScrollBar()
                if scrollbar.value() >= scrollbar.maximum() - 50:
                    self._scroll_controller.notify_user_scrolled_to_bottom()
                return
        super().wheelEvent(event)


class ChatWindow(BaseModuleWidget):
    """AI助手聊天窗口（UI 层）"""

    message_sent = pyqtSignal(str)  # 发送消息信号

    def __init__(self, parent=None):
        super().__init__(parent)
        # 从样式系统获取当前实际主题
        self.current_theme = self._get_current_theme()
        self.user_bubbles = []   # 所有用户消息气泡引用
        self.ai_bubbles = []     # 所有AI消息气泡引用
        self.current_ai_bubble = None  # 当前正在接收流式输出的AI气泡

        # 动态加载：全量消息列表 + 当前渲染窗口
        self._all_messages = []       # 完整消息列表（从持久化加载）
        self._rendered_start = 0      # 已渲染的最早消息在 _all_messages 中的索引
        self._LOAD_BATCH = 15         # 向上滚动时每次加载的条数
        self._INITIAL_LOAD = 30       # 初始加载条数
        self._is_loading_more = False # 防止重复触发加载
        self._scroll_load_connected = False  # 是否已连接滚动加载监听

        # 思考动画
        self.thinking_indicator = None
        self.thinking_wrapper = None

        # 滚动控制器
        self.scroll_controller = None

        # ===== 业务逻辑控制器 =====
        self.controller = ChatController(parent=self)
        self._connect_controller_signals()

        self.init_ui()

        # 后台预初始化 ContextManager（避免第一次发消息卡 UI）
        self.controller.pre_initialize_async()

        # 恢复上次的聊天记录到 UI
        self._restore_chat_history()

    def _connect_controller_signals(self):
        """连接控制器信号到 UI 更新方法"""
        self.controller.chunk_received.connect(self._on_chunk_received)
        self.controller.request_finished.connect(self._on_request_finished)
        self.controller.error_occurred.connect(self._on_error_occurred)
        self.controller.tool_started.connect(self._on_tool_start)
        self.controller.tool_completed.connect(self._on_tool_complete)
        self.controller.session_title_updated.connect(self._on_session_title_updated)

    def _restore_chat_history(self):
        """从持久化存储恢复聊天气泡（只渲染最近 N 条，滚动时动态加载更多）"""
        try:
            messages = self.controller.message_manager.get_persisted_messages()
            if not messages:
                return

            # 保存完整消息列表
            self._all_messages = messages

            # 找到最后一条 assistant 消息的索引
            last_assistant_idx = -1
            for i in range(len(messages) - 1, -1, -1):
                if messages[i].get("role") == "assistant":
                    last_assistant_idx = i
                    break

            # 只渲染最近 INITIAL_LOAD 条
            total = len(messages)
            start_idx = max(0, total - self._INITIAL_LOAD)
            self._rendered_start = start_idx

            # 监听滚动范围变化，恢复期间自动到底部
            scrollbar = self.scroll_area.verticalScrollBar()
            self._auto_scroll_on_range_change = True
            scrollbar.rangeChanged.connect(self._on_range_changed_scroll)

            for i in range(start_idx, total):
                msg = messages[i]
                is_last_assistant = (i == last_assistant_idx)
                self._render_history_bubble(msg, is_last_assistant=is_last_assistant)

            # 延迟断开自动滚动 + 连接动态加载监听
            QTimer.singleShot(800, self._finish_initial_restore)

            loaded = total - start_idx
            remaining = start_idx
            print(f"[INFO] 已渲染 {loaded} 条气泡（共 {total} 条，{remaining} 条可向上滚动加载）")
        except Exception as e:
            print(f"[WARNING] 恢复聊天记录 UI 失败: {e}")

    def _finish_initial_restore(self):
        """初始恢复完成后：断开自动滚动，连接动态加载"""
        self._stop_auto_scroll_on_range()
        self._connect_scroll_load_listener()

    def _on_range_changed_scroll(self, min_val, max_val):
        """滚动范围变化时自动到底部（恢复历史期间）"""
        if getattr(self, '_auto_scroll_on_range_change', False):
            scrollbar = self.scroll_area.verticalScrollBar()
            scrollbar.setValue(max_val)

    def _stop_auto_scroll_on_range(self):
        """断开自动滚动，恢复正常滚动行为"""
        self._auto_scroll_on_range_change = False
        try:
            scrollbar = self.scroll_area.verticalScrollBar()
            scrollbar.rangeChanged.disconnect(self._on_range_changed_scroll)
        except (TypeError, RuntimeError):
            pass

    def _connect_scroll_load_listener(self):
        """连接滚动条监听，用户接近顶部时动态加载更多旧消息"""
        if self._scroll_load_connected:
            return
        scrollbar = self.scroll_area.verticalScrollBar()
        scrollbar.valueChanged.connect(self._on_scroll_check_load_more)
        self._scroll_load_connected = True

    def _disconnect_scroll_load_listener(self):
        """断开滚动加载监听"""
        if not self._scroll_load_connected:
            return
        try:
            scrollbar = self.scroll_area.verticalScrollBar()
            scrollbar.valueChanged.disconnect(self._on_scroll_check_load_more)
        except (TypeError, RuntimeError):
            pass
        self._scroll_load_connected = False

    def _on_scroll_check_load_more(self, value):
        """滚动位置变化时检查是否需要加载更多旧消息"""
        if self._is_loading_more:
            return
        if self._rendered_start <= 0:
            return  # 已经全部加载了

        scrollbar = self.scroll_area.verticalScrollBar()
        # 当滚动到顶部附近（距顶部 200px 以内）时触发加载
        if value < 200:
            self._load_older_messages()

    def _load_older_messages(self):
        """向上加载更多旧消息，并补偿滚动位置"""
        if self._is_loading_more or self._rendered_start <= 0:
            return

        self._is_loading_more = True

        try:
            scrollbar = self.scroll_area.verticalScrollBar()
            # 记录当前滚动位置和内容高度
            old_max = scrollbar.maximum()
            old_value = scrollbar.value()

            # 计算要加载的范围
            new_start = max(0, self._rendered_start - self._LOAD_BATCH)
            messages_to_load = self._all_messages[new_start:self._rendered_start]

            if not messages_to_load:
                self._is_loading_more = False
                return

            # 找最后一条 assistant 的全局索引（用于 regenerate 按钮）
            last_assistant_idx = -1
            for i in range(len(self._all_messages) - 1, -1, -1):
                if self._all_messages[i].get("role") == "assistant":
                    last_assistant_idx = i
                    break

            # 逐条插入到顶部（按时间顺序，最早的在最上面）
            for i, msg in enumerate(messages_to_load):
                global_idx = new_start + i
                is_last_assistant = (global_idx == last_assistant_idx)
                self._render_history_bubble(msg, insert_at_top=True, is_last_assistant=is_last_assistant)

            self._rendered_start = new_start

            # 补偿滚动位置：新内容插入顶部后，scrollbar.maximum() 会增大
            # 需要把 scrollbar 值增加相应的差值，保持视觉位置不变
            def _compensate_scroll():
                new_max = scrollbar.maximum()
                height_diff = new_max - old_max
                target_value = old_value + height_diff

                # 绕过 monkey-patched setValue 的阻断
                if hasattr(scrollbar, '_original_setValue'):
                    scrollbar._original_setValue(target_value)
                else:
                    scrollbar.setValue(target_value)

                self._is_loading_more = False

                remaining = self._rendered_start
                print(f"[INFO] 动态加载了 {len(messages_to_load)} 条旧消息，还剩 {remaining} 条可加载")

            # 等 Qt 布局更新后再补偿
            QTimer.singleShot(0, _compensate_scroll)

        except Exception as e:
            self._is_loading_more = False
            print(f"[WARNING] 动态加载旧消息失败: {e}")

    def _render_history_bubble(self, msg, insert_at_top=False, is_last_assistant=False):
        """渲染单条历史消息气泡"""
        role = msg.get("role")
        content = msg.get("content", "")
        if not content:
            return

        if role == "user":
            display = content.split("\n\n[附加")[0].strip() or content
            bubble = UserMessageBubble(display, theme=self.current_theme)
            self.user_bubbles.append(bubble)
        elif role == "assistant":
            bubble = AIMessageBubble(content, theme=self.current_theme, show_regenerate=is_last_assistant)
            if is_last_assistant:
                bubble.regenerate_clicked.connect(self.on_regenerate_response)
            self.ai_bubbles.append(bubble)
        else:
            return

        if insert_at_top:
            self.message_layout.insertWidget(0, bubble, 0)
        else:
            self.message_layout.insertWidget(
                self.message_layout.count() - 1, bubble, 0
            )

        # 历史消息直接显示操作按钮（不调 finalize 避免二次渲染闪烁）
        if role == "assistant" and hasattr(bubble, 'action_buttons_container'):
            bubble.action_buttons_container.show()

    # ------------------------------------------------------------------
    # 主题
    # ------------------------------------------------------------------

    def _get_current_theme(self) -> str:
        """从样式系统获取当前主题"""
        try:
            from core.utils.style_system import get_current_theme
            theme_name = get_current_theme()
            if theme_name and "light" in theme_name.lower():
                return "light"
            return "dark"
        except Exception:
            return "dark"

    # ------------------------------------------------------------------
    # 逻辑层引用（委托给控制器）
    # ------------------------------------------------------------------

    def set_logic_references(self, asset_manager_logic=None, config_tool_logic=None, site_recommendations_logic=None):
        """设置其他模块的逻辑层引用（委托给控制器）"""
        self.controller.set_logic_references(
            asset_manager_logic=asset_manager_logic,
            config_tool_logic=config_tool_logic,
            site_recommendations_logic=site_recommendations_logic,
        )

    def set_asset_manager_logic(self, asset_manager_logic):
        """向后兼容：单独设置 asset_manager 逻辑层引用"""
        self.controller.set_logic_references(
            asset_manager_logic=asset_manager_logic,
            config_tool_logic=self.controller.config_tool_logic,
            site_recommendations_logic=self.controller.site_recommendations_logic,
        )

    def set_config_tool_logic(self, config_tool_logic):
        """向后兼容：单独设置 config_tool 逻辑层引用"""
        self.controller.set_logic_references(
            asset_manager_logic=self.controller.asset_manager_logic,
            config_tool_logic=config_tool_logic,
            site_recommendations_logic=self.controller.site_recommendations_logic,
        )

    def set_site_recommendations_logic(self, site_recommendations_logic):
        """向后兼容：单独设置 site_recommendations 逻辑层引用"""
        self.controller.set_logic_references(
            asset_manager_logic=self.controller.asset_manager_logic,
            config_tool_logic=self.controller.config_tool_logic,
            site_recommendations_logic=site_recommendations_logic,
        )

    # ------------------------------------------------------------------
    # 便捷属性（向后兼容：外部代码可能直接访问这些属性）
    # ------------------------------------------------------------------

    @property
    def asset_manager_logic(self):
        return self.controller.asset_manager_logic

    @property
    def conversation_history(self):
        return self.controller.conversation_history

    @property
    def context_manager(self):
        return self.controller.context_manager

    @property
    def current_api_client(self):
        return self.controller.current_api_client

    @current_api_client.setter
    def current_api_client(self, value):
        self.controller.current_api_client = value

    # ------------------------------------------------------------------
    # UI 初始化
    # ------------------------------------------------------------------

    def init_ui(self):
        """初始化UI"""
        self.setMinimumHeight(600)
        self.setMinimumWidth(600)
        self.setMaximumWidth(990)
        self.setSizePolicy(QSizePolicy.Policy.MinimumExpanding, QSizePolicy.Policy.Expanding)

        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        # ===== 中间区域：聊天区 =====
        middle_widget = QWidget()
        middle_layout = QVBoxLayout(middle_widget)
        middle_layout.setContentsMargins(0, 0, 0, 0)
        middle_layout.setSpacing(0)

        # 侧边栏（创建但不加入布局，由外层 wrapper 管理位置）
        self._sidebar_visible = False
        self.session_sidebar = SessionListWidget(theme=self.current_theme)
        self.session_sidebar.session_switched.connect(self._on_session_switched)
        self.session_sidebar.new_session_requested.connect(self._on_new_session)
        self.session_sidebar.session_deleted.connect(self._on_session_deleted)
        self.session_sidebar.session_renamed.connect(self._on_session_renamed)
        self.session_sidebar.close_btn.clicked.connect(self._hide_sidebar)
        self.session_sidebar.setVisible(False)

        # 消息滚动区域（使用自定义子类拦截滚轮事件）
        self.scroll_area = _ChatScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll_area.setObjectName("ChatScrollArea")
        self.scroll_area.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        from core.utils.auto_hide_scrollbar import enable_auto_hide_scrollbar
        enable_auto_hide_scrollbar(self.scroll_area)

        self.scroll_controller = ScrollController(self.scroll_area, debounce_ms=100)
        self.scroll_area.set_scroll_controller(self.scroll_controller)

        # ⚡ Monkey-patch scrollbar.setValue 来阻断 Qt 内部的自动滚动
        scrollbar = self.scroll_area.verticalScrollBar()
        scrollbar._original_setValue = scrollbar.setValue
        scrollbar._block_programmatic = False
        scrollbar._allow_next = False
        
        def _patched_setValue(value, _sb=scrollbar):
            if _sb._block_programmatic and not _sb._allow_next:
                return  # 吞掉 Qt 内部的 setValue 调用
            _sb._allow_next = False
            _sb._original_setValue(value)
        
        scrollbar.setValue = _patched_setValue
        self.scroll_controller._scrollbar = scrollbar  # 让 controller 能访问
        
        scrollbar.valueChanged.connect(self.scroll_controller.on_user_scroll)

        self.message_container = QWidget()
        self.message_container.setObjectName("ChatMessageContainer")
        self.message_container.installEventFilter(self)
        self.message_layout = QVBoxLayout(self.message_container)
        self.message_layout.setContentsMargins(20, 20, 30, 20)
        self.message_layout.setSpacing(40)
        self.message_layout.addStretch()

        self.scroll_area.setWidget(self.message_container)
        middle_layout.addWidget(self.scroll_area, 1)

        middle_layout.addSpacing(5)

        # 输入框
        input_container = QWidget()
        input_container.setObjectName("ChatInputWrapper")
        input_container.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        input_container_layout = QVBoxLayout(input_container)
        input_container_layout.setContentsMargins(0, 0, 0, 0)
        input_container_layout.setSpacing(0)

        self.input_box = ChatInputBox()
        self.input_box.send_signal.connect(self.send_message)
        self.input_box.add_asset_signal.connect(self._on_add_asset)
        self.input_box.add_config_signal.connect(self._on_add_config)
        input_container_layout.addWidget(self.input_box)

        middle_layout.addWidget(input_container, 0)

        root_layout.addWidget(middle_widget, 1)

        # 样式和标题在外层 wrapper 创建工具栏后调用

    # ------------------------------------------------------------------
    # 侧边栏 & 会话管理
    # ------------------------------------------------------------------

    def _apply_toolbar_style(self):
        """应用工具栏样式"""
        if not hasattr(self, 'sidebar_toggle_btn'):
            return
        is_dark = self.current_theme == "dark"
        text_color = "#e0e0e0" if is_dark else "#333333"
        btn_hover = "rgba(255,255,255,0.1)" if is_dark else "rgba(0,0,0,0.06)"

        btn_style = f"""
            QPushButton {{
                background: transparent;
                color: {text_color};
                border: none;
                border-radius: 6px;
                font-size: 16px;
            }}
            QPushButton:hover {{
                background: {btn_hover};
            }}
        """
        self.sidebar_toggle_btn.setStyleSheet(btn_style)

    def _update_session_title_label(self):
        """更新工具栏上的当前会话标题"""
        if not hasattr(self, 'session_title_label'):
            return
        session = self.controller.session_manager.get_current_session()
        if session:
            self.session_title_label.setText(session.title)
        else:
            self.session_title_label.setText("")

    def _on_session_title_updated(self, session_id: str, new_title: str):
        """AI 生成标题后更新 UI（从后台线程通过信号调用，线程安全）"""
        # 更新工具栏标题
        if session_id == self.controller.session_manager.current_session_id:
            self._update_session_title_label()

        # 如果侧边栏可见，刷新列表
        if self._sidebar_visible:
            sessions = self.controller.session_manager.get_sessions()
            current_id = self.controller.session_manager.current_session_id
            self.session_sidebar.refresh_sessions(sessions, current_id)

    def _toggle_sidebar(self):
        """切换侧边栏显示/隐藏"""
        if self._sidebar_visible:
            self._hide_sidebar()
        else:
            self._show_sidebar()

    def _position_sidebar(self):
        """定位浮动侧边栏：紧贴 wrapper 左侧，覆盖整个高度"""
        if not hasattr(self, '_wrapper'):
            return
        self.session_sidebar.setGeometry(
            0, 0,
            self.session_sidebar.PANEL_WIDTH, self._wrapper.height()
        )

    def _position_new_chat_btn(self):
        """定位浮动新对话按钮到 wrapper 右上角"""
        if not hasattr(self, '_wrapper') or not hasattr(self, 'new_chat_btn'):
            return
        btn = self.new_chat_btn
        btn.adjustSize()
        x = self._wrapper.width() - btn.width() - 8
        btn.move(max(0, x), 4)

    def _show_sidebar(self):
        """展开侧边栏（覆盖式滑入动画）"""
        self._sidebar_visible = True

        # 刷新会话列表
        sessions = self.controller.session_manager.get_sessions()
        current_id = self.controller.session_manager.current_session_id
        self.session_sidebar.refresh_sessions(sessions, current_id)

        # 隐藏外部 ☰ 按钮
        if hasattr(self, 'sidebar_toggle_btn'):
            self.sidebar_toggle_btn.setVisible(False)

        # 定位并显示
        self._position_sidebar()
        self.session_sidebar.setFixedWidth(self.session_sidebar.PANEL_WIDTH)
        self.session_sidebar.setVisible(True)
        self.session_sidebar.raise_()

        pw = self.session_sidebar.PANEL_WIDTH
        from PyQt6.QtCore import QPropertyAnimation, QEasingCurve, QPoint

        self._sidebar_anim = QPropertyAnimation(self.session_sidebar, b"pos")
        self._sidebar_anim.setDuration(220)
        self._sidebar_anim.setStartValue(QPoint(-pw, 0))
        self._sidebar_anim.setEndValue(QPoint(0, 0))
        self._sidebar_anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._sidebar_anim.start()

    def _hide_sidebar(self):
        """收起侧边栏（覆盖式滑出动画）"""
        self._sidebar_visible = False

        pw = self.session_sidebar.PANEL_WIDTH
        from PyQt6.QtCore import QPropertyAnimation, QEasingCurve, QPoint

        def _on_hide_finished():
            self.session_sidebar.setVisible(False)
            # 显示外部 ☰ 按钮
            if hasattr(self, 'sidebar_toggle_btn'):
                self.sidebar_toggle_btn.setVisible(True)

        self._sidebar_anim = QPropertyAnimation(self.session_sidebar, b"pos")
        self._sidebar_anim.setDuration(220)
        self._sidebar_anim.setStartValue(QPoint(0, 0))
        self._sidebar_anim.setEndValue(QPoint(-pw, 0))
        self._sidebar_anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._sidebar_anim.finished.connect(_on_hide_finished)
        self._sidebar_anim.start()

    def _on_new_session(self):
        """新建对话"""
        self.controller.session_manager.create_session()

        new_id = self.controller.session_manager.current_session_id
        self.controller.message_manager.switch_session(new_id)

        self._clear_all_bubbles()
        self._update_session_title_label()

        # 刷新侧边栏高亮
        if self._sidebar_visible:
            sessions = self.controller.session_manager.get_sessions()
            self.session_sidebar.refresh_sessions(sessions, new_id)

        self.input_box.setFocus()

    def _on_session_switched(self, session_id: str):
        """切换到指定会话"""
        if session_id == self.controller.session_manager.current_session_id:
            return

        self.controller.message_manager.switch_session(session_id)

        self._clear_all_bubbles()
        self._restore_chat_history()
        self._update_session_title_label()

        # 更新侧边栏高亮
        self.session_sidebar.set_active_session(session_id)

    def _on_session_deleted(self, session_id: str):
        """删除会话"""
        was_current = (session_id == self.controller.session_manager.current_session_id)
        self.controller.session_manager.delete_session(session_id)

        if was_current:
            # 切换到新的当前会话
            new_id = self.controller.session_manager.current_session_id
            self.controller.message_manager.switch_session(new_id)
            self._clear_all_bubbles()
            self._restore_chat_history()
            self._update_session_title_label()

        # 刷新侧边栏列表
        sessions = self.controller.session_manager.get_sessions()
        current_id = self.controller.session_manager.current_session_id
        self.session_sidebar.refresh_sessions(sessions, current_id)

    def _on_session_renamed(self, session_id: str, new_title: str):
        """重命名会话"""
        self.controller.session_manager.rename_session(session_id, new_title)
        self._update_session_title_label()

    def _clear_all_bubbles(self):
        """清空所有消息气泡"""
        # 停止正在进行的 API 请求
        if self.controller.current_api_client:
            try:
                self.controller.current_api_client.stop()
            except Exception:
                pass
            self.controller.current_api_client = None
            self.controller.current_coordinator = None

        self._hide_thinking_indicator()
        self.current_ai_bubble = None

        # 断开动态加载监听
        self._disconnect_scroll_load_listener()

        # 重置动态加载状态
        self._all_messages = []
        self._rendered_start = 0
        self._is_loading_more = False

        # 清空气泡引用
        self.user_bubbles.clear()
        self.ai_bubbles.clear()

        # 移除所有 widget（保留最后的 stretch）
        while self.message_layout.count() > 1:
            item = self.message_layout.takeAt(0)
            if item and item.widget():
                item.widget().deleteLater()

    # ------------------------------------------------------------------
    # 发送消息（入口）
    # ------------------------------------------------------------------

    def send_message(self, message: str, attachments: list = None):
        """发送消息并触发AI回复"""
        attachments = attachments or []

        # 构建消息（委托给控制器）
        display_message, full_message = self.controller.build_full_message(message, attachments)

        if not display_message and not full_message:
            return

        # UI：强制启用自动滚动
        if self.scroll_controller:
            self.scroll_controller.force_scroll_to_bottom()

        # UI：添加用户消息气泡
        self.add_user_message(display_message)

        # UI：显示思考动画
        self._show_thinking_indicator()

        # 业务逻辑：发送消息（控制器处理历史、API 调用等）
        self.controller.send_message(full_message)

        # 更新会话标题（第一条消息时会自动生成标题）
        self._update_session_title_label()

    # ------------------------------------------------------------------
    # 思考动画
    # ------------------------------------------------------------------

    def _show_thinking_indicator(self):
        """显示思考动画"""
        if self.thinking_indicator:
            return

        self.thinking_indicator = ThinkingIndicator(theme=self.current_theme)
        self.thinking_wrapper = QWidget()
        thinking_layout = QVBoxLayout(self.thinking_wrapper)
        thinking_layout.setContentsMargins(20, 12, 20, 12)
        thinking_layout.addWidget(self.thinking_indicator, 0, Qt.AlignmentFlag.AlignLeft)

        self.message_layout.insertWidget(
            self.message_layout.count() - 1,
            self.thinking_wrapper,
        )

        QTimer.singleShot(10, self.scroll_to_bottom)

    def _hide_thinking_indicator(self):
        """隐藏思考动画"""
        if self.thinking_indicator:
            self.thinking_indicator.stop()
            self.thinking_indicator.deleteLater()
            self.thinking_indicator = None

        if self.thinking_wrapper:
            self.thinking_wrapper.deleteLater()
            self.thinking_wrapper = None

    # ------------------------------------------------------------------
    # 控制器信号回调（UI 更新）
    # ------------------------------------------------------------------

    def _on_chunk_received(self, chunk: str):
        """接收到数据块 → 缓冲后匀速释放到 AI 气泡
        
        本地模型（如 Ollama）生成速度极快，信号会堆积。
        用缓冲区 + QTimer 匀速释放，实现和远程 API 一样的打字机效果。
        """
        if not self.current_ai_bubble:
            self._hide_thinking_indicator()

            self.current_ai_bubble = AIMessageBubble("", theme=self.current_theme, show_regenerate=True)
            self.current_ai_bubble.regenerate_clicked.connect(self.on_regenerate_response)

            # 新回复开始，重置滚动状态
            if self.scroll_controller:
                self.scroll_controller.reset_for_new_response()

            self.ai_bubbles.append(self.current_ai_bubble)

            self.message_layout.insertWidget(
                self.message_layout.count() - 1,
                self.current_ai_bubble,
                0,
            )

            # 初始化 token 缓冲区
            if not hasattr(self, '_chunk_buffer'):
                self._chunk_buffer = []
                self._chunk_timer = QTimer()
                self._chunk_timer.timeout.connect(self._flush_chunk_buffer)

        # 将 chunk 拆成单字符加入缓冲区，实现打字机效果
        self._chunk_buffer.extend(list(chunk))

        # 如果定时器没在跑，启动它（每 15ms 释放一批）
        if not self._chunk_timer.isActive():
            # 第一个 chunk 立即显示，不等待
            self._flush_chunk_buffer()
            self._chunk_timer.start(15)

    def _flush_chunk_buffer(self):
        """从缓冲区取出 chunk 并显示"""
        if not self._chunk_buffer or not self.current_ai_bubble:
            # 缓冲区空了，停止定时器
            if hasattr(self, '_chunk_timer') and self._chunk_timer.isActive():
                self._chunk_timer.stop()
            # 如果流已结束且缓冲区空了，执行 finalize
            if getattr(self, '_stream_finished', False):
                self._stream_finished = False
                self._do_finalize()
            return

        # 每次释放几个字符（兼顾打字机效果和速度）
        chars_per_tick = 3
        text = ""
        for _ in range(min(chars_per_tick, len(self._chunk_buffer))):
            text += self._chunk_buffer.pop(0)
        if text:
            self.current_ai_bubble.append_text(text)
            self.scroll_to_bottom()

        # 缓冲区空了就停止，并检查是否需要 finalize
        if not self._chunk_buffer:
            self._chunk_timer.stop()
            if getattr(self, '_stream_finished', False):
                self._stream_finished = False
                self._do_finalize()

    def _do_finalize(self):
        """完成气泡渲染、重置状态"""
        if self.current_ai_bubble:
            if hasattr(self.current_ai_bubble, 'finalize'):
                self.current_ai_bubble.finalize()
        self.current_ai_bubble = None

    def _on_request_finished(self, response_text: str):
        """API 请求完成 → 标记流结束，等缓冲区释放完再 finalize"""
        if hasattr(self, '_chunk_buffer') and self._chunk_buffer:
            # 缓冲区还有内容，标记等待释放完毕
            self._stream_finished = True
            # 确保定时器在跑
            if hasattr(self, '_chunk_timer') and not self._chunk_timer.isActive():
                self._chunk_timer.start(15)
        else:
            # 缓冲区已空，直接 finalize
            if hasattr(self, '_chunk_timer'):
                self._chunk_timer.stop()
            self._do_finalize()

    def _on_error_occurred(self, error_message: str):
        """API 请求出错 → 显示错误气泡"""
        self._hide_thinking_indicator()

        error_bubble = AIMessageBubble("", theme=self.current_theme, show_regenerate=False)
        self.ai_bubbles.append(error_bubble)

        self.message_layout.insertWidget(
            self.message_layout.count() - 1,
            error_bubble,
            0,
        )

        QApplication.processEvents()

        error_text = f"**发生错误**\n\n{error_message}"
        error_bubble.append_text(error_text)

        if hasattr(error_bubble, 'finalize'):
            error_bubble.finalize()

        QApplication.processEvents()
        self.scroll_to_bottom()

        self.current_ai_bubble = None

    def _on_tool_start(self, tool_name: str):
        """工具开始执行 → 更新思考动画"""
        if self.thinking_indicator:
            chinese_name = self.controller.get_tool_chinese_name(tool_name)
            self.thinking_indicator.update_text(f"调用{chinese_name}")

    def _on_tool_complete(self, tool_name: str, result: dict):
        """工具执行完成（当前仅日志）"""
        success = result.get('success', False)
        if not success:
            error = result.get('error', '未知错误')
            print(f"[WARNING] 工具 {tool_name} 执行失败: {error}")

    # ------------------------------------------------------------------
    # 消息气泡管理
    # ------------------------------------------------------------------

    def add_user_message(self, message: str):
        """添加用户消息"""
        self._hide_previous_regenerate_buttons()

        bubble = UserMessageBubble(message, theme=self.current_theme)
        self.user_bubbles.append(bubble)

        self.message_layout.insertWidget(
            self.message_layout.count() - 1,
            bubble,
            0,
        )

        self._cleanup_old_messages()
        self.scroll_to_bottom()
        QTimer.singleShot(50, self.scroll_to_bottom)

    def add_assistant_message(self, message: str):
        """添加助手消息（历史消息，不显示重新生成按钮）"""
        bubble = AIMessageBubble(message, theme=self.current_theme, show_regenerate=False)
        self.ai_bubbles.append(bubble)

        self.message_layout.insertWidget(
            self.message_layout.count() - 1,
            bubble,
            0,
        )

        self._cleanup_old_messages()
        QTimer.singleShot(10, self.scroll_to_bottom)

    def _hide_previous_regenerate_buttons(self):
        """隐藏之前所有AI消息的重新生成按钮"""
        for bubble in self.ai_bubbles:
            if hasattr(bubble, 'hide_regenerate_button'):
                bubble.hide_regenerate_button()

    def on_regenerate_response(self):
        """重新生成AI回答"""
        try:
            print("[DEBUG] 重新生成回答")

            # UI：移除最后一个 AI 气泡
            if self.ai_bubbles:
                last_ai_bubble = self.ai_bubbles.pop()
                self.message_layout.removeWidget(last_ai_bubble)
                last_ai_bubble.deleteLater()

            # UI：显示思考动画
            self._show_thinking_indicator()

            # 业务逻辑：重新生成（控制器处理历史和 API 调用）
            if not self.controller.regenerate():
                print("[ERROR] 无法重新生成")

        except Exception as e:
            print(f"[ERROR] 重新生成回答时出错: {e}")
            import traceback
            traceback.print_exc()

    def _cleanup_old_messages(self):
        """动态加载模式下不再主动截断旧消息，保留所有已渲染的 widget"""
        pass

    def _clear_all_text_selection(self):
        """清除所有消息气泡的文本选择"""
        for bubble in self.user_bubbles:
            if hasattr(bubble, 'message_label'):
                bubble.message_label.clearFocus()

        for bubble in self.ai_bubbles:
            if hasattr(bubble, 'text_browser'):
                cursor = bubble.text_browser.textCursor()
                if cursor.hasSelection():
                    cursor.clearSelection()
                    bubble.text_browser.setTextCursor(cursor)

    # ------------------------------------------------------------------
    # 资产/配置附件 UI
    # ------------------------------------------------------------------

    def _on_add_asset(self):
        """处理添加资产请求"""
        print("[DEBUG] 打开资产选择窗口")

        if not self.controller.asset_manager_logic:
            print("[WARNING] 资产管理逻辑层未初始化")
            return

        assets = self.controller.asset_manager_logic.assets if hasattr(self.controller.asset_manager_logic, 'assets') else []
        if not assets:
            print("[WARNING] 没有可用的资产")
            return

        self._show_asset_selection_window(assets)

    def _show_asset_selection_window(self, assets):
        """显示资产选择窗口"""
        from PyQt6.QtWidgets import QDialog, QVBoxLayout, QListWidget, QListWidgetItem, QPushButton, QHBoxLayout, QLabel
        from PyQt6.QtCore import Qt

        dialog = QDialog(self)
        dialog.setWindowTitle("选择资产")
        dialog.setMinimumSize(400, 500)
        dialog.setWindowFlags(dialog.windowFlags() & ~Qt.WindowType.WindowContextHelpButtonHint)

        layout = QVBoxLayout(dialog)

        title = QLabel("请选择要添加的资产：")
        title.setStyleSheet("font-size: 14px; font-weight: bold; margin-bottom: 10px;")
        layout.addWidget(title)

        list_widget = QListWidget()
        list_widget.setStyleSheet("""
            QListWidget {
                border: 1px solid #404040;
                border-radius: 8px;
                padding: 4px;
            }
            QListWidget::item {
                padding: 8px;
                border-radius: 4px;
            }
            QListWidget::item:selected {
                background-color: #1976D2;
            }
            QListWidget::item:hover {
                background-color: #404040;
            }
        """)

        for asset in assets:
            item = QListWidgetItem(f"📦 {asset.name}")
            item.setData(Qt.ItemDataRole.UserRole, asset)
            list_widget.addItem(item)

        layout.addWidget(list_widget)

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        cancel_btn = QPushButton("取消")
        cancel_btn.clicked.connect(dialog.reject)
        btn_layout.addWidget(cancel_btn)

        confirm_btn = QPushButton("确定")
        confirm_btn.setDefault(True)

        def on_confirm():
            selected_items = list_widget.selectedItems()
            if selected_items:
                asset = selected_items[0].data(Qt.ItemDataRole.UserRole)
                self._add_asset_to_input(asset)
                dialog.accept()

        confirm_btn.clicked.connect(on_confirm)
        btn_layout.addWidget(confirm_btn)

        layout.addLayout(btn_layout)

        list_widget.itemDoubleClicked.connect(lambda item: on_confirm())

        dialog.exec()

    def _add_asset_to_input(self, asset):
        """将资产添加到输入框"""
        asset_data = self._get_asset_tree_structure(asset)

        self.input_box.add_attachment(
            attachment_type="asset",
            name=asset.name,
            path=str(asset.path),
            data=asset_data,
        )

    def _get_asset_tree_structure(self, asset) -> dict:
        """获取资产的树形结构和文件列表"""
        from pathlib import Path

        result = {
            'name': asset.name,
            'path': str(asset.path),
            'tree': '',
            'files': [],
        }

        try:
            asset_path = Path(asset.path)
            if asset_path.exists():
                tree_lines = []
                file_list = []

                def build_tree(path, prefix="", is_last=True):
                    name = path.name
                    connector = "└── " if is_last else "├── "
                    tree_lines.append(f"{prefix}{connector}{name}")

                    if path.is_file():
                        file_list.append(str(path.relative_to(asset_path)))

                    if path.is_dir():
                        children = sorted(path.iterdir(), key=lambda x: (x.is_file(), x.name.lower()))
                        for i, child in enumerate(children):
                            is_last_child = (i == len(children) - 1)
                            new_prefix = prefix + ("    " if is_last else "│   ")
                            build_tree(child, new_prefix, is_last_child)

                tree_lines.append(asset.name)
                children = sorted(asset_path.iterdir(), key=lambda x: (x.is_file(), x.name.lower()))
                for i, child in enumerate(children):
                    is_last = (i == len(children) - 1)
                    build_tree(child, "", is_last)

                result['tree'] = "\n".join(tree_lines)
                result['files'] = file_list
        except Exception as e:
            print(f"[WARNING] 获取资产树形结构失败: {e}")

        return result

    def _on_add_config(self):
        """处理添加配置请求"""
        print("[DEBUG] 添加配置功能待实现")

    # ------------------------------------------------------------------
    # 滚动
    # ------------------------------------------------------------------

    def scroll_to_bottom(self):
        """智能滚动到底部"""
        self.scroll_area.widget().updateGeometry()

        if self.scroll_controller:
            self.scroll_controller.request_scroll_to_bottom()
        else:
            scrollbar = self.scroll_area.verticalScrollBar()
            scrollbar.setValue(scrollbar.maximum())

    def showEvent(self, event):
        """窗口首次显示时，刷新所有已恢复气泡的高度"""
        super().showEvent(event)
        if not getattr(self, '_bubbles_refreshed', False):
            self._bubbles_refreshed = True
            QTimer.singleShot(50, self._refresh_bubble_heights)

    def _refresh_bubble_heights(self):
        """刷新所有 AI 气泡的高度（解决懒加载时 document 高度为 0 的问题）"""
        for bubble in self.ai_bubbles:
            if hasattr(bubble, 'adjust_height'):
                bubble.update_content()
        self.scroll_to_bottom()

    # ------------------------------------------------------------------
    # 事件处理
    # ------------------------------------------------------------------

    def mousePressEvent(self, event):
        """鼠标点击事件：点击空白区域时清除文本选择"""
        super().mousePressEvent(event)
        self._clear_all_text_selection()

    def resizeEvent(self, event):
        """窗口大小变化"""
        super().resizeEvent(event)

    def eventFilter(self, obj, event):
        """事件过滤器：处理点击事件"""
        if hasattr(self, 'message_container') and obj == self.message_container and event.type() == QEvent.Type.MouseButtonPress:
            self._clear_all_text_selection()
            
            # 如果侧边栏展开，点击聊天区域时自动收起
            if self._sidebar_visible:
                self._hide_sidebar()

        return super().eventFilter(obj, event)

    # ------------------------------------------------------------------
    # 主题
    # ------------------------------------------------------------------

    def update_theme(self, theme_name: str):
        """主题切换时更新组件"""
        new_theme = "dark" if "dark" in theme_name.lower() else "light"

        if new_theme == self.current_theme:
            return

        self.current_theme = new_theme

        if hasattr(self, 'input_box') and hasattr(self.input_box, 'update_theme'):
            self.input_box.update_theme()

        # 更新侧边栏和工具栏主题
        if hasattr(self, 'session_sidebar'):
            self.session_sidebar.set_theme(new_theme)
        if hasattr(self, 'sidebar_toggle_btn'):
            self._apply_toolbar_style()

        self._update_bubbles_theme_async()

    def on_theme_changed(self, theme_name: str) -> None:
        """主题切换回调方法（继承自 BaseModuleWidget）"""
        super().on_theme_changed(theme_name)
        self.update_theme(theme_name)

    def _update_bubbles_theme_async(self):
        """异步分批更新气泡主题"""
        all_bubbles = self.user_bubbles + self.ai_bubbles

        if not all_bubbles:
            return

        bubbles_to_update = all_bubbles
        batch_size = 10
        index = [0]

        def update_batch():
            start = index[0]
            end = min(start + batch_size, len(bubbles_to_update))

            for i in range(start, end):
                try:
                    bubbles_to_update[i].set_theme(self.current_theme)
                except Exception:
                    pass

            index[0] = end

            if index[0] < len(bubbles_to_update):
                QTimer.singleShot(1, update_batch)

        update_batch()
