# -*- coding: utf-8 -*-

"""
虚幻引擎工具箱主入口
"""

import sys
import os
import time
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from PyQt6.QtWidgets import QApplication, QMessageBox
from PyQt6.QtCore import Qt, QStandardPaths, QTimer
from PyQt6.QtGui import QIcon
from ui.ue_main_window import UEMainWindow
from core.app_manager import AppManager
from core.logger import init_logging_system, get_logger, setup_console_encoding
from core.single_instance import SingleInstanceManager
from core.utils.style_system import style_system  # ⭐ 导入样式系统
import json

# ⚡ 设置控制台编码为 UTF-8（Windows 平台）
setup_console_encoding()

init_logging_system()
logger = get_logger(__name__)


def set_windows_app_user_model_id():
    """设置 Windows AppUserModelID，确保任务栏图标正确显示"""
    try:
        import ctypes
        app_id = 'HUTAO.UEToolkit.1.0'  # 应用程序唯一标识符
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(app_id)
        logger.info(f"已设置 Windows AppUserModelID: {app_id}")
    except Exception as e:
        logger.warning(f"设置 Windows AppUserModelID 失败: {e}")


def main():
    """主函数"""
    # ⚡ 性能优化：记录启动时间（Requirement 16.5）
    startup_start_time = time.time()

    # 创建应用实例
    app = QApplication(sys.argv)
    app.setApplicationName("ue_toolkit")  # 统一使用无空格的名称
    app.setApplicationVersion("1.0.1")

    # ⚡ 优化：立即创建并显示启动加载界面（在输出任何日志之前）
    from ui.splash_screen import SplashScreen
    # 根据QSS主题选择启动界面主题
    current_theme = "modern_dark"  # 默认主题
    splash_theme = "dark" if "dark" in current_theme.lower() else "light"
    splash = SplashScreen(theme=splash_theme)

    # ⚡ 关键：在显示启动界面之前就注册日志处理器，确保捕获所有日志
    splash.register_log_handler()

    splash.show()
    app.processEvents()  # 强制刷新UI，确保启动界面立即显示

    # 现在开始输出日志，这些日志会被捕获并更新进度条
    logger.info("启动虚幻引擎工具箱")
    app.processEvents()  # 让进度条动画更新

    # 设置 Windows 任务栏图标
    if sys.platform == 'win32':
        set_windows_app_user_model_id()
    app.processEvents()  # 让进度条动画更新

    # 设置应用程序图标
    icon_path = project_root / "resources" / "tubiao.ico"
    if icon_path.exists():
        app.setWindowIcon(QIcon(str(icon_path)))
        logger.info(f"已设置应用图标: {icon_path}")
    else:
        logger.warning(f"图标文件不存在: {icon_path}")
    app.processEvents()  # 让进度条动画更新

    # ⭐ 加载保存的主题设置
    try:
        app_data = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.AppDataLocation)
        config_path = Path(app_data) / "ue_toolkit" / "ui_settings.json"
        if config_path.exists():
            with open(config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
            saved_theme = config.get('theme', 'modern_dark')

            # 兼容旧版本配置：如果保存的是 'dark' 或 'light'，映射到新的主题名称
            theme_mapping = {
                'dark': 'modern_dark',
                'light': 'modern_light'
            }
            current_theme = theme_mapping.get(saved_theme, saved_theme)

            logger.info(f"已加载保存的主题: {saved_theme} -> {current_theme}")
        else:
            logger.info("未找到主题配置，使用默认主题: modern_dark")
    except Exception as e:
        logger.warning(f"加载主题设置失败，使用默认主题: {e}")

    # ⭐ 应用QSS主题（在创建任何窗口之前）
    logger.info(f"正在应用QSS主题: {current_theme}...")
    style_system.apply_theme(app, current_theme)
    logger.info("✅ QSS主题应用成功")
    app.processEvents()  # 让进度条动画更新

    logger.info("启动加载界面已显示")
    app.processEvents()  # 让进度条动画更新

    # 检查单实例（日志会自动更新进度条）
    single_instance = SingleInstanceManager("UEToolkit")
    app.processEvents()  # 让进度条动画更新

    if single_instance.is_running():
        logger.info("程序已经在运行，激活现有实例")
        splash.close()
        return 0

    try:
        # 创建应用管理器（日志会自动更新进度条）
        app_manager = AppManager()
        app.processEvents()  # 让进度条动画更新

        # 设置应用程序（日志会自动更新进度条）
        logger.info("开始设置应用程序")
        app.processEvents()  # 让进度条动画更新

        if not app_manager.setup():
            logger.error("应用程序设置失败")
            splash.close()
            QMessageBox.critical(None, "启动失败", "应用程序设置失败，请查看日志文件获取详细信息。")
            return 1

        logger.info("应用程序设置成功")
        app.processEvents()  # 让进度条动画更新

        # 存储主窗口引用（在回调中使用）
        main_window = None
        module_provider = None

        def on_startup_complete(success: bool):
            """异步启动完成回调"""
            nonlocal main_window, module_provider, splash
            
            if not success:
                logger.error("应用程序启动失败")
                QMessageBox.critical(
                    None, 
                    "启动失败", 
                    "应用程序启动失败，请查看日志文件获取详细信息。"
                )
                app.quit()
                return
            
            try:
                logger.info("应用程序启动成功")
                app.processEvents()  # 让进度条动画更新

                # 创建模块提供者（日志会自动更新进度条）
                from core.module_interface import ModuleProviderAdapter
                module_provider = ModuleProviderAdapter(app_manager.module_manager)
                app.processEvents()  # 让进度条动画更新

                # 建立模块间的连接（AI助手、资产管理器、配置工具）
                try:
                    logger.info("========== 开始建立模块间连接 ==========")
                    print("[DEBUG] ========== 开始建立模块间连接 ==========")
                    app.processEvents()  # 让进度条动画更新

                    if not app_manager.module_manager:
                        print("[DEBUG] [ERROR] module_manager 未初始化")
                        raise RuntimeError("module_manager 未初始化")

                    asset_manager_module = app_manager.module_manager.get_module("asset_manager")
                    config_tool_module = app_manager.module_manager.get_module("config_tool")
                    ai_assistant_module = app_manager.module_manager.get_module("ai_assistant")
                    app.processEvents()  # 让进度条动画更新
                    
                    print(f"[DEBUG] asset_manager 模块: {asset_manager_module}")
                    print(f"[DEBUG] config_tool 模块: {config_tool_module}")
                    print(f"[DEBUG] ai_assistant 模块: {ai_assistant_module}")
                    
                    if ai_assistant_module:
                        print(f"[DEBUG] ai_assistant 实例: {ai_assistant_module.instance}")

                        # 连接 asset_manager
                        if asset_manager_module and asset_manager_module.instance:
                            print(f"[DEBUG] asset_manager 实例: {asset_manager_module.instance}")
                            
                            # 获取 asset_manager 的逻辑层实例
                            if hasattr(asset_manager_module.instance, 'logic'):
                                asset_logic = asset_manager_module.instance.logic  # type: ignore
                                print(f"[DEBUG] [OK] 通过 .logic 属性获取到 asset_manager 逻辑层: {asset_logic}")
                                logger.info("获取到 asset_manager 逻辑层")
                            elif asset_manager_module.instance and hasattr(asset_manager_module.instance, 'get_logic'):
                                asset_logic = asset_manager_module.instance.get_logic()  # type: ignore
                                print(f"[DEBUG] [OK] 通过 get_logic() 获取到 asset_manager 逻辑层: {asset_logic}")
                                logger.info("通过 get_logic 获取到 asset_manager 逻辑层")
                            else:
                                asset_logic = None
                                print("[DEBUG] [ERROR] 无法获取 asset_manager 逻辑层")
                                logger.warning("无法获取 asset_manager 逻辑层")
                            
                            # 将 asset_manager 逻辑层传递给 AI助手
                            if asset_logic and ai_assistant_module.instance and hasattr(ai_assistant_module.instance, 'set_asset_manager_logic'):
                                print(f"[DEBUG] 正在调用 ai_assistant.set_asset_manager_logic({asset_logic})...")
                                ai_assistant_module.instance.set_asset_manager_logic(asset_logic)  # type: ignore
                                print("[DEBUG] [OK] 已将 asset_manager 逻辑层连接到 AI助手")
                                logger.info("已将 asset_manager 逻辑层连接到 AI助手")
                            else:
                                if not asset_logic:
                                    print("[DEBUG] [ERROR] asset_logic 为 None，无法连接")
                                if ai_assistant_module.instance and not hasattr(ai_assistant_module.instance, 'set_asset_manager_logic'):
                                    print("[DEBUG] [ERROR] AI助手模块缺少 set_asset_manager_logic 方法")
                                    logger.warning("AI助手模块缺少 set_asset_manager_logic 方法")
                        else:
                            print("[DEBUG] [WARN] asset_manager 模块未加载")
                            logger.info("asset_manager 模块未加载，跳过连接")
                        
                        # 连接 config_tool
                        if config_tool_module and config_tool_module.instance:
                            print(f"[DEBUG] config_tool 实例: {config_tool_module.instance}")
                            
                            # 获取 config_tool 的逻辑层实例
                            if hasattr(config_tool_module.instance, 'logic'):
                                config_logic = config_tool_module.instance.logic  # type: ignore
                                print(f"[DEBUG] [OK] 通过 .logic 属性获取到 config_tool 逻辑层: {config_logic}")
                                logger.info("获取到 config_tool 逻辑层")
                            elif config_tool_module.instance and hasattr(config_tool_module.instance, 'get_logic'):
                                config_logic = config_tool_module.instance.get_logic()  # type: ignore
                                print(f"[DEBUG] [OK] 通过 get_logic() 获取到 config_tool 逻辑层: {config_logic}")
                                logger.info("通过 get_logic 获取到 config_tool 逻辑层")
                            else:
                                config_logic = None
                                print("[DEBUG] [ERROR] 无法获取 config_tool 逻辑层")
                                logger.warning("无法获取 config_tool 逻辑层")
                            
                            # 将 config_tool 逻辑层传递给 AI助手
                            if config_logic and ai_assistant_module.instance and hasattr(ai_assistant_module.instance, 'set_config_tool_logic'):
                                print(f"[DEBUG] 正在调用 ai_assistant.set_config_tool_logic({config_logic})...")
                                ai_assistant_module.instance.set_config_tool_logic(config_logic)  # type: ignore
                                print("[DEBUG] [OK] 已将 config_tool 逻辑层连接到 AI助手")
                                logger.info("已将 config_tool 逻辑层连接到 AI助手")
                            else:
                                if not config_logic:
                                    print("[DEBUG] [ERROR] config_logic 为 None，无法连接")
                                if ai_assistant_module.instance and not hasattr(ai_assistant_module.instance, 'set_config_tool_logic'):
                                    print("[DEBUG] [ERROR] AI助手模块缺少 set_config_tool_logic 方法")
                                    logger.warning("AI助手模块缺少 set_config_tool_logic 方法")
                        else:
                            print("[DEBUG] [WARN] config_tool 模块未加载")
                            logger.info("config_tool 模块未加载，跳过连接")
                        
                        # 连接 site_recommendations
                        site_recommendations_module = module_provider.get_module("site_recommendations")
                        if site_recommendations_module and site_recommendations_module.instance:  # type: ignore
                            print(f"[DEBUG] site_recommendations 实例: {site_recommendations_module.instance}")  # type: ignore
                            
                            # 获取 site_recommendations 的逻辑层实例
                            if hasattr(site_recommendations_module.instance, 'logic'):  # type: ignore
                                site_logic = site_recommendations_module.instance.logic  # type: ignore
                                print(f"[DEBUG] [OK] 通过 .logic 属性获取到 site_recommendations 逻辑层: {site_logic}")
                                logger.info("获取到 site_recommendations 逻辑层")
                            elif site_recommendations_module.instance and hasattr(site_recommendations_module.instance, 'get_logic'):  # type: ignore
                                site_logic = site_recommendations_module.instance.get_logic()  # type: ignore
                                print(f"[DEBUG] [OK] 通过 get_logic() 获取到 site_recommendations 逻辑层: {site_logic}")
                                logger.info("通过 get_logic 获取到 site_recommendations 逻辑层")
                            else:
                                site_logic = None
                                print("[DEBUG] [ERROR] 无法获取 site_recommendations 逻辑层")
                                logger.warning("无法获取 site_recommendations 逻辑层")
                            
                            # 将 site_recommendations 逻辑层传递给 AI助手
                            if site_logic and ai_assistant_module.instance and hasattr(ai_assistant_module.instance, 'site_recommendations_logic'):  # type: ignore
                                print(f"[DEBUG] 正在设置 ai_assistant.site_recommendations_logic = {site_logic}")
                                ai_assistant_module.instance.site_recommendations_logic = site_logic  # type: ignore
                                print("[DEBUG] [OK] 已将 site_recommendations 逻辑层连接到 AI助手")
                                logger.info("已将 site_recommendations 逻辑层连接到 AI助手")
                            else:
                                if not site_logic:
                                    print("[DEBUG] [ERROR] site_logic 为 None，无法连接")
                                if ai_assistant_module.instance and not hasattr(ai_assistant_module.instance, 'site_recommendations_logic'):
                                    print("[DEBUG] [ERROR] AI助手模块缺少 site_recommendations_logic 属性")
                                    logger.warning("AI助手模块缺少 site_recommendations_logic 属性")
                        else:
                            print("[DEBUG] [WARN] site_recommendations 模块未加载")
                            logger.info("site_recommendations 模块未加载，跳过连接")
                    else:
                        print("[DEBUG] [WARN] ai_assistant 模块未加载")
                        logger.info("ai_assistant 模块未加载，跳过连接")
                    
                    print("[DEBUG] ========== 模块连接流程结束 ==========")
                except Exception as e:
                    print(f"[DEBUG] [ERROR] 建立模块间连接时发生异常: {e}")
                    logger.error(f"建立模块间连接失败: {e}", exc_info=True)
                    import traceback
                    traceback.print_exc()
                
                # 创建主窗口（但不显示）（日志会自动更新进度条）
                logger.info("创建主窗口")
                app.processEvents()  # 让进度条动画更新
                main_window = UEMainWindow(module_provider)
                app.processEvents()  # 让进度条动画更新

                # ⚡ 优化：不在启动时预加载资产，让资产管理器在首次显示时才加载
                # 这样可以避免启动时的卡顿，提升用户体验
                logger.info("主窗口创建完成，准备显示")
                splash.update_progress(100, "启动完成！")
                app.processEvents()  # 让进度条动画更新

                # ⚡ 优化：延迟500ms后加载模块、关闭启动界面并显示主窗口
                def load_and_show_window():
                    """加载第一个模块，关闭启动界面，然后显示主窗口"""
                    # 先加载第一个模块（资产库），避免显示占位页
                    logger.info("预加载第一个模块（资产库）")
                    
                    def on_assets_loaded():
                        """资产加载完成回调"""
                        logger.info("资产加载完成回调被调用")
                        # 多次处理事件，确保UI更新
                        for _ in range(3):
                            app.processEvents()  # 让进度条动画更新

                        # 关闭启动界面
                        splash.finish()

                        # 显示主窗口
                        main_window.show()  # type: ignore
                        main_window.raise_()  # type: ignore
                        main_window.activateWindow()  # type: ignore
                        logger.info("主窗口已显示")
                    
                    # 加载模块并异步加载资产
                    logger.info("开始加载初始模块")
                    main_window.load_initial_module(on_complete=on_assets_loaded)  # type: ignore

                QTimer.singleShot(500, load_and_show_window)

                # ⚡ 性能优化：记录窗口创建时间（Requirement 16.5）
                window_create_time = time.time()
                startup_duration = window_create_time - startup_start_time
                logger.info(f"⚡ 启动性能：从启动到窗口创建耗时 {startup_duration:.3f} 秒")

                if startup_duration < 1.0:
                    logger.info(f"✅ 启动性能达标（< 1秒）")
                else:
                    logger.warning(f"⚠️ 启动性能未达标（目标 < 1秒，实际 {startup_duration:.3f}秒）")

                # 启动单实例服务器
                single_instance.start_server(main_window)

                logger.info("应用程序完全启动完成")
                
            except Exception as e:
                logger.error(f"创建主窗口时发生错误: {e}", exc_info=True)
                QMessageBox.critical(
                    None,
                    "启动失败",
                    f"创建主窗口失败: {str(e)}"
                )
                app.quit()
        
        def on_startup_error(error_message: str):
            """启动错误回调"""
            nonlocal splash
            logger.error(f"启动过程出错: {error_message}")
            splash.close()
            QMessageBox.critical(
                None,
                "启动错误",
                f"启动过程中发生错误:\n{error_message}"
            )
            app.quit()

        # 异步启动应用程序（日志会自动更新进度条，不需要 on_progress 回调）
        logger.info("开始异步启动应用程序")
        app_manager.start_async(
            on_complete=on_startup_complete,
            on_error=on_startup_error
        )
        
        # 运行应用程序事件循环
        exit_code = app.exec()
        
        # 清理单实例资源
        single_instance.cleanup()
        
        logger.info(f"应用程序退出，退出码: {exit_code}")
        return exit_code
        
    except Exception as e:
        logger.error(f"启动应用程序时发生错误: {e}", exc_info=True)
        return 1


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)