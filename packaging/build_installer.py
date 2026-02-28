#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
自动化打包脚本 - 一键生成安装包

步骤:
0. 清理上次构建产物（build/、dist/、packaging/Output/）
1. 从 version.py 读取版本号
2. 更新 UeToolkitpack.iss 中的版本号
3. 运行 PyInstaller 打包 EXE
4. 调用 Inno Setup 编译安装包
"""

import sys
import shutil
import subprocess
from pathlib import Path
import re

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# 导入版本信息
from version import VERSION


def clean_build():
    """清理上次构建产物"""

    dirs_to_clean = [
        project_root / "build",
        project_root / "dist",
        Path(__file__).parent / "Output",
    ]

    cleaned = False
    for d in dirs_to_clean:
        if d.exists():
            size_mb = sum(f.stat().st_size for f in d.rglob("*") if f.is_file()) / (1024 * 1024)
            print(f"   🗑️  {d.relative_to(project_root)}/ ({size_mb:.1f} MB)")
            shutil.rmtree(d)
            cleaned = True

    if cleaned:
        print("   ✅ 清理完成")
    else:
        print("   ✅ 无需清理（没有旧构建文件）")
    return True


def update_iss_version():
    """更新 Inno Setup 脚本中的版本号"""
    
    iss_file = Path(__file__).parent / "UeToolkitpack.iss"
    
    if not iss_file.exists():
        print(f"❌ 错误: 找不到文件 {iss_file}")
        return False
    
    print(f"📖 读取文件: {iss_file.name}")
    with open(iss_file, 'r', encoding='utf-8') as f:
        content = f.read()
    
    old_version_match = re.search(r'#define MyAppVersion "([^"]+)"', content)
    old_version = old_version_match.group(1) if old_version_match else "未知"
    
    content = re.sub(
        r'(#define MyAppVersion ")([^"]+)(")',
        rf'\g<1>{VERSION}\g<3>',
        content
    )
    
    with open(iss_file, 'w', encoding='utf-8') as f:
        f.write(content)
    
    print(f"✅ 版本号已更新: {old_version} → {VERSION}")
    return True


def build_exe():
    """使用 PyInstaller 打包 EXE"""
    
    print()
    print("=" * 60)
    print("步骤 3/4: 打包 EXE 文件")
    print("=" * 60)
    print()
    
    spec_file = Path(__file__).parent / "ue_toolkit.spec"
    
    if not spec_file.exists():
        print(f"❌ 错误: 找不到 {spec_file}")
        return False
    
    print(f"🔨 运行 PyInstaller...")
    print(f"   配置文件: {spec_file.name}")
    print()
    
    try:
        result = subprocess.run(
            [sys.executable, "-m", "PyInstaller", str(spec_file), "--clean"],
            cwd=project_root,
            check=True
        )
        
        print()
        print("✅ EXE 打包完成")
        return True
        
    except subprocess.CalledProcessError as e:
        print()
        print(f"❌ PyInstaller 打包失败: {e}")
        return False
    except FileNotFoundError:
        print()
        print("❌ 错误: 找不到 pyinstaller 命令")
        print("   请先安装: pip install pyinstaller")
        return False


def build_installer():
    """使用 Inno Setup 编译安装包"""
    
    print()
    print("=" * 60)
    print("步骤 4/4: 编译安装包")
    print("=" * 60)
    print()
    
    iss_file = Path(__file__).parent / "UeToolkitpack.iss"
    
    # 查找 Inno Setup 编译器
    iscc_paths = [
        r"C:\Program Files (x86)\Inno Setup 6\ISCC.exe",
        r"C:\Program Files\Inno Setup 6\ISCC.exe",
        r"C:\Program Files (x86)\Inno Setup 5\ISCC.exe",
        r"C:\Program Files\Inno Setup 5\ISCC.exe",
    ]
    
    iscc_exe = None
    for path in iscc_paths:
        if Path(path).exists():
            iscc_exe = path
            break
    
    if not iscc_exe:
        print("⚠️  警告: 找不到 Inno Setup 编译器")
        print()
        print("请手动执行以下步骤:")
        print(f"1. 打开 Inno Setup")
        print(f"2. 打开文件: {iss_file}")
        print(f"3. 点击 Build → Compile")
        print()
        print("或者安装 Inno Setup:")
        print("   下载地址: https://jrsoftware.org/isdl.php")
        return False
    
    print(f"🔨 运行 Inno Setup 编译器...")
    print(f"   编译器: {iscc_exe}")
    print(f"   脚本: {iss_file.name}")
    print()
    
    try:
        result = subprocess.run(
            [iscc_exe, str(iss_file)],
            check=True,
            capture_output=True,
            text=True,
            encoding='utf-8',
            errors='replace'
        )
        
        print(result.stdout)
        print()
        print("✅ 安装包编译完成")
        
        # 显示输出文件位置
        output_dir = Path(__file__).parent / "Output"
        if output_dir.exists():
            output_files = list(output_dir.glob("*.exe"))
            if output_files:
                print()
                print("📦 安装包位置:")
                for file in output_files:
                    print(f"   {file}")
        
        return True
        
    except subprocess.CalledProcessError as e:
        print()
        print(f"❌ Inno Setup 编译失败:")
        print(e.stderr)
        return False


def main():
    """主函数"""
    
    print("=" * 60)
    print("UE Toolkit - 自动化打包脚本")
    print("=" * 60)
    print()
    print(f"📌 当前版本: {VERSION}")
    print()
    
    # 步骤 1: 清理旧构建
    print("=" * 60)
    print("步骤 1/4: 清理旧构建文件")
    print("=" * 60)
    print()
    clean_build()
    
    # 步骤 2: 更新版本号
    print()
    print("=" * 60)
    print("步骤 2/4: 更新 Inno Setup 版本号")
    print("=" * 60)
    print()
    
    if not update_iss_version():
        print()
        print("❌ 更新版本号失败")
        return False
    
    # 询问是否继续打包
    print()
    response = input("是否继续打包 EXE 和安装包? (y/n): ").strip().lower()
    if response not in ['y', 'yes', '是']:
        print()
        print("⏸️  已取消打包")
        return True
    
    # 步骤 3: 打包 EXE
    if not build_exe():
        print()
        print("❌ EXE 打包失败")
        return False
    
    # 步骤 4: 编译安装包
    if not build_installer():
        print()
        print("⚠️  安装包编译未完成")
        print("   请手动使用 Inno Setup 编译")
        return True
    
    print()
    print("=" * 60)
    print("🎉 打包完成！")
    print("=" * 60)
    print()
    print(f"✅ 版本: {VERSION}")
    print(f"✅ EXE 文件: dist/UE_Toolkit.exe")
    print(f"✅ 安装包: packaging/Output/UE_Toolkit_Setup_v{VERSION}.exe")
    print()
    
    return True


if __name__ == "__main__":
    try:
        success = main()
        
        if not success:
            sys.exit(1)
            
    except KeyboardInterrupt:
        print()
        print()
        print("⏸️  用户取消操作")
        sys.exit(1)
        
    except Exception as e:
        print()
        print(f"❌ 发生错误: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
