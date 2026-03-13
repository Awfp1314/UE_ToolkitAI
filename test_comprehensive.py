# -*- coding: utf-8 -*-

"""
资产类型全面测试脚本 - 大量测试用例
"""

import sys
import json
import shutil
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from modules.asset_manager.logic.asset_model import PackageType
from modules.asset_manager.utils.asset_structure_analyzer import AssetStructureAnalyzer


class ComprehensiveTestSuite:
    """全面测试套件"""
    
    def __init__(self):
        self.test_dir = Path(__file__).parent / "test_assets_comprehensive"
        self.results = []
        
    def setup(self):
        """初始化"""
        if self.test_dir.exists():
            shutil.rmtree(self.test_dir)
        self.test_dir.mkdir()
        print("=" * 70)
        print("资产类型全面测试")
        print("=" * 70)
    
    def create_content_variants(self):
        """创建 CONTENT 类型的多种变体"""
        print("\n创建 CONTENT 类型测试资产...")
        variants = []
        
        # 变体 1: 标准 Content 文件夹
        v1 = self.test_dir / "Content_Standard"
        (v1 / "Content").mkdir(parents=True)
        (v1 / "Content" / "Material.uasset").write_bytes(b"FAKE")
        (v1 / "Content" / "Blueprint.uasset").write_bytes(b"FAKE")
        variants.append(("Content_Standard", v1, False))
        
        # 变体 2: Content 带子文件夹
        v2 = self.test_dir / "Content_WithSubfolders"
        (v2 / "Content" / "Materials").mkdir(parents=True)
        (v2 / "Content" / "Blueprints").mkdir(parents=True)
        (v2 / "Content" / "Materials" / "M_Base.uasset").write_bytes(b"FAKE")
        (v2 / "Content" / "Blueprints" / "BP_Actor.uasset").write_bytes(b"FAKE")
        variants.append(("Content_WithSubfolders", v2, False))
        
        # 变体 3: 嵌套的 Content（AssetName/Content/）
        v3 = self.test_dir / "Content_Nested"
        (v3 / "MyAsset" / "Content").mkdir(parents=True)
        (v3 / "MyAsset" / "Content" / "Texture.uasset").write_bytes(b"FAKE")
        variants.append(("Content_Nested", v3, False))
        
        # 变体 4: Content 压缩包
        v4_zip = self.test_dir / "Content_Archive.zip"
        with zipfile.ZipFile(v4_zip, 'w') as zf:
            zf.writestr("Content/Asset1.uasset", b"FAKE")
            zf.writestr("Content/Asset2.umap", b"FAKE")
        variants.append(("Content_Archive", v4_zip, True))
        
        # 变体 5: 大小写混合的 content
        v5 = self.test_dir / "Content_MixedCase"
        (v5 / "content").mkdir(parents=True)  # 小写
        (v5 / "content" / "test.uasset").write_bytes(b"FAKE")
        variants.append(("Content_MixedCase", v5, False))
        
        print(f"  创建了 {len(variants)} 个 CONTENT 变体")
        return variants
    
    def create_project_variants(self):
        """创建 PROJECT 类型的多种变体"""
        print("\n创建 PROJECT 类型测试资产...")
        variants = []
        
        uproject_template = {
            "FileVersion": 3,
            "EngineAssociation": "5.4",
            "Category": "",
            "Description": "Test Project"
        }
        
        # 变体 1: 标准项目结构
        v1 = self.test_dir / "Project_Standard"
        v1.mkdir()
        (v1 / "TestProj.uproject").write_text(json.dumps(uproject_template, indent=4))
        (v1 / "Content").mkdir()
        (v1 / "Content" / "Map.umap").write_bytes(b"FAKE")
        (v1 / "Config").mkdir()
        (v1 / "Config" / "DefaultEngine.ini").write_text("[Settings]")
        variants.append(("Project_Standard", v1, False))
        
        # 变体 2: 项目带多个 Content 资产
        v2 = self.test_dir / "Project_WithAssets"
        v2.mkdir()
        (v2 / "MyProject.uproject").write_text(json.dumps(uproject_template, indent=4))
        (v2 / "Content" / "Materials").mkdir(parents=True)
        (v2 / "Content" / "Blueprints").mkdir(parents=True)
        (v2 / "Content" / "Materials" / "M_Test.uasset").write_bytes(b"FAKE")
        (v2 / "Content" / "Blueprints" / "BP_Test.uasset").write_bytes(b"FAKE")
        variants.append(("Project_WithAssets", v2, False))
        
        # 变体 3: 空 Content 的项目
        v3 = self.test_dir / "Project_EmptyContent"
        v3.mkdir()
        (v3 / "EmptyProj.uproject").write_text(json.dumps(uproject_template, indent=4))
        (v3 / "Content").mkdir()  # 空文件夹
        variants.append(("Project_EmptyContent", v3, False))
        
        # 变体 4: 项目压缩包
        v4_zip = self.test_dir / "Project_Archive.zip"
        with zipfile.ZipFile(v4_zip, 'w') as zf:
            zf.writestr("TestProj.uproject", json.dumps(uproject_template))
            zf.writestr("Content/Map.umap", b"FAKE")
            zf.writestr("Config/DefaultEngine.ini", "[Settings]")
        variants.append(("Project_Archive", v4_zip, True))
        
        # 变体 5: 嵌套的项目（ProjectName/ProjectName.uproject）
        v5 = self.test_dir / "Project_Nested"
        (v5 / "MyGame").mkdir(parents=True)
        (v5 / "MyGame" / "MyGame.uproject").write_text(json.dumps(uproject_template, indent=4))
        (v5 / "MyGame" / "Content").mkdir()
        (v5 / "MyGame" / "Content" / "Level.umap").write_bytes(b"FAKE")
        variants.append(("Project_Nested", v5, False))
        
        print(f"  创建了 {len(variants)} 个 PROJECT 变体")
        return variants
    
    def create_plugin_variants(self):
        """创建 PLUGIN 类型的多种变体"""
        print("\n创建 PLUGIN 类型测试资产...")
        variants = []
        
        uplugin_template = {
            "FileVersion": 3,
            "Version": 1,
            "VersionName": "1.0",
            "FriendlyName": "Test Plugin",
            "EngineVersion": "5.4.0",
            "CanContainContent": True
        }
        
        # 变体 1: 标准插件
        v1 = self.test_dir / "Plugin_Standard"
        v1.mkdir()
        (v1 / "TestPlugin.uplugin").write_text(json.dumps(uplugin_template, indent=4))
        (v1 / "Content").mkdir()
        (v1 / "Content" / "PluginAsset.uasset").write_bytes(b"FAKE")
        (v1 / "Resources").mkdir()
        (v1 / "Resources" / "Icon128.png").write_bytes(b"FAKE_PNG")
        variants.append(("Plugin_Standard", v1, False))
        
        # 变体 2: 插件带多个资产
        v2 = self.test_dir / "Plugin_WithAssets"
        v2.mkdir()
        (v2 / "MyPlugin.uplugin").write_text(json.dumps(uplugin_template, indent=4))
        (v2 / "Content" / "UI").mkdir(parents=True)
        (v2 / "Content" / "Data").mkdir(parents=True)
        (v2 / "Content" / "UI" / "Widget.uasset").write_bytes(b"FAKE")
        (v2 / "Content" / "Data" / "Config.uasset").write_bytes(b"FAKE")
        variants.append(("Plugin_WithAssets", v2, False))
        
        # 变体 3: 插件压缩包
        v3_zip = self.test_dir / "Plugin_Archive.zip"
        with zipfile.ZipFile(v3_zip, 'w') as zf:
            zf.writestr("TestPlugin.uplugin", json.dumps(uplugin_template))
            zf.writestr("Content/Asset.uasset", b"FAKE")
            zf.writestr("Resources/Icon.png", b"FAKE_PNG")
        variants.append(("Plugin_Archive", v3_zip, True))
        
        # 变体 4: 空 Content 的插件
        v4 = self.test_dir / "Plugin_EmptyContent"
        v4.mkdir()
        (v4 / "EmptyPlugin.uplugin").write_text(json.dumps(uplugin_template, indent=4))
        (v4 / "Content").mkdir()
        variants.append(("Plugin_EmptyContent", v4, False))
        
        print(f"  创建了 {len(variants)} 个 PLUGIN 变体")
        return variants
    
    def create_others_variants(self):
        """创建 OTHERS 类型的多种变体"""
        print("\n创建 OTHERS 类型测试资产...")
        variants = []
        
        # 变体 1: 纯 3D 模型
        v1 = self.test_dir / "Others_3DModels"
        v1.mkdir()
        (v1 / "character.fbx").write_bytes(b"FAKE_FBX")
        (v1 / "prop.obj").write_bytes(b"FAKE_OBJ")
        variants.append(("Others_3DModels", v1, False))
        
        # 变体 2: 纯纹理
        v2 = self.test_dir / "Others_Textures"
        v2.mkdir()
        (v2 / "BaseColor.png").write_bytes(b"FAKE_PNG")
        (v2 / "Normal.png").write_bytes(b"FAKE_PNG")
        (v2 / "Roughness.tga").write_bytes(b"FAKE_TGA")
        variants.append(("Others_Textures", v2, False))
        
        # 变体 3: 混合文件
        v3 = self.test_dir / "Others_Mixed"
        v3.mkdir()
        (v3 / "model.fbx").write_bytes(b"FAKE_FBX")
        (v3 / "texture.png").write_bytes(b"FAKE_PNG")
        (v3 / "audio.wav").write_bytes(b"FAKE_WAV")
        (v3 / "video.mp4").write_bytes(b"FAKE_MP4")
        (v3 / "document.pdf").write_bytes(b"FAKE_PDF")
        variants.append(("Others_Mixed", v3, False))
        
        # 变体 4: 带子文件夹的混合文件
        v4 = self.test_dir / "Others_WithFolders"
        (v4 / "Models").mkdir(parents=True)
        (v4 / "Textures").mkdir(parents=True)
        (v4 / "Audio").mkdir(parents=True)
        (v4 / "Models" / "char.fbx").write_bytes(b"FAKE_FBX")
        (v4 / "Textures" / "tex.png").write_bytes(b"FAKE_PNG")
        (v4 / "Audio" / "sound.wav").write_bytes(b"FAKE_WAV")
        variants.append(("Others_WithFolders", v4, False))
        
        # 变体 5: 压缩包
        v5_zip = self.test_dir / "Others_Archive.zip"
        with zipfile.ZipFile(v5_zip, 'w') as zf:
            zf.writestr("model.fbx", b"FAKE_FBX")
            zf.writestr("texture.png", b"FAKE_PNG")
        variants.append(("Others_Archive", v5_zip, True))
        
        print(f"  创建了 {len(variants)} 个 OTHERS 变体")
        return variants
    
    def test_all_variants(self, variants, expected_type):
        """测试所有变体"""
        analyzer = AssetStructureAnalyzer()
        
        for name, path, is_archive in variants:
            print(f"\n  测试: {name}")
            
            try:
                # 处理压缩包
                test_path = path
                temp_dir = None
                
                if is_archive:
                    from modules.asset_manager.utils.archive_extractor import ArchiveExtractor
                    extractor = ArchiveExtractor()
                    temp_dir = extractor.extract(path)
                    test_path = temp_dir
                    print(f"    解压到: {temp_dir}")
                
                # 分析
                analysis = analyzer.analyze(test_path)
                
                # 映射类型
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
                status = "✅" if success else "❌"
                
                print(f"    期望: {expected_type.value}")
                print(f"    检测: {detected.value}")
                print(f"    描述: {analysis.description}")
                print(f"    {status} {'通过' if success else '失败'}")
                
                self.results.append({
                    "name": name,
                    "expected": expected_type.value,
                    "detected": detected.value,
                    "success": success,
                    "description": analysis.description,
                    "is_archive": is_archive
                })
                
                # 清理临时目录
                if temp_dir:
                    extractor.cleanup(temp_dir)
                    
            except Exception as e:
                print(f"    ❌ 错误: {e}")
                self.results.append({
                    "name": name,
                    "expected": expected_type.value,
                    "detected": None,
                    "success": False,
                    "error": str(e),
                    "is_archive": is_archive
                })
    
    def run_all_tests(self):
        """运行所有测试"""
        # 创建所有变体
        content_variants = self.create_content_variants()
        project_variants = self.create_project_variants()
        plugin_variants = self.create_plugin_variants()
        others_variants = self.create_others_variants()
        
        print("\n" + "=" * 70)
        print("开始测试")
        print("=" * 70)
        
        # 测试 CONTENT
        print("\n【测试 CONTENT 类型】")
        self.test_all_variants(content_variants, PackageType.CONTENT)
        
        # 测试 PROJECT
        print("\n【测试 PROJECT 类型】")
        self.test_all_variants(project_variants, PackageType.PROJECT)
        
        # 测试 PLUGIN
        print("\n【测试 PLUGIN 类型】")
        self.test_all_variants(plugin_variants, PackageType.PLUGIN)
        
        # 测试 OTHERS
        print("\n【测试 OTHERS 类型】")
        self.test_all_variants(others_variants, PackageType.OTHERS)
    
    def generate_report(self):
        """生成测试报告"""
        print("\n" + "=" * 70)
        print("测试报告")
        print("=" * 70)
        
        total = len(self.results)
        passed = sum(1 for r in self.results if r.get("success", False))
        failed = total - passed
        
        # 按类型统计
        by_type = {}
        for r in self.results:
            exp = r["expected"]
            if exp not in by_type:
                by_type[exp] = {"total": 0, "passed": 0}
            by_type[exp]["total"] += 1
            if r.get("success"):
                by_type[exp]["passed"] += 1
        
        print(f"\n总体统计:")
        print(f"  总测试数: {total}")
        print(f"  通过: {passed} ✅")
        print(f"  失败: {failed} ❌")
        print(f"  通过率: {(passed/total*100):.1f}%")
        
        print(f"\n分类统计:")
        for type_name, stats in by_type.items():
            rate = (stats["passed"] / stats["total"] * 100) if stats["total"] > 0 else 0
            print(f"  {type_name}: {stats['passed']}/{stats['total']} ({rate:.1f}%)")
        
        # 失败的测试
        failures = [r for r in self.results if not r.get("success", False)]
        if failures:
            print(f"\n失败的测试 ({len(failures)} 个):")
            for r in failures:
                print(f"  ❌ {r['name']}")
                print(f"     期望: {r['expected']} | 检测: {r.get('detected', 'N/A')}")
                if r.get('error'):
                    print(f"     错误: {r['error']}")
        
        # 保存报告
        report_path = self.test_dir / "comprehensive_report.json"
        with open(report_path, 'w', encoding='utf-8') as f:
            json.dump({
                "summary": {
                    "total": total,
                    "passed": passed,
                    "failed": failed,
                    "pass_rate": f"{(passed/total*100):.1f}%"
                },
                "by_type": by_type,
                "results": self.results
            }, f, indent=2, ensure_ascii=False)
        
        print(f"\n详细报告已保存: {report_path}")
    
    def cleanup(self):
        """清理"""
        print("\n" + "=" * 70)
        print("清理测试数据")
        print("=" * 70)
        
        try:
            if self.test_dir.exists():
                shutil.rmtree(self.test_dir)
                print(f"✅ 已删除: {self.test_dir}")
        except Exception as e:
            print(f"❌ 清理失败: {e}")


def main():
    suite = ComprehensiveTestSuite()
    
    try:
        suite.setup()
        suite.run_all_tests()
        suite.generate_report()
        suite.cleanup()
        
        print("\n" + "=" * 70)
        print("全面测试完成！")
        print("=" * 70)
        
    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
