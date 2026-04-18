# -*- coding: utf-8 -*-

"""
主窗口 - 现代化设计（QSS样式版本）
从内联样式迁移到外部QSS系统
保持所有样式完全不变
"""

import sys
import time
import json
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QFrame, QStackedWidget, QScrollArea, QProgressBar
)
from PyQt6.QtCore import Qt, QStandardPaths, pyqtSignal, QTimer
from PyQt6.QtGui import QIcon, QPixmap
from pathlib import Path

# 使用统一服务层
from core.services import style_service
# 注意：不在模块级别导入 log_service，避免循环导入问题

# 导入设置界面
from ui.settings_widget import SettingsWidget

# 导入版本信息
from version import APP_NAME, APP_DISPLAY_NAME, get_version_string

# 导入 UI 常量
from core.constants import (
    WINDOW_DEFAULT_WIDTH,
    WINDOW_DEFAULT_HEIGHT,
    TITLEBAR_HEIGHT,
    TITLEBAR_ICON_SIZE,
    TITLEBAR_BUTTON_WIDTH,
    TITLEBAR_BUTTON_HEIGHT,
    LEFT_PANEL_WIDTH,
    LOGO_CONTAINER_HEIGHT,
    NAV_BUTTON_HEIGHT,
    FEEDBACK_BUTTON_HEIGHT,
    RIGHT_PANEL_MARGIN_TOP,
    RIGHT_PANEL_MARGIN_BOTTOM,
    RIGHT_PANEL_MARGIN_LEFT,
    RIGHT_PANEL_MARGIN_RIGHT,
    ICON_BUTTON_SIZE,
    UPDATE_BUTTON_WIDTH,
    UPDATE_BUTTON_HEIGHT,
    UPDATE_BADGE_SIZE,
    THEME_TOGGLE_DEBOUNCE_MS
)


