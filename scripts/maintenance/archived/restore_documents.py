# -*- coding: utf-8 -*-
"""
从备份恢复资产文档
"""
import json
import shutil
from pathlib import Path

def restore_documents():
    config_path = Path("E:/UE_Asset/.asset_config/config.json")
    backup_path = Path("E:/UE_Asset/.asset_config/backup/config_20260310_182202.json")
    documents_dir = Path("E:/UE_Asset/.asset_config/documents")
    
    if not documents_dir.exists():
        documents_dir.mkdir(parents=True)

    if not backup_path.exists():
        print(f"备份文件不存在: {backup_path}")
        return

    print(f"正在从备份恢复文档...")
    
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
        current_id = asset.get('id')
        
        # 检查当前文档是否存在
        current_doc_path = documents_dir / f"{current_id}.txt"
        
        if not current_doc_path.exists():
            # 尝试从备份恢复
            backup_asset = backup_assets.get(name)
            if backup_asset:
                backup_id = backup_asset.get('id')
                backup_doc_path = documents_dir / f"{backup_id}.txt"
                
                if backup_doc_path.exists():
                    try:
                        shutil.copy2(backup_doc_path, current_doc_path)
                        print(f"✓ 恢复文档: {name}")
                        print(f"  {backup_id}.txt -> {current_id}.txt")
                        restored_count += 1
                    except Exception as e:
                        print(f"✗ 复制失败 {name}: {e}")
                else:
                    print(f"✗ 备份文档也不存在: {name} (Backup ID: {backup_id})")
            else:
                print(f"✗ 备份中未找到资产: {name}")
        else:
            print(f"✓ 文档已存在: {name}")
            
    print("-" * 60)
    print(f"文档恢复完成: {restored_count} 个")

if __name__ == "__main__":
    restore_documents()
