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
    QLabel, QPushButton, QFrame, QStackedWidget, QScrollArea
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
from version import APP_NAME, get_version_string

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

    def init_ui(self):
        """初始化UI"""
        # 设置窗口标题（从 version.py 读取版本号）
        self.setWindowTitle(f"{APP_NAME} {get_version_string()} - 虚幻引擎工具箱")
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
        
        # 加载第一个模块
        self._ensure_module_loaded(0)
        
        # 如果是资产库模块，异步加载资产
        if hasattr(self, "module_keys") and len(self.module_keys) > 0:
            if self.module_keys[0] == "asset_manager" and self.module_provider:
                self.logger.info("检测到资产库模块，开始加载资产")
                asset_manager = self.module_provider.get_module("asset_manager")
                if asset_manager:
                    # 确保UI已创建
                    asset_widget = asset_manager.get_widget()
                    self.logger.info(f"获取资产库UI组件: {asset_widget}")
                    if asset_widget and hasattr(asset_widget, "load_assets_async"):
                        # 使用异步加载资产，避免阻塞UI
                        self.logger.info("开始异步加载资产")
                        asset_widget.load_assets_async(on_complete)
                    elif on_complete:
                        self.logger.warning("资产库UI组件不支持异步加载，直接调用回调")
                        on_complete()
                else:
                    self.logger.error("无法获取资产库模块")
                    if on_complete:
                        on_complete()
            elif on_complete:
                self.logger.warning("不是资产库模块，直接调用回调")
                on_complete()
        elif on_complete:
            self.logger.warning("没有模块键，直接调用回调")
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

        # UE 插件连接状态指示器
        self._ue_status_dot = QLabel("●")
        self._ue_status_dot.setStyleSheet("color: #666666; font-size: 9px;")
        self._ue_status_dot.setFixedWidth(10)
        layout.addWidget(self._ue_status_dot)
        
        self._ue_status_label = QLabel("UE 未连接")
        self._ue_status_label.setStyleSheet("color: rgba(255,255,255,0.35); font-size: 11px;")
        layout.addWidget(self._ue_status_label)
        
        layout.addSpacing(8)

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
        """在标题栏创建授权状态（仅试用时显示）"""
        from core.security.license_manager import _DEV_MODE

        # 容器：胶囊形状，包含状态文字 + 升级按钮
        self._license_container = QWidget()
        self._license_container.setObjectName("LicenseCapsule")
        self._license_container.setFixedHeight(26)
        cap_layout = QHBoxLayout(self._license_container)
        cap_layout.setContentsMargins(10, 0, 4, 0)
        cap_layout.setSpacing(6)

        self.license_status_label = QLabel()
        self.license_status_label.setObjectName("LicenseCapsuleText")
        cap_layout.addWidget(self.license_status_label)

        self.license_activate_btn = QPushButton("升级")
        self.license_activate_btn.setObjectName("LicenseCapsuleBtn")
        self.license_activate_btn.setFixedSize(44, 20)
        self.license_activate_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.license_activate_btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.license_activate_btn.clicked.connect(self._on_activate_clicked)
        cap_layout.addWidget(self.license_activate_btn)

        parent_layout.addWidget(self._license_container)

        # 默认隐藏，只在试用/未授权时显示
        self._license_container.hide()

        if not _DEV_MODE:
            self._update_license_status_ui()

    def _update_license_status_ui(self):
        """根据本地授权数据更新标题栏状态"""
        try:
            from core.security.license_manager import get_license_status
            import time as _time
            from core.security.machine_id import MachineID
            from core.security.license_crypto import LicenseCrypto

            status = get_license_status()
            
            if status == "permanent":
                # 永久授权 — 隐藏所有提示
                self._license_container.hide()
            elif status == "daily":
                # 天卡 — 显示剩余时间
                machine = MachineID()
                crypto = LicenseCrypto(machine.get_machine_id())
                data = crypto.load()
                if data:
                    expire = data.get("expire_time")
                    if expire:
                        remaining_sec = max(0, expire - _time.time())
                        remaining_hours = int(remaining_sec / 3600)
                        remaining_days = int(remaining_sec / 86400)
                        if remaining_days >= 1:
                            self.license_status_label.setText(f"剩余 {remaining_days}天")
                        else:
                            self.license_status_label.setText(f"剩余 {remaining_hours}小时")
                        self._license_container.show()
                    else:
                        self._license_container.hide()
                else:
                    self._license_container.hide()
            else:
                # 无授权或已过期 — 隐藏（Freemium 模式不强制显示）
                self._license_container.hide()
        except Exception as e:
            self.logger.warning(f"更新授权状态UI失败: {e}")
            self._license_container.hide()

    def _get_license_manager(self):
        """获取或创建 LicenseManager 实例（缓存复用）"""
        if not hasattr(self, '_license_manager') or self._license_manager is None:
            from core.security.license_manager import LicenseManager
            self._license_manager = LicenseManager()
        return self._license_manager

    def _on_activate_clicked(self):
        """标题栏升级按钮点击"""
        try:
            lm = self._get_license_manager()
            # 试用中点击升级 → 升级模式（引导输入永久码）
            if lm._show_activation_dialog(upgrade_mode=True):
                # 激活成功后刷新缓存的 LicenseManager（授权数据已变更）
                self._license_manager = None
                self._update_license_status_ui()
        except Exception as e:
            self.logger.error(f"激活失败: {e}", exc_info=True)

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

        title_layout.addStretch()

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
        # 检查模块访问权限
        if not self._check_module_access(index):
            return
        
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
            
            # 如果是AI助手模块，添加当前模型名称（灰色小字）
            if module_name == "AI 助手":
                model_info = self._get_ai_model_name()
                if model_info:
                    # 使用HTML设置不同样式：标题正常，模型名称灰色小字
                    self.subtitle_label.setText(
                        f'{module_name}    '
                        f'<span style="font-size: 14px; color: #888; font-weight: normal;">{model_info}</span>'
                    )
                else:
                    self.subtitle_label.setText(module_name)
            else:
                self.subtitle_label.setText(module_name)

        # 首次切换到该模块时，延迟到下一个事件循环再懒加载，避免阻塞 UI
        if index not in getattr(self, "_loaded_module_indices", set()):
            from PyQt6.QtCore import QTimer
            QTimer.singleShot(0, lambda idx=index: self._ensure_module_loaded(idx))
    
    def _check_module_access(self, index: int) -> bool:
        """检查模块访问权限
        
        Args:
            index: 模块索引
            
        Returns:
            True: 允许访问
            False: 拒绝访问（弹出激活引导）
        """
        # 免费模块列表（索引）
        # 0: 我的工程, 1: 资产管理, 4: 站点推荐
        FREE_MODULE_INDICES = [0, 1, 4]
        
        # 如果是免费模块，直接放行
        if index in FREE_MODULE_INDICES:
            return True
        
        # 付费模块：检查授权状态
        from core.security.license_manager import get_license_status
        status = get_license_status()
        
        # 有效授权：放行
        if status in ["permanent", "daily"]:
            return True
        
        # 无授权或已过期：弹出激活引导
        self._show_activation_guide(status)
        return False
    
    def _show_activation_guide(self, license_status: str):
        """显示激活引导对话框
        
        Args:
            license_status: 当前授权状态 ("none", "expired")
        """
        from ui.dialogs.activation_guide_dialog import ActivationGuideDialog
        from core.security.license_manager import LicenseManager
        
        lm = LicenseManager()
        purchase_link = lm._get_purchase_link()
        
        while True:
            dialog = ActivationGuideDialog(
                parent=self,
                purchase_link=purchase_link,
                license_status=license_status
            )
            dialog.exec()
            
            if dialog.result_action != ActivationGuideDialog.RESULT_ACTIVATED:
                # 用户取消，不做任何操作
                return
            
            # 用户输入了激活码，尝试激活
            key = dialog.get_activation_key()
            if not key:
                continue
            
            # 显示加载状态
            dialog.set_loading(True)
            
            # 尝试激活
            if lm.activate(key):
                # 激活成功
                dialog.set_status("激活成功！", is_error=False)
                from PyQt6.QtCore import QTimer
                QTimer.singleShot(1000, dialog.accept)
                
                # 刷新授权状态UI
                if hasattr(self, '_update_license_status_ui'):
                    self._update_license_status_ui()
                
                return
            else:
                # 激活失败
                dialog.set_loading(False)
                dialog.set_status("激活码无效或已被使用，请检查后重试", is_error=True)
                # 继续循环，让用户重试

        # 选中当前按钮
        if 0 <= index < len(self.nav_buttons):
            self.nav_buttons[index].setChecked(True)

        # 先切换页面（立即响应），再异步懒加载
        if self.content_stack is not None:
            self.content_stack.setCurrentIndex(index)

        # 更新副标题为模块名称
        if hasattr(self, "module_names") and 0 <= index < len(self.module_names):
            module_name = self.module_names[index]
            
            # 如果是AI助手模块，添加当前模型名称（灰色小字）
            if module_name == "AI 助手":
                model_info = self._get_ai_model_name()
                if model_info:
                    # 使用HTML设置不同样式：标题正常，模型名称灰色小字
                    self.subtitle_label.setText(
                        f'{module_name}    '
                        f'<span style="font-size: 14px; color: #888; font-weight: normal;">{model_info}</span>'
                    )
                else:
                    self.subtitle_label.setText(module_name)
            else:
                self.subtitle_label.setText(module_name)

        # 首次切换到该模块时，延迟到下一个事件循环再懒加载，避免阻塞 UI
        if index not in getattr(self, "_loaded_module_indices", set()):
            from PyQt6.QtCore import QTimer
            QTimer.singleShot(0, lambda idx=index: self._ensure_module_loaded(idx))
        
    def _ensure_module_loaded(self, index: int) -> None:
        """确保指定索引的模块UI已加载（懒加载）

        在第一次切换到某个模块时，才真正创建对应的模块UI，
        避免在应用启动阶段一次性创建所有模块导致卡顿。
        """
        # 已经加载过，直接返回
        if index in getattr(self, "_loaded_module_indices", set()):
            self.logger.debug(f"模块索引 {index} 已加载，跳过")
            return

        if not self.module_provider:
            self.logger.warning(f"module_provider 为 None，无法加载模块索引 {index}")
            return

        if not hasattr(self, "module_keys") or index < 0 or index >= len(self.module_keys):
            self.logger.warning(f"模块索引 {index} 超出范围或 module_keys 不存在")
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
                if old_widget is not None:
                    self.content_stack.removeWidget(old_widget)
                    old_widget.deleteLater()

                # 在相同位置插入新的真实UI
                self.content_stack.insertWidget(index, widget)

                # 确保显示的是刚加载的模块
                self.content_stack.setCurrentIndex(index)
                self.logger.info(f"懒加载模块 UI 成功: {module_name}")
                print(f"[SUCCESS] 懒加载模块 UI 成功: {module_name}")

            # ⚡ 只对新加载的模块 widget 刷新样式，避免全局重刷导致卡顿
            widget.style().unpolish(widget)
            widget.style().polish(widget)
            widget.update()

        except Exception as e:
            self.logger.error(f"懒加载模块 {module_name} 失败: {e}", exc_info=True)
            return

        # 记录已经加载
        if hasattr(self, "_loaded_module_indices"):
            self._loaded_module_indices.add(index)


    def show_settings(self):
        """显示设置界面"""
        # 取消所有导航按钮的选中状态
        for btn in self.nav_buttons:
            btn.setChecked(False)

        # 更新副标题为"设置"
        self.subtitle_label.setText("设置")

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

        print(f"✓ 已切换到{'深色' if new_theme == 'modern_dark' else '浅色'}主题")

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
            # 获取配置文件路径
            app_data = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.AppDataLocation)
            config_dir = Path(app_data) / "ue_toolkit"
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
    
    def _save_window_state(self) -> None:
        """保存窗口位置到配置文件
        
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
            
            # 只保存窗口位置，不保存大小（窗口大小是固定的）
            window_state = {
                "x": geometry.x(),
                "y": geometry.y()
            }
            
            app_config["window_state"] = window_state
            
            # 保存配置
            config_service.save_module_config("app", app_config)
            
            self.logger.debug(f"窗口位置已保存: x={window_state['x']}, y={window_state['y']}")
            
        except Exception as e:
            self.logger.error(f"保存窗口位置失败: {e}", exc_info=True)
    
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
            
            # 提取窗口位置（只恢复位置，不恢复大小）
            x = window_state.get("x")
            y = window_state.get("y")
            
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
        """保存用户的关闭偏好"""
        try:
            from core.services import config_service
            app_config = config_service.get_module_config("app")
            if app_config:
                app_config["close_action_preference"] = preference
                config_service.save_module_config("app", app_config)
                self.logger.info(f"✅ 保存关闭偏好成功: {preference}")
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
        """检查 UE RPC 服务器是否真正可用（后台线程，不阻塞 UI）"""
        from threading import Thread
        
        def _ping():
            import socket
            import struct
            import json as _json
            connected = False
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(1.5)
                sock.connect(('127.0.0.1', 9998))
                ping = _json.dumps({"action": "ping"}).encode('utf-8')
                sock.sendall(struct.pack('!I', len(ping)) + ping)
                prefix = sock.recv(4)
                if len(prefix) == 4:
                    resp_len = struct.unpack('!I', prefix)[0]
                    if 0 < resp_len < 65536:
                        _resp = sock.recv(min(resp_len, 4096))
                        if len(_resp) > 0:
                            connected = True
                sock.close()
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
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.warning(
                self,
                "检查更新失败",
                f"无法检查更新，请稍后重试。\n\n错误: {str(e)}"
            )
    
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
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.information(
                self,
                "检查更新",
                "当前已是最新版本！"
            )
            
        except Exception as e:
            self.logger.error(f"处理更新完成事件失败: {e}", exc_info=True)
