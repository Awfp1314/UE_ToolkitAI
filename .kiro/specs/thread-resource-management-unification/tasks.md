# Implementation Plan

## Overview

This implementation plan breaks down the thread and resource management unification into discrete, manageable coding tasks. Each task builds incrementally on previous work, with testing integrated throughout.

## Task List

- [x] 1. Implement core configuration and data objects

  - Create ThreadConfiguration, ModuleThreadConfig, and PrivacyRule classes with JSON loading
  - Create CleanupResult, ModuleCleanupFailure, ShutdownResult data classes
  - Create ThreadState enum and TaskInfo, ThreadInfo data classes
  - Write unit tests for configuration loading and data object creation
  - _Requirements: 8.1, 8.2, 8.3, 3.1_

- [x] 2. Implement ThreadMonitor with privacy-aware export

  - Create ThreadLifecycleEvent and ThreadMetrics classes
  - Implement ThreadMonitor with record methods for all states (start, complete, failed, cancelled, timeout)
  - Implement NDJSON export with privacy rule application
  - Write unit tests for event recording and privacy redaction
  - _Requirements: 9.1, 9.2, 9.3, 9.4, 9.5_

- [x] 3. Enhance existing Worker and CancellationToken

  - Review existing Worker class in core/utils/thread_utils.py
  - Add error signal handling if not present
  - Ensure CancellationToken is properly integrated
  - Write unit tests for Worker error handling and cancellation
  - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5_

- [x] 4. Implement EnhancedThreadManager core functionality
- [x] 4.1 Implement singleton accessor with double-checked locking

  - Create get_thread_manager() function with thread-safe initialization
  - Load ThreadConfiguration from file with fallback to defaults
  - Write unit tests for singleton behavior and thread safety
  - _Requirements: 14.1, 14.2_

- [x] 4.2 Implement CancellationToken injection with signature inspection

  - Create \_inject_cancellation_token() method with functools unwrapping
  - Use inspect.signature to detect cancel_token parameter
  - Log one-time warning for functions without cancel_token
  - Write unit tests for various function signatures (plain, partial, wrapped, lambda)
  - _Requirements: 2.1, 2.2, 2.3_

- [x] 4.3 Implement queue-based task submission with backpressure

  - Create \_task_queue with configurable size
  - Implement run_in_thread() with non-blocking enqueue
  - Raise QueueFullError when queue is full
  - Return (QThread, Worker, task_id) or (None, None, task_id)
  - Write unit tests for queue overflow and task queuing
  - _Requirements: 11.1, 11.2, 11.3, 11.4_

- [x] 4.4 Implement \_start_task() with QThread + Worker creation

  - Create QThread and Worker from task metadata
  - Wire signals: started, finished, result, error
  - Set thread name using \_create_thread_name()
  - Create TaskInfo and store in \_active_tasks
  - Record task start in ThreadMonitor
  - Write unit tests for thread creation and signal wiring
  - _Requirements: 1.1, 1.4, 14.4_

- [x] 4.5 Implement timeout mechanism with QTimer and grace period

  - Create \_setup_timeout() method with QTimer
  - On timeout: cancel token, start grace period timer
  - Handle completion during grace vs stuck after grace
  - Write unit tests for timeout scenarios (complete before, during grace, stuck)
  - _Requirements: 4.1, 4.2, 4.3, 4.4_

- [x] 4.6 Implement task completion and cleanup

  - Create \_cleanup_task() to record final state and remove from active_tasks
  - Create \_on_thread_finished() to cleanup, release semaphore, process queue
  - Create \_handle_task_error() for error signal handling
  - Implement cancel_task() for user-initiated cancellation
  - Write unit tests for all completion paths (success, error, cancel, timeout)
  - Write unit tests for task_id propagation and cancellation via task_id
  - Write unit tests for cancelling queued tasks (verify queue state and cleanup)
  - Add performance assertions for task submission overhead (< 10ms)
  - _Requirements: 2.3, 2.4, 2.5, 5.2, 5.3, 5.4_

- [x] 4.7 Implement thread pool management and monitoring

  - Implement get_active_threads() for snapshot
  - Implement get_metrics() for aggregated metrics
  - Implement cleanup() for manager shutdown
  - Write unit tests for pool utilization and cleanup
  - _Requirements: 5.1, 5.2, 5.5, 11.5_

- [x] 5. Update IModule interface with CleanupResult contract

  - Add request_stop() method to IModule (optional, default no-op)
  - Update cleanup() signature to return CleanupResult
  - Create backward compatibility wrapper for legacy cleanup methods
  - Write unit tests for interface compliance
  - _Requirements: 3.1, 3.2, 3.4, 3.5_

