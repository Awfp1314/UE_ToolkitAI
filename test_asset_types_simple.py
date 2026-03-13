# -*- coding: utf-8 -*-

"""
资产类型简化测试脚本 - 直接测试结构分析
"""

import sys
import json
import shutil
import zipfile
from pathlib import Path

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent))

from modules.asset_manager.logic.asset_model import PackageType
from modules.asset_manager.utils.asset_structure_analyzer import AssetStructureAnalyzer


def create_test_assets():
    """创建测试资产"""
    test_dir = Path(__file__).parent / "test_assets_temp"
    
    # 清理旧数据
    if test_dir.exists():
        shutil.rmtree(test_dir)
    test_dir.mkdir()
    
    print("=" * 60)
    print("创建测试资产")
    print("=" * 60)
    
    # 1. CONTENT 类型
    content_dir = test_dir / "ContentAsset"
    (content_dir / "Content").mkdir(parents=True)
    (content_dir / "Content" / "TestMaterial.uasset").write_bytes(b"FAKE_UASSET")
    (content_dir / "Content" / "TestBlueprint.uasset").write_bytes(b"FAKE_UASSET")
    print(f"✅ 创建 CONTENT 资产: {content_dir.name}")
    
    # 2. PROJECT 类型
    project_dir = test_dir / "ProjectAsset"
    project_dir.mkdir()
    uproject_data = {
        "FileVersion": 3,
        "EngineAssociation": "5.4",
        "Category": "",
        "Description": "Test Project"
    }
    (project_dir / "TestProject.uproject").write_text(json.dumps(uproject_data, indent=4))
    (project_dir / "Content").mkdir()
    (project_dir / "Content" / "TestMap.umap").write_bytes(b"FAKE_UMAP")
    print(f"✅ 创建 PROJECT 资产: {project_dir.name}")
    
    # 3. PLUGIN 类型
    plugin_dir = test_dir / "PluginAsset"
    plugin_dir.mkdir()
    uplugin_data = {
        "FileVersion": 3,
        "Version": 1,
        "VersionName": "1.0",
        "FriendlyName": "Test Plugin",
        "EngineVersion": "5.4.0"
    }
    (plugin_dir / "TestPlugin.uplugin").write_text(json.dumps(uplugin_data, indent=4))
    (plugin_dir / "Content").mkdir()
    (plugin_dir / "Content" / "PluginAsset.uasset").write_bytes(b"FAKE_UASSET")
    print(f"✅ 创建 PLUGIN 资产: {plugin_dir.name}")
    
    # 4. OTHERS 类型
    others_dir = test_dir / "OthersAsset"
    others_dir.mkdir()
    (others_dir / "model.fbx").write_bytes(b"FAKE_FBX")
    (others_dir / "texture.png").write_bytes(b"FAKE_PNG")
    (others_dir / "audio.wav").write_bytes(b"FAKE_WAV")
    print(f"✅ 创建 OTHERS 资产: {others_dir.name}")
    
    # 5. CONTENT 压缩包
    content_zip = test_dir / "ContentAsset.zip"
    with zipfile.ZipFile(content_zip, 'w') as zf:
        zf.writestr("Content/Material.uasset", b"FAKE_UASSET")
        zf.writestr("Content/Blueprint.uasset", b"FAKE_UASSET")
    print(f"✅ 创建 CONTENT 压缩包: {content_zip.name}")
    
    # 6. PROJECT 压缩包
    project_zip = test_dir / "ProjectAsset.zip"
    with zipfile.ZipFile(project_zip, 'w') as zf:
        zf.writestr("TestProj.uproject", json.dumps(uproject_data))
        zf.writestr("Content/Map.umap", b"FAKE_UMAP")
    print(f"✅ 创建 PROJECT 压缩包: {project_zip.name}")
    
    print(f"\n测试资产目录: {test_dir}\n")
    return test_dir


def test_structure_detection(test_dir):
    """测试结构检测"""
    print("=" * 60)
    print("测试结构检测")
    print("=" * 60)
    
    analyzer = AssetStructureAnalyzer()
    
    test_cases = [
        ("ContentAsset", PackageType.CONTENT, "文件夹"),
        ("ProjectAsset", PackageType.PROJECT, "文件夹"),
        ("PluginAsset", PackageType.PLUGIN, "文件夹"),
        ("OthersAsset", PackageType.OTHERS, "文件夹"),
    ]
    
    results = []
    
    for name, expected_type, source_type in test_cases:
        asset_path = test_dir / name
        
        print(f"\n测试: {name} ({source_type})")
        print(f"  路径: {asset_path}")
        
        try:
            # 分析结构
            analysis = analyzer.analyze(asset_path)
            
            # 映射 StructureType → PackageType
            type_map = {
                'content_package': PackageType.CONTENT,
                'ue_project': PackageType.PROJECT,
                'ue_plugin': PackageType.PLUGIN,
                'loose_assets': PackageType.OTHERS,
                'raw_3d_files': PackageType.OTHERS,
                'mixed_files': PackageType.OTHERS,
                'unknown': PackageType.OTHERS,
            }
            detected = type_map.get(analysis.structure_type.value, PackageType.CONTENT)
            
            success = (detected == expected_type)
            
            print(f"  期望类型: {expected_type.value}")
            print(f"  检测类型: {detected.value}")
            print(f"  描述: {analysis.description}")
            print(f"  结果: {'✅ 通过' if success else '❌ 失败'}")
            
            results.append({
                "name": name,
                "source_type": source_type,
                "expected": expected_type.value,
                "detected": detected.value,
                "success": success,
                "description": analysis.description
            })
            
        except Exception as e:
            print(f"  ❌ 错误: {e}")
            results.append({
                "name": name,
                "source_type": source_type,
                "expected": expected_type.value,
                "detected": None,
                "success": False,
                "error": str(e)
            })
    
    return results


