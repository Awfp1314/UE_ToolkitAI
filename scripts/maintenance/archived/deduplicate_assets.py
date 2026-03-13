import json
import os
from pathlib import Path

config_path = 'E:/UE_Asset/.asset_config/config.json'

with open(config_path, 'r', encoding='utf-8') as f:
    config = json.load(f)

assets = config.get('assets', [])
name_map = {}

print(f"Total assets: {len(assets)}")
print("-" * 50)

for asset in assets:
    name = asset.get('name')
    if name not in name_map:
        name_map[name] = []
    name_map[name].append(asset)

duplicates_found = False
assets_to_keep = []
ids_to_remove = set()

for name, entries in name_map.items():
    if len(entries) > 1:
        duplicates_found = True
        print(f"Duplicate: {name} ({len(entries)} entries)")
        
        valid_entries = []
        for entry in entries:
            path = entry.get('path', '')
            exists = os.path.exists(path)
            entry['_exists'] = exists
            print(f"  ID: {entry.get('id')} | Path: {path} | Exists: {exists}")
            if exists:
                valid_entries.append(entry)
        
        # Decision logic
        if len(valid_entries) == 1:
            print(f"  -> Keeping valid entry: {valid_entries[0].get('id')}")
            assets_to_keep.append(valid_entries[0])
        elif len(valid_entries) > 1:
            # If multiple valid, prefer the one that matches the expected structure (CustomName == FolderName)
            # or the one with a thumbnail
            best_entry = valid_entries[0]
            for entry in valid_entries:
                path = entry.get('path', '')
                folder_name = os.path.basename(path)
                if folder_name == name:
                    best_entry = entry
                    break
            print(f"  -> Keeping best entry: {best_entry.get('id')} (Path: {best_entry.get('path')})")
            assets_to_keep.append(best_entry)
        else:
            # None exist, keep the first one
            print(f"  -> No valid paths, keeping first entry: {entries[0].get('id')}")
            assets_to_keep.append(entries[0])
    else:
        assets_to_keep.append(entries[0])

if duplicates_found:
    print("-" * 50)
    print(f"Original count: {len(assets)}")
    print(f"New count: {len(assets_to_keep)}")
    
    # Clean up temporary key
    for a in assets_to_keep:
        if '_exists' in a:
            del a['_exists']
            
    # Save
    backup_path = config_path.replace('config.json', 'config_before_dedup.json')
    with open(backup_path, 'w', encoding='utf-8') as f:
        json.dump(config, f, ensure_ascii=False, indent=2)
    print(f"Backup saved to {backup_path}")
    
    config['assets'] = assets_to_keep
    with open(config_path, 'w', encoding='utf-8') as f:
        json.dump(config, f, ensure_ascii=False, indent=2)
    print("Config cleaned and saved.")
else:
    print("No duplicates to clean.")
