# -*- coding: utf-8 -*-
"""
AppData 路径自动迁移模块

在程序启动时检测旧路径，如果存在则自动迁移到新路径。
"""

import os
import shutil
from pathlib import Path
from typing import Optional
import logging


def get_old_appdata_path() -> Path:
    """获取旧的 AppData 路径"""
    appdata = os.environ.get("APPDATA", "")
    return Path(appdata) / "UE Toolkit" / "ue_toolkit"


def get_new_appdata_path() -> Path:
    """获取新的 AppData 路径"""
    appdata = os.environ.get("APPDATA", "")
    return Path(appdata) / "ue_toolkit"


def should_migrate() -> bool:
    """检查是否需要迁移"""
    old_path = get_old_appdata_path()
    new_path = get_new_appdata_path()
    
    # 旧路径存在且新路径不存在，需要迁移
    return old_path.exists() and not new_path.exists()


def migrate_appdata_path(logger: Optional[logging.Logger] = None) -> bool:
    """
    迁移 AppData 路径
    
    Args:
        logger: 日志记录器（可选）
    
    Returns:
        bool: 迁移是否成功
    """
    old_path = get_old_appdata_path()
    new_path = get_new_appdata_path()
    
    if not should_migrate():
        return True
    
    try:
        if logger:
            logger.info(f"检测到旧路径数据，开始迁移...")
            logger.info(f"  从: {old_path}")
            logger.info(f"  到: {new_path}")
        
        # 确保新路径的父目录存在
        new_path.parent.mkdir(parents=True, exist_ok=True)
        
        # 复制数据（使用复制而不是移动，避免权限问题）
        shutil.copytree(old_path, new_path, dirs_exist_ok=True)
        
        if logger:
            logger.info("数据迁移完成")
        
        # 尝试删除旧路径（如果失败也不影响）
        try:
            shutil.rmtree(old_path)
            old_parent = old_path.parent
            if old_parent.exists() and not any(old_parent.iterdir()):
                old_parent.rmdir()
            if logger:
                logger.info("旧路径已清理")
        except Exception as e:
            if logger:
                logger.warning(f"清理旧路径失败（不影响使用）: {e}")
        
        return True
        
    except Exception as e:
        if logger:
            logger.error(f"路径迁移失败: {e}")
        return False


def check_and_migrate(logger: Optional[logging.Logger] = None) -> None:
    """
    检查并执行路径迁移（如果需要）
    
    Args:
        logger: 日志记录器（可选）
    """
    if should_migrate():
        migrate_appdata_path(logger)
