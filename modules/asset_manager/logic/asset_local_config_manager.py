# -*- coding: utf-8 -*-

"""
资产本地配置管理器

从 AssetManagerLogic 提取的配置持久化逻辑（Task 10 重构）。
负责本地配置文件的加载、保存、验证、备份和迁移。
"""

import json
import shutil
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime

from core.utils.config_utils import ConfigUtils
from core.exceptions import ConfigError
from .asset_model import Asset


class AssetLocalConfigManager:
    """资产本地配置管理器

    职责：
    - 本地配置文件的加载和保存
    - 配置格式迁移（旧版本 → 新版本）
    - 配置验证（防止保存损坏的配置）
    - 配置备份和清理
    - 全局配置迁移
    """

    def __init__(self, config_manager, logger: logging.Logger):
        """初始化

        Args:
            config_manager: 核心配置管理器（ConfigManager 实例）
            logger: 日志记录器
        """
        self._config_manager = config_manager
        self._logger = logger

        # 本地配置路径（在资产库目录下，只在需要时初始化）
        self.local_config_path: Optional[Path] = None

        # 本地缩略图目录
        self.thumbnails_dir: Optional[Path] = None

        # 本地文档目录
        self.documents_dir: Optional[Path] = None

        # 备份策略
        self._last_backup_time: Optional[datetime] = None
        self._last_backup_asset_count: int = 0
        self._backup_interval_seconds: int = 300  # 5分钟


    def setup_local_paths(self, asset_library_path: str) -> None:
        """根据资产库路径设置本地配置路径

        Args:
            asset_library_path: 资产库路径字符串
        """
        asset_config_dir = Path(asset_library_path) / ".asset_config"
        self.local_config_path = asset_config_dir / "config.json"
        self.thumbnails_dir = asset_config_dir / "thumbnails"
        self.documents_dir = asset_config_dir / "documents"

    def load_global_config(self) -> Dict[str, Any]:
        """加载全局配置

        Returns:
            配置字典
        """
        config = self._config_manager.load_user_config()
        if not config:
            config = {
                "_version": "2.0.0",
                "asset_libraries": [],
                "current_asset_library": "",
                "preview_projects": [],
                "last_preview_project": "",
                "last_target_project": ""
            }
        return config

    def migrate_global_config(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """迁移旧配置格式到新的多路径格式

        Args:
            config: 原始配置

        Returns:
            迁移后的配置
        """
        version = config.get("_version", "1.0.0")

        # 如果已包含新格式字段，无需迁移
        if config.get("current_asset_library") is not None or config.get("asset_libraries") is not None:
            self._logger.debug("配置已是新格式，跳过迁移")
            return config

        if version == "2.0.0" and not config.get("asset_library_path"):
            self._logger.debug("配置已是最新版本2.0.0")
            return config

        self._logger.info(f"检测到旧配置版本 {version}，开始迁移到新格式...")

        try:
            old_asset_library_path = config.get("asset_library_path", "")
            old_categories = config.get("categories", ["默认分类"])
            old_assets = config.get("assets", [])

            new_config = {
                "_version": "2.0.0",
                "current_asset_library": old_asset_library_path,
                "asset_libraries": [],
                "preview_projects": [],
                "last_preview_project": config.get("last_preview_project_name", ""),
                "last_target_project": config.get("last_target_project_path", ""),
            }

            if old_asset_library_path:
                new_config["asset_libraries"] = [
                    {"path": old_asset_library_path, "name": "主资产库", "last_opened": ""}
                ]
                self._logger.info(f"已迁移资产库路径: {old_asset_library_path}")

            # 迁移预览工程
            old_projects = (config.get("additional_preview_projects_with_names")
                            or config.get("preview_projects", []))
            if not old_projects:
                old_single = config.get("preview_project_path", "")
                if old_single and Path(old_single).exists():
                    old_projects = [{"path": old_single, "name": "默认工程"}]
            new_config["preview_projects"] = old_projects or []

            save_result = self._config_manager.save_user_config(new_config, backup_reason="config_migration")
            if not save_result:
                self._logger.error("保存迁移后的配置失败")
                return config

            self._logger.info("配置迁移完成（旧格式→新格式）")
            return new_config

        except json.JSONDecodeError as e:
            self._logger.error(f"配置迁移失败 - JSON格式错误: {e}", exc_info=True)
            return config
        except (PermissionError, OSError) as e:
            self._logger.error(f"配置迁移失败 - 文件操作错误: {e}", exc_info=True)
            return config
        except Exception as e:
            self._logger.error(f"配置迁移失败 - 未知错误: {e}", exc_info=True)
            return config

    def load_local_config(self) -> Optional[Dict[str, Any]]:
        """从本地配置文件加载资产库配置

        Returns:
            配置字典或None
        """
        if not self.local_config_path:
            self._logger.debug("本地配置路径未设置")
            return None

        try:
            config = ConfigUtils.read_json(self.local_config_path, default=None)

            if config is None:
                self._logger.debug(f"本地配置文件不存在: {self.local_config_path}")
                return None

            version = config.get("_version", "1.0.0")
            if version != "2.0.0":
                self._logger.info(f"检测到本地配置版本 {version}，需要迁移到 2.0.0")
                config = self._migrate_local_config(config)
                self.save_local_config(config)

            self._logger.info(f"成功加载本地配置: {self.local_config_path}")
            return config
        except ConfigError as e:
            self._logger.error(f"加载本地配置失败: {e}")
            return None

    def _migrate_local_config(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """迁移本地配置文件到新版本"""
        version = config.get("_version", "1.0.0")
        self._logger.info(f"开始迁移本地配置，从版本 {version} 到 2.0.0")

        if version == "2.0.0":
            return config

        config["_version"] = "2.0.0"
        return config

    def save_local_config(self, config: Dict[str, Any], create_backup: bool = False) -> bool:
        """保存资产库配置到本地文件

        Args:
            config: 要保存的配置字典
            create_backup: 是否创建备份

        Returns:
            是否保存成功
        """
        if not self.local_config_path:
            self._logger.warning("本地配置路径未设置，无法保存本地配置")
            return False

        try:
            if "_version" not in config:
                config["_version"] = "2.0.0"

            if create_backup and self.local_config_path.exists():
                self._backup_current_config()

            ConfigUtils.write_json(self.local_config_path, config, create_backup=False)

            self._logger.debug(f"成功保存本地配置: {self.local_config_path}")
            return True
        except ConfigError as e:
            self._logger.error(f"保存本地配置失败: {e}")
            return False
        except Exception as e:
            self._logger.error(f"保存本地配置失败: {e}", exc_info=True)
            return False


    def validate_config_before_save(self, config: Dict[str, Any],
                                     current_asset_count: int) -> bool:
        """验证配置完整性，防止保存损坏的配置

        Args:
            config: 要验证的配置
            current_asset_count: 当前内存中的资产数量

        Returns:
            配置有效返回 True
        """
        try:
            assets = config.get("assets", [])

            if current_asset_count > 0 and len(assets) == 0:
                self._logger.error(
                    f"配置验证失败：当前有 {current_asset_count} 个资产，但新配置为空"
                )
                return False

            if current_asset_count > 5 and len(assets) < current_asset_count * 0.5:
                self._logger.error(
                    f"配置验证失败：资产数量从 {current_asset_count} 骤降到 {len(assets)}，"
                    f"拒绝保存以防止数据丢失"
                )
                return False

            for i, asset_data in enumerate(assets):
                if not asset_data.get("id"):
                    self._logger.error(f"配置验证失败：资产 {i} 缺少 id 字段")
                    return False
                if not asset_data.get("name"):
                    self._logger.error(f"配置验证失败：资产 {i} 缺少 name 字段")
                    return False
                if not asset_data.get("path"):
                    self._logger.error(f"配置验证失败：资产 {i} 缺少 path 字段")
                    return False

            return True

        except Exception as e:
            self._logger.error(f"配置验证异常: {e}")
            return False

    def should_create_backup(self, current_asset_count: int) -> bool:
        """判断是否需要创建备份

        Args:
            current_asset_count: 当前资产数量

        Returns:
            True表示需要备份
        """
        if current_asset_count != self._last_backup_asset_count:
            return True

        if self._last_backup_time is None:
            return True

        time_since_last_backup = (datetime.now() - self._last_backup_time).total_seconds()
        if time_since_last_backup >= self._backup_interval_seconds:
            return True

        return False

    def update_backup_record(self, asset_count: int) -> None:
        """更新备份记录

        Args:
            asset_count: 当前资产数量
        """
        self._last_backup_time = datetime.now()
        self._last_backup_asset_count = asset_count

    def _backup_current_config(self) -> bool:
        """备份当前的配置文件

        Returns:
            备份成功返回 True
        """
        try:
            if not self.local_config_path or not self.local_config_path.exists():
                return False

            backup_dir = self.local_config_path.parent / "backup"
            backup_dir.mkdir(parents=True, exist_ok=True)

            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_path = backup_dir / f"config_{timestamp}.json"

            shutil.copy2(self.local_config_path, backup_path)
            self._logger.info(f"已备份当前配置: {backup_path}")

            self._cleanup_old_backups(backup_dir, keep_count=20)

            return True

        except Exception as e:
            self._logger.warning(f"备份当前配置失败: {e}")
            return False

    def _cleanup_old_backups(self, backup_dir: Path, keep_count: int = 20) -> None:
        """清理旧备份，保留指定数量的最新备份"""
        try:
            backup_files = sorted(backup_dir.glob("config_*.json"), reverse=True)

            for old_backup in backup_files[keep_count:]:
                try:
                    old_backup.unlink()
                    self._logger.debug(f"已删除旧备份: {old_backup}")
                except Exception as e:
                    self._logger.warning(f"删除旧备份失败: {e}")

        except Exception as e:
            self._logger.warning(f"清理旧备份失败: {e}")

    def save_full_config(self, assets: List[Asset], categories: List[str],
                          current_lib_path: Optional[Path]) -> None:
        """保存完整配置（序列化资产列表并写入本地配置文件）

        Args:
            assets: 资产列表
            categories: 分类列表
            current_lib_path: 当前资产库路径
        """
        if not current_lib_path:
            return

        # 安全检查：确保 local_config_path 与当前资产库路径一致
        expected_local_config_path = current_lib_path / ".asset_config" / "config.json"
        if self.local_config_path and self.local_config_path != expected_local_config_path:
            self._logger.warning(
                f"检测到配置路径不一致，跳过保存以防止数据覆盖。"
                f"当前路径: {self.local_config_path}, 期望路径: {expected_local_config_path}"
            )
            return

        # 安全检查：验证资产路径是否在当前资产库下
        if assets:
            first_asset_path = assets[0].path
            try:
                first_asset_path.relative_to(current_lib_path)
            except ValueError:
                self._logger.warning(
                    f"检测到资产路径与资产库路径不一致，跳过保存以防止数据覆盖。"
                    f"资产路径: {first_asset_path}, 资产库路径: {current_lib_path}"
                )
                return

        lib_config = {"categories": categories}

        assets_data = []
        for asset in assets:
            assets_data.append({
                "id": asset.id,
                "name": asset.name,
                "asset_type": asset.asset_type.value,
                "path": str(asset.path),
                "category": asset.category,
                "file_extension": asset.file_extension,
                "thumbnail_path": str(asset.thumbnail_path) if asset.thumbnail_path else None,
                "thumbnail_source": asset.thumbnail_source,
                "size": asset.size,
                "created_time": asset.created_time.isoformat(),
                "description": asset.description
            })

        lib_config["assets"] = assets_data

        # 验证配置
        if not self.validate_config_before_save(lib_config, len(assets)):
            self._logger.error("配置验证失败，跳过保存以防止数据丢失")
            return

        # 智能备份
        do_backup = self.should_create_backup(len(assets))
        self.save_local_config(lib_config, create_backup=do_backup)

        if do_backup:
            self.update_backup_record(len(assets))

        self._logger.debug(
            f"已保存 {len(assets)} 个资产的配置到本地: "
            f"{self.local_config_path} (备份: {do_backup})"
        )
