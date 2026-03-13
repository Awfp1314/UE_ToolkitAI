# -*- coding: utf-8 -*-
"""
从备份配置恢复缩略图路径
"""
import json
from pathlib import Path
import shutil

def restore_thumbnails_from_backup():
    config_path = Path("E:/UE_Asset/.asset_config/config.json")
    backup_path = Path("E:/UE_Asset/.asset_config/backup/config_20260310_182202.json")
    
    if not backup_path.exists():
        print(f"备份文件不存在: {backup_path}")
        return

    print(f"从备份恢复缩略图: {backup_path.name}")
    
    with open(config_path, 'r', encoding='utf-8') as f:
        current_config = json.load(f)
        
    with open(backup_path, 'r', encoding='utf-8') as f:
        backup_config = json.load(f)
        
    # 构建备份资产的映射 (name -> asset_data)
    backup_assets = {a.get('name'): a for a in backup_config.get('assets', [])}
    
    current_assets = current_config.get('assets', [])
    restored_count = 0
    
    print("-" * 60)
    
    for asset in current_assets:
        name = asset.get('name')
        current_thumb = asset.get('thumbnail_path', '')
        
        # 如果当前没有缩略图，或者缩略图文件不存在
        needs_restore = False
        if not current_thumb:
            needs_restore = True
        elif not Path(current_thumb).exists():
            needs_restore = True
            
        if needs_restore:
            backup_asset = backup_assets.get(name)
            if backup_asset:
                backup_thumb = backup_asset.get('thumbnail_path', '')
                if backup_thumb and Path(backup_thumb).exists():
                    asset['thumbnail_path'] = backup_thumb
                    print(f"✓ 恢复: {name}")
                    print(f"  路径: {backup_thumb}")
                    restored_count += 1
                else:
                    if backup_thumb:
                        print(f"✗ 备份中有路径但文件不存在: {name} -> {backup_thumb}")
                    else:
                        print(f"✗ 备份中也无缩略图: {name}")
            else:
                print(f"✗ 备份中未找到资产: {name}")
    
    print("-" * 60)
    
    if restored_count > 0:
        # 保存更新后的配置
        # 先备份当前配置
        shutil.copy2(config_path, config_path.parent / "config_before_restore_thumbs.json")
        
        with open(config_path, 'w', encoding='utf-8') as f:
            json.dump(current_config, f, ensure_ascii=False, indent=2)
            
        print(f"成功恢复 {restored_count} 个资产的缩略图路径！")
    else:
        print("没有可恢复的缩略图路径。")

if __name__ == "__main__":
    restore_thumbnails_from_backup()
