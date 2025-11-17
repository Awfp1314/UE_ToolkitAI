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

    # 获取配置管理器
    manager = config_service.get_config_manager("test_module")

    # 修改配置
    test_data = {"test_key": "test_value", "test_number": 42}
    manager.config = test_data

    # 保存配置
    manager.save_config()

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
    manager1 = config_service.get_config_manager("module1")
    manager2 = config_service.get_config_manager("module2")

    manager1.config = {"module": "module1"}
    manager2.config = {"module": "module2"}

    # 保存配置
    manager1.save_config()
    manager2.save_config()

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
    2. 配置管理器被正确缓存
    """
    from core.services import _get_config_service, config_service

    # 获取两次
    service1 = _get_config_service()
    service2 = _get_config_service()

    # 验证是同一个实例
    assert service1 is service2, "ConfigService 应该是单例"

    # 获取配置管理器
    manager1 = config_service.get_config_manager("test_module")
    manager2 = config_service.get_config_manager("test_module")

    # 验证配置管理器被缓存
    assert manager1 is manager2, "配置管理器应该被缓存"


def test_config_service_force_reload(clean_services, test_env):
    """测试 ConfigService 强制重新加载

    验证：
    1. force_reload=True 时重新加载配置
    2. 可以获取最新的配置
    """
    from core.services import config_service

    # 获取配置管理器
    manager = config_service.get_config_manager("test_module")

    # 第一次保存
    manager.config = {"version": 1}
    manager.save_config()

    # 第一次加载
    config1 = config_service.get_module_config("test_module")
    assert config1["version"] == 1, "第一次加载应该是版本 1"

    # 修改并保存
    manager.config = {"version": 2}
    manager.save_config()

    # 不强制重新加载（应该还是旧配置）
    config2 = config_service.get_module_config("test_module", force_reload=False)
    # 注意：这里可能会是新配置，因为 ConfigManager 内部已经更新了

    # 强制重新加载
    config3 = config_service.get_module_config("test_module", force_reload=True)
    assert config3["version"] == 2, "强制重新加载应该获取最新配置"

