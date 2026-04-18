# -*- coding: utf-8 -*-

"""
配置存储管理器

负责管理配置模板的存储、读取和删除操作。
所有配置模板存储在 %APPDATA%/ue_toolkit/config_templates/ 目录。
"""

import json
import shutil
from pathlib import Path
from typing import List, Optional

from PyQt6.QtCore import QStandardPaths

from core.logger import get_logger
from .config_model import ConfigTemplate, ConfigType
from .utils import validate_path, check_write_permission

logger = get_logger(__name__)


class ConfigStorage:
    """配置存储管理器

    负责管理配置模板的存储、读取和删除操作。
    所有配置模板存储在 %APPDATA%/ue_toolkit/config_templates/ 目录。
    """

    def __init__(self):
        """初始化存储管理器"""
        self.storage_root = self._get_storage_root()
        self.storage_root.mkdir(parents=True, exist_ok=True)
        logger.info(f"配置存储管理器初始化，存储根目录: {self.storage_root}")

    def _get_storage_root(self) -> Path:
        """获取存储根目录

        Returns:
            存储根目录路径
        """
        app_data = QStandardPaths.writableLocation(
            QStandardPaths.StandardLocation.AppDataLocation
        )
        return Path(app_data) / "config_templates"

    def save_template(self, template: ConfigTemplate, source_path: Path) -> bool:
        """保存配置模板

        Args:
            template: 配置模板对象
            source_path: 源项目路径

        Returns:
            是否保存成功
        """
        try:
            # 创建模板目录
            template_dir = self.get_template_path(template.name)
            template_dir.mkdir(parents=True, exist_ok=True)
            logger.info(f"创建模板目录: {template_dir}")
            
            # 安全验证：确保模板目录在存储根目录内
            if not validate_path(template_dir, self.storage_root):
                logger.error(f"路径安全性验证失败: {template_dir} 不在存储根目录内")
                return False
            
            # 检查写入权限
            if not check_write_permission(template_dir):
                logger.error(f"没有写入权限: {template_dir}")
                return False

            # 根据配置类型复制文件
            if template.type == ConfigType.PROJECT_SETTINGS:
                # 复制 Config/ 目录
                source_config_dir = source_path / "Config"
                target_config_dir = template_dir / "Config"
                
                if not source_config_dir.exists():
                    logger.error(f"源配置目录不存在: {source_config_dir}")
                    return False
                
                # 复制整个 Config 目录
                if target_config_dir.exists():
                    shutil.rmtree(target_config_dir)
                shutil.copytree(source_config_dir, target_config_dir)
                logger.info(f"复制配置目录: {source_config_dir} -> {target_config_dir}")

            elif template.type == ConfigType.EDITOR_PREFERENCES:
                # 复制 EditorPerProjectUserSettings.ini 文件
                source_file = source_path / "Saved" / "Config" / "WindowsEditor" / "EditorPerProjectUserSettings.ini"
                
                # 如果 WindowsEditor 不存在，尝试 Windows 目录（UE4）
                if not source_file.exists():
                    source_file = source_path / "Saved" / "Config" / "Windows" / "EditorPerProjectUserSettings.ini"
                
                if not source_file.exists():
                    logger.error(f"编辑器偏好文件不存在: {source_file}")
                    return False
                
                target_file = template_dir / "EditorPerProjectUserSettings.ini"
                shutil.copy2(source_file, target_file)
                logger.info(f"复制编辑器偏好文件: {source_file} -> {target_file}")

            # 保存元数据
            metadata_file = template_dir / "metadata.json"
            with open(metadata_file, 'w', encoding='utf-8') as f:
                json.dump(template.to_dict(), f, ensure_ascii=False, indent=2)
            logger.info(f"保存元数据文件: {metadata_file}")

            return True

        except Exception as e:
            logger.error(f"保存配置模板失败: {e}", exc_info=True)
            return False

    def load_template(self, template_name: str) -> Optional[ConfigTemplate]:
        """加载配置模板

        Args:
            template_name: 模板名称

        Returns:
            配置模板对象，如果不存在则返回 None
        """
        try:
            template_dir = self.get_template_path(template_name)
            metadata_file = template_dir / "metadata.json"

            if not metadata_file.exists():
                logger.warning(f"元数据文件不存在: {metadata_file}")
                return None

            with open(metadata_file, 'r', encoding='utf-8') as f:
                data = json.load(f)

            template = ConfigTemplate.from_dict(data, template_dir)
            logger.info(f"加载配置模板: {template_name}")
            return template

        except Exception as e:
            logger.error(f"加载配置模板失败: {template_name}, 错误: {e}", exc_info=True)
            return None

    def list_templates(self) -> List[ConfigTemplate]:
        """列出所有配置模板

        Returns:
            配置模板列表
        """
        templates = []
        
        try:
            if not self.storage_root.exists():
                logger.info("存储根目录不存在，返回空列表")
                return templates

            for template_dir in self.storage_root.iterdir():
                if template_dir.is_dir():
                    template = self.load_template(template_dir.name)
                    if template:
                        templates.append(template)

            logger.info(f"列出配置模板，共 {len(templates)} 个")
            return templates

        except Exception as e:
            logger.error(f"列出配置模板失败: {e}", exc_info=True)
            return templates

    def delete_template(self, template_name: str) -> bool:
        """删除配置模板

        Args:
            template_name: 模板名称

        Returns:
            是否删除成功
        """
        try:
            template_dir = self.get_template_path(template_name)

            if not template_dir.exists():
                logger.warning(f"模板目录不存在: {template_dir}")
                return False

            shutil.rmtree(template_dir)
            logger.info(f"删除配置模板: {template_name}")
            return True

        except Exception as e:
            logger.error(f"删除配置模板失败: {template_name}, 错误: {e}", exc_info=True)
            return False

    def get_template_path(self, template_name: str) -> Path:
        """获取模板存储路径

        Args:
            template_name: 模板名称

        Returns:
            模板目录路径
        """
        return self.storage_root / template_name
