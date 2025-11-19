"""
UILauncher - UI 启动组件

负责用户界面的准备和显示，包括：
- 主题配置加载
- UI 准备阶段（主题应用、Splash Screen创建）
- UI 显示阶段（主窗口创建和显示）
"""

import json
from pathlib import Path
from typing import Optional

from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import QStandardPaths

from core.logger import get_logger
from core.single_instance import SingleInstanceManager
from core.utils.style_system import style_system
from ui.splash_screen import SplashScreen
from ui.ue_main_window import UEMainWindow


class UILauncher:
    """UI 启动器"""

    def __init__(self):
        self.splash: Optional[SplashScreen] = None
        self.main_window: Optional[UEMainWindow] = None
        self.current_theme: str = "modern_dark"
        self.logger = get_logger(__name__)

    def prepare_ui(self, app: QApplication) -> SplashScreen:
        """准备 UI（创建 Splash Screen 并应用主题）

        Args:
            app: QApplication 实例

        Returns:
            SplashScreen: Splash Screen 实例
        """
        # 占位符：将在任务 3.2 中实现
        pass

    def show_ui(self,
                app: QApplication,
                module_provider,
                single_instance: SingleInstanceManager) -> bool:
        """显示 UI（创建主窗口并显示）

        Args:
            app: QApplication 实例
            module_provider: 模块提供者
            single_instance: 单实例管理器

        Returns:
            bool: 是否成功
        """
        # 占位符：将在任务 3.3 中实现
        pass

    def _load_theme_config(self) -> str:
        """加载主题配置

        Returns:
            str: 主题名称
        """
        try:
            # 从 AppData/ue_toolkit/ui_settings.json 读取主题配置
            app_data = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.AppDataLocation)
            config_path = Path(app_data) / "ue_toolkit" / "ui_settings.json"

            if config_path.exists():
                with open(config_path, 'r', encoding='utf-8') as f:
                    config = json.load(f)

                saved_theme = config.get('theme', 'modern_dark')

                # 支持旧版本配置映射（dark → modern_dark, light → modern_light）
                theme_mapping = {
                    'dark': 'modern_dark',
                    'light': 'modern_light'
                }
                theme = theme_mapping.get(saved_theme, saved_theme)

                self.logger.info(f"已加载保存的主题: {saved_theme} -> {theme}")
                return theme
            else:
                self.logger.info("未找到主题配置，使用默认主题: modern_dark")
                return "modern_dark"

        except Exception as e:
            # 失败时使用默认主题 modern_dark
            self.logger.warning(f"加载主题设置失败，使用默认主题: {e}")
            return "modern_dark"

    def _apply_theme(self, app: QApplication, theme: str) -> None:
        """应用主题

        Args:
            app: QApplication 实例
            theme: 主题名称
        """
        # 占位符：将在任务 3.2 中实现
        pass

    def _create_splash(self, theme: str) -> SplashScreen:
        """创建 Splash Screen

        Args:
            theme: 主题名称

        Returns:
            SplashScreen: Splash Screen 实例
        """
        # 占位符：将在任务 3.2 中实现
        pass

    def _create_main_window(self, module_provider) -> UEMainWindow:
        """创建主窗口

        Args:
            module_provider: 模块提供者

        Returns:
            UEMainWindow: 主窗口实例
        """
        # 占位符：将在任务 3.3 中实现
        pass
