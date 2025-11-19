# Cleanup Contract Implementation Guide

## Overview

This guide explains how to implement the cleanup contract for modules that use ThreadManager. The cleanup contract ensures graceful shutdown and proper resource cleanup.

## What is the Cleanup Contract?

The cleanup contract is a standardized interface for module shutdown:

1. **`request_stop()`** - Signal the module to stop accepting new work
2. **`cleanup()`** - Clean up resources and return a `CleanupResult`

## CleanupResult

The `CleanupResult` class represents the outcome of a cleanup operation:

```python
from core.utils.cleanup_result import CleanupResult

# Success
result = CleanupResult.success_result()

# Failure with error message
result = CleanupResult.failure_result("Database connection failed to close")

# Partial success with warnings
result = CleanupResult.partial_result(["Cache not cleared", "Temp files remain"])
```

## Basic Implementation

### Minimal Module

```python
from core.utils.cleanup_result import CleanupResult

class MyModule:
    def __init__(self):
        self.should_stop = False
    
    def request_stop(self):
        """Signal the module to stop accepting new work."""
        self.should_stop = True
    
    def cleanup(self) -> CleanupResult:
        """Clean up resources."""
        try:
            # Perform cleanup
            self.close_connections()
            return CleanupResult.success_result()
        except Exception as e:
            return CleanupResult.failure_result(str(e))
```

### Module with ThreadManager

```python
from core.utils.thread_manager import EnhancedThreadManager
from core.utils.cleanup_result import CleanupResult

class MyModule:
    def __init__(self):
        self.thread_manager = EnhancedThreadManager.get_instance()
        self.active_tasks = []
    
    def request_stop(self):
        """Cancel all active tasks."""
        for task_id in self.active_tasks:
            self.thread_manager.cancel_task(task_id)
    
    def cleanup(self) -> CleanupResult:
        """Clean up resources."""
        try:
            # Wait for tasks to complete (they're already cancelled)
            # ThreadManager will handle timeout
            
            # Clean up other resources
            self.close_files()
            self.clear_cache()
            
            return CleanupResult.success_result()
        except Exception as e:
            return CleanupResult.failure_result(str(e))
```

## Best Practices

### 1. Implement Both Methods

```python
class GoodModule:
    def request_stop(self):
        """Always implement this, even if empty."""
        self.should_stop = True
    
    def cleanup(self) -> CleanupResult:
        """Always return CleanupResult."""
        return CleanupResult.success_result()
```

### 2. Make request_stop() Fast

```python
class FastStopModule:
    def request_stop(self):
        """Should complete in < 100ms."""
        # ✅ Just set flags and cancel tasks
        self.should_stop = True
        for task_id in self.active_tasks:
            self.thread_manager.cancel_task(task_id)
        
        # ❌ Don't wait for tasks to complete here
        # ❌ Don't do heavy I/O here
```

### 3. Handle Cleanup Errors Gracefully

```python
class RobustModule:
    def cleanup(self) -> CleanupResult:
        """Handle errors without crashing."""
        errors = []
        
        # Try to close database
        try:
            self.db.close()
        except Exception as e:
            errors.append(f"Database: {e}")
        
        # Try to close files
        try:
            self.file.close()
        except Exception as e:
            errors.append(f"File: {e}")
        
        # Return appropriate result
        if not errors:
            return CleanupResult.success_result()
        else:
            return CleanupResult.partial_result(errors)
```

### 4. Clean Up in Correct Order

```python
class OrderedCleanupModule:
    def cleanup(self) -> CleanupResult:
        """Clean up in reverse order of initialization."""
        try:
            # 1. Stop accepting new work (already done in request_stop)
            
            # 2. Cancel active tasks
            for task_id in self.active_tasks:
                self.thread_manager.cancel_task(task_id)
            
            # 3. Close connections
            self.db_connection.close()
            
            # 4. Clear caches
            self.cache.clear()
            
            # 5. Delete temp files
            self.cleanup_temp_files()
            
            return CleanupResult.success_result()
        except Exception as e:
            return CleanupResult.failure_result(str(e))
```

### 5. Don't Block Forever

