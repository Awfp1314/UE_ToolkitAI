# Thread and Resource Management Unification - Design Document

## Overview

This design unifies thread management across the application by establishing ThreadManager as the single source of truth for all thread operations, implementing universal cancellation support, standardizing cleanup contracts, and providing comprehensive monitoring.

**Key Design Decisions**:

- **Threading Model**: QThread + Worker pattern for PyQt6 signal compatibility
- **Singleton**: Thread-safe get_thread_manager() with double-checked locking
- **Timeout**: QTimer-based with cooperative cancellation and grace period
- **Queue**: Non-blocking enqueue with backpressure rejection
- **Shutdown**: Parallel cleanup via ThreadPoolExecutor with per-module timeouts
- **Feature Flags**: Per-module enforcement toggle for gradual migration

## Architecture

```
Application
├── AppManager
│   ├── ModuleManager
│   │   ├── Module 1 (uses ThreadManager)
│   │   ├── Module 2 (uses ThreadManager)
│   │   └── Module N (uses ThreadManager)
│   ├── ThreadManager (Singleton)
│   │   ├── Task Queue (bounded)
│   │   ├── Thread Pool (semaphore-limited)
│   │   ├── ThreadMonitor
│   │   └── ThreadConfiguration
│   ├── ShutdownOrchestrator
│   └── FeatureFlagManager
```

## Core Components

### 1. ThreadConfiguration

**Location**: `core/config/thread_config.py`

Manages global and per-module thread parameters.

```python
@dataclass
class ModuleThreadConfig:
    task_timeout: Optional[int] = None
    cleanup_timeout: Optional[int] = None

    def merge_with_defaults(self, defaults: 'ThreadConfiguration') -> 'ModuleThreadConfig':
        return ModuleThreadConfig(
            task_timeout=self.task_timeout if self.task_timeout is not None else defaults.task_timeout,
            cleanup_timeout=self.cleanup_timeout if self.cleanup_timeout is not None else defaults.cleanup_timeout
        )
```

```python
@dataclass
class ThreadConfiguration:
    task_timeout: int = 30000
    grace_period: int = 2000
    cleanup_timeout: int = 2000
    global_shutdown_timeout: int = 10000
    thread_pool_size: int = 10
    task_queue_size: int = 50
    cancellation_check_interval: int = 500
    privacy_rules: List[PrivacyRule] = field(default_factory=list)
    module_overrides: Dict[str, ModuleThreadConfig] = field(default_factory=dict)

    @classmethod
    def load_from_file(cls, config_path: Path) -> 'ThreadConfiguration':
        with open(config_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        module_overrides = {k: ModuleThreadConfig(**v) for k, v in data.get('module_overrides', {}).items()}
        privacy_rules = [PrivacyRule(**r) for r in data.get('privacy_rules', [])]
        return cls(
            task_timeout=data.get('task_timeout', 30000),
            grace_period=data.get('grace_period', 2000),
            cleanup_timeout=data.get('cleanup_timeout', 2000),
            global_shutdown_timeout=data.get('global_shutdown_timeout', 10000),
            thread_pool_size=data.get('thread_pool_size', 10),
            task_queue_size=data.get('task_queue_size', 50),
            cancellation_check_interval=data.get('cancellation_check_interval', 500),
            privacy_rules=privacy_rules,
            module_overrides=module_overrides
        )

    def get_module_config(self, module_name: str) -> ModuleThreadConfig:
        if module_name in self.module_overrides:
            return self.module_overrides[module_name].merge_with_defaults(self)
        return ModuleThreadConfig(task_timeout=self.task_timeout, cleanup_timeout=self.cleanup_timeout)

@dataclass
class PrivacyRule:
    field: str
    action: str  # 'redact' or 'mask'
    pattern: Optional[str] = None

    def apply(self, value: str) -> str:
        if self.action == 'redact':
            return '[REDACTED]'
        elif self.action == 'mask' and self.pattern:
            return re.sub(self.pattern, '[MASKED]', value)
        return value
```

### 2. EnhancedThreadManager (Integrated)

**Location**: `core/utils/thread_manager.py`

**Key Methods** (full implementation details in code):

