"""
AppInitializer - 应用初始化组件

负责应用程序的基础初始化工作，包括：
- 日志系统配置
- QApplication 创建和配置
- 单例检查
"""

import sys
from pathlib import Path
from typing import Optional

from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QIcon

from core.logger import init_logging_system, setup_console_encoding, get_logger
from core.single_instance import SingleInstanceManager


class AppInitializer:
    """应用程序初始化器"""

    def __init__(self):
        self.logger: Optional[object] = None
        self.project_root = Path(__file__).parent.parent.parent

    def initialize(self) -> tuple[QApplication, SingleInstanceManager, bool]:
        """初始化应用程序

        Returns:
            tuple: (QApplication实例, SingleInstanceManager实例, 是否成功)
        """
        # 2.1: 配置日志系统
        self._setup_logging()

        # 2.2: 创建并配置 QApplication
        app = self._create_qapplication()

        # 2.3: 检查单实例
        single_instance = SingleInstanceManager("UEToolkit")
        if not self._check_single_instance(single_instance):
            # 已有实例在运行
            return app, single_instance, False

        return app, single_instance, True

    def _setup_logging(self) -> None:
        """配置日志系统"""
        # 调用 setup_console_encoding() 设置控制台编码（Windows）
        setup_console_encoding()

        # 调用 init_logging_system() 配置日志
        init_logging_system()

        # 获取日志记录器
        self.logger = get_logger(__name__)
        self.logger.info("日志系统初始化完成")

    def _create_qapplication(self) -> QApplication:
        """创建并配置 QApplication"""
        # 创建 QApplication 实例
        app = QApplication(sys.argv)

        # 设置应用程序名称为 "ue_toolkit"
        app.setApplicationName("ue_toolkit")

        # 设置应用程序版本为 "1.0.1"
        app.setApplicationVersion("1.0.1")

        # 设置应用程序图标（resources/tubiao.ico）
        icon_path = self.project_root / "resources" / "tubiao.ico"
        if icon_path.exists():
            app.setWindowIcon(QIcon(str(icon_path)))
            if self.logger:
                self.logger.info(f"已设置应用图标: {icon_path}")
        else:
            if self.logger:
                self.logger.warning(f"图标文件不存在: {icon_path}")

        # 设置 Windows AppUserModelID（Windows 平台）
        if sys.platform == 'win32':
            self._set_windows_app_user_model_id()

        if self.logger:
            self.logger.info("QApplication 创建和配置完成")

        return app

    def _set_windows_app_user_model_id(self) -> None:
        """设置 Windows AppUserModelID，确保任务栏图标正确显示"""
        try:
            import ctypes
            app_id = 'HUTAO.UEToolkit.1.0'  # 应用程序唯一标识符
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(app_id)
            if self.logger:
                self.logger.info(f"已设置 Windows AppUserModelID: {app_id}")
        except Exception as e:
            if self.logger:
                self.logger.warning(f"设置 Windows AppUserModelID 失败: {e}")

    def _check_single_instance(self, single_instance: SingleInstanceManager) -> bool:
        """检查单实例

        Args:
            single_instance: SingleInstanceManager 实例

        Returns:
            bool: True=可以继续启动, False=已有实例运行
        """
        # 占位符：将在任务 2.3 中实现
        pass
