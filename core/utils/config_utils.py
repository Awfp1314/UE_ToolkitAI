# -*- coding: utf-8 -*-

"""
配置文件工具模块
提供集中化的配置文件读写操作，支持 JSON 和 YAML 格式
"""

import json
import shutil
from pathlib import Path
from typing import Any, Dict, Optional, Union

import yaml

from core.logger import get_logger
from core.exceptions import ConfigError

logger = get_logger(__name__)


class ConfigUtils:
    """配置文件工具类
    
    提供静态方法用于读写 JSON 和 YAML 配置文件，
    包含错误处理、默认值支持和备份创建功能。
    
    Examples:
        >>> # 读取 JSON 配置
        >>> config = ConfigUtils.read_json(Path("config.json"), default={})
        
        >>> # 写入 JSON 配置（自动创建备份）
        >>> ConfigUtils.write_json(Path("config.json"), {"key": "value"})
        
        >>> # 读取 YAML 配置
        >>> config = ConfigUtils.read_yaml(Path("config.yaml"))
    """
    
    @staticmethod
    def read_json(
        path: Union[str, Path],
        default: Optional[Any] = None
    ) -> Optional[Dict[str, Any]]:
        """读取 JSON 配置文件
        
        Args:
            path: JSON 文件路径
            default: 文件不存在时返回的默认值
            
        Returns:
            配置字典，文件不存在时返回 default
            
        Raises:
            ConfigError: 文件存在但 JSON 格式无效时
            
        Examples:
            >>> config = ConfigUtils.read_json("config.json", default={})
            >>> config = ConfigUtils.read_json(Path("settings.json"))
        """
        path = Path(path)
        
        if not path.exists():
            logger.debug(f"Config file not found: {path}, returning default")
            return default
        
        try:
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            logger.debug(f"Successfully read JSON config from: {path}")
            return data
        except json.JSONDecodeError as e:
            error_msg = f"Invalid JSON format in {path}: {e}"
            logger.error(error_msg)
            raise ConfigError(error_msg) from e
        except PermissionError as e:
            error_msg = f"Permission denied reading {path}: {e}"
            logger.error(error_msg)
            raise ConfigError(error_msg) from e
        except OSError as e:
            error_msg = f"OS error reading {path}: {e}"
            logger.error(error_msg, exc_info=True)
            raise ConfigError(error_msg) from e
    
    @staticmethod
    def write_json(
        path: Union[str, Path],
        data: Dict[str, Any],
        create_backup: bool = True,
        indent: int = 2
    ) -> bool:
        """写入 JSON 配置文件
        
        Args:
            path: JSON 文件路径
            data: 要写入的配置数据
            create_backup: 是否在写入前创建备份文件（.bak）
            indent: JSON 缩进空格数
            
        Returns:
            True 表示写入成功
            
        Raises:
            ConfigError: 写入失败时
            
        Examples:
            >>> ConfigUtils.write_json("config.json", {"key": "value"})
            >>> ConfigUtils.write_json(Path("settings.json"), data, create_backup=False)
        """
        path = Path(path)
        
        try:
            # 确保父目录存在
            path.parent.mkdir(parents=True, exist_ok=True)
            
            # 创建备份
            if create_backup and path.exists():
                backup_path = path.with_suffix(path.suffix + '.bak')
                shutil.copy2(path, backup_path)
                logger.debug(f"Created backup: {backup_path}")
            
            # 写入文件
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=indent, ensure_ascii=False)
            
            logger.debug(f"Successfully wrote JSON config to: {path}")
            return True
            
        except PermissionError as e:
            error_msg = f"Permission denied writing {path}: {e}"
            logger.error(error_msg)
            raise ConfigError(error_msg) from e
        except OSError as e:
            error_msg = f"OS error writing {path}: {e}"
            logger.error(error_msg, exc_info=True)
            raise ConfigError(error_msg) from e
    
    @staticmethod
    def read_yaml(
        path: Union[str, Path],
        default: Optional[Any] = None
    ) -> Optional[Dict[str, Any]]:
        """读取 YAML 配置文件
        
        Args:
            path: YAML 文件路径
            default: 文件不存在时返回的默认值
            
        Returns:
            配置字典，文件不存在时返回 default
            
        Raises:
            ConfigError: 文件存在但 YAML 格式无效时
            
        Examples:
            >>> config = ConfigUtils.read_yaml("config.yaml", default={})
            >>> config = ConfigUtils.read_yaml(Path("settings.yml"))
        """
        path = Path(path)
        
        if not path.exists():
            logger.debug(f"Config file not found: {path}, returning default")
            return default
        
        try:
            with open(path, 'r', encoding='utf-8') as f:
                data = yaml.safe_load(f)
            # yaml.safe_load 对空文件返回 None
            if data is None:
                data = {}
            logger.debug(f"Successfully read YAML config from: {path}")
            return data
        except yaml.YAMLError as e:
            error_msg = f"Invalid YAML format in {path}: {e}"
            logger.error(error_msg)
            raise ConfigError(error_msg) from e
        except PermissionError as e:
            error_msg = f"Permission denied reading {path}: {e}"
            logger.error(error_msg)
            raise ConfigError(error_msg) from e
        except OSError as e:
            error_msg = f"OS error reading {path}: {e}"
            logger.error(error_msg, exc_info=True)
            raise ConfigError(error_msg) from e
    
    @staticmethod
    def write_yaml(
        path: Union[str, Path],
        data: Dict[str, Any],
        create_backup: bool = True
    ) -> bool:
        """写入 YAML 配置文件
        
        Args:
            path: YAML 文件路径
            data: 要写入的配置数据
            create_backup: 是否在写入前创建备份文件（.bak）
            
        Returns:
            True 表示写入成功
            
        Raises:
            ConfigError: 写入失败时
            
        Examples:
            >>> ConfigUtils.write_yaml("config.yaml", {"key": "value"})
            >>> ConfigUtils.write_yaml(Path("settings.yml"), data, create_backup=False)
        """
        path = Path(path)
        
        try:
            # 确保父目录存在
            path.parent.mkdir(parents=True, exist_ok=True)
            
            # 创建备份
            if create_backup and path.exists():
                backup_path = path.with_suffix(path.suffix + '.bak')
                shutil.copy2(path, backup_path)
                logger.debug(f"Created backup: {backup_path}")
            
            # 写入文件
            with open(path, 'w', encoding='utf-8') as f:
                yaml.safe_dump(data, f, allow_unicode=True, default_flow_style=False)
            
            logger.debug(f"Successfully wrote YAML config to: {path}")
            return True
            
        except PermissionError as e:
            error_msg = f"Permission denied writing {path}: {e}"
            logger.error(error_msg)
            raise ConfigError(error_msg) from e
        except OSError as e:
            error_msg = f"OS error writing {path}: {e}"
            logger.error(error_msg, exc_info=True)
            raise ConfigError(error_msg) from e


__all__ = ["ConfigUtils"]
