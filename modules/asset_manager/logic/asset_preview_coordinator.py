# -*- coding: utf-8 -*-

"""
资产预览协调器

管理预览工程配置、预览执行、进程管理和截图处理。
从 asset_manager_logic.py 提取（Task 9 重构）。
"""

import shutil
import subprocess
import threading
from pathlib import Path
from typing import List, Optional, Dict, Any, Callable
from logging import Logger

from core.exceptions import AssetError
from .asset_model import Asset, AssetType
from .file_operations import FileOperations
from .screenshot_processor import ScreenshotProcessor


class AssetPreviewCoordinator:
    """资产预览协调器
    
    职责：
    - 预览工程配置管理（设置/获取预览工程路径）
    - 预览执行（启动UE引擎、复制资产到预览工程）
    - 进程管理（查找/关闭UE进程）
    - 截图处理（预览后处理截图）
    - 资产迁移（从资产库复制到目标工程）
    """

    def __init__(
        self,
        config_manager: Any,
        file_ops: FileOperations,
        screenshot_processor: ScreenshotProcessor,
        logger: Logger
    ):
        """初始化预览协调器
        
        Args:
            config_manager: 配置管理器（用于读写预览工程配置）
            file_ops: 文件操作工具
            screenshot_processor: 截图处理器
            logger: 日志记录器
        """
        self._config_manager = config_manager
        self._file_ops = file_ops
        self._screenshot_processor = screenshot_processor
        self._logger = logger

        # 当前预览工程的进程和路径
        self.current_preview_process = None
        self.current_preview_project_path: Optional[Path] = None

    # ─── 预览工程配置 ───────────────────────────────────────

    def set_preview_project(self, project_path: Path) -> bool:
        """设置预览工程路径
        
        Args:
            project_path: 预览工程路径
            
        Returns:
            成功返回True，失败返回False
        """
        try:
            config = self._config_manager.load_user_config() or {}
            config["preview_project_path"] = str(project_path)
            self._config_manager.save_user_config(config)
            
            self._logger.info(f"预览工程路径已设置: {project_path}")
            return True
            
        except Exception as e:
            self._logger.error(f"设置预览工程路径失败: {e}", exc_info=True)
            return False

    def get_preview_project(self) -> Optional[Path]:
        """获取预览工程路径
        
        优先级：
        1. 额外工程列表中的第一个工程
        2. 配置中的旧单个预览工程
        
        Returns:
            预览工程路径，不存在返回None
        """
        try:
            # 优先从额外工程中获取第一个
            additional_projects = self.get_additional_preview_projects_with_names()
            if additional_projects:
                first_project_path = additional_projects[0].get("path", "")
                if first_project_path:
                    path = Path(first_project_path)
                    if path.exists():
                        return path
            
            # 回退到旧的单个预览工程配置
            config = self._config_manager.load_user_config()
            preview_path = config.get("preview_project_path", "")
            if preview_path:
                path = Path(preview_path)
                if path.exists():
                    return path
            
            return None
        except Exception as e:
            self._logger.error(f"获取预览工程路径失败: {e}", exc_info=True)
            return None

    def get_additional_preview_projects(self) -> List[str]:
        """获取额外的预览工程路径列表
        
        Returns:
            额外预览工程路径列表（字符串）
        """
        try:
            config = self._config_manager.load_user_config() or {}
            additional_paths = config.get("additional_preview_projects", [])
            
            # 确保返回的是字符串列表
            if isinstance(additional_paths, list):
                return [str(p) for p in additional_paths]
            
            self._logger.debug(f"已加载 {len(additional_paths)} 个额外预览工程路径")
            return additional_paths
            
        except Exception as e:
            self._logger.error(f"获取额外预览工程路径失败: {e}", exc_info=True)
            return []

    def get_additional_preview_projects_with_names(self) -> List[Dict[str, str]]:
        """获取额外的预览工程路径和名称列表
        
        Returns:
            包含path和name的字典列表，格式: [{"path": "...", "name": "..."}, ...]
        """
        try:
            config = self._config_manager.load_user_config() or {}
            
            # 支持新旧格式的兼容性
            additional_projects = config.get("additional_preview_projects_with_names", [])
            if not additional_projects:
                # 尝试从旧格式迁移
                old_paths = config.get("additional_preview_projects", [])
                additional_projects = [
                    {"path": str(p), "name": f"工程 {i+1}"} 
                    for i, p in enumerate(old_paths)
                ]
            
            self._logger.debug(f"已加载 {len(additional_projects)} 个额外预览工程")
            return additional_projects
            
        except Exception as e:
            self._logger.error(f"获取额外预览工程路径失败: {e}", exc_info=True)
            return []

    def set_additional_preview_projects(self, project_paths: List[str]) -> bool:
        """设置额外的预览工程路径列表
        
        Args:
            project_paths: 预览工程路径列表
            
        Returns:
            成功返回True，失败返回False
        """
        try:
            config = self._config_manager.load_user_config() or {}
            
            # 验证所有路径都存在
            for path_str in project_paths:
                path = Path(path_str)
                if not path.exists():
                    self._logger.warning(f"预览工程路径不存在，跳过: {path_str}")
                    project_paths = [p for p in project_paths if p != path_str]
            
            config["additional_preview_projects"] = project_paths
            self._config_manager.save_user_config(config)
            
            self._logger.info(f"已保存 {len(project_paths)} 个额外预览工程路径")
            return True
            
        except Exception as e:
            self._logger.error(f"保存额外预览工程路径失败: {e}", exc_info=True)
            return False

    def set_additional_preview_projects_with_names(self, projects: List[Dict[str, str]]) -> bool:
        """设置额外的预览工程路径和名称列表
        
        Args:
            projects: 包含path和name的字典列表，格式: [{"path": "...", "name": "..."}, ...]
            
        Returns:
            成功返回True，失败返回False
        """
        try:
            config = self._config_manager.load_user_config() or {}
            
            # 验证所有路径都存在
            valid_projects = []
            for project in projects:
                path_str = project.get("path", "")
                name = project.get("name", "")
                if not path_str or not name:
                    continue
                
                path = Path(path_str)
                if not path.exists():
                    self._logger.warning(f"预览工程路径不存在，跳过: {path_str}")
                    continue
                
                valid_projects.append({"path": path_str, "name": name})
            
            config["additional_preview_projects_with_names"] = valid_projects
            self._config_manager.save_user_config(config)
            
            self._logger.info(f"已保存 {len(valid_projects)} 个额外预览工程")
            return True
            
        except Exception as e:
            self._logger.error(f"保存额外预览工程路径失败: {e}", exc_info=True)
            return False

    # ─── 预览工程清理 ──────────────────────────────────────

    def clean_preview_project(
        self,
        error_callback: Optional[Callable[[str], None]] = None
    ) -> bool:
        """清理预览工程的Content文件夹
        
        Args:
            error_callback: 错误回调函数（用于发射信号）
            
        Returns:
            成功返回True，失败返回False
        """
        try:
            preview_project = self.get_preview_project()
            if not preview_project or not preview_project.exists():
                error_msg = "预览工程未设置或不存在"
                self._logger.error(error_msg)
                if error_callback:
                    error_callback(error_msg)
                return False
            
            content_dir = preview_project / "Content"
            if content_dir.exists():
                self._logger.info(f"清空预览工程Content文件夹: {content_dir}")
                shutil.rmtree(content_dir)
                content_dir.mkdir(parents=True, exist_ok=True)
                self._logger.info("预览工程Content文件夹已清理")
                return True
            else:
                self._logger.info("Content文件夹不存在，无需清理")
                return True
                
        except Exception as e:
            error_msg = f"清理预览工程失败: {e}"
            self._logger.error(error_msg, exc_info=True)
            if error_callback:
                error_callback(error_msg)
            return False

    # ─── 预览执行 ──────────────────────────────────────────

    def do_preview_asset(
        self,
        asset: Asset,
        preview_project: Path,
        progress_callback: Optional[Callable] = None,
        on_preview_finished: Optional[Callable] = None,
        on_error: Optional[Callable[[str], None]] = None,
        on_thumbnail_updated: Optional[Callable[[str, str], None]] = None,
        save_config_callback: Optional[Callable] = None,
        thumbnails_dir: Optional[Path] = None
    ) -> None:
        """执行资产预览（后台线程）
        
        Args:
            asset: 资产对象
            preview_project: 预览工程路径
            progress_callback: 进度回调函数 (current, total, message)
            on_preview_finished: 预览完成回调
            on_error: 错误回调
            on_thumbnail_updated: 缩略图更新回调 (asset_id, thumbnail_path)
            save_config_callback: 保存配置回调
            thumbnails_dir: 缩略图目录
        """
        try:
            # 清空预览工程的Content文件夹
            content_dir = preview_project / "Content"
            
            # 检查资产路径是否在预览工程内（防止循环复制）
            try:
                asset_path_resolved = asset.path.resolve()
                content_dir_resolved = content_dir.resolve()
                
                if asset_path_resolved == content_dir_resolved or \
                   content_dir_resolved in asset_path_resolved.parents:
                    error_msg = "不能预览位于预览工程Content目录内的资产，这会导致循环复制！\n\n请选择预览工程外的资产。"
                    self._logger.error(error_msg)
                    if on_error:
                        on_error(error_msg)
                    return
            except Exception as e:
                self._logger.warning(f"检查路径时出错: {e}")
            
            if progress_callback:
                progress_callback(0, 1, "正在清空预览工程Content文件夹...")
            
            if content_dir.exists():
                self._logger.info("清空预览工程Content文件夹...")
                shutil.rmtree(content_dir)
            content_dir.mkdir(parents=True, exist_ok=True)
            
            # 链接资产到Content文件夹（使用符号链接，极快）
            self._logger.info(f"链接资产到预览工程: {asset.name}")
            if asset.asset_type == AssetType.PACKAGE:
                dest_dir = content_dir / asset.path.name
                self._file_ops.safe_copytree(
                    asset.path, 
                    dest_dir, 
                    progress_callback=progress_callback,
                    use_symlink=True
                )
            else:
                if progress_callback:
                    progress_callback(0, 1, f"正在复制: {asset.path.name}")
                dest_file = content_dir / asset.path.name
                shutil.copy2(asset.path, dest_file)
                if progress_callback:
                    progress_callback(1, 1, "复制完成！")
            
            # 启动虚幻引擎
            self._logger.info("启动虚幻引擎预览工程...")
            
            if progress_callback:
                progress_callback(1, 1, "资产链接完成，正在启动虚幻引擎...")
            
            def launch_and_monitor():
                """在独立线程中启动和监听虚幻引擎"""
                try:
                    process = self._launch_unreal_project(preview_project)
                    
                    if process:
                        self.current_preview_process = process
                        self.current_preview_project_path = preview_project
                        self._logger.info(f"已记录当前预览工程: {preview_project.name} (PID: {process.pid})")
                    
                    if process:
                        self._logger.info("监听虚幻引擎进程，等待关闭后自动清理...")
                        process.wait()
                        self._logger.info("虚幻引擎已关闭，开始处理截图和清理预览工程...")
                        
                        try:
                            self.process_screenshot(
                                asset=asset,
                                preview_project=preview_project,
                                thumbnails_dir=thumbnails_dir,
                                on_thumbnail_updated=on_thumbnail_updated,
                                save_config_callback=save_config_callback
                            )
                        except Exception as e:
                            self._logger.error(f"处理截图时出错: {e}", exc_info=True)
                        
                        # 同步 UE 中的修改回原始资产目录
                        try:
                            if asset.asset_type == AssetType.PACKAGE:
                                dest_dir = content_dir / asset.path.name
                                self._sync_changes_back(dest_dir, asset.path)
                                if save_config_callback:
                                    save_config_callback()
                        except Exception as e:
                            self._logger.error(f"同步修改回原始资产时出错: {e}", exc_info=True)
                        
                        # 自动清理Content文件夹
                        if content_dir.exists():
                            shutil.rmtree(content_dir)
                            content_dir.mkdir(parents=True, exist_ok=True)
                            self._logger.info("预览工程Content文件夹已自动清理完成")
                        
                        self.current_preview_process = None
                        self.current_preview_project_path = None
                    
                    if on_preview_finished:
                        on_preview_finished()
                except Exception as e:
                    self._logger.error(f"启动或监听虚幻引擎时出错: {e}", exc_info=True)
                    if on_error:
                        on_error(f"启动虚幻引擎失败: {e}")
                    self.current_preview_process = None
                    self.current_preview_project_path = None
            
            monitor_thread = threading.Thread(target=launch_and_monitor, daemon=True)
            monitor_thread.start()
            
        except Exception as e:
            error_msg = f"预览资产失败: {e}"
            self._logger.error(error_msg, exc_info=True)
            if on_error:
                on_error(error_msg)

    # ─── 预览修改同步 ─────────────────────────────────────

    def _sync_changes_back(self, content_asset_dir: Path, original_asset_dir: Path) -> None:
        """将 UE 中的修改同步回原始资产目录
        
        三种同步：
        1. 修改：Content 中非符号链接的文件 → 覆盖回原始目录
        2. 新增：Content 中非符号链接且原始目录没有的 → 复制到原始目录
        3. 删除：原始目录有但 Content 中不存在的 → 从原始目录删除
        
        Args:
            content_asset_dir: Content 中的资产目录（如 Content/MyAsset/）
            original_asset_dir: 原始资产目录（资产库中的路径）
        """
        import os
        
        if not content_asset_dir.exists():
            return
        
        synced_count = 0
        new_count = 0
        deleted_count = 0
        
        # ── 第1步：同步修改和新增（Content → 原始资产）──
        for item in content_asset_dir.rglob('*'):
            if not item.is_file():
                continue
            
            # 跳过符号链接（未被修改的文件）
            if os.path.islink(str(item)):
                continue
            
            # 这是一个真实文件 — UE 修改或新建的
            rel_path = item.relative_to(content_asset_dir)
            target_path = original_asset_dir / rel_path
            
            try:
                target_path.parent.mkdir(parents=True, exist_ok=True)
                is_new = not target_path.exists()
                shutil.copy2(str(item), str(target_path))
                
                if is_new:
                    new_count += 1
                    self._logger.info(f"同步新文件: {rel_path}")
                else:
                    synced_count += 1
                    self._logger.info(f"同步修改: {rel_path}")
            except Exception as e:
                self._logger.error(f"同步文件失败 {rel_path}: {e}")
        
        # ── 第2步：同步删除（原始资产中有但 Content 中没有的）──
        for item in original_asset_dir.rglob('*'):
            if not item.is_file():
                continue
            
            rel_path = item.relative_to(original_asset_dir)
            content_item = content_asset_dir / rel_path
            
            # 如果 Content 中既没有符号链接也没有真实文件，说明被 UE 删了
            if not content_item.exists() and not os.path.islink(str(content_item)):
                try:
                    item.unlink()
                    deleted_count += 1
                    self._logger.info(f"同步删除: {rel_path}")
                except Exception as e:
                    self._logger.error(f"删除文件失败 {rel_path}: {e}")
        
        # 清理空目录
        if deleted_count > 0:
            for dirpath in sorted(original_asset_dir.rglob('*'), reverse=True):
                if dirpath.is_dir() and not any(dirpath.iterdir()):
                    try:
                        dirpath.rmdir()
                        self._logger.info(f"清理空目录: {dirpath.relative_to(original_asset_dir)}")
                    except Exception:
                        pass
        
        total = synced_count + new_count + deleted_count
        if total > 0:
            self._logger.info(f"预览修改已同步: {synced_count} 修改, {new_count} 新增, {deleted_count} 删除")
        else:
            self._logger.info("预览中无修改，无需同步")

    # ─── 进程管理 ──────────────────────────────────────────

    def _launch_unreal_project(self, project_path: Path):
        """启动虚幻引擎工程
        
        Args:
            project_path: 工程路径
            
        Returns:
            进程对象（如果可获取），用于监听引擎关闭；否则返回None
        """
        uproject_files = list(project_path.glob("*.uproject"))
        if not uproject_files:
            raise FileNotFoundError(f"未找到.uproject文件: {project_path}")
        
        uproject_file = uproject_files[0]
        
        import sys
        
        try:
            if sys.platform == "win32":
                import os
                try:
                    os.startfile(str(uproject_file))
                    self._logger.info(f"已启动工程: {uproject_file.name}")
                    
                    import time
                    time.sleep(2)
                    
                    ue_process = self._find_ue_process()
                    if ue_process:
                        self._logger.info(f"找到虚幻引擎进程: PID {ue_process.pid}")
                        return ue_process
                    else:
                        self._logger.warning("未能找到虚幻引擎进程，无法自动清理")
                        return None
                except OSError as e:
                    self._logger.error(f"启动工程失败: {e}")
                    raise AssetError(f"无法启动虚幻引擎项目: {e}") from e
                    
            elif sys.platform == "darwin":
                process = subprocess.Popen(
                    ['open', '-W', str(uproject_file)],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL
                )
                self._logger.info(f"已启动工程: {uproject_file.name}")
                return process
            else:
                process = subprocess.Popen(
                    ['xdg-open', str(uproject_file)],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL
                )
                self._logger.info(f"已启动工程: {uproject_file.name}")
                return process
                
        except AssetError:
            raise
        except Exception as e:
            self._logger.error(f"启动工程时出错: {e}", exc_info=True)
            raise AssetError(f"启动虚幻引擎项目失败: {e}") from e

    def check_preview_project_running(self, preview_project: Path):
        """检查指定的预览工程是否有UE进程在运行
        
        Args:
            preview_project: 预览工程路径
            
        Returns:
            如果找到正在运行该工程的进程，返回进程对象，否则返回None
        """
        try:
            import psutil
            
            uproject_files = list(preview_project.glob("*.uproject"))
            if not uproject_files:
                return None
            
            uproject_file = uproject_files[0]
            uproject_name = uproject_file.name
            
            ue_process_names = [
                'UE4Editor.exe',
                'UE4Editor-Win64-Debug.exe',
                'UE4Editor-Win64-DebugGame.exe',
                'UnrealEditor.exe',
                'UnrealEditor-Win64-Debug.exe',
                'UnrealEditor-Win64-DebugGame.exe',
            ]
            
            for proc in psutil.process_iter(['name']):
                try:
                    if proc.info['name'] in ue_process_names:
                        cmdline = proc.cmdline()
                        for arg in cmdline:
                            if uproject_name in arg or str(uproject_file) in arg:
                                return proc
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
            
            return None
            
        except ImportError:
            self._logger.warning("psutil未安装，无法检查预览工程")
            return None
        except Exception as e:
            self._logger.error(f"检查预览工程时出错: {e}")
            return None

    def _find_ue_process(self):
        """查找虚幻引擎编辑器进程（Windows）- 返回最新启动的进程"""
        try:
            import psutil
            
            ue_process_names = [
                'UE4Editor.exe',
                'UE4Editor-Win64-Debug.exe',
                'UE4Editor-Win64-DebugGame.exe',
                'UnrealEditor.exe',
                'UnrealEditor-Win64-Debug.exe',
                'UnrealEditor-Win64-DebugGame.exe',
            ]
            
            ue_processes = []
            for proc in psutil.process_iter(['name', 'create_time']):
                try:
                    if proc.info['name'] in ue_process_names:
                        ue_processes.append((proc, proc.info['create_time']))
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
            
            if not ue_processes:
                return None
            
            ue_processes.sort(key=lambda x: x[1], reverse=True)
            latest_proc = ue_processes[0][0]
            return latest_proc
            
        except ImportError:
            self._logger.warning("psutil未安装，无法查找UE进程。自动清理功能将不可用。")
            return None
        except Exception as e:
            self._logger.error(f"查找UE进程时出错: {e}")
            return None

    def close_current_preview_if_running(self) -> bool:
        """关闭当前正在运行的预览工程（如果有）并清空Content文件夹
        
        Returns:
            bool: 如果成功关闭或无需关闭返回True，失败返回False
        """
        if not self.current_preview_process or not self.current_preview_project_path:
            return True
        
        try:
            import psutil
            
            if not psutil.pid_exists(self.current_preview_process.pid):
                self._logger.info("之前的预览工程已关闭")
                self.current_preview_process = None
                self.current_preview_project_path = None
                return True
            
            try:
                proc = psutil.Process(self.current_preview_process.pid)
                
                ue_process_names = [
                    'UE4Editor.exe',
                    'UE4Editor-Win64-Debug.exe',
                    'UE4Editor-Win64-DebugGame.exe',
                    'UnrealEditor.exe',
                    'UnrealEditor-Win64-Debug.exe',
                    'UnrealEditor-Win64-DebugGame.exe',
                ]
                
                if proc.name() not in ue_process_names:
                    self._logger.warning(f"进程 {proc.pid} 不是UE进程，跳过关闭")
                    self.current_preview_process = None
                    self.current_preview_project_path = None
                    return True
                
                self._logger.info(f"正在关闭预览工程: {self.current_preview_project_path.name} (PID: {proc.pid})")
                proc.terminate()
                
                preview_project_path = self.current_preview_project_path
                
                import time
                for i in range(10):
                    if not proc.is_running():
                        self._logger.info("预览工程已成功关闭")
                        break
                    time.sleep(1)
                else:
                    self._logger.warning("优雅关闭超时，强制关闭预览工程")
                    proc.kill()
                    time.sleep(1)
                
                content_dir = preview_project_path / "Content"
                if content_dir.exists():
                    self._logger.info(f"清空预览工程Content文件夹: {content_dir}")
                    shutil.rmtree(content_dir)
                    content_dir.mkdir(parents=True, exist_ok=True)
                    self._logger.info("预览工程Content文件夹已清空")
                
                self.current_preview_process = None
                self.current_preview_project_path = None
                return True
                
            except psutil.NoSuchProcess:
                self._logger.info("预览工程进程已不存在")
                self.current_preview_process = None
                self.current_preview_project_path = None
                return True
            except psutil.AccessDenied:
                self._logger.error("无权限关闭预览工程进程")
                return False
                
        except ImportError:
            self._logger.warning("psutil未安装，无法关闭预览工程")
            return False
        except Exception as e:
            self._logger.error(f"关闭预览工程时出错: {e}", exc_info=True)
            return False

    # ─── 截图处理 ──────────────────────────────────────────

    def process_screenshot(
        self,
        asset: Asset,
        preview_project: Path,
        thumbnails_dir: Optional[Path] = None,
        on_thumbnail_updated: Optional[Callable[[str, str], None]] = None,
        save_config_callback: Optional[Callable] = None
    ) -> None:
        """处理预览截图
        
        在虚幻引擎关闭后，查找并移动截图到缩略图目录
        
        Args:
            asset: 资产对象
            preview_project: 预览工程路径
            thumbnails_dir: 缩略图目录
            on_thumbnail_updated: 缩略图更新回调 (asset_id, thumbnail_path)
            save_config_callback: 保存配置回调
        """
        try:
            has_thumbnail = asset.thumbnail_path and Path(asset.thumbnail_path).exists()

            # 查找截图文件
            screenshot_path, source = self._screenshot_processor.find_screenshot(
                preview_project, asset.thumbnail_source
            )
            
            if not screenshot_path:
                if has_thumbnail:
                    self._logger.info(f"资产 {asset.name} 保留原缩略图，未找到新截图")
                else:
                    self._logger.info(f"未找到资产 {asset.name} 的截图")
                return
            
            if not thumbnails_dir:
                self._logger.warning("缩略图目录未设置，无法处理截图")
                return
            
            thumbnail_filename = f"{asset.id}.png"
            thumbnail_path = thumbnails_dir / thumbnail_filename
            
            # 确保缩略图目录存在
            if not thumbnails_dir.exists():
                thumbnails_dir.mkdir(parents=True, exist_ok=True)
                self._logger.info(f"创建缩略图目录: {thumbnails_dir}")
            
            try:
                if thumbnail_path.exists():
                    thumbnail_path.unlink()
                    self._logger.debug(f"删除旧缩略图: {thumbnail_path}")
                
                shutil.move(str(screenshot_path), str(thumbnail_path))
                self._logger.info(f"截图已移动: {screenshot_path} -> {thumbnail_path}")
                
                asset.thumbnail_path = thumbnail_path
                asset.thumbnail_source = source
                
                if save_config_callback:
                    save_config_callback()
                
                if on_thumbnail_updated:
                    on_thumbnail_updated(asset.id, str(thumbnail_path))
                
                self._logger.info(f"资产 {asset.name} 的缩略图已更新，来源: {source}")
                
            except Exception as e:
                self._logger.error(f"移动截图文件时出错: {e}", exc_info=True)
                
        except Exception as e:
            self._logger.error(f"处理截图时出错: {e}", exc_info=True)

    # ─── 资产迁移 ──────────────────────────────────────────

    def migrate_asset(
        self,
        asset: Asset,
        target_project: Path,
        progress_callback: Optional[Callable] = None,
        error_callback: Optional[Callable[[str], None]] = None
    ) -> bool:
        """将资产迁移到目标工程
        
        Args:
            asset: 资产对象
            target_project: 目标工程路径
            progress_callback: 进度回调函数 (current, total, message)
            error_callback: 错误回调函数
            
        Returns:
            成功返回True，失败返回False
        """
        try:
            if not target_project.exists():
                error_msg = f"目标工程不存在: {target_project}"
                self._logger.error(error_msg)
                if error_callback:
                    error_callback(error_msg)
                return False
            
            target_content = target_project / "Content"
            if not target_content.exists():
                error_msg = f"目标工程Content文件夹不存在: {target_content}"
                self._logger.error(error_msg)
                if error_callback:
                    error_callback(error_msg)
                return False
            
            self._logger.info(f"迁移资产到目标工程: {asset.name}")
            if asset.asset_type == AssetType.PACKAGE:
                dest_dir = target_content / asset.path.name
                
                if dest_dir.exists():
                    if progress_callback:
                        progress_callback(0, 1, "正在删除已有的同名文件夹...")
                    shutil.rmtree(dest_dir)

                self._file_ops.safe_copytree(asset.path, dest_dir, progress_callback=progress_callback)
            else:
                if progress_callback:
                    progress_callback(0, 1, f"正在复制: {asset.path.name}")
                dest_file = target_content / asset.path.name
                shutil.copy2(asset.path, dest_file)
                if progress_callback:
                    progress_callback(1, 1, "复制完成！")
            
            # 保存最后使用的目标工程路径
            try:
                config = self._config_manager.load_user_config()
                config["last_target_project_path"] = str(target_project)
                self._config_manager.save_user_config(config)
            except Exception as e:
                self._logger.warning(f"保存目标工程路径失败: {e}")
            
            self._logger.info(f"资产迁移成功: {asset.name} -> {target_project}")
            return True
            
        except Exception as e:
            error_msg = f"迁移资产失败: {e}"
            self._logger.error(error_msg, exc_info=True)
            if error_callback:
                error_callback(error_msg)
            return False
