# -*- coding: utf-8 -*-
"""
检查缩略图和文档路径问题
"""
import json
from pathlib import Path

def check_assets():
    config_path = Path("E:/UE_Asset/.asset_config/config.json")
    thumbnails_dir = Path("E:/UE_Asset/.asset_config/thumbnails")
    
    with open(config_path, 'r', encoding='utf-8') as f:
        config = json.load(f)
    
    assets = config.get('assets', [])
    
    print(f"检查 {len(assets)} 个资产的缩略图和文档...")
    print("=" * 70)
    
    missing_thumbs = []
    missing_docs = []
    
    for asset in assets:
        name = asset.get('name', '')
        asset_id = asset.get('id', '')
        thumb_path = asset.get('thumbnail_path', '')
        
        # 检查缩略图
        if thumb_path:
            if not Path(thumb_path).exists():
                missing_thumbs.append({
                    'name': name,
                    'id': asset_id,
                    'path': thumb_path
                })
            else:
                # 检查ID对应的缩略图文件
                thumb_file = thumbnails_dir / f"{asset_id}.png"
                if not thumb_file.exists():
                    missing_thumbs.append({
                        'name': name,
                        'id': asset_id,
                        'path': thumb_path
                    })
        else:
            missing_thumbs.append({
                'name': name,
                'id': asset_id,
                'path': '无路径'
            })
    
    print(f"\n缺失缩略图: {len(missing_thumbs)}")
    if missing_thumbs:
        print("\n列表:")
        for i, item in enumerate(missing_thumbs[:10], 1):  # 只显示前10个
            print(f"{i}. {item['name']} -> {item['path']}")
        if len(missing_thumbs) > 10:
            print(f"... 还有 {len(missing_thumbs) - 10} 个")
    
    print("\n" + "=" * 70)
    
    # 检查文档
    documents_dir = Path("E:/UE_Asset/.asset_config/documents")
    if documents_dir.exists():
        doc_files = list(documents_dir.glob("*.txt"))
        print(f"\n文档文件夹存在，共 {len(doc_files)} 个文档文件")
        
        # 检查每个资产是否有对应文档
        for asset in assets[:5]:
            doc_file = documents_dir / f"{asset.get('id')}.txt"
            if doc_file.exists():
                print(f"✓ {asset.get('name')} 有文档")
            else:
                print(f"✗ {asset.get('name')} 无文档")

if __name__ == "__main__":
    check_assets()
