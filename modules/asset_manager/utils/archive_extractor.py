# -*- coding: utf-8 -*-

"""
压缩包解压工具

支持 .zip、.7z、.rar 三种主流压缩格式的解压操作，
提供进度回调以便在 UI 上展示解压进度。
"""

import os
import tempfile
import zipfile
import subprocess
import shutil
from pathlib import Path
from typing import Optional, Callable

from core.logger import get_logger

logger = get_logger(__name__)

# 支持的压缩包扩展名
ARCHIVE_EXTENSIONS = {'.zip', '.rar', '.7z'}

# 广告文件过滤规则 - 直接按扩展名过滤
AD_FILE_EXTENSIONS = {
    '.url',      # 网页链接
    '.html',     # 网页文件
    '.htm',      # 网页文件
    '.lnk',      # Windows 快捷方式
    '.txt',      # 文本文件（通常是广告说明）
}

# UE 资产文件扩展名白名单（这些文件永远不会被过滤）
UE_ASSET_EXTENSIONS = {
    '.uasset', '.umap', '.uproject', '.uplugin',
    '.fbx', '.obj', '.png', '.jpg', '.jpeg', '.tga', '.bmp', '.dds',
    '.wav', '.mp3', '.ogg',
    '.cpp', '.h', '.cs', '.ini', '.json',
}