```python
class EnhancedThreadManager:
    def __init__(self, config: ThreadConfiguration):
        self.config = config
        self.monitor = ThreadMonitor(config)
        self._active_tasks: Dict[str, TaskInfo] = {}
        self._task_queue: Queue = Queue(maxsize=config.task_queue_size)
        self._semaphore = threading.Semaphore(config.thread_pool_size)
        self._lock = threading.Lock()

    def run_in_thread(self, func, module_name, task_name=None, timeout=None,
                      on_result=None, on_error=None, on_timeout=None, *args, **kwargs) -> Tuple[QThread, Worker]:
        """
        Submit task with queue-based backpressure.
        Returns (QThread, Worker) if started immediately, (None, None) if queued.
        Raises QueueFullError if queue at capacity.
        """
        # 1. Create task metadata
        # 2. Try queue.put_nowait() → raises QueueFullError if full
        # 3. Try semaphore.acquire(blocking=False)
        # 4. If acquired: dequeue and _start_task() immediately
        # 5. If not: task queued, returns (None, None)

    def _start_task(self, task_metadata: dict) -> Tuple[QThread, Worker]:
        """Create QThread+Worker, wire signals, start thread, record in monitor"""
        # Inject cancel_token, create thread, setup timeout QTimer, record start

    def _inject_cancellation_token(self, func, args, kwargs) -> Tuple[tuple, dict]:
        """Unwrap decorators, inspect signature, inject if cancel_token parameter exists"""

    def _setup_timeout(self, task_id, worker, timeout_ms, on_timeout) -> QTimer:
        """Create QTimer that cancels token, waits grace period, logs if stuck"""

    def cancel_task(self, task_id: str):
        """Cancel task, set state to CANCELLED, record in monitor"""

    def _cleanup_task(self, task_id: str):
        """Record completion/cancellation/timeout, stop timer, remove from active_tasks"""

    def _on_thread_finished(self, task_id: str):
        """Cleanup task, release semaphore, process next queued task"""

    def cleanup(self, timeout_ms: int = None) -> bool:
        """Cancel all tasks, wait for completion, log stuck tasks"""

# Singleton accessor with double-checked locking
_thread_manager_instance: Optional[EnhancedThreadManager] = None
_thread_manager_lock = threading.Lock()

def get_thread_manager() -> EnhancedThreadManager:
    global _thread_manager_instance
    if _thread_manager_instance is None:
        with _thread_manager_lock:
            if _thread_manager_instance is None:
                config = ThreadConfiguration.load_from_file(Path('config/thread_config.json'))
                _thread_manager_instance = EnhancedThreadManager(config)
    return _thread_manager_instance
```

### 3. Data Objects

```python
@dataclass
class CleanupResult:
    success: bool
    error_message: Optional[str] = None
    errors: List[str] = field(default_factory=list)
    duration_ms: int = 0

@dataclass
class ModuleCleanupFailure:
    module_name: str
    failure_type: str  # 'exception', 'false_return', 'timeout'
    exception_type: Optional[str] = None
    error_message: Optional[str] = None
    traceback: Optional[str] = None

@dataclass
class ShutdownResult:
    total_modules: int
    success_count: int
    failure_count: int
    failures: List[ModuleCleanupFailure]
    duration_ms: int

class ThreadState(Enum):
    QUEUED = "queued"
    STARTING = "starting"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    TIMEOUT = "timeout"

@dataclass
class TaskInfo:
    task_id: str
    module_name: str
    task_name: str
    thread: QThread
    worker: Worker
    cancel_token: CancellationToken
    state: ThreadState
    start_time: float
    timeout_ms: Optional[int]
    timeout_timer: Optional[QTimer] = None
```

### 4. IModule Interface (Updated)

```python
class IModule(ABC):
    def request_stop(self) -> None:
        """Optional: Request module to stop operations before cleanup"""
        pass

    @abstractmethod
    def cleanup(self) -> CleanupResult:
        """Required: Clean up resources, must be thread-safe"""
        pass
```

### 5. ShutdownOrchestrator

```python
class ShutdownOrchestrator:
    def shutdown_modules(self, modules: Dict[str, IModule]) -> ShutdownResult:
        """Parallel cleanup using ThreadPoolExecutor, aggregate failures"""
        with ThreadPoolExecutor(max_workers=len(modules)) as executor:
            futures = {name: executor.submit(self._cleanup_module, name, mod) for name, mod in modules.items()}
            done, not_done = wait(futures.values(), timeout=self.config.global_shutdown_timeout / 1000.0)
            # Collect results, record timeouts, aggregate failures

    def _cleanup_module(self, module_name: str, module: IModule) -> CleanupResult:
        """Call request_stop(), then cleanup() with per-module timeout enforcement"""
        if hasattr(module, 'request_stop'):
            module.request_stop()
        # Execute cleanup in thread with timeout
```

