# -*- coding: utf-8 -*-

"""
工程注册表 - 管理已知工程列表

职责：
- 中央注册表（AppData）的加载/保存/备份
- 每个工程目录下 .UeToolkitconfig/ 的创建和管理
"""

import json
import shutil
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any, Optional

from PyQt6.QtCore import QStandardPaths

from core.logger import get_logger

logger = get_logger(__name__)

# 常量
TOOLKIT_CONFIG_DIR = ".UeToolkitconfig"
PROJECT_CONFIG_FILE = "project.json"
REGISTRY_FILE = "registry.json"
BACKUP_DIR = ".backups"
MAX_BACKUPS = 10


class ProjectRegistry:
    """工程注册表管理器"""

    def __init__(self):
        self._registry_dir = self._get_registry_dir()
        self._registry_path = self._registry_dir / REGISTRY_FILE
        self._backup_dir = self._registry_dir / BACKUP_DIR

    @staticmethod
    def _get_registry_dir() -> Path:
        """获取注册表目录（兼容新旧路径）"""
        candidates = []

        app_data = QStandardPaths.writableLocation(
            QStandardPaths.StandardLocation.AppDataLocation
        )
        if app_data:
            app_data_path = Path(app_data)
            # 当前默认路径（Qt 自动使用 APP_NAME = "ue_toolkit"）
            candidates.append(app_data_path / "my_projects")
            # 兼容历史路径（目录名带空格）
            candidates.append(app_data_path / "UE Toolkit" / "ue_toolkit" / "my_projects")
            candidates.append(app_data_path / "UE Toolkit" / "my_projects")

        # Windows 下再追加显式 Roaming 兼容路径
        roaming = Path.home() / "AppData" / "Roaming"
        candidates.append(roaming / "UE Toolkit" / "ue_toolkit" / "my_projects")
        candidates.append(roaming / "ue_toolkit" / "my_projects")

        # 增加项目根目录下的候选路径（针对便携式或特定配置）
        project_root = Path(__file__).parent.parent.parent.parent.parent
        candidates.append(project_root / "Toolkit" / "ue_toolkit" / "my_projects")

        # 优先使用已存在 registry.json 的目录
        for candidate in candidates:
            if (candidate / REGISTRY_FILE).exists():
                return candidate

        # 都不存在时使用默认候选
        return candidates[0]

    # ── 注册表读写 ──

    def load_registry(self) -> Dict[str, Any]:
        """加载注册表，不存在则返回空结构"""
        try:
            if self._registry_path.exists():
                with open(self._registry_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                logger.info(f"加载注册表: {len(data.get('projects', []))} 个工程")
                return data
        except Exception as e:
            logger.error(f"加载注册表失败: {e}", exc_info=True)
        return self._empty_registry()

    def save_registry(self, data: Dict[str, Any]) -> bool:
        """保存注册表（先备份再写入）"""
        try:
            self._registry_dir.mkdir(parents=True, exist_ok=True)

            # 备份现有文件
            if self._registry_path.exists():
                self._create_backup()

            with open(self._registry_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)

            logger.info(f"注册表已保存: {len(data.get('projects', []))} 个工程")
            return True
        except Exception as e:
            logger.error(f"保存注册表失败: {e}", exc_info=True)
            return False

    def has_registry(self) -> bool:
        """注册表文件是否存在"""
        return self._registry_path.exists()

    # ── 工程操作 ──

    def clear_registry(self) -> bool:
        """清理注册表缓存，强制重新扫描（保留分类列表）"""
        try:
            if self._registry_path.exists():
                # 先备份
                self._create_backup()
                
                # 加载现有数据，保留分类列表
                existing_data = self.load_registry()
                existing_categories = existing_data.get("categories", ["默认"])
                
                # 创建新的空注册表，但保留分类
                data = self._empty_registry()
                data["categories"] = existing_categories
                
                # 保存（这会清空工程列表，但保留分类）
                self.save_registry(data)
                logger.info(f"注册表缓存已清理（保留 {len(existing_categories)} 个分类），将强制重新扫描")
                return True
        except Exception as e:
            logger.error(f"清理注册表缓存失败: {e}")
        return False

    def get_projects(self) -> List[Dict[str, Any]]:
        """获取所有已注册工程"""
        return self.load_registry().get("projects", [])

    def add_projects(self, projects: List[Dict[str, Any]]) -> None:
        """添加工程到注册表并创建 .UeToolkitconfig"""
        if not projects:
            return
        data = self.load_registry()
        known_paths = {p["path"] for p in data["projects"]}

        added = 0
        for proj in projects:
            if proj["path"] not in known_paths:
                data["projects"].append(proj)
                known_paths.add(proj["path"])
                self._ensure_toolkit_config(proj)
                added += 1

        if added:
            data["last_updated"] = datetime.now().isoformat()
            self.save_registry(data)
            logger.info(f"新增 {added} 个工程到注册表")

    def remove_project(self, project_path: str) -> None:
        """从注册表移除工程"""
        data = self.load_registry()
        data["projects"] = [
            p for p in data["projects"] if p["path"] != project_path
        ]
        data["last_updated"] = datetime.now().isoformat()
        self.save_registry(data)

    def save_full_scan_result(self, projects: List[Dict[str, Any]]) -> None:
        """首次全量扫描后保存结果"""
        # 加载现有注册表以保留用户创建的分类和工程分类信息
        existing_data = self.load_registry()
        existing_categories = existing_data.get("categories", ["默认"])
        existing_projects = {p["path"]: p for p in existing_data.get("projects", [])}
        
        # 合并扫描结果和现有数据，保留已有工程的分类信息
        merged_projects = []
        for proj in projects:
            proj_path = proj["path"]
            if proj_path in existing_projects:
                # 保留现有工程的分类信息
                existing_proj = existing_projects[proj_path]
                proj["category"] = existing_proj.get("category", proj.get("category", "默认"))
            merged_projects.append(proj)
        
        data = self._empty_registry()
        data["projects"] = merged_projects
        data["categories"] = existing_categories  # 保留现有分类
        data["last_full_scan"] = datetime.now().isoformat()
        data["last_updated"] = datetime.now().isoformat()
        self.save_registry(data)

        # 为每个工程创建 .UeToolkitconfig
        for proj in merged_projects:
            self._ensure_toolkit_config(proj)

    # ── 每个工程的 .UeToolkitconfig ──

    @staticmethod
    def _ensure_toolkit_config(proj: Dict[str, Any]) -> None:
        """确保工程目录下有 .UeToolkitconfig/project.json，并保留现有分类信息"""
        try:
            proj_path = Path(proj["path"])
            if not proj_path.exists():
                return

            config_dir = proj_path / TOOLKIT_CONFIG_DIR
            config_file = config_dir / PROJECT_CONFIG_FILE

            # 如果配置文件已存在，读取并更新（保留现有分类）
            if config_file.exists():
                try:
                    with open(config_file, "r", encoding="utf-8") as f:
                        existing_config = json.load(f)
                    # 只有当工程数据中有明确的分类时才更新，否则保留配置文件中的分类
                    if "category" in proj and proj["category"] != existing_config.get("category"):
                        existing_config["category"] = proj["category"]
                        existing_config["path"] = proj["path"]  # 更新路径（可能改名）
                        with open(config_file, "w", encoding="utf-8") as f:
                            json.dump(existing_config, f, ensure_ascii=False, indent=2)
                except Exception as e:
                    logger.warning(f"更新工程配置失败 {proj.get('path')}: {e}")
                return

            # 配置文件不存在，创建新的
            config_dir.mkdir(parents=True, exist_ok=True)

            config = {
                "_version": "1.0.0",
                "path": proj["path"],
                "category": proj.get("category", "默认"),
                "created": datetime.now().isoformat(),
            }
            with open(config_file, "w", encoding="utf-8") as f:
                json.dump(config, f, ensure_ascii=False, indent=2)

        except Exception as e:
            logger.warning(f"创建工程配置失败 {proj.get('path')}: {e}")

    @staticmethod
    def has_toolkit_config(proj_dir: Path) -> bool:
        """检查工程目录是否已有 .UeToolkitconfig"""
        return (proj_dir / TOOLKIT_CONFIG_DIR / PROJECT_CONFIG_FILE).exists()

    # ── 备份 ──

    def _create_backup(self) -> None:
        """创建注册表备份"""
        try:
            self._backup_dir.mkdir(parents=True, exist_ok=True)
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_path = self._backup_dir / f"{REGISTRY_FILE}.{ts}.bak"
            shutil.copy2(self._registry_path, backup_path)
            self._cleanup_old_backups()
            logger.debug(f"注册表备份: {backup_path}")
        except Exception as e:
            logger.warning(f"创建备份失败: {e}")

    def _cleanup_old_backups(self) -> None:
        """保留最近 MAX_BACKUPS 个备份"""
        try:
            backups = sorted(self._backup_dir.glob("*.bak"), key=lambda p: p.stat().st_mtime)
            for old in backups[:-MAX_BACKUPS]:
                old.unlink()
        except Exception:
            pass

    @staticmethod
    def _empty_registry() -> Dict[str, Any]:
        return {
            "_version": "1.0.0",
            "projects": [],
            "categories": ["默认"],
            "last_full_scan": None,
            "last_updated": None,
        }
