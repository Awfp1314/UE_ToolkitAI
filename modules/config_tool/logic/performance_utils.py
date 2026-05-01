# -*- coding: utf-8 -*-

"""
性能优化工具

提供配置工具模块的性能优化功能：
- 大文件复制进度报告
- 异步操作支持
- 临时文件清理
"""

import shutil
import os
from pathlib import Path
from typing import Optional, Callable
from core.logger import get_logger

logger = get_logger(__name__)


def copy_with_progress(
    src: Path,
    dst: Path,
    progress_callback: Optional[Callable[[int, int], None]] = None
) -> bool:
    """复制文件并报告进度
    
    Args:
        src: 源文件路径
        dst: 目标文件路径
        progress_callback: 进度回调函数 (已复制字节数, 总字节数)
        
    Returns:
        是否成功
    """
    try:
        # 确保目标目录存在
        dst.parent.mkdir(parents=True, exist_ok=True)
        
        # 获取文件大小
        file_size = src.stat().st_size
        
        # 如果文件小于 10MB，直接复制
        if file_size < 10 * 1024 * 1024:
            shutil.copy2(src, dst)
            if progress_callback:
                progress_callback(file_size, file_size)
            return True
        
        # 大文件分块复制
        buffer_size = 1024 * 1024  # 1MB 缓冲区
        copied = 0
        
        with open(src, 'rb') as fsrc:
            with open(dst, 'wb') as fdst:
                while True:
                    buf = fsrc.read(buffer_size)
                    if not buf:
                        break
                    fdst.write(buf)
                    copied += len(buf)
                    
                    # 报告进度
                    if progress_callback:
                        progress_callback(copied, file_size)
        
        # 复制文件元数据
        shutil.copystat(src, dst)
        
        logger.info(f"大文件复制完成: {src} -> {dst}, 大小: {file_size / 1024 / 1024:.2f} MB")
        return True
        
    except Exception as e:
        logger.error(f"复制文件失败: {src} -> {dst}, 错误: {e}", exc_info=True)
        return False


def copytree_with_progress(
    src: Path,
    dst: Path,
    progress_callback: Optional[Callable[[int, int], None]] = None
) -> bool:
    """复制目录树并报告进度
    
    Args:
        src: 源目录路径
        dst: 目标目录路径
        progress_callback: 进度回调函数 (已复制文件数, 总文件数)
        
    Returns:
        是否成功
    """
    try:
        # 极速预计算总文件数（不触发 stat）
        total_files = sum(len(files) for _, _, files in os.walk(src))
        copied_files = 0
        
        # 创建目标目录
        dst.mkdir(parents=True, exist_ok=True)
        
        # 遍历并复制
        for root, dirs, files in os.walk(src):
            rel_root = Path(root).relative_to(src)
            target_root = dst / rel_root
            
            # 创建目录
            for dir_name in dirs:
                (target_root / dir_name).mkdir(parents=True, exist_ok=True)
            
            # 复制文件
            for file_name in files:
                src_file = Path(root) / file_name
                dst_file = target_root / file_name
                shutil.copy2(src_file, dst_file)
                copied_files += 1
                
                # 报告进度
                if progress_callback:
                    progress_callback(copied_files, total_files)
        
        logger.info(f"目录树复制完成: {src} -> {dst}, 文件数: {total_files}")
        return True
        
    except Exception as e:
        logger.error(f"复制目录树失败: {src} -> {dst}, 错误: {e}", exc_info=True)
        return False


def cleanup_temp_files(project_path: Path) -> int:
    """清理项目临时文件
    
    清理以下目录：
    - Intermediate/
    - Binaries/
    - DerivedDataCache/
    - Saved/Logs/
    - Saved/Crashes/
    
    Args:
        project_path: 项目路径
        
    Returns:
        清理的文件数量
    """
    cleaned_count = 0
    
    # 要清理的目录列表
    cleanup_dirs = [
        "Intermediate",
        "Binaries",
        "DerivedDataCache",
        "Saved/Logs",
        "Saved/Crashes"
    ]
    
    for dir_name in cleanup_dirs:
        dir_path = project_path / dir_name
        if dir_path.exists():
            try:
                # 直接删除目录
                shutil.rmtree(dir_path)
                cleaned_count += 1
                
                logger.info(f"清理临时目录: {dir_path}")
                
            except Exception as e:
                logger.warning(f"清理临时目录失败: {dir_path}, 错误: {e}")
    
    logger.info(f"临时文件清理完成，共清理 {cleaned_count} 个目录")
    return cleaned_count


def get_directory_size(path: Path) -> int:
    """获取目录大小（字节）
    
    Args:
        path: 目录路径
        
    Returns:
        目录大小（字节）
    """
    total_size = 0
    
    try:
        for entry in os.scandir(path):
            if entry.is_file(follow_symlinks=False):
                total_size += entry.stat().st_size
            elif entry.is_dir(follow_symlinks=False):
                total_size += get_directory_size(Path(entry.path))
    except Exception as e:
        logger.warning(f"计算目录大小失败: {path}, 错误: {e}")
    
    return total_size


def format_size(size_bytes: int) -> str:
    """格式化文件大小
    
    Args:
        size_bytes: 字节数
        
    Returns:
        格式化的大小字符串（如 "1.5 MB"）
    """
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    elif size_bytes < 1024 * 1024 * 1024:
        return f"{size_bytes / 1024 / 1024:.1f} MB"
    else:
        return f"{size_bytes / 1024 / 1024 / 1024:.1f} GB"
