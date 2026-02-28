#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
UE Toolkit - Complete Configuration Cleanup Script
完全清理配置脚本 - 用于测试全新安装

This script removes ALL configuration and data to simulate a fresh installation.
"""

import os
import shutil
from pathlib import Path


def remove_directory(path, description):
    """Remove a directory and all its contents."""
    if path.exists():
        try:
            shutil.rmtree(path)
            print(f"  [OK] 已删除: {path}")
            return True
        except Exception as e:
            print(f"  [ERROR] 删除失败: {path}")
            print(f"         错误: {e}")
            return False
    else:
        print(f"  [SKIP] 目录不存在: {path}")
        return False


def main():
    print("=" * 60)
    print("UE Toolkit - 完全清理配置工具")
    print("=" * 60)
    print()
    print("此脚本将删除所有配置和数据：")
    print("  [X] AppData 中的所有应用配置")
    print("  [X] AI 模型缓存")
    print("  [X] 资产库配置")
    print("  [X] 所有用户数据")
    print()
    print("这将模拟全新安装的状态！")
    print()
    
    response = input("确认要继续吗？(yes/no): ").strip().lower()
    if response not in ['yes', 'y', '是']:
        print("\n已取消清理操作。")
        return
    
    print("\n开始完全清理...\n")
    
    # Define paths to clean
    home = Path.home()
    appdata = Path(os.environ.get('APPDATA', home / 'AppData' / 'Roaming'))
    
    paths_to_clean = [
        (home / '.cache' / 'huggingface', 'AI 模型缓存'),
        (appdata / 'ue_toolkit', '应用数据目录'),
    ]
    
    cleaned_count = 0
    for i, (path, description) in enumerate(paths_to_clean, 1):
        print(f"[{i}/{len(paths_to_clean)}] 清理 {description}...")
        if remove_directory(path, description):
            cleaned_count += 1
    
    print()
    print("=" * 60)
    print("完全清理完成！")
    print("=" * 60)
    print()
    print(f"已清理 {cleaned_count} 个目录。")
    print("现在可以测试安装包的全新安装效果了！")
    print()


if __name__ == '__main__':
    main()
