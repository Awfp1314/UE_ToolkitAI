# -*- coding: utf-8 -*-
"""
测试打包版 7z 的查找逻辑
"""

from pathlib import Path
import sys

# 添加 Client 到路径
sys.path.insert(0, str(Path(__file__).parent))

def test_find_7z():
    """测试 7z 查找逻辑"""
    print("=" * 60)
    print("测试 7z 查找逻辑")
    print("=" * 60)
    
    # 模拟查找逻辑
    script_dir = Path(__file__).parent
    
    # 1. 打包版本（优先）
    bundled_7z = script_dir / "resources" / "tools" / "7z.exe"
    print(f"\n1. 打包版本: {bundled_7z}")
    print(f"   存在: {bundled_7z.exists()}")
    if bundled_7z.exists():
        size = bundled_7z.stat().st_size / 1024
        print(f"   大小: {size:.1f} KB")
    
    # 2. 系统安装
    system_7z = Path("C:/Program Files/7-Zip/7z.exe")
    print(f"\n2. 系统安装: {system_7z}")
    print(f"   存在: {system_7z.exists()}")
    if system_7z.exists():
        size = system_7z.stat().st_size / 1024
        print(f"   大小: {size:.1f} KB")
    
    # 3. 测试 FastFileOperations
    print("\n" + "=" * 60)
    print("测试 FastFileOperations 类")
    print("=" * 60)
    
    from core.utils.fast_file_ops import FastFileOperations
    import logging
    
    # 创建日志
    logger = logging.getLogger("test")
    logger.setLevel(logging.INFO)
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter('%(message)s'))
    logger.addHandler(handler)
    
    # 创建实例
    fast_ops = FastFileOperations(logger)
    
    print(f"\n✅ FastFileOperations 初始化完成")
    print(f"   7z 路径: {fast_ops._7z_path}")
    print(f"   快速模式: {fast_ops._use_fast_mode}")
    
    # 检查 DLL
    if fast_ops._7z_path:
        dll_path = fast_ops._7z_path.parent / "7z.dll"
        print(f"\n检查 7z.dll:")
        print(f"   路径: {dll_path}")
        print(f"   存在: {dll_path.exists()}")
        if dll_path.exists():
            size = dll_path.stat().st_size / 1024
            print(f"   大小: {size:.1f} KB")

if __name__ == "__main__":
    test_find_7z()
