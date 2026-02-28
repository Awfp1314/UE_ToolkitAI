# -*- coding: utf-8 -*-

"""
工程创建器 - 从模板创建 UE 工程
"""

import json
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Optional

from core.logger import get_logger

logger = get_logger(__name__)

# 最小 .uproject 模板
_BLANK_UPROJECT = {
    "FileVersion": 3,
    "EngineAssociation": "",
    "Category": "",
    "Description": "",
}

# C++ 模块模板
_MODULE_HEADER = '''#pragma once

#include "CoreMinimal.h"

'''

_MODULE_SOURCE = '''#include "{module_name}.h"
#include "Modules/ModuleManager.h"

IMPLEMENT_PRIMARY_GAME_MODULE(FDefaultGameModuleImpl, {module_name}, "{module_name}");
'''

_BUILD_CS = '''using UnrealBuildTool;

public class {module_name} : ModuleRules
{{
    public {module_name}(ReadOnlyTargetRules Target) : base(Target)
    {{
        PCHUsage = PCHUsageMode.UseExplicitOrSharedPCHs;
        PublicDependencyModuleNames.AddRange(new string[] {{ "Core", "CoreUObject", "Engine", "InputCore" }});
    }}
}}
'''

_TARGET_CS = '''using UnrealBuildTool;
using System.Collections.Generic;

public class {module_name}Target : TargetRules
{{
    public {module_name}Target(TargetInfo Target) : base(Target)
    {{
        Type = TargetType.Game;
        DefaultBuildSettings = BuildSettingsVersion.V4;
        IncludeOrderVersion = EngineIncludeOrderVersion.Unreal5_4;
        ExtraModuleNames.Add("{module_name}");
    }}
}}
'''

_EDITOR_TARGET_CS = '''using UnrealBuildTool;
using System.Collections.Generic;

public class {module_name}EditorTarget : TargetRules
{{
    public {module_name}EditorTarget(TargetInfo Target) : base(Target)
    {{
        Type = TargetType.Editor;
        DefaultBuildSettings = BuildSettingsVersion.V4;
        IncludeOrderVersion = EngineIncludeOrderVersion.Unreal5_4;
        ExtraModuleNames.Add("{module_name}");
    }}
}}
'''