- [x] 6. Implement ShutdownOrchestrator for parallel module cleanup

  - Create ShutdownOrchestrator class with ThreadPoolExecutor
  - Implement shutdown_modules() with parallel cleanup submission
  - Implement \_cleanup_module() with request_stop() and timeout enforcement
  - Aggregate failures and create ShutdownResult
  - Log critical error if > 50% modules fail
  - Write integration tests for shutdown sequence with multiple modules
  - Add integration test to verify request_stop() is called before cleanup()
  - Add integration test to verify per-module cleanup timeout overrides
  - Add performance assertions for shutdown time (within global_shutdown_timeout)
  - _Requirements: 7.1, 7.2, 7.3, 7.4, 7.5, 10.1, 10.2, 10.3, 10.4_
  - **Status**: ✅ Completed - 11 integration tests passing, 95% code coverage

- [x] 7. Implement FeatureFlagManager for migration control

  - Create ModuleFeatureFlags and FeatureFlagManager classes
  - Implement JSON loading and saving
  - Implement is_thread_manager_enforced() and set_enforcement()
  - Create get_feature_flags() singleton accessor
  - Write unit tests for flag management
  - _Requirements: 13.1, 13.2, 13.3, 13.4, 13.5_

- [x] 8. Implement MigrationValidator for static analysis

  - Create QThreadViolation data class
  - Implement AST-based scanning for QThread usage (instantiation, subclass, import)
  - Implement scan_module() and scan_all_modules()
  - Implement generate_report() for JSON output
  - Write unit tests with sample code containing violations
  - _Requirements: 6.1, 6.5_
  - **Status**: ✅ Completed - 16 unit tests passing, 90% code coverage
  - **Scan Results**: 21 violations found (12 in ai_assistant, 2 in asset_manager, 7 in core)

- [x] 9. Integrate ShutdownOrchestrator into AppManager

  - Update AppManager.quit() to use ShutdownOrchestrator
  - Log ShutdownResult with success/failure details
  - Handle partial and complete failures appropriately
  - Write integration tests for application shutdown
  - _Requirements: 7.1, 7.2, 7.3, 7.4, 7.5_

- [x] 10. Create developer documentation ✅

  - Write guide for implementing cancellation-aware tasks
  - Write guide for implementing cleanup contracts
  - Write guide for configuring timeouts
  - Write troubleshooting guide for stuck tasks and cleanup failures
  - Include code examples and best practices
  - _Requirements: 15.1, 15.2, 15.3, 15.4, 15.5_
  - **Status**: ✅ Completed - All developer guides created
    - `docs/CANCELLATION_AWARE_TASKS_GUIDE.md` - How to implement cancellation-aware tasks
    - `docs/CLEANUP_CONTRACT_GUIDE.md` - How to implement cleanup contracts
    - `docs/TIMEOUT_CONFIGURATION_GUIDE.md` - How to configure timeouts
    - `docs/TROUBLESHOOTING_GUIDE.md` - How to diagnose and fix common issues
    - All guides include code examples, best practices, and common mistakes

- [x] 11. Migrate AI Assistant module to ThreadManager ✅
- [ ] 11.1 Enable feature flag for ai_assistant module (跳过)

  - Feature flag 相关任务跳过，直接迁移
  - _Requirements: 13.1, 13.2_

- [x] 11.2 Migrate APIClient from QThread to ThreadManager ✅

  - Replace QThread inheritance with QObject
  - Change run() to \_execute_request(cancel_token)
  - Add start() method using ThreadManager.run_in_thread()
  - Update stop() to use cancel_task()
  - Preserve all signals: chunk_received, request_finished, token_usage, error_occurred
  - **Commit**: `02a38d7`
  - _Requirements: 1.1, 1.3, 2.1, 3.1, 6.2, 6.3_

- [x] 11.3 Migrate StreamingAPIClient from QThread to ThreadManager ✅

  - Replace QThread inheritance with QObject
  - Change run() to \_execute_request(cancel_token)
  - Add start() method using ThreadManager.run_in_thread()
  - Preserve intelligent buffering with ChunkBuffer
  - Preserve all signals: chunk_received, tool_call_detected, request_finished, token_usage, error_occurred
  - **Commit**: `2ee8a14`
  - _Requirements: 1.1, 1.3, 2.1, 3.1, 6.2, 6.3_

- [x] 11.4 Migrate AsyncMemoryCompressor from QThread to ThreadManager ✅

  - Replace QThread inheritance with QObject
  - Change run() to \_execute_compression(cancel_token)
  - Add start() method using ThreadManager.run_in_thread()
  - Update timeout handler to use cancel_task() instead of terminate()
  - Preserve timeout mechanism with QTimer
  - Preserve all signals: compression_complete, compression_timeout
  - **Commit**: `809eb4d`
  - _Requirements: 1.1, 1.3, 2.1, 3.1, 6.2, 6.3_

