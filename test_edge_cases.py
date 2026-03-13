# -*- coding: utf-8 -*-

"""
测试边界情况：用户直接选择 Content 文件夹
"""

import sys
import shutil
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from modules.asset_manager.logic.asset_model import PackageType
from modules.asset_manager.utils.asset_structure_analyzer import AssetStructureAnalyzer


def test_content_folder_selection():
    """测试用户直接选择 Content 文件夹的情况"""
    test_dir = Path(__file__).parent / "test_edge_cases_temp"
    
    # 清理
    if test_dir.exists():
        shutil.rmtree(test_dir)
    test_dir.mkdir()
    
    print("=" * 70)
    print("测试边界情况：用户直接选择 Content 文件夹")
    print("=" * 70)
    
    analyzer = AssetStructureAnalyzer()
    
    # 场景 1: 用户选择了 Content 文件夹本身（包含 .uasset）
    print("\n场景 1: 用户选择 Content 文件夹本身")
    content_dir = test_dir / "Content"
    content_dir.mkdir()
    (content_dir / "Material.uasset").write_bytes(b"FAKE")
    (content_dir / "Blueprint.uasset").write_bytes(b"FAKE")
    (content_dir / "Textures").mkdir()
    (content_dir / "Textures" / "BaseColor.uasset").write_bytes(b"FAKE")
    
    result = analyzer.analyze(content_dir)
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
    
    print(f"  路径: {content_dir}")
    print(f"  检测类型: {detected.value}")
    print(f"  结构类型: {result.structure_type.value}")
    print(f"  描述: {result.description}")
    print(f"  期望: content")
    print(f"  结果: {'✅ 通过' if detected == PackageType.CONTENT else '❌ 失败'}")
    
    # 场景 2: 用户选择了包含 Content 的父文件夹
    print("\n场景 2: 用户选择包含 Content 的父文件夹")
    parent_dir = test_dir / "MyAsset"
    parent_dir.mkdir()
    (parent_dir / "Content").mkdir()
    (parent_dir / "Content" / "Asset.uasset").write_bytes(b"FAKE")
    
    result2 = analyzer.analyze(parent_dir)
    detected2 = type_map.get(result2.structure_type.value, PackageType.CONTENT)
    
    print(f"  路径: {parent_dir}")
    print(f"  检测类型: {detected2.value}")
    print(f"  结构类型: {result2.structure_type.value}")
    print(f"  描述: {result2.description}")
    print(f"  期望: content")
    print(f"  结果: {'✅ 通过' if detected2 == PackageType.CONTENT else '❌ 失败'}")
    
    # 场景 3: 用户选择了 Content 子文件夹（如 Content/Materials）
    print("\n场景 3: 用户选择 Content 的子文件夹")
    materials_dir = content_dir / "Materials"
    materials_dir.mkdir(exist_ok=True)
    (materials_dir / "M_Base.uasset").write_bytes(b"FAKE")
    (materials_dir / "M_Metal.uasset").write_bytes(b"FAKE")
    
    result3 = analyzer.analyze(materials_dir)
    detected3 = type_map.get(result3.structure_type.value, PackageType.CONTENT)
    
    print(f"  路径: {materials_dir}")
    print(f"  检测类型: {detected3.value}")
    print(f"  结构类型: {result3.structure_type.value}")
    print(f"  描述: {result3.description}")
    print(f"  期望: content 或 loose_assets")
    print(f"  结果: {'✅ 通过' if detected3 in [PackageType.CONTENT, PackageType.OTHERS] else '❌ 失败'}")
    
    # 场景 4: Content 文件夹为空
    print("\n场景 4: 空的 Content 文件夹")
    empty_content = test_dir / "EmptyContent"
    empty_content.mkdir()
    
    result4 = analyzer.analyze(empty_content)
    detected4 = type_map.get(result4.structure_type.value, PackageType.CONTENT)
    
    print(f"  路径: {empty_content}")
    print(f"  检测类型: {detected4.value}")
    print(f"  结构类型: {result4.structure_type.value}")
    print(f"  描述: {result4.description}")
    print(f"  期望: unknown 或 others")
    print(f"  结果: {'✅ 通过' if detected4 == PackageType.OTHERS else '❌ 失败'}")
    
    # 场景 5: Content 文件夹只有非 UE 资产
    print("\n场景 5: Content 文件夹只有非 UE 资产（FBX/PNG）")
    mixed_content = test_dir / "MixedContent"
    mixed_content.mkdir()
    (mixed_content / "model.fbx").write_bytes(b"FAKE_FBX")
    (mixed_content / "texture.png").write_bytes(b"FAKE_PNG")
    
    result5 = analyzer.analyze(mixed_content)
    detected5 = type_map.get(result5.structure_type.value, PackageType.CONTENT)
    
    print(f"  路径: {mixed_content}")
    print(f"  检测类型: {detected5.value}")
    print(f"  结构类型: {result5.structure_type.value}")
    print(f"  描述: {result5.description}")
    print(f"  期望: others")
    print(f"  结果: {'✅ 通过' if detected5 == PackageType.OTHERS else '❌ 失败'}")
    
    # 清理
    print("\n" + "=" * 70)
    shutil.rmtree(test_dir)
    print("测试完成，已清理临时文件")
    print("=" * 70)


if __name__ == "__main__":
    test_content_folder_selection()
