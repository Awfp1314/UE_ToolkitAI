"""
资产迁移器类

将资产迁移到其他 UE 工程。
"""

import os
from pathlib import Path
from typing import Optional, Callable
from logging import Logger

from .file_operations import FileOperations


class AssetMigrator:
    """资产迁移器类
    
    提供资产迁移功能：
    - 将资产复制到目标 UE 工程
    - 支持进度回调
    - 冲突处理（覆盖模式）
    """
    
    def __init__(self, file_ops: FileOperations, logger: Logger):
        """初始化资产迁移器
        
        Args:
            file_ops: 文件操作工具
            logger: 日志记录器
        """
        self._file_ops = file_ops
        self._logger = logger
        self._mock_mode = os.environ.get('ASSET_MANAGER_MOCK_MODE') == '1'
        
        if self._mock_mode:
            self._logger.info("AssetMigrator: Mock mode enabled")
    
    def migrate_asset(
        self,
        asset,
        target_project: Path,
        progress_callback: Optional[Callable[[int, int, str], None]] = None
    ) -> bool:
        """迁移资产到目标工程
        
        Args:
            asset: 资产对象
            target_project: 目标工程路径
            progress_callback: 进度回调函数 (current, total, message)
        
        Returns:
            bool: 成功返回 True，失败返回 False
        """
        try:
            # 获取资产路径
            asset_path = Path(getattr(asset, 'path', ''))
            if not asset_path or not asset_path.exists():
                self._logger.error(f"Asset path not found: {asset_path}")
                return False
            
            # 检查目标工程路径
            if not target_project.exists():
                self._logger.error(f"Target project not found: {target_project}")
                return False
            
            # 构建目标路径
            asset_name = getattr(asset, 'name', asset_path.name)
            target_content_dir = target_project / "Content"
            target_path = target_content_dir / asset_name
            
            # 确保 Content 目录存在
            target_content_dir.mkdir(parents=True, exist_ok=True)
            
            if self._mock_mode:
                # Mock 模式：模拟迁移过程
                self._logger.info(f"Mock mode: migrating {asset_path} to {target_path}")
                if progress_callback:
                    progress_callback(0, 100, "Starting migration...")
                    progress_callback(50, 100, "Copying files...")
                    progress_callback(100, 100, "Migration complete")
                return True
            
            # 报告开始
            if progress_callback:
                progress_callback(0, 100, f"Starting migration: {asset_name}")

            # 执行复制
            self._logger.info(f"Migrating asset: {asset_path} -> {target_path}")

            # 检查资产是否使用包装结构（包含 Content 子文件夹）
            asset_content_folder = asset_path / "Content"
            if asset_content_folder.exists() and asset_content_folder.is_dir():
                # 包装结构：将 Content 文件夹内的内容复制到目标工程的 Content 文件夹
                self._logger.info(f"Detected wrapper structure, copying from {asset_content_folder} to {target_content_dir}")

                # 获取所有需要复制的项目
                all_items = list(asset_content_folder.iterdir())
                total_items = len(all_items)

                if total_items == 0:
                    self._logger.info("Content folder is empty")
                    if progress_callback:
                        progress_callback(100, 100, "Migration complete (empty folder)")
                    return True

                self._logger.info(f"Copying {total_items} items from Content folder")

                # 逐个复制每个项目
                import shutil
                for idx, item in enumerate(all_items, 1):
                    try:
                        target_item = target_content_dir / item.name

                        # 删除旧的目标（如果存在）
                        if target_item.exists():
                            if progress_callback:
                                percent = int((idx - 0.5) / total_items * 100)
                                progress_callback(percent, 100, f"Removing old: {item.name}")
                            if target_item.is_dir():
                                shutil.rmtree(target_item)
                            else:
                                target_item.unlink()

                        # 复制文件或文件夹
                        if progress_callback:
                            percent = int((idx - 0.5) / total_items * 100)
                            progress_callback(percent, 100, f"Copying: {item.name}")

                        if item.is_dir():
                            shutil.copytree(item, target_item)
                        else:
                            shutil.copy2(item, target_item)

                        self._logger.debug(f"Copied: {item.name}")

                        if progress_callback:
                            percent = int(idx / total_items * 100)
                            progress_callback(percent, 100, f"Copied: {item.name}")

                    except Exception as e:
                        self._logger.error(f"Failed to copy {item.name}: {e}")
                        return False

                self._logger.info(f"Successfully copied {total_items} items")
                if progress_callback:
                    progress_callback(100, 100, "Migration complete")
                return True
            else:
                # 旧的直接结构（不应该出现，但保留兼容性）
                self._logger.warning(f"Asset {asset_name} does not have Content subfolder, using direct copy mode")

                # 使用 FileOperations 复制
                def copy_progress(current, total, message):
                    if progress_callback:
                        # 将文件复制进度映射到 0-100
                        percent = int((current / total) * 100) if total > 0 else 0
                        progress_callback(percent, 100, message)

                success = self._file_ops.safe_copytree(
                    asset_path,
                    target_path,
                    progress_callback=copy_progress
                )

                if success:
                    self._logger.info(f"Successfully migrated asset to: {target_path}")
                    if progress_callback:
                        progress_callback(100, 100, "Migration complete")
                    return True
                else:
                    self._logger.error(f"Failed to migrate asset: {asset_path}")
                    return False
                
        except Exception as e:
            self._logger.error(f"Migration failed: {e}")
            return False

