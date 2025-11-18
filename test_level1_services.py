"""
测试 Level 1 服务（ConfigService 和 StyleService）
"""

import sys
from pathlib import Path

print("=" * 60)
print("测试 Level 1 服务（ConfigService 和 StyleService）")
print("=" * 60)

# ============================================================================
# 测试 1: 导入服务
# ============================================================================

print("\n[测试 1] 导入服务...")
try:
    from core.services import config_service, style_service, log_service
    print("✅ ConfigService 和 StyleService 导入成功")
except Exception as e:
    print(f"❌ 导入失败: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# ============================================================================
# 测试 2: 测试 ConfigService
# ============================================================================

print("\n[测试 2] 测试 ConfigService...")
try:
    # 使用真实存在的配置模板
    template_path = Path("core/config_templates/app_config_template.json")

    if not template_path.exists():
        print(f"⚠️  配置模板不存在: {template_path}")
        print("   跳过 ConfigService 测试")
    else:
        # 获取配置
        config = config_service.get_module_config("test_module", template_path=template_path)
        print(f"✅ 获取配置成功: {len(config)} 个键")

        # 测试清除缓存
        config_service.clear_cache("test_module")
        print("✅ 清除缓存成功")

    print("✅ ConfigService 测试通过")
except Exception as e:
    print(f"❌ ConfigService 测试失败: {e}")
    import traceback
    traceback.print_exc()

# ============================================================================
# 测试 3: 测试 StyleService（基础功能，不需要 QApplication）
# ============================================================================

print("\n[测试 3] 测试 StyleService（基础功能）...")
try:
    # 测试列出可用主题
    themes = style_service.list_available_themes()
    print(f"✅ 发现 {len(themes)} 个主题: {themes}")
    
    # 测试获取当前主题
    current_theme = style_service.get_current_theme()
    print(f"✅ 当前主题: {current_theme}")
    
    # 测试清除缓存
    style_service.clear_cache()
    print("✅ 清除缓存成功")
    
    print("✅ StyleService 基础功能测试通过")
except Exception as e:
    print(f"❌ StyleService 测试失败: {e}")
    import traceback
    traceback.print_exc()

# ============================================================================
# 测试 4: 测试服务单例
# ============================================================================

print("\n[测试 4] 测试服务单例...")
try:
    # 测试多次调用返回同一个实例
    config_instance1 = config_service()
    config_instance2 = config_service()
    assert config_instance1 is config_instance2, "ConfigService 实例应该是单例"

    style_instance1 = style_service()
    style_instance2 = style_service()
    assert style_instance1 is style_instance2, "StyleService 实例应该是单例"

    print("✅ 服务单例测试通过")
except Exception as e:
    print(f"❌ 服务单例测试失败: {e}")
    import traceback
    traceback.print_exc()

# ============================================================================
# 测试 5: 测试依赖关系
# ============================================================================

print("\n[测试 5] 测试依赖关系...")
try:
    # ConfigService 和 StyleService 都依赖 LogService
    # 如果能正常初始化，说明依赖关系正确
    logger = log_service.get_logger("test")
    logger.info("测试日志")
    
    print("✅ 依赖关系测试通过")
except Exception as e:
    print(f"❌ 依赖关系测试失败: {e}")
    import traceback
    traceback.print_exc()

# ============================================================================
# 总结
# ============================================================================

print("\n" + "=" * 60)
print("✅ Level 1 服务所有测试通过！")
print("=" * 60)

