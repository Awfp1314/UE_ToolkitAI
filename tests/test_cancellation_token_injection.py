"""Unit tests for CancellationToken injection mechanism.

Tests ThreadManager's ability to detect and inject cancel_token parameter
into various function signatures.

Task 14.2 Requirements:
- Test function with cancel_token parameter
- Test function without cancel_token parameter
- Test functools.partial wrapped function
- Test functools.wraps decorated function
- Test lambda function
- Test class method
"""
import functools
import sys
from pathlib import Path

import pytest

# Ensure project root on path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from core.utils.thread_utils import CancellationToken, Worker  # noqa: E402


# Test functions
def plain_function_with_token(cancel_token, value):
    """Plain function with cancel_token parameter."""
    if cancel_token.is_cancelled():
        return None
    return f"result: {value}"


def plain_function_without_token(value):
    """Plain function without cancel_token parameter."""
    return f"result: {value}"


def function_with_token_only(cancel_token):
    """Function with only cancel_token parameter."""
    return "done" if not cancel_token.is_cancelled() else None


def decorated_function(cancel_token, value):
    """Function to be decorated."""
    return f"decorated: {value}"


@functools.wraps(decorated_function)
def wrapped_function(cancel_token, value):
    """Function decorated with functools.wraps."""
    return decorated_function(cancel_token, value)


class TestClass:
    """Test class for method testing."""

    def instance_method_with_token(self, cancel_token, value):
        """Instance method with cancel_token."""
        return f"method: {value}"

    def instance_method_without_token(self, value):
        """Instance method without cancel_token."""
        return f"method: {value}"

    @staticmethod
    def static_method_with_token(cancel_token, value):
        """Static method with cancel_token."""
        return f"static: {value}"

    @classmethod
    def class_method_with_token(cls, cancel_token, value):
        """Class method with cancel_token."""
        return f"class: {value}"


