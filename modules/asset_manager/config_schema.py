# -*- coding: utf-8 -*-

"""
资产管理器配置模式定义
定义配置文件中合法的字段和验证规则
"""

from core.config.config_validator import ConfigSchema


def get_asset_manager_schema() -> ConfigSchema:
    """获取资产管理器的配置模式定义
    
    Returns:
        ConfigSchema: 配置模式
    """
    return ConfigSchema(
        required_fields={
            "_version"  # 配置版本号（必需）
        },
        optional_fields={
            # ── 新格式字段 ──
            "asset_libraries",              # 资产库列表 [{path, name, last_opened}]
            "current_asset_library",        # 当前激活的资产库路径
            "preview_projects",             # 预览工程列表 [{path, name}]
            "last_preview_project",         # 最后使用的预览工程名称
            "last_target_project",          # 最后使用的目标工程路径

            # ── 旧格式字段（向后兼容，迁移时读取）──
            "asset_library_path",
            "asset_library_configs",
            "assets",
            "categories",
            "preview_project_path",
            "additional_preview_projects_with_names",
            "last_preview_project_name",
            "last_target_project_path",
            "view_mode"
        },
        field_types={
            "_version": str,
            "asset_libraries": list,
            "current_asset_library": str,
            "preview_projects": list,
            "last_preview_project": str,
            "last_target_project": str,
            "asset_library_path": str,
            "asset_library_configs": dict,
            "assets": list,
            "categories": list,
            "preview_project_path": str,
            "additional_preview_projects_with_names": list,
            "last_preview_project_name": str,
            "last_target_project_path": str,
            "view_mode": str
        },
        allow_unknown_fields=True,
        strict_mode=False
    )
