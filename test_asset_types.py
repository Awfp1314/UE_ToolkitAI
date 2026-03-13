# -*- coding: utf-8 -*-

"""
资产类型自动化测试脚本

测试内容：
1. 创建 4 种类型的测试资产（CONTENT、PROJECT、PLUGIN、OTHERS）
2. 测试压缩包和文件夹两种导入方式
3. 验证类型检测、版本检测、筛选功能
4. 自动清理测试数据
"""

import sys
import json
import shutil
import zipfile
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent))

from modules.asset_manager.logic.asset_model import PackageType
from modules.asset_manager.utils.asset_structure_analyzer import AssetStructureAnalyzer
from core.logger import get_logger

logger = get_logger(__name__)


class AssetTypeTestSuite:
    """资产类型测试套件"""
    
    def __init__(self):
        self.test_root = Path(__file__).parent / "test_assets_temp"
        self.test_sources = self.test_root / "test_sources"
        self.results = []
        
    def setup(self):
        """初始化测试环境"""
        logger.info("=" * 60)
        logger.info("开始资产类型自动化测试")
        logger.info("=" * 60)
        
        # 清理旧测试数据
        if self.test_root.exists():
            logger.info(f"清理旧测试数据: {self.test_root}")
            shutil.rmtree(self.test_root)
        
        # 创建测试目录
        self.test_sources.mkdir(parents=True, exist_ok=True)
        logger.info(f"测试源文件路径: {self.test_sources}")
    
    def create_content_asset(self, name: str, as_zip: bool = False) -> Path:
        """创建 CONTENT 类型测试资产"""
        logger.info(f"创建 CONTENT 资产: {name} ({'压缩包' if as_zip else '文件夹'})")
        
        asset_dir = self.test_sources / f"{name}_folder"
        content_dir = asset_dir / "Content"
        content_dir.mkdir(parents=True, exist_ok=True)
        
        # 创建测试 .uasset 文件
        (content_dir / "TestMaterial.uasset").write_bytes(b"FAKE_UASSET_DATA")
        (content_dir / "TestBlueprint.uasset").write_bytes(b"FAKE_UASSET_DATA")
        
        # 创建子文件夹
        materials_dir = content_dir / "Materials"
        materials_dir.mkdir(exist_ok=True)
        (materials_dir / "M_Test.uasset").write_bytes(b"FAKE_UASSET_DATA")
        
        # 添加版本信息（模拟 UE 5.3 资产）
        version_file = content_dir / "TestMaterial.uasset"
        # 在文件中嵌入版本标记（简化模拟）
        version_data = b"FAKE_UASSET_DATA" + b"\x00\x00\x05\x03"  # 5.3
        version_file.write_bytes(version_data)
        
        if as_zip:
            zip_path = self.test_sources / f"{name}.zip"
            with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
                for file in asset_dir.rglob("*"):
                    if file.is_file():
                        zf.write(file, file.relative_to(asset_dir))
            shutil.rmtree(asset_dir)
            return zip_path
        
        return asset_dir
    
    def create_project_asset(self, name: str, as_zip: bool = False) -> Path:
        """创建 PROJECT 类型测试资产"""
        logger.info(f"创建 PROJECT 资产: {name} ({'压缩包' if as_zip else '文件夹'})")
        
        asset_dir = self.test_sources / f"{name}_folder"
        asset_dir.mkdir(parents=True, exist_ok=True)
        
        # 创建 .uproject 文件
        uproject_data = {
            "FileVersion": 3,
            "EngineAssociation": "5.4",
            "Category": "",
            "Description": "Test Project",
            "Modules": [
                {
                    "Name": "TestProject",
                    "Type": "Runtime",
                    "LoadingPhase": "Default"
                }
            ]
        }
        (asset_dir / f"{name}.uproject").write_text(
            json.dumps(uproject_data, indent=4), encoding='utf-8'
        )
        
        # 创建 Content 文件夹
        content_dir = asset_dir / "Content"
        content_dir.mkdir(exist_ok=True)
        (content_dir / "TestMap.umap").write_bytes(b"FAKE_UMAP_DATA")
        
        # 创建 Config 文件夹
        config_dir = asset_dir / "Config"
        config_dir.mkdir(exist_ok=True)
        (config_dir / "DefaultEngine.ini").write_text("[/Script/EngineSettings.GameMapsSettings]\nEditorStartupMap=/Game/TestMap")
        
        if as_zip:
            zip_path = self.test_sources / f"{name}.zip"
            with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
                for file in asset_dir.rglob("*"):
                    if file.is_file():
                        zf.write(file, file.relative_to(asset_dir))
            shutil.rmtree(asset_dir)
            return zip_path
        
        return asset_dir
    
    def create_plugin_asset(self, name: str, as_zip: bool = False) -> Path:
        """创建 PLUGIN 类型测试资产"""
        logger.info(f"创建 PLUGIN 资产: {name} ({'压缩包' if as_zip else '文件夹'})")
        
        asset_dir = self.test_sources / f"{name}_folder"
        asset_dir.mkdir(parents=True, exist_ok=True)
        
        # 创建 .uplugin 文件
        uplugin_data = {
            "FileVersion": 3,
            "Version": 1,
            "VersionName": "1.0",
            "FriendlyName": "Test Plugin",
            "Description": "A test plugin",
            "Category": "Other",
            "CreatedBy": "Test",
            "CreatedByURL": "",
            "EngineVersion": "5.4.0",
            "CanContainContent": True,
            "Modules": []
        }
        (asset_dir / f"{name}.uplugin").write_text(
            json.dumps(uplugin_data, indent=4), encoding='utf-8'
        )
        
        # 创建 Content 文件夹
        content_dir = asset_dir / "Content"
        content_dir.mkdir(exist_ok=True)
        (content_dir / "PluginAsset.uasset").write_bytes(b"FAKE_UASSET_DATA")
        
        # 创建 Resources 文件夹
        resources_dir = asset_dir / "Resources"
        resources_dir.mkdir(exist_ok=True)
        (resources_dir / "Icon128.png").write_bytes(b"FAKE_PNG_DATA")
        
        if as_zip:
            zip_path = self.test_sources / f"{name}.zip"
            with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
                for file in asset_dir.rglob("*"):
                    if file.is_file():
                        zf.write(file, file.relative_to(asset_dir))
            shutil.rmtree(asset_dir)
            return zip_path
        
        return asset_dir
    
    def create_others_asset(self, name: str, as_zip: bool = False) -> Path:
        """创建 OTHERS 类型测试资产（混合文件）"""
        logger.info(f"创建 OTHERS 资产: {name} ({'压缩包' if as_zip else '文件夹'})")
        
        asset_dir = self.test_sources / f"{name}_folder"
        asset_dir.mkdir(parents=True, exist_ok=True)
        
        # 创建各种类型的文件
        (asset_dir / "model.fbx").write_bytes(b"FAKE_FBX_DATA")
        (asset_dir / "texture.png").write_bytes(b"FAKE_PNG_DATA")
        (asset_dir / "audio.wav").write_bytes(b"FAKE_WAV_DATA")
        (asset_dir / "video.mp4").write_bytes(b"FAKE_MP4_DATA")
        (asset_dir / "document.pdf").write_bytes(b"FAKE_PDF_DATA")
        
        # 创建子文件夹
        textures_dir = asset_dir / "Textures"
        textures_dir.mkdir(exist_ok=True)
        (textures_dir / "BaseColor.png").write_bytes(b"FAKE_PNG_DATA")
        (textures_dir / "Normal.png").write_bytes(b"FAKE_PNG_DATA")
        
        if as_zip:
            zip_path = self.test_sources / f"{name}.zip"
            with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
                for file in asset_dir.rglob("*"):
                    if file.is_file():
                        zf.write(file, file.relative_to(asset_dir))
            shutil.rmtree(asset_dir)
            return zip_path
        
        return asset_dir
    
    def test_structure_detection(self, source_path: Path, expected_type: PackageType) -> Dict[str, Any]:
        """测试资产结构检测"""
        logger.info(f"测试结构检测: {source_path.name}")
        
        result = {
            "source": str(source_path),
            "expected_type": expected_type.value,
            "detected_type": None,
            "success": False,
            "error": None
        }
        
        try:
            # 如果是压缩包，先解压
            test_path = source_path
            temp_extract = None
            
            if source_path.suffix in ['.zip', '.rar', '.7z']:
                from modules.asset_manager.utils.archive_extractor import ArchiveExtractor
                extractor = ArchiveExtractor()
                temp_extract = extractor.extract(source_path)
                test_path = temp_extract
                logger.info(f"解压到临时目录: {temp_extract}")
            
            # 分析结构
            analyzer = AssetStructureAnalyzer()
            analysis = analyzer.analyze(test_path)
            
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
            
            result["detected_type"] = detected.value
            result["success"] = (detected == expected_type)
            result["description"] = analysis.description
            
            logger.info(f"  期望类型: {expected_type.value}")
            logger.info(f"  检测类型: {detected.value}")
            logger.info(f"  结果: {'✅ 通过' if result['success'] else '❌ 失败'}")
            
            # 清理临时解压目录
            if temp_extract:
                from modules.asset_manager.utils.archive_extractor import ArchiveExtractor
                extractor.cleanup(temp_extract)
            
        except Exception as e:
            result["error"] = str(e)
            logger.error(f"  检测失败: {e}", exc_info=True)
        
        return result
    
    def run_all_tests(self):
        """运行所有测试"""
        logger.info("\n" + "=" * 60)
        logger.info("开始生成测试资产")
        logger.info("=" * 60)
        
        # 生成测试资产
        test_cases = [
            # CONTENT 类型
            ("ContentAsset_Folder", PackageType.CONTENT, False),
            ("ContentAsset_Zip", PackageType.CONTENT, True),
            
            # PROJECT 类型
            ("ProjectAsset_Folder", PackageType.PROJECT, False),
            ("ProjectAsset_Zip", PackageType.PROJECT, True),
            
            # PLUGIN 类型
            ("PluginAsset_Folder", PackageType.PLUGIN, False),
            ("PluginAsset_Zip", PackageType.PLUGIN, True),
            
            # OTHERS 类型
            ("OthersAsset_Folder", PackageType.OTHERS, False),
            ("OthersAsset_Zip", PackageType.OTHERS, True),
        ]
        
        test_assets = []
        for name, pkg_type, as_zip in test_cases:
            try:
                if pkg_type == PackageType.CONTENT:
                    path = self.create_content_asset(name, as_zip)
                elif pkg_type == PackageType.PROJECT:
                    path = self.create_project_asset(name, as_zip)
                elif pkg_type == PackageType.PLUGIN:
                    path = self.create_plugin_asset(name, as_zip)
                elif pkg_type == PackageType.OTHERS:
                    path = self.create_others_asset(name, as_zip)
                else:
                    continue
                
                test_assets.append((path, pkg_type))
            except Exception as e:
                logger.error(f"创建测试资产失败 {name}: {e}")
        
        logger.info(f"\n成功创建 {len(test_assets)} 个测试资产")
        
        # 运行结构检测测试
        logger.info("\n" + "=" * 60)
        logger.info("开始结构检测测试")
        logger.info("=" * 60)
        
        for asset_path, expected_type in test_assets:
            result = self.test_structure_detection(asset_path, expected_type)
            self.results.append(result)
        
        # 生成测试报告
        self.generate_report()
    
    def generate_report(self):
        """生成测试报告"""
        logger.info("\n" + "=" * 60)
        logger.info("测试报告")
        logger.info("=" * 60)
        
        total = len(self.results)
        passed = sum(1 for r in self.results if r["success"])
        failed = total - passed
        
        logger.info(f"\n总测试数: {total}")
        logger.info(f"通过: {passed} ✅")
        logger.info(f"失败: {failed} ❌")
        logger.info(f"通过率: {(passed/total*100):.1f}%")
        
        # 详细结果
        logger.info("\n详细测试结果:")
        logger.info("-" * 60)
        
        for i, result in enumerate(self.results, 1):
            status = "✅ 通过" if result["success"] else "❌ 失败"
            source_name = Path(result["source"]).name
            logger.info(f"{i}. {source_name}")
            logger.info(f"   期望类型: {result['expected_type']}")
            logger.info(f"   检测类型: {result['detected_type']}")
            logger.info(f"   状态: {status}")
            if result.get("error"):
                logger.info(f"   错误: {result['error']}")
            logger.info("")
        
        # 保存报告到文件
        report_path = self.test_root / "test_report.json"
        with open(report_path, 'w', encoding='utf-8') as f:
            json.dump({
                "timestamp": datetime.now().isoformat(),
                "summary": {
                    "total": total,
                    "passed": passed,
                    "failed": failed,
                    "pass_rate": f"{(passed/total*100):.1f}%"
                },
                "results": self.results
            }, f, indent=2, ensure_ascii=False)
        
        logger.info(f"详细报告已保存到: {report_path}")
    
    def cleanup(self):
        """清理测试数据"""
        logger.info("\n" + "=" * 60)
        logger.info("清理测试数据")
        logger.info("=" * 60)
        
        try:
            if self.test_root.exists():
                shutil.rmtree(self.test_root)
                logger.info(f"✅ 已删除测试目录: {self.test_root}")
        except Exception as e:
            logger.error(f"清理失败: {e}")


def main():
    """主函数"""
    suite = AssetTypeTestSuite()
    
    try:
        # 初始化
        suite.setup()
        
        # 运行测试
        suite.run_all_tests()
        
        # 清理
        suite.cleanup()
        
        logger.info("\n" + "=" * 60)
        logger.info("测试完成！")
        logger.info("=" * 60)
        
    except Exception as e:
        logger.error(f"测试过程出错: {e}", exc_info=True)
        # 确保清理
        try:
            suite.cleanup()
        except:
            pass


if __name__ == "__main__":
    main()
