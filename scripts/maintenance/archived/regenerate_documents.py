# -*- coding: utf-8 -*-
"""
重新生成缺失的资产文档
"""
import json
from pathlib import Path
from datetime import datetime

def format_size(size):
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if size < 1024.0:
            return f"{size:.2f} {unit}"
        size /= 1024.0
    return f"{size:.2f} PB"

def regenerate_documents():
    config_path = Path("E:/UE_Asset/.asset_config/config.json")
    documents_dir = Path("E:/UE_Asset/.asset_config/documents")
    
    if not documents_dir.exists():
        documents_dir.mkdir(parents=True)
        
    with open(config_path, 'r', encoding='utf-8') as f:
        config = json.load(f)
        
    assets = config.get('assets', [])
    generated_count = 0
    
    print("-" * 60)
    
    for asset in assets:
        asset_id = asset.get('id')
        name = asset.get('name', 'Unknown')
        doc_path = documents_dir / f"{asset_id}.txt"
        
        if not doc_path.exists():
            print(f"生成文档: {name}")
            
            try:
                # 准备文档内容
                asset_type = asset.get('asset_type', 'package')
                category = asset.get('category', '默认分类')
                path = asset.get('path', '')
                size = asset.get('size', 0)
                created_time_str = asset.get('created_time', '')
                try:
                    created_time = datetime.fromisoformat(created_time_str)
                    created_time_display = created_time.strftime('%Y-%m-%d %H:%M:%S')
                except:
                    created_time_display = created_time_str
                
                description = asset.get('description', '')
                
                text_content = f"""资产信息表
{'='*50}

资产名称: {name}
资产ID: {asset_id}
资产类型: {asset_type}
分类: {category}
文件路径: {path}
文件大小: {format_size(size)}
创建时间: {created_time_display}

描述:
{description or '暂无'}

{'='*50}

使用说明:
请在下方添加关于如何使用该资产的详细说明...


备注:
请在下方添加其他备注信息...

"""
                with open(doc_path, 'w', encoding='utf-8') as f:
                    f.write(text_content)
                
                generated_count += 1
                
            except Exception as e:
                print(f"✗ 生成失败 {name}: {e}")
        else:
            # print(f"✓ 文档已存在: {name}")
            pass
            
    print("-" * 60)
    print(f"文档生成完成: {generated_count} 个")

if __name__ == "__main__":
    regenerate_documents()
