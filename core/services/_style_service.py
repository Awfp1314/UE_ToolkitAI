"""
StyleService - 统一的样式服务

封装 StyleSystem，提供简化的主题管理接口
Level 1 服务：依赖 LogService
"""

from typing import List, Optional
from PyQt6.QtWidgets import QApplication, QWidget
from PyQt6.QtCore import pyqtSignal, QObject

from core.utils.style_system import style_system


class StyleService(QObject):
    """统一的样式服务
    
    封装 StyleSystem，提供简化的主题管理接口
    
    特点：
    - Level 1 服务，依赖 LogService
    - 封装现有 StyleSystem 单例
    - 转发 StyleSystem 的信号
    - 线程安全（Qt 方法需在主线程调用）
    """
    
    # 转发 StyleSystem 的信号
    themeChanged = pyqtSignal(str)
    
    def __init__(self):
        """初始化样式服务

        注意：使用 LogService 记录日志
        """
        super().__init__()

        # 延迟导入，避免循环依赖
        from core.services import _get_log_service

        # 使用全局 StyleSystem 单例
        self._style_system = style_system

        # 获取 logger（通过内部 getter 函数）
        log_service_instance = _get_log_service()
        self._logger = log_service_instance.get_logger("style_service")

        # 连接 StyleSystem 的信号
        self._style_system.themeChanged.connect(self.themeChanged.emit)

        self._logger.info("StyleService 初始化完成")
    
    def apply_theme(self, theme_name: str, app: Optional[QApplication] = None) -> bool:
        """应用主题
        
        Args:
            theme_name: 主题名称
            app: QApplication 实例，如果为 None 则使用 QApplication.instance()
            
        Returns:
            是否成功应用
            
        Example:
            success = style_service.apply_theme("modern_dark")
        """
        if app is None:
            app = QApplication.instance()
        
        if app is None:
            self._logger.error("无法获取 QApplication 实例")
            return False
        
        self._logger.info(f"应用主题: {theme_name}")
        return self._style_system.apply_theme(app, theme_name)
    
    def apply_to_widget(
        self,
        widget: QWidget,
        theme_name: Optional[str] = None
    ) -> bool:
        """应用主题到控件
        
        Args:
            widget: 要应用主题的控件
            theme_name: 主题名称，如果为 None 则使用当前主题
            
        Returns:
            是否成功应用
            
        Example:
            success = style_service.apply_to_widget(my_widget, "modern_light")
        """
        return self._style_system.apply_to_widget(widget, theme_name)
    
    def get_current_theme(self) -> Optional[str]:
        """获取当前主题名称
        
        Returns:
            当前主题名称，如果未设置则返回 None
            
        Example:
            theme = style_service.get_current_theme()
        """
        return self._style_system.current_theme
    
    def list_available_themes(self) -> List[str]:
        """列出所有可用主题
        
        Returns:
            主题名称列表
            
        Example:
            themes = style_service.list_available_themes()
            print(f"可用主题: {themes}")
        """
        return self._style_system.discover_themes()
    
    def preload_themes(self, theme_names: List[str]) -> None:
        """预加载主题到缓存
        
        Args:
            theme_names: 要预加载的主题名称列表
            
        Example:
            style_service.preload_themes(["modern_dark", "modern_light"])
        """
        self._logger.info(f"预加载主题: {theme_names}")
        self._style_system.preload_themes(theme_names)
    
    def clear_cache(self, theme_name: Optional[str] = None) -> None:
        """清除主题缓存
        
        Args:
            theme_name: 主题名称，如果为 None 则清除所有缓存
            
        Example:
            # 清除特定主题的缓存
            style_service.clear_cache("modern_dark")
            
            # 清除所有主题的缓存
            style_service.clear_cache()
        """
        self._style_system.clear_cache(theme_name)
        if theme_name is None:
            self._logger.info("已清除所有主题缓存")
        else:
            self._logger.info(f"已清除主题缓存: {theme_name}")
    
    def reload_theme(self, theme_name: Optional[str] = None) -> bool:
        """重新加载主题
        
        Args:
            theme_name: 主题名称，如果为 None 则重新加载当前主题
            
        Returns:
            是否成功重新加载
            
        Example:
            success = style_service.reload_theme("modern_dark")
        """
        return self._style_system.reload_theme(theme_name)

