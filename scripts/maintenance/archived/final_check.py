# -*- coding: utf-8 -*-
"""
最终检查所有资产状态
"""
import json
from pathlib import Path

def final_check():
    config_path = Path("E:/UE_Asset/.asset_config/config.json")
    if not config_path.exists():
        print("配置文件不存在")
        return

    with open(config_path, 'r', encoding='utf-8') as f:
        config = json.load(f)

    assets = config.get('assets', [])
    print(f"最终检查: {len(assets)} 个资产")
    print("-" * 60)

    issues = []
    for a in assets:
        name = a.get('name', 'Unknown')
        path = a.get('path', '')
        thumb = a.get('thumbnail_path', '')
        tid = a.get('id', '')
        
        # 1. 检查资产路径
        if not path or not Path(path).exists():
            issues.append(f"🔴 路径丢失: {name} -> {path}")
        
        # 2. 检查Content结构
        if Path(path).exists():
            content = Path(path) / "Content"
            if not content.exists():
                issues.append(f"🟠 无Content: {name}")
            else:
                # 检查Content下是否还有子文件夹 (应该是 资产名/Content/原名/...)
                subs = [d for d in content.iterdir() if d.is_dir()]
                if not subs:
                    issues.append(f"🟠 Content为空: {name}")
        
        # 3. 检查缩略图
        if not thumb or not Path(thumb).exists():
            issues.append(f"🟡 缩略图丢失: {name}")
            
        # 4. 检查文档
        doc = Path("E:/UE_Asset/.asset_config/documents") / f"{tid}.txt"
        if not doc.exists():
            issues.append(f"🔵 文档丢失: {name}")

    if not issues:
        print("✅ 所有资产状态正常！")
        print("   - 文件夹结构正确")
        print("   - 缩略图存在")
        print("   - 文档存在")
    else:
        print(f"发现 {len(issues)} 个问题:")
        for i in issues:
            print(f"  {i}")

if __name__ == "__main__":
    final_check()
