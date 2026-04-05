# -*- coding: utf-8 -*-

"""
配置工具数据模型

包含配置类型枚举和配置模板数据类
"""

from enum import Enum
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import List, Optional


class ConfigType(Enum):
    """配置类型枚举"""
    PROJECT_SETTINGS = "project_settings"      # 项目设置
    EDITOR_PREFERENCES = "editor_preferences"  # 编辑器偏好

    @property
    def display_name(self) -> str:
        """显示名称"""
        return {
            ConfigType.PROJECT_SETTINGS: "项目设置",
            ConfigType.EDITOR_PREFERENCES: "编辑器偏好"
        }[self]


@dataclass
class ConfigTemplate:
    """配置模板数据类"""
    name: str                      # 配置名称
    description: str               # 配置描述
    type: ConfigType               # 配置类型
    config_version: str            # 配置版本（如 "4.27"）
    source_project: str            # 源项目路径
    created_at: datetime           # 创建时间
    file_count: int                # 文件数量
    total_size: int                # 总大小（字节）
    files: List[str]               # 文件列表（相对路径）
    template_path: Path            # 模板存储路径

    def to_dict(self) -> dict:
        """转换为字典（用于 JSON 序列化）"""
        return {
            "name": self.name,
            "description": self.description,
            "type": self.type.value,
            "config_version": self.config_version,
            "source_project": self.source_project,
            "created_at": self.created_at.isoformat(),
            "file_count": self.file_count,
            "total_size": self.total_size,
            "files": self.files
        }

    @staticmethod
    def from_dict(data: dict, template_path: Path) -> 'ConfigTemplate':
        """从字典创建实例（用于 JSON 反序列化）"""
        return ConfigTemplate(
            name=data["name"],
            description=data.get("description", ""),
            type=ConfigType(data["type"]),
            config_version=data["config_version"],
            source_project=data["source_project"],
            created_at=datetime.fromisoformat(data["created_at"]),
            file_count=data["file_count"],
            total_size=data["total_size"],
            files=data["files"],
            template_path=template_path
        )
