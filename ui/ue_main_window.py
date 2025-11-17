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
    QLabel, QPushButton, QFrame, QStackedWidget
)
from PyQt6.QtCore import Qt, QStandardPaths
from PyQt6.QtGui import QIcon, QPixmap
from pathlib import Path

# 使用统一服务层
from core.services import style_service
# 注意：不在模块级别导入 log_service，避免循环导入问题


class UEMainWindow(QMainWindow):
    """主窗口 - 现代化设计"""

    def __init__(self, module_provider=None):
        super().__init__()

        # 初始化 logger（使用旧的 logger，避免导入冲突）
        from core.logger import get_logger
        self.logger = get_logger(__name__)

        self.module_provider = module_provider
        # 模块名称和键（用于懒加载，避免启动时一次性创建所有模块UI）
        self.module_names = ["资产库", "AI 助手", "工程配置", "作者推荐"]
        self.module_keys = ["asset_manager", "ai_assistant", "config_tool", "site_recommendations"]
        self._loaded_module_indices = set()  # 记录已经真正加载过UI的模块索引
        # 不再需要 is_dark_theme，由 style_system 管理
        self.init_ui()

    def init_ui(self):
        """初始化UI"""
        self.setWindowTitle("UE Toolkit - 虚幻引擎工具箱")
        # 使用 16:10 黄金比例（1280x800），符合人类美学
        self.setGeometry(100, 100, 1280, 800)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint)  # 无边框窗口
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)  # 透明背景，支持圆角

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
        title_bar.setFixedHeight(40)

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
            pixmap = QPixmap(str(icon_path))
            # 标题栏图标较小（24x24）
            scaled_pixmap = pixmap.scaled(24, 24, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            logo_icon.setPixmap(scaled_pixmap)
        else:
            # 如果图标不存在，使用后备图标
            logo_icon.setText("◆")
            logo_icon.setObjectName("LogoIconFallback")  # ⭐ 使用QSS样式

        layout.addWidget(logo_icon)

        # 程序名称+版本号（使用HTML实现不同颜色）
        self.titlebar_label = QLabel('<span style="color: #ffffff;">UE Toolkit</span> <span style="color: rgba(255, 255, 255, 0.5);">v1.3</span>')
        self.titlebar_label.setObjectName("TitleBarLabel")  # ⭐ 使用QSS样式
        layout.addWidget(self.titlebar_label)

        layout.addStretch()

        # 窗口控制按钮
        btn_minimize = QPushButton("━")
        btn_minimize.setObjectName("WindowButton")
        btn_minimize.setFixedSize(32, 28)
        btn_minimize.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        btn_minimize.clicked.connect(self.showMinimized)
        layout.addWidget(btn_minimize)

        # 最大化按钮（禁用状态，仅保留视觉统一性）
        btn_maximize = QPushButton("☐")
        btn_maximize.setObjectName("WindowButtonDisabled")
        btn_maximize.setFixedSize(32, 28)
        btn_maximize.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        btn_maximize.setEnabled(False)  # 禁用按钮
        btn_maximize.setToolTip("固定窗口大小")
        layout.addWidget(btn_maximize)

        btn_close = QPushButton("✕")
        btn_close.setObjectName("CloseButton")
        btn_close.setFixedSize(32, 28)
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

    def create_left_panel(self, parent_layout):
        """创建左侧导航面板（文字按钮形式）"""
        left_panel = QFrame()
        left_panel.setObjectName("LeftPanel")
        left_panel.setFixedWidth(200)  # 加宽以容纳文字

        layout = QVBoxLayout(left_panel)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        # 顶部Logo区域
        logo_container = QWidget()
        logo_container.setObjectName("LogoContainer")  # ⭐ 使用QSS样式
        logo_container.setFixedHeight(80)
        logo_layout = QVBoxLayout(logo_container)
        logo_layout.setContentsMargins(12, 20, 12, 20)
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

        layout.addSpacing(16)

        # 导航按钮容器（添加边距）
        nav_container = QWidget()
        nav_container.setObjectName("NavContainer")  # ⭐ 使用QSS样式
        nav_layout = QVBoxLayout(nav_container)
        nav_layout.setContentsMargins(12, 0, 12, 0)
        nav_layout.setSpacing(6)

        # 导航按钮（纯文字）
        modules = self.module_names

        self.nav_buttons = []
        for i, name in enumerate(modules):
            btn = QPushButton(name)
            btn.setObjectName("NavTextButton")
            btn.setFixedHeight(48)
            btn.setCheckable(True)
            btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)

            # 默认选中第一个
            if i == 0:
                btn.setChecked(True)

            btn.clicked.connect(lambda checked, idx=i: self.switch_module(idx))
            nav_layout.addWidget(btn)
            self.nav_buttons.append(btn)

        layout.addWidget(nav_container)

        # 弹性空间
        layout.addStretch()

        parent_layout.addWidget(left_panel)

    def create_right_panel(self, parent_layout):
        """创建右侧内容区"""
        right_panel = QFrame()
        right_panel.setObjectName("RightPanel")

        layout = QVBoxLayout(right_panel)
        layout.setContentsMargins(40, 40, 40, 40)
        layout.setSpacing(0)

        # 标题区域容器（简化：只保留副标题和设置按钮）
        title_container = QWidget()
        title_container.setObjectName("TitleContainer")
        title_layout = QHBoxLayout(title_container)
        title_layout.setContentsMargins(0, 0, 0, 20)
        title_layout.setSpacing(15)

        # 副标题（显示当前模块名称）- 更突出的样式
        self.subtitle_label = QLabel("资产库")
        self.subtitle_label.setObjectName("SubTitle")
        title_layout.addWidget(self.subtitle_label)

        title_layout.addStretch()

        # 主题切换按钮
        btn_theme = QPushButton("☀")  # 默认显示太阳图标（深色主题下）
        btn_theme.setObjectName("ThemeToggleButton")
        btn_theme.setFixedSize(40, 40)
        btn_theme.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        btn_theme.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_theme.setToolTip("切换主题")
        btn_theme.clicked.connect(self.toggle_theme)
        title_layout.addWidget(btn_theme)
        self.theme_button = btn_theme

        # 设置按钮
        btn_settings = QPushButton("⚙")
        btn_settings.setObjectName("SettingsIconButton")
        btn_settings.setFixedSize(40, 40)
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
        for module_name in self.module_names:
            page = self.create_placeholder_page(module_name)
            self.content_stack.addWidget(page)

        layout.addWidget(self.content_stack)

        parent_layout.addWidget(right_panel)

        # 根据当前主题更新按钮图标
        self._update_theme_button_icon()

    def create_placeholder_page(self, module_name):
        """创建占位页面（简约设计）"""
        page = QWidget()
        page.setObjectName("PlaceholderPage")

        layout = QVBoxLayout(page)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.setSpacing(24)

        # 模块图标
        icon_map = {
            "资产库": "📦",
            "工程配置": "⚙️",
            "作者推荐": "🔗",
            "AI 助手": "🤖"
        }

        icon_label = QLabel(icon_map.get(module_name, "📄"))
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
        # 取消所有导航按钮的选中状态
        for btn in self.nav_buttons:
            btn.setChecked(False)

        # 选中当前按钮
        if 0 <= index < len(self.nav_buttons):
            self.nav_buttons[index].setChecked(True)

        # 首次切换到该模块时懒加载真实UI
        self._ensure_module_loaded(index)

        # 切换内容
        if self.content_stack is not None:
            self.content_stack.setCurrentIndex(index)

        # 更新副标题为模块名称
        if hasattr(self, "module_names") and 0 <= index < len(self.module_names):
            self.subtitle_label.setText(self.module_names[index])
    def _ensure_module_loaded(self, index: int) -> None:
        """确保指定索引的模块UI已加载（懒加载）

        在第一次切换到某个模块时，才真正创建对应的模块UI，
        避免在应用启动阶段一次性创建所有模块导致卡顿。
        """
        # 已经加载过，直接返回
        if index in getattr(self, "_loaded_module_indices", set()):
            return

        if not self.module_provider:
            return

        if not hasattr(self, "module_keys") or index < 0 or index >= len(self.module_keys):
            return

        module_key = self.module_keys[index]
        module_name = (
            self.module_names[index]
            if hasattr(self, "module_names") and 0 <= index < len(self.module_names)
            else module_key
        )

        try:
            module = self.module_provider.get_module(module_key)
            if not module:
                return

            widget = module.get_widget()
            if not widget:
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
                print(f"✅ 懒加载模块 UI 成功: {module_name}")

            # ⚡ 关键修复：懒加载后强制重新应用全局样式
            # 这样可以确保滚动条等样式正确应用
            from PyQt6.QtWidgets import QApplication
            app = QApplication.instance()
            if app:
                # 获取当前样式表并重新应用，强制刷新所有控件样式
                current_stylesheet = app.styleSheet()
                app.setStyleSheet("")  # 先清空
                app.setStyleSheet(current_stylesheet)  # 再重新应用
                print(f"   🎨 已刷新全局样式")

        except Exception as e:
            print(f"⚠️ 懒加载模块 {module_name} 失败: {e}")
            return

        # 记录已经加载
        if hasattr(self, "_loaded_module_indices"):
            self._loaded_module_indices.add(index)


    def show_settings(self):
        """显示设置"""
        # 取消所有导航按钮的选中状态
        for btn in self.nav_buttons:
            btn.setChecked(False)

        # 更新副标题为"设置"
        self.subtitle_label.setText("设置")

        print("设置界面（待实现）")

    def toggle_theme(self):
        """切换主题（使用QSS系统）"""
        # 防抖：避免快速重复点击
        current_time = time.time() * 1000  # 转换为毫秒
        if hasattr(self, '_last_theme_toggle_time'):
            if current_time - self._last_theme_toggle_time < 300:  # 300ms 防抖
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
        app = QApplication.instance()
        style_service.apply_theme(app, new_theme)

        # 保存主题设置到配置文件
        self._save_theme_setting(new_theme)

        # 更新主题按钮图标
        if new_theme == 'modern_dark':
            self.theme_button.setText("☀")  # 深色主题显示太阳图标
            self.theme_button.setToolTip("切换到浅色主题")
            # 更新标题栏文字颜色（深色主题）
            self.titlebar_label.setText('<span style="color: #ffffff;">UE Toolkit</span> <span style="color: rgba(255, 255, 255, 0.5);">v1.3</span>')
        else:
            self.theme_button.setText("🌙")  # 浅色主题显示月亮图标
            self.theme_button.setToolTip("切换到深色主题")
            # 更新标题栏文字颜色（浅色主题）
            self.titlebar_label.setText('<span style="color: #000000;">UE Toolkit</span> <span style="color: rgba(0, 0, 0, 0.5);">v1.3</span>')

        # 通知所有已加载的模块更新主题（只更新已经加载的模块，不触发懒加载）
        if self.module_provider and hasattr(self, '_loaded_module_indices'):
            for i, module_key in enumerate(self.module_keys):
                # 只更新已经加载过的模块
                if i not in self._loaded_module_indices:
                    continue

                try:
                    module = self.module_provider.get_module(module_key)
                    if module:
                        widget = module.get_widget()
                        if widget and hasattr(widget, 'update_theme'):
                            widget.update_theme(theme_name)
                except Exception as e:
                    print(f"⚠️ 更新模块 {module_key} 主题失败: {e}")

        print(f"✓ 已切换到{'深色' if new_theme == 'modern_dark' else '浅色'}主题")

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
        current_theme = style_service.get_current_theme()

        if current_theme == 'modern_dark':
            self.theme_button.setText("☀")  # 深色主题显示太阳图标
            self.theme_button.setToolTip("切换到浅色主题")
            # 更新标题栏文字颜色（深色主题）
            self.titlebar_label.setText('<span style="color: #ffffff;">UE Toolkit</span> <span style="color: rgba(255, 255, 255, 0.5);">v1.3</span>')
        else:
            self.theme_button.setText("🌙")  # 浅色主题显示月亮图标
            self.theme_button.setToolTip("切换到深色主题")
            # 更新标题栏文字颜色（浅色主题）
            self.titlebar_label.setText('<span style="color: #000000;">UE Toolkit</span> <span style="color: rgba(0, 0, 0, 0.5);">v1.3</span>')

    def center_window(self):
        """居中窗口"""
        screen = self.screen()
        if screen:
            screen_geometry = screen.availableGeometry()
            x = (screen_geometry.width() - self.width()) // 2
            y = (screen_geometry.height() - self.height()) // 2
            self.move(x, y)

    def title_bar_mouse_press(self, event):
        """标题栏鼠标按下"""
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_position = event.globalPosition().toPoint() - self.frameGeometry().topLeft()

    def title_bar_mouse_move(self, event):
        """标题栏鼠标移动"""
        if event.buttons() == Qt.MouseButton.LeftButton and self._drag_position:
            self.move(event.globalPosition().toPoint() - self._drag_position)

    def closeEvent(self, event):
        """窗口关闭事件处理

        重写此方法以在窗口关闭时自动清理资源。

        Args:
            event: 关闭事件对象
        """
        self.logger.info("主窗口正在关闭，清理资源...")

        try:
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

    # ⭐ 旧的内联样式方法已删除,现在使用外部QSS系统
    # 样式文件位置: resources/styles/widgets/main_window.qss
    # 主题配置位置: resources/styles/config/themes/modern_dark.py