### 6. ThreadMonitor

```python
class ThreadMonitor:
    def record_task_start(self, task_id, module_name, task_name, thread_id, thread_name):
        """Record start event with actual thread.objectName()"""

    def record_task_complete(self, task_id, duration_ms):
        """Record completion"""

    def record_task_cancelled(self, task_id):
        """Record cancellation"""

    def record_task_timeout(self, task_id):
        """Record timeout"""

    def export_ndjson(self, output_path, apply_privacy=True) -> int:
        """Export with privacy rules applied to all configured fields"""

@dataclass
class ThreadMetrics:
    total_tasks_executed: int = 0
    tasks_completed: int = 0
    tasks_failed: int = 0
    tasks_cancelled: int = 0
    tasks_timeout: int = 0
```

### 7. FeatureFlagManager

```python
class FeatureFlagManager:
    def is_thread_manager_enforced(self, module_name: str) -> bool:
        """Check if ThreadManager enforced for module"""

    def set_enforcement(self, module_name: str, enforced: bool):
        """Enable/disable enforcement, save to config"""
```

## Key Flows

### Task Submission with Backpressure

```
1. run_in_thread() called
2. Create task metadata
3. queue.put_nowait(metadata) → QueueFullError if full
4. semaphore.acquire(blocking=False)
5. If acquired:
   - Dequeue task
   - _start_task(): create QThread+Worker, wire signals, start
   - Return (QThread, Worker)
6. If not acquired:
   - Task queued
   - Return (None, None)
7. On thread finish:
   - _cleanup_task()
   - semaphore.release()
   - Process next queued task
```

### Timeout and Cancellation

```
1. QTimer started with timeout_ms
2. On timeout:
   - cancel_token.cancel()
   - Start grace period timer
3. If task completes within grace:
   - State = COMPLETED
   - Call on_timeout callback
4. If task stuck after grace:
   - State = TIMEOUT
   - Log stuck task
   - Call on_timeout callback
```

### Parallel Shutdown

```
1. ShutdownOrchestrator.shutdown_modules()
2. For each module:
   - Submit to ThreadPoolExecutor
   - Call request_stop() if exists
   - Call cleanup() with per-module timeout
3. Wait global_shutdown_timeout
4. Collect results from completed futures
5. Record timeouts for incomplete futures
6. Aggregate failures
7. Return ShutdownResult
```

## State Transitions

```
QUEUED → STARTING → RUNNING → {COMPLETED | FAILED | CANCELLED | TIMEOUT}
```

## Implementation Notes

1. **Queue Processing**: Non-blocking enqueue/dequeue prevents UI blocking
2. **Cancellation**: Cooperative via CancellationToken, tasks must check periodically
3. **Timeout**: QTimer + grace period, no hard termination
4. **Privacy**: Rules applied to all configured fields during export
5. **Thread Names**: Use actual thread.objectName() for observability
6. **Singleton**: Double-checked locking for thread safety
7. **Module Cleanup**: request_stop() called before cleanup() for graceful shutdown

This integrated design resolves all interface mismatches and provides a coherent implementation blueprint.

## Implementation Clarifications

### 1. Queued Task Identity

```python
def run_in_thread(...) -> Tuple[Optional[QThread], Optional[Worker], str]:
    """
    Returns: (QThread, Worker, task_id) if started immediately
             (None, None, task_id) if queued

    Callers can use task_id to:
    - Cancel queued/running tasks via cancel_task(task_id)
    - Track task status
    - Correlate with monitoring events
    """
```

### 2. Task Start and Finish Wiring

