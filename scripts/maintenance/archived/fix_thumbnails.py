# -*- coding: utf-8 -*-
"""
修复缩略图路径
"""
import json
from pathlib import Path

def fix_thumbnails():
    config_path = Path("E:/UE_Asset/.asset_config/config.json")
    thumbnails_dir = Path("E:/UE_Asset/.asset_config/thumbnails")
    
    with open(config_path, 'r', encoding='utf-8') as f:
        config = json.load(f)
    
    assets = config.get('assets', [])
    
    print(f"修复 {len(assets)} 个资产的缩略图路径...")
    print("=" * 70)
    
    fixed = 0
    
    for asset in assets:
        asset_id = asset.get('id', '')
        name = asset.get('name', '')
        
        # 检查是否有对应的缩略图文件
        thumb_file = thumbnails_dir / f"{asset_id}.png"
        
        if thumb_file.exists():
            # 更新缩略图路径
            asset['thumbnail_path'] = str(thumb_file)
            print(f"✓ {name} -> {thumb_file}")
            fixed += 1
        else:
            # 检查是否路径存在但ID不匹配
            # 可能是文件夹重命名导致的问题
            asset_path = Path(asset.get('path', ''))
            if asset_path.exists():
                # 查找该资产文件夹下的截图
                screenshots = list(asset_path.rglob("*.png"))
                if screenshots:
                    # 使用第一个找到的截图
                    asset['thumbnail_path'] = str(screenshots[0])
                    print(f"✓ {name} -> 找到截图: {screenshots[0]}")
                    fixed += 1
                else:
                    print(f"✗ {name} -> 无缩略图文件")
            else:
                print(f"✗ {name} -> 资产路径不存在")
    
    # 保存配置
    if fixed > 0:
        backup_path = config_path.parent / "config_before_fix_thumbnails.json"
        import shutil
        shutil.copy2(config_path, backup_path)
        print(f"\n已备份配置: {backup_path}")
        
        with open(config_path, 'w', encoding='utf-8') as f:
            json.dump(config, f, ensure_ascii=False, indent=2)
        
        print(f"\n修复完成: {fixed}/{len(assets)}")
    else:
        print("\n没有需要修复的缩略图")

if __name__ == "__main__":
    fix_thumbnails()
