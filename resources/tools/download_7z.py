# -*- coding: utf-8 -*-
"""
复制 7z.exe 和 7z.dll 到 resources/tools 目录

7-Zip 是开源软件（LGPL 许可），可以自由分发。
从系统已安装的 7-Zip 复制文件。
"""

import shutil
from pathlib import Path

def copy_7z_from_system():
    """从系统安装的 7-Zip 复制文件"""
    script_dir = Path(__file__).parent
    target_exe = script_dir / "7z.exe"
    target_dll = script_dir / "7z.dll"
    
    # 检查是否已存在
    if target_exe.exists() and target_dll.exists():
        exe_size = target_exe.stat().st_size / 1024
        dll_size = target_dll.stat().st_size / 1024
        print(f"✅ 7-Zip 文件已存在:")
        print(f"   7z.exe: {exe_size:.1f} KB")
        print(f"   7z.dll: {dll_size:.1f} KB")
        print(f"   总大小: {(exe_size + dll_size) / 1024:.2f} MB")
        return True
    
    # 查找系统安装的 7-Zip
    system_7z_dir = Path("C:/Program Files/7-Zip")
    if not system_7z_dir.exists():
        print(f"❌ 未找到系统安装的 7-Zip: {system_7z_dir}")
        print(f"\n💡 请先安装 7-Zip:")
        print(f"   1. 访问: https://www.7-zip.org/download.html")
        print(f"   2. 下载并安装 64-bit x64 版本")
        print(f"   3. 重新运行此脚本")
        return False
    
    source_exe = system_7z_dir / "7z.exe"
    source_dll = system_7z_dir / "7z.dll"
    
    if not source_exe.exists() or not source_dll.exists():
        print(f"❌ 7-Zip 安装目录中缺少文件:")
        print(f"   7z.exe: {'✓' if source_exe.exists() else '✗'}")
        print(f"   7z.dll: {'✓' if source_dll.exists() else '✗'}")
        return False
    
    try:
        # 复制文件
        print(f"📋 从系统 7-Zip 复制文件...")
        print(f"   源目录: {system_7z_dir}")
        print(f"   目标目录: {script_dir}")
        
        shutil.copy2(source_exe, target_exe)
        shutil.copy2(source_dll, target_dll)
        
        exe_size = target_exe.stat().st_size / 1024
        dll_size = target_dll.stat().st_size / 1024
        
        print(f"\n✅ 复制完成:")
        print(f"   7z.exe: {exe_size:.1f} KB")
        print(f"   7z.dll: {dll_size:.1f} KB")
        print(f"   总大小: {(exe_size + dll_size) / 1024:.2f} MB")
        
        return True
        
    except Exception as e:
        print(f"❌ 复制失败: {e}")
        return False

if __name__ == "__main__":
    success = copy_7z_from_system()
    if success:
        print("\n🎉 7-Zip 文件准备完成，可以打包到安装程序中了！")
    else:
        print("\n⚠️ 请手动完成文件准备")
