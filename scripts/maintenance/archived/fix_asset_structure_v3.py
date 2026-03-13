# -*- coding: utf-8 -*-
"""
修复资产文件夹结构 v3

正确结构：自定义名称/Content/原资产文件夹名/内容
例如：女鬼/Content/AGhost/Maps/...

问题：文件夹名和自定义名称搞反了
例如：AGhost/Content/女鬼/Maps/...

修复方案：
1. 检查配置中的资产名称和实际文件夹名是否匹配
2. 如果不匹配，重命名文件夹
"""
import json
import shutil
from pathlib import Path

def fix_structure():
    config_path = Path("E:/UE_Asset/.asset_config/config.json")
    
    if not config_path.exists():
        print(f"配置文件不存在: {config_path}")
        return
    
    with open(config_path, 'r', encoding='utf-8') as f:
        config = json.load(f)
    
    assets = config.get('assets', [])
    
    print(f"检查 {len(assets)} 个资产...")
    print("=" * 70)
    
    need_fix = []
    
    for asset in assets:
        custom_name = asset.get('name', '')  # 自定义名称
        asset_path = Path(asset.get('path', ''))
        
        if not asset_path.exists():
            print(f"⚠️  路径不存在: {custom_name} -> {asset_path}")
            continue
        
        folder_name = asset_path.name  # 实际文件夹名
        
        if custom_name == folder_name:
            # 名称匹配，检查Content下的结构
            content_folder = asset_path / "Content"
            if content_folder.exists():
                subs = [d.name for d in content_folder.iterdir() if d.is_dir()]
                print(f"✓ 正确: {custom_name} -> Content/{subs}")
            else:
                print(f"⚠️  无Content: {custom_name}")
        else:
            # 名称不匹配 - 可能是反了
            print(f"❌ 名称不匹配: 自定义名称='{custom_name}', 文件夹名='{folder_name}'")
            
            # 检查是否是反了的情况
            content_folder = asset_path / "Content"
            if content_folder.exists():
                subs = [d for d in content_folder.iterdir() if d.is_dir()]
                # 检查Content下是否有以自定义名称命名的文件夹
                custom_in_content = content_folder / custom_name
                if custom_in_content.exists():
                    print(f"   发现反转: {folder_name}/Content/{custom_name}/...")
                    print(f"   应该是: {custom_name}/Content/{folder_name}/...")
                    need_fix.append({
                        'custom_name': custom_name,
                        'folder_name': folder_name,
                        'asset_path': asset_path,
                        'content_folder': content_folder,
                        'wrong_subfolder': custom_in_content,
                        'asset_config': asset
                    })
                else:
                    print(f"   Content下: {[d.name for d in subs]}")
    
    print("=" * 70)
    print(f"\n发现 {len(need_fix)} 个需要修复的资产")
    
    if need_fix:
        print("\n修复计划：")
        for i, item in enumerate(need_fix, 1):
            print(f"\n{i}. {item['folder_name']} -> {item['custom_name']}")
            print(f"   当前: {item['folder_name']}/Content/{item['custom_name']}/...")
            print(f"   修复: {item['custom_name']}/Content/{item['folder_name']}/...")
        
        choice = input("\n执行修复？(y/n): ").strip().lower()
        
        if choice == 'y':
            execute_fix(need_fix, config, config_path)
        else:
            print("已取消")

def execute_fix(need_fix, config, config_path):
    """执行修复"""
    fixed = 0
    
    for item in need_fix:
        try:
            custom_name = item['custom_name']
            folder_name = item['folder_name']
            asset_path = item['asset_path']  # 例如 E:\UE_Asset\人物\AGhost
            wrong_subfolder = item['wrong_subfolder']  # 例如 AGhost/Content/女鬼
            
            print(f"\n修复: {folder_name} -> {custom_name}")
            
            parent_dir = asset_path.parent  # 例如 E:\UE_Asset\人物
            
            # 步骤1: 重命名 Content/自定义名称 为 Content/原文件夹名
            # AGhost/Content/女鬼 -> AGhost/Content/AGhost
            temp_subfolder = asset_path / "Content" / f"_temp_{folder_name}"
            print(f"  1. 重命名: Content/{custom_name} -> Content/_temp_{folder_name}")
            shutil.move(str(wrong_subfolder), str(temp_subfolder))
            
            correct_subfolder = asset_path / "Content" / folder_name
            print(f"  2. 重命名: Content/_temp_{folder_name} -> Content/{folder_name}")
            shutil.move(str(temp_subfolder), str(correct_subfolder))
            
            # 步骤2: 重命名外层文件夹
            # AGhost -> 女鬼
            new_asset_path = parent_dir / custom_name
            
            # 检查目标是否已存在
            if new_asset_path.exists():
                print(f"  ⚠️  目标文件夹已存在: {new_asset_path}")
                # 尝试合并
                temp_path = parent_dir / f"_temp_{custom_name}"
                shutil.move(str(asset_path), str(temp_path))
                # 合并到现有文件夹
                for item_to_move in (temp_path / "Content").iterdir():
                    dest = new_asset_path / "Content" / item_to_move.name
                    if not dest.exists():
                        shutil.move(str(item_to_move), str(dest))
                shutil.rmtree(temp_path)
            else:
                print(f"  3. 重命名文件夹: {folder_name} -> {custom_name}")
                shutil.move(str(asset_path), str(new_asset_path))
            
            # 步骤3: 更新配置文件中的路径
            item['asset_config']['path'] = str(new_asset_path)
            print(f"  4. 更新配置路径: {new_asset_path}")
            
            print(f"  ✓ 完成")
            fixed += 1
            
        except Exception as e:
            print(f"  ✗ 失败: {e}")
            import traceback
            traceback.print_exc()
    
    # 保存配置
    if fixed > 0:
        backup_path = config_path.parent / "config_before_fix_v3.json"
        shutil.copy2(config_path, backup_path)
        print(f"\n已备份配置: {backup_path}")
        
        with open(config_path, 'w', encoding='utf-8') as f:
            json.dump(config, f, ensure_ascii=False, indent=2)
        print(f"已更新配置: {config_path}")
    
    print(f"\n修复完成: {fixed}/{len(need_fix)}")

if __name__ == "__main__":
    try:
        fix_structure()
    except KeyboardInterrupt:
        print("\n用户中断")
