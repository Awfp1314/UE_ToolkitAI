# -*- coding: utf-8 -*-

"""
样式系统核心 - 统一的主题加载和应用接口

核心功能：
1. 统一入口：加载和应用主题
2. 缓存机制：内存缓存已加载主题
3. 预加载：启动时预加载常用主题
4. 主题切换：运行时切换主题
5. 信号通知：主题切换时发送Qt信号，UI模块可响应

使用示例:
    # 基本使用
    from core.utils.style_system import style_system
    
    # 应用主题到应用程序
    app = QApplication.instance()
    style_system.apply_theme(app, "modern_dark")
    
    # 应用主题到单个控件
    style_system.apply_to_widget(my_widget, "modern_light")
    
    # 监听主题切换信号
    style_system.themeChanged.connect(on_theme_changed)
    
    def on_theme_changed(theme_name: str):
        print(f"主题已切换到: {theme_name}")
"""

import logging
from pathlib import Path
from typing import Dict, Optional, List
from PyQt6.QtCore import QObject, pyqtSignal
from PyQt6.QtWidgets import QApplication, QWidget

logger = logging.getLogger(__name__)


class StyleSystem(QObject):
    """样式系统核心类"""
    
    # Qt信号：主题切换时发送
    themeChanged = pyqtSignal(str)  # 参数：新主题名称
    
    def __init__(self, styles_root: Optional[Path] = None):
        """
        初始化样式系统
        
        Args:
            styles_root: 样式系统根目录，如果为None则自动检测
        """
        super().__init__()
        
        # 自动检测样式根目录
        if styles_root is None:
            # 从当前文件向上查找 resources/styles 目录
            current_file = Path(__file__)
            project_root = current_file.parent.parent.parent  # core/utils -> core -> project_root
            styles_root = project_root / "resources" / "styles"
        
        self.styles_root = Path(styles_root)
        self.themes_dir = self.styles_root / "themes"
        
        # 主题缓存
        self._theme_cache: Dict[str, str] = {}
        
        # 当前主题
        self.current_theme: Optional[str] = None
        
        logger.info(f"✅ 样式系统初始化完成")
        logger.info(f"   样式根目录: {self.styles_root}")
        logger.info(f"   主题目录: {self.themes_dir}")
    
    def discover_themes(self) -> List[str]:
        """
        发现所有可用的主题
        
        Returns:
            主题名称列表
        """
        if not self.themes_dir.exists():
            logger.warning(f"主题目录不存在: {self.themes_dir}")
            return []
        
        themes = []
        for file in self.themes_dir.glob("*.qss"):
            theme_name = file.stem
            themes.append(theme_name)
        
        logger.debug(f"发现 {len(themes)} 个主题: {themes}")
        return themes
    
    def load_theme(self, theme_name: str, use_cache: bool = True) -> str:
        """
        加载主题QSS内容
        
        Args:
            theme_name: 主题名称
            use_cache: 是否使用缓存（默认True）
            
        Returns:
            QSS内容字符串
        """
        # 检查缓存
        if use_cache and theme_name in self._theme_cache:
            logger.debug(f"从缓存加载主题: {theme_name}")
            return self._theme_cache[theme_name]
        
        # 从文件加载
        theme_file = self.themes_dir / f"{theme_name}.qss"
        
        if not theme_file.exists():
            logger.error(f"主题文件不存在: {theme_file}")
            return ""
        
        try:
            with open(theme_file, 'r', encoding='utf-8') as f:
                qss_content = f.read()
            
            # 缓存主题
            if use_cache:
                self._theme_cache[theme_name] = qss_content
            
            logger.info(f"✅ 成功加载主题: {theme_name} ({len(qss_content)} 字符)")
            return qss_content
            
        except Exception as e:
            logger.error(f"加载主题文件失败: {theme_file}, 错误: {e}")
            return ""
    
    def apply_theme(
        self, 
        app: QApplication, 
        theme_name: str,
        emit_signal: bool = True
    ) -> bool:
        """
        应用主题到应用程序
        
        Args:
            app: QApplication实例
            theme_name: 主题名称
            emit_signal: 是否发送主题切换信号（默认True）
            
        Returns:
            是否成功应用
        """
        qss = self.load_theme(theme_name)
        
        if not qss:
            logger.error(f"无法应用主题: {theme_name}")
            return False
        
        try:
            app.setStyleSheet(qss)
            
            # 更新当前主题
            old_theme = self.current_theme
            self.current_theme = theme_name
            
            logger.info(f"✅ 成功应用主题到应用程序: {theme_name}")
            
            # 发送主题切换信号
            if emit_signal:
                self.themeChanged.emit(theme_name)
                logger.debug(f"发送主题切换信号: {old_theme} -> {theme_name}")
            
            return True
            
        except Exception as e:
            logger.error(f"应用主题失败: {theme_name}, 错误: {e}")
            return False
    
    def apply_to_widget(
        self, 
        widget: QWidget, 
        theme_name: Optional[str] = None
    ) -> bool:
        """
        应用主题到单个控件
        
        Args:
            widget: 要应用主题的控件
            theme_name: 主题名称，如果为None则使用当前主题
            
        Returns:
            是否成功应用
        """
        if theme_name is None:
            theme_name = self.current_theme
        
        if theme_name is None:
            logger.warning("未指定主题且当前主题为空")
            return False
        
        qss = self.load_theme(theme_name)
        
        if not qss:
            logger.error(f"无法应用主题到控件: {theme_name}")
            return False
        
        try:
            widget.setStyleSheet(qss)
            logger.debug(f"✅ 成功应用主题到控件: {widget.objectName() or widget.__class__.__name__}")
            return True
            
        except Exception as e:
            logger.error(f"应用主题到控件失败: {e}")
            return False
    
    def preload_themes(self, theme_names: List[str]) -> None:
        """
        预加载主题到缓存
        
        Args:
            theme_names: 要预加载的主题名称列表
        """
        logger.info(f"开始预加载 {len(theme_names)} 个主题...")
        
        for theme_name in theme_names:
            self.load_theme(theme_name, use_cache=True)
        
        logger.info(f"✅ 预加载完成，缓存中有 {len(self._theme_cache)} 个主题")
    
    def clear_cache(self, theme_name: Optional[str] = None) -> None:
        """
        清除主题缓存
        
        Args:
            theme_name: 主题名称，如果为None则清除所有缓存
        """
        if theme_name is None:
            self._theme_cache.clear()
            logger.info("🧹 已清除所有主题缓存")
        elif theme_name in self._theme_cache:
            del self._theme_cache[theme_name]
            logger.info(f"🧹 已清除主题缓存: {theme_name}")
    
    def reload_theme(self, theme_name: Optional[str] = None) -> bool:
        """
        重新加载主题（清除缓存后重新加载）
        
        Args:
            theme_name: 主题名称，如果为None则重新加载当前主题
            
        Returns:
            是否成功重新加载
        """
        if theme_name is None:
            theme_name = self.current_theme
        
        if theme_name is None:
            logger.warning("未指定主题且当前主题为空")
            return False
        
        # 清除缓存
        self.clear_cache(theme_name)
        
        # 重新加载
        qss = self.load_theme(theme_name, use_cache=True)
        
        if not qss:
            logger.error(f"重新加载主题失败: {theme_name}")
            return False
        
        # 如果是当前主题，重新应用到应用程序
        if theme_name == self.current_theme:
            app = QApplication.instance()
            if app:
                return self.apply_theme(app, theme_name, emit_signal=False)
        
        logger.info(f"✅ 成功重新加载主题: {theme_name}")
        return True
    
    def get_cached_themes(self) -> List[str]:
        """
        获取已缓存的主题列表
        
        Returns:
            已缓存的主题名称列表
        """
        return list(self._theme_cache.keys())
    
    def is_theme_cached(self, theme_name: str) -> bool:
        """
        检查主题是否已缓存
        
        Args:
            theme_name: 主题名称
            
        Returns:
            是否已缓存
        """
        return theme_name in self._theme_cache


# 全局单例实例
style_system = StyleSystem()


# 便捷函数
def apply_theme(app: QApplication, theme_name: str) -> bool:
    """
    便捷函数：应用主题到应用程序
    
    Args:
        app: QApplication实例
        theme_name: 主题名称
        
    Returns:
        是否成功应用
    """
    return style_system.apply_theme(app, theme_name)


def get_current_theme() -> Optional[str]:
    """
    便捷函数：获取当前主题名称
    
    Returns:
        当前主题名称，如果未设置则返回None
    """
    return style_system.current_theme

