import json
from collections import Counter
import os

config_path = 'E:/UE_Asset/.asset_config/config.json'

if not os.path.exists(config_path):
    print(f"Config file not found at {config_path}")
    exit(1)

with open(config_path, 'r', encoding='utf-8') as f:
    config = json.load(f)

assets = config.get('assets', [])
names = [a.get('name') for a in assets]
ids = [a.get('id') for a in assets]

name_counts = Counter(names)
id_counts = Counter(ids)

dup_names = {name: count for name, count in name_counts.items() if count > 1}
dup_ids = {id: count for id, count in id_counts.items() if count > 1}

print(f"Total assets in config: {len(assets)}")
print("-" * 30)

if dup_names:
    print(f"Duplicate Names ({len(dup_names)}):")
    for name, count in dup_names.items():
        print(f"  '{name}': {count} times")
else:
    print("No duplicate names found.")

print("-" * 30)

if dup_ids:
    print(f"Duplicate IDs ({len(dup_ids)}):")
    for id, count in dup_ids.items():
        print(f"  '{id}': {count} times")
else:
    print("No duplicate IDs found.")
