"""
配置管理器类

管理资产库配置（全局配置 + 本地配置）。
"""

import os
import json
from pathlib import Path
from typing import Dict, Any, List, Optional
from logging import Logger


class ConfigHandler:
    """配置管理器类
    
    提供配置管理功能：
    - 加载/保存全局配置
    - 加载/保存本地配置
    - 配置迁移
    - 资产库路径管理
    """
    
    # 本地配置文件名
    LOCAL_CONFIG_FILE = ".asset_library.json"
    
    # 备份目录名
    BACKUP_DIR = ".backups"
    
    def __init__(self, config_manager, logger: Logger):
        """初始化配置管理器
        
        Args:
            config_manager: 核心配置管理器
            logger: 日志记录器
        """
        self._config_manager = config_manager
        self._logger = logger
        self._mock_mode = os.environ.get('ASSET_MANAGER_MOCK_MODE') == '1'
        
        # 配置缓存
        self._config_cache = None
        self._cache_valid = False
        
        if self._mock_mode:
            self._logger.info("ConfigHandler: Mock mode enabled")
    
    def invalidate_cache(self):
        """使缓存失效"""
        self._cache_valid = False
        self._config_cache = None
    
    def load_config(self) -> Dict[str, Any]:
        """加载全局配置（带缓存）
        
        Returns:
            Dict[str, Any]: 全局配置
        """
        # 如果缓存有效，直接返回
        if self._cache_valid and self._config_cache is not None:
            return self._config_cache
        
        try:
            config = self._config_manager.load_user_config()
            if not config:
                # 返回默认配置
                config = {
                    "_version": "2.0.0",
                    "asset_libraries": [],
                    "current_asset_library": "",
                    "preview_projects": [],
                    "last_preview_project": "",
                    "last_target_project": ""
                }
            
            # 缓存配置
            self._config_cache = config
            self._cache_valid = True
            
            return config
        except Exception as e:
            self._logger.error(f"Failed to load config: {e}")
            return {}
    
    def save_config(self, assets: List, categories: List[str]) -> bool:
        """保存全局配置
        
        Args:
            assets: 资产列表
            categories: 分类列表
        
        Returns:
            bool: 成功返回 True，失败返回 False
        """
        try:
            # 加载当前配置
            config = self.load_config()
            
            # 更新资产库路径的配置
            asset_library_path = config.get("current_asset_library", "") or config.get("asset_library_path", "")
            if asset_library_path:
                libs = config.setdefault("asset_libraries", [])
                existing = next((l for l in libs if l.get("path") == asset_library_path), None)
                if not existing:
                    libs.append({"path": asset_library_path, "name": "主资产库", "last_opened": ""})
            
            # 保存配置
            result = self._config_manager.save_user_config(config, backup_reason="manual_save")
            
            # 使缓存失效
            if result:
                self.invalidate_cache()
            
            return result
            
        except Exception as e:
            self._logger.error(f"Failed to save config: {e}")
            return False
    
    def load_local_config(self, library_path: Path) -> Optional[Dict[str, Any]]:
        """加载本地配置
        
        Args:
            library_path: 资产库路径
        
        Returns:
            Optional[Dict[str, Any]]: 本地配置，失败返回 None
        """
        try:
            local_config_path = library_path / self.LOCAL_CONFIG_FILE
            if not local_config_path.exists():
                self._logger.info(f"Local config not found: {local_config_path}")
                return None
            
            with open(local_config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
            
            self._logger.info(f"Loaded local config from: {local_config_path}")
            return config
            
        except Exception as e:
            self._logger.error(f"Failed to load local config: {e}")
            return None
    
    def save_local_config(
        self,
        library_path: Path,
        assets: List,
        categories: List[str],
        create_backup: bool = True
    ) -> bool:
        """保存本地配置

        Args:
            library_path: 资产库路径
            assets: 资产列表
            categories: 分类列表
            create_backup: 是否创建备份

        Returns:
            bool: 成功返回 True，失败返回 False
        """
        try:
            local_config_path = library_path / self.LOCAL_CONFIG_FILE

            # 创建备份
            if create_backup and local_config_path.exists():
                backup_dir = library_path / self.BACKUP_DIR
                backup_dir.mkdir(parents=True, exist_ok=True)

                import datetime
                timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
                backup_path = backup_dir / f"{self.LOCAL_CONFIG_FILE}.{timestamp}.bak"

                import shutil
                shutil.copy2(local_config_path, backup_path)
                self._logger.info(f"Created backup: {backup_path}")

            # 构建配置数据
            config = {
                "_version": "2.0.0",
                "assets": [self._asset_to_dict(asset) for asset in assets],
                "categories": categories
            }

            # 保存配置
            with open(local_config_path, 'w', encoding='utf-8') as f:
                json.dump(config, f, ensure_ascii=False, indent=2)

            self._logger.info(f"Saved local config to: {local_config_path}")
            return True

        except Exception as e:
            self._logger.error(f"Failed to save local config: {e}")
            return False

    def _asset_to_dict(self, asset) -> Dict[str, Any]:
        """将资产对象转换为字典

        Args:
            asset: 资产对象

        Returns:
            Dict[str, Any]: 资产字典
        """
        pkg_type = getattr(asset, 'package_type', None)
        pkg_type_val = pkg_type.value if hasattr(pkg_type, 'value') else 'content'
        return {
            "id": getattr(asset, 'id', ''),
            "name": getattr(asset, 'name', ''),
            "asset_type": getattr(asset, 'asset_type', '').value if hasattr(getattr(asset, 'asset_type', ''), 'value') else '',
            "path": str(getattr(asset, 'path', '')),
            "category": getattr(asset, 'category', ''),
            "package_type": pkg_type_val,
            "file_extension": getattr(asset, 'file_extension', ''),
            "description": getattr(asset, 'description', ''),
            "thumbnail_path": str(getattr(asset, 'thumbnail_path', '')) if getattr(asset, 'thumbnail_path', None) else '',
            "thumbnail_source": getattr(asset, 'thumbnail_source', ''),
            "size": getattr(asset, 'size', 0),
            "created_time": getattr(asset, 'created_time', '').isoformat() if hasattr(getattr(asset, 'created_time', ''), 'isoformat') else str(getattr(asset, 'created_time', '')),
            "engine_min_version": getattr(asset, 'engine_min_version', ''),
            "project_file": getattr(asset, 'project_file', '')
        }

    def migrate_config(self, old_config: Dict[str, Any]) -> Dict[str, Any]:
        """迁移配置

        Args:
            old_config: 旧配置

        Returns:
            Dict[str, Any]: 新配置
        """
        try:
            # 检查版本
            version = old_config.get("_version", "1.0.0")

            # 如果已包含新格式字段则跳过
            if old_config.get("current_asset_library") is not None or old_config.get("asset_libraries") is not None:
                return old_config

            if version == "2.0.0" and not old_config.get("asset_library_path"):
                return old_config

            # 迁移到新格式
            old_lib = old_config.get("asset_library_path", "")
            new_config = {
                "_version": "2.0.0",
                "current_asset_library": old_lib,
                "asset_libraries": [{"path": old_lib, "name": "主资产库", "last_opened": ""}] if old_lib else [],
                "preview_projects": (old_config.get("additional_preview_projects_with_names")
                                     or old_config.get("preview_projects", [])),
                "last_preview_project": old_config.get("last_preview_project_name", ""),
                "last_target_project": old_config.get("last_target_project_path", ""),
            }

            self._logger.info(f"Migrated config from {version} to new format")
            return new_config

        except Exception as e:
            self._logger.error(f"Failed to migrate config: {e}")
            return old_config

    def get_asset_library_path(self) -> Optional[Path]:
        """获取资产库路径

        Returns:
            Optional[Path]: 资产库路径，未设置返回 None
        """
        try:
            config = self.load_config()
            path_str = config.get("current_asset_library", "") or config.get("asset_library_path", "")
            if path_str:
                return Path(path_str)
            return None
        except Exception as e:
            self._logger.error(f"Failed to get asset library path: {e}")
            return None

    def set_asset_library_path(self, library_path: Path) -> bool:
        """设置资产库路径

        Args:
            library_path: 资产库路径

        Returns:
            bool: 成功返回 True，失败返回 False
        """
        try:
            config = self.load_config()
            config["current_asset_library"] = str(library_path)
            libs = config.setdefault("asset_libraries", [])
            if not any(l.get("path") == str(library_path) for l in libs):
                libs.append({"path": str(library_path), "name": "主资产库", "last_opened": ""})
            result = self._config_manager.save_user_config(config, backup_reason="set_library_path")
            
            # 使缓存失效
            if result:
                self.invalidate_cache()
            
            return result
        except Exception as e:
            self._logger.error(f"Failed to set asset library path: {e}")
            return False

