# -*- coding: utf-8 -*-
"""
测试版本信息的完整数据流
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from modules.asset_manager.logic.asset_model import Asset, AssetType
from modules.asset_manager.logic.asset_controller import AssetController
from modules.asset_manager.logic.asset_manager_logic import AssetManagerLogic
from core.logger import get_logger
from datetime import datetime

logger = get_logger(__name__)

def test_version_data_flow():
    """测试版本数据流"""
    
    # 1. 读取配置文件
    config_path = Path("E:/UE_Asset/.asset_config/config.json")
    with open(config_path, 'r', encoding='utf-8') as f:
        config = json.load(f)
    
    # 找一个有版本信息的资产
    test_asset_data = None
    for asset_data in config['assets']:
        if asset_data.get('engine_min_version'):
            test_asset_data = asset_data
            break
    
    if not test_asset_data:
        print("没有找到有版本信息的资产！")
        test_asset_data = config['assets'][0]
    
    print(f"\n{'='*60}")
    print(f"1. 配置文件中的资产数据:")
    print(f"{'='*60}")
    print(f"Name: {test_asset_data.get('name')}")
    print(f"engine_min_version: '{test_asset_data.get('engine_min_version')}'")
    
    # 2. 创建Asset对象（模拟扫描器的反序列化）
    asset = Asset(
        id=test_asset_data["id"],
        name=test_asset_data["name"],
        asset_type=AssetType(test_asset_data["asset_type"]),
        path=Path(test_asset_data["path"]),
        category=test_asset_data.get("category", "默认分类"),
        file_extension=test_asset_data.get("file_extension", ""),
        thumbnail_path=Path(test_asset_data["thumbnail_path"]) if test_asset_data.get("thumbnail_path") else None,
        thumbnail_source=test_asset_data.get("thumbnail_source"),
        size=test_asset_data.get("size", 0),
        created_time=datetime.fromisoformat(test_asset_data.get("created_time", datetime.now().isoformat())),
        description=test_asset_data.get("description", ""),
        engine_min_version=test_asset_data.get("engine_min_version", "")
    )
    
    print(f"\n{'='*60}")
    print(f"2. Asset对象:")
    print(f"{'='*60}")
    print(f"Name: {asset.name}")
    print(f"engine_min_version: '{asset.engine_min_version}'")
    print(f"hasattr: {hasattr(asset, 'engine_min_version')}")
    print(f"getattr: '{getattr(asset, 'engine_min_version', 'NOT_FOUND')}'")
    
    # 3. 测试 convert_asset_to_dict 的核心逻辑
    asset_dict = {
        'id': asset.id,
        'name': asset.name,
        'category': asset.category,
        'size': asset.size,
        'path': str(asset.path) if asset.path else None,
        'thumbnail_path': str(asset.thumbnail_path) if asset.thumbnail_path else None,
        'asset_type': (
            asset.asset_type.value
            if hasattr(asset.asset_type, 'value')
            else str(asset.asset_type)
        ),
        'created_time': (
            asset.created_time.isoformat()
            if hasattr(asset.created_time, 'isoformat')
            else str(asset.created_time)
        ),
        'engine_min_version': getattr(asset, 'engine_min_version', ''),
        'has_document': False,
    }
    
    print(f"\n{'='*60}")
    print(f"3. convert_asset_to_dict 结果:")
    print(f"{'='*60}")
    print(f"Name: {asset_dict.get('name')}")
    print(f"engine_min_version: '{asset_dict.get('engine_min_version')}'")
    print(f"完整字典键: {list(asset_dict.keys())}")
    
    # 4. 测试版本徽标格式化
    from modules.asset_manager.utils.ue_version_detector import UEVersionDetector
    version_detector = UEVersionDetector()
    
    version = asset_dict.get('engine_min_version', '')
    badge = version_detector.format_version_badge(version)
    
    print(f"\n{'='*60}")
    print(f"4. 版本徽标:")
    print(f"{'='*60}")
    print(f"原始版本: '{version}'")
    print(f"徽标文本: '{badge}'")
    
    print(f"\n{'='*60}")
    print(f"诊断完成！")
    print(f"{'='*60}\n")

if __name__ == "__main__":
    test_version_data_flow()
