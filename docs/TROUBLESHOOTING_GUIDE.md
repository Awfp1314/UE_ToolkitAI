# ThreadManager Troubleshooting Guide

## Overview

This guide helps you diagnose and fix common issues with the ThreadManager system.

## Quick Diagnostics

### Check ThreadManager Status

```python
from core.utils.thread_manager import EnhancedThreadManager

manager = EnhancedThreadManager.get_instance()
metrics = manager.monitor.get_metrics()

print(f"Total tasks: {metrics.total_tasks_executed}")
print(f"Completed: {metrics.tasks_completed}")
print(f"Failed: {metrics.tasks_failed}")
print(f"Timeout: {metrics.tasks_timeout}")
print(f"Cancelled: {metrics.tasks_cancelled}")
print(f"Active: {metrics.active_tasks}")
```

### Export Monitoring Data

```python
from pathlib import Path

# Export to NDJSON for analysis
manager.monitor.export_ndjson(Path("logs/thread_events.ndjson"))
```

### Check Configuration

```python
from core.config.thread_config import ThreadConfiguration

config = ThreadConfiguration()
print(f"Pool size: {config.thread_pool_size}")
print(f"Queue size: {config.task_queue_size}")
print(f"Task timeout: {config.task_timeout}ms")
print(f"Cleanup timeout: {config.cleanup_timeout}ms")
```

## Common Issues

### Issue 1: Tasks Stuck / Not Completing

**Symptoms:**
- Tasks never complete
- `active_tasks` metric stays high
- Application hangs

**Diagnosis:**

```python
# Check active tasks
metrics = manager.monitor.get_metrics()
print(f"Active tasks: {metrics.active_tasks}")

# Check if tasks are timing out
print(f"Timed out tasks: {metrics.tasks_timeout}")
```

**Possible Causes:**

1. **Task has infinite loop**
   ```python
   # ❌ Bad: No exit condition
   def stuck_task(cancel_token):
       while True:  # Never exits!
           do_work()
   ```
   
   **Fix:** Add cancellation check
   ```python
   # ✅ Good: Checks cancellation
   def good_task(cancel_token):
       while not cancel_token.is_cancelled():
           do_work()
   ```

2. **Task is blocking on I/O**
   ```python
   # ❌ Bad: Blocking forever
   def blocking_task(cancel_token):
       data = socket.recv()  # May block forever
   ```
   
   **Fix:** Use timeout or non-blocking I/O
   ```python
   # ✅ Good: Timeout on I/O
   def timeout_task(cancel_token):
       socket.settimeout(1.0)
       try:
           data = socket.recv()
       except socket.timeout:
           return None
   ```

3. **Task timeout too short**
   
   **Fix:** Increase timeout in config
   ```json
   {
     "module_overrides": {
       "my_module": {
         "task_timeout": 60000
       }
     }
   }
   ```

### Issue 2: Queue Full Errors

**Symptoms:**
- `QueueFullError` exceptions
- Tasks rejected
- Application becomes unresponsive

**Diagnosis:**

```python
# Check queue size
config = ThreadConfiguration()
print(f"Queue size: {config.task_queue_size}")

# Check if tasks are being rejected
# (Look for QueueFullError in logs)
```

**Possible Causes:**

1. **Too many tasks submitted at once**
   
   **Fix:** Increase queue size
   ```json
   {
     "task_queue_size": 50
   }
   ```

2. **Tasks taking too long to complete**
   
   **Fix:** Increase pool size
   ```json
   {
     "thread_pool_size": 10
   }
   ```

3. **Backpressure not handled**
   
   **Fix:** Implement backpressure handling
   ```python
   from core.utils.thread_manager import QueueFullError
   
   try:
       manager.run_in_thread(task, module_name="my_module")
   except QueueFullError:
       # Wait and retry, or drop task
       print("Queue full, dropping task")
   ```

### Issue 3: Slow Shutdown

**Symptoms:**
- Application takes > 10 seconds to exit
- Shutdown hangs
- "Tasks still active" warnings

**Diagnosis:**

```python
# Check cleanup timeout
config = ThreadConfiguration()
print(f"Cleanup timeout: {config.cleanup_timeout}ms")
print(f"Global shutdown timeout: {config.global_shutdown_timeout}ms")
```

**Possible Causes:**

1. **Module cleanup is slow**
   
   **Fix:** Optimize cleanup logic
   ```python
   # ❌ Bad: Slow cleanup
   def cleanup(self):
       for item in self.large_list:
           item.cleanup()  # Slow!
       return CleanupResult.success_result()
   
   # ✅ Good: Fast cleanup
   def cleanup(self):
       self.large_list.clear()  # Fast!
       return CleanupResult.success_result()
   ```

2. **Tasks not responding to cancellation**
   
   **Fix:** Implement `request_stop()`
   ```python
   def request_stop(self):
       """Cancel all active tasks."""
       for task_id in self.active_tasks:
           self.thread_manager.cancel_task(task_id)
   ```

