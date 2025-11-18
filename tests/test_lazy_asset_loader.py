# -*- coding: utf-8 -*-

"""
测试 LazyAssetLoader 组件
"""

import pytest
from unittest.mock import Mock, MagicMock, patch
from PyQt6.QtCore import QCoreApplication


@pytest.fixture(scope="module")
def qapp():
    """创建 QApplication 实例（整个模块共享）"""
    app = QCoreApplication.instance()
    if app is None:
        app = QCoreApplication([])
    return app


class TestLazyAssetLoaderImplementation:
    """测试 LazyAssetLoader 的实现（代码检查）"""

    def test_file_exists(self):
        """测试文件存在"""
        from pathlib import Path
        file_path = Path('modules/asset_manager/logic/lazy_asset_loader.py')
        assert file_path.exists()

    def test_classes_exist(self):
        """测试类存在"""
        from modules.asset_manager.logic.lazy_asset_loader import LazyAssetLoader, _load_assets_task
        assert LazyAssetLoader is not None
        assert _load_assets_task is not None

    def test_load_assets_task_is_function(self):
        """测试 _load_assets_task 是函数"""
        from modules.asset_manager.logic.lazy_asset_loader import _load_assets_task
        import inspect
        assert inspect.isfunction(_load_assets_task)

    def test_load_assets_task_has_cancel_token_param(self):
        """测试 _load_assets_task 有 cancel_token 参数"""
        from modules.asset_manager.logic.lazy_asset_loader import _load_assets_task
        import inspect
        sig = inspect.signature(_load_assets_task)
        assert 'cancel_token' in sig.parameters
    
    def test_lazy_asset_loader_methods_exist(self):
        """测试 LazyAssetLoader 的方法存在"""
        from modules.asset_manager.logic.lazy_asset_loader import LazyAssetLoader
        
        assert hasattr(LazyAssetLoader, 'ensure_loaded')
        assert hasattr(LazyAssetLoader, 'is_loaded')
        assert hasattr(LazyAssetLoader, 'is_loading')
        assert hasattr(LazyAssetLoader, 'get_error')
        assert hasattr(LazyAssetLoader, 'reset')
    
    def test_ensure_loaded_signature(self):
        """测试 ensure_loaded 方法签名"""
        import inspect
        from modules.asset_manager.logic.lazy_asset_loader import LazyAssetLoader
        
        sig = inspect.signature(LazyAssetLoader.ensure_loaded)
        assert 'on_complete' in sig.parameters
    
    def test_implementation_has_state_flags(self):
        """测试实现包含状态标志"""
        import inspect
        from modules.asset_manager.logic.lazy_asset_loader import LazyAssetLoader

        source = inspect.getsource(LazyAssetLoader.__init__)
        assert '_loaded' in source
        assert '_loading' in source
        assert '_error_message' in source
        assert '_task_id' in source  # 使用 ThreadManager 的 task_id
    
    def test_implementation_handles_concurrent_calls(self):
        """测试实现处理并发调用"""
        import inspect
        from modules.asset_manager.logic.lazy_asset_loader import LazyAssetLoader
        
        source = inspect.getsource(LazyAssetLoader)
        # 检查是否有回调队列
        assert '_pending_callbacks' in source or 'callbacks' in source.lower()
    
    def test_implementation_has_logging(self):
        """测试实现包含日志记录"""
        import inspect
        from modules.asset_manager.logic.lazy_asset_loader import LazyAssetLoader
        
        source = inspect.getsource(LazyAssetLoader)
        assert 'logger' in source.lower()
        assert 'logger.info' in source or 'self.logger.info' in source


class TestLazyAssetLoaderBehavior:
    """测试 LazyAssetLoader 的行为（需要 QApplication）"""

    def test_initial_state(self, qapp):
        """测试初始状态"""
        from modules.asset_manager.logic.lazy_asset_loader import LazyAssetLoader

        mock_logic = Mock()
        loader = LazyAssetLoader(mock_logic)

        assert loader.is_loaded() == False
        assert loader.is_loading() == False
        assert loader.get_error() == ""
        assert loader._task_id is None

    @patch('core.utils.thread_utils.get_thread_manager')
    def test_ensure_loaded_starts_loading(self, mock_get_tm, qapp):
        """测试 ensure_loaded 启动加载"""
        from modules.asset_manager.logic.lazy_asset_loader import LazyAssetLoader

        # Mock ThreadManager
        mock_tm = Mock()
        mock_tm.run_in_thread.return_value = (None, None, "task_123")
        mock_get_tm.return_value = mock_tm

        mock_logic = Mock()
        loader = LazyAssetLoader(mock_logic)

        callback = Mock()
        loader.ensure_loaded(callback)

        # 应该开始加载
        assert loader.is_loading() == True
        assert loader.is_loaded() == False
        assert loader._task_id == "task_123"

        # 应该调用 ThreadManager.run_in_thread
        mock_tm.run_in_thread.assert_called_once()

    def test_ensure_loaded_success(self, qapp):
        """测试加载成功（通过直接调用回调模拟）"""
        from modules.asset_manager.logic.lazy_asset_loader import LazyAssetLoader

        mock_logic = Mock()
        loader = LazyAssetLoader(mock_logic)

        callback = Mock()

        # 模拟加载过程
        loader._loading = True
        loader._on_load_complete(True, "")

        # 应该加载成功
        assert loader.is_loaded() == True
        assert loader.is_loading() == False
        assert loader.get_error() == ""

    def test_ensure_loaded_already_loaded(self, qapp):
        """测试已加载时立即返回"""
        from modules.asset_manager.logic.lazy_asset_loader import LazyAssetLoader

        mock_logic = Mock()
        loader = LazyAssetLoader(mock_logic)
        loader._loaded = True

        callback = Mock()
        loader.ensure_loaded(callback)

        # 应该立即调用回调
        callback.assert_called_once_with(True, "")

        # 不应该有 task_id
        assert loader._task_id is None

    @patch('core.utils.thread_utils.get_thread_manager')
    def test_reset_cancels_task(self, mock_get_tm, qapp):
        """测试 reset 取消正在运行的任务"""
        from modules.asset_manager.logic.lazy_asset_loader import LazyAssetLoader

        # Mock ThreadManager
        mock_tm = Mock()
        mock_get_tm.return_value = mock_tm

        mock_logic = Mock()
        loader = LazyAssetLoader(mock_logic)

        # 模拟正在加载
        loader._loading = True
        loader._task_id = "task_123"

        # 重置
        loader.reset()

        # 应该取消任务
        mock_tm.cancel_task.assert_called_once_with("task_123")

        # 状态应该被重置
        assert loader.is_loaded() == False
        assert loader.is_loading() == False
        assert loader._task_id is None


if __name__ == '__main__':
    pytest.main([__file__, '-v'])

