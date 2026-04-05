# -*- coding: utf-8 -*-

"""
Phase 2 集成测试

测试版本匹配、配置应用和回滚功能
"""

import json
import tempfile
import shutil
from pathlib import Path
from datetime import datetime

from .config_model import ConfigType, ConfigTemplate
from .config_storage import ConfigStorage
from .config_saver import ConfigSaver
from .version_matcher import VersionMatcher
from .config_applier import ConfigApplier, apply_config_with_rollback, restore_from_backup


def create_test_project(name: str, engine_version: str, with_config: bool = True) -> Path:
    """创建测试用 UE 项目"""
    project_dir = Path(tempfile.mkdtemp()) / name
    project_dir.mkdir()
    
    # 创建 .uproject 文件
    uproject_file = project_dir / f"{name}.uproject"
    uproject_data = {
        "FileVersion": 3,
        "EngineAssociation": engine_version,
        "Category": "",
        "Description": "",
        "EpicAccountID": "00000000-0000-0000-0000-000000000000"
    }
    uproject_file.write_text(json.dumps(uproject_data, indent=4))
    
    if with_config:
        # 创建 Config 目录和配置文件
        config_dir = project_dir / "Config"
        config_dir.mkdir()
        
        # 创建基本配置文件
        for ini_name in ["DefaultEngine.ini", "DefaultGame.ini", "DefaultInput.ini"]:
            ini_file = config_dir / ini_name
            ini_file.write_text(f"[/Script/Engine.Engine]\n; Test config for {name}\n")
    
    return project_dir


def test_version_matcher():
    """测试版本匹配器"""
    print("\n=== 测试版本匹配器 ===")
    
    matcher = VersionMatcher()
    
    # 测试版本匹配
    is_compatible, msg = matcher.validate_version("4.27", "4.27")
    assert is_compatible, "相同版本应该兼容"
    print("✓ 相同版本匹配测试通过")
    
    # 测试版本不匹配
    is_compatible, msg = matcher.validate_version("4.27", "4.26")
    assert not is_compatible, "不同版本应该不兼容"
    assert "版本不兼容" in msg
    print("✓ 不同版本不匹配测试通过")
    
    # 测试带补丁版本
    is_compatible, msg = matcher.validate_version("4.27.2", "4.27")
    assert is_compatible, "带补丁版本应该与标准版本兼容"
    print("✓ 补丁版本匹配测试通过")
    
    print("✓ 版本匹配器测试全部通过")


def test_config_backup_and_restore():
    """测试配置备份和恢复"""
    print("\n=== 测试配置备份和恢复 ===")
    
    # 创建测试项目
    project = create_test_project("TestBackup", "4.27", with_config=True)
    
    try:
        storage = ConfigStorage()
        matcher = VersionMatcher()
        applier = ConfigApplier(storage, matcher)
        
        # 测试备份
        backup_path = applier._backup_config(project, ConfigType.PROJECT_SETTINGS)
        assert backup_path is not None, "备份应该成功"
        assert backup_path.exists(), "备份路径应该存在"
        print(f"✓ 配置备份成功: {backup_path}")
        
        # 修改原配置
        config_dir = project / "Config"
        test_file = config_dir / "DefaultEngine.ini"
        test_file.write_text("[Modified]\ntest=modified\n")
        
        # 测试恢复
        success, msg = restore_from_backup(backup_path, project, ConfigType.PROJECT_SETTINGS)
        assert success, f"恢复应该成功: {msg}"
        
        # 验证恢复后的内容
        restored_content = test_file.read_text()
        assert "Test config for TestBackup" in restored_content, "应该恢复原始内容"
        print("✓ 配置恢复成功")
        
        print("✓ 配置备份和恢复测试全部通过")
        
    finally:
        # 清理
        if project.exists():
            shutil.rmtree(project)


