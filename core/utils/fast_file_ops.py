# -*- coding: utf-8 -*-
"""
高性能文件操作工具

使用外部工具（7z、robocopy）加速文件操作：
- 7z.exe：多线程解压，速度提升 3-5 倍
- robocopy：多线程复制，速度提升 3-10 倍

自动降级到 Python 实现以保证兼容性。
"""

import os
import re
import subprocess
import shutil
from pathlib import Path
from typing import Optional, Callable
from logging import Logger


class FastFileOperations:
    """高性能文件操作工具
    
    优先使用外部工具（7z、robocopy），失败时降级到 Python 实现。
    """
    
    # 类级别的 7z 路径缓存（避免重复查找）
    _7z_path_cache = None
    _7z_checked = False
    
    def __init__(self, logger: Logger):
        """初始化
        
        Args:
            logger: 日志记录器
        """
        self._logger = logger
        
        # 使用类级别缓存，避免重复查找
        if not FastFileOperations._7z_checked:
            FastFileOperations._7z_path_cache = self._find_7z()
            FastFileOperations._7z_checked = True
            
            if FastFileOperations._7z_path_cache:
                self._logger.info(f"✅ 找到 7z: {FastFileOperations._7z_path_cache}")
            else:
                self._logger.warning("⚠️ 未找到 7z，将使用 Python zipfile（较慢）")
                self._logger.info("💡 提示：安装 7-Zip 可提升解压速度 3-5 倍: https://www.7-zip.org/")
        
        self._7z_path = FastFileOperations._7z_path_cache
        self._use_fast_mode = True  # 是否启用快速模式
    
    def _find_7z(self) -> Optional[Path]:
        """查找 7z.exe
        
        查找顺序：
        1. resources/tools/7z.exe（打包版本）
        2. C:/Program Files/7-Zip/7z.exe（系统安装）
        3. PATH 环境变量
        
        Returns:
            7z.exe 路径，未找到返回 None
        """
        # 1. 打包版本
        bundled_7z = Path(__file__).parent.parent.parent / "resources" / "tools" / "7z.exe"
        if bundled_7z.exists():
            return bundled_7z
        
        # 2. 系统安装
        system_7z = Path("C:/Program Files/7-Zip/7z.exe")
        if system_7z.exists():
            return system_7z
        
        # 3. PATH 环境变量
        try:
            result = subprocess.run(
                ["where", "7z.exe"],
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode == 0:
                path = result.stdout.strip().split('\n')[0]
                return Path(path)
        except Exception:
            pass
        
        return None
    
    def extract_archive_fast(
        self,
        archive_path: Path,
        extract_to: Path,
        password: str = "",
        progress_callback: Optional[Callable[[int, int, str], None]] = None
    ) -> bool:
        """高性能解压（使用 7z）
        
        Args:
            archive_path: 压缩包路径
            extract_to: 解压目标目录
            password: 密码（可选）
            progress_callback: 进度回调 (current, total, message)
        
        Returns:
            成功返回 True，失败返回 False
        """
        if not self._use_fast_mode or not self._7z_path:
            # 降级到 Python 实现
            return self._extract_with_python(archive_path, extract_to, password, progress_callback)
        
        try:
            self._logger.info(f"🚀 使用 7z 高速解压: {archive_path.name}")
            
            # 创建目标目录
            extract_to.mkdir(parents=True, exist_ok=True)
            
            # 构建 7z 命令
            cmd = [
                str(self._7z_path),
                "x",  # 解压（保持目录结构）
                str(archive_path),
                f"-o{extract_to}",  # 输出目录
                "-mmt=4",  # 4 线程（可根据 CPU 调整）
                "-y",  # 自动确认
            ]
            
            if password:
                cmd.append(f"-p{password}")
            
            # 执行解压
            if progress_callback:
                progress_callback(0, 100, f"正在解压: {archive_path.name}")
            
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding='utf-8',
                errors='ignore'
            )
            
            # 解析进度
            last_progress = 0
            for line in process.stdout:
                # 7z 输出格式：Extracting  file.txt  50%
                match = re.search(r'(\d+)%', line)
                if match:
                    progress = int(match.group(1))
                    if progress > last_progress:
                        last_progress = progress
                        if progress_callback:
                            progress_callback(progress, 100, f"解压中: {progress}%")
            
            process.wait()
            
            if process.returncode == 0:
                if progress_callback:
                    progress_callback(100, 100, "解压完成")
                self._logger.info(f"✅ 7z 解压成功: {archive_path.name}")
                return True
            else:
                error = process.stderr.read() if process.stderr else "Unknown error"
                self._logger.error(f"❌ 7z 解压失败: {error}")
                
                # 降级到 Python 实现
                self._logger.info("⚠️ 降级到 Python zipfile")
                return self._extract_with_python(archive_path, extract_to, password, progress_callback)
        
        except Exception as e:
            self._logger.error(f"❌ 7z 解压异常: {e}", exc_info=True)
            # 降级到 Python 实现
            return self._extract_with_python(archive_path, extract_to, password, progress_callback)
    
    def _extract_with_python(
        self,
        archive_path: Path,
        extract_to: Path,
        password: str = "",
        progress_callback: Optional[Callable[[int, int, str], None]] = None
    ) -> bool:
        """使用 Python zipfile 解压（降级方案）
        
        Args:
            archive_path: 压缩包路径
            extract_to: 解压目标目录
            password: 密码（可选）
            progress_callback: 进度回调
        
        Returns:
            成功返回 True，失败返回 False
        """
        import zipfile
        
        try:
            self._logger.info(f"📦 使用 Python zipfile 解压: {archive_path.name}")
            
            extract_to.mkdir(parents=True, exist_ok=True)
            
            with zipfile.ZipFile(archive_path, 'r') as zip_ref:
                members = zip_ref.namelist()
                total_files = len(members)
                
                if progress_callback:
                    progress_callback(0, total_files, f"准备解压 {total_files} 个文件")
                
                pwd = password.encode('utf-8') if password else None
                
                for i, member in enumerate(members):
                    try:
                        zip_ref.extract(member, extract_to, pwd=pwd)
                        
                        if progress_callback and (i % 10 == 0 or i == total_files - 1):
                            progress_callback(i + 1, total_files, f"解压中: {member}")
                    except Exception as e:
                        self._logger.warning(f"跳过文件 {member}: {e}")
                
                if progress_callback:
                    progress_callback(total_files, total_files, "解压完成")
                
                self._logger.info(f"✅ Python 解压成功: {archive_path.name}")
                return True
        
        except Exception as e:
            self._logger.error(f"❌ Python 解压失败: {e}", exc_info=True)
            return False
    
    def copy_tree_fast(
        self,
        src: Path,
        dst: Path,
        progress_callback: Optional[Callable[[int, int, str], None]] = None
    ) -> bool:
        """高性能复制目录（使用 robocopy）
        
        Args:
            src: 源目录
            dst: 目标目录
            progress_callback: 进度回调 (current, total, message)
        
        Returns:
            成功返回 True，失败返回 False
        """
        if not self._use_fast_mode:
            # 降级到 Python 实现
            return self._copy_with_python(src, dst, progress_callback)
        
        try:
            self._logger.info(f"🚀 使用 robocopy 高速复制: {src} -> {dst}")
            
            # 创建目标目录
            dst.mkdir(parents=True, exist_ok=True)
            
            # 构建 robocopy 命令
            cmd = [
                "robocopy",
                str(src),
                str(dst),
                "/E",  # 复制所有子目录（包括空目录）
                "/MT:8",  # 8 线程
                "/NFL",  # 不记录文件列表
                "/NDL",  # 不记录目录列表
                "/NJH",  # 不显示作业头
                "/NJS",  # 不显示作业摘要
                "/NP",  # 不显示进度百分比
                "/BYTES",  # 以字节显示大小
            ]
            
            # 执行复制
            if progress_callback:
                progress_callback(0, 100, f"正在复制: {src.name}")
            
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding='gbk',  # Windows 中文环境
                errors='ignore'
            )
            
            # 解析进度（robocopy 输出格式复杂，简化处理）
            copied_files = 0
            for line in process.stdout:
                # 检测文件复制行（包含文件大小）
                if re.search(r'\d+\s+\S+\.(uasset|umap|png|jpg|fbx|obj)', line, re.IGNORECASE):
                    copied_files += 1
                    if progress_callback and copied_files % 50 == 0:
                        progress_callback(copied_files, copied_files + 100, f"已复制 {copied_files} 个文件")
            
            process.wait()
            
            # robocopy 返回码：0-7 表示成功，8+ 表示失败
            if process.returncode < 8:
                if progress_callback:
                    progress_callback(100, 100, "复制完成")
                self._logger.info(f"✅ robocopy 复制成功: {src.name}")
                return True
            else:
                error = process.stderr.read() if process.stderr else "Unknown error"
                self._logger.error(f"❌ robocopy 复制失败 (code {process.returncode}): {error}")
                
                # 降级到 Python 实现
                self._logger.info("⚠️ 降级到 shutil.copytree")
                return self._copy_with_python(src, dst, progress_callback)
        
        except Exception as e:
            self._logger.error(f"❌ robocopy 复制异常: {e}", exc_info=True)
            # 降级到 Python 实现
            return self._copy_with_python(src, dst, progress_callback)
    
    def _copy_with_python(
        self,
        src: Path,
        dst: Path,
        progress_callback: Optional[Callable[[int, int, str], None]] = None
    ) -> bool:
        """使用 Python shutil 复制（降级方案）
        
        Args:
            src: 源目录
            dst: 目标目录
            progress_callback: 进度回调
        
        Returns:
            成功返回 True，失败返回 False
        """
        try:
            self._logger.info(f"📋 使用 shutil 复制: {src} -> {dst}")
            
            # 删除旧目标（如果存在）
            if dst.exists():
                shutil.rmtree(dst)
            
            # 收集所有文件
            all_files = list(src.rglob('*'))
            total_files = len([f for f in all_files if f.is_file()])
            
            if progress_callback:
                progress_callback(0, total_files, f"准备复制 {total_files} 个文件")
            
            # 创建目标目录
            dst.mkdir(parents=True, exist_ok=True)
            
            # 复制文件
            copied_files = 0
            for item in all_files:
                rel_path = item.relative_to(src)
                dst_item = dst / rel_path
                
                if item.is_dir():
                    dst_item.mkdir(parents=True, exist_ok=True)
                else:
                    dst_item.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(str(item), str(dst_item))
                    copied_files += 1
                    
                    if progress_callback and (copied_files % 10 == 0 or copied_files == total_files):
                        progress_callback(copied_files, total_files, f"复制中: {item.name}")
            
            if progress_callback:
                progress_callback(total_files, total_files, "复制完成")
            
            self._logger.info(f"✅ shutil 复制成功: {src.name}")
            return True
        
        except Exception as e:
            self._logger.error(f"❌ shutil 复制失败: {e}", exc_info=True)
            return False
    
    def set_fast_mode(self, enabled: bool):
        """设置是否启用快速模式
        
        Args:
            enabled: True 启用，False 禁用（使用 Python 实现）
        """
        self._use_fast_mode = enabled
        self._logger.info(f"快速模式: {'启用' if enabled else '禁用'}")
