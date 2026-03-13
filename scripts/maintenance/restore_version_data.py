# -*- coding: utf-8 -*-
"""
恢复资产版本数据脚本
从备份配置文件中恢复 engine_min_version 字段
"""
import json
from pathlib import Path

def restore_version_data():
    """从备份恢复版本数据"""
    current_path = Path(r"E:\UE_Asset\.asset_config\config.json")
    backup_path = Path(r"E:\UE_Asset\.asset_config\config_before_version_detect.json")
    
    if not current_path.exists():
        print(f"错误：当前配置文件不存在: {current_path}")
        return False
    
    if not backup_path.exists():
        print(f"错误：备份配置文件不存在: {backup_path}")
        return False
    
    # 读取配置文件
    current = json.loads(current_path.read_text(encoding='utf-8'))
    backup = json.loads(backup_path.read_text(encoding='utf-8'))
    
    # 创建备份映射（使用资产名称作为key，因为路径可能已更改）
    backup_map = {}
    for asset in backup.get('assets', []):
        name = asset['name']
        backup_map[name] = asset
    
    # 恢复版本数据
    updated_count = 0
    for asset in current.get('assets', []):
        # 跳过已有版本的资产
        if asset.get('engine_min_version'):
            continue
        
        # 从备份中查找（使用名称匹配）
        name = asset['name']
        source = backup_map.get(name)
        if source:
            version = source.get('engine_min_version')
            if version:
                asset['engine_min_version'] = version
                updated_count += 1
                print(f"✅ 恢复版本: {asset['name']} -> {version}")
    
    if updated_count > 0:
        # 保存更新后的配置
        current_path.write_text(json.dumps(current, ensure_ascii=False, indent=2), encoding='utf-8')
        print(f"\n成功恢复 {updated_count} 个资产的版本数据")
        return True
    else:
        print("无需更新，所有资产已有版本数据")
        return False

if __name__ == "__main__":
    restore_version_data()