class UEMainWindow(QMainWindow):
    """主窗口 - 现代化设计"""
    
    # 主题切换信号
    theme_changed = pyqtSignal(str)  # 参数: theme_name ('dark' 或 'light')
    # UE 连接状态信号（后台线程 → 主线程）
    _ue_connection_changed = pyqtSignal(bool)
    # Ollama 模型加载完成信号
    _ollama_models_loaded = pyqtSignal(list, dict)  # (models, config)

    def __init__(self, module_provider=None):
        super().__init__()

        # 初始化 logger（使用旧的 logger，避免导入冲突）
        from core.logger import get_logger
        self.logger = get_logger(__name__)

        self.module_provider = module_provider
        
        # 关闭状态标志
        self._is_closing = False
        
        # 防止自动激活标志
        self._allow_auto_activate = True
        
        # 系统托盘
        self.system_tray = None
        
        # 连接 Ollama 模型加载信号
        self._ollama_models_loaded.connect(self._on_ollama_models_loaded)
        
        # 当前模块索引（退出时保存）
        self._current_module_index = 0
        
        # 模块名称和键（用于懒加载，避免启动时一次性创建所有模块UI）
        self.module_names = ["我的工程", "资产库", "AI 助手", "工程配置", "作者推荐"]
        self.module_keys = ["my_projects", "asset_manager", "ai_assistant", "config_tool", "site_recommendations"]
        self._loaded_module_indices = set()  # 记录已经真正加载过UI的模块索引
        # 不再需要 is_dark_theme，由 style_system 管理
        
        # 设置页面相关
        self.settings_widget = None  # 懒加载
        self.settings_page_index = -1  # 设置页面在content_stack中的索引
        
        # 悬浮窗
        self._floating_widget = None
        
        self.init_ui()
        
        # 恢复窗口状态（在UI初始化后）
        self._restore_window_state()
        
        # 初始化悬浮窗（根据配置决定是否显示）
        self._init_floating_widget()
        
        # ⚡ 移除授权状态预加载，所有模块免费开放

    def init_ui(self):
        """初始化UI"""
        # 设置窗口标题（从 version.py 读取版本号）
        self.setWindowTitle(f"{APP_DISPLAY_NAME} {get_version_string()} - 虚幻引擎工具箱")
        # 使用 16:10 黄金比例，符合人类美学
        self.setGeometry(100, 100, WINDOW_DEFAULT_WIDTH, WINDOW_DEFAULT_HEIGHT)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint)  # 无边框窗口
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)  # 透明背景，支持圆角

        # Windows: 给无边框窗口添加 WS_MINIMIZEBOX，让任务栏点击能切换最小化/恢复
        if sys.platform == 'win32':
            try:
                import ctypes
                hwnd = int(self.winId())
                GWL_STYLE = -16
                WS_MINIMIZEBOX = 0x00020000
                style = ctypes.windll.user32.GetWindowLongW(hwnd, GWL_STYLE)
                ctypes.windll.user32.SetWindowLongW(hwnd, GWL_STYLE, style | WS_MINIMIZEBOX)
            except Exception as e:
                self.logger.warning(f"设置 WS_MINIMIZEBOX 失败: {e}")

        # 创建中央部件（用于包裹整个窗口）
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        # 中央部件布局
        central_layout = QVBoxLayout(central_widget)
        central_layout.setContentsMargins(0, 0, 0, 0)

        # 创建主容器（带圆角）
        main_container = QWidget()
        main_container.setObjectName("MainContainer")

        central_layout.addWidget(main_container)

        # 容器内部布局
        inner_layout = QVBoxLayout(main_container)
        inner_layout.setContentsMargins(0, 0, 0, 0)
        inner_layout.setSpacing(0)

        # ⭐ 不再在这里应用样式，由 main.py 统一应用
        # 样式将通过 style_system.apply_theme() 在应用程序级别应用

        # 标题栏
        self.create_title_bar(inner_layout)

        # 内容区域（横向布局）
        content_layout = QHBoxLayout()
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(0)

        # 左侧导航栏
        self.create_left_panel(content_layout)

        # 右侧内容区
        self.create_right_panel(content_layout)

        inner_layout.addLayout(content_layout)

        # 居中显示
        self.center_window()
        
        # 初始化系统托盘
        self.init_system_tray()

        # 授权状态 UI 已在 _create_license_status_widget 中刷新，无需重复调用
    
    def init_system_tray(self):
        """初始化系统托盘"""
        try:
            from ui.system_tray import SystemTrayManager
            
            # 检查系统托盘是否可用
            from PyQt6.QtWidgets import QSystemTrayIcon
            if not QSystemTrayIcon.isSystemTrayAvailable():
                self.logger.warning("系统托盘不可用")
                return
            
            self.system_tray = SystemTrayManager(self)
            
            # 获取图标路径 - 使用 .ico 格式
            resources_dir = Path(__file__).parent.parent / "resources"
            icon_path = resources_dir / "tubiao.ico"
            
            if not icon_path.exists():
                self.logger.warning(f"找不到托盘图标: {icon_path}")
                return
            
            self.logger.info(f"使用托盘图标: {icon_path}")
            
            # 初始化托盘
            self.system_tray.initialize(icon_path)
            
            # 连接信号
            self.system_tray.show_window_requested.connect(self._on_show_from_tray)
            self.system_tray.quit_requested.connect(self._on_quit_from_tray)
            
            self.logger.info("系统托盘初始化成功")
            
        except Exception as e:
            self.logger.error(f"系统托盘初始化失败: {e}", exc_info=True)
    
    def _on_show_from_tray(self):
        """从托盘显示窗口"""
        # 只有在用户主动从托盘恢复时才激活窗口
        self._allow_auto_activate = True
        if self.isMinimized():
            self.showNormal()
        self.show()
        self.activateWindow()
        self.raise_()
        self.logger.info("从托盘恢复窗口显示")
    
    def changeEvent(self, event):
        """窗口状态改变事件"""
        # 当窗口最小化时，禁止自动激活
        if event.type() == event.Type.WindowStateChange:
            if self.isMinimized():
                # 窗口已最小化，禁止自动激活
                self._allow_auto_activate = False
                self.logger.debug("窗口已最小化，禁止自动激活")
            elif self.windowState() == Qt.WindowState.WindowNoState:
                # 窗口恢复正常状态
                self._allow_auto_activate = True
                self.logger.debug("窗口恢复正常状态")
        
        super().changeEvent(event)
    
    def showEvent(self, event):
        """窗口显示事件"""
        # 如果不允许自动激活且窗口是最小化状态，不激活窗口
        if not self._allow_auto_activate and self.isMinimized():
            self.logger.debug("阻止窗口自动激活（最小化状态）")
            event.ignore()
            return
        
        super().showEvent(event)
    
    def _on_quit_from_tray(self):
        """从托盘退出程序"""
        self.logger.info("从托盘退出程序")
        self._is_closing = True
        self.close()
        
        # 确保应用程序退出
        from PyQt6.QtWidgets import QApplication
        QApplication.quit()
        self.logger.info("已调用 QApplication.quit()")

    def load_initial_module(self, on_complete=None):
        """加载初始模块（由外部在窗口显示后调用）
        
        Args:
            on_complete: 加载完成回调函数
        """
        from core.logger import get_logger
        logger = get_logger(__name__)
        
        self.logger.info("开始加载初始模块")

        # 恢复上次打开的模块
        initial_index = 0
        try:
            from core.services import config_service
            app_config = config_service.get_module_config("app") or {}
            saved_key = app_config.get("module_state", {}).get("current_module", "")
            if saved_key and hasattr(self, "module_keys") and saved_key in self.module_keys:
                initial_index = self.module_keys.index(saved_key)
        except Exception:
            pass

        # 加载初始模块并切换到正确位置
        self._ensure_module_loaded(initial_index)
        if self.content_stack is not None:
            self.content_stack.setCurrentIndex(initial_index)
        for i, btn in enumerate(self.nav_buttons):
            btn.setChecked(i == initial_index)
        
        # 更新副标题和模型下拉框
        if hasattr(self, "module_names") and 0 <= initial_index < len(self.module_names):
            module_name = self.module_names[initial_index]
            self.subtitle_label.setText(module_name)
            
            # 如果初始模块是 AI 助手，显示模型下拉框
            if module_name == "AI 助手" and hasattr(self, 'ai_model_combo'):
                self.ai_model_combo.setVisible(True)
                # 延迟加载模型列表
                from PyQt6.QtCore import QTimer
                QTimer.singleShot(100, self._load_ai_models)
                # 显示 UE 连接状态
                if hasattr(self, '_ue_status_container'):
                    self._ue_status_container.setVisible(True)
            elif hasattr(self, 'ai_model_combo'):
                self.ai_model_combo.setVisible(False)
                # 隐藏 UE 连接状态
                if hasattr(self, '_ue_status_container'):
                    self._ue_status_container.setVisible(False)

        # 如果初始模块是资产库，触发异步加载资产
        initial_key = self.module_keys[initial_index] if hasattr(self, "module_keys") else ""
        if initial_key == "asset_manager" and self.module_provider:
            self.logger.info("检测到资产库模块，开始加载资产")
            asset_manager = self.module_provider.get_module("asset_manager")
            if asset_manager:
                asset_widget = asset_manager.get_widget()
                self.logger.info(f"获取资产库UI组件: {asset_widget}")
                if asset_widget and hasattr(asset_widget, "load_assets_async"):
                    self.logger.info("开始异步加载资产")
                    asset_widget.load_assets_async(on_complete)
                elif on_complete:
                    on_complete()
            else:
                self.logger.error("无法获取资产库模块")
                if on_complete:
                    on_complete()
        elif on_complete:
            on_complete()

    def create_title_bar(self, parent_layout):
        """创建标题栏"""
        title_bar = QWidget()
        title_bar.setObjectName("TitleBar")
        title_bar.setFixedHeight(TITLEBAR_HEIGHT)

        # 标题栏布局
        layout = QHBoxLayout(title_bar)
        layout.setContentsMargins(16, 0, 10, 0)
        layout.setSpacing(10)

        # Logo 图标（在标题栏左侧）
        logo_icon = QLabel()
        logo_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # 尝试加载图标文件
        icon_path = Path(__file__).parent.parent / "resources" / "tubiao.ico"
        if icon_path.exists():
            # Bug fix: QPixmap 加载 .ico 只取16x16，改用 QIcon 取高清层
            _icon = QIcon(str(icon_path))
            pixmap = _icon.pixmap(256, 256)
            scaled_pixmap = pixmap.scaled(
                TITLEBAR_ICON_SIZE, TITLEBAR_ICON_SIZE,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation
            )
            logo_icon.setPixmap(scaled_pixmap)
        else:
            # 如果图标不存在，使用后备图标
            logo_icon.setText("◆")
            logo_icon.setObjectName("LogoIconFallback")  # ⭐ 使用QSS样式

        layout.addWidget(logo_icon)

        # 程序名称+版本号（使用HTML实现不同颜色）
        from version import VERSION
        self.titlebar_label = QLabel(f'<span style="color: #ffffff;">UE Toolkit</span> <span style="color: rgba(255, 255, 255, 0.5);">v{VERSION}</span>')
        self.titlebar_label.setObjectName("TitleBarLabel")  # ⭐ 使用QSS样式
        layout.addWidget(self.titlebar_label)

        layout.addStretch()

        # 授权状态标签 + 激活按钮
        self._create_license_status_widget(layout)

        # 检查更新按钮容器（用于添加小红点）
        update_btn_container = QWidget()
        update_btn_container.setFixedSize(UPDATE_BUTTON_WIDTH, UPDATE_BUTTON_HEIGHT)
        update_btn_layout = QHBoxLayout(update_btn_container)
        update_btn_layout.setContentsMargins(0, 0, 0, 0)
        update_btn_layout.setSpacing(0)
        
        # 检查更新按钮（透明无边框，只显示文字）
        self.check_update_btn = QPushButton("检查更新")
        self.check_update_btn.setObjectName("CheckUpdateButton")
        self.check_update_btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.check_update_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.check_update_btn.clicked.connect(self.manual_check_update)
        update_btn_layout.addWidget(self.check_update_btn)
        
        # 小红点（默认隐藏）
        self.update_badge = QLabel("●")
        self.update_badge.setObjectName("UpdateBadge")
        self.update_badge.setFixedSize(UPDATE_BADGE_SIZE, UPDATE_BADGE_SIZE)
        self.update_badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.update_badge.hide()  # 默认隐藏
        
        # 将小红点放在按钮右上角
        self.update_badge.setParent(update_btn_container)
        self.update_badge.move(72, 2)  # 右上角位置
        
        layout.addWidget(update_btn_container)


        # 窗口控制按钮
        btn_minimize = QPushButton("━")
        btn_minimize.setObjectName("WindowButton")
        btn_minimize.setFixedSize(TITLEBAR_BUTTON_WIDTH, TITLEBAR_BUTTON_HEIGHT)
        btn_minimize.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        btn_minimize.clicked.connect(self.showMinimized)
        layout.addWidget(btn_minimize)

        # 最大化按钮（禁用状态，仅保留视觉统一性）
        btn_maximize = QPushButton("☐")
        btn_maximize.setObjectName("WindowButtonDisabled")
        btn_maximize.setFixedSize(TITLEBAR_BUTTON_WIDTH, TITLEBAR_BUTTON_HEIGHT)
        btn_maximize.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        btn_maximize.setEnabled(False)  # 禁用按钮
        btn_maximize.setToolTip("固定窗口大小")
        layout.addWidget(btn_maximize)

        btn_close = QPushButton("✕")
        btn_close.setObjectName("CloseButton")
        btn_close.setFixedSize(TITLEBAR_BUTTON_WIDTH, TITLEBAR_BUTTON_HEIGHT)
        btn_close.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        btn_close.clicked.connect(self.close)
        layout.addWidget(btn_close)

        parent_layout.addWidget(title_bar)

        # 保存按钮引用
        self.maximize_button = btn_maximize

        # 启用标题栏拖动（禁用双击最大化）
        title_bar.mousePressEvent = self.title_bar_mouse_press
        title_bar.mouseMoveEvent = self.title_bar_mouse_move
        # 双击标题栏不做任何操作
        title_bar.mouseDoubleClickEvent = lambda e: e.accept()
        self._drag_position = None
        
        # 启动 UE 连接状态轮询
        self._start_ue_connection_check()

    def _create_license_status_widget(self, parent_layout):
        """在标题栏创建授权状态（已移除，所有模块免费开放）"""
        # ⚡ 不再显示授权状态，所有功能免费开放
        pass

    def create_left_panel(self, parent_layout):
        """创建左侧导航面板（文字按钮形式）"""
        left_panel = QFrame()
        left_panel.setObjectName("LeftPanel")
        left_panel.setFixedWidth(LEFT_PANEL_WIDTH)  # 加宽以容纳文字

        layout = QVBoxLayout(left_panel)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        # 顶部Logo区域
        logo_container = QWidget()
        logo_container.setObjectName("LogoContainer")  # ⭐ 使用QSS样式
        logo_container.setFixedHeight(LOGO_CONTAINER_HEIGHT)
        logo_layout = QVBoxLayout(logo_container)
        logo_layout.setContentsMargins(12, 12, 12, 12)
        logo_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # Logo文字
        logo_label = QLabel("虚幻工具箱\n专业版")
        logo_label.setObjectName("LogoText")
        logo_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        logo_layout.addWidget(logo_label)
        layout.addWidget(logo_container)

        # 分割线（渐变效果）
        separator = QFrame()
        separator.setObjectName("Separator")
        separator.setFixedHeight(1)
        layout.addWidget(separator)

        layout.addSpacing(10)

        # 导航按钮滚动区域（QScrollArea 兜底，模块多时自动滚动）
        nav_scroll = QScrollArea()
        nav_scroll.setObjectName("NavScrollArea")
        nav_scroll.setWidgetResizable(True)
        nav_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        nav_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        nav_scroll.setFrameShape(QFrame.Shape.NoFrame)
        # 关键：viewport 必须透明，否则会遮挡侧边栏渐变背景
        nav_scroll.viewport().setAutoFillBackground(False)
        nav_scroll.setStyleSheet("QScrollArea { background: transparent; } QScrollArea > QWidget > QWidget { background: transparent; }")

        # 导航按钮容器（添加边距）
        nav_container = QWidget()
        nav_container.setObjectName("NavContainer")  # ⭐ 使用QSS样式
        nav_layout = QVBoxLayout(nav_container)
        nav_layout.setContentsMargins(12, 0, 12, 0)
        nav_layout.setSpacing(4)

        # 导航按钮（纯文字）
        modules = self.module_names

        self.nav_buttons = []
        for i, name in enumerate(modules):
            btn = QPushButton(name)
            btn.setObjectName("NavTextButton")
            btn.setFixedHeight(NAV_BUTTON_HEIGHT)
            btn.setCheckable(True)
            btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)

            # 默认选中第一个
            if i == 0:
                btn.setChecked(True)

            btn.clicked.connect(lambda checked, idx=i: self.switch_module(idx))
            nav_layout.addWidget(btn)
            self.nav_buttons.append(btn)

        nav_layout.addStretch()
        nav_scroll.setWidget(nav_container)
        layout.addWidget(nav_scroll)
        
        # 问题反馈按钮（底部）
        feedback_btn = QPushButton("💬 问题反馈")
        feedback_btn.setObjectName("FeedbackButton")
        feedback_btn.setFixedHeight(FEEDBACK_BUTTON_HEIGHT)
        feedback_btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        feedback_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        feedback_btn.clicked.connect(self.show_feedback_dialog)
        
        # 添加底部边距
        feedback_container = QWidget()
        feedback_layout = QVBoxLayout(feedback_container)
        feedback_layout.setContentsMargins(12, 0, 12, 12)
        feedback_layout.addWidget(feedback_btn)
        
        layout.addWidget(feedback_container)

        parent_layout.addWidget(left_panel)

    def create_right_panel(self, parent_layout):
        """创建右侧内容区"""
        right_panel = QFrame()
        right_panel.setObjectName("RightPanel")

        layout = QVBoxLayout(right_panel)
        layout.setContentsMargins(RIGHT_PANEL_MARGIN_LEFT, RIGHT_PANEL_MARGIN_TOP, RIGHT_PANEL_MARGIN_RIGHT, RIGHT_PANEL_MARGIN_BOTTOM)
        layout.setSpacing(0)

        # 标题区域容器（简化：只保留副标题和设置按钮）
        title_container = QWidget()
        title_container.setObjectName("TitleContainer")
        title_layout = QHBoxLayout(title_container)
        title_layout.setContentsMargins(0, 0, 0, 20)
        title_layout.setSpacing(15)

        # 副标题（显示当前模块名称）- 更突出的样式
        self.subtitle_label = QLabel(self.module_names[0] if self.module_names else "")
        self.subtitle_label.setObjectName("SubTitle")
        title_layout.addWidget(self.subtitle_label)
        
        # AI 助手模型选择下拉框（默认隐藏）
        from PyQt6.QtWidgets import QComboBox
        self.ai_model_combo = QComboBox()
        self.ai_model_combo.setObjectName("AssetSortCombo")  # 使用资产管理界面的样式
        self.ai_model_combo.setFixedHeight(36)
        self.ai_model_combo.setMinimumWidth(180)
        self.ai_model_combo.setMaximumWidth(250)
        self.ai_model_combo.setPlaceholderText("加载中...")
        self.ai_model_combo.setVisible(False)  # 默认隐藏
        self.ai_model_combo.currentIndexChanged.connect(self._on_ai_model_changed)
        title_layout.addWidget(self.ai_model_combo)
        
        # UE 插件连接状态指示器（放在模型选择右边，默认隐藏）
        self._ue_status_container = QWidget()
        ue_status_layout = QHBoxLayout(self._ue_status_container)
        ue_status_layout.setContentsMargins(12, 0, 0, 0)
        ue_status_layout.setSpacing(6)
        
        self._ue_status_dot = QLabel("●")
        self._ue_status_dot.setStyleSheet("color: #666666; font-size: 10px;")
        self._ue_status_dot.setFixedWidth(10)
        ue_status_layout.addWidget(self._ue_status_dot)
        
        self._ue_status_label = QLabel("UE 未连接")
        self._ue_status_label.setStyleSheet("color: #888888; font-size: 11px;")
        ue_status_layout.addWidget(self._ue_status_label)
        
        self._ue_status_container.setVisible(False)  # 默认隐藏，只在 AI 助手模块显示
        title_layout.addWidget(self._ue_status_container)

        title_layout.addStretch()

        # 状态信息指示器（默认隐藏，触发时显示，紧贴主题按钮左侧）
        self._status_indicator = QWidget()
        self._status_indicator.setObjectName("StatusIndicator")
        self._status_indicator.setVisible(False)
        indicator_layout = QHBoxLayout(self._status_indicator)
        indicator_layout.setContentsMargins(0, 0, 8, 0)
        indicator_layout.setSpacing(8)

        self._status_progress = QProgressBar()
        self._status_progress.setObjectName("StatusProgressBar")
        self._status_progress.setFixedHeight(3)
        self._status_progress.setFixedWidth(80)
        self._status_progress.setTextVisible(False)
        self._status_progress.setRange(0, 100)
        self._status_progress.setValue(0)
        indicator_layout.addWidget(self._status_progress, 0, Qt.AlignmentFlag.AlignVCenter)

        # 两行文本容器
        from PyQt6.QtWidgets import QSizePolicy
        text_container = QWidget()
        text_container.setObjectName("StatusTextContainer")
        text_container.setFixedWidth(180)  # 固定宽度，防止文本变化时整体跳位
        text_layout = QVBoxLayout(text_container)
        text_layout.setContentsMargins(0, 0, 0, 0)
        text_layout.setSpacing(1)

        self._status_label = QLabel("")          # 上行：阶段 X/N · 阶段名
        self._status_label.setObjectName("StatusLabel")
        self._status_label.setFixedWidth(180)
        text_layout.addWidget(self._status_label)

        self._status_detail = QLabel("")         # 下行：详情描述
        self._status_detail.setObjectName("StatusDetail")
        self._status_detail.setFixedWidth(180)
        text_layout.addWidget(self._status_detail)

        indicator_layout.addWidget(text_container)

        # 「显示详情」按钮（默认隐藏，由调用方通过 set_status_detail_callback 激活）
        self._status_detail_btn = QPushButton("详情")
        self._status_detail_btn.setObjectName("StatusDetailButton")
        self._status_detail_btn.setFixedHeight(22)
        self._status_detail_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._status_detail_btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._status_detail_btn.setVisible(False)
        self._status_detail_btn.clicked.connect(self._on_status_detail_clicked)
        self._status_detail_callback = None
        indicator_layout.addWidget(self._status_detail_btn, 0, Qt.AlignmentFlag.AlignVCenter)

        # 防止 indicator 被拉伸，紧贴主题按钮
        self._status_indicator.setSizePolicy(
            QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Fixed
        )

        title_layout.addWidget(self._status_indicator)

        # 主题切换按钮
        btn_theme = QPushButton("☀")  # 默认显示太阳图标（深色主题下）
        btn_theme.setObjectName("ThemeToggleButton")
        btn_theme.setFixedSize(ICON_BUTTON_SIZE, ICON_BUTTON_SIZE)
        btn_theme.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        btn_theme.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_theme.setToolTip("切换主题")
        btn_theme.clicked.connect(self.toggle_theme)
        title_layout.addWidget(btn_theme)
        self.theme_button = btn_theme

        # 设置按钮
        btn_settings = QPushButton("⚙")
        btn_settings.setObjectName("SettingsIconButton")
        btn_settings.setFixedSize(ICON_BUTTON_SIZE, ICON_BUTTON_SIZE)
        btn_settings.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        btn_settings.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_settings.setToolTip("设置")
        btn_settings.clicked.connect(self.show_settings)
        title_layout.addWidget(btn_settings)
        self.settings_button = btn_settings

        layout.addWidget(title_container)

        layout.addSpacing(20)

        # 堆叠窗口（用于切换模块）
        self.content_stack = QStackedWidget()
        self.content_stack.setObjectName("ContentStack")

        # 创建模块页面（启动时只创建占位页，真正的模块UI在首次切换时再懒加载）
        for i, module_name in enumerate(self.module_names):
            # ⚡ 首个模块使用加载中页面，其他模块使用占位符
            if i == 0:
                page = self.create_loading_page(module_name)
            else:
                page = self.create_placeholder_page(module_name)
            self.content_stack.addWidget(page)

        layout.addWidget(self.content_stack)

        parent_layout.addWidget(right_panel)

        # 根据当前主题更新按钮图标
        self._update_theme_button_icon()
    
    def create_loading_page(self, module_name):
        """创建加载中页面"""
        page = QWidget()
        page.setObjectName("PlaceholderPage")

        layout = QVBoxLayout(page)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.setSpacing(24)

        # 加载中标签
        loading_label = QLabel("⏳ 正在加载...")
        loading_label.setObjectName("PlaceholderTitle")
        loading_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(loading_label)

        # 进度指示（三个点）
        dots_container = QWidget()
        dots_container.setObjectName("DotsContainer")
        dots_layout = QHBoxLayout(dots_container)
        dots_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        dots_layout.setSpacing(8)

        for _ in range(3):
            dot = QLabel("•")
            dot.setObjectName("ProgressDot")
            dots_layout.addWidget(dot)

        layout.addWidget(dots_container)

        return page

    def create_placeholder_page(self, module_name):
        """创建占位页面（简约设计）"""
        page = QWidget()
        page.setObjectName("PlaceholderPage")

        layout = QVBoxLayout(page)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.setSpacing(24)

        # 模块图标
        icon_map = {
            "资产库": "BOX",
            "工程配置": "CFG",
            "作者推荐": "LINK",
            "AI 助手": "AI"
        }

        icon_label = QLabel(icon_map.get(module_name, "FILE"))
        icon_label.setObjectName("PlaceholderIcon")
        icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(icon_label)

        # 模块名称
        name_label = QLabel(module_name)
        name_label.setObjectName("PlaceholderTitle")
        name_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(name_label)

        # 说明文字
        desc_label = QLabel("模块 UI 待实现")
        desc_label.setObjectName("PlaceholderDesc")
        desc_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(desc_label)

        layout.addSpacing(10)

        # 状态标签
        status_label = QLabel("即将推出")
        status_label.setObjectName("StatusTag")
        status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(status_label, alignment=Qt.AlignmentFlag.AlignCenter)

        # 进度指示（三个点）
        dots_container = QWidget()
        dots_container.setObjectName("DotsContainer")
        dots_layout = QHBoxLayout(dots_container)
        dots_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        dots_layout.setSpacing(8)

        for _ in range(3):
            dot = QLabel("•")
            dot.setObjectName("ProgressDot")
            dots_layout.addWidget(dot)

        layout.addWidget(dots_container)

        return page

    def switch_module(self, index):
            """切换模块"""
            # ⚡ 移除授权检查，所有模块免费开放

            # 取消所有导航按钮的选中状态
            for btn in self.nav_buttons:
                btn.setChecked(False)

            # 选中当前按钮
            if 0 <= index < len(self.nav_buttons):
                self.nav_buttons[index].setChecked(True)

            # 先切换页面（立即响应），再异步懒加载
            if self.content_stack is not None:
                self.content_stack.setCurrentIndex(index)

            # 更新副标题为模块名称
            if hasattr(self, "module_names") and 0 <= index < len(self.module_names):
                module_name = self.module_names[index]

                # 如果是AI助手模块，显示模型下拉框
                if module_name == "AI 助手":
                    self.subtitle_label.setText(module_name)
                    # 显示模型下拉框并加载模型列表
                    if hasattr(self, 'ai_model_combo'):
                        self.ai_model_combo.setVisible(True)
                        # 延迟加载模型列表，避免阻塞 UI
                        from PyQt6.QtCore import QTimer
                        QTimer.singleShot(100, self._load_ai_models)
                    # 显示 UE 连接状态
                    if hasattr(self, '_ue_status_container'):
                        self._ue_status_container.setVisible(True)
                else:
                    self.subtitle_label.setText(module_name)
                    # 隐藏模型下拉框
                    if hasattr(self, 'ai_model_combo'):
                        self.ai_model_combo.setVisible(False)
                    # 隐藏 UE 连接状态
                    if hasattr(self, '_ue_status_container'):
                        self._ue_status_container.setVisible(False)

            # 保存当前模块索引（退出时保存到配置）
            if hasattr(self, "module_keys") and 0 <= index < len(self.module_keys):
                self._current_module_index = index

            # 首次切换到该模块时，延迟到下一个事件循环再懒加载，避免阻塞 UI
            if index not in getattr(self, "_loaded_module_indices", set()):
                from PyQt6.QtCore import QTimer
                QTimer.singleShot(0, lambda idx=index: self._ensure_module_loaded(idx))
        
    def _ensure_module_loaded(self, index: int) -> None:
        """确保指定索引的模块UI已加载（懒加载）

        在第一次切换到某个模块时，才真正创建对应的模块UI，
        避免在应用启动阶段一次性创建所有模块导致卡顿。
        """
        self.logger.info(f"[ENTER] _ensure_module_loaded(index={index})")
        print(f"[DEBUG] [ENTER] _ensure_module_loaded(index={index})")
        
        # 已经加载过，直接返回
        if index in getattr(self, "_loaded_module_indices", set()):
            self.logger.debug(f"模块索引 {index} 已加载，跳过")
            print(f"[DEBUG] 模块索引 {index} 已加载，跳过")
            return

        if not self.module_provider:
            self.logger.warning(f"module_provider 为 None，无法加载模块索引 {index}")
            print(f"[ERROR] module_provider 为 None")
            return

        if not hasattr(self, "module_keys") or index < 0 or index >= len(self.module_keys):
            self.logger.warning(f"模块索引 {index} 超出范围或 module_keys 不存在")
            print(f"[ERROR] 模块索引 {index} 超出范围")
            return

        module_key = self.module_keys[index]
        module_name = (
            self.module_names[index]
            if hasattr(self, "module_names") and 0 <= index < len(self.module_names)
            else module_key
        )
        
        self.logger.info(f"开始懒加载模块: {module_name} (key={module_key}, index={index})")
        print(f"[DEBUG] 开始懒加载模块: {module_name} (key={module_key}, index={index})")

        try:
            module = self.module_provider.get_module(module_key)
            print(f"[DEBUG] get_module({module_key}) 返回: {module}")
            if not module:
                self.logger.error(f"无法获取模块: {module_key}")
                print(f"[ERROR] 无法获取模块: {module_key}")
                return

            widget = module.get_widget()
            print(f"[DEBUG] module.get_widget() 返回: {widget}")
            if not widget:
                self.logger.error(f"模块 {module_key} 的 get_widget() 返回 None")
                print(f"[ERROR] 模块 {module_key} 的 get_widget() 返回 None")
                return

            # 用真实模块UI替换掉当前索引位置的占位页
            if self.content_stack is not None:
                # 先移除旧的占位页
                old_widget = self.content_stack.widget(index)
                print(f"[DEBUG] 移除旧占位页: {old_widget}")
                if old_widget is not None:
                    self.content_stack.removeWidget(old_widget)
                    old_widget.deleteLater()

                # 在相同位置插入新的真实UI
                self.content_stack.insertWidget(index, widget)
                print(f"[DEBUG] 插入新 widget 到索引 {index}")

                # 确保显示的是刚加载的模块
                self.content_stack.setCurrentIndex(index)
                print(f"[DEBUG] 设置 currentIndex 为 {index}")
                self.logger.info(f"懒加载模块 UI 成功: {module_name}")
                print(f"[SUCCESS] 懒加载模块 UI 成功: {module_name}")

            # ⚡ 只对新加载的模块 widget 刷新样式，避免全局重刷导致卡顿
            print(f"[DEBUG] 开始刷新样式...")
            widget.style().unpolish(widget)
            widget.style().polish(widget)
            widget.update()
            print(f"[DEBUG] 样式刷新完成")
            
            # ⚡ 样式刷新后，调用 widget 的 refresh_floating_button 方法（如果存在）
            # 这个方法由 AI 助手模块的 wrapper 提供，用于重新显示浮动按钮
            if hasattr(widget, 'refresh_floating_button'):
                print(f"[DEBUG] 调用 refresh_floating_button 方法")
                widget.refresh_floating_button()
                self.logger.debug("已调用 refresh_floating_button 重新显示浮动控件")
            else:
                print(f"[DEBUG] widget 没有 refresh_floating_button 方法")

        except Exception as e:
            self.logger.error(f"懒加载模块 {module_name} 失败: {e}", exc_info=True)
            print(f"[ERROR] 懒加载失败: {e}")
            import traceback
            traceback.print_exc()
            return

        # 记录已经加载
        if hasattr(self, "_loaded_module_indices"):
            self._loaded_module_indices.add(index)
            print(f"[DEBUG] 已将索引 {index} 添加到 _loaded_module_indices")
            print(f"[DEBUG] 当前已加载模块: {self._loaded_module_indices}")
            
            # ⚡ AI 助手模块加载完成后，显示模型下拉框
            if module_key == "ai_assistant":
                # 延迟更新，确保配置已完全加载
                def _update_ai_title():
                    if hasattr(self, '_cached_ai_model_name'):
                        del self._cached_ai_model_name
                        print(f"[DEBUG] 清除 AI 模型名称缓存")
                    
                    # 显示模型下拉框
                    if hasattr(self, 'ai_model_combo'):
                        self.ai_model_combo.setVisible(True)
                        # 加载模型列表
                        self._load_ai_models()
                        print(f"[DEBUG] 显示 AI 模型下拉框")
                
                # 延迟 100ms 执行，确保模块完全初始化
                QTimer.singleShot(100, _update_ai_title)


    def show_settings(self):
        """显示设置界面"""
        # 取消所有导航按钮的选中状态
        for btn in self.nav_buttons:
            btn.setChecked(False)

        # 更新副标题为"设置"
        self.subtitle_label.setText("设置")
        
        # 隐藏模型下拉框
        if hasattr(self, 'ai_model_combo'):
            self.ai_model_combo.setVisible(False)

        # 懒加载设置页面
        if self.settings_widget is None:
            self.logger.info("📝 首次加载设置界面...")
            self.settings_widget = SettingsWidget(module_provider=self.module_provider)
            # 添加到content_stack
            self.settings_page_index = self.content_stack.addWidget(self.settings_widget)
            self.logger.info(f"✅ 设置界面已加载，索引: {self.settings_page_index}")
            
            # 连接设置页面的悬浮窗开关信号
            if hasattr(self.settings_widget, 'general_section'):
                self.settings_widget.general_section.floating_widget_toggled.connect(self._on_floating_toggled)
            
            # 首次加载后刷新滚动条样式
            if hasattr(self.settings_widget, 'refresh_scrollbar_style'):
                self.settings_widget.refresh_scrollbar_style()

        # 切换到设置页面
        self.content_stack.setCurrentIndex(self.settings_page_index)
        self.logger.info("🔄 已切换到设置界面")

    def toggle_theme(self):
        """切换主题（使用QSS系统）"""
        # 防抖：避免快速重复点击
        current_time = time.time() * 1000  # 转换为毫秒
        if hasattr(self, '_last_theme_toggle_time'):
            if current_time - self._last_theme_toggle_time < THEME_TOGGLE_DEBOUNCE_MS:
                print("⚠️ 主题切换过快，已忽略")
                return
        self._last_theme_toggle_time = current_time

        # 获取当前主题并切换（使用统一服务层）
        current_theme = style_service.get_current_theme()

        # 在深色和浅色主题之间切换
        if current_theme == 'modern_dark':
            new_theme = 'modern_light'
            theme_name = 'light'
        else:
            new_theme = 'modern_dark'
            theme_name = 'dark'

        # 应用新主题（使用统一服务层）
        self._apply_theme(new_theme)

        # 保存主题设置到配置文件
        self._save_theme_setting(new_theme)

        # 更新主题按钮图标
        self._update_theme_button_icon()

        # 通知所有已加载的模块更新主题
        self._notify_modules_theme_changed(theme_name)
        
        # 发出主题切换信号
        self.theme_changed.emit(theme_name)
        
        # 同步悬浮窗主题
        if self._floating_widget:
            self._floating_widget.set_theme(theme_name)

        # 刷新设置界面的滚动条样式
        if hasattr(self, 'settings_widget') and self.settings_widget:
            if hasattr(self.settings_widget, 'refresh_scrollbar_style'):
                self.settings_widget.refresh_scrollbar_style()
            # 同步更新设置界面的主题选择下拉框
            if hasattr(self.settings_widget, 'update_theme_selection'):
                self.settings_widget.update_theme_selection(new_theme)

        self.logger.info(f"已切换到{'深色' if new_theme == 'modern_dark' else '浅色'}主题")

    def _apply_theme(self, theme_name: str) -> None:
        """应用主题样式表
        
        清除并重新应用样式表，使用 unpolish/polish 强制刷新样式。
        
        Args:
            theme_name: 主题名称 (如 'modern_dark' 或 'modern_light')
        """
        try:
            # 使用统一服务层应用主题
            style_service.apply_theme(theme_name)
            
            # 获取应用实例
            app = QApplication.instance()
            if app:
                # 强制刷新应用样式
                app.style().unpolish(app)
                app.style().polish(app)
                
            self.logger.debug(f"主题样式已应用: {theme_name}")
            
        except Exception as e:
            self.logger.error(f"应用主题失败: {e}", exc_info=True)

    def _notify_modules_theme_changed(self, theme_name: str) -> None:
        """通知所有已加载的模块主题已切换
        
        遍历所有已加载的模块，调用其 on_theme_changed 方法。
        只通知已经加载的模块，不触发懒加载。
        
        Args:
            theme_name: 主题名称 ('dark' 或 'light')
        """
        if not self.module_provider:
            return

        # 获取所有已加载的模块索引
        loaded_indices = getattr(self, '_loaded_module_indices', set())

        for index in loaded_indices:
            if index < len(self.module_keys):
                module_key = self.module_keys[index]
                try:
                    module = self.module_provider.get_module(module_key)
                    if module:
                        widget = module.get_widget()
                        if widget and hasattr(widget, 'on_theme_changed'):
                            widget.on_theme_changed(theme_name)
                            self.logger.debug(f"已通知模块 {module_key} 主题切换")
                except Exception as e:
                    self.logger.warning(f"通知模块 {module_key} 主题切换失败: {e}")

    def _save_theme_setting(self, theme_name: str):
        """保存主题设置到配置文件"""
        try:
            # 获取配置文件路径（Qt 会自动使用 APP_NAME 创建目录）
            app_data = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.AppDataLocation)
            config_dir = Path(app_data)
            config_dir.mkdir(parents=True, exist_ok=True)
            config_path = config_dir / "ui_settings.json"

            # 读取现有配置（如果存在）
            config = {}
            if config_path.exists():
                try:
                    with open(config_path, 'r', encoding='utf-8') as f:
                        config = json.load(f)
                except Exception as e:
                    self.logger.warning(f"读取配置文件失败，将创建新配置: {e}")

            # 更新主题设置
            config['theme'] = theme_name

            # 保存配置
            with open(config_path, 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=2, ensure_ascii=False)

            self.logger.info(f"主题设置已保存到配置文件: {theme_name}")

        except Exception as e:
            self.logger.error(f"保存主题设置失败: {e}", exc_info=True)

    def _update_theme_button_icon(self):
        """根据当前主题更新主题按钮图标"""
        # 使用统一服务层获取当前主题
        from version import VERSION
        current_theme = style_service.get_current_theme()

        if current_theme == 'modern_dark':
            self.theme_button.setText("☀")  # 深色主题显示太阳图标
            self.theme_button.setToolTip("切换到浅色主题")
            # 更新标题栏文字颜色（深色主题）
            self.titlebar_label.setText(f'<span style="color: #ffffff;">UE Toolkit</span> <span style="color: rgba(255, 255, 255, 0.5);">v{VERSION}</span>')
        else:
            self.theme_button.setText("🌙")  # 浅色主题显示月亮图标
            self.theme_button.setToolTip("切换到深色主题")
            # 更新标题栏文字颜色（浅色主题）
            self.titlebar_label.setText(f'<span style="color: #000000;">UE Toolkit</span> <span style="color: rgba(0, 0, 0, 0.5);">v{VERSION}</span>')

    def center_window(self):
        """居中窗口（保留用于向后兼容）"""
        self._center_window()

    def title_bar_mouse_press(self, event):
        """标题栏鼠标按下"""
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_position = event.globalPosition().toPoint() - self.frameGeometry().topLeft()

    def title_bar_mouse_move(self, event):
        """标题栏鼠标移动"""
        if event.buttons() == Qt.MouseButton.LeftButton and self._drag_position:
            self.move(event.globalPosition().toPoint() - self._drag_position)

    def _get_ai_model_name(self):
        """获取AI助手当前使用的模型名称（带缓存）"""
        # 使用缓存避免每次切换都读磁盘
        if hasattr(self, '_cached_ai_model_name'):
            return self._cached_ai_model_name
        try:
            from core.config.config_manager import ConfigManager
            from pathlib import Path
            
            # 加载AI助手配置
            template_path = Path(__file__).parent.parent / "modules" / "ai_assistant" / "config_template.json"
            config_manager = ConfigManager(
                "ai_assistant", 
                template_path=template_path
            )
            config = config_manager.get_module_config()
            
            provider = config.get("llm_provider", "api")
            model_name = ""
            
            if provider == "api":
                api_config = config.get("api_settings", {})
                model_name = api_config.get('default_model', '')
            elif provider == "ollama":
                ollama_config = config.get("ollama_settings", {})
                model_name = ollama_config.get('default_model', '')
            
            result = f"模型: {model_name}" if model_name else ""
            self._cached_ai_model_name = result
            return result
            
        except Exception as e:
            print(f"[WARNING] 获取AI模型名称失败: {e}")
            return ""
    
    def _load_ai_models(self):
        """加载 AI 助手可用模型列表（使用 config_service，避免重复创建 ConfigManager）"""
        if not hasattr(self, 'ai_model_combo'):
            return
        
        try:
            from core.services import config_service
            from pathlib import Path
            
            # 使用 config_service 获取配置（复用已有的 ConfigManager 实例）
            template_path = Path(__file__).parent.parent / "modules" / "ai_assistant" / "config_template.json"
            config = config_service.get_module_config("ai_assistant", template_path=template_path)
            
            provider = config.get("llm_provider", "api")
            self.logger.debug(f"加载模型列表，llm_provider={provider}")
            
            if provider == "ollama":
                # Ollama: 从本地服务获取模型列表
                ollama_url = config.get("ollama_settings", {}).get("base_url", "http://localhost:11434")
                self.logger.debug(f"Ollama 配置 - URL: {ollama_url}")
                self._load_ollama_models_for_combo(config)
            else:
                # API: 从配置或缓存加载模型列表
                api_url = config.get("api_settings", {}).get("api_url", "")
                self.logger.debug(f"API 配置 - URL: {api_url}")
                self._load_api_models_for_combo(config)
                
        except Exception as e:
            self.logger.error(f"加载模型列表失败: {e}", exc_info=True)
            self.ai_model_combo.clear()
            self.ai_model_combo.addItem("加载失败")
    
    def _load_ollama_models_for_combo(self, config):
        """加载 Ollama 模型列表到下拉框"""
        from threading import Thread
        
        # 先显示加载中状态
        if hasattr(self, 'ai_model_combo'):
            self.ai_model_combo.clear()
            self.ai_model_combo.addItem("正在连接 Ollama...")
        
        # 保存 config 的副本，避免作用域问题
        ollama_url = config.get("ollama_settings", {}).get("base_url", "http://localhost:11434")
        current_model = config.get("ollama_settings", {}).get("default_model", "")
        
        self.logger.info(f"[主窗口] 开始加载 Ollama 模型，URL: {ollama_url}, 当前模型: {current_model}")
        
        def fetch_in_background():
            models = []
            
            try:
                import requests
                self.logger.info(f"[Ollama] 正在连接: {ollama_url}")
                
                session = requests.Session()
                session.trust_env = False
                session.proxies = {'http': None, 'https': None}
                
                response = session.get(f"{ollama_url}/api/tags", timeout=10)
                if response.status_code == 200:
                    data = response.json()
                    models = [m.get("name", "") for m in data.get("models", []) if m.get("name")]
                    self.logger.info(f"[Ollama] 成功获取 {len(models)} 个模型: {models}")
                else:
                    self.logger.error(f"[Ollama] 请求失败，状态码: {response.status_code}")
            except requests.exceptions.ConnectionError as e:
                self.logger.error(f"[Ollama] 连接失败: {e}")
            except requests.exceptions.Timeout as e:
                self.logger.error(f"[Ollama] 连接超时: {e}")
            except Exception as e:
                self.logger.error(f"[Ollama] 获取模型失败: {e}", exc_info=True)
            
            # 创建临时 config 对象用于 UI 更新
            temp_config = {
                "llm_provider": "ollama",
                "ollama_settings": {
                    "base_url": ollama_url,
                    "default_model": current_model
                }
            }
            
            # 通过信号发送到主线程
            self.logger.info(f"[Ollama] 准备发送信号，模型数量: {len(models)}")
            self._ollama_models_loaded.emit(models, temp_config)
        
        thread = Thread(target=fetch_in_background, daemon=True)
        thread.start()
    
    def _on_ollama_models_loaded(self, models, config):
        """Ollama 模型加载完成回调（主线程）"""
        self.logger.info(f"[主窗口] 收到 Ollama 模型加载信号，模型数量: {len(models)}")
        
        if models:
            self._update_model_combo_ui(models, config)
        else:
            self._show_ollama_connection_error()
    
    def _show_ollama_connection_error(self):
        """显示 Ollama 连接错误"""
        if hasattr(self, 'ai_model_combo'):
            self.ai_model_combo.blockSignals(True)
            self.ai_model_combo.clear()
            self.ai_model_combo.addItem("Ollama 未运行")
            self.ai_model_combo.blockSignals(False)
    
    def _load_api_models_for_combo(self, config):
        """加载 API 模型列表到下拉框（从缓存或动态获取）"""
        from threading import Thread
        from pathlib import Path
        import json
        
        # 先显示加载中状态
        if hasattr(self, 'ai_model_combo'):
            self.ai_model_combo.clear()
            self.ai_model_combo.addItem("正在加载模型...")
        
        api_url = config.get("api_settings", {}).get("api_url", "")
        api_key = config.get("api_settings", {}).get("api_key", "")
        current_model = config.get("api_settings", {}).get("default_model", "")
        
        self.logger.info(f"[主窗口] 开始加载 API 模型，URL: {api_url}, 当前模型: {current_model}")
        
        # 尝试从缓存加载
        cache_file = Path.home() / "AppData" / "Roaming" / "ue_toolkit" / "user_data" / "cache" / "api_models_cache.json"
        cached_models = []
        
        try:
            if cache_file.exists():
                cache_data = json.loads(cache_file.read_text(encoding='utf-8'))
                cached_url = cache_data.get('api_url', '')
                
                # 只有 URL 匹配时才使用缓存
                if cached_url == api_url:
                    cached_models = cache_data.get('models', [])
                    self.logger.info(f"[主窗口] 从缓存加载了 {len(cached_models)} 个模型")
        except Exception as e:
            self.logger.warning(f"[主窗口] 读取缓存失败: {e}")
        
        # 如果有缓存，先显示缓存的模型（快速响应）
        if cached_models:
            self._update_model_combo_ui(cached_models, config)
        
        # 后台异步获取最新模型列表
        def fetch_in_background():
            models = []
            
            try:
                if not api_key:
                    self.logger.warning("[主窗口] API Key 为空，跳过模型获取")
                    # 如果没有缓存，使用 default_model
                    if not cached_models:
                        models = [current_model] if current_model else []
                else:
                    from modules.ai_assistant.clients.api_llm_client import ApiLLMClient
                    self.logger.info(f"[主窗口] 正在从 API 获取模型列表...")
                    models = ApiLLMClient.fetch_available_models(api_url, api_key, timeout=10)
                    self.logger.info(f"[主窗口] 成功获取 {len(models)} 个模型")
                    
                    # 保存到缓存
                    try:
                        cache_file.parent.mkdir(parents=True, exist_ok=True)
                        cache_data = {
                            'api_url': api_url,
                            'models': models
                        }
                        cache_file.write_text(json.dumps(cache_data, ensure_ascii=False, indent=2), encoding='utf-8')
                        self.logger.info(f"[主窗口] 模型列表已缓存")
                    except Exception as e:
                        self.logger.warning(f"[主窗口] 保存缓存失败: {e}")
                
            except Exception as e:
                self.logger.error(f"[主窗口] 获取模型列表失败: {e}")
                # 如果获取失败且没有缓存，使用 default_model
                if not cached_models:
                    models = [current_model] if current_model else []
            
            # 通过信号更新 UI（如果获取到了新的模型列表）
            if models and models != cached_models:
                # 使用 QTimer 确保在主线程更新 UI
                from PyQt6.QtCore import QTimer
                QTimer.singleShot(0, lambda: self._update_model_combo_ui(models, config))
        
        # 启动后台线程
        thread = Thread(target=fetch_in_background, daemon=True)
        thread.start()
    
    def _update_model_combo_ui(self, models, config):
        """更新模型下拉框 UI（主线程）"""
        if not hasattr(self, 'ai_model_combo'):
            self.logger.warning("[模型下拉框] ai_model_combo 不存在")
            return
        
        try:
            self.logger.info(f"[模型下拉框] 开始更新 UI，模型数量: {len(models)}")
            
            # 阻止信号触发，避免在填充时触发 _on_ai_model_changed
            self.ai_model_combo.blockSignals(True)
            self.ai_model_combo.clear()
            
            if models:
                # 获取当前配置的模型
                provider = config.get("llm_provider", "api")
                if provider == "ollama":
                    current_model = config.get("ollama_settings", {}).get("default_model", "")
                else:
                    current_model = config.get("api_settings", {}).get("default_model", "")
                
                self.logger.info(f"[模型下拉框] 加载 {len(models)} 个模型，当前模型: {current_model}")
                
                # 添加模型到下拉框
                for model in models:
                    self.ai_model_combo.addItem(model)
                
                self.logger.info(f"[模型下拉框] 已添加 {self.ai_model_combo.count()} 个模型到下拉框")
                
                # 选中当前配置的模型
                if current_model:
                    index = self.ai_model_combo.findText(current_model)
                    if index >= 0:
                        self.ai_model_combo.setCurrentIndex(index)
                        self.logger.info(f"[模型下拉框] 已选中模型: {current_model} (索引 {index})")
                    else:
                        # 如果找不到，选择第一个
                        if self.ai_model_combo.count() > 0:
                            self.ai_model_combo.setCurrentIndex(0)
                            self.logger.info(f"[模型下拉框] 配置的模型未找到，选择第一个: {self.ai_model_combo.currentText()}")
                elif self.ai_model_combo.count() > 0:
                    self.ai_model_combo.setCurrentIndex(0)
                    self.logger.info(f"[模型下拉框] 无配置模型，选择第一个: {self.ai_model_combo.currentText()}")
            else:
                # 根据供应商显示不同的提示
                provider = config.get("llm_provider", "api")
                if provider == "ollama":
                    self.ai_model_combo.addItem("无可用模型（请在设置中启动 Ollama）")
                else:
                    self.ai_model_combo.addItem("无可用模型")
                self.logger.warning(f"[模型下拉框] 没有可用模型")
            
            # 恢复信号
            self.ai_model_combo.blockSignals(False)
            self.logger.info("[模型下拉框] UI 更新完成")
                
        except Exception as e:
            self.logger.error(f"[模型下拉框] 更新失败: {e}", exc_info=True)
            self.ai_model_combo.blockSignals(False)
    
    def _on_ai_model_changed(self):
        """AI 模型切换事件"""
        if not hasattr(self, 'ai_model_combo'):
            return
        
        selected_model = self.ai_model_combo.currentText()
        
        # 过滤掉占位符文本和错误提示
        invalid_texts = [
            "加载中...", 
            "无可用模型", 
            "加载失败",
            "正在连接 Ollama...",
            "Ollama 未运行",
            "无可用模型（请在设置中启动 Ollama）"
        ]
        
        if not selected_model or selected_model in invalid_texts:
            self.logger.debug(f"[模型切换] 跳过无效文本: {selected_model}")
            return
        
        try:
            from core.config.config_manager import ConfigManager
            from pathlib import Path
            from modules.ai_assistant.config_schema import get_ai_assistant_schema
            
            self.logger.info(f"[模型切换] 用户选择模型: {selected_model}")
            
            template_path = Path(__file__).parent.parent / "modules" / "ai_assistant" / "config_template.json"
            config_manager = ConfigManager(
                "ai_assistant", 
                template_path=template_path,
                config_schema=get_ai_assistant_schema()
            )
            config = config_manager.get_module_config()
            
            # 更新配置中的模型
            provider = config.get("llm_provider", "api")
            self.logger.info(f"[模型切换] 当前供应商: {provider}")
            
            if provider == "ollama":
                if "ollama_settings" not in config:
                    config["ollama_settings"] = {}
                old_model = config["ollama_settings"].get("default_model", "")
                config["ollama_settings"]["default_model"] = selected_model
                self.logger.info(f"[模型切换] Ollama 模型: {old_model} -> {selected_model}")
            else:
                if "api_settings" not in config:
                    config["api_settings"] = {}
                old_model = config["api_settings"].get("default_model", "")
                config["api_settings"]["default_model"] = selected_model
                self.logger.info(f"[模型切换] API 模型: {old_model} -> {selected_model}")
            
            # 保存配置
            success = config_manager.save_user_config_fast(config)
            if success:
                self.logger.info(f"[模型切换] ✅ 配置保存成功，模型已切换到: {selected_model}")
            else:
                self.logger.error(f"[模型切换] ❌ 配置保存失败")
            
            # 清除缓存
            if hasattr(self, '_cached_ai_model_name'):
                del self._cached_ai_model_name
                self.logger.debug("[模型切换] 已清除模型名称缓存")
            
        except Exception as e:
            self.logger.error(f"[模型切换] 保存模型配置失败: {e}", exc_info=True)
    
    def _save_window_state(self) -> None:
        """保存窗口位置到配置文件（退出时统一保存，包含窗口状态和当前模块）
        
        只保存窗口的位置（x, y），不保存大小，因为窗口大小是固定的。
        """
        try:
            from core.services import config_service
            
            # 获取应用配置
            app_config = config_service.get_module_config("app")
            if not app_config:
                app_config = {}
            
            # 获取窗口几何信息
            geometry = self.geometry()
            
            app_config["window_state"] = {
                "position": {"x": geometry.x(), "y": geometry.y()},
                "size": {"width": geometry.width(), "height": geometry.height()},
                "maximized": self.isMaximized()
            }
            
            # 保存当前模块状态（合并到同一次保存）
            if hasattr(self, '_current_module_index') and hasattr(self, 'module_keys'):
                index = self._current_module_index
                if 0 <= index < len(self.module_keys):
                    app_config.setdefault("module_state", {})["current_module"] = self.module_keys[index]
            
            # 统一保存配置（immediate=True 立即写入磁盘）
            config_service.save_module_config("app", app_config, backup_reason="exit_save", immediate=True)
            
            # 保存所有运行时累积的脏配置
            config_service.flush_all_configs(backup_reason="exit_save")
            
            self.logger.info(f"退出时保存所有配置完成")
            
        except Exception as e:
            self.logger.error(f"保存退出状态失败: {e}", exc_info=True)
    
    def _save_current_module_on_exit(self):
        """退出时保存当前模块状态（已合并到 _save_window_state，此方法保留为空以兼容旧代码）"""
        # 注意：此方法已废弃，保存逻辑已合并到 _save_window_state() 中
        # 保留此方法是为了避免其他地方的调用出错
        pass
    
    def _restore_window_state(self) -> None:
        """从配置文件恢复窗口位置
        
        只恢复窗口的位置（x, y），不改变窗口大小，因为窗口大小是固定的。
        如果保存的位置无效或不存在，则使用默认位置并居中显示。
        """
        try:
            from core.services import config_service
            
            # 获取应用配置
            app_config = config_service.get_module_config("app")
            if not app_config:
                self.logger.info("未找到应用配置，使用默认窗口位置")
                self._center_window()
                return
            
            window_state = app_config.get("window_state")
            if not window_state:
                self.logger.info("未找到窗口位置配置，使用默认窗口位置")
                self._center_window()
                return
            
            # 支持新格式 {position:{x,y}} 和旧格式 {x,y}
            pos = window_state.get("position", {})
            x = pos.get("x") if pos else window_state.get("x")
            y = pos.get("y") if pos else window_state.get("y")
            
            if x is None or y is None:
                self.logger.info("窗口位置数据不完整，使用默认窗口位置")
                self._center_window()
                return
            
            # 验证窗口位置是否在屏幕边界内
            x, y = self._validate_window_position(x, y)
            
            # 只设置窗口位置，保持当前大小不变
            self.move(x, y)
            
            self.logger.info(f"窗口位置已恢复: x={x}, y={y}")
            
        except Exception as e:
            self.logger.error(f"恢复窗口位置失败: {e}", exc_info=True)
            self._center_window()
    
    def _validate_window_position(self, x: int, y: int) -> tuple:
        """验证窗口位置是否在屏幕边界内，支持多显示器
        
        Args:
            x: 窗口X坐标
            y: 窗口Y坐标
            
        Returns:
            tuple: 验证后的 (x, y)
        """
        try:
            from PyQt6.QtWidgets import QApplication
            from PyQt6.QtCore import QRect
            
            app = QApplication.instance()
            if not app:
                self.logger.warning("无法获取应用实例，使用默认窗口位置")
                return self._get_default_window_position()
            
            # 获取当前窗口大小（固定大小）
            width = self.width()
            height = self.height()
            
            # 创建窗口矩形
            window_rect = QRect(x, y, width, height)
            
            # 检查窗口是否在任何屏幕上可见
            visible_on_screen = False
            for screen in app.screens():
                screen_geometry = screen.geometry()
                # 如果窗口与屏幕有交集，则认为可见
                if screen_geometry.intersects(window_rect):
                    visible_on_screen = True
                    break
            
            if not visible_on_screen:
                # 窗口不在任何屏幕上，使用主屏幕居中
                self.logger.warning("保存的窗口位置不在任何屏幕上，使用主屏幕居中")
                return self._get_default_window_position()
            
            return x, y
            
        except Exception as e:
            self.logger.error(f"验证窗口位置失败: {e}", exc_info=True)
            return self._get_default_window_position()
    
    def _get_default_window_position(self) -> tuple:
        """获取默认窗口位置（居中）
        
        Returns:
            tuple: (x, y)
        """
        try:
            from PyQt6.QtWidgets import QApplication
            
            app = QApplication.instance()
            if app:
                primary_screen = app.primaryScreen()
                if primary_screen:
                    screen_geometry = primary_screen.availableGeometry()
                    # 使用当前窗口大小计算居中位置
                    x = (screen_geometry.width() - self.width()) // 2
                    y = (screen_geometry.height() - self.height()) // 2
                    return x, y
            
            # 如果无法获取屏幕信息，使用固定位置
            return 100, 100
            
        except Exception as e:
            self.logger.error(f"获取默认窗口位置失败: {e}", exc_info=True)
            return 100, 100
    
    def _center_window(self) -> None:
        """将窗口居中显示在主屏幕上"""
        try:
            x, y = self._get_default_window_position()
            self.move(x, y)
            self.logger.debug(f"窗口已居中: x={x}, y={y}")
        except Exception as e:
            self.logger.error(f"居中窗口失败: {e}", exc_info=True)

    # ------------------------------------------------------------------
    # 悬浮窗集成 (Req 6.4, 6.5, 6.7)
    # ------------------------------------------------------------------

    def _init_floating_widget(self):
        """根据配置决定是否创建悬浮窗"""
        try:
            from ui.floating_widget import _load_general_settings
            settings = _load_general_settings()
            if settings.get("floating_widget_enabled", False):
                self._create_floating_widget()
        except Exception as e:
            self.logger.error(f"初始化悬浮窗失败: {e}", exc_info=True)

    def _create_floating_widget(self):
        """创建并显示悬浮窗，连接信号"""
        if self._floating_widget is not None:
            return
        from ui.floating_widget import FloatingWidget
        theme = "dark" if style_service.get_current_theme() == "modern_dark" else "light"
        self._floating_widget = FloatingWidget(main_window=self)
        self._floating_widget.set_theme(theme)
        self._floating_widget.module_selected.connect(self._on_floating_module_selected)
        self._floating_widget.autostart_changed.connect(self._on_floating_autostart_changed)
        self._floating_widget.floating_close_requested.connect(self._on_floating_close_requested)
        self._floating_widget.theme_toggle_requested.connect(self.toggle_theme)
        self._floating_widget.show()

    def _destroy_floating_widget(self):
        """销毁悬浮窗"""
        if self._floating_widget is not None:
            self._floating_widget.hide()
            self._floating_widget.deleteLater()
            self._floating_widget = None

    def _on_floating_toggled(self, enabled: bool):
        """设置页面悬浮窗开关变化"""
        if enabled:
            self._create_floating_widget()
        else:
            self._destroy_floating_widget()

    def _on_floating_module_selected(self, index: int):
        """悬浮窗快捷菜单选择模块"""
        self._allow_auto_activate = True
        if self.isMinimized():
            self.showNormal()
        self.show()
        self.raise_()
        self.activateWindow()
        # Windows 下 activateWindow 受系统限制，需要调用 Win32 API 强制前台
        try:
            import ctypes
            hwnd = int(self.winId())
            ctypes.windll.user32.SetForegroundWindow(hwnd)
        except Exception:
            pass
        self.switch_module(index)

    def _on_floating_autostart_changed(self, enabled: bool):
        """悬浮窗右键菜单切换开机自启 → 同步设置页面"""
        if self.settings_widget and hasattr(self.settings_widget, 'general_section'):
            self.settings_widget.general_section.update_autostart_state(enabled)

    def _on_floating_close_requested(self):
        """悬浮窗右键菜单关闭悬浮窗 → 同步设置页面开关"""
        self._destroy_floating_widget()
        if self.settings_widget and hasattr(self.settings_widget, 'general_section'):
            self.settings_widget.general_section.update_floating_state(False)
        else:
            # 设置页面尚未创建，直接写配置
            try:
                from ui.floating_widget import _load_general_settings, _save_general_settings
                settings = _load_general_settings()
                settings["floating_widget_enabled"] = False
                _save_general_settings(settings)
            except Exception as e:
                self.logger.error(f"保存悬浮窗配置失败: {e}")

    def closeEvent(self, event):
        """窗口关闭事件处理 - 显示关闭确认对话框

        重写此方法以在窗口关闭时显示确认对话框并清理资源。

        Args:
            event: 关闭事件对象
        """
        # 保存窗口状态
        self._save_window_state()
        
        # 保存当前模块状态（退出时统一保存，避免运行时频繁保存）
        self._save_current_module_on_exit()
        
        # 如果已经在关闭过程中，直接接受事件
        if hasattr(self, '_is_closing') and self._is_closing:
            event.accept()
            return
        
        # 检查是否有保存的关闭偏好
        close_preference = self._get_close_preference()
        
        if close_preference == "close":
            # 用户之前选择了直接关闭
            self.logger.info("根据用户偏好直接关闭程序")
            self._perform_close(event)
            return
        elif close_preference == "minimize":
            # 用户之前选择了最小化到托盘
            self.logger.info("根据用户偏好最小化到托盘")
            event.ignore()
            self.hide()
            # 显示托盘提示
            if self.system_tray:
                self.system_tray.show_message(
                    "UE Toolkit",
                    "程序已最小化到系统托盘",
                    duration=2000
                )
            return
        
        # 显示关闭确认对话框
        from ui.dialogs.close_confirmation_dialog import CloseConfirmationDialog
        
        result, remember = CloseConfirmationDialog.ask_close_action(self)
        
        if result == CloseConfirmationDialog.RESULT_CLOSE:
            # 用户选择直接关闭
            if remember:
                self._save_close_preference("close")
            self._perform_close(event)
        elif result == CloseConfirmationDialog.RESULT_MINIMIZE:
            # 用户选择最小化到托盘
            if remember:
                self._save_close_preference("minimize")
            event.ignore()
            self.hide()
            # 显示托盘提示
            if self.system_tray:
                self.system_tray.show_message(
                    "UE Toolkit",
                    "程序已最小化到系统托盘\n双击托盘图标可恢复窗口",
                    duration=3000
                )
        else:
            # 用户取消
            event.ignore()
    
    def _perform_close(self, event):
        """执行关闭操作"""
        try:
            self._is_closing = True
            self.logger.info("主窗口正在关闭，清理资源...")
            
            # 清理授权缓存线程
            try:
                from core.security.license_manager import cleanup_license_cache
                cleanup_license_cache()
            except Exception as e:
                self.logger.warning(f"清理授权缓存线程失败: {e}")
            
            # 清理悬浮窗
            self._destroy_floating_widget()
            
            # 清理系统托盘
            if self.system_tray:
                self.system_tray.cleanup()
            
            # 调用 app_manager 的 quit 方法清理资源
            from core.app_manager import get_app_manager
            app_manager = get_app_manager()
            app_manager.quit()

            # 接受关闭事件
            event.accept()
            self.logger.info("主窗口资源清理完成")
            
        except Exception as e:
            self.logger.error(f"关闭窗口时发生错误: {e}", exc_info=True)
            # 即使出错也要接受关闭事件
            event.accept()
    
    def _get_close_preference(self):
        """获取用户的关闭偏好"""
        try:
            from core.services import config_service
            app_config = config_service.get_module_config("app")
            if app_config:
                preference = app_config.get("close_action_preference")
                self.logger.info(f"读取关闭偏好: {preference}")
                return preference
            return None
        except Exception as e:
            self.logger.error(f"读取关闭偏好失败: {e}", exc_info=True)
            return None
    
    def _save_close_preference(self, preference):
        """保存用户的关闭偏好（immediate=False，延迟到退出时保存）"""
        try:
            from core.services import config_service
            app_config = config_service.get_module_config("app")
            if app_config:
                app_config["close_action_preference"] = preference
                # immediate=False: 仅更新内存，退出时统一保存
                config_service.save_module_config("app", app_config, immediate=False)
                self.logger.debug(f"关闭偏好已更新到内存: {preference}")
            else:
                self.logger.warning("无法获取 app 配置")
        except Exception as e:
            self.logger.error(f"保存关闭偏好失败: {e}", exc_info=True)

    # ⭐ 旧的内联样式方法已删除,现在使用外部QSS系统
    # 样式文件位置: resources/styles/widgets/main_window.qss
    # 主题配置位置: resources/styles/config/themes/modern_dark.py


    def show_feedback_dialog(self):
        """显示问题反馈对话框"""
        from ui.dialogs.feedback_dialog import FeedbackDialog
        
        dialog = FeedbackDialog(self)
        dialog.exec()
    
    # ------------------------------------------------------------------
    # UE 插件连接状态检测
    # ------------------------------------------------------------------
    
    def _start_ue_connection_check(self):
        """启动 UE 插件连接状态轮询（每 5 秒检查一次）"""
        # 信号连接（线程安全）
        self._ue_connection_changed.connect(self._update_ue_status)
        
        self._ue_check_timer = QTimer(self)
        self._ue_check_timer.timeout.connect(self._check_ue_connection)
        self._ue_check_timer.start(5000)
        # 首次延迟 2 秒检查
        QTimer.singleShot(2000, self._check_ue_connection)
    
    def _check_ue_connection(self):
        """检查 UE Remote Control API 是否可用（后台线程，不阻塞 UI）"""
        from threading import Thread
        
        def _ping():
            import requests
            connected = False
            try:
                # 使用 Remote Control API 的 /remote/info 端点检查连接
                response = requests.get('http://127.0.0.1:30010/remote/info', timeout=1.5)
                if response.status_code == 200:
                    data = response.json()
                    # 检查响应是否包含预期的字段
                    if 'HttpRoutes' in data or 'ActivePreset' in data:
                        connected = True
            except Exception:
                connected = False
            # 通过信号安全地通知主线程
            try:
                self._ue_connection_changed.emit(connected)
            except RuntimeError:
                pass  # 窗口已销毁
        
        Thread(target=_ping, daemon=True).start()
    
    def _update_ue_status(self, connected: bool):
        """更新 UE 连接状态 UI"""
        if not hasattr(self, '_ue_status_dot'):
            return
        if connected:
            self._ue_status_dot.setStyleSheet("color: #4CAF50; font-size: 10px;")
            self._ue_status_label.setText("UE 已连接")
            self._ue_status_label.setStyleSheet("color: #4CAF50; font-size: 11px;")
        else:
            self._ue_status_dot.setStyleSheet("color: #666666; font-size: 10px;")
            self._ue_status_label.setText("UE 未连接")
            self._ue_status_label.setStyleSheet("color: #888888; font-size: 11px;")
    
    # ========== 状态信息指示器 ==========

    def show_status(self, label: str, detail: str = "", progress: int = -1):
        """显示状态信息指示器（两行���式）

        Args:
            label:    上行文本，如 "阶段 3/5 · 同步配置"
            detail:   下行文本，如 "正在处理引用兼容…"
            progress: 进度值 0-100，-1 表示不确定进度（循环动画）
        """
        if not hasattr(self, '_status_indicator'):
            return
        self._status_label.setText(label)
        self._status_detail.setText(detail)
        if progress < 0:
            self._status_progress.setRange(0, 0)  # 不确定进度，循环动画
        else:
            self._status_progress.setRange(0, 100)
            self._status_progress.setValue(progress)
        self._status_indicator.setVisible(True)

    def set_status_detail_callback(self, callback):
        """注册详情按钮回调，callback 不为 None 时显示按钮，为 None 时隐藏"""
        if not hasattr(self, '_status_detail_btn'):
            return
        self._status_detail_callback = callback
        self._status_detail_btn.setVisible(callback is not None)

    def _on_status_detail_clicked(self):
        """详情按钮点击"""
        if self._status_detail_callback:
            self._status_detail_callback()

    def set_status_progress_smooth(self, value: int):
        """平滑设置进度条值（0-100），供外部定时器驱动"""
        if not hasattr(self, '_status_progress'):
            return
        self._status_progress.setRange(0, 100)
        self._status_progress.setValue(value)

    def animate_status_progress(self, target: int, duration_ms: int = 400):
        """从当前值平滑动画到 target（0-100），duration_ms 为总时长"""
        if not hasattr(self, '_status_progress'):
            return
        # 停止上一次动画
        if hasattr(self, '_progress_anim_timer') and self._progress_anim_timer is not None:
            self._progress_anim_timer.stop()
            self._progress_anim_timer = None

        self._status_progress.setRange(0, 100)
        start = self._status_progress.value()
        delta = target - start
        if delta == 0:
            return

        step_ms = 16  # ~60fps
        steps = max(1, duration_ms // step_ms)
        current_step = [0]

        def _tick():
            current_step[0] += 1
            t = current_step[0] / steps
            # ease-out cubic
            t_ease = 1 - (1 - t) ** 3
            val = int(start + delta * t_ease)
            self._status_progress.setValue(min(max(val, 0), 100))
            if current_step[0] >= steps:
                self._status_progress.setValue(target)
                self._progress_anim_timer.stop()
                self._progress_anim_timer = None

        timer = QTimer(self)
        timer.setInterval(step_ms)
        timer.timeout.connect(_tick)
        self._progress_anim_timer = timer
        timer.start()

    def hide_status(self):
        """隐藏状态信息指示器"""
        if not hasattr(self, '_status_indicator'):
            return
        # 停止正在进行的进度动画
        if hasattr(self, '_progress_anim_timer') and self._progress_anim_timer is not None:
            self._progress_anim_timer.stop()
            self._progress_anim_timer = None
        self._status_indicator.setVisible(False)
        self._status_progress.setRange(0, 100)
        self._status_progress.setValue(0)
        self._status_label.setText("")
        self._status_detail.setText("")
        # 清理详情按钮
        if hasattr(self, '_status_detail_btn'):
            self._status_detail_btn.setVisible(False)
            self._status_detail_callback = None

    def _start_status_demo(self):
        """演示模式：循环播放进度条 + 两行文本"""
        self._demo_stages = [
            ("阶段 1/5 · 备份项目",       "正在备份配置文件…"),
            ("阶段 2/5 · 重命名目录",     "正在重命名项目文件夹…"),
            ("阶段 3/5 · 同步配置",       "正在处理引用兼容…"),
            ("阶段 4/5 · 更新 .uproject", "正在写入模块信息…"),
            ("阶段 5/5 · 验证结果",       "正在扫描残留引用…"),
        ]
        self._demo_stage_idx = 0
        self._demo_timer = QTimer(self)
        self._demo_timer.timeout.connect(self._demo_tick)
        self._demo_progress = 0.0
        label, detail = self._demo_stages[0]
        self.show_status(label, detail, 0)
        self._demo_timer.start(16)  # ~60fps

    def _demo_tick(self):
        """演示模式的定时器回调"""
        self._demo_progress += 0.4  # 每帧步进 0.4，约 4 秒跑完一圈
        if self._demo_progress >= 100:
            self._demo_progress = 0.0
            self._demo_stage_idx = (self._demo_stage_idx + 1) % len(self._demo_stages)
            label, detail = self._demo_stages[self._demo_stage_idx]
            self._status_label.setText(label)
            self._status_detail.setText(detail)
        self._status_progress.setRange(0, 1000)
        self._status_progress.setValue(int(self._demo_progress * 10))

    def _stop_status_demo(self):
        """停止演示模式"""
        if hasattr(self, '_demo_timer') and self._demo_timer:
            self._demo_timer.stop()
            self._demo_timer = None
        self.hide_status()

    def show_update_badge(self):
        """显示更新小红点"""
        if hasattr(self, 'update_badge'):
            self.update_badge.show()
            self.logger.info("显示更新小红点")
    
    def hide_update_badge(self):
        """隐藏更新小红点"""
        if hasattr(self, 'update_badge'):
            self.update_badge.hide()
            self.logger.info("隐藏更新小红点")
    
    def manual_check_update(self):
        """手动检查更新"""
        try:
            self.logger.info("用户手动触发更新检查")
            
            # 禁用按钮，防止重复点击
            self.check_update_btn.setEnabled(False)
            self.check_update_btn.setText("检查中...")
            # 隐藏小红点
            self.update_badge.hide()
            
            # 获取当前版本号
            from PyQt6.QtWidgets import QApplication
            app = QApplication.instance()
            current_version = app.applicationVersion()
            
            # 创建更新检查线程（强制检查，忽略跳过列表）
            from core.bootstrap.update_checker_integration import UpdateCheckThread
            self.manual_update_thread = UpdateCheckThread(current_version, force_check=True)
            
            # 连接信号
            self.manual_update_thread.update_available.connect(
                lambda version_info: self._on_manual_update_available(version_info, app)
            )
            self.manual_update_thread.check_completed.connect(
                self._on_manual_update_completed
            )
            
            # 启动线程
            self.manual_update_thread.start()
            
        except Exception as e:
            self.logger.error(f"手动检查更新失败: {e}", exc_info=True)
            self.check_update_btn.setEnabled(True)
            self.check_update_btn.setText("检查更新")
            
            # 显示错误提示
            from modules.asset_manager.ui.message_dialog import MessageDialog
            MessageDialog(
                "检查更新失败",
                f"无法检查更新，请稍后重试。\n\n错误: {str(e)}",
                "warning",
                parent=self
            ).exec()
    
    # ⚡ 已移除 _start_license_preload 方法
    # 所有模块现在免费开放，无需授权预加载
    
    def _on_manual_update_available(self, version_info: dict, app):
        """手动检查发现新版本"""
        try:
            self.logger.info(f"发现新版本: {version_info.get('version', '')}")
            
            # 更新按钮文字为"有新版本"并显示小红点
            self.check_update_btn.setText("有新版本")
            self.check_update_btn.setEnabled(True)
            self.show_update_badge()
            
            # 显示更新对话框
            from ui.dialogs.update_dialog import UpdateDialog
            force_update = version_info.get('force_update', False)
            
            result = UpdateDialog.show_update_dialog(
                version_info=version_info,
                force_update=force_update,
                parent=self
            )
            
            # 处理用户选择
            if result == UpdateDialog.RESULT_SKIP:
                # 用户选择跳过此版本
                from core.update_checker import UpdateChecker
                update_checker = UpdateChecker(current_version=app.applicationVersion())
                update_checker.skip_version(version_info.get('version', ''))
                self.logger.info(f"用户跳过版本: {version_info.get('version', '')}")
                
        except Exception as e:
            self.logger.error(f"处理更新信息失败: {e}", exc_info=True)
            self.check_update_btn.setEnabled(True)
            self.check_update_btn.setText("检查更新")
    
    def _on_manual_update_completed(self):
        """手动检查完成（无更新）"""
        try:
            self.logger.info("手动检查完成，没有可用更新")
            
            # 恢复按钮状态
            self.check_update_btn.setEnabled(True)
            self.check_update_btn.setText("检查更新")
            # 隐藏小红点
            self.update_badge.hide()
            
            # 显示提示
            from modules.asset_manager.ui.message_dialog import MessageDialog
            MessageDialog(
                "检查更新",
                "当前已是最新版本！",
                "info",
                parent=self
            ).exec()
            
        except Exception as e:
            self.logger.error(f"处理更新完成事件失败: {e}", exc_info=True)
