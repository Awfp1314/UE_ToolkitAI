# -*- coding: utf-8 -*-

"""
压缩包解压工具

支持 .zip、.7z、.rar 三种主流压缩格式的解压操作，
提供进度回调以便在 UI 上展示解压进度。
"""

import os
import tempfile
import zipfile
from pathlib import Path
from typing import Optional, Callable

from core.logger import get_logger

logger = get_logger(__name__)

# 支持的压缩包扩展名
ARCHIVE_EXTENSIONS = {'.zip', '.rar', '.7z'}


def is_archive_file(path: Path) -> bool:
    """判断文件是否为支持的压缩包格式
    
    Args:
        path: 文件路径
        
    Returns:
        bool: 是压缩包返回 True
    """
    return path.is_file() and path.suffix.lower() in ARCHIVE_EXTENSIONS


class ArchiveExtractor:
    """压缩包解压器
    
    支持 .zip（内置）、.7z（py7zr）、.rar（rarfile）
    解压到临时目录，返回解压后的根目录路径。
    """
    
    def __init__(self):
        self._temp_dirs = []  # 记录创建的临时目录，便于清理
    
    def extract(
        self,
        archive_path: Path,
        progress_callback: Optional[Callable[[int, int, str], None]] = None
    ) -> Optional[Path]:
        """解压压缩包到临时目录
        
        Args:
            archive_path: 压缩包文件路径
            progress_callback: 进度回调 (current, total, message)
            
        Returns:
            解压后的临时目录路径，失败返回 None
        """
        if not archive_path.exists():
            logger.error(f"压缩包不存在: {archive_path}")
            return None
        
        suffix = archive_path.suffix.lower()
        
        if suffix == '.zip':
            return self._extract_zip(archive_path, progress_callback)
        elif suffix == '.7z':
            return self._extract_7z(archive_path, progress_callback)
        elif suffix == '.rar':
            return self._extract_rar(archive_path, progress_callback)
        else:
            logger.error(f"不支持的压缩格式: {suffix}")
            return None
    
    def _create_temp_dir(self, prefix: str = "ue_toolkit_extract_") -> Path:
        """创建临时解压目录
        
        Returns:
            临时目录路径
        """
        temp_dir = Path(tempfile.mkdtemp(prefix=prefix))
        self._temp_dirs.append(temp_dir)
        logger.info(f"创建临时解压目录: {temp_dir}")
        return temp_dir
    
    def _extract_zip(
        self,
        archive_path: Path,
        progress_callback: Optional[Callable[[int, int, str], None]] = None
    ) -> Optional[Path]:
        """解压 .zip 文件（使用内置 zipfile）
        
        Args:
            archive_path: zip 文件路径
            progress_callback: 进度回调
            
        Returns:
            解压目录路径，失败返回 None
        """
        try:
            temp_dir = self._create_temp_dir()
            
            with zipfile.ZipFile(str(archive_path), 'r') as zf:
                # 检查是否有密码保护
                for info in zf.infolist():
                    if info.flag_bits & 0x1:
                        logger.error("压缩包有密码保护，暂不支持")
                        return None
                
                members = zf.infolist()
                total = len(members)
                
                if total == 0:
                    logger.warning("压缩包为空")
                    return temp_dir
                
                for i, member in enumerate(members, 1):
                    # 跳过 macOS 元数据文件
                    if member.filename.startswith('__MACOSX/') or member.filename.endswith('.DS_Store'):
                        if progress_callback:
                            progress_callback(i, total, f"跳过: {member.filename}")
                        continue
                    
                    zf.extract(member, str(temp_dir))
                    
                    if progress_callback:
                        name = Path(member.filename).name or member.filename
                        progress_callback(i, total, f"解压: {name}")
            
            logger.info(f"ZIP 解压完成: {archive_path.name} -> {temp_dir}")
            return temp_dir
            
        except zipfile.BadZipFile:
            logger.error(f"无效的 ZIP 文件: {archive_path}")
            return None
        except Exception as e:
            logger.error(f"ZIP 解压失败: {e}", exc_info=True)
            return None
    
    def _extract_7z(
        self,
        archive_path: Path,
        progress_callback: Optional[Callable[[int, int, str], None]] = None
    ) -> Optional[Path]:
        """解压 .7z 文件（使用 py7zr）
        
        Args:
            archive_path: 7z 文件路径
            progress_callback: 进度回调
            
        Returns:
            解压目录路径，失败返回 None
        """
        try:
            import py7zr
        except ImportError:
            logger.error("未安装 py7zr 库，无法解压 .7z 文件。请运行: pip install py7zr")
            return None
        
        try:
            temp_dir = self._create_temp_dir()
            
            with py7zr.SevenZipFile(str(archive_path), mode='r') as sz:
                # 检查密码保护
                if sz.needs_password():
                    logger.error("压缩包有密码保护，暂不支持")
                    return None
                
                all_files = sz.getnames()
                total = len(all_files)
                
                if progress_callback:
                    progress_callback(0, total, "开始解压 .7z...")
                
                # py7zr 一次性解压（没有逐文件回调）
                sz.extractall(path=str(temp_dir))
                
                if progress_callback:
                    progress_callback(total, total, "解压完成")
            
            logger.info(f"7z 解压完成: {archive_path.name} -> {temp_dir}")
            return temp_dir
            
        except Exception as e:
            logger.error(f"7z 解压失败: {e}", exc_info=True)
            return None
    
    def _extract_rar(
        self,
        archive_path: Path,
        progress_callback: Optional[Callable[[int, int, str], None]] = None
    ) -> Optional[Path]:
        """解压 .rar 文件（使用 rarfile）
        
        Args:
            archive_path: rar 文件路径
            progress_callback: 进度回调
            
        Returns:
            解压目录路径，失败返回 None
        """
        try:
            import rarfile
        except ImportError:
            logger.error("未安装 rarfile 库，无法解压 .rar 文件。请运行: pip install rarfile")
            return None
        
        try:
            temp_dir = self._create_temp_dir()
            
            with rarfile.RarFile(str(archive_path), 'r') as rf:
                members = rf.infolist()
                total = len(members)
                
                if total == 0:
                    logger.warning("压缩包为空")
                    return temp_dir
                
                for i, member in enumerate(members, 1):
                    rf.extract(member, str(temp_dir))
                    
                    if progress_callback:
                        name = Path(member.filename).name or member.filename
                        progress_callback(i, total, f"解压: {name}")
            
            logger.info(f"RAR 解压完成: {archive_path.name} -> {temp_dir}")
            return temp_dir
            
        except Exception as e:
            logger.error(f"RAR 解压失败: {e}", exc_info=True)
            return None
    
    def cleanup(self, temp_dir: Optional[Path] = None):
        """清理临时解压目录
        
        Args:
            temp_dir: 指定清理的目录，None 则清理所有
        """
        import shutil
        
        if temp_dir:
            dirs_to_clean = [temp_dir]
        else:
            dirs_to_clean = list(self._temp_dirs)
        
        for d in dirs_to_clean:
            try:
                if d.exists():
                    shutil.rmtree(str(d))
                    logger.info(f"已清理临时目录: {d}")
                if d in self._temp_dirs:
                    self._temp_dirs.remove(d)
            except Exception as e:
                logger.warning(f"清理临时目录失败: {d} - {e}")
    
    def cleanup_all(self):
        """清理所有临时解压目录"""
        self.cleanup(None)
