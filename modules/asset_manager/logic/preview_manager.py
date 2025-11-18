"""
预览管理器类

管理 UE 工程预览（启动、关闭、进程管理）。
"""

import os
import subprocess
from pathlib import Path
from typing import Optional, Callable
from logging import Logger

from .file_operations import FileOperations


class PreviewManager:
    """预览管理器类

    提供 UE 工程预览功能：
    - 启动 UE 项目
    - 关闭预览进程
    - 查找 UE 进程
    - 清理预览工程
    """

    def __init__(self, file_ops: FileOperations, logger: Logger):
        """初始化预览管理器

        Args:
            file_ops: 文件操作工具
            logger: 日志记录器
        """
        self._file_ops = file_ops
        self._logger = logger
        self._mock_mode = os.environ.get('ASSET_MANAGER_MOCK_MODE') == '1'

        # 当前预览进程和路径
        self._current_process: Optional[subprocess.Popen] = None
        self._current_project_path: Optional[Path] = None
        self._preview_project_path: Optional[Path] = None

        # 尝试导入 psutil
        self._psutil_available = False
        try:
            import psutil
            self._psutil = psutil
            self._psutil_available = True
            self._logger.info("psutil is available, process management enabled")
        except ImportError:
            self._logger.warning(
                "psutil not installed, process management limited. "
                "Install with: pip install psutil"
            )

        if self._mock_mode:
            self._logger.info("PreviewManager: Mock mode enabled")

    def set_preview_project(self, project_path: Path) -> bool:
        """设置预览工程路径

        Args:
            project_path: 预览工程路径

        Returns:
            bool: 成功返回 True，失败返回 False
        """
        try:
            if not project_path.exists():
                self._logger.error(f"Preview project not found: {project_path}")
                return False

            if not project_path.suffix == '.uproject':
                self._logger.error(f"Invalid project file: {project_path}")
                return False

            self._preview_project_path = project_path
            self._logger.info(f"Set preview project: {project_path}")
            return True

        except Exception as e:
            self._logger.error(f"Failed to set preview project: {e}")
            return False

    def get_preview_project(self) -> Optional[Path]:
        """获取预览工程路径

        Returns:
            Optional[Path]: 预览工程路径，未设置返回 None
        """
        return self._preview_project_path

    def close_current_preview(self) -> bool:
        """关闭当前预览进程

        Returns:
            bool: 成功返回 True，失败返回 False
        """
        if self._mock_mode:
            self._logger.info("Mock mode: closing preview")
            self._current_process = None
            self._current_project_path = None
            return True

        try:
            if not self._current_process:
                self._logger.info("No preview process to close")
                return True

            # 尝试优雅关闭
            self._current_process.terminate()
            try:
                self._current_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                # 强制关闭
                self._current_process.kill()
                self._current_process.wait()

            self._logger.info("Closed preview process")
            self._current_process = None
            self._current_project_path = None
            return True

        except Exception as e:
            self._logger.error(f"Failed to close preview: {e}")
            return False

    def clean_preview_project(self) -> bool:
        """清理预览工程的临时文件

        Returns:
            bool: 成功返回 True，失败返回 False
        """
        try:
            if not self._preview_project_path:
                self._logger.warning("No preview project set")
                return False

            if self._mock_mode:
                self._logger.info("Mock mode: cleaning preview project")
                return True

            project_dir = self._preview_project_path.parent

            # 清理临时目录
            temp_dirs = ["Saved", "Intermediate", "DerivedDataCache"]
            for dir_name in temp_dirs:
                temp_dir = project_dir / dir_name
                if temp_dir.exists():
                    self._file_ops._remove_if_exists(temp_dir)
                    self._logger.info(f"Cleaned: {temp_dir}")

            return True

        except Exception as e:
            self._logger.error(f"Failed to clean preview project: {e}")
            return False




    def find_ue_process(self, project_path: Path) -> Optional[int]:
        """查找 UE 进程

        Args:
            project_path: 项目路径

        Returns:
            Optional[int]: 进程 PID，未找到返回 None
        """
        if self._mock_mode:
            self._logger.info("Mock mode: find_ue_process returns None")
            return None

        try:
            if not self._psutil_available:
                self._logger.warning("psutil not available, cannot find process")
                return None

            project_name = project_path.stem

            # 查找 UE 编辑器进程
            for proc in self._psutil.process_iter(['pid', 'name', 'cmdline']):
                try:
                    cmdline = proc.info.get('cmdline', [])
                    if cmdline and any(project_name in arg for arg in cmdline):
                        self._logger.info(f"Found UE process: PID={proc.info['pid']}")
                        return proc.info['pid']
                except (self._psutil.NoSuchProcess, self._psutil.AccessDenied):
                    continue

            return None

        except Exception as e:
            self._logger.warning(f"Failed to find UE process: {e}")
            return None

    def launch_unreal_project(self, project_path: Path) -> Optional[subprocess.Popen]:
        """启动 UE 项目

        Args:
            project_path: 项目路径

        Returns:
            Optional[subprocess.Popen]: 进程对象，失败返回 None
        """
        if self._mock_mode:
            self._logger.info(f"Mock mode: launching {project_path}")
            return None

        try:
            if not project_path.exists():
                self._logger.error(f"Project not found: {project_path}")
                return None

            # 查找 UE 编辑器路径
            ue_editor_path = self._find_ue_editor()
            if not ue_editor_path:
                self._logger.error("UE Editor not found")
                return None

            # 启动 UE 编辑器
            cmd = [str(ue_editor_path), str(project_path)]
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )

            self._logger.info(f"Launched UE project: {project_path}")
            return process

        except Exception as e:
            self._logger.error(f"Failed to launch UE project: {e}")
            return None

    def _find_ue_editor(self) -> Optional[Path]:
        """查找 UE 编辑器路径

        Returns:
            Optional[Path]: UE 编辑器路径，未找到返回 None
        """
        try:
            # 尝试从环境变量获取
            ue_path = os.environ.get('UE_EDITOR_PATH')
            if ue_path:
                ue_path = Path(ue_path)
                if ue_path.exists():
                    return ue_path

            # 尝试从注册表获取（Windows）
            if os.name == 'nt':
                try:
                    import winreg
                    key = winreg.OpenKey(
                        winreg.HKEY_LOCAL_MACHINE,
                        r"SOFTWARE\EpicGames\Unreal Engine"
                    )
                    # 这里简化处理，实际需要遍历版本
                    # 返回 None 表示未找到
                except Exception:
                    pass

            # 尝试常见路径
            common_paths = [
                Path("C:/Program Files/Epic Games/UE_5.0/Engine/Binaries/Win64/UnrealEditor.exe"),
                Path("C:/Program Files/Epic Games/UE_5.1/Engine/Binaries/Win64/UnrealEditor.exe"),
                Path("C:/Program Files/Epic Games/UE_5.2/Engine/Binaries/Win64/UnrealEditor.exe"),
                Path("C:/Program Files/Epic Games/UE_5.3/Engine/Binaries/Win64/UnrealEditor.exe"),
            ]

            for path in common_paths:
                if path.exists():
                    self._logger.info(f"Found UE Editor: {path}")
                    return path

            return None

        except Exception as e:
            self._logger.warning(f"Failed to find UE editor: {e}")
            return None

    def preview_asset(
        self,
        asset,
        preview_project: Path,
        progress_callback: Optional[Callable[[int, int, str], None]] = None
    ) -> bool:
        """预览资产

        Args:
            asset: 资产对象
            preview_project: 预览工程路径
            progress_callback: 进度回调函数 (current, total, message)

        Returns:
            bool: 成功返回 True，失败返回 False
        """
        if self._mock_mode:
            self._logger.info(f"Mock mode: previewing asset {getattr(asset, 'name', 'unknown')}")
            if progress_callback:
                progress_callback(0, 100, "Starting preview...")
                progress_callback(100, 100, "Preview complete")
            return True

        try:
            # 报告开始
            if progress_callback:
                progress_callback(0, 100, "Preparing preview...")

            # 复制资产到预览工程
            asset_path = Path(getattr(asset, 'path', ''))
            if not asset_path.exists():
                self._logger.error(f"Asset path not found: {asset_path}")
                return False

            target_path = preview_project.parent / "Content" / asset_path.name

            if progress_callback:
                progress_callback(30, 100, "Copying asset...")

            success = self._file_ops.safe_copytree(asset_path, target_path)
            if not success:
                self._logger.error("Failed to copy asset to preview project")
                return False

            if progress_callback:
                progress_callback(60, 100, "Launching UE...")

            # 关闭旧进程
            if self._current_process:
                self.close_current_preview()

            # 启动 UE
            process = self.launch_unreal_project(preview_project)
            if not process:
                return False

            self._current_process = process
            self._current_project_path = preview_project

            if progress_callback:
                progress_callback(100, 100, "Preview launched")

            return True

        except Exception as e:
            self._logger.error(f"Failed to preview asset: {e}")
            return False