- [x] 11.5 Migrate FunctionCallingCoordinator from QThread to ThreadManager ✅

  - Replace QThread and ThreadCleanupMixin inheritance with QObject
  - Change run() to \_execute_coordination(cancel_token)
  - Add start() method using ThreadManager.run_in_thread()
  - Update stop() to use cancel_task()
  - Replace \_should_stop flag with cancel_token.is_cancelled()
  - Preserve all signals and multi-round tool calling functionality
  - **Commit**: `8baaa78`
  - _Requirements: 1.1, 1.3, 2.1, 3.1, 6.2, 6.3_

- [x] 11.6 Migrate remaining AI Assistant workers ✅

  - [x] Migrate NonStreamingWorker (Commit: `6bcf384`)
  - [x] Migrate AsyncTemplateGeneratorThread (Commit: `123ca8d`)
  - All workers successfully migrated to ThreadManager
  - _Requirements: 1.1, 1.3, 2.1, 3.1, 6.2, 6.3_

- [ ] 11.7 Verify feature flag behavior for ai_assistant module (跳过)

  - Feature flag 相关任务跳过
  - _Requirements: 13.1, 13.2, 13.5_

- [x] 11.8 Run MigrationValidator on ai_assistant module ✅

  - ✅ Verified no direct QThread usage remains
  - ✅ AI Assistant module violations: 12 → 0
  - ✅ Total project violations: 21 → 7 (only core module legitimate usage)
  - _Requirements: 6.5_

- [x] 12. Migrate Asset Manager module to ThreadManager
- [x] 12.1 Enable feature flag for asset_manager module

  - Set thread_manager_enforced: true in config/feature_flags.json
  - _Requirements: 13.1, 13.2_
  - **Status**: ⏭️ Skipped - Feature flag not required for this migration

- [x] 12.2 Migrate AssetLoadThread from QThread to ThreadManager

  - Replace QThread inheritance with task function
  - Add cancel_token parameter
  - Update LazyAssetLoader to use ThreadManager
  - Update cleanup() to return CleanupResult
  - Run existing tests
  - _Requirements: 1.1, 1.3, 2.1, 3.1, 6.2, 6.3_
  - **Status**: ✅ Completed - 14 tests passing, 67% coverage

- [x] 12.3 Verify feature flag behavior for asset_manager module

  - Identify key functionality regression test cases (lazy loading, asset retrieval, error handling)
  - Test module behavior with thread_manager_enforced: true
  - Test module behavior with thread_manager_enforced: false (rollback scenario)
  - Compare results and verify functionality is identical in both modes
  - Document any behavioral differences or edge cases
  - _Requirements: 13.1, 13.2, 13.5_
  - **Status**: ⏭️ Skipped - Feature flag not required for this migration

- [x] 12.4 Run MigrationValidator on asset_manager module

  - Verify no direct QThread usage remains
  - _Requirements: 6.5_
  - **Status**: ✅ Completed - 0 violations found (reduced from 2)

- [x] 13. Add CI integration for MigrationValidator ✅

  - Create GitHub Actions workflow for thread validation
  - Configure to run on push and pull request
  - Limit scan scope to migrated modules only (ai_assistant, asset_manager)
  - Configure failure threshold and report output path
  - Fail build if violations found in migrated modules
  - Add workflow badge to README
  - _Requirements: 6.5_
  - **Status**: ✅ Completed - CI integration configured
    - GitHub Actions workflow created: `.github/workflows/thread-migration-validation.yml`
    - Validates ai_assistant and asset_manager modules on push/PR
    - Generates validation report and uploads as artifact
    - Comments on PRs with validation results
    - Workflow badge added to README.md
    - Local validation script created: `scripts/validate_thread_migration.py`
    - Current validation status: 0 violations in both modules ✅

- [x] 14. Write comprehensive test suite ✅
- [x] 14.1 Unit tests for ThreadConfiguration ✅

  - Test JSON loading with valid and invalid data
  - Test module override resolution
  - Test default value fallback
  - _Requirements: 8.1, 8.2, 8.3, 8.4, 8.5, 12.1_
  - **Status**: ✅ Completed - 12 tests passing, 98% coverage

- [x] 14.2 Unit tests for CancellationToken injection ✅

  - Test function with cancel_token parameter
  - Test function without cancel_token parameter
  - Test functools.partial wrapped function
  - Test functools.wraps decorated function
  - Test lambda function
  - Test class method
  - _Requirements: 2.1, 2.2, 2.3, 12.2_
  - **Status**: ✅ Completed - 13 tests passing

