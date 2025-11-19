"""
ModuleLoader - 模块加载组件

负责应用程序模块的加载和依赖管理，包括：
- AppManager 设置
- 异步模块加载
- 模块依赖连接
- ModuleProviderAdapter 创建
"""

from typing import Optional, Callable

from core.logger import get_logger
from core.app_manager import AppManager
from core.module_interface import ModuleProviderAdapter


class ModuleLoader:
    """模块加载器（AppManager 的门面）"""

    def __init__(self):
        self.app_manager: Optional[AppManager] = None
        self.module_provider: Optional[ModuleProviderAdapter] = None
        self.logger = get_logger(__name__)

    def load_modules(self,
                     on_progress: Callable[[int, str], None],
                     on_complete: Callable[[ModuleProviderAdapter], None],
                     on_error: Callable[[str], None]) -> None:
        """异步加载模块

        Args:
            on_progress: 进度回调 (percent: int, message: str) -> None
            on_complete: 完成回调，传入 ModuleProviderAdapter
            on_error: 错误回调，传入错误消息
        """
        # 首先设置 AppManager
        if not self._setup_app_manager():
            error_msg = "AppManager 设置失败"
            self.logger.error(error_msg)
            on_error(error_msg)
            return

        # 启动异步加载
        self._start_async_loading(on_progress, on_complete, on_error)

    def _setup_app_manager(self) -> bool:
        """设置 AppManager

        Returns:
            bool: 是否成功
        """
        try:
            # 创建 AppManager 实例
            self.logger.info("创建 AppManager 实例")
            self.app_manager = AppManager()

            # 调用 app_manager.setup() 初始化核心服务
            self.logger.info("开始设置应用程序")
            if not self.app_manager.setup():
                self.logger.error("应用程序设置失败")
                return False

            self.logger.info("应用程序设置成功")
            return True

        except Exception as e:
            self.logger.error(f"设置 AppManager 失败: {e}", exc_info=True)
            return False

    def _start_async_loading(self,
                             on_progress: Callable,
                             on_complete: Callable,
                             on_error: Callable) -> None:
        """启动异步加载

        Args:
            on_progress: 进度回调
            on_complete: 完成回调
            on_error: 错误回调
        """
        if not self.app_manager:
            error_msg = "AppManager 未初始化"
            self.logger.error(error_msg)
            on_error(error_msg)
            return

        # 定义内部回调函数处理 on_complete、on_error、on_progress
        def internal_on_progress(percent: int, message: str):
            """内部进度回调，转发到外部回调"""
            self.logger.info(f"[{percent}%] {message}")
            # 调用外部传入的 on_progress
            on_progress(percent, message)

        def internal_on_complete(success: bool):
            """内部完成回调"""
            if not success:
                error_msg = "模块加载失败"
                self.logger.error(error_msg)
                on_error(error_msg)
                return

            try:
                self.logger.info("应用程序启动成功")
                
                # 建立模块依赖连接
                self._connect_module_dependencies()

                # 创建 ModuleProviderAdapter
                if self.app_manager and self.app_manager.module_manager:
                    self.logger.info("创建模块提供者")
                    self.module_provider = ModuleProviderAdapter(self.app_manager.module_manager)
                    
                    # 调用外部 on_complete，传入 module_provider
                    on_complete(self.module_provider)
                else:
                    error_msg = "ModuleManager 未初始化"
                    self.logger.error(error_msg)
                    on_error(error_msg)

            except Exception as e:
                error_msg = f"创建 ModuleProviderAdapter 失败: {e}"
                self.logger.error(error_msg, exc_info=True)
                on_error(error_msg)

        def internal_on_error(error_message: str):
            """内部错误回调，转发到外部回调"""
            self.logger.error(f"模块加载错误: {error_message}")
            on_error(error_message)

        # 调用 app_manager.start_async() 异步加载模块
        self.logger.info("开始异步加载模块")
        self.app_manager.start_async(
            on_complete=internal_on_complete,
            on_progress=internal_on_progress,
            on_error=internal_on_error
        )

    def _connect_module_dependencies(self) -> None:
        """建立模块间的依赖连接"""
        # 占位符：将在任务 4.3 中实现
        pass
