# -*- coding: utf-8 -*-
"""
修复资产文件夹嵌套结构

问题描述：
同步逻辑错误导致资产结构被破坏
- 错误结构：自定义名称/Content/Maps（直接把内容放到Content下）
- 正确结构：自定义名称/Content/原始资产文件夹/Maps

这个脚本检测并修复被破坏的资产结构
"""
import json
import shutil
from pathlib import Path

def check_and_fix_asset_structure():
    """检查并修复资产结构"""
    
    # 配置文件路径
    config_path = Path("E:/UE_Asset/.asset_config/config.json")
    
    if not config_path.exists():
        print(f"配置文件不存在: {config_path}")
        return
    
    # 读取配置
    with open(config_path, 'r', encoding='utf-8') as f:
        config = json.load(f)
    
    assets = config.get('assets', [])
    
    print(f"检查 {len(assets)} 个资产的结构...")
    print("=" * 60)
    
    # UE常见的内容文件夹名称（这些不应该直接出现在Content下）
    ue_content_folders = {
        'Maps', 'Blueprints', 'Materials', 'Textures', 'Meshes', 
        'Animations', 'Characters', 'Effects', 'Sounds', 'Audio',
        'Particles', 'Niagara', 'Cinematics', 'Sequences', 'Data',
        'Environment', 'Props', 'Weapons', 'Vehicles', 'UI', 'Widgets',
        'AI', 'GameFramework', 'Core', 'Shared', 'Common'
    }
    
    need_fix = []
    
    for asset in assets:
        asset_name = asset.get('name', 'Unknown')
        asset_path = Path(asset.get('path', ''))
        
        if not asset_path.exists():
            print(f"⚠️  跳过（路径不存在）: {asset_name}")
            continue
        
        content_folder = asset_path / "Content"
        
        if not content_folder.exists():
            print(f"⚠️  无Content文件夹: {asset_name}")
            continue
        
        content_items = list(content_folder.iterdir())
        
        if not content_items:
            print(f"⚠️  Content为空: {asset_name}")
            continue
        
        # 检查Content下是否直接包含UE内容文件夹（这是错误的）
        direct_ue_folders = []
        asset_folders = []
        
        for item in content_items:
            if item.is_dir():
                if item.name in ue_content_folders:
                    direct_ue_folders.append(item)
                else:
                    asset_folders.append(item)
        
        if direct_ue_folders:
            # 发现错误结构：Content下直接有Maps等UE文件夹
            print(f"❌ 错误结构: {asset_name}")
            print(f"   路径: {asset_path}")
            print(f"   Content下直接有: {[f.name for f in direct_ue_folders]}")
            need_fix.append({
                'name': asset_name,
                'path': asset_path,
                'content_folder': content_folder,
                'direct_ue_folders': direct_ue_folders,
                'asset_folders': asset_folders
            })
        else:
            print(f"✓ 结构正确: {asset_name}")
    
    print("=" * 60)
    print(f"\n发现 {len(need_fix)} 个需要修复的资产")
    
    if need_fix:
        print("\n需要修复的资产列表：")
        for i, item in enumerate(need_fix, 1):
            print(f"{i}. {item['name']}")
            print(f"   错误的UE文件夹: {[f.name for f in item['direct_ue_folders']]}")
            if item['asset_folders']:
                print(f"   正常的资产文件夹: {[f.name for f in item['asset_folders']]}")
        
        print("\n修复方案：")
        print("  将错误的UE文件夹移动到正确的资产子文件夹中")
        print("  如果没有资产子文件夹，将创建一个以资产名命名的文件夹")
        
        choice = input("\n是否修复这些资产？(y/n): ").strip().lower()
        
        if choice == 'y':
            fixed_count = 0
            for item in need_fix:
                try:
                    asset_name = item['name']
                    content_folder = item['content_folder']
                    direct_ue_folders = item['direct_ue_folders']
                    asset_folders = item['asset_folders']
                    
                    print(f"\n修复: {asset_name}")
                    
                    # 确定目标资产文件夹
                    if asset_folders:
                        # 如果有正常的资产文件夹，移动到第一个
                        target_folder = asset_folders[0]
                        print(f"  移动到现有资产文件夹: {target_folder.name}")
                    else:
                        # 创建新的资产文件夹
                        target_folder = content_folder / asset_name
                        target_folder.mkdir(parents=True, exist_ok=True)
                        print(f"  创建新资产文件夹: {target_folder.name}")
                    
                    # 移动错误的UE文件夹到目标文件夹
                    for ue_folder in direct_ue_folders:
                        dest = target_folder / ue_folder.name
                        if dest.exists():
                            # 如果目标已存在，合并内容
                            print(f"  合并: {ue_folder.name} -> {target_folder.name}/{ue_folder.name}")
                            for sub_item in ue_folder.iterdir():
                                sub_dest = dest / sub_item.name
                                if sub_dest.exists():
                                    if sub_dest.is_dir():
                                        shutil.rmtree(sub_dest)
                                    else:
                                        sub_dest.unlink()
                                shutil.move(str(sub_item), str(sub_dest))
                            # 删除空的源文件夹
                            ue_folder.rmdir()
                        else:
                            print(f"  移动: {ue_folder.name} -> {target_folder.name}/{ue_folder.name}")
                            shutil.move(str(ue_folder), str(dest))
                    
                    print(f"  ✓ 修复完成")
                    fixed_count += 1
                    
                except Exception as e:
                    print(f"  ✗ 修复失败: {e}")
                    import traceback
                    traceback.print_exc()
            
            print(f"\n修复完成! 成功: {fixed_count}/{len(need_fix)}")
        else:
            print("已取消")
    else:
        print("\n所有资产结构正确，无需修复！")

if __name__ == "__main__":
    try:
        check_and_fix_asset_structure()
    except KeyboardInterrupt:
        print("\n\n用户中断")
    except Exception as e:
        print(f"\n执行失败: {e}")
        import traceback
        traceback.print_exc()
