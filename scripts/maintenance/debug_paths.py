# -*- coding: utf-8 -*-
"""调试路径匹配问题"""
import json
from pathlib import Path

current_path = Path(r"E:\UE_Asset\.asset_config\config.json")
backup_path = Path(r"E:\UE_Asset\.asset_config\config_before_version_detect.json")

current = json.loads(current_path.read_text(encoding='utf-8'))
backup = json.loads(backup_path.read_text(encoding='utf-8'))

print("=== 备份配置中的资产路径 ===")
for asset in backup.get('assets', []):
    if asset.get('engine_min_version'):
        print(f"{asset['name']}: {asset['path']}")

print("\n=== 当前配置中缺失版本的资产路径 ===")
for asset in current.get('assets', []):
    if not asset.get('engine_min_version'):
        print(f"{asset['name']}: {asset['path']}")
