"""
文件操作工具类

提供安全的文件操作功能，包括复制、移动、大小计算等。
所有操作都有完善的错误处理和日志记录。
"""

import os
import shutil
from pathlib import Path
from typing import Optional, Callable
from logging import Logger


class FileOperations:
    """文件操作工具类
    
    提供安全的文件和目录操作，包括：
    - 复制目录/文件
    - 移动目录/文件
    - 计算大小
    - 格式化大小显示
    
    所有操作失败时返回 False，不抛出异常。
    """
    
    def __init__(self, logger: Logger):
        """初始化文件操作工具
        
        Args:
            logger: 日志记录器
        """
        self._logger = logger
        self._mock_mode = os.environ.get('ASSET_MANAGER_MOCK_MODE') == '1'
        
        if self._mock_mode:
            self._logger.info("FileOperations: Mock mode enabled")
    
    def _remove_if_exists(self, path: Path) -> bool:
        """如果路径存在则删除

        Args:
            path: 要删除的路径

        Returns:
            bool: 成功返回 True，失败返回 False
        """
        try:
            if path.exists():
                self._logger.warning(f"Removing existing path: {path}")
                if path.is_dir():
                    shutil.rmtree(path)
                else:
                    path.unlink()
            return True
        except Exception as e:
            self._logger.error(f"Failed to remove path {path}: {e}")
            return False

    def safe_copytree(
        self,
        src: Path,
        dst: Path,
        progress_callback: Optional[Callable[[int, int, str], None]] = None
    ) -> bool:
        """安全地复制目录树

        如果目标已存在，先删除再复制（覆盖模式）。

        Args:
            src: 源目录路径
            dst: 目标目录路径
            progress_callback: 进度回调函数 (current, total, message)

        Returns:
            bool: 成功返回 True，失败返回 False
        """
        # Mock 模式：模拟成功
        if self._mock_mode:
            self._logger.info(f"[Mock] Copying tree: {src} -> {dst}")
            if progress_callback:
                progress_callback(1, 1, "Mock copy completed")
            return True

        # 检查源路径
        if not src.exists():
            self._logger.error(f"Source path does not exist: {src}")
            return False

        # 删除目标路径（如果存在）
        if not self._remove_if_exists(dst):
            return False

        # 执行复制
        try:
            self._logger.info(f"Copying tree: {src} -> {dst}")
            shutil.copytree(src, dst)
            if progress_callback:
                progress_callback(1, 1, f"Copied {src.name}")
            self._logger.info(f"Successfully copied tree: {src} -> {dst}")
            return True
        except (PermissionError, OSError) as e:
            self._logger.error(f"Failed to copy tree: {e}")
            return False
        except Exception as e:
            self._logger.error(f"Unexpected error: {e}")
            return False
    
    def safe_move_tree(
        self,
        src: Path,
        dst: Path,
        progress_callback: Optional[Callable[[int, int, str], None]] = None
    ) -> bool:
        """安全地移动目录树

        如果目标已存在，返回 False（不覆盖）。

        Args:
            src: 源目录路径
            dst: 目标目录路径
            progress_callback: 进度回调函数 (current, total, message)

        Returns:
            bool: 成功返回 True，失败返回 False
        """
        # Mock 模式：模拟成功
        if self._mock_mode:
            self._logger.info(f"[Mock] Moving tree: {src} -> {dst}")
            if progress_callback:
                progress_callback(1, 1, "Mock move completed")
            return True

        # 检查源路径
        if not src.exists():
            self._logger.error(f"Source path does not exist: {src}")
            return False

        # 检查目标路径（不覆盖）
        if dst.exists():
            self._logger.error(f"Target path already exists: {dst}")
            return False

        # 执行移动
        try:
            self._logger.info(f"Moving tree: {src} -> {dst}")
            shutil.move(str(src), str(dst))
            if progress_callback:
                progress_callback(1, 1, f"Moved {src.name}")
            self._logger.info(f"Successfully moved tree: {src} -> {dst}")
            return True
        except (PermissionError, OSError) as e:
            self._logger.error(f"Failed to move tree: {e}")
            return False
        except Exception as e:
            self._logger.error(f"Unexpected error: {e}")
            return False
    
    def safe_move_file(
        self,
        src: Path,
        dst: Path,
        progress_callback: Optional[Callable[[int, int, str], None]] = None
    ) -> bool:
        """安全地移动文件

        如果目标已存在，先删除再移动（覆盖模式）。

        Args:
            src: 源文件路径
            dst: 目标文件路径
            progress_callback: 进度回调函数 (current, total, message)

        Returns:
            bool: 成功返回 True，失败返回 False
        """
        # Mock 模式：模拟成功
        if self._mock_mode:
            self._logger.info(f"[Mock] Moving file: {src} -> {dst}")
            if progress_callback:
                progress_callback(1, 1, "Mock move completed")
            return True

        # 检查源路径
        if not src.exists():
            self._logger.error(f"Source file does not exist: {src}")
            return False

        # 删除目标文件（如果存在）
        if not self._remove_if_exists(dst):
            return False

        # 执行移动
        try:
            self._logger.info(f"Moving file: {src} -> {dst}")
            shutil.move(str(src), str(dst))
            if progress_callback:
                progress_callback(1, 1, f"Moved {src.name}")
            self._logger.info(f"Successfully moved file: {src} -> {dst}")
            return True
        except (PermissionError, OSError) as e:
            self._logger.error(f"Failed to move file: {e}")
            return False
        except Exception as e:
            self._logger.error(f"Unexpected error: {e}")
            return False
    
    def calculate_size(self, path: Path) -> int:
        """计算文件或目录的大小

        Args:
            path: 文件或目录路径

        Returns:
            int: 大小（字节），失败返回 0
        """
        try:
            if not path.exists():
                return 0

            if path.is_file():
                return path.stat().st_size

            # 计算目录大小
            total_size = 0
            for item in path.rglob('*'):
                if item.is_file():
                    total_size += item.stat().st_size
            return total_size
        except Exception as e:
            self._logger.error(f"Failed to calculate size for {path}: {e}")
            return 0
    
    def format_size(self, size_bytes: int) -> str:
        """格式化文件大小为人类可读格式

        Args:
            size_bytes: 字节数

        Returns:
            str: 格式化后的大小，如 "1.5 MB"
        """
        units = ['B', 'KB', 'MB', 'GB', 'TB']
        size = float(size_bytes)
        unit_index = 0

        while size >= 1024.0 and unit_index < len(units) - 1:
            size /= 1024.0
            unit_index += 1

        if unit_index == 0:
            return f"{int(size)} {units[unit_index]}"
        return f"{size:.1f} {units[unit_index]}"

