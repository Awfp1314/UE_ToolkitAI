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
        # 加载主题配置
        self.current_theme = self._load_theme_config()

        # 应用主题到 QApplication
        self._apply_theme(app, self.current_theme)

        # 创建 Splash Screen
        self.splash = self._create_splash(self.current_theme)

        self.logger.info("UI 准备阶段完成")
        return self.splash

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
        try:
            # 创建主窗口
            self.main_window = self._create_main_window(module_provider)

            # 启动单实例服务器（防御性检查）
            if single_instance is not None:
                single_instance.start_server(self.main_window)
                self.logger.info("单实例服务器已启动")
            else:
                self.logger.warning("single_instance 为 None，跳过单实例服务器启动")

            # ⚡ 优化：先关闭启动界面并显示主窗口，再加载资产
            # 关闭 Splash
            if self.splash:
                self.splash.finish()
                self.logger.info("启动界面已关闭")

            # 显示主窗口
            if self.main_window:
                self.main_window.show()
                self.main_window.raise_()
                self.main_window.activateWindow()
                self.logger.info("主窗口已显示")

            # ⚡ 延迟加载初始模块，避免阻塞窗口显示
            from PyQt6.QtCore import QTimer
            def load_initial_module():
                self.logger.info("开始加载初始模块")
                if self.main_window:
                    def on_complete():
                        self.logger.info("初始模块加载完成")
                        # 延迟检查资产库路径
                        QTimer.singleShot(100, lambda: self._check_asset_library_path(app, module_provider))
                    
                    self.main_window.load_initial_module(on_complete=on_complete)

            # ⚡ 延迟到下一个事件循环加载初始模块，让窗口先完成绘制
            QTimer.singleShot(0, load_initial_module)

            return True

        except Exception as e:
            self.logger.error(f"显示 UI 失败: {e}", exc_info=True)
            return False

    def _load_theme_config(self) -> str:
        """加载主题配置

        Returns:
            str: 主题名称
        """
        try:
            # 从 AppData/ue_toolkit/ui_settings.json 读取主题配置（Qt 自动使用 APP_NAME）
            app_data = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.AppDataLocation)
            config_path = Path(app_data) / "ui_settings.json"

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
        # 应用主题到 QApplication
        self.logger.info(f"正在应用QSS主题: {theme}...")
        style_system.apply_theme(app, theme)
        self.logger.info("✅ QSS主题应用成功")

    def _create_splash(self, theme: str) -> SplashScreen:
        """创建 Splash Screen

        Args:
            theme: 主题名称

        Returns:
            SplashScreen: Splash Screen 实例
        """
        # 根据主题选择 Splash 主题（dark 或 light）
        splash_theme = "dark" if "dark" in theme.lower() else "light"

        # 创建 SplashScreen 实例
        splash = SplashScreen(theme=splash_theme)

        # 注册日志处理器
        splash.register_log_handler()

        # 显示 Splash
        splash.show()

        # 刷新 UI
        from PyQt6.QtWidgets import QApplication as QApp
        QApp.processEvents()

        self.logger.info("启动加载界面已显示")
        return splash

    def _create_main_window(self, module_provider) -> UEMainWindow:
        """创建主窗口

        Args:
            module_provider: 模块提供者

        Returns:
            UEMainWindow: 主窗口实例
        """
        self.logger.info("创建主窗口")
        main_window = UEMainWindow(module_provider)
        self.logger.info("主窗口创建完成")
        return main_window
    
    def _check_asset_library_path(self, app: QApplication, module_provider):
        """检查资产库路径是否有效
        
        Args:
            app: QApplication 实例
            module_provider: 模块提供者
        """
        try:
            from PyQt6.QtCore import QTimer
            
            # 延迟检查，确保主窗口已完全显示
            def do_check():
                try:
                    # 获取资产管理器模块
                    asset_module = module_provider.get_module("asset_manager")
                    if not asset_module or not hasattr(asset_module, 'instance'):
                        self.logger.info("资产管理器模块未加载，跳过路径检查")
                        return
                    
                    asset_instance = asset_module.instance
                    if not hasattr(asset_instance, 'logic') or not asset_instance.logic:
                        self.logger.info("资产管理器逻辑层未初始化，跳过路径检查")
                        return
                    
                    asset_logic = asset_instance.logic
                    
                    # 获取当前资产库路径
                    current_path = asset_logic.get_asset_library_path()
                    
                    # 检查路径是否有效
                    path_valid = False
                    if current_path:
                        if current_path.exists():
                            path_valid = True
                            self.logger.info(f"资产库路径有效: {current_path}")
                        else:
                            self.logger.warning(f"资产库路径不存在: {current_path}")
                    else:
                        self.logger.warning("资产库路径未设置")
                    
                    # 如果路径无效，显示设置弹窗
                    if not path_valid:
                        self._show_asset_path_setup_dialog(app, module_provider, asset_logic, str(current_path) if current_path else "")
                        
                except Exception as e:
                    self.logger.error(f"检查资产库路径失败: {e}", exc_info=True)
            
            # 延迟1秒执行检查，确保UI已稳定
            QTimer.singleShot(1000, do_check)
            
        except Exception as e:
            self.logger.error(f"资产库路径检查异常: {e}", exc_info=True)
    
    def _show_asset_path_setup_dialog(self, app: QApplication, module_provider, asset_logic, current_path: str):
        """显示资产库路径设置弹窗
        
        Args:
            app: QApplication 实例
            module_provider: 模块提供者
            asset_logic: 资产管理器逻辑层
            current_path: 当前路径
        """
        try:
            from ui.asset_path_setup_dialog import AssetPathSetupDialog
            
            self.logger.info("显示资产库路径设置弹窗")
            
            # 创建弹窗
            dialog = AssetPathSetupDialog(parent=self.main_window, current_path=current_path)
            
            # 连接路径确认信号
            def on_path_confirmed(path_str: str):
                try:
                    from pathlib import Path
                    lib_path = Path(path_str.strip())
                    
                    # 保存路径
                    if asset_logic.set_asset_library_path(lib_path):
                        self.logger.info(f"✅ 资产库路径已保存: {lib_path}")
                        
                        # 刷新资产管理器UI
                        self._refresh_asset_manager_ui(module_provider)
                    else:
                        self.logger.error(f"❌ 保存资产库路径失败")
                        
                except Exception as e:
                    self.logger.error(f"保存资产库路径异常: {e}", exc_info=True)
            
            dialog.path_confirmed.connect(on_path_confirmed)
            
            # 显示弹窗（模态）
            dialog.exec()
            
        except Exception as e:
            self.logger.error(f"显示资产库路径设置弹窗失败: {e}", exc_info=True)
    
    def _refresh_asset_manager_ui(self, module_provider):
        """刷新资产管理器UI
        
        Args:
            module_provider: 模块提供者
        """
        try:
            # 获取资产管理器模块
            asset_module = module_provider.get_module("asset_manager")
            if not asset_module or not hasattr(asset_module, 'instance'):
                self.logger.warning("无法获取资产管理器模块")
                return
            
            asset_instance = asset_module.instance
            if not hasattr(asset_instance, 'ui') or not asset_instance.ui:
                self.logger.warning("无法获取资产管理器UI")
                return
            
            asset_ui = asset_instance.ui
            
            # 重置已加载标志，强制重新加载
            if hasattr(asset_ui, '_assets_loaded'):
                asset_ui._assets_loaded = False
                self.logger.info("已重置资产加载标志")
            
            # 触发加载 - 使用正确的方法名 load_assets_async
            if hasattr(asset_ui, 'load_assets_async'):
                asset_ui.load_assets_async(force_reload=True)
                self.logger.info("✅ 资产管理器UI已刷新，正在重新加载资产")
            else:
                self.logger.warning("资产管理器UI没有 load_assets_async 方法")
                
        except Exception as e:
            self.logger.error(f"刷新资产管理器UI失败: {e}", exc_info=True)
