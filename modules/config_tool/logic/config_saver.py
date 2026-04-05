# -*- coding: utf-8 -*-

"""
配置保存器

负责从源项目提取配置并保存为模板。
"""

import json
import re
from pathlib import Path
from typing import List, Tuple
from datetime import datetime

from core.logger import get_logger
from .config_model import ConfigTemplate, ConfigType
from .config_storage import ConfigStorage

logger = get_logger(__name__)


class ConfigSaver:
    """配置保存器

    负责从源项目提取配置并保存为模板。
    """

    def __init__(self, storage: ConfigStorage):
        """初始化配置保存器

        Args:
            storage: 配置存储管理器
        """
        self.storage = storage
        logger.info("配置保存器初始化完成")

    def validate_config(self, project_path: Path, config_type: ConfigType) -> Tuple[bool, str]:
        """验证配置有效性

        Args:
            project_path: 项目路径
            config_type: 配置类型

        Returns:
            (是否有效, 错误消息)
        """
        try:
            if config_type == ConfigType.PROJECT_SETTINGS:
                # 验证 Config/ 目录
                config_dir = project_path / "Config"
                
                if not config_dir.exists():
                    return False, "Config 目录不存在"
                
                # 检查是否有自定义内容（至少有一个 .ini 文件）
                ini_files = list(config_dir.glob("*.ini"))
                if not ini_files:
                    return False, "Config 目录没有自定义内容"
                
                logger.info(f"项目设置配置验证通过，找到 {len(ini_files)} 个配置文件")
                return True, ""

            elif config_type == ConfigType.EDITOR_PREFERENCES:
                # 验证 EditorPerProjectUserSettings.ini 文件
                # 尝试 WindowsEditor 目录（UE5）
                editor_prefs = project_path / "Saved" / "Config" / "WindowsEditor" / "EditorPerProjectUserSettings.ini"
                
                # 如果不存在，尝试 Windows 目录（UE4）
                if not editor_prefs.exists():
                    editor_prefs = project_path / "Saved" / "Config" / "Windows" / "EditorPerProjectUserSettings.ini"
                
                if not editor_prefs.exists():
                    return False, "编辑器偏好设置文件不存在"
                
                logger.info(f"编辑器偏好配置验证通过: {editor_prefs}")
                return True, ""

            return False, "未知的配置类型"

        except Exception as e:
            logger.error(f"验证配置时发生错误: {e}", exc_info=True)
            return False, f"验证配置时发生错误: {str(e)}"

    def save_config(
        self,
        name: str,
        description: str,
        config_type: ConfigType,
        source_project: Path
    ) -> Tuple[bool, str]:
        """保存配置模板

        Args:
            name: 配置名称
            description: 配置描述
            config_type: 配置类型
            source_project: 源项目路径

        Returns:
            (是否成功, 消息)
        """
        try:
            # 验证配置名称
            is_valid, error_msg = self._validate_config_name(name)
            if not is_valid:
                return False, error_msg

            # 验证配置有效性
            is_valid, error_msg = self.validate_config(source_project, config_type)
            if not is_valid:
                return False, error_msg

            # 获取引擎版本
            config_version = self._get_engine_version(source_project)
            if not config_version:
                return False, "无法获取引擎版本"

            # 提取配置文件
            if config_type == ConfigType.PROJECT_SETTINGS:
                files = self._extract_project_settings(source_project)
            else:
                files = self._extract_editor_preferences(source_project)

            if not files:
                return False, "没有找到配置文件"

            # 计算文件统计信息
            file_count = len(files)
            total_size = sum(f.stat().st_size for f in files if f.exists())

            # 创建配置模板对象
            template = ConfigTemplate(
                name=name,
                description=description,
                type=config_type,
                config_version=config_version,
                source_project=str(source_project),
                created_at=datetime.now(),
                file_count=file_count,
                total_size=total_size,
                files=[str(f.relative_to(source_project)) for f in files],
                template_path=self.storage.get_template_path(name)
            )

            # 保存模板
            success = self.storage.save_template(template, source_project)
            if success:
                logger.info(
                    f"配置保存成功: name={name}, type={config_type.display_name}, "
                    f"source={source_project}, version={config_version}, "
                    f"files={file_count}, size={total_size}"
                )
                return True, "配置保存成功"
            else:
                return False, "保存配置失败"

        except Exception as e:
            logger.error(f"保存配置时发生错误: {e}", exc_info=True)
            return False, f"保存配置时发生错误: {str(e)}"

    def _extract_project_settings(self, project_path: Path) -> List[Path]:
        """提取项目设置配置文件

        Args:
            project_path: 项目路径

        Returns:
            配置文件路径列表
        """
        config_dir = project_path / "Config"
        if not config_dir.exists():
            return []

        # 获取所有 .ini 文件
        ini_files = list(config_dir.glob("*.ini"))
        logger.info(f"提取项目设置配置文件，共 {len(ini_files)} 个")
        return ini_files

    def _extract_editor_preferences(self, project_path: Path) -> List[Path]:
        """提取编辑器偏好配置文件

        Args:
            project_path: 项目路径

        Returns:
            配置文件路径列表
        """
        # 尝试 WindowsEditor 目录（UE5）
        editor_prefs = project_path / "Saved" / "Config" / "WindowsEditor" / "EditorPerProjectUserSettings.ini"
        
        # 如果不存在，尝试 Windows 目录（UE4）
        if not editor_prefs.exists():
            editor_prefs = project_path / "Saved" / "Config" / "Windows" / "EditorPerProjectUserSettings.ini"
        
        if editor_prefs.exists():
            logger.info(f"提取编辑器偏好配置文件: {editor_prefs}")
            return [editor_prefs]
        
        return []

    def _validate_config_name(self, name: str) -> Tuple[bool, str]:
        """验证配置名称

        Args:
            name: 配置名称

        Returns:
            (是否有效, 错误消息)
        """
        if not name or not name.strip():
            return False, "配置名称不能为空"

        if len(name) > 100:
            return False, "配置名称不能超过 100 个字符"

        # 检查非法字符
        invalid_chars = '<>:"/\\|?*'
        if any(c in name for c in invalid_chars):
            return False, f"配置名称不能包含以下字符: {invalid_chars}"

        return True, ""

    def _get_engine_version(self, project_path: Path) -> str:
        """获取引擎版本

        Args:
            project_path: 项目路径

        Returns:
            引擎版本字符串（如 "4.27"），如果无法获取则返回空字符串
        """
        try:
            # 查找 .uproject 文件
            uproject_files = list(project_path.glob("*.uproject"))
            if not uproject_files:
                logger.warning(f"未找到 .uproject 文件: {project_path}")
                return ""

            uproject_file = uproject_files[0]
            with open(uproject_file, 'r', encoding='utf-8') as f:
                data = json.load(f)

            engine_association = data.get('EngineAssociation', '')
            
            # 解析版本号
            # 可能的格式: "4.27", "5.0", "{GUID}", "4.27.2"
            if re.match(r'^\d+\.\d+', engine_association):
                # 提取主版本号和次版本号
                match = re.match(r'^(\d+\.\d+)', engine_association)
                if match:
                    version = match.group(1)
                    logger.info(f"获取引擎版本: {version}")
                    return version

            logger.warning(f"无法解析引擎版本: {engine_association}")
            return ""

        except Exception as e:
            logger.error(f"获取引擎版本时发生错误: {e}", exc_info=True)
            return ""
