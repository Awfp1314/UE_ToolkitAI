# Cancellation-Aware Tasks Implementation Guide

## Overview

This guide explains how to implement tasks that can be gracefully cancelled using the ThreadManager's cancellation token system.

## What is a Cancellation Token?

A `CancellationToken` is an object that signals when a task should stop executing. It allows tasks to:
- Check if cancellation has been requested
- Exit gracefully before completion
- Clean up resources properly
- Avoid wasting CPU on cancelled work

## Basic Usage

### Simple Cancellation-Aware Task

```python
def my_task(cancel_token):
    """A simple task that checks for cancellation."""
    for i in range(100):
        # Check if cancellation was requested
        if cancel_token.is_cancelled():
            print("Task cancelled, exiting early")
            return None
        
        # Do some work
        process_item(i)
    
    return "completed"
```

### Submitting the Task

```python
from core.utils.thread_manager import EnhancedThreadManager

manager = EnhancedThreadManager.get_instance()

# Submit task
task_id = manager.run_in_thread(
    my_task,
    module_name="my_module",
    task_name="process_items",
)

# Cancel task if needed
manager.cancel_task(task_id)
```

## Automatic Token Injection

The ThreadManager **automatically injects** the `cancel_token` parameter if your function accepts it. You don't need to pass it manually.

### Functions That Accept cancel_token

```python
# ✅ Automatically receives cancel_token
def task_with_token(cancel_token):
    while not cancel_token.is_cancelled():
        do_work()

# ✅ Also works with other parameters
def task_with_params(data, cancel_token, timeout=30):
    for item in data:
        if cancel_token.is_cancelled():
            break
        process(item, timeout)
```

### Functions That Don't Accept cancel_token

```python
# ✅ Still works, but can't be cancelled gracefully
def task_without_token(data):
    for item in data:
        process(item)
```

**Note:** Tasks without `cancel_token` will still be forcefully terminated after the grace period, but they won't have a chance to clean up gracefully.

## Best Practices

### 1. Check Cancellation Frequently

```python
def good_task(cancel_token):
    """Check cancellation in loops."""
    for i in range(1000):
        if cancel_token.is_cancelled():
            return None
        
        process_item(i)  # Short operation
```

### 2. Check Before Long Operations

```python
def better_task(cancel_token):
    """Check before expensive operations."""
    items = load_items()
    
    for item in items:
        # Check BEFORE expensive operation
        if cancel_token.is_cancelled():
            return None
        
        expensive_operation(item)  # Long operation
```

### 3. Clean Up Resources on Cancellation

```python
def best_task(cancel_token):
    """Clean up resources when cancelled."""
    file = open("data.txt", "w")
    
    try:
        for i in range(1000):
            if cancel_token.is_cancelled():
                print("Cancelled, cleaning up...")
                file.write("CANCELLED\n")
                return None
            
            file.write(f"Item {i}\n")
        
        return "completed"
    finally:
        file.close()
```

### 4. Return Meaningful Results

```python
def informative_task(cancel_token):
    """Return information about cancellation."""
    processed = 0
    
    for i in range(100):
        if cancel_token.is_cancelled():
            return {"status": "cancelled", "processed": processed}
        
        process_item(i)
        processed += 1
    
    return {"status": "completed", "processed": processed}
```

## Advanced Patterns

### Nested Cancellation Checks

```python
def nested_task(cancel_token):
    """Check cancellation at multiple levels."""
    for batch in batches:
        if cancel_token.is_cancelled():
            return None
        
        for item in batch:
            if cancel_token.is_cancelled():
                return None
            
            process_item(item)
```

### Cancellation with Timeout

```python
import time

def task_with_timeout(cancel_token, timeout=10):
    """Combine cancellation with timeout."""
    start_time = time.time()
    
    while not cancel_token.is_cancelled():
        if time.time() - start_time > timeout:
            return {"status": "timeout"}
        
        do_work()
    
    return {"status": "cancelled"}
```

### Cancellation in Callbacks

```python
def task_with_callback(cancel_token, on_progress=None):
    """Support progress callbacks with cancellation."""
    total = 100
    
    for i in range(total):
        if cancel_token.is_cancelled():
            if on_progress:
                on_progress(i, total, cancelled=True)
            return None
        
        process_item(i)
        
        if on_progress:
            on_progress(i + 1, total, cancelled=False)
    
    return "completed"
```

## Common Mistakes

### ❌ Not Checking Cancellation

```python
def bad_task(cancel_token):
    """Never checks cancellation - will run to completion."""
    for i in range(1000000):
        expensive_operation(i)  # No cancellation check!
```

### ❌ Checking Too Infrequently

```python
def slow_task(cancel_token):
    """Checks only once - may run for hours before noticing."""
    if cancel_token.is_cancelled():
        return None
    
    very_long_operation()  # Hours of work
```

### ❌ Ignoring Cancellation

```python
def stubborn_task(cancel_token):
    """Checks but ignores cancellation."""
    for i in range(100):
        if cancel_token.is_cancelled():
            print("Cancelled, but continuing anyway!")
            # ❌ Should return here!
        
        process_item(i)
```

## Testing Cancellation

```python
import pytest
from core.utils.thread_manager import EnhancedThreadManager

def test_task_cancellation(qtbot):
    """Test that task responds to cancellation."""
    manager = EnhancedThreadManager.get_instance()
    
    results = []
    
    def on_result(result):
        results.append(result)
    
    # Submit long-running task
    task_id = manager.run_in_thread(
        my_task,
        module_name="test",
        task_name="cancellable_task",
        on_result=on_result,
    )
    
    # Cancel immediately
    manager.cancel_task(task_id)
    
    # Wait for result
    qtbot.waitUntil(lambda: len(results) > 0, timeout=5000)
    
    # Verify task was cancelled
    assert results[0] is None or results[0].get("status") == "cancelled"
```

## See Also

- [Cleanup Contract Guide](CLEANUP_CONTRACT_GUIDE.md)
- [Timeout Configuration Guide](TIMEOUT_CONFIGURATION_GUIDE.md)
- [Troubleshooting Guide](TROUBLESHOOTING_GUIDE.md)

