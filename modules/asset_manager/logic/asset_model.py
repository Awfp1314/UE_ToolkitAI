# -*- coding: utf-8 -*-

"""
资产数据模型
"""

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Optional
from datetime import datetime


class AssetType(Enum):
    """资产类型枚举"""
    PACKAGE = "package"  # A型：资源包（文件夹）
    FILE = "file"        # B型：原始文件（已废弃，保留向后兼容）

    @classmethod
    def _missing_(cls, value):
        """访问废弃枚举值时发出警告"""
        import warnings
        if value == "file":
            warnings.warn(
                "AssetType.FILE 已废弃，请使用 AssetType.PACKAGE",
                DeprecationWarning,
                stacklevel=2,
            )
            return cls.FILE
        return None


class PackageType(Enum):
    """包装类型枚举 - 决定资产的存储结构和预览行为"""
    CONTENT = "content"    # UE 资产包：名称/Content/...
    PROJECT = "project"    # UE 项目：名称/Project/...
    PLUGIN = "plugin"      # UE 插件：名称/Plugins/...
    OTHERS = "others"      # 其他资源：名称/Others/...

    @property
    def display_name(self) -> str:
        """获取中文显示名称"""
        return {
            PackageType.CONTENT: "资产包",
            PackageType.PROJECT: "UE 项目",
            PackageType.PLUGIN: "UE 插件",
            PackageType.OTHERS: "其他资源",
        }.get(self, self.value)

    @property
    def wrapper_folder(self) -> str:
        """获取包装文件夹名称"""
        return {
            PackageType.CONTENT: "Content",
            PackageType.PROJECT: "Project",
            PackageType.PLUGIN: "Plugins",
            PackageType.OTHERS: "Others",
        }.get(self, "Others")


@dataclass
class Asset:
    """资产数据类
    
    Attributes:
        id: 资产唯一标识符
        name: 资产名称
        asset_type: 资产类型（PACKAGE或FILE）
        path: 资产路径
        category: 资产分类
        package_type: 包装类型（content/project/plugin/others）
        file_extension: 文件扩展名（仅FILE类型，已废弃）
        thumbnail_path: 缩略图路径
        thumbnail_source: 缩略图来源（"screenshots" 或 "saved" 或 None）
        size: 文件大小（字节）
        created_time: 创建时间
        description: 资产描述
        engine_min_version: 最低引擎版本
        project_file: .uproject 文件相对路径（仅 PROJECT 类型）
    """
    id: str
    name: str
    asset_type: AssetType
    path: Path
    category: str = "默认分类"
    package_type: PackageType = PackageType.CONTENT
    file_extension: str = ""
    thumbnail_path: Optional[Path] = None
    thumbnail_source: Optional[str] = None
    size: int = 0
    created_time: datetime = field(default_factory=datetime.now)
    description: str = ""
    engine_min_version: str = ""
    project_file: str = ""
    
    def get_display_info(self) -> str:
        """获取显示信息"""
        return f"{self.package_type.display_name} · {self._format_size()}"
    
    def _format_size(self) -> str:
        """格式化文件大小"""
        if self.size < 1024:
            return f"{self.size} B"
        elif self.size < 1024 * 1024:
            return f"{self.size / 1024:.1f} KB"
        elif self.size < 1024 * 1024 * 1024:
            return f"{self.size / (1024 * 1024):.1f} MB"
        else:
            return f"{self.size / (1024 * 1024 * 1024):.2f} GB"

