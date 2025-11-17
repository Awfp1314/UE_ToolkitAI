"""
测试 Level 0 服务（LogService 和 PathService）
"""

import sys
from pathlib import Path

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent))

print("=" * 60)
print("测试 Level 0 服务（LogService 和 PathService）")
print("=" * 60)

# 测试 1：导入服务
print("\n[测试 1] 导入服务...")
try:
    from core.services import path_service, log_service
    print("✅ PathService 和 LogService 导入成功")
except Exception as e:
    print(f"❌ 服务导入失败: {e}")
    sys.exit(1)

# 测试 2：获取用户数据目录
print("\n[测试 2] 获取用户数据目录...")
try:
    data_dir = path_service.get_user_data_dir()
    assert data_dir.exists(), "数据目录不存在"
    print(f"✅ 数据目录: {data_dir}")
except Exception as e:
    print(f"❌ 测试失败: {e}")
    sys.exit(1)

# 测试 3：获取配置目录
print("\n[测试 3] 获取配置目录...")
try:
    config_dir = path_service.get_config_dir()
    assert config_dir.exists(), "配置目录不存在"
    print(f"✅ 配置目录: {config_dir}")
except Exception as e:
    print(f"❌ 测试失败: {e}")
    sys.exit(1)

# 测试 4：获取日志目录
print("\n[测试 4] 获取日志目录...")
try:
    log_dir = path_service.get_log_dir()
    assert log_dir.exists(), "日志目录不存在"
    print(f"✅ 日志目录: {log_dir}")
except Exception as e:
    print(f"❌ 测试失败: {e}")
    sys.exit(1)

# 测试 5：获取缓存目录
print("\n[测试 5] 获取缓存目录...")
try:
    cache_dir = path_service.get_cache_dir()
    assert cache_dir.exists(), "缓存目录不存在"
    print(f"✅ 缓存目录: {cache_dir}")
except Exception as e:
    print(f"❌ 测试失败: {e}")
    sys.exit(1)

# 测试 6：单例模式
print("\n[测试 6] 测试单例模式...")
try:
    from core.services import path_service as ps1
    from core.services import path_service as ps2
    assert ps1 is ps2, "path_service 不是单例"
    print("✅ 单例模式测试通过")
except Exception as e:
    print(f"❌ 测试失败: {e}")
    sys.exit(1)

# 测试 7：LogService
print("\n[测试 7] 测试 LogService...")
try:
    logger = log_service.get_logger("test")
    logger.info("这是一条测试日志")
    print("✅ LogService 测试通过")
except Exception as e:
    print(f"❌ 测试失败: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# 测试 8：服务状态
print("\n[测试 8] 测试服务状态...")
try:
    from core.services import _service_states, ServiceState
    assert _service_states['path'] == ServiceState.INITIALIZED, "PathService 未初始化"
    assert _service_states['log'] == ServiceState.INITIALIZED, "LogService 未初始化"
    print("✅ 服务状态测试通过")
except Exception as e:
    print(f"❌ 测试失败: {e}")
    sys.exit(1)

# 测试 9：LogService 单例
print("\n[测试 9] 测试 LogService 单例...")
try:
    from core.services import log_service as ls1
    from core.services import log_service as ls2
    assert ls1 is ls2, "log_service 不是单例"
    print("✅ LogService 单例测试通过")
except Exception as e:
    print(f"❌ 测试失败: {e}")
    sys.exit(1)

print("\n" + "=" * 60)
print("✅ Level 0 服务所有测试通过！")
print("=" * 60)