def test_config_apply_workflow():
    """测试配置应用工作流"""
    print("\n=== 测试配置应用工作流 ===")
    
    # 创建源项目和目标项目
    source_project = create_test_project("SourceProject", "4.27", with_config=True)
    target_project = create_test_project("TargetProject", "4.27", with_config=True)
    
    try:
        storage = ConfigStorage()
        saver = ConfigSaver(storage)
        matcher = VersionMatcher()
        applier = ConfigApplier(storage, matcher)
        
        # 保存配置模板
        success, msg = saver.save_config(
            name="TestConfig",
            description="测试配置",
            config_type=ConfigType.PROJECT_SETTINGS,
            source_project=source_project
        )
        assert success, f"保存配置应该成功: {msg}"
        print("✓ 配置模板保存成功")
        
        # 加载配置模板
        template = storage.load_template("TestConfig")
        assert template is not None, "应该能加载配置模板"
        print("✓ 配置模板加载成功")
        
        # 应用配置（带备份）
        progress_stages = []
        def progress_callback(stage, title, detail):
            progress_stages.append((stage, title))
            print(f"  进度: 阶段 {stage} - {title}")
        
        success, msg = applier.apply_config(
            template, target_project, backup=True, progress_callback=progress_callback
        )
        assert success, f"应用配置应该成功: {msg}"
        print("✓ 配置应用成功")
        
        # 验证进度回调
        assert len(progress_stages) == 5, "应该有5个进度阶段"
        print("✓ 进度回调正常")
        
        # 验证配置已应用
        target_config = target_project / "Config" / "DefaultEngine.ini"
        assert target_config.exists(), "配置文件应该存在"
        content = target_config.read_text()
        assert "SourceProject" in content, "应该包含源项目的配置内容"
        print("✓ 配置内容验证通过")
        
        # 验证项目ID已更新
        uproject_file = target_project / "TargetProject.uproject"
        with open(uproject_file, 'r') as f:
            data = json.load(f)
        assert data['EpicAccountID'] != "00000000-0000-0000-0000-000000000000", "项目ID应该已更新"
        print("✓ 项目ID更新成功")
        
        # 验证备份模板已创建
        templates = storage.list_templates()
        backup_templates = [t for t in templates if "备份配置" in t.name]
        assert len(backup_templates) > 0, "应该创建了备份模板"
        print(f"✓ 备份模板已创建: {backup_templates[0].name}")
        
        print("✓ 配置应用工作流测试全部通过")
        
        # 清理测试模板
        storage.delete_template("TestConfig")
        for t in backup_templates:
            storage.delete_template(t.name)
        
    finally:
        # 清理
        if source_project.exists():
            shutil.rmtree(source_project)
        if target_project.exists():
            shutil.rmtree(target_project)


def test_version_mismatch_rejection():
    """测试版本不匹配时拒绝应用"""
    print("\n=== 测试版本不匹配拒绝 ===")
    
    # 创建不同版本的项目
    source_project = create_test_project("Source427", "4.27", with_config=True)
    target_project = create_test_project("Target426", "4.26", with_config=True)
    
    try:
        storage = ConfigStorage()
        saver = ConfigSaver(storage)
        matcher = VersionMatcher()
        applier = ConfigApplier(storage, matcher)
        
        # 保存配置模板
        success, msg = saver.save_config(
            name="TestConfig427",
            description="4.27配置",
            config_type=ConfigType.PROJECT_SETTINGS,
            source_project=source_project
        )
        assert success, f"保存配置应该成功: {msg}"
        
        # 加载配置模板
        template = storage.load_template("TestConfig427")
        assert template is not None, "应该能加载配置模板"
        
        # 尝试应用到不同版本的项目
        success, msg = applier.apply_config(template, target_project, backup=False)
        assert not success, "应该拒绝应用不兼容版本的配置"
        assert "版本不兼容" in msg, "错误消息应该包含版本不兼容信息"
        print(f"✓ 版本不匹配正确拒绝: {msg}")
        
        print("✓ 版本不匹配拒绝测试通过")
        
        # 清理
        storage.delete_template("TestConfig427")
        
    finally:
        if source_project.exists():
            shutil.rmtree(source_project)
        if target_project.exists():
            shutil.rmtree(target_project)


def run_all_tests():
    """运行所有测试"""
    print("\n" + "="*60)
    print("Phase 2 集成测试")
    print("="*60)
    
    try:
        test_version_matcher()
        test_config_backup_and_restore()
        test_config_apply_workflow()
        test_version_mismatch_rejection()
        
        print("\n" + "="*60)
        print("✓ 所有测试通过！")
        print("="*60)
        return True
        
    except AssertionError as e:
        print(f"\n✗ 测试失败: {e}")
        return False
    except Exception as e:
        print(f"\n✗ 测试异常: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    run_all_tests()
