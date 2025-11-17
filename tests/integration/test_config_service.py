# -*- coding: utf-8 -*-

"""
ConfigService 集成测试
"""

import pytest
import json
from pathlib import Path


def test_config_service_basic(clean_services, test_env):
    """测试 ConfigService 基本功能

    验证：
    1. 可以获取模块配置
    2. 配置是字典类型
    """
    from core.services import config_service

    # 获取配置
    config = config_service.get_module_config("test_module")

    # 验证配置
    assert isinstance(config, dict), "配置应该是字典类型"


def test_config_service_save_and_load(clean_services, test_env):
    """测试 ConfigService 保存和加载

    验证：
    1. 可以保存配置
    2. 可以重新加载配置
    3. 加载的配置与保存的一致
    """
    from core.services import config_service

    # 获取配置
    config = config_service.get_module_config("test_module")

    # 修改配置
    config["test_key"] = "test_value"
    config["test_number"] = 42

    # 保存配置
    success = config_service.save_module_config("test_module", config)
    assert success, "配置保存应该成功"

    # 清除缓存
    config_service.clear_cache("test_module")

    # 重新加载配置
    loaded_config = config_service.get_module_config("test_module", force_reload=True)

    # 验证配置
    assert loaded_config["test_key"] == "test_value", "配置应该正确保存和加载"
    assert loaded_config["test_number"] == 42, "配置应该正确保存和加载"


def test_config_service_multiple_modules(clean_services, test_env):
    """测试 ConfigService 多模块管理

    验证：
    1. 可以管理多个模块的配置
    2. 不同模块的配置互不干扰
    """
    from core.services import config_service

    # 获取两个模块的配置
    config1 = config_service.get_module_config("module1")
    config2 = config_service.get_module_config("module2")

    # 修改配置
    config1["module"] = "module1"
    config2["module"] = "module2"

    # 保存配置
    config_service.save_module_config("module1", config1)
    config_service.save_module_config("module2", config2)

    # 清除缓存
    config_service.clear_cache()

    # 重新加载配置
    loaded1 = config_service.get_module_config("module1", force_reload=True)
    loaded2 = config_service.get_module_config("module2", force_reload=True)

    # 验证配置
    assert loaded1["module"] == "module1", "module1 配置应该正确"
    assert loaded2["module"] == "module2", "module2 配置应该正确"


def test_config_service_singleton(clean_services):
    """测试 ConfigService 单例

    验证：
    1. 多次获取返回相同实例
    2. ConfigManager 被正确缓存
    """
    from core.services import _get_config_service

    # 获取两次
    service1 = _get_config_service()
    service2 = _get_config_service()

    # 验证是同一个实例
    assert service1 is service2, "ConfigService 应该是单例"

    # 直接使用服务实例获取配置
    config1 = service1.get_module_config("test_module")
    config2 = service1.get_module_config("test_module")

    # 验证配置内容相同（ConfigManager 返回配置副本，不是同一个对象）
    assert config1 == config2, "配置内容应该相同"

    # 验证 ConfigManager 实例被缓存
    assert "test_module" in service1._config_managers, "ConfigManager 应该被缓存"

    # 验证同一个模块的 ConfigManager 是同一个实例
    manager1 = service1._config_managers["test_module"]
    service1.get_module_config("test_module")  # 再次获取
    manager2 = service1._config_managers["test_module"]
    assert manager1 is manager2, "同一个模块的 ConfigManager 应该是同一个实例"


def test_config_service_force_reload(clean_services, test_env):
    """测试 ConfigService 强制重新加载

    验证：
    1. force_reload=True 时重新加载配置
    2. 可以获取最新的配置
    """
    from core.services import config_service

    # 第一次保存
    config1 = config_service.get_module_config("test_module")
    config1["version"] = 1
    config_service.save_module_config("test_module", config1)

    # 第一次加载
    loaded1 = config_service.get_module_config("test_module", force_reload=True)
    assert loaded1["version"] == 1, "第一次加载应该是版本 1"

    # 修改并保存
    config2 = config_service.get_module_config("test_module")
    config2["version"] = 2
    config_service.save_module_config("test_module", config2)

    # 清除缓存
    config_service.clear_cache("test_module")

    # 强制重新加载
    loaded2 = config_service.get_module_config("test_module", force_reload=True)
    assert loaded2["version"] == 2, "强制重新加载应该获取最新配置"

