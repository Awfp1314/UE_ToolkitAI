# Timeout Configuration Guide

## Overview

This guide explains how to configure timeouts for the ThreadManager system. Proper timeout configuration ensures tasks don't run forever and the application can shut down gracefully.

## Timeout Types

The ThreadManager system has three types of timeouts:

1. **Task Timeout** - Maximum time a task can run
2. **Cleanup Timeout** - Maximum time for module cleanup
3. **Global Shutdown Timeout** - Maximum time for entire shutdown

## Configuration File

Timeouts are configured in `config/thread_config.json`:

```json
{
  "thread_pool_size": 5,
  "task_queue_size": 20,
  "task_timeout": 30000,
  "grace_period": 1000,
  "cleanup_timeout": 2000,
  "global_shutdown_timeout": 10000,
  "module_overrides": {
    "ai_assistant": {
      "task_timeout": 60000,
      "cleanup_timeout": 5000
    }
  }
}
```

## Task Timeout

**Default:** 30000ms (30 seconds)

Controls how long a task can run before being cancelled.

### When to Adjust

```python
# Quick tasks (< 5 seconds)
{
  "task_timeout": 5000  # 5 seconds
}

# Medium tasks (5-30 seconds)
{
  "task_timeout": 30000  # 30 seconds (default)
}

# Long tasks (> 30 seconds)
{
  "task_timeout": 60000  # 60 seconds
}

# Very long tasks (AI, rendering, etc.)
{
  "task_timeout": 300000  # 5 minutes
}
```

### Module-Specific Overrides

```json
{
  "task_timeout": 30000,
  "module_overrides": {
    "ai_assistant": {
      "task_timeout": 120000
    },
    "asset_manager": {
      "task_timeout": 10000
    }
  }
}
```

### Programmatic Configuration

```python
from core.config.thread_config import ThreadConfiguration, ModuleThreadConfig

config = ThreadConfiguration(
    task_timeout=30000,
    module_overrides={
        "ai_assistant": ModuleThreadConfig(task_timeout=120000),
        "asset_manager": ModuleThreadConfig(task_timeout=10000),
    }
)
```

## Grace Period

**Default:** 1000ms (1 second)

Time given to tasks to clean up after timeout before forced termination.

### Timeline

```
Task starts
    ↓
    ... (task_timeout) ...
    ↓
Timeout reached → cancel_token.is_cancelled() = True
    ↓
    ... (grace_period) ...
    ↓
Grace period ends → Task forcefully terminated
```

### When to Adjust

```python
# Fast cleanup (< 1 second)
{
  "grace_period": 500  # 500ms
}

# Normal cleanup (1-2 seconds)
{
  "grace_period": 1000  # 1 second (default)
}

# Slow cleanup (> 2 seconds)
{
  "grace_period": 3000  # 3 seconds
}
```

**Warning:** Long grace periods delay shutdown. Keep it as short as possible.

## Cleanup Timeout

**Default:** 2000ms (2 seconds)

Maximum time for a module's `cleanup()` method to complete.

### When to Adjust

```python
# Simple modules (no I/O)
{
  "cleanup_timeout": 1000  # 1 second
}

# Normal modules (some I/O)
{
  "cleanup_timeout": 2000  # 2 seconds (default)
}

# Complex modules (database, network)
{
  "cleanup_timeout": 5000  # 5 seconds
}
```

### Module-Specific Overrides

```json
{
  "cleanup_timeout": 2000,
  "module_overrides": {
    "ai_assistant": {
      "cleanup_timeout": 5000
    }
  }
}
```

## Global Shutdown Timeout

**Default:** 10000ms (10 seconds)

Maximum time for the entire application shutdown.

### When to Adjust

```python
# Few modules (< 5)
{
  "global_shutdown_timeout": 5000  # 5 seconds
}

# Normal application (5-10 modules)
{
  "global_shutdown_timeout": 10000  # 10 seconds (default)
}

# Large application (> 10 modules)
{
  "global_shutdown_timeout": 20000  # 20 seconds
}
```

