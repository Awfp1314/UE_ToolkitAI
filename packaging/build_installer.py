#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
自动化打包脚本 - 一键生成安装包

步骤:
1. 清理上次构建产物（build/、dist/、packaging/Output/）
2. 运行 PyInstaller 打包 EXE
3. 调用 Inno Setup 编译安装包
"""

import sys
import shutil
import subprocess
from pathlib import Path

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


def build_exe():
    """使用 PyInstaller 打包 EXE"""
    
    print()
    print("=" * 60)
    print("步骤 2/3: 打包 EXE 文件")
    print("=" * 60)
    print()
    
    spec_file = Path(__file__).parent / "ue_toolkit.spec"
    
    if not spec_file.exists():
        print(f"❌ 错误: 找不到 {spec_file}")
        return False
    
    print(f"🔨 运行 PyInstaller...")
    print(f"   配置文件: {spec_file.name}")
    print(f"   正在打包，请稍候...")
    print()
    
    try:
        # 捕获 PyInstaller 输出
        result = subprocess.run(
            [sys.executable, "-m", "PyInstaller", str(spec_file), "--clean"],
            cwd=project_root,
            check=True,
            capture_output=True,
            text=True,
            encoding='utf-8',
            errors='replace'
        )
        
        # 解析输出，提取错误和警告
        errors = []
        warnings = []
        
        for line in result.stdout.splitlines() + result.stderr.splitlines():
            line_lower = line.lower()
            if 'error' in line_lower or 'failed' in line_lower:
                errors.append(line)
            elif 'warning' in line_lower or 'warn' in line_lower:
                warnings.append(line)
        
        # 保存完整日志到文件
        log_file = project_root / "dist" / "build.log"
        log_file.parent.mkdir(exist_ok=True)
        with open(log_file, 'w', encoding='utf-8') as f:
            f.write("=" * 80 + "\n")
            f.write("PyInstaller 完整构建日志\n")
            f.write("=" * 80 + "\n\n")
            f.write(result.stdout)
            if result.stderr:
                f.write("\n" + "=" * 80 + "\n")
                f.write("标准错误输出\n")
                f.write("=" * 80 + "\n\n")
                f.write(result.stderr)
        
        # 生成错误和警告摘要日志
        summary_log = project_root / "dist" / "build_summary.log"
        with open(summary_log, 'w', encoding='utf-8') as f:
            f.write("=" * 80 + "\n")
            f.write("PyInstaller 构建摘要（仅错误和警告）\n")
            f.write("=" * 80 + "\n\n")
            
            if errors:
                f.write("❌ 错误:\n")
                f.write("-" * 80 + "\n")
                for error in errors:
                    f.write(error + "\n")
                f.write("\n")
            
            if warnings:
                f.write("⚠️  警告:\n")
                f.write("-" * 80 + "\n")
                for warning in warnings:
                    f.write(warning + "\n")
                f.write("\n")
            
            if not errors and not warnings:
                f.write("✅ 没有错误或警告\n")
        
        print("✅ EXE 打包完成")
        
        # 显示摘要
        if errors:
            print(f"   ⚠️  发现 {len(errors)} 个错误")
        if warnings:
            print(f"   ⚠️  发现 {len(warnings)} 个警告")
        
        if errors or warnings:
            print(f"   📄 详细日志: dist/build_summary.log")
            print(f"   📄 完整日志: dist/build.log")
        
        return True
        
    except subprocess.CalledProcessError as e:
        print()
        print(f"❌ PyInstaller 打包失败")
        
        # 保存错误日志
        log_file = project_root / "dist" / "build_error.log"
        log_file.parent.mkdir(exist_ok=True)
        with open(log_file, 'w', encoding='utf-8') as f:
            f.write("=" * 80 + "\n")
            f.write("PyInstaller 错误日志\n")
            f.write("=" * 80 + "\n\n")
            f.write(f"返回码: {e.returncode}\n\n")
            if e.stdout:
                f.write("标准输出:\n")
                f.write("-" * 80 + "\n")
                f.write(e.stdout)
                f.write("\n\n")
            if e.stderr:
                f.write("标准错误:\n")
                f.write("-" * 80 + "\n")
                f.write(e.stderr)
        
        print(f"   📄 错误日志: dist/build_error.log")
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
    print("步骤 3/3: 编译安装包")
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
    print(f"   正在编译，请稍候...")
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
        
        # 保存 Inno Setup 日志
        inno_log = project_root / "dist" / "inno_setup.log"
        with open(inno_log, 'w', encoding='utf-8') as f:
            f.write("=" * 80 + "\n")
            f.write("Inno Setup 编译日志\n")
            f.write("=" * 80 + "\n\n")
            f.write(result.stdout)
            if result.stderr:
                f.write("\n" + "=" * 80 + "\n")
                f.write("标准错误输出\n")
                f.write("=" * 80 + "\n\n")
                f.write(result.stderr)
        
        print("✅ 安装包编译完成")
        print(f"   📄 编译日志: dist/inno_setup.log")
        
        # 显示输出文件位置
        output_dir = project_root / "dist"
        if output_dir.exists():
            output_files = list(output_dir.glob("*Setup*.exe"))
            if output_files:
                print()
                print("📦 安装包位置:")
                for file in output_files:
                    print(f"   {file}")
        
        return True
        
    except subprocess.CalledProcessError as e:
        print()
        print(f"❌ Inno Setup 编译失败")
        
        # 保存错误日志
        error_log = project_root / "dist" / "inno_setup_error.log"
        with open(error_log, 'w', encoding='utf-8') as f:
            f.write("=" * 80 + "\n")
            f.write("Inno Setup 错误日志\n")
            f.write("=" * 80 + "\n\n")
            f.write(f"返回码: {e.returncode}\n\n")
            if e.stdout:
                f.write("标准输出:\n")
                f.write("-" * 80 + "\n")
                f.write(e.stdout)
                f.write("\n\n")
            if e.stderr:
                f.write("标准错误:\n")
                f.write("-" * 80 + "\n")
                f.write(e.stderr)
        
        print(f"   📄 错误日志: dist/inno_setup_error.log")
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
    print("步骤 1/3: 清理旧构建文件")
    print("=" * 60)
    print()
    clean_build()
    
    # 询问是否继续打包
    print()
    response = input("是否继续打包 EXE 和安装包? (y/n): ").strip().lower()
    if response not in ['y', 'yes', '是']:
        print()
        print("⏸️  已取消打包")
        return True
    
    # 步骤 2: 打包 EXE
    if not build_exe():
        print()
        print("❌ EXE 打包失败")
        return False
    
    # 步骤 3: 编译安装包
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
    print(f"✅ 安装包: dist/UE_Toolkit_Setup_v{VERSION}.exe")
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
