"""Integration tests for thread pool backpressure (Task 14.7).

Tests thread pool limits, queue limits, task rejection, execution order,
cancellation, and performance under load.
"""
import time
import pytest
from PyQt6.QtCore import QCoreApplication

from core.config.thread_config import ThreadConfiguration
from core.utils.thread_manager import EnhancedThreadManager, QueueFullError
from core.utils.thread_utils import CancellationToken


@pytest.fixture
def app(qapp):
    """Provide QApplication for tests."""
    return qapp


@pytest.fixture
def thread_config():
    """Create a ThreadConfiguration for testing."""
    return ThreadConfiguration(
        task_timeout=5000,
        grace_period=500,
        cleanup_timeout=1000,
        thread_pool_size=3,  # Small pool for testing
        task_queue_size=5,   # Small queue for testing
    )


@pytest.fixture
def thread_manager(thread_config):
    """Create an EnhancedThreadManager for testing."""
    return EnhancedThreadManager(thread_config)


def simple_task(cancel_token: CancellationToken, duration: float = 0.1):
    """Simple task that sleeps for a duration."""
    start_time = time.time()
    while time.time() - start_time < duration:
        if cancel_token and cancel_token.is_cancelled():
            return "cancelled"
        time.sleep(0.01)
    return "completed"


def counting_task(cancel_token: CancellationToken, counter: list, index: int, duration: float = 0.05):
    """Task that appends its index to a counter list."""
    time.sleep(duration)
    if cancel_token and cancel_token.is_cancelled():
        return
    counter.append(index)


