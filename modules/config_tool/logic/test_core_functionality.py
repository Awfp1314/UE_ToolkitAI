# -*- coding: utf-8 -*-

"""
核心功能验证测试

这是一个简单的验证脚本，用于测试配置工具的核心功能。
"""

import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

from modules.config_tool.logic.config_model import ConfigType, ConfigTemplate
from modules.config_tool.logic.config_storage import ConfigStorage
from modules.config_tool.logic.config_saver import ConfigSaver
from modules.config_tool.logic.utils import validate_config_name, sanitize_filename
from datetime import datetime


def test_config_type_enum():
    """测试配置类型枚举"""
    print("测试 ConfigType 枚举...")
    
    # 测试枚举值
    assert ConfigType.PROJECT_SETTINGS.value == "project_settings"
    assert ConfigType.EDITOR_PREFERENCES.value == "editor_preferences"
    
    # 测试显示名称
    assert ConfigType.PROJECT_SETTINGS.display_name == "项目设置"
    assert ConfigType.EDITOR_PREFERENCES.display_name == "编辑器偏好"
    
    print("✓ ConfigType 枚举测试通过")


def test_config_template_serialization():
    """测试配置模板序列化"""
    print("测试 ConfigTemplate 序列化...")
    
    # 创建测试模板
    template = ConfigTemplate(
        name="测试配置",
        description="测试描述",
        type=ConfigType.PROJECT_SETTINGS,
        config_version="4.27",
        source_project="D:/Projects/TestProject",
        created_at=datetime.now(),
        file_count=5,
        total_size=102400,
        files=["Config/DefaultEngine.ini", "Config/DefaultGame.ini"],
        template_path=Path("C:/test/path")
    )
    
    # 测试 to_dict
    data = template.to_dict()
    assert data["name"] == "测试配置"
    assert data["type"] == "project_settings"
    assert data["config_version"] == "4.27"
    assert data["file_count"] == 5
    
    # 测试 from_dict
    restored = ConfigTemplate.from_dict(data, Path("C:/test/path"))
    assert restored.name == template.name
    assert restored.type == template.type
    assert restored.config_version == template.config_version
    
    print("✓ ConfigTemplate 序列化测试通过")


def test_config_storage_initialization():
    """测试配置存储管理器初始化"""
    print("测试 ConfigStorage 初始化...")
    
    storage = ConfigStorage()
    
    # 验证存储根目录已创建
    assert storage.storage_root.exists()
    assert storage.storage_root.name == "config_templates"
    
    print(f"✓ ConfigStorage 初始化测试通过，存储路径: {storage.storage_root}")


def test_config_saver_initialization():
    """测试配置保存器初始化"""
    print("测试 ConfigSaver 初始化...")
    
    storage = ConfigStorage()
    saver = ConfigSaver(storage)
    
    assert saver.storage == storage
    
    print("✓ ConfigSaver 初始化测试通过")


def test_validate_config_name():
    """测试配置名称验证"""
    print("测试配置名称验证...")
    
    # 有效名称
    is_valid, msg = validate_config_name("我的配置")
    assert is_valid
    
    # 空名称
    is_valid, msg = validate_config_name("")
    assert not is_valid
    assert "不能为空" in msg
    
    # 包含非法字符
    is_valid, msg = validate_config_name("配置<>")
    assert not is_valid
    assert "不能包含" in msg
    
    # 名称过长
    is_valid, msg = validate_config_name("a" * 101)
    assert not is_valid
    assert "不能超过" in msg
    
    print("✓ 配置名称验证测试通过")


def test_sanitize_filename():
    """测试文件名清理"""
    print("测试文件名清理...")
    
    # 包含非法字符
    cleaned = sanitize_filename("配置<>:test")
    assert "<" not in cleaned
    assert ">" not in cleaned
    assert ":" not in cleaned
    
    # 前后空白
    cleaned = sanitize_filename("  test  ")
    assert cleaned == "test"
    
    # 过长文件名
    long_name = "a" * 150
    cleaned = sanitize_filename(long_name)
    assert len(cleaned) == 100
    
    print("✓ 文件名清理测试通过")


def run_all_tests():
    """运行所有测试"""
    print("=" * 60)
    print("开始核心功能验证测试")
    print("=" * 60)
    
    try:
        test_config_type_enum()
        test_config_template_serialization()
        test_config_storage_initialization()
        test_config_saver_initialization()
        test_validate_config_name()
        test_sanitize_filename()
        
        print("=" * 60)
        print("✓ 所有核心功能测试通过！")
        print("=" * 60)
        return True
        
    except AssertionError as e:
        print(f"✗ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False
    except Exception as e:
        print(f"✗ 测试出错: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