def is_ad_file(file_path: Path) -> bool:
    """判断文件是否为广告文件
    
    Args:
        file_path: 文件路径
        
    Returns:
        bool: 是广告文件返回 True
    
    规则：
    1. 白名单：UE 资产文件扩展名永远不过滤
    2. 扩展名匹配：.url、.html、.htm、.lnk、.txt
    """
    # 白名单：UE 资产文件永远不过滤
    if file_path.suffix.lower() in UE_ASSET_EXTENSIONS:
        return False
    
    # 检查扩展名
    if file_path.suffix.lower() in AD_FILE_EXTENSIONS:
        return True
    
    return False


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
    
    支持 .zip（内置）、.7z（py7zr + 7z.exe 降级）、.rar（rarfile）
    解压到临时目录，返回解压后的根目录路径。
    支持密码保护的压缩包。
    """
    
    # 类级别的密码缓存（进程生命周期内有效）
    _password_cache = ""
    
    # 7z.exe 路径缓存
    _7z_exe_path = None
    _7z_exe_checked = False
    
    def __init__(self):
        self._temp_dirs = []  # 记录创建的临时目录，便于清理
    
    @staticmethod
    def _find_7z_exe() -> Optional[Path]:
        """查找系统中的 7z.exe
        
        Returns:
            7z.exe 路径，未找到返回 None
        """
        # 如果已经检查过，直接返回缓存结果
        if ArchiveExtractor._7z_exe_checked:
            return ArchiveExtractor._7z_exe_path
        
        ArchiveExtractor._7z_exe_checked = True
        
        # 常见安装位置
        possible_paths = [
            Path(r"C:\Program Files\7-Zip\7z.exe"),
            Path(r"C:\Program Files (x86)\7-Zip\7z.exe"),
        ]
        
        # 检查常见位置
        for path in possible_paths:
            if path.exists():
                logger.info(f"找到 7z.exe: {path}")
                ArchiveExtractor._7z_exe_path = path
                return path
        
        # 尝试从 PATH 环境变量查找
        try:
            result = subprocess.run(
                ["where", "7z.exe"],
                capture_output=True,
                text=True,
                timeout=5,
                creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0
            )
            if result.returncode == 0:
                path = Path(result.stdout.strip().split('\n')[0])
                if path.exists():
                    logger.info(f"从 PATH 找到 7z.exe: {path}")
                    ArchiveExtractor._7z_exe_path = path
                    return path
        except Exception as e:
            logger.debug(f"从 PATH 查找 7z.exe 失败: {e}")
        
        # 递归搜索 Program Files 目录（最后的手段，可能较慢）
        try:
            logger.info("在 Program Files 中递归搜索 7z.exe...")
            for base_dir in [r"C:\Program Files", r"C:\Program Files (x86)"]:
                base_path = Path(base_dir)
                if not base_path.exists():
                    continue
                
                # 使用 PowerShell 快速搜索（比 Python 递归快）
                result = subprocess.run(
                    ["powershell", "-Command", 
                     f"Get-ChildItem -Path '{base_dir}' -Filter '7z.exe' -Recurse -ErrorAction SilentlyContinue | Select-Object -First 1 -ExpandProperty FullName"],
                    capture_output=True,
                    text=True,
                    timeout=30,
                    creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0
                )
                if result.returncode == 0 and result.stdout.strip():
                    path = Path(result.stdout.strip())
                    if path.exists():
                        logger.info(f"递归搜索找到 7z.exe: {path}")
                        ArchiveExtractor._7z_exe_path = path
                        return path
        except Exception as e:
            logger.debug(f"递归搜索 7z.exe 失败: {e}")
        
        logger.warning("未找到 7z.exe，无法使用命令行降级方案")
        return None
    
    @classmethod
    def set_cached_password(cls, password: str):
        """设置缓存的密码
        
        Args:
            password: 密码字符串
        """
        cls._password_cache = password
        logger.info("已缓存解压密码")
    
    @classmethod
    def get_cached_password(cls) -> str:
        """获取缓存的密码
        
        Returns:
            缓存的密码，如果没有则返回空字符串
        """
        return cls._password_cache
    
    @classmethod
    def clear_cached_password(cls):
        """清除缓存的密码"""
        cls._password_cache = ""
        logger.info("已清除缓存的解压密码")
    
    @staticmethod
    def check_password_required(archive_path: Path) -> bool:
        """检查压缩包是否需要密码
        
        Args:
            archive_path: 压缩包路径
            
        Returns:
            True: 需要密码
            False: 不需要密码或无法检测
        """
        if not archive_path.exists():
            return False
        
        suffix = archive_path.suffix.lower()
        
        try:
            if suffix == '.zip':
                import zipfile
                with zipfile.ZipFile(str(archive_path), 'r') as zf:
                    for info in zf.infolist():
                        if info.flag_bits & 0x1:
                            return True
                return False
            
            elif suffix == '.7z':
                try:
                    import py7zr
                    with py7zr.SevenZipFile(str(archive_path), mode='r') as sz:
                        return sz.needs_password()
                except py7zr.exceptions.UnsupportedCompressionMethodError:
                    # 压缩方法不支持，无法检测密码
                    logger.warning("7z 文件使用了不支持的压缩方法")
                    return False
                except ImportError:
                    return False
            
            elif suffix == '.rar':
                try:
                    import rarfile
                    with rarfile.RarFile(str(archive_path), 'r') as rf:
                        # RAR 没有直接的 needs_password 方法，尝试读取文件列表
                        try:
                            rf.infolist()
                            return False
                        except rarfile.PasswordRequired:
                            return True
                except ImportError:
                    return False
            
            return False
            
        except Exception as e:
            logger.warning(f"检测密码失败: {e}")
            return False
    
    def extract(
        self,
        archive_path: Path,
        progress_callback: Optional[Callable[[int, int, str], None]] = None,
        password: Optional[str] = None
    ) -> Optional[Path]:
        """解压压缩包到临时目录
        
        Args:
            archive_path: 压缩包文件路径
            progress_callback: 进度回调 (current, total, message)
            password: 解压密码（可选）
            
        Returns:
            解压后的临时目录路径，失败返回 None
            
        Raises:
            RuntimeError: 当需要密码但未提供时抛出，错误信息为 "PASSWORD_REQUIRED"
            RuntimeError: 当密码错误时抛出，错误信息为 "PASSWORD_INCORRECT"
        """
        if not archive_path.exists():
            logger.error(f"压缩包不存在: {archive_path}")
            return None
        
        suffix = archive_path.suffix.lower()
        
        if suffix == '.zip':
            return self._extract_zip(archive_path, progress_callback, password)
        elif suffix == '.7z':
            return self._extract_7z(archive_path, progress_callback, password)
        elif suffix == '.rar':
            return self._extract_rar(archive_path, progress_callback, password)
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
        progress_callback: Optional[Callable[[int, int, str], None]] = None,
        password: Optional[str] = None
    ) -> Optional[Path]:
        """解压 .zip 文件
        
        性能优化：
        - 优先使用 7z.exe（多线程，3-5倍提速）
        - 降级到 Python zipfile（兼容性）
        
        Args:
            archive_path: zip 文件路径
            progress_callback: 进度回调
            password: 解压密码
            
        Returns:
            解压目录路径，失败返回 None
            
        Raises:
            RuntimeError: 需要密码或密码错误时抛出
        """
        # 尝试使用高性能解压（7z.exe）
        try:
            from core.utils.fast_file_ops import FastFileOperations
            from core.logger import get_logger
            
            fast_ops = FastFileOperations(get_logger(__name__))
            temp_dir = self._create_temp_dir()
            
            # 使用 7z 高速解压
            success = fast_ops.extract_archive_fast(
                archive_path, temp_dir, password or "", progress_callback
            )
            
            if success:
                # 解压成功后，清理广告文件
                self._cleanup_ad_files(temp_dir)
                logger.info(f"✅ ZIP 高速解压完成: {archive_path.name}")
                return temp_dir
            else:
                logger.warning("⚠️ 高速解压失败，降级到 Python zipfile")
        except Exception as e:
            logger.warning(f"⚠️ 高速解压异常，降级到 Python zipfile: {e}")
        
        # 降级到 Python zipfile
        try:
            temp_dir = self._create_temp_dir()
            pwd_bytes = password.encode('utf-8') if password else None
            
            with zipfile.ZipFile(str(archive_path), 'r') as zf:
                # 检查是否有密码保护
                has_password = False
                for info in zf.infolist():
                    if info.flag_bits & 0x1:
                        has_password = True
                        break
                
                if has_password and not password:
                    logger.warning("压缩包需要密码")
                    raise RuntimeError("PASSWORD_REQUIRED")
                
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
                    
                    # 跳过广告文件
                    member_path = Path(member.filename)
                    if is_ad_file(member_path):
                        logger.info(f"跳过广告文件: {member.filename}")
                        if progress_callback:
                            progress_callback(i, total, f"跳过广告: {member_path.name}")
                        continue
                    
                    try:
                        # Windows 路径修复：清理路径中每个部分的尾随空格
                        # 例如：'Tactical Flashlight /file.fbx' -> 'Tactical Flashlight/file.fbx'
                        original_filename = member.filename
                        cleaned_parts = [part.rstrip() for part in original_filename.split('/')]
                        cleaned_filename = '/'.join(cleaned_parts)
                        
                        if cleaned_filename != original_filename:
                            logger.info(f"修复路径空格: '{original_filename}' -> '{cleaned_filename}'")
                            # 创建新的 ZipInfo 对象，使用清理后的文件名
                            new_member = zipfile.ZipInfo(cleaned_filename)
                            new_member.compress_type = member.compress_type
                            new_member.compress_size = member.compress_size
                            new_member.file_size = member.file_size
                            new_member.CRC = member.CRC
                            new_member.external_attr = member.external_attr
                            
                            # 手动解压：读取内容并写入清理后的路径
                            target_path = temp_dir / cleaned_filename
                            target_path.parent.mkdir(parents=True, exist_ok=True)
                            
                            if member.is_dir():
                                target_path.mkdir(parents=True, exist_ok=True)
                            else:
                                with zf.open(member, pwd=pwd_bytes) as source:
                                    with open(target_path, 'wb') as target:
                                        target.write(source.read())
                        else:
                            # 正常解压
                            zf.extract(member, str(temp_dir), pwd=pwd_bytes)
                    except RuntimeError as e:
                        if 'Bad password' in str(e) or 'password' in str(e).lower():
                            logger.error("ZIP 密码错误")
                            raise RuntimeError("PASSWORD_INCORRECT")
                        raise
                    
                    if progress_callback:
                        name = Path(member.filename).name or member.filename
                        progress_callback(i, total, f"解压: {name}")
            
            logger.info(f"ZIP 解压完成: {archive_path.name} -> {temp_dir}")
            return temp_dir
            
        except RuntimeError:
            # 重新抛出密码相关错误
            raise
        except zipfile.BadZipFile:
            logger.error(f"无效的 ZIP 文件: {archive_path}")
            return None
        except Exception as e:
            logger.error(f"ZIP 解压失败: {e}", exc_info=True)
            return None
    
    def _extract_7z(
        self,
        archive_path: Path,
        progress_callback: Optional[Callable[[int, int, str], None]] = None,
        password: Optional[str] = None
    ) -> Optional[Path]:
        """解压 .7z 文件（优先使用 py7zr，失败时降级到 7z.exe）
        
        Args:
            archive_path: 7z 文件路径
            progress_callback: 进度回调
            password: 解压密码
            
        Returns:
            解压目录路径，失败返回 None
            
        Raises:
            RuntimeError: 需要密码或密码错误时抛出
        """
        # 优先尝试 py7zr
        try:
            import py7zr
            
            temp_dir = self._create_temp_dir()
            
            with py7zr.SevenZipFile(str(archive_path), mode='r') as sz:
                # 检查密码保护
                if sz.needs_password():
                    if not password:
                        logger.warning("压缩包需要密码")
                        raise RuntimeError("PASSWORD_REQUIRED")
                
                all_files = sz.getnames()
                total = len(all_files)
                
                if progress_callback:
                    progress_callback(0, total, "开始解压 .7z...")
                
                try:
                    # py7zr 一次性解压，密码在 extractall 时传递
                    if password:
                        sz.extractall(path=str(temp_dir), password=password)
                    else:
                        sz.extractall(path=str(temp_dir))
                except py7zr.exceptions.PasswordRequired:
                    logger.warning("7z 压缩包需要密码")
                    raise RuntimeError("PASSWORD_REQUIRED")
                except py7zr.exceptions.Bad7zFile as e:
                    if 'password' in str(e).lower():
                        logger.error("7z 密码错误")
                        raise RuntimeError("PASSWORD_INCORRECT")
                    raise
                
                if progress_callback:
                    progress_callback(total, total, "解压完成")
            
            # 解压成功后，清理广告文件
            self._cleanup_ad_files(temp_dir)
            
            logger.info(f"7z 解压完成（py7zr）: {archive_path.name} -> {temp_dir}")
            return temp_dir
            
        except py7zr.exceptions.UnsupportedCompressionMethodError:
            logger.warning("py7zr 不支持此压缩方法，尝试降级到 7z.exe")
            # 降级到 7z.exe
            return self._extract_7z_with_exe(archive_path, progress_callback, password)
        except ImportError:
            logger.warning("未安装 py7zr 库，尝试使用 7z.exe")
            # 降级到 7z.exe
            return self._extract_7z_with_exe(archive_path, progress_callback, password)
        except RuntimeError:
            # 重新抛出密码相关错误
            raise
        except Exception as e:
            logger.error(f"py7zr 解压失败: {e}，尝试降级到 7z.exe")
            # 降级到 7z.exe
            return self._extract_7z_with_exe(archive_path, progress_callback, password)
    
    def _extract_7z_with_exe(
        self,
        archive_path: Path,
        progress_callback: Optional[Callable[[int, int, str], None]] = None,
        password: Optional[str] = None
    ) -> Optional[Path]:
        """使用 7z.exe 命令行工具解压 .7z 文件
        
        Args:
            archive_path: 7z 文件路径
            progress_callback: 进度回调
            password: 解压密码
            
        Returns:
            解压目录路径，失败返回 None
            
        Raises:
            RuntimeError: 需要密码或密码错误时抛出
        """
        # 查找 7z.exe
        exe_path = self._find_7z_exe()
        if not exe_path:
            logger.error("未找到 7z.exe，请安装 7-Zip: https://www.7-zip.org/")
            raise RuntimeError("MISSING_7Z_EXE")
        
        try:
            temp_dir = self._create_temp_dir()
            
            if progress_callback:
                progress_callback(0, 1, "正在使用 7z.exe 解压...")
            
            # 构建命令行参数
            # x: 解压并保持目录结构
            # -o: 输出目录
            # -y: 自动确认所有提示
            cmd = [str(exe_path), "x", str(archive_path), f"-o{temp_dir}", "-y"]
            
            # 添加密码参数
            if password:
                cmd.append(f"-p{password}")
            else:
                # 不提示密码输入
                cmd.append("-p")
            
            # 执行解压（隐藏命令行窗口）
            import sys
            startupinfo = None
            creationflags = 0
            
            if sys.platform == 'win32':
                # Windows: 隐藏命令行窗口
                creationflags = subprocess.CREATE_NO_WINDOW
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=300,  # 5分钟超时
                encoding='utf-8',
                errors='ignore',
                creationflags=creationflags
            )
            
            # 检查返回码
            if result.returncode == 0:
                # 解压成功后，清理广告文件
                self._cleanup_ad_files(temp_dir)
                
                logger.info(f"7z 解压完成（7z.exe）: {archive_path.name} -> {temp_dir}")
                if progress_callback:
                    progress_callback(1, 1, "解压完成")
                return temp_dir
            elif result.returncode == 2:
                # 错误码 2: 密码错误或需要密码
                if password:
                    logger.error("7z.exe: 密码错误")
                    raise RuntimeError("PASSWORD_INCORRECT")
                else:
                    logger.warning("7z.exe: 需要密码")
                    raise RuntimeError("PASSWORD_REQUIRED")
            else:
                # 其他错误
                error_msg = result.stderr or result.stdout or "未知错误"
                logger.error(f"7z.exe 解压失败 (返回码 {result.returncode}): {error_msg}")
                return None
                
        except subprocess.TimeoutExpired:
            logger.error("7z.exe 解压超时")
            return None
        except RuntimeError:
            # 重新抛出密码相关错误
            raise
        except Exception as e:
            logger.error(f"7z.exe 解压失败: {e}", exc_info=True)
            return None
    
    def _extract_rar(
        self,
        archive_path: Path,
        progress_callback: Optional[Callable[[int, int, str], None]] = None,
        password: Optional[str] = None
    ) -> Optional[Path]:
        """解压 .rar 文件（使用 rarfile）
        
        Args:
            archive_path: rar 文件路径
            progress_callback: 进度回调
            password: 解压密码
            
        Returns:
            解压目录路径，失败返回 None
            
        Raises:
            RuntimeError: 需要密码或密码错误时抛出
        """
        try:
            import rarfile
        except ImportError:
            logger.error("未安装 rarfile 库，无法解压 .rar 文件。请运行: pip install rarfile")
            return None
        
        try:
            temp_dir = self._create_temp_dir()
            
            with rarfile.RarFile(str(archive_path), 'r') as rf:
                # 设置密码
                if password:
                    rf.setpassword(password)
                
                members = rf.infolist()
                total = len(members)
                
                if total == 0:
                    logger.warning("压缩包为空")
                    return temp_dir
                
                for i, member in enumerate(members, 1):
                    # 跳过广告文件
                    member_path = Path(member.filename)
                    if is_ad_file(member_path):
                        logger.info(f"跳过广告文件: {member.filename}")
                        if progress_callback:
                            progress_callback(i, total, f"跳过广告: {member_path.name}")
                        continue
                    
                    try:
                        rf.extract(member, str(temp_dir))
                    except rarfile.PasswordRequired:
                        logger.warning("RAR 压缩包需要密码")
                        raise RuntimeError("PASSWORD_REQUIRED")
                    except rarfile.BadRarFile as e:
                        if 'password' in str(e).lower() or 'encrypted' in str(e).lower():
                            logger.error("RAR 密码错误")
                            raise RuntimeError("PASSWORD_INCORRECT")
                        raise
                    
                    if progress_callback:
                        name = Path(member.filename).name or member.filename
                        progress_callback(i, total, f"解压: {name}")
            
            logger.info(f"RAR 解压完成: {archive_path.name} -> {temp_dir}")
            return temp_dir
            
        except RuntimeError:
            # 重新抛出密码相关错误
            raise
        except Exception as e:
            logger.error(f"RAR 解压失败: {e}", exc_info=True)
            return None
    
    def _cleanup_ad_files(self, directory: Path):
        """清理目录中的广告文件
        
        Args:
            directory: 要清理的目录
        """
        try:
            ad_files_count = 0
            for root, dirs, files in os.walk(directory):
                for filename in files:
                    file_path = Path(root) / filename
                    if is_ad_file(file_path):
                        try:
                            file_path.unlink()
                            ad_files_count += 1
                            logger.debug(f"删除广告文件: {file_path}")
                        except Exception as e:
                            logger.warning(f"删除广告文件失败: {file_path} - {e}")
            
            if ad_files_count > 0:
                logger.info(f"已清理 {ad_files_count} 个广告文件")
        except Exception as e:
            logger.warning(f"清理广告文件失败: {e}")
    
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