3. **Cleanup timeout too long**
   
   **Fix:** Reduce timeout for fast modules
   ```json
   {
     "module_overrides": {
       "fast_module": {
         "cleanup_timeout": 1000
       }
     }
   }
   ```

### Issue 4: Tasks Failing Silently

**Symptoms:**
- Tasks complete but no result
- No error messages
- Unexpected behavior

**Diagnosis:**

```python
# Check failed tasks
metrics = manager.monitor.get_metrics()
print(f"Failed tasks: {metrics.tasks_failed}")

# Export events to see errors
manager.monitor.export_ndjson(Path("logs/errors.ndjson"))
```

**Possible Causes:**

1. **Exception not caught**
   
   **Fix:** Add try/except
   ```python
   def safe_task(cancel_token):
       try:
           result = do_work()
           return result
       except Exception as e:
           print(f"Task failed: {e}")
           return None
   ```

2. **No result callback**
   
   **Fix:** Add result callback
   ```python
   def on_result(result):
       print(f"Task completed: {result}")
   
   def on_error(error):
       print(f"Task failed: {error}")
   
   manager.run_in_thread(
       task,
       module_name="my_module",
       on_result=on_result,
       on_error=on_error,
   )
   ```

### Issue 5: Memory Leaks

**Symptoms:**
- Memory usage grows over time
- Application becomes slow
- Out of memory errors

**Diagnosis:**

```python
import psutil
import os

process = psutil.Process(os.getpid())
print(f"Memory usage: {process.memory_info().rss / 1024 / 1024:.2f} MB")
```

**Possible Causes:**

1. **Tasks not cleaning up resources**
   
   **Fix:** Use context managers
   ```python
   def leaky_task(cancel_token):
       file = open("data.txt")  # ❌ Never closed!
       data = file.read()
       return data
   
   def clean_task(cancel_token):
       with open("data.txt") as file:  # ✅ Auto-closed
           data = file.read()
       return data
   ```

2. **Results not garbage collected**
   
   **Fix:** Don't store all results
   ```python
   # ❌ Bad: Stores all results
   results = []
   for i in range(10000):
       manager.run_in_thread(
           task,
           on_result=lambda r: results.append(r)
       )
   
   # ✅ Good: Process results immediately
   for i in range(10000):
       manager.run_in_thread(
           task,
           on_result=process_and_discard
       )
   ```

### Issue 6: Cleanup Failures

**Symptoms:**
- Cleanup returns failure result
- Resources not released
- Warnings in logs

**Diagnosis:**

```python
# Check cleanup result
result = module.cleanup()
if not result.is_success:
    print(f"Cleanup failed: {result.errors}")
```

**Possible Causes:**

1. **Exception in cleanup**
   
   **Fix:** Catch exceptions
   ```python
   def cleanup(self):
       try:
           self.db.close()
           return CleanupResult.success_result()
       except Exception as e:
           return CleanupResult.failure_result(str(e))
   ```

2. **Cleanup timeout**
   
   **Fix:** Increase timeout or optimize cleanup
   ```json
   {
     "module_overrides": {
       "my_module": {
         "cleanup_timeout": 5000
       }
     }
   }
   ```

## Debugging Tools

### Enable Debug Logging

```python
import logging

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger("core.utils.thread_manager")
logger.setLevel(logging.DEBUG)
```

### Monitor Thread Events

```python
# Export events with privacy applied
manager.monitor.export_ndjson(
    Path("logs/events.ndjson"),
    apply_privacy=True
)

# Read events
import json
with open("logs/events.ndjson") as f:
    for line in f:
        event = json.loads(line)
        print(event)
```

### Run Migration Validator

```python
from core.utils.migration_validator import MigrationValidator

validator = MigrationValidator()
violations = validator.scan_directory("modules/my_module")

for v in violations:
    print(f"{v.file}:{v.line} - {v.pattern}")
```

## Performance Issues

### Tasks Too Slow

**Diagnosis:**
```python
metrics = manager.monitor.get_metrics()
print(f"Average duration: {metrics.average_task_duration_ms:.2f}ms")
```

**Solutions:**
1. Profile task code
2. Optimize algorithms
3. Use caching
4. Increase pool size for I/O-bound tasks

### High CPU Usage

**Diagnosis:**
```python
import psutil
print(f"CPU usage: {psutil.cpu_percent()}%")
```

**Solutions:**
1. Reduce pool size
2. Add delays in tight loops
3. Optimize task logic

## Getting Help

If you're still stuck:

1. **Check logs:** `logs/ue_toolkit.log`
2. **Export monitoring data:** `logs/thread_events.ndjson`
3. **Run tests:** `pytest tests/test_thread_*.py -v`
4. **Check configuration:** `config/thread_config.json`

## See Also

- [Cancellation-Aware Tasks Guide](CANCELLATION_AWARE_TASKS_GUIDE.md)
- [Cleanup Contract Guide](CLEANUP_CONTRACT_GUIDE.md)
- [Timeout Configuration Guide](TIMEOUT_CONFIGURATION_GUIDE.md)
- [Performance Tuning Guide](PERFORMANCE_TUNING_GUIDE.md)

