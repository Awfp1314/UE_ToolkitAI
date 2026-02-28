"""
LogService - 统一的日志服务

封装 Logger，提供简化的日志访问接口
Level 0 服务：无依赖
"""

import logging
from core.logger import Logger


class LogService:
    """统一的日志服务
    
    封装 Logger，提供简化的日志访问接口
    
    特点：
    - Level 0 服务，无依赖
    - 封装现有 Logger 类
    - 线程安全（Logger 本身是线程安全的单例）
    """
    
    def __init__(self):
        """初始化日志服务
        
        注意：保持初始化安静，避免污染控制台
        """
        # 确保全局 Logger 已初始化
        self._logger_instance = Logger()
    
    def get_logger(self, name: str) -> logging.Logger:
        """获取日志记录器

        Args:
            name: 日志记录器名称

        Returns:
            logging.Logger 实例

        Example:
            logger = log_service.get_logger("my_module")
            logger.info("这是一条日志")
        """
        # 直接使用已初始化的 Logger 实例，避免重复调用 Logger()
        return self._logger_instance.get_logger(name)
    
    def set_level(self, level: int) -> None:
        """设置全局日志级别
        
        Args:
            level: 日志级别 (logging.DEBUG, logging.INFO, etc.)
            
        Example:
            log_service.set_level(logging.DEBUG)
        """
        self._logger_instance.set_level(level)
    
    def cleanup(self) -> None:
        """清理日志处理器
        
        释放日志系统占用的资源（文件句柄等）
        
        注意：
        - 应在应用退出时调用
        - 清理后可以重新初始化
        """
        try:
            self._logger_instance.cleanup_handlers()
        except Exception as e:
            try:
                self._logger_instance.get_logger(__name__).error(
                    "LogService 清理日志处理器时出错: %s", e
                )
            except Exception:
                pass