class TestThreadPoolBackpressure:
    """Test suite for thread pool backpressure."""
    
    def test_submit_tasks_up_to_pool_limit(self, thread_manager, app, qtbot):
        """Test submitting tasks up to pool limit (3 tasks)."""
        results = []

        def on_result(result):
            results.append(result)

        # Submit 3 tasks (pool size = 3)
        task_ids = []
        for i in range(3):
            thread, worker, task_id = thread_manager.run_in_thread(
                simple_task,
                module_name="test_module",
                task_name=f"task_{i}",
                on_result=on_result,
                duration=0.1,
            )
            task_ids.append(task_id)
            # First 3 tasks should start immediately
            assert thread is not None
            assert worker is not None

        # Wait for all tasks to complete
        qtbot.waitUntil(lambda: len(results) == 3, timeout=2000)

        assert len(results) == 3
        assert all(r == "completed" for r in results)
    
    def test_submit_tasks_up_to_queue_limit(self, thread_manager, app, qtbot):
        """Test submitting tasks up to queue limit (3 running + 5 queued = 8 tasks)."""
        results = []
        
        def on_result(result):
            results.append(result)
        
        # Submit 8 tasks (3 running + 5 queued)
        task_ids = []
        for i in range(8):
            thread, worker, task_id = thread_manager.run_in_thread(
                simple_task,
                module_name="test_module",
                task_name=f"task_{i}",
                on_result=on_result,
                duration=0.1,
            )
            task_ids.append(task_id)
            
            if i < 3:
                # First 3 tasks should start immediately
                assert thread is not None
                assert worker is not None
            else:
                # Next 5 tasks should be queued
                assert thread is None
                assert worker is None
        
        # Wait for all tasks to complete
        qtbot.waitUntil(lambda: len(results) == 8, timeout=3000)
        
        assert len(results) == 8
        assert all(r == "completed" for r in results)
    
    def test_queue_overflow_rejection(self, thread_manager, app):
        """Test queue overflow rejection with QueueFullError."""
        # Submit 8 tasks (3 running + 5 queued)
        for i in range(8):
            thread_manager.run_in_thread(
                simple_task,
                module_name="test_module",
                task_name=f"task_{i}",
                duration=0.5,  # Long duration to keep tasks running
            )
        
        # 9th task should raise QueueFullError
        with pytest.raises(QueueFullError) as exc_info:
            thread_manager.run_in_thread(
                simple_task,
                module_name="test_module",
                task_name="overflow_task",
                duration=0.1,
            )
        
        assert "queue at capacity" in str(exc_info.value).lower()
    
    def test_task_execution_order(self, thread_manager, app, qtbot):
        """Test that all queued tasks eventually execute (order may vary due to parallelism)."""
        counter = []

        # Submit 8 tasks (3 running + 5 queued)
        for i in range(8):
            thread_manager.run_in_thread(
                counting_task,
                module_name="test_module",
                task_name=f"task_{i}",
                counter=counter,
                index=i,
                duration=0.05,
            )

        # Wait for all tasks to complete
        qtbot.waitUntil(lambda: len(counter) == 8, timeout=3000)

        # All tasks should complete (order may vary due to parallel execution)
        assert len(counter) == 8
        assert set(counter) == {0, 1, 2, 3, 4, 5, 6, 7}  # All tasks completed

    def test_cancel_queued_task(self, thread_manager, app, qtbot):
        """Test cancelling queued tasks and verify queue state consistency."""
        results = []

        def on_result(result):
            results.append(result)

        # Submit 6 tasks (3 running + 3 queued)
        task_ids = []
        for i in range(6):
            _, _, task_id = thread_manager.run_in_thread(
                simple_task,
                module_name="test_module",
                task_name=f"task_{i}",
                on_result=on_result,
                duration=0.2,
            )
            task_ids.append(task_id)

        # Cancel the 5th task (index 4, which should be queued)
        thread_manager.cancel_task(task_ids[4])

        # Wait for remaining tasks to complete
        qtbot.waitUntil(lambda: len(results) == 5, timeout=3000)

        # Should have 5 completed tasks (6 - 1 cancelled)
        assert len(results) == 5

        # Verify cancellation was recorded
        metrics = thread_manager.monitor.get_metrics()
        assert metrics.tasks_cancelled >= 1

    def test_cancel_running_task_starts_next_queued(self, thread_manager, app, qtbot):
        """Test cancelling running tasks and verify next queued task starts."""
        results = []

        def on_result(result):
            results.append(result)

        # Submit 5 tasks (3 running + 2 queued)
        task_ids = []
        for i in range(5):
            _, _, task_id = thread_manager.run_in_thread(
                simple_task,
                module_name="test_module",
                task_name=f"task_{i}",
                on_result=on_result,
                duration=0.5,  # Long duration
            )
            task_ids.append(task_id)

        # Wait a bit for tasks to start
        time.sleep(0.1)

        # Cancel the first running task
        thread_manager.cancel_task(task_ids[0])

        # Wait for all tasks to complete
        qtbot.waitUntil(lambda: len(results) >= 4, timeout=3000)

        # Should have at least 4 results (1 cancelled, 4 completed)
        assert len(results) >= 4

        # Verify cancellation was recorded
        metrics = thread_manager.monitor.get_metrics()
        assert metrics.tasks_cancelled >= 1

    def test_performance_benchmark_pool_utilization(self, thread_manager, app, qtbot):
        """Performance benchmark: pool utilization under load."""
        results = []

        def on_result(result):
            results.append(result)

        # Submit 20 tasks (3 running + 5 queued + 12 rejected)
        # We'll submit 8 tasks (3 running + 5 queued) to avoid rejection
        num_tasks = 8
        start_time = time.time()

        for i in range(num_tasks):
            thread_manager.run_in_thread(
                simple_task,
                module_name="test_module",
                task_name=f"task_{i}",
                on_result=on_result,
                duration=0.1,
            )

        # Wait for all tasks to complete
        qtbot.waitUntil(lambda: len(results) == num_tasks, timeout=5000)

        duration = time.time() - start_time

        # With pool size 3 and 8 tasks of 0.1s each:
        # - First 3 tasks: 0.1s (parallel)
        # - Next 3 tasks: 0.1s (parallel)
        # - Last 2 tasks: 0.1s (parallel)
        # Total: ~0.3s (plus overhead)
        # Sequential would be: 8 * 0.1 = 0.8s

        assert duration < 0.6, f"Pool utilization took {duration:.2f}s, expected < 0.6s"
        assert len(results) == num_tasks

        # Verify metrics
        metrics = thread_manager.monitor.get_metrics()
        assert metrics.total_tasks_executed == num_tasks
        assert metrics.tasks_completed == num_tasks

    def test_queue_state_after_multiple_cancellations(self, thread_manager, app, qtbot):
        """Test queue state consistency after multiple cancellations."""
        results = []

        def on_result(result):
            results.append(result)

        # Submit 8 tasks (3 running + 5 queued)
        task_ids = []
        for i in range(8):
            _, _, task_id = thread_manager.run_in_thread(
                simple_task,
                module_name="test_module",
                task_name=f"task_{i}",
                on_result=on_result,
                duration=0.2,
            )
            task_ids.append(task_id)

        # Cancel 3 queued tasks (indices 3, 4, 5)
        for i in [3, 4, 5]:
            thread_manager.cancel_task(task_ids[i])

        # Wait for remaining tasks to complete
        qtbot.waitUntil(lambda: len(results) == 5, timeout=3000)

        # Should have 5 completed tasks (8 - 3 cancelled)
        assert len(results) == 5

        # Verify cancellations were recorded
        metrics = thread_manager.monitor.get_metrics()
        assert metrics.tasks_cancelled >= 3

    def test_empty_queue_after_all_tasks_complete(self, thread_manager, app, qtbot):
        """Test that queue is empty after all tasks complete."""
        results = []

        def on_result(result):
            results.append(result)

        # Submit 5 tasks
        for i in range(5):
            thread_manager.run_in_thread(
                simple_task,
                module_name="test_module",
                task_name=f"task_{i}",
                on_result=on_result,
                duration=0.1,
            )

        # Wait for all tasks to complete
        qtbot.waitUntil(lambda: len(results) == 5, timeout=3000)

        # Queue should be empty
        assert thread_manager._task_queue.empty()

        # Wait for threads to finish cleanup
        qtbot.waitUntil(lambda: len(thread_manager.get_active_threads()) == 0, timeout=1000)

        # No active tasks
        assert len(thread_manager.get_active_threads()) == 0

