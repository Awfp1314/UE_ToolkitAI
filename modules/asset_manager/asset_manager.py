# -*- coding: utf-8 -*-

"""
资产管理模块主类
"""

from pathlib import Path
from PyQt6.QtWidgets import QWidget

from core.logger import get_logger
from core.services import style_service
from core.utils.cleanup_result import CleanupResult
from .logic import AssetManagerLogic
from .ui import AssetManagerUI

logger = get_logger(__name__)


class AssetManagerModule:
    """资产管理模块主类"""
    
    def __init__(self, parent=None):
        self.parent = parent
        self.ui = None
        self.logic = None
        logger.info("AssetManagerModule 初始化")
    
    def initialize(self, config_dir: str):
        """初始化模块
        
        Args:
            config_dir: 配置目录路径
        """
        try:
            config_path = Path(config_dir)
            
            self.logic = AssetManagerLogic(config_path)
            
            logger.info(f"资产管理模块初始化成功，配置目录: {config_dir}")
            
        except Exception as e:
            logger.error(f"资产管理模块初始化失败: {e}", exc_info=True)
            raise
    
    def get_widget(self) -> QWidget:
        """获取模块的主界面组件"""
        if self.ui is None:
            if self.logic is None:
                raise RuntimeError("模块未初始化，请先调用 initialize()")

            # 获取当前主题
            current_theme = style_service.get_current_theme()
            theme_name = 'dark' if current_theme == 'modern_dark' else 'light'

            # 创建 UI
            self.ui = AssetManagerUI(self.logic, theme=theme_name, parent=self.parent)
            logger.info(f"资产管理器 UI 创建完成，主题: {theme_name}")

        return self.ui
    
    def request_stop(self) -> None:
        """请求模块停止操作（在 cleanup 之前调用）"""
        logger.info("请求资产管理模块停止")
        # 资产管理模块没有长时间运行的任务，无需特殊处理

    def cleanup(self) -> CleanupResult:
        """清理资源

        Returns:
            CleanupResult: 清理结果
        """
        try:
            if self.ui:
                self.ui.deleteLater()
                self.ui = None

            if self.logic:
                self.logic.deleteLater()
                self.logic = None

            logger.info("资产管理模块清理完成")
            return CleanupResult.success_result()

        except Exception as e:
            logger.error(f"清理资产管理模块资源时出错: {e}", exc_info=True)
            return CleanupResult.failure_result(str(e))