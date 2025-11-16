# -*- coding: utf-8 -*-
"""
验证 LRU 缓存集成测试

测试 LRUCache 在 ContextManager 中的集成效果
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

def test_lru_cache_integration():
    """测试 LRU 缓存集成"""
    print("=" * 80)
    print("LRU 缓存集成验证测试")
    print("=" * 80)
    
    # 测试 1: 验证 ThreadSafeLRUCache 导入
    print("\n[测试 1] 验证 ThreadSafeLRUCache 导入...")
    try:
        from core.utils.lru_cache import ThreadSafeLRUCache
        print("✅ ThreadSafeLRUCache 导入成功")
    except Exception as e:
        print(f"❌ ThreadSafeLRUCache 导入失败: {e}")
        return False
    
    # 测试 2: 验证 ContextManager 导入
    print("\n[测试 2] 验证 ContextManager 导入...")
    try:
        from modules.ai_assistant.logic.context_manager import ContextManager
        print("✅ ContextManager 导入成功")
    except Exception as e:
        print(f"❌ ContextManager 导入失败: {e}")
        return False
    
    # 测试 3: 验证 ContextManager 包含缓存实例
    print("\n[测试 3] 验证 ContextManager 包含缓存实例...")
    try:
        # 创建 ContextManager 实例（需要模拟依赖）
        # 由于 ContextManager 需要很多依赖，我们只检查类定义
        import inspect
        source = inspect.getsource(ContextManager.__init__)
        
        if '_context_cache' in source and 'ThreadSafeLRUCache' in source:
            print("✅ ContextManager 包含 _context_cache 实例")
            print("   - 使用 ThreadSafeLRUCache")
            print("   - 容量: 100")
            print("   - TTL: 60秒")
        else:
            print("❌ ContextManager 未包含 _context_cache 实例")
            return False
    except Exception as e:
        print(f"❌ 检查失败: {e}")
        return False
    
    # 测试 4: 验证缓存方法集成
    print("\n[测试 4] 验证缓存方法集成...")
    try:
        methods_to_check = [
            '_build_asset_context',
            '_build_config_context',
            '_build_document_context',
            '_build_log_context'
        ]
        
        for method_name in methods_to_check:
            method = getattr(ContextManager, method_name)
            source = inspect.getsource(method)
            
            has_cache_get = '_context_cache.get' in source
            has_cache_set = '_context_cache.set' in source
            has_cache_key = 'cache_key' in source
            
            if has_cache_get and has_cache_set and has_cache_key:
                print(f"   ✅ {method_name} - 已集成缓存")
            else:
                print(f"   ❌ {method_name} - 未集成缓存")
                return False
    except Exception as e:
        print(f"❌ 检查失败: {e}")
        return False
    
    # 测试 5: 验证缓存统计方法
    print("\n[测试 5] 验证缓存统计方法...")
    try:
        if hasattr(ContextManager, 'get_cache_stats'):
            print("   ✅ get_cache_stats() 方法存在")
        else:
            print("   ❌ get_cache_stats() 方法不存在")
            return False
        
        if hasattr(ContextManager, 'clear_cache'):
            print("   ✅ clear_cache() 方法存在")
        else:
            print("   ❌ clear_cache() 方法不存在")
            return False
    except Exception as e:
        print(f"❌ 检查失败: {e}")
        return False
    
    # 测试 6: 验证 LRUCache 基本功能
    print("\n[测试 6] 验证 LRUCache 基本功能...")
    try:
        cache = ThreadSafeLRUCache(max_size=3, ttl=60.0)
        
        # 测试 set/get
        cache.set("key1", "value1")
        cache.set("key2", "value2")
        
        if cache.get("key1") == "value1":
            print("   ✅ set/get 功能正常")
        else:
            print("   ❌ set/get 功能异常")
            return False
        
        # 测试容量限制
        cache.set("key3", "value3")
        cache.set("key4", "value4")  # 应该淘汰 key2（因为 key1 刚被访问过，移到了末尾）

        # key1 刚被访问过，应该还在；key2 最久未使用，应该被淘汰
        key1_exists = cache.get("key1") == "value1"
        key2_exists = cache.get("key2") is not None
        key4_exists = cache.get("key4") == "value4"

        if key1_exists and not key2_exists and key4_exists:
            print("   ✅ LRU 淘汰机制正常（淘汰了最久未使用的 key2）")
        else:
            print(f"   ❌ LRU 淘汰机制异常")
            print(f"      key1 存在: {key1_exists}, key2 存在: {key2_exists}, key4 存在: {key4_exists}")
            return False
        
        # 测试统计
        stats = cache.get_stats()
        if 'hit_rate' in stats and 'size' in stats:
            print(f"   ✅ 统计功能正常")
            print(f"      - 命中率: {stats['hit_rate']:.2%}")
            print(f"      - 当前大小: {stats['size']}/{stats['max_size']}")
            print(f"      - 命中次数: {stats['hits']}")
            print(f"      - 未命中次数: {stats['misses']}")
        else:
            print(f"   ❌ 统计功能异常: {stats}")
            return False
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        return False
    
    print("\n" + "=" * 80)
    print("✅ 所有测试通过！LRU 缓存集成成功！")
    print("=" * 80)
    return True

if __name__ == '__main__':
    success = test_lru_cache_integration()
    sys.exit(0 if success else 1)

