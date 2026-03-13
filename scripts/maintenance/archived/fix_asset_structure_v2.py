# -*- coding: utf-8 -*-
"""
修复资产文件夹嵌套结构 v2

正确结构：自定义名称/Content/原始资产文件夹/Maps等
错误结构：自定义名称/Content/Maps等（缺少原始资产文件夹层级）

检测方法：Content下应该只有一个资产文件夹，而不是直接的UE内容文件夹
"""
import json
import shutil
from pathlib import Path

def check_asset_structure():
    """检查资产结构"""
    
    config_path = Path("E:/UE_Asset/.asset_config/config.json")
    
    if not config_path.exists():
        print(f"配置文件不存在: {config_path}")
        return
    
    with open(config_path, 'r', encoding='utf-8') as f:
        config = json.load(f)
    
    assets = config.get('assets', [])
    
    print(f"检查 {len(assets)} 个资产的结构...")
    print("=" * 70)
    
    # UE常见的内容文件夹名称
    ue_content_folders = {
        'Maps', 'Map', 'Blueprints', 'Blueprint', 'Materials', 'Material',
        'Textures', 'Texture', 'Meshes', 'Mesh', 'Animations', 'Animation',
        'Characters', 'Character', 'Effects', 'Effect', 'Sounds', 'Sound', 
        'Audio', 'Particles', 'Particle', 'Niagara', 'Cinematics', 'Sequences',
        'Data', 'Environment', 'Props', 'Prop', 'Weapons', 'Weapon', 
        'Vehicles', 'Vehicle', 'UI', 'Widgets', 'Widget', 'AI', 'GameFramework',
        'Core', 'Shared', 'Common', 'MaterialFunction', 'MaterialFunctions',
        'Master_Material', 'IES', 'LUT', 'Share_Materials'
    }
    
    need_fix = []
    
    for asset in assets:
        asset_name = asset.get('name', 'Unknown')
        asset_path = Path(asset.get('path', ''))
        
        if not asset_path.exists():
            print(f"⚠️  路径不存在: {asset_name}")
            continue
        
        content_folder = asset_path / "Content"
        
        if not content_folder.exists():
            print(f"⚠️  无Content: {asset_name}")
            continue
        
        content_items = [d for d in content_folder.iterdir() if d.is_dir()]
        
        if not content_items:
            print(f"⚠️  Content为空: {asset_name}")
            continue
        
        # 检查Content下的文件夹是否都是UE内容文件夹
        # 如果是，说明缺少资产文件夹层级
        ue_folders = [d for d in content_items if d.name in ue_content_folders]
        non_ue_folders = [d for d in content_items if d.name not in ue_content_folders]
        
        # 打印当前结构
        folder_names = [d.name for d in content_items]
        
        if len(ue_folders) > 0 and len(non_ue_folders) == 0:
            # 全是UE文件夹，完全缺少资产层级
            print(f"❌ 完全错误: {asset_name}")
            print(f"   Content下: {folder_names}")
            need_fix.append({
                'name': asset_name,
                'path': asset_path,
                'content_folder': content_folder,
                'all_folders': content_items,
                'fix_type': 'create_wrapper'  # 需要创建包装文件夹
            })
        elif len(ue_folders) > 0 and len(non_ue_folders) > 0:
            # 混合情况：有UE文件夹也有非UE文件夹
            # 检查非UE文件夹是否是正确的资产文件夹（应该包含UE内容）
            valid_asset_folder = None
            for nuf in non_ue_folders:
                sub_items = [d.name for d in nuf.iterdir() if d.is_dir()]
                if any(s in ue_content_folders for s in sub_items):
                    valid_asset_folder = nuf
                    break
            
            if valid_asset_folder:
                # 有正确的资产文件夹，但也有错误的UE文件夹在Content下
                print(f"⚠️  部分错误: {asset_name}")
                print(f"   正确资产文件夹: {valid_asset_folder.name}")
                print(f"   错误的UE文件夹: {[d.name for d in ue_folders]}")
                need_fix.append({
                    'name': asset_name,
                    'path': asset_path,
                    'content_folder': content_folder,
                    'ue_folders': ue_folders,
                    'target_folder': valid_asset_folder,
                    'fix_type': 'move_to_existing'  # 移动到现有资产文件夹
                })
            else:
                print(f"✓ 结构正确: {asset_name} -> {folder_names}")
        else:
            # 没有UE文件夹在Content下，结构正确
            print(f"✓ 结构正确: {asset_name} -> {folder_names}")
    
    print("=" * 70)
    print(f"\n发现 {len(need_fix)} 个需要修复的资产")
    
    if need_fix:
        print("\n需要修复的资产：")
        for i, item in enumerate(need_fix, 1):
            print(f"\n{i}. {item['name']} ({item['fix_type']})")
            if item['fix_type'] == 'create_wrapper':
                print(f"   将创建资产文件夹并移动所有内容进去")
            else:
                print(f"   将UE文件夹移动到: {item['target_folder'].name}/")
        
        choice = input("\n是否修复？(y/n): ").strip().lower()
        
        if choice == 'y':
            fix_assets(need_fix)
        else:
            print("已取消")

def fix_assets(need_fix):
    """执行修复"""
    fixed = 0
    for item in need_fix:
        try:
            print(f"\n修复: {item['name']}")
            
            if item['fix_type'] == 'create_wrapper':
                # 创建资产文件夹并移动所有内容
                content_folder = item['content_folder']
                asset_name = item['name']
                
                # 创建临时文件夹
                temp_folder = content_folder.parent / "Content_temp"
                temp_folder.mkdir(exist_ok=True)
                
                # 移动所有内容到临时文件夹
                for folder in item['all_folders']:
                    dest = temp_folder / folder.name
                    print(f"  移动: {folder.name} -> temp/")
                    shutil.move(str(folder), str(dest))
                
                # 创建资产文件夹
                asset_folder = content_folder / asset_name
                asset_folder.mkdir(exist_ok=True)
                
                # 移动临时文件夹内容到资产文件夹
                for sub in temp_folder.iterdir():
                    dest = asset_folder / sub.name
                    print(f"  移动: temp/{sub.name} -> {asset_name}/")
                    shutil.move(str(sub), str(dest))
                
                # 删除临时文件夹
                temp_folder.rmdir()
                
            else:  # move_to_existing
                target = item['target_folder']
                for ue_folder in item['ue_folders']:
                    dest = target / ue_folder.name
                    if dest.exists():
                        # 合并
                        print(f"  合并: {ue_folder.name} -> {target.name}/")
                        for sub in ue_folder.iterdir():
                            sub_dest = dest / sub.name
                            if sub_dest.exists():
                                if sub_dest.is_dir():
                                    shutil.rmtree(sub_dest)
                                else:
                                    sub_dest.unlink()
                            shutil.move(str(sub), str(sub_dest))
                        ue_folder.rmdir()
                    else:
                        print(f"  移动: {ue_folder.name} -> {target.name}/")
                        shutil.move(str(ue_folder), str(dest))
            
            print(f"  ✓ 完成")
            fixed += 1
        except Exception as e:
            print(f"  ✗ 失败: {e}")
            import traceback
            traceback.print_exc()
    
    print(f"\n修复完成: {fixed}/{len(need_fix)}")

if __name__ == "__main__":
    try:
        check_asset_structure()
    except KeyboardInterrupt:
        print("\n用户中断")