**Note:** Modules are cleaned up in parallel, so this should be based on the slowest module, not the sum of all modules.

## Best Practices

### 1. Start Conservative, Then Optimize

```json
{
  "task_timeout": 60000,
  "cleanup_timeout": 5000,
  "global_shutdown_timeout": 15000
}
```

Monitor actual task durations, then reduce timeouts:

```json
{
  "task_timeout": 30000,
  "cleanup_timeout": 2000,
  "global_shutdown_timeout": 10000
}
```

### 2. Use Module Overrides

Don't increase global timeouts for one slow module:

```json
{
  "task_timeout": 30000,
  "module_overrides": {
    "slow_module": {
      "task_timeout": 120000
    }
  }
}
```

### 3. Monitor Timeout Events

```python
from core.utils.thread_manager import EnhancedThreadManager

manager = EnhancedThreadManager.get_instance()
metrics = manager.monitor.get_metrics()

print(f"Tasks timed out: {metrics.tasks_timeout}")
print(f"Average duration: {metrics.average_task_duration_ms:.2f}ms")
```

### 4. Test Timeout Behavior

```python
import pytest
import time

def test_task_timeout(qtbot):
    """Test that tasks timeout correctly."""
    from core.config.thread_config import ThreadConfiguration
    from core.utils.thread_manager import EnhancedThreadManager
    
    config = ThreadConfiguration(task_timeout=1000)  # 1 second
    manager = EnhancedThreadManager(config)
    
    def slow_task(cancel_token):
        time.sleep(5)  # Longer than timeout
        return "completed"
    
    results = []
    
    task_id = manager.run_in_thread(
        slow_task,
        module_name="test",
        task_name="slow_task",
        on_result=lambda r: results.append(r),
    )
    
    # Wait for timeout
    qtbot.wait(2000)
    
    # Task should have timed out
    metrics = manager.monitor.get_metrics()
    assert metrics.tasks_timeout > 0
```

## Common Scenarios

### Scenario 1: AI Assistant with Long Requests

```json
{
  "task_timeout": 30000,
  "module_overrides": {
    "ai_assistant": {
      "task_timeout": 300000,
      "grace_period": 2000,
      "cleanup_timeout": 5000
    }
  }
}
```

### Scenario 2: Asset Manager with Quick Operations

```json
{
  "task_timeout": 30000,
  "module_overrides": {
    "asset_manager": {
      "task_timeout": 10000,
      "grace_period": 500,
      "cleanup_timeout": 1000
    }
  }
}
```

### Scenario 3: Development Environment (Fast Feedback)

```json
{
  "task_timeout": 10000,
  "grace_period": 500,
  "cleanup_timeout": 1000,
  "global_shutdown_timeout": 5000
}
```

### Scenario 4: Production Environment (Stable)

```json
{
  "task_timeout": 60000,
  "grace_period": 2000,
  "cleanup_timeout": 5000,
  "global_shutdown_timeout": 20000
}
```

## Troubleshooting

### Tasks Timing Out Too Often

**Symptoms:** High `tasks_timeout` metric

**Solutions:**
1. Increase `task_timeout` for the module
2. Optimize task logic to complete faster
3. Check for blocking I/O or infinite loops

### Shutdown Takes Too Long

**Symptoms:** Application hangs on exit

**Solutions:**
1. Reduce `cleanup_timeout` for fast modules
2. Implement `request_stop()` to cancel tasks early
3. Optimize cleanup logic

### Tasks Not Timing Out

**Symptoms:** Stuck tasks never terminate

**Solutions:**
1. Verify `task_timeout` is set correctly
2. Check that timeout mechanism is enabled
3. Ensure tasks check `cancel_token.is_cancelled()`

## See Also

- [Cancellation-Aware Tasks Guide](CANCELLATION_AWARE_TASKS_GUIDE.md)
- [Cleanup Contract Guide](CLEANUP_CONTRACT_GUIDE.md)
- [Performance Tuning Guide](PERFORMANCE_TUNING_GUIDE.md)
- [Troubleshooting Guide](TROUBLESHOOTING_GUIDE.md)