```python
def _start_task(self, task_metadata: dict) -> Tuple[QThread, Worker]:
    """
    Internal steps:
    1. Extract task_id from metadata
    2. Inject cancel_token into func
    3. Create QThread, Worker(func, cancel_token, *args, **kwargs)
    4. worker.moveToThread(thread)
    5. Wire signals:
       - thread.started → worker.run
       - worker.finished → thread.quit
       - worker.result → on_result (if provided)
       - worker.error → on_error + _handle_task_error(task_id)
       - thread.finished → lambda: self._on_thread_finished(task_id)
    6. Create TaskInfo, store in _active_tasks[task_id]
    7. Start QTimer if timeout > 0
    8. thread.start()
    9. Return (thread, worker)
    """

def _on_thread_finished(self, task_id: str):
    """
    Called when thread finishes:
    1. _cleanup_task(task_id) - records completion/cancellation/timeout
    2. semaphore.release()
    3. Try to process next queued task:
       - Check if queue not empty
       - Try semaphore.acquire(blocking=False)
       - If acquired: dequeue and _start_task()
       - If not acquired or queue empty: do nothing

    Race safety: Only one task processed per release, empty queue handled gracefully
    """
```

### 3. Timeout and Cancellation Outcomes

```python
def _setup_timeout(self, task_id, worker, timeout_ms, on_timeout) -> QTimer:
    """
    Timeout behavior:
    1. QTimer expires after timeout_ms
    2. Cancel token: worker.cancel_token.cancel()
    3. Start grace period timer (config.grace_period)
    4. During grace period:
       - If task completes normally:
         * State → COMPLETED
         * on_result callback invoked
         * on_timeout NOT invoked (task succeeded)
       - If task checks cancel_token and exits:
         * State → CANCELLED
         * on_timeout invoked (task was interrupted)
    5. After grace period:
       - If task still running:
         * State → TIMEOUT
         * Log stuck task
         * on_timeout invoked

    Callback rules:
    - on_result: Task completed successfully (even if during grace)
    - on_timeout: Task cancelled or timed out
    - on_error: Task raised exception
    """
```

### 4. Failure Tracking

```python
def _handle_task_error(self, task_id: str, error_message: str):
    """
    Called when worker.error signal emitted:
    1. Set task state to FAILED
    2. Call monitor.record_task_failed(task_id, error_message)
    3. Update metrics
    """

# In _start_task():
worker.error.connect(lambda err: self._handle_task_error(task_id, err))

# ThreadMonitor:
def record_task_failed(self, task_id: str, error_message: str):
    with self._lock:
        for event in reversed(self.events):
            if event.task_id == task_id:
                event.state = 'failed'
                event.end_time = time.time()
                event.error_message = error_message
                self.metrics.tasks_failed += 1
                break
```

### 5. Shutdown Cleanup Enforcement

```python
def _cleanup_module(self, module_name: str, module: IModule) -> CleanupResult:
    """
    Per-module cleanup with timeout enforcement:

    1. Get module config: module_config = self.config.get_module_config(module_name)
    2. Call request_stop() if exists:
       try:
           if hasattr(module, 'request_stop'):
               module.request_stop()
       except Exception as e:
           logger.warning(f"request_stop failed for {module_name}: {e}")

    3. Execute cleanup in thread with timeout:
       result_container = {'result': None, 'exception': None}

       def cleanup_wrapper():
           try:
               result_container['result'] = module.cleanup()
           except Exception as e:
               result_container['exception'] = e

       cleanup_thread = threading.Thread(target=cleanup_wrapper, name=f"cleanup_{module_name}")
       cleanup_thread.start()
       cleanup_thread.join(timeout=module_config.cleanup_timeout / 1000.0)

    4. Check outcome:
       if cleanup_thread.is_alive():
           # Timeout
           logger.error(f"Module {module_name} cleanup exceeded {module_config.cleanup_timeout}ms")
           return CleanupResult.failure_result(f"Cleanup timeout after {module_config.cleanup_timeout}ms")

       if result_container['exception']:
           # Exception
           raise result_container['exception']

       # Success
       return result_container['result'] or CleanupResult.success_result()
    """
```

### 6. Queue Processing Race Safety

```
_on_thread_finished() guarantees:
- Exactly one task processed per semaphore release
- Empty queue handled without error
- No state drift if multiple threads finish simultaneously

Implementation:
1. Lock-free semaphore operations
2. Queue.get_nowait() with try/except Empty
3. If queue empty after acquire, release semaphore immediately
4. TaskInfo stored before thread.start(), removed in _cleanup_task()
```

## Summary

All interfaces are now fully specified with:

- Return types including task_id for queued tasks
- Complete signal wiring and error handling
- Clarified timeout/cancellation outcomes
- Concrete per-module cleanup timeout enforcement
- Race-safe queue processing

The design is ready for implementation.
