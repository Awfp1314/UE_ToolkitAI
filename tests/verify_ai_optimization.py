# -*- coding: utf-8 -*-
"""
AI 助手优化任务验证脚本
验证所有昨天完成的优化任务是否还在
"""

import sys
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

def test_task_1_lru_cache():
    """任务1：验证 LRUCache 组件"""
    print("✅ 任务1：验证 LRUCache 组件...")
    from core.utils.lru_cache import LRUCache, ThreadSafeLRUCache, CacheEntry
    
    # 测试基本功能
    cache = LRUCache(max_size=10, ttl=60.0)
    cache.set("key1", "value1")
    assert cache.get("key1") == "value1"
    stats = cache.get_stats()
    assert stats['hit_rate'] == 1.0
    print("  ✓ LRUCache 基本功能正常")
    
    # 测试线程安全版本
    thread_safe_cache = ThreadSafeLRUCache(max_size=10, ttl=60.0)
    thread_safe_cache.set("key2", "value2")
    assert thread_safe_cache.get("key2") == "value2"
    print("  ✓ ThreadSafeLRUCache 基本功能正常")

def test_task_2_thread_cleanup():
    """任务2：验证 ThreadCleanupMixin 组件"""
    print("✅ 任务2：验证 ThreadCleanupMixin 组件...")
    from core.utils.thread_cleanup import ThreadCleanupMixin
    from PyQt6.QtCore import QThread
    
    # 验证抽象方法存在
    assert hasattr(ThreadCleanupMixin, 'request_stop')
    assert hasattr(ThreadCleanupMixin, 'cleanup')
    print("  ✓ ThreadCleanupMixin 接口正常")

def test_task_4_error_handler():
    """任务4：验证 ErrorHandler 组件"""
    print("✅ 任务4：验证 ErrorHandler 组件...")
    from core.utils.error_handler import ErrorHandler, ErrorMessage
    
    # 测试错误码映射
    assert 401 in ErrorHandler.ERROR_CODE_MAP
    assert 404 in ErrorHandler.ERROR_CODE_MAP
    
    # 测试格式化功能
    error = Exception("API key invalid")
    formatted = ErrorHandler.format_error(error, 401)
    assert formatted.title == '认证失败'
    print("  ✓ ErrorHandler 基本功能正常")

def test_task_5_streaming_buffer():
    """任务5：验证 StreamingBufferManager 组件"""
    print("✅ 任务5：验证 StreamingBufferManager 组件...")
    from modules.ai_assistant.logic.streaming_buffer_manager import StreamingBufferManager
    
    # 验证方法存在
    manager = StreamingBufferManager(flush_interval_ms=100)
    assert hasattr(manager, 'start')
    assert hasattr(manager, 'add_chunk')
    assert hasattr(manager, 'flush')
    assert hasattr(manager, 'stop_and_cleanup')
    print("  ✓ StreamingBufferManager 接口正常")

def test_task_8_lazy_asset_loader():
    """任务8：验证 LazyAssetLoader 组件"""
    print("✅ 任务8：验证 LazyAssetLoader 组件...")
    from modules.asset_manager.logic.lazy_asset_loader import LazyAssetLoader, AssetLoadThread
    
    # 验证类存在
    assert LazyAssetLoader is not None
    assert AssetLoadThread is not None
    print("  ✓ LazyAssetLoader 组件存在")

def test_task_9_tool_status_display():
    """任务9：验证 ToolStatusDisplay 组件"""
    print("✅ 任务9：验证 ToolStatusDisplay 组件...")
    from modules.ai_assistant.ui.tool_status_display import ToolStatusDisplay
    
    # 测试工具名称映射
    friendly_name = ToolStatusDisplay.get_friendly_name("search_assets")
    assert friendly_name == "搜索资产"
    
    status_text = ToolStatusDisplay.show_tool_calling("search_assets")
    assert "搜索资产" in status_text
    print("  ✓ ToolStatusDisplay 基本功能正常")

def test_task_10_safe_print():
    """任务10：验证 safe_print 函数"""
    print("✅ 任务10：验证 safe_print 函数...")
    from core.logger import safe_print, setup_console_encoding
    
    # 测试 safe_print
    safe_print("测试中文输出")
    print("  ✓ safe_print 函数正常")

def test_task_14_faiss_optimization():
    """任务14：验证 FAISS 索引优化"""
    print("✅ 任务14：验证 FAISS 索引优化...")
    from modules.ai_assistant.logic.faiss_memory_store import FaissMemoryStore
    from pathlib import Path
    import tempfile
    
    # 创建临时存储
    with tempfile.TemporaryDirectory() as tmpdir:
        store = FaissMemoryStore(
            storage_dir=Path(tmpdir),
            vector_dim=384,
            user_id="test",
            batch_delete_threshold=50
        )
        
        # 验证新增的方法
        assert hasattr(store, 'count_active')
        assert hasattr(store, 'get_stats')
        assert hasattr(store, 'force_rebuild')
        assert hasattr(store, '_pending_deletes')
        
        # 测试统计功能
        stats = store.get_stats()
        assert 'total' in stats
        assert 'active' in stats
        assert 'pending_deletes' in stats
        
        print("  ✓ FAISS 优化功能正常")

def test_task_15_async_compressor():
    """任务15：验证异步压缩器超时机制"""
    print("✅ 任务15：验证异步压缩器超时机制...")
    from modules.ai_assistant.logic.async_memory_compressor import AsyncMemoryCompressor
    
    # 验证超时相关属性
    # 注意：不实际运行，只验证接口
    assert hasattr(AsyncMemoryCompressor, 'compression_timeout')
    print("  ✓ AsyncMemoryCompressor 超时机制存在")

def main():
    """运行所有验证测试"""
    print("=" * 60)
    print("🔍 开始验证 AI 助手优化任务...")
    print("=" * 60)
    
    try:
        test_task_1_lru_cache()
        test_task_2_thread_cleanup()
        test_task_4_error_handler()
        test_task_5_streaming_buffer()
        test_task_8_lazy_asset_loader()
        test_task_9_tool_status_display()
        test_task_10_safe_print()
        test_task_14_faiss_optimization()
        test_task_15_async_compressor()
        
        print("=" * 60)
        print("🎉 所有验证测试通过！")
        print("=" * 60)
        return 0
        
    except Exception as e:
        print("=" * 60)
        print(f"❌ 验证失败: {e}")
        print("=" * 60)
        import traceback
        traceback.print_exc()
        return 1

if __name__ == "__main__":
    sys.exit(main())

