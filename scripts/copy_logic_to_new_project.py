#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
将现有项目的逻辑和框架复制到新项目目录（不复制 UI）

目标：
- 复制 core/ 目录（完整）
- 复制 modules/ 目录（仅 logic/ 和配置文件）
- 复制 resources/ 目录（仅配置和模板，不复制 QSS）
- 复制 main.py（作为参考）
- 复制配置文件（requirements.txt, README.md, LICENSE）
- 复制 scripts/ 和 tools/（工具脚本）
- 复制 tests/（测试文件）
- 不复制 ui/ 目录
- 不复制 resources/qss/ 和 resources/themes/（UI 样式）
"""

import os
import shutil
from pathlib import Path
from typing import List, Set

# 项目根目录
PROJECT_ROOT = Path(__file__).parent.parent
TARGET_DIR = PROJECT_ROOT / "UE_TOOKITS_AI_NEW"

# 需要完整复制的目录
FULL_COPY_DIRS = [
    "core",
    "scripts",
    "tools",
    "tests",
    "docs",
]

# 需要部分复制的目录（自定义规则）
PARTIAL_COPY_DIRS = [
    "modules",
    "resources",
]

# 需要复制的根目录文件
ROOT_FILES = [
    "main.py",
    "requirements.txt",
    "README.md",
    "LICENSE",
    "ue_toolkit.spec",
]

# 需要排除的文件/目录（全局）
EXCLUDE_PATTERNS = {
    "__pycache__",
    "*.pyc",
    "*.pyo",
    ".pytest_cache",
    ".mypy_cache",
    ".DS_Store",
    "Thumbs.db",
}


def should_exclude(path: Path) -> bool:
    """检查路径是否应该被排除"""
    for pattern in EXCLUDE_PATTERNS:
        if pattern.startswith("*"):
            if path.name.endswith(pattern[1:]):
                return True
        elif path.name == pattern:
            return True
    return False


def copy_full_directory(src: Path, dst: Path):
    """完整复制目录（排除特定模式）"""
    print(f"📁 完整复制: {src.name}/")
    
    if dst.exists():
        shutil.rmtree(dst)
    
    def ignore_patterns(directory, files):
        ignored = []
        for file in files:
            file_path = Path(directory) / file
            if should_exclude(file_path):
                ignored.append(file)
        return ignored
    
    shutil.copytree(src, dst, ignore=ignore_patterns)
    print(f"   ✅ 已复制到: {dst.relative_to(TARGET_DIR)}/")


def copy_modules_directory(src: Path, dst: Path):
    """复制 modules/ 目录（仅 logic/ 和配置文件）"""
    print(f"📁 部分复制: modules/ (仅 logic 层)")
    
    dst.mkdir(parents=True, exist_ok=True)
    
    # 复制 modules/README.md
    if (src / "README.md").exists():
        shutil.copy2(src / "README.md", dst / "README.md")
        print(f"   ✅ README.md")
    
    # 复制 modules/_template/
    if (src / "_template").exists():
        copy_full_directory(src / "_template", dst / "_template")
    
    # 遍历所有模块
    for module_dir in src.iterdir():
        if not module_dir.is_dir() or module_dir.name.startswith("_"):
            continue
        
        module_name = module_dir.name
        target_module_dir = dst / module_name
        target_module_dir.mkdir(parents=True, exist_ok=True)
        
        print(f"   📦 {module_name}/")
        
        # 复制模块根目录文件
        for file in module_dir.iterdir():
            if file.is_file() and not should_exclude(file):
                shutil.copy2(file, target_module_dir / file.name)
                print(f"      ✅ {file.name}")
        
        # 复制 logic/ 目录（完整）
        logic_dir = module_dir / "logic"
        if logic_dir.exists():
            target_logic_dir = target_module_dir / "logic"
            copy_full_directory(logic_dir, target_logic_dir)
        
        # 复制 resources/ 目录（如果有）
        resources_dir = module_dir / "resources"
        if resources_dir.exists():
            target_resources_dir = target_module_dir / "resources"
            copy_full_directory(resources_dir, target_resources_dir)
        
        # 不复制 ui/ 目录
        ui_dir = module_dir / "ui"
        if ui_dir.exists():
            print(f"      ⏭️  跳过 ui/ (将在新项目中重做)")


def copy_resources_directory(src: Path, dst: Path):
    """复制 resources/ 目录（不复制 QSS 和主题）"""
    print(f"📁 部分复制: resources/ (不复制 UI 样式)")
    
    dst.mkdir(parents=True, exist_ok=True)
    
    # 复制 README.md
    if (src / "README.md").exists():
        shutil.copy2(src / "README.md", dst / "README.md")
        print(f"   ✅ README.md")
    
    # 复制 templates/ 目录
    if (src / "templates").exists():
        copy_full_directory(src / "templates", dst / "templates")
    
    # 复制图标文件
    if (src / "tubiao.ico").exists():
        shutil.copy2(src / "tubiao.ico", dst / "tubiao.ico")
        print(f"   ✅ tubiao.ico")
    
    # 不复制 qss/ 和 themes/
    print(f"   ⏭️  跳过 qss/ (UI 样式)")
    print(f"   ⏭️  跳过 themes/ (UI 主题)")


def main():
    """主函数"""
    print("=" * 60)
    print("🚀 开始复制项目逻辑和框架到新目录")
    print("=" * 60)
    print(f"源目录: {PROJECT_ROOT}")
    print(f"目标目录: {TARGET_DIR}")
    print()
    
    # 创建目标目录
    TARGET_DIR.mkdir(parents=True, exist_ok=True)
    
    # 1. 复制根目录文件
    print("📄 复制根目录文件:")
    for file_name in ROOT_FILES:
        src_file = PROJECT_ROOT / file_name
        if src_file.exists():
            shutil.copy2(src_file, TARGET_DIR / file_name)
            print(f"   ✅ {file_name}")
    print()
    
    # 2. 完整复制目录
    for dir_name in FULL_COPY_DIRS:
        src_dir = PROJECT_ROOT / dir_name
        if src_dir.exists():
            copy_full_directory(src_dir, TARGET_DIR / dir_name)
            print()
    
    # 3. 部分复制 modules/
    src_modules = PROJECT_ROOT / "modules"
    if src_modules.exists():
        copy_modules_directory(src_modules, TARGET_DIR / "modules")
        print()
    
    # 4. 部分复制 resources/
    src_resources = PROJECT_ROOT / "resources"
    if src_resources.exists():
        copy_resources_directory(src_resources, TARGET_DIR / "resources")
        print()
    
    # 5. 创建空的 ui/ 目录（占位）
    ui_dir = TARGET_DIR / "ui"
    ui_dir.mkdir(exist_ok=True)
    (ui_dir / "README.md").write_text(
        "# UI 层\n\n"
        "此目录用于存放新的 UI 实现。\n\n"
        "## 待实现\n\n"
        "- [ ] 主窗口框架\n"
        "- [ ] 模块 UI 组件\n"
        "- [ ] 样式和主题\n",
        encoding="utf-8"
    )
    print("📁 创建空的 ui/ 目录（占位）")
    print(f"   ✅ ui/README.md")
    print()
    
    print("=" * 60)
    print("✅ 复制完成！")
    print("=" * 60)
    print()
    print("📊 复制总结:")
    print(f"   ✅ 完整复制: {', '.join(FULL_COPY_DIRS)}")
    print(f"   ✅ 部分复制: modules/ (仅 logic), resources/ (不含样式)")
    print(f"   ✅ 根目录文件: {len(ROOT_FILES)} 个")
    print(f"   ⏭️  跳过: ui/, resources/qss/, resources/themes/")
    print()
    print("🎯 下一步:")
    print("   1. 在 UE_TOOKITS_AI_NEW/ 中重新设计 UI")
    print("   2. 保持 core/ 和 modules/logic/ 不变")
    print("   3. 原项目作为参考和备份")


if __name__ == "__main__":
    main()

