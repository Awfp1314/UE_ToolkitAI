# -*- coding: utf-8 -*-
"""
修复 BasicUI 结构
将 Content 下的文件移动到 Content/BasicUI 下
"""
import shutil
from pathlib import Path

def fix_basic_ui():
    asset_path = Path("E:/UE_Asset/UI/BasicUI")
    content_dir = asset_path / "Content"
    
    if not content_dir.exists():
        print("BasicUI Content 目录不存在")
        return

    # 检查是否已经修复
    target_dir = content_dir / "BasicUI"
    if target_dir.exists():
        # 检查Content下是否还有文件
        files_in_content = [f for f in content_dir.iterdir() if f.is_file()]
        if not files_in_content:
            print("BasicUI 结构看似已经正确")
            return

    print(f"正在修复 BasicUI 结构: {asset_path}")
    
    # 创建目标文件夹
    target_dir.mkdir(parents=True, exist_ok=True)
    
    # 移动文件和文件夹（除了目标文件夹自己）
    moved_count = 0
    for item in content_dir.iterdir():
        if item == target_dir:
            continue
            
        dest = target_dir / item.name
        print(f"  移动: {item.name}")
        shutil.move(str(item), str(dest))
        moved_count += 1
        
    print(f"完成! 移动了 {moved_count} 个项目")

if __name__ == "__main__":
    fix_basic_ui()
