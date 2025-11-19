# -*- coding: utf-8 -*-

from PyQt6.QtWidgets import QWidget
from modules.config_tool.logic.config_tool_logic import ConfigToolLogic
from typing import Optional

# 使用统一的日志系统
from core.logger import get_logger
from core.utils.cleanup_result import CleanupResult
logger = get_logger(__name__)


class ConfigToolModule:
    """配置工具模块主类"""
    
    def __init__(self, parent=None):
        self.parent = parent
        self.ui: Optional[QWidget] = None  # 延迟初始化UI  # TODO: 改为具体的 UI 类型
        self.logic: Optional[ConfigToolLogic] = None
        logger.info("ConfigToolModule 初始化")
    
    def initialize(self, config_dir: str):
        """初始化模块"""
        logger.info(f"初始化配置工具模块，配置目录: {config_dir}")
        self.logic = ConfigToolLogic(config_dir)
        # 注意：UI将在get_widget时创建
        logger.info("配置工具模块初始化完成")
    
    def setup_connections(self):
        """设置信号槽连接"""
        if self.ui and hasattr(self.ui, 'add_config_button') and self.ui.add_config_button:
            # 连接添加配置按钮的点击事件
            self.ui.add_config_button.clicked.connect(self.ui.on_add_config_clicked)
            logger.info("信号槽连接设置完成")
    
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
            logger.info("创建配置工具占位 UI")
            # 使用占位 UI，避免 NotImplementedError
            from modules.config_tool.ui.placeholder_ui import ConfigToolPlaceholderUI
            self.ui = ConfigToolPlaceholderUI()
            logger.info("配置工具占位 UI 创建完成")
            return self.ui

            # TODO: 实现完整的配置工具 UI
            # 请先创建 modules/config_tool/ui/ 目录和 UI 类
            # raise NotImplementedError(
            #     "UI 尚未实现，请先创建 modules/config_tool/ui/ 目录和相应的 UI 类"
            # )

            # 设置逻辑层引用
            if self.logic:
                setattr(self.ui, 'logic', self.logic)
            self.setup_connections()
            # 如果有逻辑数据，更新UI
            if self.logic:
                templates = self.logic.get_templates()
                if templates:
                    self.ui.config_templates = templates
                    self.ui.update_config_buttons()
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