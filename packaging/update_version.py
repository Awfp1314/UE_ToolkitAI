#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
自动更新 Inno Setup 脚本中的版本号

从 version.py 读取版本号，自动更新 UeToolkitpack.iss 文件
"""

import sys
from pathlib import Path
import re

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# 导入版本信息
from version import VERSION, APP_NAME, APP_AUTHOR


def update_iss_version():
    """更新 Inno Setup 脚本中的版本号"""
    
    # 文件路径
    iss_file = Path(__file__).parent / "UeToolkitpack.iss"
    
    if not iss_file.exists():
        print(f"❌ 错误: 找不到文件 {iss_file}")
        return False
    
    # 读取文件内容
    print(f"📖 读取文件: {iss_file.name}")
    with open(iss_file, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # 备份原始版本号
    old_version_match = re.search(r'#define MyAppVersion "([^"]+)"', content)
    old_version = old_version_match.group(1) if old_version_match else "未知"
    
    # 替换版本号
    # 1. 替换 #define MyAppVersion "x.x.x"
    content = re.sub(
        r'(#define MyAppVersion ")([^"]+)(")',
        rf'\g<1>{VERSION}\g<3>',
        content
    )
    
    # 写回文件
    with open(iss_file, 'w', encoding='utf-8') as f:
        f.write(content)
    
    print(f"✅ 版本号已更新:")
    print(f"   旧版本: {old_version}")
    print(f"   新版本: {VERSION}")
    print(f"   文件: {iss_file.name}")
    
    return True


if __name__ == "__main__":
    print("=" * 60)
    print("UE Toolkit - Inno Setup 版本号自动更新工具")
    print("=" * 60)
    print()
    
    try:
        success = update_iss_version()
        
        if success:
            print()
            print("🎉 更新完成！")
            print()
            print("💡 提示:")
            print("   现在可以使用 Inno Setup 编译安装包了")
            print("   版本号会自动与 version.py 保持一致")
        else:
            print()
            print("❌ 更新失败！")
            sys.exit(1)
            
    except Exception as e:
        print()
        print(f"❌ 发生错误: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
