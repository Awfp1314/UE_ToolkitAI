# -*- coding: utf-8 -*-
"""
节点字典切换工具
用于测试不同版本字典对 AI 性能的影响
"""

import os
import shutil
import sys

def switch_dictionary(mode):
    """
    切换节点字典模式
    
    Args:
        mode: 'full' (完整) / 'minimal' (精简) / 'empty' (空)
    """
    script_dir = os.path.dirname(os.path.abspath(__file__))
    current_dict = os.path.join(script_dir, 'node_dictionary.json')
    full_dict = os.path.join(script_dir, 'node_dictionary_full.json')
    minimal_dict = os.path.join(script_dir, 'node_dictionary_minimal.json')
    
    # 首次运行：备份完整字典
    if not os.path.exists(full_dict):
        if os.path.exists(current_dict):
            print("[备份] 保存完整字典为 node_dictionary_full.json")
            shutil.copy(current_dict, full_dict)
        else:
            print("[错误] 找不到 node_dictionary.json")
            return False
    
    # 切换模式
    if mode == 'full':
        print("[切换] 使用完整字典 (~63 KB, ~21,500 tokens)")
        shutil.copy(full_dict, current_dict)
        
    elif mode == 'minimal':
        print("[切换] 使用精简字典 (~3 KB, ~1,000 tokens)")
        if not os.path.exists(minimal_dict):
            print("[错误] 找不到 node_dictionary_minimal.json")
            return False
        shutil.copy(minimal_dict, current_dict)
        
    elif mode == 'empty':
        print("[切换] 使用空字典 (0 tokens，测试 AI 裸奔)")
        with open(current_dict, 'w', encoding='utf-8') as f:
            f.write('{"version": "empty", "description": "AI 依赖自身知识"}')
    
    else:
        print("[错误] 未知模式:", mode)
        print("可用模式: full / minimal / empty")
        return False
    
    # 显示当前文件大小
    size = os.path.getsize(current_dict)
    tokens = size // 3
    print(f"[完成] 当前字典: {size} 字节 (~{tokens} tokens)")
    print("\n重启 UE 编辑器和 ue_toolkits 使更改生效")
    return True


def show_info():
    """显示字典信息"""
    script_dir = os.path.dirname(os.path.abspath(__file__))
    current_dict = os.path.join(script_dir, 'node_dictionary.json')
    
    if os.path.exists(current_dict):
        size = os.path.getsize(current_dict)
        tokens = size // 3
        
        print("=" * 60)
        print("当前节点字典状态")
        print("=" * 60)
        print(f"文件大小: {size:,} 字节 ({size/1024:.2f} KB)")
        print(f"预估 token: ~{tokens:,}")
        print()
        
        # 读取版本信息
        try:
            import json
            with open(current_dict, 'r', encoding='utf-8') as f:
                data = json.load(f)
                version = data.get('version', 'unknown')
                print(f"当前版本: {version}")
                
                if 'categories' in data:
                    print(f"分类数量: {len(data['categories'])}")
                elif 'class_names' in data:
                    print(f"类名映射: {len(data['class_names'])} 个")
        except:
            pass
        
        print("=" * 60)
    else:
        print("[错误] 找不到 node_dictionary.json")


if __name__ == '__main__':
    print("=" * 60)
    print("节点字典切换工具")
    print("=" * 60)
    print()
    
    if len(sys.argv) < 2:
        print("用法:")
        print("  python switch_dictionary.py info      # 显示当前状态")
        print("  python switch_dictionary.py full      # 切换到完整字典")
        print("  python switch_dictionary.py minimal   # 切换到精简字典")
        print("  python switch_dictionary.py empty     # 切换到空字典")
        print()
        show_info()
    else:
        mode = sys.argv[1].lower()
        if mode == 'info':
            show_info()
        else:
            if switch_dictionary(mode):
                print()
                show_info()

