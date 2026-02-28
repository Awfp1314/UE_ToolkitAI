# -*- coding: utf-8 -*-

"""
配置访问工具模块
提供简化的配置访问方法，支持点号表示法
"""

from typing import Any, Optional

from core.logger import get_logger
from core.exceptions import ConfigError

logger = get_logger(__name__)


class ConfigAccessor:
    """配置访问工具类
    
    提供简化的配置访问方法，支持点号表示法（如 "database.host"）
    """
    
    def __init__(self, config_manager):
        """初始化配置访问器
        
        Args:
            config_manager: ConfigManager实例
        """
        self.config_manager = config_manager
    
    def get_value(
        self,
        key: str,
        default: Any = None,
        required: bool = False
    ) -> Any:
        """获取配置值（支持点号表示法）
        
        Args:
            key: 配置键，支持点号表示法（如 "database.host"）
            default: 默认值（当键不存在时返回）
            required: 是否为必需配置（如果为True且键不存在，则抛出异常）
            
        Returns:
            配置值，如果不存在则返回默认值
            
        Raises:
            ConfigError: 如果required=True且配置键不存在
            
        Examples:
            >>> accessor.get_value("theme", default="dark")
            'dark'
            >>> accessor.get_value("window.width", default=1280)
            1280
            >>> accessor.get_value("api.key", required=True)
            ConfigError: Required config key missing: api.key
        """
        try:
            config = self.config_manager.get_all_config()
            
            # 支持嵌套键：如 "database.host"
            keys = key.split('.')
            value = config
            
            for k in keys:
                if isinstance(value, dict) and k in value:
                    value = value[k]
                else:
                    # 键不存在
                    if required:
                        error_msg = f"Required config key missing: {key}"
                        logger.error(error_msg)
                        raise ConfigError(error_msg)
                    
                    logger.debug(f"Config key not found: {key}, using default: {default}")
                    return default
            
            logger.debug(f"Config value retrieved: {key} = {value}")
            return value
            
        except ConfigError:
            # 重新抛出ConfigError
            raise
        except Exception as e:
            error_msg = f"Error accessing config key '{key}': {e}"
            logger.error(error_msg, exc_info=True)
            if required:
                raise ConfigError(error_msg) from e
            return default
    
    def set_value(self, key: str, value: Any) -> bool:
        """设置配置值（支持点号表示法）
        
        Args:
            key: 配置键，支持点号表示法（如 "database.host"）
            value: 配置值
            
        Returns:
            True表示设置成功，False表示失败
            
        Examples:
            >>> accessor.set_value("theme", "light")
            True
            >>> accessor.set_value("window.width", 1920)
            True
        """
        try:
            config = self.config_manager.get_all_config()
            
            # 支持嵌套键：如 "database.host"
            keys = key.split('.')
            
            # 导航到目标位置
            current = config
            for k in keys[:-1]:
                if k not in current:
                    current[k] = {}
                elif not isinstance(current[k], dict):
                    # 中间键不是字典，无法继续
                    error_msg = f"Cannot set nested key '{key}': intermediate key '{k}' is not a dict"
                    logger.error(error_msg)
                    raise ConfigError(error_msg)
                current = current[k]
            
            # 设置最终值
            final_key = keys[-1]
            current[final_key] = value
            
            # 保存配置
            self.config_manager._save_config(config)
            logger.debug(f"Config value set: {key} = {value}")
            return True
            
        except ConfigError as e:
            logger.error(f"Failed to set config value '{key}': {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error setting config value '{key}': {e}", exc_info=True)
            return False
    
    def get_required(self, key: str) -> Any:
        """获取必需的配置值（如果不存在则抛出异常）
        
        这是 get_value(key, required=True) 的快捷方法
        
        Args:
            key: 配置键
            
        Returns:
            配置值
            
        Raises:
            ConfigError: 如果配置键不存在
        """
        return self.get_value(key, required=True)
    
    def has_key(self, key: str) -> bool:
        """检查配置键是否存在
        
        Args:
            key: 配置键，支持点号表示法
            
        Returns:
            True表示键存在，False表示不存在
        """
        try:
            config = self.config_manager.get_all_config()
            
            keys = key.split('.')
            value = config
            
            for k in keys:
                if isinstance(value, dict) and k in value:
                    value = value[k]
                else:
                    return False
            
            return True
            
        except Exception as e:
            logger.debug(f"Error checking config key '{key}': {e}")
            return False
    
    def delete_value(self, key: str) -> bool:
        """删除配置值
        
        Args:
            key: 配置键，支持点号表示法
            
        Returns:
            True表示删除成功，False表示键不存在或删除失败
        """
        try:
            config = self.config_manager.get_all_config()
            
            keys = key.split('.')
            
            # 导航到父级
            current = config
            for k in keys[:-1]:
                if isinstance(current, dict) and k in current:
                    current = current[k]
                else:
                    # 键不存在
                    logger.debug(f"Config key not found for deletion: {key}")
                    return False
            
            # 删除最终键
            final_key = keys[-1]
            if isinstance(current, dict) and final_key in current:
                del current[final_key]
                self.config_manager._save_config(config)
                logger.debug(f"Config value deleted: {key}")
                return True
            else:
                logger.debug(f"Config key not found for deletion: {key}")
                return False
                
        except Exception as e:
            logger.error(f"Error deleting config value '{key}': {e}", exc_info=True)
            return False


__all__ = ["ConfigAccessor"]
