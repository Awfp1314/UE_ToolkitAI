# -*- coding: utf-8 -*-

"""
测试用户选择 Content 子文件夹的情况
例如：Content/MyAsset/ 用户选择了 MyAsset
"""

import sys
import shutil
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from modules.asset_manager.logic.asset_model import PackageType
from modules.asset_manager.utils.asset_structure_analyzer import AssetStructureAnalyzer


def test_content_subfolder_selection():
    """测试用户选择 Content 子文件夹的情况"""
    test_dir = Path(__file__).parent / "test_subfolder_temp"
    
    if test_dir.exists():
        shutil.rmtree(test_dir)
    test_dir.mkdir()
    
    print("=" * 70)
    print("测试：用户选择 Content 的子文件夹（资产文件夹）")
    print("=" * 70)
    
    analyzer = AssetStructureAnalyzer()
    
    # 场景：Content/MyAsset/ 结构，用户选择了 MyAsset
    print("\n场景：用户选择了 Content/MyAsset 中的 MyAsset 文件夹")
    print("（这是一个典型的资产包内部结构）")
    
    # 创建完整结构
    full_structure = test_dir / "FullPackage"
    content_dir = full_structure / "Content"
    asset_dir = content_dir / "MyAsset"
    asset_dir.mkdir(parents=True)
    
    # 在 MyAsset 下创建资产
    (asset_dir / "Material.uasset").write_bytes(b"FAKE")
    (asset_dir / "Blueprint.uasset").write_bytes(b"FAKE")
    (asset_dir / "Textures").mkdir()
    (asset_dir / "Textures" / "BaseColor.uasset").write_bytes(b"FAKE")
    
    print(f"\n完整结构：")
    print(f"  {full_structure}/")
    print(f"    Content/")
    print(f"      MyAsset/  ← 用户选择了这个")
    print(f"        Material.uasset")
    print(f"        Blueprint.uasset")
    print(f"        Textures/")
    print(f"          BaseColor.uasset")
    
    # 测试：用户选择了 MyAsset 文件夹
    result = analyzer.analyze(asset_dir)
    
    type_map = {
        'content_package': PackageType.CONTENT,
        'ue_project': PackageType.PROJECT,
        'ue_plugin': PackageType.PLUGIN,
        'loose_assets': PackageType.OTHERS,
        'raw_3d_files': PackageType.OTHERS,
        'mixed_files': PackageType.OTHERS,
        'unknown': PackageType.OTHERS,
    }
    detected = type_map.get(result.structure_type.value, PackageType.CONTENT)
    
    print(f"\n分析结果：")
    print(f"  路径: {asset_dir}")
    print(f"  检测类型: {detected.value}")
    print(f"  结构类型: {result.structure_type.value}")
    print(f"  描述: {result.description}")
    print(f"\n问题分析：")
    print(f"  期望: CONTENT（因为这是资产包的一部分）")
    print(f"  实际: {detected.value}")
    
    if detected == PackageType.OTHERS:
        print(f"  ❌ 被误判为 OTHERS（散装资产）")
        print(f"\n原因：MyAsset 文件夹本身没有 Content 子文件夹")
        print(f"      分析器找不到 Content，降级为 loose_assets")
    elif detected == PackageType.CONTENT:
        print(f"  ✅ 正确识别为 CONTENT")
    
    # 清理
    print("\n" + "=" * 70)
    shutil.rmtree(test_dir)
    print("测试完成")
    print("=" * 70)


if __name__ == "__main__":
    test_content_subfolder_selection()