def test_archive_detection(test_dir):
    """测试压缩包检测（需要解压）"""
    print("\n" + "=" * 60)
    print("测试压缩包检测")
    print("=" * 60)
    
    from modules.asset_manager.utils.archive_extractor import ArchiveExtractor
    
    analyzer = AssetStructureAnalyzer()
    extractor = ArchiveExtractor()
    
    test_cases = [
        ("ContentAsset.zip", PackageType.CONTENT),
        ("ProjectAsset.zip", PackageType.PROJECT),
    ]
    
    results = []
    
    for name, expected_type in test_cases:
        archive_path = test_dir / name
        
        print(f"\n测试: {name}")
        print(f"  路径: {archive_path}")
        
        try:
            # 解压
            temp_dir = extractor.extract(archive_path)
            print(f"  解压到: {temp_dir}")
            
            # 分析
            analysis = analyzer.analyze(temp_dir)
            
            type_map = {
                'content_package': PackageType.CONTENT,
                'ue_project': PackageType.PROJECT,
                'ue_plugin': PackageType.PLUGIN,
                'loose_assets': PackageType.OTHERS,
                'raw_3d_files': PackageType.OTHERS,
                'mixed_files': PackageType.OTHERS,
                'unknown': PackageType.OTHERS,
            }
            detected = type_map.get(analysis.structure_type.value, PackageType.CONTENT)
            
            success = (detected == expected_type)
            
            print(f"  期望类型: {expected_type.value}")
            print(f"  检测类型: {detected.value}")
            print(f"  描述: {analysis.description}")
            print(f"  结果: {'✅ 通过' if success else '❌ 失败'}")
            
            results.append({
                "name": name,
                "source_type": "压缩包",
                "expected": expected_type.value,
                "detected": detected.value,
                "success": success,
                "description": analysis.description
            })
            
            # 清理临时目录
            extractor.cleanup(temp_dir)
            
        except Exception as e:
            print(f"  ❌ 错误: {e}")
            results.append({
                "name": name,
                "source_type": "压缩包",
                "expected": expected_type.value,
                "detected": None,
                "success": False,
                "error": str(e)
            })
    
    return results


def generate_report(all_results, test_dir):
    """生成测试报告"""
    print("\n" + "=" * 60)
    print("测试报告")
    print("=" * 60)
    
    total = len(all_results)
    passed = sum(1 for r in all_results if r.get("success", False))
    failed = total - passed
    
    print(f"\n总测试数: {total}")
    print(f"通过: {passed} ✅")
    print(f"失败: {failed} ❌")
    print(f"通过率: {(passed/total*100):.1f}%")
    
    print("\n详细结果:")
    print("-" * 60)
    for i, r in enumerate(all_results, 1):
        status = "✅" if r.get("success") else "❌"
        print(f"{i}. {r['name']} ({r['source_type']}) {status}")
        print(f"   期望: {r['expected']} | 检测: {r.get('detected', 'N/A')}")
        if r.get('error'):
            print(f"   错误: {r['error']}")
    
    # 保存报告
    report_path = test_dir / "test_report.json"
    with open(report_path, 'w', encoding='utf-8') as f:
        json.dump({
            "summary": {
                "total": total,
                "passed": passed,
                "failed": failed,
                "pass_rate": f"{(passed/total*100):.1f}%"
            },
            "results": all_results
        }, f, indent=2, ensure_ascii=False)
    
    print(f"\n报告已保存: {report_path}")


def cleanup(test_dir):
    """清理测试数据"""
    print("\n" + "=" * 60)
    print("清理测试数据")
    print("=" * 60)
    
    try:
        if test_dir.exists():
            shutil.rmtree(test_dir)
            print(f"✅ 已删除: {test_dir}")
    except Exception as e:
        print(f"❌ 清理失败: {e}")


def main():
    """主函数"""
    try:
        # 创建测试资产
        test_dir = create_test_assets()
        
        # 测试文件夹检测
        folder_results = test_structure_detection(test_dir)
        
        # 测试压缩包检测
        archive_results = test_archive_detection(test_dir)
        
        # 合并结果
        all_results = folder_results + archive_results
        
        # 生成报告
        generate_report(all_results, test_dir)
        
        # 清理
        cleanup(test_dir)
        
        print("\n" + "=" * 60)
        print("测试完成！")
        print("=" * 60)
        
    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
