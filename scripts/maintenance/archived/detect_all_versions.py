# -*- coding: utf-8 -*-
"""
批量检测所有资产的引擎版本并更新配置文件
"""
import json
import sys
from pathlib import Path

# 添加模块路径
sys.path.insert(0, str(Path(__file__).parent))

from modules.asset_manager.utils.ue_version_detector import UEVersionDetector
from core.logger import get_logger

logger = get_logger(__name__)

def detect_all_asset_versions():
    """检测所有资产的版本并更新配置"""
    
    # 配置文件路径
    config_path = Path("E:/UE_Asset/.asset_config/config.json")
    
    if not config_path.exists():
        logger.error(f"配置文件不存在: {config_path}")
        return
    
    # 读取配置
    logger.info(f"读取配置文件: {config_path}")
    with open(config_path, 'r', encoding='utf-8') as f:
        config = json.load(f)
    
    assets = config.get('assets', [])
    total = len(assets)
    logger.info(f"共有 {total} 个资产需要检测版本")
    
    # 创建版本检测器
    version_detector = UEVersionDetector(logger)
    
    # 遍历检测
    updated_count = 0
    for i, asset in enumerate(assets, 1):
        asset_path_str = asset.get('path', '')
        asset_name = asset.get('name', 'Unknown')
        
        if not asset_path_str:
            logger.warning(f"[{i}/{total}] 跳过: {asset_name} (无路径)")
            continue
        
        asset_path = Path(asset_path_str)
        
        # 检测版本
        logger.info(f"[{i}/{total}] 检测: {asset_name}")
        try:
            version = version_detector.detect_asset_min_version(asset_path)
            
            if version:
                asset['engine_min_version'] = version
                updated_count += 1
                logger.info(f"  ✓ 版本: {version}")
            else:
                asset['engine_min_version'] = ""
                logger.warning(f"  ✗ 未检测到版本")
                
        except Exception as e:
            logger.error(f"  ✗ 检测失败: {e}")
            asset['engine_min_version'] = ""
    
    # 备份原配置
    backup_path = config_path.parent / f"config_before_version_detect.json"
    logger.info(f"备份原配置到: {backup_path}")
    with open(backup_path, 'w', encoding='utf-8') as f:
        json.dump(config, f, ensure_ascii=False, indent=2)
    
    # 保存更新后的配置
    logger.info(f"保存更新后的配置到: {config_path}")
    with open(config_path, 'w', encoding='utf-8') as f:
        json.dump(config, f, ensure_ascii=False, indent=2)
    
    logger.info(f"✓ 完成! 共更新 {updated_count}/{total} 个资产的版本信息")
    print(f"\n{'='*60}")
    print(f"版本检测完成!")
    print(f"总资产数: {total}")
    print(f"成功检测: {updated_count}")
    print(f"配置已更新: {config_path}")
    print(f"备份位置: {backup_path}")
    print(f"{'='*60}\n")

if __name__ == "__main__":
    try:
        detect_all_asset_versions()
    except KeyboardInterrupt:
        print("\n用户中断")
    except Exception as e:
        logger.error(f"执行失败: {e}", exc_info=True)
        sys.exit(1)
