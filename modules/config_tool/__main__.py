# -*- coding: utf-8 -*-

from PyQt6.QtWidgets import QWidget
from .logic.config_tool_logic import ConfigToolLogic
from typing import Optional

# 使用统一的日志系统
from core.logger import get_logger
from core.utils.cleanup_result import CleanupResult
logger = get_logger(__name__)


class ConfigToolModule:
    """配置工具模块主类"""
    
    def __init__(self, parent=None):
        self.parent = parent
        self.ui: Optional['ConfigToolUI'] = None  # 延迟初始化UI
        self.logic: Optional[ConfigToolLogic] = None
        logger.info("ConfigToolModule 初始化")
    
    def initialize(self, config_dir: str):
        """初始化模块"""
        logger.info(f"初始化配置工具模块，配置目录: {config_dir}")
        self.logic = ConfigToolLogic(config_dir)
        
        # 初始化新的存储系统
        from .logic.config_storage import ConfigStorage
        self.storage = ConfigStorage()
        
        # 注意：UI将在get_widget时创建
        logger.info("配置工具模块初始化完成")
    
    def setup_connections(self):
        """设置信号槽连接"""
        # 按钮已经在 UI 的 setup_ui() 中连接，这里不需要重复连接
        logger.info("信号槽连接设置完成（按钮已在UI层连接）")
    
    def on_add_config_clicked(self):
        """添加配置按钮点击事件"""
        logger.info("添加配置按钮被点击")
        # 实际的添加配置逻辑在UI层实现
        if self.ui:
            self.ui.on_add_config_clicked()
    
    def get_widget(self) -> QWidget:
        """获取模块的主界面组件"""
        logger.info("获取配置工具UI组件")
        # 延迟初始化UI，确保只创建一次

        if self.ui is None:
            logger.info("创建工程配置 UI")
            from .ui.config_tool_ui import ConfigToolUI
            self.ui = ConfigToolUI()
            
            # 设置逻辑层引用（使用新的存储系统）
            if hasattr(self, 'storage'):
                # 创建一个简单的逻辑对象来传递存储引用
                class SimpleLogic:
                    def __init__(self, storage):
                        self.storage = storage
                
                self.ui.set_logic(SimpleLogic(self.storage))
                
                # 加载并显示配置模板
                templates = self.storage.list_templates()
                if templates:
                    self.ui.config_templates = templates
                    self.ui.update_config_buttons()
                    logger.info(f"加载了 {len(templates)} 个配置模板")
                else:
                    logger.info("没有配置模板，显示空状态")
            else:
                logger.warning("存储系统未初始化")
            
            self.setup_connections()
            
            logger.info("工程配置 UI 创建完成")
        else:
            logger.info("返回已存在的ConfigToolUI实例")

        return self.ui
    
    def request_stop(self) -> None:
        """请求模块停止操作（在 cleanup 之前调用）"""
        logger.info("请求配置工具模块停止")
        # 配置工具模块没有长时间运行的任务，无需特殊处理

    def cleanup(self) -> CleanupResult:
        """清理资源

        Returns:
            CleanupResult: 清理结果
        """
        logger.info("清理配置工具模块资源")
        try:
            if self.logic:
                self.logic.save_config()

            if self.ui:
                self.ui = None

            logger.info("配置工具模块清理完成")
            return CleanupResult.success_result()
        except Exception as e:
            logger.error(f"清理配置工具模块资源时发生错误: {e}", exc_info=True)
            return CleanupResult.failure_result(str(e))