```python
class TimeoutAwareModule:
    def cleanup(self) -> CleanupResult:
        """Respect cleanup timeout (default 2 seconds)."""
        try:
            # ✅ Quick cleanup only
            self.cache.clear()
            self.close_connections()
            
            # ❌ Don't wait for external services
            # ❌ Don't do expensive I/O
            
            return CleanupResult.success_result()
        except Exception as e:
            return CleanupResult.failure_result(str(e))
```

## Advanced Patterns

### Cleanup with Progress Tracking

```python
class ProgressTrackingModule:
    def cleanup(self) -> CleanupResult:
        """Track cleanup progress."""
        steps = [
            ("Cancelling tasks", self.cancel_tasks),
            ("Closing database", self.close_db),
            ("Clearing cache", self.clear_cache),
        ]
        
        errors = []
        
        for step_name, step_func in steps:
            try:
                step_func()
            except Exception as e:
                errors.append(f"{step_name}: {e}")
        
        if not errors:
            return CleanupResult.success_result()
        else:
            return CleanupResult.partial_result(errors)
```

### Cleanup with Resource Tracking

```python
class ResourceTrackingModule:
    def __init__(self):
        self.resources = []  # Track all resources
    
    def open_file(self, path):
        """Track opened files."""
        f = open(path)
        self.resources.append(("file", f))
        return f
    
    def cleanup(self) -> CleanupResult:
        """Clean up all tracked resources."""
        errors = []
        
        for resource_type, resource in self.resources:
            try:
                if resource_type == "file":
                    resource.close()
                elif resource_type == "connection":
                    resource.disconnect()
            except Exception as e:
                errors.append(f"{resource_type}: {e}")
        
        self.resources.clear()
        
        if not errors:
            return CleanupResult.success_result()
        else:
            return CleanupResult.partial_result(errors)
```

### Cleanup with Retry Logic

```python
import time

class RetryCleanupModule:
    def cleanup(self) -> CleanupResult:
        """Retry critical cleanup operations."""
        # Try to close database with retry
        for attempt in range(3):
            try:
                self.db.close()
                break
            except Exception as e:
                if attempt == 2:  # Last attempt
                    return CleanupResult.failure_result(f"Database close failed: {e}")
                time.sleep(0.1)  # Brief retry delay
        
        return CleanupResult.success_result()
```

## Common Mistakes

### ❌ Not Returning CleanupResult

```python
class BadModule:
    def cleanup(self):
        """Missing return type annotation and CleanupResult."""
        self.close()
        # ❌ Should return CleanupResult!
```

### ❌ Raising Exceptions

```python
class CrashyModule:
    def cleanup(self) -> CleanupResult:
        """Don't raise exceptions!"""
        self.db.close()  # ❌ May raise exception
        return CleanupResult.success_result()
```

**Fix:**
```python
class SafeModule:
    def cleanup(self) -> CleanupResult:
        """Catch and report exceptions."""
        try:
            self.db.close()
            return CleanupResult.success_result()
        except Exception as e:
            return CleanupResult.failure_result(str(e))
```

### ❌ Blocking in request_stop()

```python
class BlockingModule:
    def request_stop(self):
        """Don't block here!"""
        for task_id in self.active_tasks:
            self.thread_manager.cancel_task(task_id)
        
        # ❌ Don't wait for tasks to complete
        time.sleep(5)
```

## Testing Cleanup

```python
import pytest
from core.utils.cleanup_result import CleanupResult

def test_cleanup_success():
    """Test successful cleanup."""
    module = MyModule()
    module.request_stop()
    result = module.cleanup()
    
    assert result.is_success
    assert not result.errors

def test_cleanup_failure():
    """Test cleanup failure handling."""
    module = BrokenModule()
    module.request_stop()
    result = module.cleanup()
    
    assert not result.is_success
    assert len(result.errors) > 0

def test_cleanup_timeout():
    """Test cleanup respects timeout."""
    import time
    
    module = SlowModule()
    module.request_stop()
    
    start = time.time()
    result = module.cleanup()
    duration = time.time() - start
    
    # Should complete within cleanup_timeout (2 seconds default)
    assert duration < 2.5
```

## See Also

- [Cancellation-Aware Tasks Guide](CANCELLATION_AWARE_TASKS_GUIDE.md)
- [Timeout Configuration Guide](TIMEOUT_CONFIGURATION_GUIDE.md)
- [Troubleshooting Guide](TROUBLESHOOTING_GUIDE.md)

