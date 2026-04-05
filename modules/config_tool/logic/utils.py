# -*- coding: utf-8 -*-

"""
配置工具实用函数

包含错误处理、文件操作和验证等实用函数。
"""

import shutil
from pathlib import Path
from typing import Tuple

from core.logger import get_logger

logger = get_logger(__name__)


def safe_copy_file(src: Path, dst: Path) -> Tuple[bool, str]:
    """安全复制文件

    Args:
        src: 源文件路径
        dst: 目标文件路径

    Returns:
        (是否成功, 错误消息)
    """
    try:
        # 确保目标目录存在
        dst.parent.mkdir(parents=True, exist_ok=True)
        
        # 复制文件
        shutil.copy2(src, dst)
        logger.debug(f"成功复制文件: {src} -> {dst}")
        return True, ""
        
    except PermissionError:
        error_msg = f"没有权限访问文件: {dst}"
        logger.error(error_msg)
        return False, error_msg
        
    except OSError as e:
        if e.errno == 28:  # No space left on device
            error_msg = "磁盘空间不足"
            logger.error(error_msg)
            return False, error_msg
        error_msg = f"文件操作失败: {e}"
        logger.error(error_msg)
        return False, error_msg
        
    except Exception as e:
        logger.error(f"复制文件失败: {src} -> {dst}", exc_info=True)
        error_msg = "文件复制失败，请检查文件是否被占用"
        return False, error_msg


def validate_config_name(name: str) -> Tuple[bool, str]:
    """验证配置名称

    Args:
        name: 配置名称

    Returns:
        (是否有效, 错误消息)
    """
    if not name or not name.strip():
        return False, "配置名称不能为空"

    if len(name) > 100:
        return False, "配置名称不能超过 100 个字符"

    # 检查非法字符
    invalid_chars = '<>:"/\\|?*'
    if any(c in name for c in invalid_chars):
        return False, f"配置名称不能包含以下字符: {invalid_chars}"

    return True, ""


def sanitize_filename(filename: str) -> str:
    """清理文件名，移除非法字符

    Args:
        filename: 原始文件名

    Returns:
        清理后的文件名
    """
    # 移除非法字符
    invalid_chars = '<>:"/\\|?*'
    for char in invalid_chars:
        filename = filename.replace(char, '_')

    # 移除前后空白
    filename = filename.strip()

    # 限制长度
    if len(filename) > 100:
        filename = filename[:100]

    return filename


def validate_path(path: Path, base_path: Path) -> bool:
    """验证路径是否在基础路径下

    Args:
        path: 要验证的路径
        base_path: 基础路径

    Returns:
        是否有效
    """
    try:
        resolved_path = path.resolve()
        resolved_base = base_path.resolve()
        
        # Python 3.9+ 使用 is_relative_to
        try:
            return resolved_path.is_relative_to(resolved_base)
        except AttributeError:
            # Python 3.8 兼容性处理
            try:
                resolved_path.relative_to(resolved_base)
                return True
            except ValueError:
                return False
                
    except (ValueError, OSError):
        logger.error(f"路径验证失败: {path}")
        return False


def check_write_permission(path: Path) -> bool:
    """检查是否有写入权限

    Args:
        path: 目标路径

    Returns:
        是否有权限
    """
    import os
    
    try:
        if path.exists():
            return os.access(path, os.W_OK)
        else:
            return os.access(path.parent, os.W_OK)
    except OSError:
        return False


def format_file_size(size_bytes: int) -> str:
    """格式化文件大小

    Args:
        size_bytes: 文件大小（字节）

    Returns:
        格式化后的文件大小字符串
    """
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size_bytes < 1024.0:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.1f} TB"
