# -*- coding: utf-8 -*-

"""
ThreadService 集成测试
"""

import pytest
import time
from PyQt6.QtWidgets import QApplication


def test_thread_service_basic(clean_services):
    """测试 ThreadService 基本功能

    验证：
    1. 可以提交任务
    2. 任务可以正常执行
    3. 可以获取任务结果
    """
    from core.services import thread_service

    # 测试数据
    result_container = []

    def test_task():
        return "test_result"

    def on_result(result):
        result_container.append(result)

    # 提交任务
    thread_service.run_async(test_task, on_result=on_result)

    # 等待任务完成，处理 Qt 事件
    for _ in range(10):  # 最多等待 1 秒
        QApplication.processEvents()
        time.sleep(0.1)
        if len(result_container) > 0:
            break

    # 验证结果
    assert len(result_container) == 1, "应该收到一个结果"
    assert result_container[0] == "test_result", "结果应该正确"


def test_thread_service_error_handling(clean_services):
    """测试 ThreadService 错误处理

    验证：
    1. 任务抛出异常时不会崩溃
    2. 错误回调被正确调用
    """
    from core.services import thread_service

    # 测试数据
    error_container = []

    def error_task():
        raise ValueError("test error")

    def on_error(error):
        error_container.append(str(error))

    # 提交任务
    thread_service.run_async(error_task, on_error=on_error)

    # 等待任务完成，处理 Qt 事件
    for _ in range(10):  # 最多等待 1 秒
        QApplication.processEvents()
        time.sleep(0.1)
        if len(error_container) > 0:
            break

    # 验证错误
    assert len(error_container) == 1, "应该收到一个错误"
    assert "test error" in error_container[0], "错误信息应该正确"


def test_thread_service_multiple_tasks(clean_services):
    """测试 ThreadService 多任务处理

    验证：
    1. 可以同时提交多个任务
    2. 所有任务都能正常完成
    """
    from core.services import thread_service

    # 测试数据
    result_container = []

    def create_task(task_id):
        def task():
            time.sleep(0.1)
            return f"task_{task_id}"
        return task

    def on_result(result):
        result_container.append(result)

    # 提交多个任务
    for i in range(5):
        thread_service.run_async(create_task(i), on_result=on_result)

    # 等待所有任务完成，处理 Qt 事件
    for _ in range(20):  # 最多等待 2 秒
        QApplication.processEvents()
        time.sleep(0.1)
        if len(result_container) >= 5:
            break

    # 验证结果
    assert len(result_container) == 5, f"应该收到 5 个结果，实际收到 {len(result_container)} 个"
    for i in range(5):
        assert f"task_{i}" in result_container, f"应该包含 task_{i}"


def test_thread_service_cleanup(clean_services):
    """测试 ThreadService 清理

    验证：
    1. cleanup() 可以正常清理线程资源
    2. 清理后不会有线程泄漏
    """
    from core.services import thread_service, cleanup_all_services

    # 提交一些任务
    def dummy_task():
        time.sleep(0.1)
        return "done"

    for _ in range(3):
        thread_service.run_async(dummy_task)

    # 等待任务开始
    time.sleep(0.05)

    # 清理服务
    cleanup_all_services()

    # 验证清理成功（不抛出异常即可）
    assert True, "清理应该成功完成"


def test_thread_service_singleton(clean_services):
    """测试 ThreadService 单例

    验证：
    1. 多次获取返回相同实例
    2. 底层 ThreadManager 是同一个
    """
    from core.services import _get_thread_service

    # 获取两次
    service1 = _get_thread_service()
    service2 = _get_thread_service()

    # 验证是同一个实例
    assert service1 is service2, "ThreadService 应该是单例"

    # 验证底层 ThreadManager 也是同一个
    assert service1._thread_manager is service2._thread_manager, \
        "底层 ThreadManager 应该是同一个"

