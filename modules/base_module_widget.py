# -*- coding: utf-8 -*-

"""
基础模块组件 - 提供主题切换支持
"""

from PyQt6.QtWidgets import QWidget
from core.logger import get_logger

logger = get_logger(__name__)


class BaseModuleWidget(QWidget):
    """模块组件基类，提供主题切换支持
    
    所有模块组件应继承此类以获得主题切换通知功能。
    """

    def __init__(self, parent=None):
        super().__init__(parent)

    def on_theme_changed(self, theme_name: str) -> None:
        """主题切换回调方法
        
        当应用主题切换时，此方法会被调用。
        子类可以重写此方法以实现自定义的主题切换逻辑。
        默认实现会刷新组件及其所有子组件的样式。
        
        Args:
            theme_name: 新主题名称 ('dark' 或 'light')
        """
        logger.debug(f"{self.__class__.__name__} 收到主题切换通知: {theme_name}")
        
        # 刷新当前组件的样式
        self.style().unpolish(self)
        self.style().polish(self)
        self.update()

        # 递归刷新所有子组件的样式
        for child in self.findChildren(QWidget):
            child.style().unpolish(child)
            child.style().polish(child)
            child.update()

        logger.debug(f"{self.__class__.__name__} 主题样式已刷新")
