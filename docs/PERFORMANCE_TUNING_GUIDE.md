# Performance Tuning Guide

## Overview

This guide documents the performance characteristics of the ThreadManager system and provides tuning recommendations for optimal performance.

## Performance Benchmarks

### Current Performance (as of 2025-11-19)

| Metric | Target | Actual | Status |
|--------|--------|--------|--------|
| ThreadManager Initialization | < 50ms | ~0ms | ✅ Excellent |
| Task Submission Overhead | < 10ms/task | ~0.3ms/task | ✅ Excellent |
| Shutdown Sequence (10 modules) | < 5000ms | ~116ms | ✅ Excellent |
| Monitoring Export (1000 events) | < 100ms | ~8ms | ✅ Excellent |

**Test Environment:**
- Platform: Windows 10
- Python: 3.9.12
- Processor: Intel Core (12th Gen)
- Pool Size: 3-5 threads
- Queue Size: 5-20 tasks

## Configuration Parameters

### Thread Pool Size (`thread_pool_size`)

**Default:** 5

**Tuning Guidelines:**
- **CPU-bound tasks**: Set to `CPU_COUNT` or `CPU_COUNT - 1`
- **I/O-bound tasks**: Set to `CPU_COUNT * 2` or higher
- **Mixed workload**: Start with `CPU_COUNT` and adjust based on monitoring

**Impact:**
- Too low: Tasks queue up, increased latency
- Too high: Context switching overhead, memory usage

**Example:**
```python
import os
config = ThreadConfiguration(
    thread_pool_size=os.cpu_count()  # 8 cores = 8 threads
)
```

### Task Queue Size (`task_queue_size`)

**Default:** 20

**Tuning Guidelines:**
- **Bursty workload**: Increase to 50-100
- **Steady workload**: Keep at 20-30
- **Memory-constrained**: Reduce to 10-15

**Impact:**
- Too low: Tasks rejected with `QueueFullError`
- Too high: Memory usage, harder to detect backpressure

**Example:**
```python
config = ThreadConfiguration(
    task_queue_size=50  # Handle burst of 50 tasks
)
```

### Task Timeout (`task_timeout`)

**Default:** 30000ms (30 seconds)

**Tuning Guidelines:**
- **Quick tasks (< 5s)**: 5000-10000ms
- **Medium tasks (5-30s)**: 30000ms (default)
- **Long tasks (> 30s)**: 60000-120000ms

**Impact:**
- Too low: Tasks timeout prematurely
- Too high: Stuck tasks block resources longer

**Module-specific overrides:**
```python
config = ThreadConfiguration(
    task_timeout=30000,  # Default
    module_overrides={
        "ai_assistant": ModuleThreadConfig(task_timeout=60000),  # AI needs more time
        "asset_manager": ModuleThreadConfig(task_timeout=10000),  # Assets are quick
    }
)
```

### Grace Period (`grace_period`)

**Default:** 1000ms (1 second)

**Tuning Guidelines:**
- **Fast cleanup**: 500-1000ms
- **Slow cleanup**: 2000-3000ms

**Impact:**
- Too low: Tasks killed before cleanup completes
- Too high: Delayed shutdown

### Cleanup Timeout (`cleanup_timeout`)

**Default:** 2000ms (2 seconds)

**Tuning Guidelines:**
- **Simple modules**: 1000-2000ms
- **Complex modules**: 3000-5000ms

**Module-specific overrides:**
```python
config = ThreadConfiguration(
    cleanup_timeout=2000,  # Default
    module_overrides={
        "ai_assistant": ModuleThreadConfig(cleanup_timeout=5000),  # Complex cleanup
    }
)
```

### Global Shutdown Timeout (`global_shutdown_timeout`)

**Default:** 10000ms (10 seconds)

**Tuning Guidelines:**
- **Few modules (< 5)**: 5000-10000ms
- **Many modules (> 10)**: 15000-20000ms

**Note:** Modules are cleaned up in parallel, so this should be based on the slowest module, not the sum.

## Performance Optimization Tips

### 1. Minimize Task Submission Overhead

**Current:** ~0.3ms per task

**Best Practices:**
- Batch similar tasks together
- Avoid creating tasks in tight loops
- Use task queuing for burst workloads

**Example:**
```python
# ❌ Bad: Create task per item
for item in items:
    thread_manager.run_in_thread(process_item, item=item)

# ✅ Good: Batch process
thread_manager.run_in_thread(process_items, items=items)
```

### 2. Optimize Shutdown Performance

**Current:** ~116ms for 10 modules (parallel)

**Best Practices:**
- Implement `request_stop()` to signal early shutdown
- Keep cleanup logic simple and fast
- Avoid blocking I/O in cleanup

**Example:**
```python
class MyModule:
    def request_stop(self):
        """Signal workers to stop early."""
        self.should_stop = True
    
    def cleanup(self) -> CleanupResult:
        """Fast cleanup - no blocking I/O."""
        try:
            # Quick cleanup only
            self.cache.clear()
            return CleanupResult.success_result()
        except Exception as e:
            return CleanupResult.failure_result(str(e))
```

### 3. Monitor Performance

**Use ThreadMonitor for insights:**
```python
metrics = thread_manager.monitor.get_metrics()
print(f"Total tasks: {metrics.total_tasks_executed}")
print(f"Completed: {metrics.tasks_completed}")
print(f"Failed: {metrics.tasks_failed}")
print(f"Avg duration: {metrics.average_task_duration_ms:.2f}ms")
```

**Export for analysis:**
```python
thread_manager.monitor.export_ndjson("logs/thread_metrics.ndjson")
```

## Troubleshooting Performance Issues

### Issue: Tasks Timing Out

**Symptoms:** Tasks frequently timeout, `tasks_timeout` metric high

**Solutions:**
1. Increase `task_timeout` for the module
2. Optimize task logic to complete faster
3. Check for blocking I/O or infinite loops

### Issue: Queue Full Errors

**Symptoms:** `QueueFullError` exceptions

**Solutions:**
1. Increase `task_queue_size`
2. Increase `thread_pool_size` to process tasks faster
3. Implement backpressure handling in caller

### Issue: Slow Shutdown

**Symptoms:** Shutdown takes > 5 seconds

**Solutions:**
1. Implement `request_stop()` in modules
2. Reduce `cleanup_timeout` for fast modules
3. Optimize cleanup logic

### Issue: High Memory Usage

**Symptoms:** Memory grows during task execution

**Solutions:**
1. Reduce `task_queue_size`
2. Reduce `thread_pool_size`
3. Check for memory leaks in task functions

## Performance Testing

### Run Performance Validation

```bash
pytest tests/test_performance_validation.py -v
```

### Run Regression Tests

```bash
pytest tests/test_performance_regression.py -v -m performance
```

### View Performance Report

```bash
cat logs/performance/thread_manager_benchmarks.json
```

## Recommended Configurations

### Development Environment

```python
config = ThreadConfiguration(
    thread_pool_size=3,
    task_queue_size=10,
    task_timeout=10000,  # Shorter for quick feedback
)
```

### Production Environment

```python
config = ThreadConfiguration(
    thread_pool_size=os.cpu_count(),
    task_queue_size=50,
    task_timeout=30000,
    global_shutdown_timeout=15000,
)
```

### High-Throughput Environment

```python
config = ThreadConfiguration(
    thread_pool_size=os.cpu_count() * 2,
    task_queue_size=100,
    task_timeout=60000,
)
```

