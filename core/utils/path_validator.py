# -*- coding: utf-8 -*-

"""
路径验证工具模块
提供统一的路径验证方法，减少代码重复
"""

import os
from pathlib import Path
from typing import Optional

from core.logger import get_logger
from core.exceptions import ConfigError

logger = get_logger(__name__)


class PathValidator:
    """路径验证工具类
    
    提供统一的路径验证方法，包括存在性、可写性、目录/文件类型验证等
    """
    
    @staticmethod
    def validate_exists(path: Path, name: str = "Path") -> Path:
        """验证路径是否存在
        
        Args:
            path: 要验证的路径
            name: 路径的描述名称（用于错误消息）
            
        Returns:
            验证通过的路径对象
            
        Raises:
            FileNotFoundError: 如果路径不存在
        """
        if not path.exists():
            error_msg = f"{name} does not exist: {path}"
            logger.error(error_msg)
            raise FileNotFoundError(error_msg)
        
        logger.debug(f"{name} exists: {path}")
        return path
    
    @staticmethod
    def validate_writable(path: Path, name: str = "Path") -> Path:
        """验证路径是否可写
        
        Args:
            path: 要验证的路径
            name: 路径的描述名称（用于错误消息）
            
        Returns:
            验证通过的路径对象
            
        Raises:
            PermissionError: 如果路径不可写
        """
        # 如果路径不存在，检查父目录是否可写
        target_path = path if path.exists() else path.parent
        
        if not os.access(target_path, os.W_OK):
            error_msg = f"No write permission for {name}: {path}"
            logger.error(error_msg)
            raise PermissionError(error_msg)
        
        logger.debug(f"{name} is writable: {path}")
        return path
    
    @staticmethod
    def validate_directory(path: Path, name: str = "Directory") -> Path:
        """验证路径是否为目录
        
        Args:
            path: 要验证的路径
            name: 路径的描述名称（用于错误消息）
            
        Returns:
            验证通过的路径对象
            
        Raises:
            NotADirectoryError: 如果路径不是目录
        """
        if not path.is_dir():
            error_msg = f"{name} is not a directory: {path}"
            logger.error(error_msg)
            raise NotADirectoryError(error_msg)
        
        logger.debug(f"{name} is a directory: {path}")
        return path
    
    @staticmethod
    def validate_file(path: Path, name: str = "File") -> Path:
        """验证路径是否为文件
        
        Args:
            path: 要验证的路径
            name: 路径的描述名称（用于错误消息）
            
        Returns:
            验证通过的路径对象
            
        Raises:
            FileNotFoundError: 如果路径不是文件
        """
        if not path.is_file():
            error_msg = f"{name} is not a file: {path}"
            logger.error(error_msg)
            raise FileNotFoundError(error_msg)
        
        logger.debug(f"{name} is a file: {path}")
        return path
    
    @staticmethod
    def validate_readable(path: Path, name: str = "Path") -> Path:
        """验证路径是否可读
        
        Args:
            path: 要验证的路径
            name: 路径的描述名称（用于错误消息）
            
        Returns:
            验证通过的路径对象
            
        Raises:
            PermissionError: 如果路径不可读
        """
        if not os.access(path, os.R_OK):
            error_msg = f"No read permission for {name}: {path}"
            logger.error(error_msg)
            raise PermissionError(error_msg)
        
        logger.debug(f"{name} is readable: {path}")
        return path
    
    @staticmethod
    def ensure_directory_exists(path: Path, name: str = "Directory") -> Path:
        """确保目录存在，如果不存在则创建
        
        Args:
            path: 目录路径
            name: 路径的描述名称（用于错误消息）
            
        Returns:
            目录路径对象
            
        Raises:
            PermissionError: 如果无法创建目录
            OSError: 如果创建目录时发生其他错误
        """
        try:
            path.mkdir(parents=True, exist_ok=True)
            logger.debug(f"{name} ensured to exist: {path}")
            return path
        except PermissionError as e:
            error_msg = f"No permission to create {name}: {path}"
            logger.error(error_msg)
            raise PermissionError(error_msg) from e
        except OSError as e:
            error_msg = f"Failed to create {name}: {path}"
            logger.error(error_msg, exc_info=True)
            raise OSError(error_msg) from e
    
    @staticmethod
    def validate_path_chain(
        path: Path,
        name: str = "Path",
        must_exist: bool = True,
        must_be_dir: Optional[bool] = None,
        must_be_writable: bool = False,
        must_be_readable: bool = False
    ) -> Path:
        """链式验证路径的多个属性
        
        Args:
            path: 要验证的路径
            name: 路径的描述名称（用于错误消息）
            must_exist: 是否必须存在
            must_be_dir: 是否必须是目录（None表示不检查）
            must_be_writable: 是否必须可写
            must_be_readable: 是否必须可读
            
        Returns:
            验证通过的路径对象
            
        Raises:
            FileNotFoundError: 如果路径不存在（当must_exist=True时）
            NotADirectoryError: 如果路径不是目录（当must_be_dir=True时）
            PermissionError: 如果权限不足
        """
        if must_exist:
            PathValidator.validate_exists(path, name)
        
        if must_be_dir is not None:
            if must_be_dir:
                PathValidator.validate_directory(path, name)
            else:
                PathValidator.validate_file(path, name)
        
        if must_be_writable:
            PathValidator.validate_writable(path, name)
        
        if must_be_readable:
            PathValidator.validate_readable(path, name)
        
        return path


__all__ = ["PathValidator"]
