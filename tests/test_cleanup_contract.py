"""Unit tests for cleanup contract (Task 14.4).

Tests CleanupResult success, failure, exception, and timeout scenarios.
"""
import time
import pytest
from unittest.mock import Mock

from core.utils.cleanup_result import CleanupResult, ModuleCleanupFailure
from core.module_interface import IModule
from core.config.thread_config import ThreadConfiguration


class MockModule:
    """Mock module for testing cleanup scenarios."""
    
    def __init__(self, cleanup_behavior="success", cleanup_delay=0.0, raise_exception=False):
        """Initialize mock module.
        
        Args:
            cleanup_behavior: "success", "failure", or "exception"
            cleanup_delay: Delay in seconds before cleanup completes
            raise_exception: Whether to raise an exception during cleanup
        """
        self.cleanup_behavior = cleanup_behavior
        self.cleanup_delay = cleanup_delay
        self.raise_exception = raise_exception
        self.cleanup_called = False
        self.request_stop_called = False
    
    def request_stop(self):
        """Request module to stop."""
        self.request_stop_called = True
    
    def cleanup(self) -> CleanupResult:
        """Cleanup with configurable behavior."""
        self.cleanup_called = True
        
        # Simulate delay
        if self.cleanup_delay > 0:
            time.sleep(self.cleanup_delay)
        
        # Raise exception if configured
        if self.raise_exception:
            raise RuntimeError("Cleanup failed with exception")
        
        # Return result based on behavior
        if self.cleanup_behavior == "success":
            return CleanupResult.success_result()
        elif self.cleanup_behavior == "failure":
            return CleanupResult.failure_result(
                error_message="Cleanup failed",
                errors=["Error 1", "Error 2"]
            )
        else:
            return CleanupResult.success_result()


class TestCleanupContract:
    """Test suite for cleanup contract."""
    
    def test_cleanup_result_success(self):
        """Test CleanupResult.success_result()."""
        result = CleanupResult.success_result()
        
        assert result.success is True
        assert result.error_message is None
        assert result.errors == []
        assert result.duration_ms == 0
    
    def test_cleanup_result_failure(self):
        """Test CleanupResult.failure_result() with error message."""
        result = CleanupResult.failure_result(
            error_message="Test error",
            errors=["error1", "error2"]
        )
        
        assert result.success is False
        assert result.error_message == "Test error"
        assert result.errors == ["error1", "error2"]
        assert result.duration_ms == 0
    
    def test_cleanup_result_failure_no_errors(self):
        """Test CleanupResult.failure_result() without errors list."""
        result = CleanupResult.failure_result(error_message="Test error")
        
        assert result.success is False
        assert result.error_message == "Test error"
        assert result.errors == []
    
    def test_module_cleanup_success(self):
        """Test module cleanup returns success."""
        module = MockModule(cleanup_behavior="success")
        result = module.cleanup()
        
        assert module.cleanup_called is True
        assert result.success is True
        assert result.error_message is None
    
    def test_module_cleanup_failure(self):
        """Test module cleanup returns failure."""
        module = MockModule(cleanup_behavior="failure")
        result = module.cleanup()
        
        assert module.cleanup_called is True
        assert result.success is False
        assert result.error_message == "Cleanup failed"
        assert result.errors == ["Error 1", "Error 2"]
    
    def test_module_cleanup_exception(self):
        """Test exception during module cleanup."""
        module = MockModule(raise_exception=True)
        
        with pytest.raises(RuntimeError, match="Cleanup failed with exception"):
            module.cleanup()
        
        assert module.cleanup_called is True
    
    def test_module_cleanup_timeout(self):
        """Test cleanup timeout detection."""
        # Create a module that takes 2 seconds to cleanup
        module = MockModule(cleanup_delay=2.0)
        
        # Simulate timeout by checking if cleanup is still running after 0.5s
        import threading
        
        result_container = {"result": None, "exception": None, "completed": False}
        
        def cleanup_wrapper():
            try:
                result_container["result"] = module.cleanup()
                result_container["completed"] = True
            except Exception as e:
                result_container["exception"] = e
                result_container["completed"] = True
        
        cleanup_thread = threading.Thread(target=cleanup_wrapper, daemon=True)
        cleanup_thread.start()
        
        # Wait for 0.5 seconds (less than cleanup_delay)
        cleanup_thread.join(timeout=0.5)
        
        # Thread should still be alive (timeout)
        assert cleanup_thread.is_alive(), "Cleanup should still be running"
        assert result_container["completed"] is False, "Cleanup should not have completed"
        
        # Wait for cleanup to actually finish (for cleanup)
        cleanup_thread.join(timeout=2.0)

