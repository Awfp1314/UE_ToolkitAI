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
        """设置预览工程路径（设为 preview_projects 第一个）
        
        Args:
            project_path: 预览工程路径
            
        Returns:
            成功返回True，失败返回False
        """
        try:
            config = self._config_manager.load_user_config() or {}
            projects = config.get("preview_projects", []) or config.get("additional_preview_projects_with_names", [])
            path_str = str(project_path)
            name = project_path.name
            if projects and projects[0].get("path") != path_str:
                projects = [p for p in projects if p.get("path") != path_str]
                projects.insert(0, {"path": path_str, "name": name})
            elif not projects:
                projects = [{"path": path_str, "name": name}]
            config["preview_projects"] = projects
            
            save_result = self._config_manager.save_user_config(config, backup_reason="set_preview_project")
            if not save_result:
                self._logger.error("保存预览工程路径失败")
                return False
            
            self._logger.info(f"预览工程已设置为第一个: {project_path}")
            return True
            
        except Exception as e:
            self._logger.error(f"设置预览工程路径失败: {e}", exc_info=True)
            return False

    def get_preview_project(self) -> Optional[Path]:
        """获取预览工程路径（取 preview_projects 第一个）
        
        Returns:
            预览工程路径，不存在返回None
        """
        try:
            projects = self.get_additional_preview_projects_with_names()
            if projects:
                first_path = projects[0].get("path", "")
                if first_path:
                    path = Path(first_path)
                    if path.exists():
                        return path
            
            # 兼容旧字段 preview_project_path
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
        """获取预览工程列表（读取 preview_projects，兼容旧字段）
        
        Returns:
            包含path和name的字典列表，格式: [{"path": "...", "name": "..."}, ...]
        """
        try:
            config = self._config_manager.load_user_config() or {}
            
            # 优先读新字段 preview_projects
            projects = config.get("preview_projects", [])
            if not projects:
                # 兼容旧字段
                projects = config.get("additional_preview_projects_with_names", [])
            if not projects:
                old_paths = config.get("additional_preview_projects", [])
                projects = [{"path": str(p), "name": f"工程 {i+1}"} for i, p in enumerate(old_paths)]
            
            self._logger.debug(f"已加载 {len(projects)} 个预览工程")
            return projects
            
        except Exception as e:
            self._logger.error(f"获取预览工程路径失败: {e}", exc_info=True)
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
            
            save_result = self._config_manager.save_user_config(config, backup_reason="set_additional_preview_projects")
            if not save_result:
                self._logger.error("保存额外预览工程路径失败")
                return False
            
            self._logger.info(f"已保存 {len(project_paths)} 个额外预览工程路径")
            return True
            
        except Exception as e:
            self._logger.error(f"保存额外预览工程路径失败: {e}", exc_info=True)
            return False

    def set_additional_preview_projects_with_names(self, projects: List[Dict[str, str]]) -> bool:
        """设置预览工程列表（写入 preview_projects）
        
        Args:
            projects: 包含path和name的字典列表，格式: [{"path": "...", "name": "..."}, ...]
            
        Returns:
            成功返回True，失败返回False
        """
        try:
            config = self._config_manager.load_user_config() or {}
            
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
            
            config["preview_projects"] = valid_projects
            
            save_result = self._config_manager.save_user_config(config, backup_reason="set_preview_projects")
            if not save_result:
                self._logger.error("保存预览工程失败")
                return False
            
            self._logger.info(f"已保存 {len(valid_projects)} 个预览工程")
            return True
            
        except Exception as e:
            self._logger.error(f"保存预览工程失败: {e}", exc_info=True)
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
        self._logger.info(f"🎬 开始预览资产: {asset.name}, 预览工程: {preview_project}")
        self._logger.info(f"🔍 progress_callback 是否存在: {progress_callback is not None}")
        
        try:
            # 检查UE版本兼容性（已禁用）
            # if not self._check_ue_version_compatibility(asset, preview_project, on_error):
            #     return
            
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
            
            # 清理虚幻引擎缓存（解决黑色缩略图问题）
            cache_folders = [
                preview_project / "Saved" / "ShaderDebugInfo",
                preview_project / "DerivedDataCache",
                preview_project / "Intermediate"
            ]
            for cache_folder in cache_folders:
                if cache_folder.exists():
                    try:
                        self._logger.info(f"清理缓存: {cache_folder.name}")
                        shutil.rmtree(cache_folder)
                    except Exception as e:
                        self._logger.warning(f"清理缓存失败 {cache_folder.name}: {e}")

            # 强制使用复制模式（已废除符号链接功能）
            use_symlink_preview = False
            operation_text = "复制"
            self._logger.info(f"📋 准备{operation_text}资产到预览工程: {asset.name} (模式: 复制)")
            self._logger.info(f"🔍 资产路径: {asset.path}")
            self._logger.info(f"🔍 预览工程Content路径: {content_dir}")

            # 复制/链接资产到预览工程
            if progress_callback:
                self._logger.info(f"✅ 调用 progress_callback: 正在{operation_text}资产文件...")
                progress_callback(0, 1, f"正在{operation_text}资产文件...")
            else:
                self._logger.warning(f"⚠️ progress_callback 为 None，无法显示进度")
            
            try:
                # 检查资产是否使用包装结构（包含 Content 子文件夹）
                asset_content_folder = asset.path / "Content"
                if asset_content_folder.exists() and asset_content_folder.is_dir():
                    # 包装结构：将 Content 文件夹内的内容复制到预览工程 Content
                    self._logger.info(f"检测到包装结构，从 {asset_content_folder} {operation_text}内容到 {content_dir}")
                    
                    all_items = list(asset_content_folder.iterdir())
                    total_items = len(all_items)
                    
                    if total_items > 0:
                        # 预先计算总大小
                        total_bytes = 0
                        item_sizes = []
                        for item in all_items:
                            if item.is_dir():
                                dir_size = sum(f.stat().st_size for f in item.rglob('*') if f.is_file())
                                item_sizes.append(dir_size)
                                total_bytes += dir_size
                            else:
                                file_size = item.stat().st_size
                                item_sizes.append(file_size)
                                total_bytes += file_size
                        
                        self._logger.info(f"📊 统计到 {total_items} 个项目，总大小 {self._file_ops.format_size(total_bytes)}")
                        
                        copied_bytes = 0
                        for idx, (item, item_size) in enumerate(zip(all_items, item_sizes), 1):
                            target_item = content_dir / item.name
                            
                            # 定义子项的进度回调
                            def item_progress(current_bytes, total_bytes_item, message):
                                if progress_callback and total_bytes > 0:
                                    current_total = copied_bytes + current_bytes
                                    progress_callback(current_total, total_bytes, f"{operation_text}: {item.name}")
                            
                            # 使用安全的文件操作方法
                            if item.is_dir():
                                success = self._file_ops.safe_copytree(
                                    item, target_item, incremental=False, use_symlink=False, 
                                    progress_callback=item_progress
                                )
                            else:
                                success = self._file_ops.safe_copy_file(
                                    item, target_item, progress_callback=item_progress
                                )
                            
                            if not success:
                                error_msg = f"{operation_text} {item.name} 失败"
                                self._logger.error(error_msg)
                                if on_error:
                                    on_error(error_msg)
                                return
                            
                            self._logger.debug(f"已{operation_text}: {item.name}")
                            copied_bytes += item_size
                        
                        if progress_callback:
                            progress_callback(total_bytes, total_bytes, f"已{operation_text} {total_items} 个项目")
                        self._logger.info(f"✅ 成功{operation_text} {total_items} 个项目，总大小 {self._file_ops.format_size(copied_bytes)}")
                
                else:
                    # 旧的直接结构
                    self._logger.warning(f"资产 {asset.name} 没有 Content 子文件夹，使用直接{operation_text}模式")
                    if asset.asset_type == AssetType.PACKAGE:
                        dest_dir = content_dir / asset.path.name
                        success = self._file_ops.safe_copytree(
                            asset.path, dest_dir, use_symlink=False, 
                            progress_callback=progress_callback
                        )
                        if not success:
                            error_msg = f"{operation_text}资产失败"
                            self._logger.error(error_msg)
                            if on_error:
                                on_error(error_msg)
                            return
                    else:
                        dest_file = content_dir / asset.path.name
                        success = self._file_ops.safe_copy_file(
                            asset.path, dest_file, progress_callback=progress_callback
                        )
                        if not success:
                            error_msg = f"{operation_text}文件失败"
                            self._logger.error(error_msg)
                            if on_error:
                                on_error(error_msg)
                            return
                    
                    if progress_callback:
                        progress_callback(1, 1, f"{operation_text}完成！")
            
            except Exception as e:
                error_msg = f"{operation_text}文件失败: {e}"
                self._logger.error(error_msg, exc_info=True)
                if on_error:
                    on_error(error_msg)
                return

            # 启动虚幻引擎
            self._logger.info("启动虚幻引擎预览工程...")
            
            if progress_callback:
                progress_callback(1, 1, "正在启动虚幻引擎...")
            
            def monitor_ue_process():
                """在独立线程中监听虚幻引擎进程"""
                try:
                    process = self._launch_unreal_project(preview_project)
                    
                    if process:
                        self.current_preview_process = process
                        self.current_preview_project_path = preview_project
                        self._logger.info(f"已记录当前预览工程: {preview_project.name} (PID: {process.pid})")
                        
                        # 等待进程结束
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
                        
                        # 复制模式不回写，直接清理
                        self._logger.info("复制预览模式：不回写原始资产，保持源资产安全")
                        
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
            
            monitor_thread = threading.Thread(target=monitor_ue_process, daemon=True)
            monitor_thread.start()
            
        except Exception as e:
            error_msg = f"预览资产失败: {e}"
            self._logger.error(error_msg, exc_info=True)
            if on_error:
                on_error(error_msg)


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

    def _check_ue_version_compatibility(self, asset: Asset, preview_project: Path, on_error: Optional[Callable[[str], None]] = None) -> bool:
        """检查UE版本兼容性
        
        Args:
            asset: 资产对象
            preview_project: 预览工程路径
            on_error: 错误回调
            
        Returns:
            bool: 兼容返回True，不兼容返回False
        """
        try:
            # 检测预览工程的UE版本
            project_version = self._detect_project_ue_version(preview_project)
            
            # 检测资产的UE版本（如果有）
            asset_version = self._detect_asset_ue_version(asset)
            
            if asset_version and project_version:
                # 检查版本兼容性
                if not self._is_version_compatible(asset_version, project_version):
                    error_msg = (
                        f"⚠️ UE版本兼容性警告\n\n"
                        f"资产版本：UE {asset_version}\n"
                        f"预览工程版本：UE {project_version}\n\n"
                        f"继续预览可能导致：\n"
                        f"• 资产被升级到新版本\n"
                        f"• 旧版本UE无法再打开该资产\n"
                        f"• 蓝图、材质等功能丢失\n\n"
                        f"建议：使用相同版本的预览工程"
                    )
                    
                    self._logger.warning(f"UE版本不兼容：资产{asset_version} vs 预览工程{project_version}")
                    
                    if on_error:
                        on_error(error_msg)
                    return False
            
            return True
            
        except Exception as e:
            self._logger.warning(f"检查UE版本兼容性时出错: {e}")
            # 出错时允许继续，但记录警告
            return True
    
    def _detect_project_ue_version(self, project_path: Path) -> Optional[str]:
        """检测UE工程的版本
        
        Args:
            project_path: 工程路径
            
        Returns:
            版本字符串，如 "5.0" 或 "4.27"
        """
        try:
            # 查找 .uproject 文件
            uproject_files = list(project_path.glob("*.uproject"))
            if not uproject_files:
                return None
            
            uproject_file = uproject_files[0]
            
            # 读取 .uproject 文件
            import json
            with open(uproject_file, 'r', encoding='utf-8') as f:
                project_data = json.load(f)
            
            # 获取引擎版本
            engine_version = project_data.get("EngineAssociation", "")
            if engine_version.startswith("{"):
                # 是GUID，需要从注册表或安装目录查找
                return self._find_version_from_guid(engine_version)
            elif engine_version:
                # 直接是版本号
                return engine_version.replace("UE", "")
            
            return None
            
        except Exception as e:
            self._logger.warning(f"检测工程UE版本失败: {e}")
            return None
    
    def _detect_asset_ue_version(self, asset: Asset) -> Optional[str]:
        """检测资产的UE版本
        
        Args:
            asset: 资产对象
            
        Returns:
            版本字符串，如 "5.0" 或 "4.27"
        """
        try:
            # 检查资产目录中的 .uasset 文件
            uasset_files = list(asset.path.rglob("*.uasset"))
            if not uasset_files:
                return None
            
            # 读取第一个 .uasset 文件头来检测版本
            import struct
            with open(uasset_files[0], 'rb') as f:
                # UE资源文件头格式检查
                # 跳过前4字节的magic
                f.seek(4)
                # 读取版本号
                version_bytes = f.read(4)
                if len(version_bytes) == 4:
                    version = struct.unpack('<I', version_bytes)[0]
                    # 将版本号转换为字符串
                    if version >= 500:
                        major = version // 100
                        minor = (version % 100) // 10
                    else:
                        major = version // 100
                        minor = version % 100
                    
                    return f"{major}.{minor}"
            
            return None
            
        except Exception as e:
            self._logger.debug(f"检测资产UE版本失败: {e}")
            return None
    
    def _is_version_compatible(self, asset_version: str, project_version: str) -> bool:
        """判断版本是否兼容
        
        Args:
            asset_version: 资产版本
            project_version: 预览工程版本
            
        Returns:
            bool: 兼容返回True
        """
        try:
            # 解析版本号
            asset_major = int(asset_version.split('.')[0])
            project_major = int(project_version.split('.')[0])
            
            # 主版本相同则兼容
            if asset_major == project_major:
                return True
            
            # UE4和UE5之间不兼容
            if asset_major != project_major:
                return False
            
            return True
            
        except Exception:
            # 解析失败时保守处理，允许继续
            return True
    
    def _find_version_from_guid(self, guid: str) -> Optional[str]:
        """从GUID查找UE版本（简化实现）"""
        # 这里可以扩展为查询注册表或安装目录
        # 暂时返回None，让用户手动确认
        return None
    
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

            # 检查资产是否使用包装结构（包含 Content 子文件夹）
            asset_content_folder = asset.path / "Content"
            if asset_content_folder.exists() and asset_content_folder.is_dir():
                # 包装结构：将 Content 文件夹内的内容复制到目标工程的 Content 文件夹
                self._logger.info(f"检测到包装结构，从 {asset_content_folder} 复制内容到 {target_content}")

                # 获取所有需要复制的项目
                all_items = list(asset_content_folder.iterdir())
                total_items = len(all_items)

                if total_items == 0:
                    self._logger.info("Content 文件夹为空")
                    if progress_callback:
                        progress_callback(1, 1, "迁移完成（空文件夹）")
                else:
                    self._logger.info(f"开始复制 {total_items} 个项目")

                    # 预先计算总大小（用于进度映射）
                    total_bytes = 0
                    item_sizes = []
                    for item in all_items:
                        if item.is_dir():
                            dir_size = sum(f.stat().st_size for f in item.rglob('*') if f.is_file())
                            item_sizes.append(dir_size)
                            total_bytes += dir_size
                        else:
                            file_size = item.stat().st_size
                            item_sizes.append(file_size)
                            total_bytes += file_size
                    
                    self._logger.info(f"📊 统计到 {total_items} 个项目，总大小 {self._file_ops.format_size(total_bytes)}")

                    # 逐个复制每个项目
                    copied_bytes = 0
                    for idx, (item, item_size) in enumerate(zip(all_items, item_sizes), 1):
                        try:
                            target_item = target_content / item.name

                            # 删除旧的目标（如果存在）
                            if target_item.exists():
                                if progress_callback:
                                    progress_callback(idx - 1, total_items, f"删除旧文件: {item.name}")
                                if target_item.is_dir():
                                    shutil.rmtree(target_item)
                                else:
                                    target_item.unlink()

                            # 定义子项的进度回调
                            def item_progress(current_bytes, total_bytes_item, message):
                                if progress_callback and total_bytes > 0:
                                    current_total = copied_bytes + current_bytes
                                    progress_callback(current_total, total_bytes, f"复制: {item.name}")

                            # 使用安全的文件操作方法
                            if item.is_dir():
                                success = self._file_ops.safe_copytree(
                                    item, target_item, progress_callback=item_progress
                                )
                            else:
                                success = self._file_ops.safe_copy_file(
                                    item, target_item, progress_callback=item_progress
                                )
                            
                            if not success:
                                error_msg = f"复制 {item.name} 失败"
                                self._logger.error(error_msg)
                                if error_callback:
                                    error_callback(error_msg)
                                return False

                            self._logger.debug(f"已复制: {item.name}")
                            
                            # 更新已复制字节数
                            copied_bytes += item_size

                        except Exception as e:
                            self._logger.error(f"复制 {item.name} 失败: {e}", exc_info=True)
                            if error_callback:
                                error_callback(f"复制 {item.name} 失败: {e}")
                            return False

                    if progress_callback:
                        progress_callback(total_bytes, total_bytes, f"已复制 {total_items} 个项目")
                    self._logger.info(f"✅ 成功复制 {total_items} 个项目，总大小 {self._file_ops.format_size(copied_bytes)}")
            else:
                # 旧的直接结构（不应该出现，但保留兼容性）
                self._logger.warning(f"资产 {asset.name} 没有 Content 子文件夹，使用直接复制模式")
                if asset.asset_type == AssetType.PACKAGE:
                    dest_dir = target_content / asset.path.name

                    if dest_dir.exists():
                        if progress_callback:
                            progress_callback(0, 1, "正在删除已有的同名文件夹...")
                        shutil.rmtree(dest_dir)

                    # 定义进度回调映射
                    def copy_progress(current, total, message):
                        if progress_callback:
                            progress_callback(current, total, message)
                    
                    success = self._file_ops.safe_copytree(
                        asset.path, dest_dir, progress_callback=copy_progress
                    )
                    if not success:
                        error_msg = f"复制资产失败: {asset.name}"
                        self._logger.error(error_msg)
                        if error_callback:
                            error_callback(error_msg)
                        return False
                else:
                    if progress_callback:
                        progress_callback(0, 1, f"正在复制: {asset.path.name}")
                    dest_file = target_content / asset.path.name
                    
                    # 使用安全的文件复制方法
                    success = self._file_ops.safe_copy_file(asset.path, dest_file)
                    if not success:
                        error_msg = f"复制文件失败: {asset.path.name}"
                        self._logger.error(error_msg)
                        if error_callback:
                            error_callback(error_msg)
                        return False
                    
                    if progress_callback:
                        progress_callback(1, 1, "复制完成！")
            
            # 保存最后使用的目标工程路径
            try:
                config = self._config_manager.load_user_config()
                config["last_target_project"] = str(target_project)
                save_result = self._config_manager.save_user_config(config, backup_reason="migrate_asset")
                if not save_result:
                    self._logger.warning("保存目标工程路径失败")
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