- [x] 14.3 Unit tests for timeout mechanism ✅

  - Test task completes before timeout
  - Test task exceeds timeout and completes during grace
  - Test task stuck after grace period
  - Test timeout with zero (no timeout)
  - Add performance benchmarks for timeout overhead
  - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5, 12.3_
  - **Status**: ✅ Completed - 6 tests passing

- [x] 14.4 Unit tests for cleanup contract ✅

  - Test CleanupResult success
  - Test CleanupResult failure with error message
  - Test exception during cleanup
  - Test cleanup timeout
  - _Requirements: 3.1, 3.2, 3.3, 3.4, 12.4_
  - **Status**: ✅ Completed - 7 tests passing

- [x] 14.5 Unit tests for ThreadMonitor ✅

  - Test event recording for all states
  - Test NDJSON export format
  - Test privacy rule application (redact and mask)
  - Test metrics aggregation
  - Add performance benchmark for export (target < 100ms for 1000 events)
  - _Requirements: 9.1, 9.2, 9.3, 9.4, 9.5, 12.5_
  - **Status**: ✅ Completed - 9 tests passing, 100% coverage, performance benchmark included

- [x] 14.6 Integration test for shutdown sequence ✅

  - Create multiple test modules with varying cleanup times
  - Test some modules fail cleanup
  - Test some modules timeout
  - Test mixed failure scenario: combine timeout + exception + normal completion
  - Verify parallel execution
  - Verify failure aggregation in ShutdownResult with correct failure_type classification
  - Verify ShutdownResult.is_partial_failure() logic with mixed failures
  - Verify critical error logging when > 50% modules fail
  - _Requirements: 7.1, 7.2, 7.3, 7.4, 7.5, 12.4_
  - **Status**: ✅ Completed - 10 tests passing

- [x] 14.7 Integration test for thread pool backpressure ✅

  - Submit tasks up to pool limit
  - Submit tasks up to queue limit
  - Verify queue overflow rejection with QueueFullError
  - Verify task execution order
  - Test cancelling queued tasks and verify queue state consistency
  - Test cancelling running tasks and verify next queued task starts
  - Add performance benchmark for pool utilization under load
  - _Requirements: 11.1, 11.2, 11.3, 11.4, 11.5, 12.5_
  - **Status**: ✅ Completed - 9 tests passing, performance benchmark included

  **Task 14 Summary**: All 66 tests passing (100% pass rate), execution time: 11.95s

- [x] 15. Performance validation and optimization ✅

  - Aggregate all performance benchmarks from unit/integration tests
  - Verify ThreadManager initialization time (target < 50ms)
  - Verify task submission overhead (target < 10ms per task)
  - Verify shutdown sequence time (target within global_shutdown_timeout)
  - Verify monitoring export time (target < 100ms for 1000 events)
  - Create performance regression test suite
  - If performance targets not met:
    - Output detailed benchmark data with timestamps and system info
    - Log performance metrics to: logs/performance/thread_manager_benchmarks.json
    - Format: JSON with fields {timestamp, test_name, metric_name, value, target, system_info}
    - Generate performance report with bottleneck analysis to: reports/performance_analysis.md
    - Document optimization recommendations
  - Optimize based on benchmark data and re-test
  - Document performance characteristics and tuning guidelines
  - _Requirements: Performance targets from design_
  - **Status**: ✅ Completed - All performance targets exceeded
    - ThreadManager initialization: ~0ms (target < 50ms) ✅
    - Task submission overhead: ~0.3ms/task (target < 10ms) ✅
    - Shutdown sequence: ~116ms for 10 modules (target < 5000ms) ✅
    - Monitoring export: ~8ms for 1000 events (target < 100ms) ✅
    - Performance regression test suite created: `tests/test_performance_regression.py`
    - Performance tuning guide created: `docs/PERFORMANCE_TUNING_GUIDE.md`
    - Metrics logged to: `logs/performance/thread_manager_benchmarks.json`

- [ ] 16. Final validation and cleanup
  - Run MigrationValidator on entire codebase
  - Verify no direct QThread usage in migrated modules
  - Remove backward compatibility wrappers
  - Remove feature flags for fully migrated modules
  - Update all documentation
  - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5_

## Notes

- Tasks are ordered to build incrementally
- Each task includes specific requirements it addresses
- Testing is integrated throughout, not deferred to end
- Migration is phased (AI Assistant first, then Asset Manager)
- Feature flags allow rollback if issues discovered
- CI integration prevents regression after migration
