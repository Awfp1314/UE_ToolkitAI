"""测试 ThreadService 功能

测试内容：
1. ThreadService 初始化
2. run_async 方法返回值
3. cancel_task 方法
4. get_thread_usage 方法

注意：由于Qt事件循环的限制，这里只测试接口和基本功能，不测试实际的异步执行
"""

import sys
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


def main():
    """运行所有测试"""
    print("=" * 60)
    print("ThreadService 功能测试")
    print("=" * 60)

    # 一次性导入，避免命名冲突
    from core.services import thread_service
    from core.utils.thread_utils import Worker, CancellationToken

    # 测试 1：导入
    print("\n[测试 1] ThreadService 导入")
    print("-" * 60)
    assert thread_service is not None, "thread_service 导入失败"
    print(f"  thread_service: {thread_service}")
    print(f"  类型: {type(thread_service)}")
    print("✅ 测试 1 通过")

    # 测试 2：run_async 方法
    print("\n[测试 2] run_async 方法返回值")
    print("-" * 60)

    def task(cancel_token, value):
        """测试任务"""
        return f"result: {value}"

    worker, token = thread_service.run_async(task, value=42)

    assert worker is not None, "worker 为 None"
    assert token is not None, "token 为 None"
    assert isinstance(worker, Worker), f"worker 类型错误: {type(worker)}"
    assert isinstance(token, CancellationToken), f"token 类型错误: {type(token)}"
    assert hasattr(token, 'is_cancelled'), "token 缺少 is_cancelled 方法"
    assert hasattr(token, 'cancel'), "token 缺少 cancel 方法"

    print(f"  Worker 类型: {type(worker)}")
    print(f"  Token 类型: {type(token)}")
    print("✅ 测试 2 通过")

    # 测试 3：cancel_task 方法
    print("\n[测试 3] cancel_task 方法")
    print("-" * 60)

    def task2(cancel_token):
        """测试任务"""
        return "result"

    # 测试使用 token 取消
    worker3, token3 = thread_service.run_async(task2)
    assert token3.is_cancelled() is False, "初始状态应该是未取消"
    thread_service.cancel_task(token3)
    assert token3.is_cancelled() is True, "取消后应该是已取消"
    print("  使用 Token 取消: ✅")

    # 测试使用 worker 取消
    worker4, token4 = thread_service.run_async(task2)
    assert token4.is_cancelled() is False, "初始状态应该是未取消"
    thread_service.cancel_task(worker4)
    assert token4.is_cancelled() is True, "取消后应该是已取消"
    print("  使用 Worker 取消: ✅")

    # 测试错误类型
    try:
        thread_service.cancel_task("invalid")
        assert False, "应该抛出 TypeError"
    except TypeError as e:
        print(f"  错误类型检测: ✅")

    print("✅ 测试 3 通过")

    # 测试 4：get_thread_usage 方法
    print("\n[测试 4] get_thread_usage 方法")
    print("-" * 60)

    usage = thread_service.get_thread_usage()

    assert isinstance(usage, dict), "usage 不是字典"
    assert 'active' in usage, "usage 缺少 'active' 键"
    assert 'max' in usage, "usage 缺少 'max' 键"

    print(f"  线程使用情况: {usage}")
    print("✅ 测试 4 通过")

    # 总结
    print("\n" + "=" * 60)
    print("✅ 所有测试通过：ThreadService 功能完整")
    print("=" * 60)

    return 0


if __name__ == "__main__":
    sys.exit(main())

