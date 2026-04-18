# -*- coding: utf-8 -*-

"""
配置迁移管理器
负责从旧版本配置平滑迁移到新版本，确保零数据丢失
"""

import json
import shutil
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, List, Optional

from PyQt6.QtCore import QStandardPaths

from core.logger import get_logger

logger = get_logger(__name__)


class ConfigMigrationManager:
    """配置迁移管理器 - 负责从旧版本配置平滑迁移到新版本"""
    
    # 当前目标迁移版本
    TARGET_MIGRATION_VERSION = "3.0.0"
    
    def __init__(self):
        """初始化迁移管理器"""
        app_data = QStandardPaths.writableLocation(
            QStandardPaths.StandardLocation.AppDataLocation
        )
        self.config_dir = Path(app_data) / "user_data" / "configs"
        self.backup_dir = self.config_dir / ".migration_backups"
        self.migration_marker_path = self.config_dir / ".migration_marker.json"
    
    def migrate_all_configs(self) -> bool:
        """迁移所有配置（程序启动时调用）
        
        Returns:
            bool: 迁移成功返回 True
        """
        try:
            # 1. 检查是否需要迁移
            if not self._needs_migration():
                logger.info("配置已是最新版本，无需迁移")
                return True
            
            logger.info(f"开始配置迁移，目标版本: {self.TARGET_MIGRATION_VERSION}")
            
            # 2. 创建备份
            backup_path = self._create_backup()
            if not backup_path:
                logger.error("创建备份失败，取消迁移")
                return False
            
            logger.info(f"配置备份已创建: {backup_path}")
            
            # 3. 迁移各个模块
            try:
                self._migrate_asset_manager_config()
                self._migrate_app_config()
            except Exception as e:
                logger.error(f"配置迁移过程中出错: {e}", exc_info=True)
                self._rollback_from_backup(backup_path)
                return False
            
            # 4. 标记迁移完成
            self._mark_migration_complete()
            
            logger.info("✅ 配置迁移完成")
            return True
            
        except Exception as e:
            logger.error(f"配置迁移失败: {e}", exc_info=True)
            return False
    
    def _needs_migration(self) -> bool:
        """检查是否需要迁移
        
        Returns:
            bool: 需要迁移返回 True
        """
        # 检查迁移标记文件
        if not self.migration_marker_path.exists():
            logger.info("未找到迁移标记，需要迁移")
            return True
        
        try:
            with open(self.migration_marker_path, 'r', encoding='utf-8') as f:
                marker = json.load(f)
            
            current_version = marker.get("migration_version", "0.0.0")
            if current_version != self.TARGET_MIGRATION_VERSION:
                logger.info(f"配置版本 {current_version} != {self.TARGET_MIGRATION_VERSION}，需要迁移")
                return True
            
            return False
            
        except Exception as e:
            logger.warning(f"读取迁移标记失败: {e}，假定需要迁移")
            return True
    
    def _create_backup(self) -> Optional[Path]:
        """创建配置备份
        
        Returns:
            Path: 备份目录路径，失败返回 None
        """
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_path = self.backup_dir / timestamp
            backup_path.mkdir(parents=True, exist_ok=True)
            
            # 备份所有配置文件
            config_files = [
                self.config_dir / "asset_manager" / "asset_manager_config.json",
                self.config_dir / "ai_assistant" / "ai_assistant_config.json",
                self.config_dir / "my_projects" / "registry.json",
            ]
            
            for config_file in config_files:
                if config_file.exists():
                    relative_path = config_file.relative_to(self.config_dir)
                    backup_file = backup_path / relative_path
                    backup_file.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(config_file, backup_file)
                    logger.debug(f"已备份: {relative_path}")
            
            # 写入备份日志
            log_file = backup_path / "migration.log"
            with open(log_file, 'w', encoding='utf-8') as f:
                f.write(f"备份时间: {datetime.now().isoformat()}\n")
                f.write(f"目标迁移版本: {self.TARGET_MIGRATION_VERSION}\n")
            
            return backup_path
            
        except Exception as e:
            logger.error(f"创建备份失败: {e}", exc_info=True)
            return None
    
    def _rollback_from_backup(self, backup_path: Path) -> bool:
        """从备份回滚配置
        
        Args:
            backup_path: 备份目录路径
            
        Returns:
            bool: 回滚成功返回 True
        """
        try:
            logger.warning(f"开始回滚配置，使用备份: {backup_path}")
            
            # 恢复所有备份文件
            for backup_file in backup_path.rglob("*.json"):
                if backup_file.name == "migration.log":
                    continue
                
                relative_path = backup_file.relative_to(backup_path)
                target_file = self.config_dir / relative_path
                target_file.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(backup_file, target_file)
                logger.debug(f"已恢复: {relative_path}")
            
            logger.info("✅ 配置已从备份恢复")
            return True
            
        except Exception as e:
            logger.error(f"回滚配置失败: {e}", exc_info=True)
            return False
    
    def _migrate_asset_manager_config(self) -> None:
        """迁移资产管理器配置"""
        logger.info("开始迁移资产管理器配置")
        
        config_path = self.config_dir / "asset_manager" / "asset_manager_config.json"
        
        if not config_path.exists():
            logger.info("资产管理器配置文件不存在，跳过迁移")
            return
        
        # 读取旧配置
        with open(config_path, 'r', encoding='utf-8') as f:
            old_config = json.load(f)
        
        version = old_config.get("_version", "1.0.0")
        
        # 如果已经是3.0.0，跳过
        if version == "3.0.0":
            logger.info("资产管理器配置已是最新版本")
            return
        
        logger.info(f"迁移资产管理器配置: {version} -> 3.0.0")
        
        # ── 1. 提取数据 ──
        asset_library_path = old_config.get("asset_library_path", "")
        preview_projects = old_config.get("additional_preview_projects_with_names", [])
        last_preview = old_config.get("last_preview_project_name", "")
        last_target = old_config.get("last_target_project_path", "")
        view_mode = old_config.get("view_mode", "detailed")
        categories = old_config.get("categories", ["默认分类"])
        assets = old_config.get("assets", [])
        
        # ── 2. 创建新的资产管理器配置 ──
        new_asset_config = {
            "_version": "3.0.0",
            "asset_libraries": [],
            "current_asset_library": asset_library_path,
            "preview_projects": preview_projects,
            "last_preview_project": last_preview,
            "last_target_project": last_target
        }
        
        # 添加资产库
        if asset_library_path:
            new_asset_config["asset_libraries"].append({
                "path": asset_library_path,
                "name": "主资产库",
                "last_opened": datetime.now().isoformat()
            })
        
        # ── 3. 保存新配置 ──
        with open(config_path, 'w', encoding='utf-8') as f:
            json.dump(new_asset_config, f, ensure_ascii=False, indent=2)
        
        logger.info("✅ 资产管理器配置文件已更新")
        
        # ── 4. 迁移资产数据到本地配置 ──
        if asset_library_path and Path(asset_library_path).exists():
            self._migrate_assets_to_local(asset_library_path, categories, assets)
        
        # ── 5. 迁移UI状态到app_config ──
        self._save_ui_state_to_app_config("asset_manager", {
            "view_mode": view_mode,
            "selected_category": "全部分类",
            "sort_method": "添加时间（最新）",
            "scroll_position": 0
        })
        
        logger.info("✅ 资产管理器配置迁移完成")
    
    def _migrate_assets_to_local(self, library_path: str, categories: List[str], assets: List[Dict]) -> None:
        """将资产数据迁移到本地配置
        
        Args:
            library_path: 资产库路径
            categories: 分类列表
            assets: 资产列表
        """
        local_config_dir = Path(library_path) / ".asset_config"
        local_config_path = local_config_dir / "config.json"
        
        # 如果本地配置已存在，不覆盖
        if local_config_path.exists():
            logger.info(f"本地配置已存在，跳过迁移: {local_config_path}")
            return
        
        try:
            # 创建目录
            local_config_dir.mkdir(parents=True, exist_ok=True)
            
            # 写入本地配置
            local_config = {
                "_version": "2.0.0",
                "categories": categories,
                "assets": assets
            }
            
            with open(local_config_path, 'w', encoding='utf-8') as f:
                json.dump(local_config, f, ensure_ascii=False, indent=2)
            
            logger.info(f"✅ 资产数据已迁移到本地配置: {local_config_path}")
            
        except Exception as e:
            logger.warning(f"迁移资产数据到本地配置失败: {e}")
    
    def _migrate_app_config(self) -> None:
        """创建全局应用配置（如果不存在）"""
        app_config_path = self.config_dir / "app_config.json"
        
        # 如果已存在，只更新缺失的字段
        if app_config_path.exists():
            logger.info("全局应用配置已存在，检查并更新")
            self._update_existing_app_config(app_config_path)
            return
        
        logger.info("创建全局应用配置")
        
        # 创建默认配置
        app_config = {
            "_version": "1.0.0",
            "app_settings": {
                "theme": "dark",
                "language": "zh_CN",
                "auto_start": False,
                "desktop_floating_window": False,
                "check_updates_on_startup": True,
                "first_launch": False
            },
            "window_state": {
                "position": {"x": -1, "y": -1},
                "size": {"width": 1280, "height": 800},
                "maximized": False
            },
            "module_state": {
                "current_module": "asset_manager",
                "last_active_modules": ["asset_manager"]
            },
            "ui_states": {}
        }
        
        # 确保目录存在
        app_config_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(app_config_path, 'w', encoding='utf-8') as f:
            json.dump(app_config, f, ensure_ascii=False, indent=2)
        
        logger.info("✅ 全局应用配置创建完成")
    
    def _update_existing_app_config(self, config_path: Path) -> None:
        """更新现有的app_config，确保所有必需字段存在
        
        Args:
            config_path: 配置文件路径
        """
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
            
            updated = False
            
            # 确保 ui_states 存在
            if "ui_states" not in config:
                config["ui_states"] = {}
                updated = True
            
            # 确保 module_state 存在
            if "module_state" not in config:
                config["module_state"] = {
                    "current_module": "asset_manager",
                    "last_active_modules": ["asset_manager"]
                }
                updated = True
            
            if updated:
                with open(config_path, 'w', encoding='utf-8') as f:
                    json.dump(config, f, ensure_ascii=False, indent=2)
                logger.info("✅ 全局应用配置已更新")
            
        except Exception as e:
            logger.warning(f"更新全局应用配置失败: {e}")
    
    def _save_ui_state_to_app_config(self, module_name: str, ui_state: Dict[str, Any]) -> None:
        """保存UI状态到app_config
        
        Args:
            module_name: 模块名称
            ui_state: UI状态字典
        """
        app_config_path = self.config_dir / "app_config.json"
        
        try:
            # 读取或创建app_config
            if app_config_path.exists():
                with open(app_config_path, 'r', encoding='utf-8') as f:
                    app_config = json.load(f)
            else:
                app_config = {
                    "_version": "1.0.0",
                    "ui_states": {}
                }
            
            # 更新UI状态
            if "ui_states" not in app_config:
                app_config["ui_states"] = {}
            
            app_config["ui_states"][module_name] = ui_state
            
            # 保存
            app_config_path.parent.mkdir(parents=True, exist_ok=True)
            with open(app_config_path, 'w', encoding='utf-8') as f:
                json.dump(app_config, f, ensure_ascii=False, indent=2)
            
            logger.debug(f"已保存 {module_name} 的UI状态到app_config")
            
        except Exception as e:
            logger.warning(f"保存UI状态到app_config失败: {e}")
    
    def _mark_migration_complete(self) -> None:
        """标记迁移完成"""
        try:
            marker = {
                "migration_version": self.TARGET_MIGRATION_VERSION,
                "last_migration_date": datetime.now().isoformat()
            }
            
            self.migration_marker_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.migration_marker_path, 'w', encoding='utf-8') as f:
                json.dump(marker, f, ensure_ascii=False, indent=2)
            
            logger.info(f"已标记迁移完成: {self.TARGET_MIGRATION_VERSION}")
            
        except Exception as e:
            logger.warning(f"标记迁移完成失败: {e}")
