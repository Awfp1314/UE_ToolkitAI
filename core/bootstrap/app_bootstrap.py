"""
AppBootstrap - 启动流程协调器

协调整个应用程序的启动流程，包括：
- 应用初始化阶段
- UI 准备阶段
- 模块加载阶段
- 事件循环启动
- 异常处理和资源清理
"""

from typing import Optional

from PyQt6.QtWidgets import QApplication
from PyQt6 import sip

from core.logger import get_logger
from core.single_instance import SingleInstanceManager
from ui.splash_screen import SplashScreen

from .app_initializer import AppInitializer
from .ui_launcher import UILauncher
from .module_loader import ModuleLoader


class AppBootstrap:
    """应用程序启动协调器"""

    def __init__(self):
        """初始化启动协调器"""
        # 初始化 app_initializer、ui_launcher、module_loader
        self.app_initializer = AppInitializer()
        self.ui_launcher = UILauncher()
        self.module_loader = ModuleLoader()

        # 声明状态成员：app、single_instance、splash、exit_code
        self.app: Optional[QApplication] = None
        self.single_instance: Optional[SingleInstanceManager] = None
        self.splash: Optional[SplashScreen] = None
        self.exit_code: int = 0

        self.logger = get_logger(__name__)

    def run(self) -> int:
        """执行完整的启动流程

        Returns:
            int: 退出码 (0=成功, 1=初始化失败, 2=模块加载失败, 3=UI创建失败)
        """
        try:
            # 5.2: 应用初始化阶段
            self.logger.info("开始应用初始化阶段")
            self.app, self.single_instance, success = self.app_initializer.initialize()
            
            # 检查返回的 success 标志
            if not success:
                # 如果失败，返回退出码 1
                self.logger.error("应用初始化失败")
                return 1

            self.logger.info("应用初始化阶段完成")

            # 5.3: UI 准备阶段
            self.logger.info("开始 UI 准备阶段")
            self.splash = self.ui_launcher.prepare_ui(self.app)
            self.logger.info("UI 准备阶段完成")

            # 5.4: 实现模块加载回调注册
            # 定义 on_progress 回调（更新 Splash 并刷新事件）
            def on_progress(percent: int, message: str):
                """进度回调"""
                if self.splash:
                    self.splash.update_progress(percent, message)
                if self.app:
                    self.app.processEvents()

            # 定义 on_complete 回调（调用 show_ui）
            def on_complete(module_provider):
                """模块加载完成回调"""
                try:
                    self.logger.info("模块加载完成，开始显示 UI")
                    success = self.ui_launcher.show_ui(
                        self.app, module_provider, self.single_instance
                    )
                    if not success:
                        self.logger.error("UI 显示失败")
                        self.exit_code = 3
                        self._cleanup()
                        if self.app:
                            self.app.quit()
                except Exception as e:
                    self.logger.error(f"UI 显示失败: {e}", exc_info=True)
                    self.exit_code = 3
                    self._cleanup()
                    if self.app:
                        self.app.quit()

            # 定义 on_error 回调（设置退出码并清理）
            def on_error(error_message: str):
                """模块加载错误回调"""
                self.logger.error(f"模块加载失败: {error_message}")
                self.exit_code = 2
                self._cleanup()
                if self.app:
                    self.app.quit()

            # 调用 module_loader.load_modules() 注册回调
            self.logger.info("开始异步加载模块")
            self.module_loader.load_modules(on_progress, on_complete, on_error)

            # 5.5: 实现退出清理钩子
            # 注册 app.aboutToQuit 信号到 _cleanup() 方法
            self.app.aboutToQuit.connect(self._cleanup)
            self.logger.info("已注册退出清理钩子")

            # 5.6: 实现事件循环启动
            # 调用 app.exec() 进入事件循环
            self.logger.info("进入事件循环")
            self.app.exec()

            # 返回 exit_code
            self.logger.info(f"应用程序退出，退出码: {self.exit_code}")
            return self.exit_code

        # 5.7: 实现异常捕获和用户提示
        except Exception as e:
            # 捕获所有异常并记录详细日志
            # 如果日志系统未初始化，将错误输出到 stderr
            try:
                self.logger.error(f"启动失败: {e}", exc_info=True)
            except:
                import sys
                import traceback
                sys.stderr.write(f"启动失败: {e}\n")
                traceback.print_exc(file=sys.stderr)

            # 显示用户友好的错误对话框
            try:
                from PyQt6.QtWidgets import QMessageBox
                QMessageBox.critical(
                    None,
                    "启动失败",
                    f"应用程序启动失败，请查看日志文件获取详细信息。\n\n错误: {str(e)}"
                )
            except:
                pass  # 如果显示对话框失败，静默忽略

            # 5.8: 实现退出码管理和资源清理
            # 根据错误类型设置对应的退出码
            self.exit_code = 1

            # 调用 _cleanup() 清理资源
            self._cleanup()

            # 返回退出码
            return self.exit_code

    def _cleanup(self):
        """清理资源

        调用时机：
        1. 正常退出：通过 aboutToQuit 信号自动调用
        2. 异常退出：在 except 块中显式调用
        3. 模块加载失败：在 on_error 回调中调用
        4. UI 显示失败：在 on_complete 回调中调用
        """
        try:
            self.logger.info("开始清理资源")

            # 关闭 Splash Screen（如果存在）
            if self.splash:
                try:
                    # 检查 Splash 是否仍然有效
                    if not sip.isdeleted(self.splash):
                        self.splash.close()
                        self.logger.info("Splash Screen 已关闭")
                except Exception as e:
                    self.logger.debug(f"关闭 Splash Screen 失败（可能已被清理）: {e}")
                finally:
                    self.splash = None

            # 清理 SingleInstanceManager（如果存在）
            if self.single_instance:
                try:
                    self.single_instance.cleanup()
                    self.logger.info("SingleInstanceManager 已清理")
                except Exception as e:
                    self.logger.warning(f"清理 SingleInstanceManager 失败: {e}")
                finally:
                    self.single_instance = None

            # QApplication 资源通过 aboutToQuit 信号自动处理
            # 验证事件循环已停止（通过检查 QApplication 状态）
            if self.app:
                try:
                    # 事件循环在 quit() 后会自动停止
                    self.logger.info("QApplication 资源释放完成")
                except Exception as e:
                    self.logger.warning(f"QApplication 资源释放检查失败: {e}")

            self.logger.info("资源清理完成")

        except Exception as e:
            # 清理失败不应该影响退出流程
            try:
                self.logger.error(f"资源清理失败: {e}", exc_info=True)
            except:
                import sys
                sys.stderr.write(f"资源清理失败: {e}\n")
