"""检查项目中 ThreadManager 的使用情况

分析旧版 ThreadManager (thread_utils.py) 和新版 EnhancedThreadManager (thread_manager.py) 的使用情况
"""

import os
import re
from pathlib import Path
from typing import List, Dict, Tuple

def find_python_files(root_dir: str) -> List[Path]:
    """查找所有 Python 文件"""
    python_files = []
    root_path = Path(root_dir)
    
    # 排除的目录
    exclude_dirs = {'__pycache__', '.git', 'venv', 'env', 'fixtemp', 'htmlcov'}
    
    for file_path in root_path.rglob('*.py'):
        # 检查是否在排除目录中
        if any(excluded in file_path.parts for excluded in exclude_dirs):
            continue
        python_files.append(file_path)
    
    return python_files

def analyze_file(file_path: Path) -> Dict[str, List[int]]:
    """分析单个文件中的 ThreadManager 使用情况
    
    Returns:
        {
            'old_import': [行号列表],  # 导入旧版 ThreadManager
            'new_import': [行号列表],  # 导入新版 EnhancedThreadManager
            'old_usage': [行号列表],   # 使用旧版 get_thread_manager
            'new_usage': [行号列表],   # 使用新版 get_thread_manager
        }
    """
    result = {
        'old_import': [],
        'new_import': [],
        'old_usage': [],
        'new_usage': [],
    }
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        
        for i, line in enumerate(lines, start=1):
            # 检查导入语句
            if 'from core.utils.thread_utils import' in line:
                if 'ThreadManager' in line or 'get_thread_manager' in line:
                    result['old_import'].append(i)
            
            if 'from core.utils.thread_manager import' in line:
                if 'EnhancedThreadManager' in line or 'get_thread_manager' in line:
                    result['new_import'].append(i)
            
            # 检查使用语句（排除导入行）
            if 'import' not in line:
                if 'get_thread_manager()' in line:
                    # 需要根据导入判断是哪个版本
                    if result['old_import']:
                        result['old_usage'].append(i)
                    elif result['new_import']:
                        result['new_usage'].append(i)
                
                if 'ThreadManager(' in line:
                    result['old_usage'].append(i)
                
                if 'EnhancedThreadManager(' in line:
                    result['new_usage'].append(i)
    
    except Exception as e:
        print(f"❌ 读取文件失败: {file_path} - {e}")
    
    return result

def main():
    """主函数"""
    print("🔍 开始检查 ThreadManager 使用情况...\n")
    
    root_dir = "UE_TOOKITS_AI_NEW"
    python_files = find_python_files(root_dir)
    
    print(f"📁 找到 {len(python_files)} 个 Python 文件\n")
    
    # 统计结果
    old_files = []  # 使用旧版的文件
    new_files = []  # 使用新版的文件
    mixed_files = []  # 混合使用的文件
    
    for file_path in python_files:
        result = analyze_file(file_path)
        
        has_old = bool(result['old_import'] or result['old_usage'])
        has_new = bool(result['new_import'] or result['new_usage'])
        
        if has_old and has_new:
            mixed_files.append((file_path, result))
        elif has_old:
            old_files.append((file_path, result))
        elif has_new:
            new_files.append((file_path, result))
    
    # 输出结果
    print("=" * 80)
    print("📊 检查结果")
    print("=" * 80)
    
    print(f"\n✅ 使用新版 EnhancedThreadManager 的文件: {len(new_files)} 个")
    for file_path, result in new_files:
        rel_path = file_path.relative_to(root_dir)
        print(f"   - {rel_path}")
        if result['new_import']:
            print(f"     导入: 第 {result['new_import']} 行")
        if result['new_usage']:
            print(f"     使用: 第 {result['new_usage']} 行")
    
    print(f"\n⚠️  使用旧版 ThreadManager 的文件: {len(old_files)} 个")
    for file_path, result in old_files:
        rel_path = file_path.relative_to(root_dir)
        print(f"   - {rel_path}")
        if result['old_import']:
            print(f"     导入: 第 {result['old_import']} 行")
        if result['old_usage']:
            print(f"     使用: 第 {result['old_usage']} 行")
    
    print(f"\n❌ 混合使用的文件: {len(mixed_files)} 个")
    for file_path, result in mixed_files:
        rel_path = file_path.relative_to(root_dir)
        print(f"   - {rel_path}")
        if result['old_import']:
            print(f"     旧版导入: 第 {result['old_import']} 行")
        if result['new_import']:
            print(f"     新版导入: 第 {result['new_import']} 行")
        if result['old_usage']:
            print(f"     旧版使用: 第 {result['old_usage']} 行")
        if result['new_usage']:
            print(f"     新版使用: 第 {result['new_usage']} 行")
    
    print("\n" + "=" * 80)
    print("📌 总结")
    print("=" * 80)
    print(f"新版文件: {len(new_files)} 个")
    print(f"旧版文件: {len(old_files)} 个")
    print(f"混合文件: {len(mixed_files)} 个")
    
    if old_files or mixed_files:
        print("\n⚠️  建议: 将所有旧版 ThreadManager 迁移到新版 EnhancedThreadManager")
    else:
        print("\n✅ 所有文件都使用新版 EnhancedThreadManager！")

if __name__ == "__main__":
    main()

