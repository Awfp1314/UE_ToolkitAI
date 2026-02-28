# -*- coding: utf-8 -*-

"""
我的工程模块主类
"""

from pathlib import Path
from PyQt6.QtWidgets import QWidget

from core.logger import get_logger
from core.services import style_service
from core.utils.cleanup_result import CleanupResult

logger = get_logger(__name__)


class MyProjectsModule:
    """我的工程模块主类"""

    def __init__(self, parent=None):
        self.parent = parent
        self.ui = None
        logger.info("MyProjectsModule 初始化")

    def initialize(self, config_dir: str):
        """初始化模块"""
        try:
            logger.info(f"我的工程模块初始化成功，配置目录: {config_dir}")
        except Exception as e:
            logger.error(f"我的工程模块初始化失败: {e}", exc_info=True)
            raise

    def get_widget(self) -> QWidget:
        """获取模块的主界面组件"""
        if self.ui is None:
            from .ui import MyProjectsUI

            current_theme = style_service.get_current_theme()
            theme_name = 'dark' if current_theme == 'modern_dark' else 'light'

            self.ui = MyProjectsUI(theme=theme_name, parent=self.parent)
            logger.info(f"我的工程 UI 创建完成，主题: {theme_name}")

        return self.ui

    def request_stop(self) -> None:
        """请求模块停止操作"""
        logger.info("请求我的工程模块停止")

    def cleanup(self) -> CleanupResult:
        """清理资源"""
        try:
            if self.ui:
                self.ui.cleanup()
                self.ui.deleteLater()
                self.ui = None
            logger.info("我的工程模块清理完成")
            return CleanupResult.success_result()
        except Exception as e:
            logger.error(f"清理我的工程模块资源时出错: {e}", exc_info=True)
            return CleanupResult.failure_result(str(e))
