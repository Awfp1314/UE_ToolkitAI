"""
文件操作工具类

提供安全的文件操作功能，包括复制、移动、大小计算等。
所有操作都有完善的错误处理和日志记录。

性能优化：
- 大文件复制使用 robocopy（多线程，3-10倍提速）
- 自动降级到 Python 实现以保证兼容性
"""

import os
import shutil
from pathlib import Path
from typing import Optional, Callable
from logging import Logger


class FileOperations:
    """文件操作工具类
    
    提供安全的文件和目录操作，包括：
    - 复制目录/文件（自动使用高性能工具）
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
        
        # 初始化高性能文件操作（可选）
        self._fast_ops = None
        try:
            from core.utils.fast_file_ops import FastFileOperations
            self._fast_ops = FastFileOperations(logger)
            self._logger.info("✅ 高性能文件操作已启用")
        except Exception as e:
            self._logger.warning(f"⚠️ 高性能文件操作初始化失败，使用标准模式: {e}")
        
        if self._mock_mode:
            self._logger.info("FileOperations: Mock mode enabled")
    
    def _remove_if_exists(self, path: Path) -> bool:
        """如果路径存在则删除（处理只读权限）

        Args:
            path: 要删除的路径

        Returns:
            bool: 成功返回 True，失败返回 False
        """
        try:
            if not path.exists():
                return True
                
            self._logger.info(f"覆盖已存在的路径: {path}")
            
            if path.is_dir():
                # 使用 safe_remove_tree 处理目录（支持只读文件）
                return self.safe_remove_tree(path)
            else:
                # 使用 safe_remove_file 处理文件（支持只读文件）
                return self.safe_remove_file(path)
                
        except Exception as e:
            self._logger.error(f"Failed to remove path {path}: {e}")
            return False

    def safe_copytree(
        self,
        src: Path,
        dst: Path,
        progress_callback: Optional[Callable[[int, int, str], None]] = None,
        incremental: bool = False,
        use_symlink: bool = False
    ) -> bool:
        """安全地复制目录树（支持进度报告、增量复制和符号链接）

        性能优化：
        - 大目录（>1GB）自动使用 robocopy（多线程，3-10倍提速）
        - 小目录使用 Python 实现（避免进程开销）
        - 失败时自动降级

        Args:
            src: 源目录路径
            dst: 目标目录路径
            progress_callback: 进度回调函数 (copied_bytes, total_bytes, message)
            incremental: 是否使用增量复制（只复制新增或修改的文件）
            use_symlink: 是否使用符号链接（极快，但可能影响UE编辑）

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

        # 如果使用符号链接（已废除，强制禁用）
        if use_symlink:
            self._logger.warning(f"⚠️ 符号链接功能已废除，强制使用复制模式")
            use_symlink = False  # 强制改为复制模式
        
        # 直接使用高性能复制（robocopy 对小文件也很快，无需判断大小）
        if self._fast_ops:
            try:
                self._logger.info(f"🚀 尝试使用高性能复制")
                success = self._fast_ops.copy_tree_fast(src, dst, progress_callback)
                if success:
                    return True
                else:
                    self._logger.warning("⚠️ 高性能复制失败，降级到标准模式")
            except Exception as e:
                self._logger.warning(f"⚠️ 高性能复制异常，降级到标准模式: {e}")
        else:
            self._logger.warning("⚠️ 高性能文件操作未初始化，使用标准模式")

        # 如果使用增量复制且目标存在，使用增量模式
        if incremental and dst.exists():
            return self._incremental_copy(src, dst, progress_callback)
        
        # 否则使用完整复制（删除旧的，重新复制）
        if not self._remove_if_exists(dst):
            return False

        # 执行复制（带进度）
        try:
            self._logger.info(f"📋 开始复制目录树: {src} -> {dst}")
            
            # 如果有进度回调，使用基于文件大小的进度报告
            if progress_callback:
                # 1. 预先扫描所有文件，计算总大小（过滤广告和系统垃圾文件）
                _AD_EXTENSIONS = {'.txt', '.nfo', '.url', '.webloc', '.lnk', '.html', '.htm', '.mhtml', '.pdf'}
                _AD_NAMES = {'__macosx', '.ds_store', 'thumbs.db', 'desktop.ini'}
                def _is_junk(f: Path) -> bool:
                    """判断是否为广告/系统垃圾文件"""
                    # 跳过 __MACOSX 目录下所有文件
                    if any(p.lower() == '__macosx' for p in f.parts):
                        return True
                    name_lower = f.name.lower()
                    if name_lower in _AD_NAMES:
                        return True
                    if f.suffix.lower() in _AD_EXTENSIONS:
                        return True
                    return False

                all_files = []
                total_bytes = 0
                skipped_junk = 0
                for src_file in src.rglob('*'):
                    if src_file.is_file():
                        if _is_junk(src_file):
                            skipped_junk += 1
                            self._logger.debug(f"跳过广告/垃圾文件: {src_file.name}")
                            continue
                        try:
                            file_size = src_file.stat().st_size
                            all_files.append((src_file, file_size))
                            total_bytes += file_size
                        except Exception as e:
                            self._logger.warning(f"无法获取文件大小: {src_file}, {e}")
                if skipped_junk:
                    self._logger.info(f"🧹 已过滤 {skipped_junk} 个广告/垃圾文件")
                
                total_files = len(all_files)
                self._logger.info(f"📊 统计到 {total_files} 个文件，总大小 {self.format_size(total_bytes)}")
                
                if total_files == 0:
                    # 空目录，直接创建
                    dst.mkdir(parents=True, exist_ok=True)
                    progress_callback(1, 1, f"Created empty directory")
                    return True
                
                # 创建目标目录
                dst.mkdir(parents=True, exist_ok=True)
                
                # 2. 复制文件并报告进度（基于字节数）
                copied_bytes = 0
                copied_files = 0
                update_interval = max(1, total_files // 100)  # 动态调整更新频率，最多更新100次
                
                for src_file, file_size in all_files:
                    # 计算相对路径
                    rel_path = src_file.relative_to(src)
                    dst_file = dst / rel_path
                    
                    # 创建目标目录
                    dst_file.parent.mkdir(parents=True, exist_ok=True)
                    
                    # 复制文件
                    copied_files += 1
                    
                    # 小文件（< 10MB）：直接复制
                    if file_size < 10 * 1024 * 1024:
                        shutil.copy2(str(src_file), str(dst_file))
                        copied_bytes += file_size
                        
                        # 动态更新进度（避免过于频繁）
                        if copied_files % update_interval == 0 or copied_files == total_files:
                            if total_bytes == 0:
                                progress_callback(1, 1, f"正在复制: {src_file.name}")
                            else:
                                progress_callback(copied_bytes, total_bytes, f"正在复制: {src_file.name}")
                    else:
                        # 大文件（≥ 10MB）：分块复制并实时报告进度
                        chunk_size = 16 * 1024 * 1024  # 16MB per chunk（提高性能）
                        file_copied_bytes = 0
                        
                        with open(src_file, 'rb') as fsrc:
                            with open(dst_file, 'wb') as fdst:
                                while True:
                                    chunk = fsrc.read(chunk_size)
                                    if not chunk:
                                        break
                                    fdst.write(chunk)
                                    file_copied_bytes += len(chunk)
                                    copied_bytes += len(chunk)
                                    
                                    # 报告进度（按字节）
                                    if total_bytes == 0:
                                        progress_callback(1, 1, f"正在复制: {src_file.name}")
                                    else:
                                        progress_callback(copied_bytes, total_bytes, f"正在复制: {src_file.name}")
                        
                        # 复制元数据（修改时间等）
                        shutil.copystat(str(src_file), str(dst_file))
                    
                    # 移除只读属性（避免后续删除时权限错误）
                    try:
                        import stat
                        dst_file.chmod(stat.S_IWRITE | stat.S_IREAD)
                    except Exception:
                        pass  # 忽略权限修改失败
                    
                    # 每 50 个文件或最后一个文件记录日志
                    if copied_files % 50 == 0 or copied_files == total_files:
                        progress_pct = (copied_bytes * 100) // total_bytes if total_bytes > 0 else 100
                        self._logger.info(f"📊 复制进度: {copied_files}/{total_files} 文件, {self.format_size(copied_bytes)}/{self.format_size(total_bytes)} ({progress_pct}%)")
                
                self._logger.info(f"✅ 成功复制 {copied_files} 个文件，总大小 {self.format_size(copied_bytes)}")
            else:
                # 没有进度回调，使用标准方法
                shutil.copytree(src, dst)
                
                # 移除所有文件的只读属性
                try:
                    import stat
                    for dst_file in dst.rglob('*'):
                        if dst_file.is_file():
                            try:
                                dst_file.chmod(stat.S_IWRITE | stat.S_IREAD)
                            except Exception:
                                pass  # 忽略单个文件的权限修改失败
                except Exception as e:
                    self._logger.debug(f"Failed to change permissions: {e}")
            
            self._logger.info(f"Successfully copied tree: {src} -> {dst}")
            return True
        except (PermissionError, OSError) as e:
            self._logger.error(f"Failed to copy tree: {e}")
            return False
        except Exception as e:
            self._logger.error(f"Unexpected error: {e}")
            return False
    
    def _create_symlink_tree(
        self,
        src: Path,
        dst: Path,
        progress_callback: Optional[Callable[[int, int, str], None]] = None
    ) -> bool:
        """创建符号链接树（极快，但可能影响UE编辑）
        
        Args:
            src: 源目录路径
            dst: 目标目录路径
            progress_callback: 进度回调函数
            
        Returns:
            bool: 成功返回 True，失败返回 False
        """
        try:
            self._logger.info(f"Creating symlink tree: {src} -> {dst}")
            
            # 删除旧的目标（如果存在）
            if not self._remove_if_exists(dst):
                return False
            
            # 创建目标根目录
            dst.mkdir(parents=True, exist_ok=True)
            
            # 收集所有文件和目录
            all_items = list(src.rglob('*'))
            total_items = len(all_items)
            
            if total_items == 0:
                if progress_callback:
                    progress_callback(1, 1, "Empty directory")
                return True
            
            self._logger.info(f"Creating {total_items} symlinks...")
            
            created_count = 0
            for item in all_items:
                try:
                    rel_path = item.relative_to(src)
                    dst_item = dst / rel_path
                    
                    if item.is_dir():
                        # 创建目录
                        dst_item.mkdir(parents=True, exist_ok=True)
                    else:
                        # 创建符号链接
                        dst_item.parent.mkdir(parents=True, exist_ok=True)
                        
                        # Windows 上创建符号链接
                        import os
                        os.symlink(str(item), str(dst_item))
                        
                    created_count += 1
                    if progress_callback and created_count % 10 == 0:
                        progress_callback(created_count, total_items, f"Linking: {item.name}")
                        
                except Exception as e:
                    self._logger.error(f"Failed to create symlink for {item}: {e}")
                    # 如果符号链接失败，尝试复制
                    if item.is_file():
                        try:
                            shutil.copy2(str(item), str(dst_item))
                            self._logger.info(f"Fallback to copy: {item.name}")
                        except Exception as copy_error:
                            self._logger.error(f"Fallback copy also failed: {copy_error}")
            
            if progress_callback:
                progress_callback(total_items, total_items, "Symlink tree created")
            
            self._logger.info(f"Successfully created {created_count} symlinks")
            return True
            
        except Exception as e:
            self._logger.error(f"Failed to create symlink tree: {e}")
            return False
    
    def _incremental_copy(
        self,
        src: Path,
        dst: Path,
        progress_callback: Optional[Callable[[int, int, str], None]] = None
    ) -> bool:
        """增量复制：只复制新增或修改的文件
        
        Args:
            src: 源目录路径
            dst: 目标目录路径（必须已存在）
            progress_callback: 进度回调函数
            
        Returns:
            bool: 成功返回 True，失败返回 False
        """
        try:
            self._logger.info(f"Incremental copy: {src} -> {dst}")
            
            # 收集需要复制的文件
            files_to_copy = []
            for src_file in src.rglob('*'):
                if src_file.is_file():
                    rel_path = src_file.relative_to(src)
                    dst_file = dst / rel_path
                    
                    # 检查是否需要复制
                    if self._should_copy_file(src_file, dst_file):
                        files_to_copy.append((src_file, dst_file, rel_path))
            
            total_files = len(files_to_copy)
            
            if total_files == 0:
                self._logger.info("No files need to be copied (all up to date)")
                if progress_callback:
                    progress_callback(1, 1, "All files up to date")
                return True
            
            self._logger.info(f"Need to copy {total_files} files (out of {sum(1 for _ in src.rglob('*') if _.is_file())} total)")
            
            # 复制需要更新的文件
            copied_files = 0
            for src_file, dst_file, rel_path in files_to_copy:
                try:
                    # 创建目标目录
                    dst_file.parent.mkdir(parents=True, exist_ok=True)
                    
                    # 复制文件
                    shutil.copy2(str(src_file), str(dst_file))
                    
                    # 移除只读属性
                    try:
                        import stat
                        dst_file.chmod(stat.S_IWRITE | stat.S_IREAD)
                    except Exception:
                        pass
                    
                    copied_files += 1
                    if progress_callback:
                        progress_callback(copied_files, total_files, f"Updating: {src_file.name}")
                        
                except Exception as e:
                    self._logger.error(f"Failed to copy {src_file}: {e}")
            
            self._logger.info(f"Incremental copy completed: {copied_files}/{total_files} files copied")
            return True
            
        except Exception as e:
            self._logger.error(f"Incremental copy failed: {e}")
            return False
    
    def _should_copy_file(self, src_file: Path, dst_file: Path) -> bool:
        """判断文件是否需要复制
        
        Args:
            src_file: 源文件
            dst_file: 目标文件
            
        Returns:
            需要复制返回 True，否则返回 False
        """
        # 目标文件不存在，需要复制
        if not dst_file.exists():
            return True
        
        try:
            # 比较文件大小
            src_size = src_file.stat().st_size
            dst_size = dst_file.stat().st_size
            if src_size != dst_size:
                return True
            
            # 比较修改时间
            src_mtime = src_file.stat().st_mtime
            dst_mtime = dst_file.stat().st_mtime
            if src_mtime > dst_mtime:
                return True
            
            # 文件相同，不需要复制
            return False
            
        except Exception as e:
            # 出错时保守处理，复制文件
            self._logger.debug(f"Error comparing files, will copy: {e}")
            return True
    
    def safe_move_tree(
        self,
        src: Path,
        dst: Path,
        progress_callback: Optional[Callable[[int, int, str], None]] = None
    ) -> bool:
        """安全地移动目录树（支持跨驱动器和进度报告）

        如果目标已存在，返回 False（不覆盖）。
        跨驱动器时会先复制再删除源文件。

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
            
            # 检查是否跨驱动器
            src_drive = src.drive if hasattr(src, 'drive') else src.parts[0]
            dst_drive = dst.drive if hasattr(dst, 'drive') else dst.parts[0]
            is_cross_drive = src_drive != dst_drive
            
            if is_cross_drive:
                self._logger.info(f"Cross-drive move detected: {src_drive} -> {dst_drive}")
                
                # 跨驱动器：使用带进度的复制
                copy_success = self.safe_copytree(src, dst, progress_callback=progress_callback)
                if not copy_success:
                    self._logger.error("Copy failed during cross-drive move")
                    return False
                
                # 复制成功后删除源文件
                self._logger.info(f"Copy completed, now removing source: {src}")
                try:
                    shutil.rmtree(str(src))
                    self._logger.info(f"Source removed successfully")
                except Exception as e:
                    self._logger.error(f"Failed to remove source after copy: {e}")
                    # 复制成功但删除失败，仍然返回 True（文件已在目标位置）
                    return True
            else:
                # 同驱动器：直接移动（快速）
                shutil.move(str(src), str(dst))
                if progress_callback:
                    progress_callback(1, 1, f"已移动: {src.name}")
            
            self._logger.info(f"Successfully moved tree: {src} -> {dst}")
            return True
            
        except (PermissionError, OSError) as e:
            self._logger.error(f"Failed to move tree: {e}")
            # 如果复制成功但删除失败，尝试清理目标
            if dst.exists() and src.exists():
                self._logger.warning(f"Copy succeeded but delete failed, cleaning up target")
                try:
                    shutil.rmtree(str(dst))
                except Exception as cleanup_error:
                    self._logger.error(f"Failed to cleanup target: {cleanup_error}")
            return False
        except Exception as e:
            self._logger.error(f"Unexpected error: {e}")
            return False
    
    def safe_copy_file(
        self,
        src: Path,
        dst: Path,
        progress_callback: Optional[Callable[[int, int, str], None]] = None
    ) -> bool:
        """安全地复制文件（支持进度报告）

        如果目标已存在，先删除再复制（覆盖模式）。

        Args:
            src: 源文件路径
            dst: 目标文件路径
            progress_callback: 进度回调函数 (current, total, message)

        Returns:
            bool: 成功返回 True，失败返回 False
        """
        # Mock 模式：模拟成功
        if self._mock_mode:
            self._logger.info(f"[Mock] Copying file: {src} -> {dst}")
            if progress_callback:
                progress_callback(1, 1, "Mock copy completed")
            return True

        # 检查源路径
        if not src.exists():
            self._logger.error(f"Source file does not exist: {src}")
            return False

        # 删除目标文件（如果存在）
        if not self._remove_if_exists(dst):
            return False

        # 执行复制
        try:
            self._logger.info(f"Copying file: {src} -> {dst}")
            
            # 获取文件大小
            file_size = src.stat().st_size
            
            # 如果文件很小（< 1MB）或没有进度回调，直接复制
            if file_size < 1024 * 1024 or not progress_callback:
                if progress_callback:
                    progress_callback(0, 1, f"正在复制: {src.name}")
                
                shutil.copy2(str(src), str(dst))
                
                if progress_callback:
                    progress_callback(1, 1, f"已复制: {src.name}")
            else:
                # 大文件：分块复制并报告进度
                chunk_size = 1024 * 1024  # 1MB per chunk
                copied = 0
                
                with open(src, 'rb') as fsrc:
                    with open(dst, 'wb') as fdst:
                        while True:
                            chunk = fsrc.read(chunk_size)
                            if not chunk:
                                break
                            fdst.write(chunk)
                            copied += len(chunk)
                            
                            # 报告进度（按字节）
                            if progress_callback:
                                progress_callback(copied, file_size, f"正在复制: {src.name}")
                
                # 复制元数据（修改时间等）
                shutil.copystat(str(src), str(dst))
                
                if progress_callback:
                    progress_callback(file_size, file_size, f"已复制: {src.name}")
            
            self._logger.info(f"Successfully copied file: {src} -> {dst}")
            return True
            
        except Exception as e:
            self._logger.error(f"Failed to copy file: {e}")
            # 清理可能的部分复制
            if dst.exists():
                try:
                    dst.unlink()
                except Exception as cleanup_error:
                    self._logger.error(f"Failed to cleanup target: {cleanup_error}")
            return False
    
    def safe_move_file(
        self,
        src: Path,
        dst: Path,
        progress_callback: Optional[Callable[[int, int, str], None]] = None
    ) -> bool:
        """安全地移动文件（支持跨驱动器和进度报告）

        如果目标已存在，先删除再移动（覆盖模式）。
        跨驱动器时会先复制再删除源文件。

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
            
            if progress_callback:
                progress_callback(0, 1, f"正在移动: {src.name}")
            
            # 检查是否跨驱动器
            src_drive = src.drive if hasattr(src, 'drive') else src.parts[0]
            dst_drive = dst.drive if hasattr(dst, 'drive') else dst.parts[0]
            is_cross_drive = src_drive != dst_drive
            
            if is_cross_drive:
                self._logger.info(f"Cross-drive move detected: {src_drive} -> {dst_drive}")
                # 跨驱动器：先复制，再删除
                shutil.copy2(str(src), str(dst))
                self._logger.info(f"Copy completed, now removing source: {src}")
                src.unlink()
                self._logger.info(f"Source removed successfully")
            else:
                # 同驱动器：直接移动
                shutil.move(str(src), str(dst))
            
            if progress_callback:
                progress_callback(1, 1, f"已移动: {src.name}")
            self._logger.info(f"Successfully moved file: {src} -> {dst}")
            return True
            
        except (PermissionError, OSError) as e:
            self._logger.error(f"Failed to move file: {e}")
            # 如果复制成功但删除失败，尝试清理目标
            if dst.exists() and src.exists():
                self._logger.warning(f"Copy succeeded but delete failed, cleaning up target")
                try:
                    dst.unlink()
                except Exception as cleanup_error:
                    self._logger.error(f"Failed to cleanup target: {cleanup_error}")
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


    def safe_remove_file(self, file_path: Path) -> bool:
        """安全地删除文件（处理只读权限）
        
        Args:
            file_path: 文件路径
            
        Returns:
            bool: 成功返回 True，失败返回 False
        """
        if self._mock_mode:
            self._logger.info(f"[Mock] Removing file: {file_path}")
            return True
        
        try:
            if not file_path.exists():
                self._logger.warning(f"File does not exist: {file_path}")
                return True
            
            if not file_path.is_file():
                self._logger.error(f"Path is not a file: {file_path}")
                return False
            
            # 尝试直接删除
            try:
                file_path.unlink()
                self._logger.info(f"Removed file: {file_path}")
                return True
            except PermissionError:
                # 如果权限错误，尝试修改权限后删除
                self._logger.warning(f"Permission denied, trying to change attributes: {file_path}")
                import stat
                file_path.chmod(stat.S_IWRITE)
                file_path.unlink()
                self._logger.info(f"Removed file after changing attributes: {file_path}")
                return True
                
        except Exception as e:
            self._logger.error(f"Failed to remove file {file_path}: {e}", exc_info=True)
            return False
    
    def safe_remove_tree(self, dir_path: Path) -> bool:
        """安全地删除目录树（处理只读权限）
        
        Args:
            dir_path: 目录路径
            
        Returns:
            bool: 成功返回 True，失败返回 False
        """
        if self._mock_mode:
            self._logger.info(f"[Mock] Removing tree: {dir_path}")
            return True
        
        try:
            if not dir_path.exists():
                self._logger.warning(f"Directory does not exist: {dir_path}")
                return True
            
            if not dir_path.is_dir():
                self._logger.error(f"Path is not a directory: {dir_path}")
                return False
            
            # 定义错误处理函数
            def handle_remove_readonly(func, path, exc):
                """处理只读文件的删除"""
                import stat
                import os
                
                # 如果是权限错误，尝试修改权限后重试
                if isinstance(exc[1], PermissionError):
                    try:
                        os.chmod(path, stat.S_IWRITE)
                        func(path)
                    except Exception as e:
                        self._logger.error(f"Failed to remove readonly file {path}: {e}")
                        raise
                else:
                    raise
            
            # 使用 shutil.rmtree 的 onerror 参数处理权限问题
            shutil.rmtree(dir_path, onerror=handle_remove_readonly)
            self._logger.info(f"Removed directory tree: {dir_path}")
            return True
            
        except Exception as e:
            self._logger.error(f"Failed to remove directory tree {dir_path}: {e}", exc_info=True)
            return False
