# -*- coding: utf-8 -*-

"""
服务单例和依赖顺序集成测试
"""

import pytest


def test_service_singleton(clean_services):
    """测试服务单例模式

    验证：
    1. 多次获取同一服务返回相同实例
    2. 服务只初始化一次
    """
    from core.services import _get_log_service, _get_path_service, _get_config_service

    # 测试 LogService 单例
    log1 = _get_log_service()
    log2 = _get_log_service()
    assert log1 is log2, "LogService 应该是单例"

    # 测试 PathService 单例
    path1 = _get_path_service()
    path2 = _get_path_service()
    assert path1 is path2, "PathService 应该是单例"

    # 测试 ConfigService 单例
    config1 = _get_config_service()
    config2 = _get_config_service()
    assert config1 is config2, "ConfigService 应该是单例"


def test_service_dependency_order(clean_services):
    """测试服务依赖顺序

    验证：
    1. Level 0 服务（LogService, PathService）无依赖
    2. Level 1 服务（ConfigService, StyleService）依赖 Level 0
    3. Level 2 服务（ThreadService）依赖 Level 0 和 Level 1
    """
    from core.services import (
        _get_log_service, _get_path_service,
        _get_config_service, _get_style_service,
        _get_thread_service
    )

    # Level 0 服务应该可以独立初始化
    log = _get_log_service()
    assert log is not None, "LogService 应该成功初始化"

    path = _get_path_service()
    assert path is not None, "PathService 应该成功初始化"

    # Level 1 服务应该可以初始化（依赖 Level 0）
    config = _get_config_service()
    assert config is not None, "ConfigService 应该成功初始化"

    style = _get_style_service()
    assert style is not None, "StyleService 应该成功初始化"

    # Level 2 服务应该可以初始化（依赖 Level 0 和 Level 1）
    thread = _get_thread_service()
    assert thread is not None, "ThreadService 应该成功初始化"


def test_cleanup_all_services(clean_services):
    """测试清理所有服务

    验证：
    1. cleanup_all_services() 按正确顺序清理服务
    2. 清理后服务可以重新初始化
    """
    from core.services import (
        _get_log_service, _get_path_service, _get_config_service,
        cleanup_all_services
    )

    # 初始化服务
    log1 = _get_log_service()
    path1 = _get_path_service()
    config1 = _get_config_service()

    # 清理所有服务
    cleanup_all_services()

    # 重新初始化服务
    log2 = _get_log_service()
    path2 = _get_path_service()
    config2 = _get_config_service()

    # 验证是新实例
    assert log2 is not log1, "清理后应该创建新的 LogService 实例"
    assert path2 is not path1, "清理后应该创建新的 PathService 实例"
    assert config2 is not config1, "清理后应该创建新的 ConfigService 实例"


def test_lazy_service_wrapper(clean_services):
    """测试 _LazyService 包装器

    验证：
    1. 支持函数调用模式: log_service()
    2. 支持属性访问模式: log_service.get_logger()
    """
    # 注意：这里需要导入 __init__.py 中的 log_service 变量，而不是 log_service 模块
    from core.services import log_service, path_service

    # 测试函数调用模式
    log = log_service()
    assert log is not None, "log_service() 应该返回 LogService 实例"

    # 测试属性访问模式
    logger = log_service.get_logger("test")
    assert logger is not None, "log_service.get_logger() 应该返回 logger"

    # 测试 PathService
    path = path_service()
    assert path is not None, "path_service() 应该返回 PathService 实例"

    user_data_dir = path_service.get_user_data_dir()
    assert user_data_dir is not None, "path_service.get_user_data_dir() 应该返回路径"


def test_service_state_tracking(clean_services):
    """测试服务状态跟踪

    验证：
    1. 服务初始化前状态为 NOT_INITIALIZED
    2. 服务初始化后状态为 INITIALIZED
    """
    from core.services import _get_log_service, ServiceState
    from core.services import _service_states

    # 初始化前状态
    assert _service_states.get('log') in (None, ServiceState.NOT_INITIALIZED), \
        "LogService 初始化前状态应该是 NOT_INITIALIZED"

    # 初始化服务
    log = _get_log_service()

    # 初始化后状态
    assert _service_states.get('log') == ServiceState.INITIALIZED, \
        "LogService 初始化后状态应该是 INITIALIZED"

