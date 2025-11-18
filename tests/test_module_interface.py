"""测试 IModule 接口的 CleanupResult 契约"""
import sys
from pathlib import Path

import pytest

# Ensure project root on path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from PyQt6.QtWidgets import QWidget

from core.module_interface import IModule, ModuleMetadata, wrap_legacy_cleanup
from core.utils.cleanup_result import CleanupResult


class MockWidget(QWidget):
    """模拟 QWidget"""
    pass


class NewStyleModule(IModule):
    """新风格模块：返回 CleanupResult"""
    
    def __init__(self):
        self.stop_requested = False
        self.cleanup_called = False
    
    def get_metadata(self) -> ModuleMetadata:
        return ModuleMetadata(
            name="new_style",
            display_name="New Style Module",
            version="1.0.0",
            description="Test module with CleanupResult"
        )
    
    def get_widget(self) -> QWidget:
        return MockWidget()
    
    def initialize(self) -> bool:
        return True
    
    def request_stop(self) -> None:
        self.stop_requested = True
    
    def cleanup(self) -> CleanupResult:
        self.cleanup_called = True
        return CleanupResult.success_result()


class OldStyleModule(IModule):
    """旧风格模块：返回 None（需要包装器）"""
    
    def __init__(self):
        self.cleanup_called = False
    
    def get_metadata(self) -> ModuleMetadata:
        return ModuleMetadata(
            name="old_style",
            display_name="Old Style Module",
            version="1.0.0",
            description="Test module without CleanupResult"
        )
    
    def get_widget(self) -> QWidget:
        return MockWidget()
    
    def initialize(self) -> bool:
        return True
    
    @wrap_legacy_cleanup
    def cleanup(self) -> None:
        """旧风格的 cleanup，返回 None"""
        self.cleanup_called = True


class FailingModule(IModule):
    """失败的模块：cleanup 抛出异常"""
    
    def get_metadata(self) -> ModuleMetadata:
        return ModuleMetadata(
            name="failing",
            display_name="Failing Module",
            version="1.0.0",
            description="Test module that fails cleanup"
        )
    
    def get_widget(self) -> QWidget:
        return MockWidget()
    
    def initialize(self) -> bool:
        return True
    
    def cleanup(self) -> CleanupResult:
        raise RuntimeError("Cleanup failed!")


# ============================================================================
# 测试用例
# ============================================================================

def test_new_style_module_cleanup():
    """测试新风格模块的 cleanup 返回 CleanupResult"""
    module = NewStyleModule()
    result = module.cleanup()
    
    assert isinstance(result, CleanupResult)
    assert result.success is True
    assert module.cleanup_called is True


def test_new_style_module_request_stop():
    """测试新风格模块的 request_stop"""
    module = NewStyleModule()
    module.request_stop()
    
    assert module.stop_requested is True


def test_old_style_module_with_wrapper():
    """测试旧风格模块使用包装器后返回 CleanupResult"""
    module = OldStyleModule()
    result = module.cleanup()
    
    assert isinstance(result, CleanupResult)
    assert result.success is True
    assert module.cleanup_called is True


def test_failing_module_cleanup():
    """测试失败模块的 cleanup 抛出异常"""
    module = FailingModule()
    
    with pytest.raises(RuntimeError, match="Cleanup failed!"):
        module.cleanup()


def test_wrap_legacy_cleanup_decorator():
    """测试 wrap_legacy_cleanup 装饰器"""

    @wrap_legacy_cleanup
    def old_cleanup():
        """旧的 cleanup 函数"""
        pass

    result = old_cleanup()
    assert isinstance(result, CleanupResult)
    assert result.success is True


def test_wrap_legacy_cleanup_with_exception():
    """测试 wrap_legacy_cleanup 装饰器捕获异常"""

    @wrap_legacy_cleanup
    def failing_cleanup():
        """会抛出异常的 cleanup 函数"""
        raise ValueError("Something went wrong")

    result = failing_cleanup()
    assert isinstance(result, CleanupResult)
    assert result.success is False
    assert "Something went wrong" in result.error_message
    assert len(result.errors) > 0


def test_module_default_request_stop():
    """测试模块的默认 request_stop 实现（空操作）"""
    module = NewStyleModule()
    # 默认实现不应该抛出异常
    module.request_stop()
    assert module.stop_requested is True


def test_cleanup_result_success():
    """测试 CleanupResult.success_result()"""
    result = CleanupResult.success_result()
    assert result.success is True
    assert result.error_message is None
    assert result.errors == []


def test_cleanup_result_failure():
    """测试 CleanupResult.failure_result()"""
    result = CleanupResult.failure_result(
        error_message="Test error",
        errors=["error1", "error2"]
    )
    assert result.success is False
    assert result.error_message == "Test error"
    assert result.errors == ["error1", "error2"]