class ProjectCreator:
    """UE 工程创建器"""

    @staticmethod
    def create_project(
        project_name: str,
        project_path: Path,
        engine_version: str,
        template_path: Optional[Path] = None,
        is_cpp: bool = False,
        include_starter_content: bool = False,
        starter_content_path: Optional[Path] = None,
    ) -> Optional[Path]:
        """创建 UE 工程

        Args:
            project_name: 工程名称
            project_path: 工程父目录
            engine_version: 引擎版本号
            template_path: 模板路径（None 则创建空白工程）
            is_cpp: 是否为 C++ 工程
            include_starter_content: 是否包含初学者内容包
            starter_content_path: 初学者内容包路径

        Returns:
            创建的 .uproject 文件路径，失败返回 None
        """
        target_dir = project_path / project_name

        try:
            if target_dir.exists():
                logger.error(f"目标目录已存在: {target_dir}")
                return None

            if template_path and template_path.exists():
                # 从模板复制
                shutil.copytree(template_path, target_dir)
                logger.info(f"已复制模板: {template_path} → {target_dir}")

                # 重命名 .uproject 文件
                uproject_file = ProjectCreator._rename_uproject(target_dir, project_name)
            else:
                # 创建空白工程
                uproject_file = ProjectCreator._create_blank(target_dir, project_name)

            if not uproject_file:
                return None

            # 更新 EngineAssociation
            ProjectCreator._update_engine_association(uproject_file, engine_version)

            # C++ 工程：生成 Source 文件
            if is_cpp:
                ProjectCreator._setup_cpp_module(target_dir, project_name, uproject_file)

            # 初学者内容包
            if include_starter_content and starter_content_path and starter_content_path.exists():
                ProjectCreator._add_starter_content(target_dir, starter_content_path)

            logger.info(f"工程创建成功: {uproject_file}")
            return uproject_file

        except Exception as e:
            logger.error(f"创建工程失败: {e}", exc_info=True)
            # 清理失败的目录
            if target_dir.exists():
                try:
                    shutil.rmtree(target_dir)
                except Exception:
                    pass
            return None

    @staticmethod
    def open_project(editor_path: Path, uproject_path: Path) -> bool:
        """用 UE 编辑器打开工程"""
        try:
            subprocess.Popen([str(editor_path), str(uproject_path)])
            logger.info(f"已启动编辑器: {editor_path} {uproject_path}")
            return True
        except Exception as e:
            logger.error(f"启动编辑器失败: {e}")
            return False

    # ── 内部方法 ──

    @staticmethod
    def _create_blank(target_dir: Path, project_name: str) -> Optional[Path]:
        """创建空白工程"""
        try:
            target_dir.mkdir(parents=True, exist_ok=True)
            (target_dir / "Content").mkdir(exist_ok=True)
            (target_dir / "Config").mkdir(exist_ok=True)

            # 创建 DefaultEngine.ini
            engine_ini = target_dir / "Config" / "DefaultEngine.ini"
            engine_ini.write_text("[/Script/EngineSettings.GameMapsSettings]\n", encoding="utf-8")

            # 创建 DefaultGame.ini
            game_ini = target_dir / "Config" / "DefaultGame.ini"
            game_ini.write_text(f"[/Script/EngineSettings.GeneralProjectSettings]\nProjectID=\nProjectName={project_name}\n", encoding="utf-8")

            # 创建 .uproject
            uproject_path = target_dir / f"{project_name}.uproject"
            data = dict(_BLANK_UPROJECT)
            with open(uproject_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent="\t")

            return uproject_path
        except Exception as e:
            logger.error(f"创建空白工程失败: {e}")
            return None

    @staticmethod
    def _rename_uproject(target_dir: Path, project_name: str) -> Optional[Path]:
        """重命名模板的 .uproject 文件"""
        uprojects = list(target_dir.glob("*.uproject"))
        if not uprojects:
            logger.error(f"模板中未找到 .uproject 文件: {target_dir}")
            return None

        old_path = uprojects[0]
        new_path = target_dir / f"{project_name}.uproject"

        if old_path != new_path:
            old_path.rename(new_path)

        return new_path

    @staticmethod
    def _update_engine_association(uproject_path: Path, version: str) -> None:
        """更新 .uproject 中的 EngineAssociation"""
        try:
            with open(uproject_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            data["EngineAssociation"] = version
            with open(uproject_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent="\t")
        except Exception as e:
            logger.error(f"更新 EngineAssociation 失败: {e}")

    @staticmethod
    def _setup_cpp_module(target_dir: Path, project_name: str, uproject_path: Path) -> None:
        """设置 C++ 模块"""
        module_name = project_name.replace(" ", "").replace("-", "_")
        source_dir = target_dir / "Source" / module_name

        try:
            source_dir.mkdir(parents=True, exist_ok=True)

            # 头文件
            (source_dir / f"{module_name}.h").write_text(
                _MODULE_HEADER, encoding="utf-8"
            )
            # 源文件
            (source_dir / f"{module_name}.cpp").write_text(
                _MODULE_SOURCE.format(module_name=module_name), encoding="utf-8"
            )
            # Build.cs
            (source_dir / f"{module_name}.Build.cs").write_text(
                _BUILD_CS.format(module_name=module_name), encoding="utf-8"
            )
            # Target.cs
            (target_dir / "Source" / f"{module_name}.Target.cs").write_text(
                _TARGET_CS.format(module_name=module_name), encoding="utf-8"
            )
            # Editor Target.cs
            (target_dir / "Source" / f"{module_name}Editor.Target.cs").write_text(
                _EDITOR_TARGET_CS.format(module_name=module_name), encoding="utf-8"
            )

            # 更新 .uproject 添加模块
            with open(uproject_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            data["Modules"] = [{
                "Name": module_name,
                "Type": "Runtime",
                "LoadingPhase": "Default"
            }]
            with open(uproject_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent="\t")

            logger.info(f"C++ 模块已创建: {module_name}")
        except Exception as e:
            logger.error(f"创建 C++ 模块失败: {e}")

    @staticmethod
    def _add_starter_content(target_dir: Path, starter_content_path: Path) -> None:
        """添加初学者内容包"""
        try:
            packs_dir = target_dir / "Content" / "Packs"
            packs_dir.mkdir(parents=True, exist_ok=True)
            dest = packs_dir / starter_content_path.name
            shutil.copy2(starter_content_path, dest)
            logger.info(f"已添加初学者内容包: {dest}")
        except Exception as e:
            logger.error(f"添加初学者内容包失败: {e}")