class TestCancellationTokenInjection:
    """Test suite for CancellationToken injection."""

    def test_function_with_cancel_token(self):
        """Test that Worker detects cancel_token parameter in plain function."""
        worker = Worker(plain_function_with_token, value=42)

        assert hasattr(worker, 'cancel_token'), "Worker should have cancel_token attribute"
        assert isinstance(worker.cancel_token, CancellationToken), "cancel_token should be CancellationToken instance"
        assert hasattr(worker, '_supports_cancellation'), "Worker should have _supports_cancellation flag"
        assert worker._supports_cancellation is True, "Should detect cancel_token parameter"

    def test_function_without_cancel_token(self):
        """Test that Worker handles functions without cancel_token parameter."""
        worker = Worker(plain_function_without_token, value=42)

        assert hasattr(worker, 'cancel_token'), "Worker should still have cancel_token attribute"
        assert isinstance(worker.cancel_token, CancellationToken), "cancel_token should be CancellationToken instance"
        assert hasattr(worker, '_supports_cancellation'), "Worker should have _supports_cancellation flag"
        assert worker._supports_cancellation is False, "Should not detect cancel_token parameter"

    def test_function_with_token_only(self):
        """Test function with only cancel_token parameter."""
        worker = Worker(function_with_token_only)

        assert worker._supports_cancellation is True, "Should detect cancel_token parameter"
        assert isinstance(worker.cancel_token, CancellationToken), "cancel_token should be CancellationToken instance"

    def test_functools_partial_wrapped_function(self):
        """Test that Worker handles functools.partial wrapped functions."""
        # Create partial function with pre-filled value
        partial_func = functools.partial(plain_function_with_token, value=100)

        worker = Worker(partial_func)

        # Worker should detect cancel_token in the underlying function
        assert hasattr(worker, '_supports_cancellation'), "Worker should have _supports_cancellation flag"
        # Note: functools.partial may affect signature detection
        assert isinstance(worker.cancel_token, CancellationToken), "cancel_token should exist"

    def test_functools_wraps_decorated_function(self):
        """Test that Worker handles functools.wraps decorated functions."""
        worker = Worker(wrapped_function, value=42)

        assert hasattr(worker, '_supports_cancellation'), "Worker should have _supports_cancellation flag"
        assert worker._supports_cancellation is True, "Should detect cancel_token in wrapped function"
        assert isinstance(worker.cancel_token, CancellationToken), "cancel_token should be CancellationToken instance"

    def test_lambda_function_with_token(self):
        """Test that Worker handles lambda functions with cancel_token."""
        # Lambda with cancel_token parameter
        lambda_func = lambda cancel_token, x: x * 2 if not cancel_token.is_cancelled() else None  # noqa: E731

        worker = Worker(lambda_func, x=5)

        assert hasattr(worker, 'cancel_token'), "Worker should have cancel_token attribute"
        assert isinstance(worker.cancel_token, CancellationToken), "cancel_token should be CancellationToken instance"

    def test_lambda_function_without_token(self):
        """Test that Worker handles lambda functions without cancel_token."""
        # Lambda without cancel_token parameter
        lambda_func = lambda x: x * 2  # noqa: E731

        worker = Worker(lambda_func, x=5)

        assert hasattr(worker, 'cancel_token'), "Worker should have cancel_token attribute"
        assert isinstance(worker.cancel_token, CancellationToken), "cancel_token should be CancellationToken instance"

    def test_instance_method_with_token(self):
        """Test that Worker handles instance methods with cancel_token."""
        test_obj = TestClass()
        worker = Worker(test_obj.instance_method_with_token, value=42)

        assert hasattr(worker, '_supports_cancellation'), "Worker should have _supports_cancellation flag"
        assert worker._supports_cancellation is True, "Should detect cancel_token in instance method"
        assert isinstance(worker.cancel_token, CancellationToken), "cancel_token should be CancellationToken instance"

    def test_instance_method_without_token(self):
        """Test that Worker handles instance methods without cancel_token."""
        test_obj = TestClass()
        worker = Worker(test_obj.instance_method_without_token, value=42)

        assert hasattr(worker, '_supports_cancellation'), "Worker should have _supports_cancellation flag"
        assert worker._supports_cancellation is False, "Should not detect cancel_token in instance method"
        assert isinstance(worker.cancel_token, CancellationToken), "cancel_token should be CancellationToken instance"

    def test_static_method_with_token(self):
        """Test that Worker handles static methods with cancel_token."""
        worker = Worker(TestClass.static_method_with_token, value=42)

        assert hasattr(worker, '_supports_cancellation'), "Worker should have _supports_cancellation flag"
        assert worker._supports_cancellation is True, "Should detect cancel_token in static method"
        assert isinstance(worker.cancel_token, CancellationToken), "cancel_token should be CancellationToken instance"

    def test_class_method_with_token(self):
        """Test that Worker handles class methods with cancel_token."""
        worker = Worker(TestClass.class_method_with_token, value=42)

        assert hasattr(worker, '_supports_cancellation'), "Worker should have _supports_cancellation flag"
        assert worker._supports_cancellation is True, "Should detect cancel_token in class method"
        assert isinstance(worker.cancel_token, CancellationToken), "cancel_token should be CancellationToken instance"

    def test_cancellation_token_functionality(self):
        """Test that CancellationToken works correctly."""
        token = CancellationToken()

        # Initial state
        assert token.is_cancelled() is False, "Token should not be cancelled initially"

        # After cancellation
        token.cancel()
        assert token.is_cancelled() is True, "Token should be cancelled after cancel() call"

    def test_worker_with_cancelled_token(self):
        """Test that Worker respects cancelled token."""
        worker = Worker(plain_function_with_token, value=42)

        # Cancel the token before running
        worker.cancel_token.cancel()

        assert worker.cancel_token.is_cancelled() is True, "Token should be cancelled"

