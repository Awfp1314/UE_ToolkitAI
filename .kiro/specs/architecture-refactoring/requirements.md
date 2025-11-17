# Requirements Document

## Introduction

本文档定义了 UE Toolkit AI 项目架构重构的需求。该项目当前功能完整且可正常运行，但存在架构复杂度高、服务分散、线程管理不统一等问题。本次重构采用**方案 A（最小改动）**，重点解决最明显的架构问题，降低风险的同时大幅降低代码复杂度。

重构范围包括：

- 创建统一的服务层（Service Layer）
- 统一横切关注点的访问方式（配置、路径、日志、样式）
- 保持所有现有功能不变

## Glossary

- **Application**: UE Toolkit AI 应用程序主体
- **ServiceLayer**: 统一服务层，提供单例访问接口的服务集合
- **ThreadService**: 线程调度服务，封装 ThreadManager
- **ConfigService**: 配置访问服务，封装 ConfigManager
- **LogService**: 日志服务，封装 Logger
- **StyleService**: 样式服务，封装 StyleSystem
- **PathService**: 路径访问服务，统一路径获取逻辑
- **Module**: 应用程序的功能模块（如 asset_manager、ai_assistant 等）
- **LegacyCode**: 现有的旧代码实现
- **CrossCuttingConcern**: 横切关注点，指配置、日志、路径、样式等跨模块的通用功能

## Requirements

### Requirement 1: 统一服务层架构

**User Story:** 作为开发者，我希望通过统一的服务层访问所有共用服务，以便降低模块间耦合度并提高代码可维护性

#### Acceptance Criteria

1. THE ServiceLayer SHALL provide singleton access to ThreadService, ConfigService, LogService, StyleService, and PathService
2. WHEN a Module requests a service, THE ServiceLayer SHALL return the same singleton instance across all requests using module-level singleton pattern
3. THE ServiceLayer SHALL initialize all services lazily on first access rather than during Application startup
4. THE ServiceLayer SHALL provide a cleanup method that properly releases all service resources
5. WHERE a Module needs to access multiple services, THE Module SHALL import services from a single entry point `core.services`
6. THE ServiceLayer SHALL implement module-level singletons by storing instances as module-level variables in `core/services/__init__.py`
7. THE ServiceLayer SHALL initialize services on first access in a dependency-aware manner
8. IF a service depends on another service, THE dependent service SHALL trigger initialization of its dependencies automatically
9. THE ServiceLayer SHALL prevent circular dependencies by ensuring services only depend on lower-level services (LogService and PathService are lowest level, ConfigService and StyleService are mid-level, ThreadService is highest level)
10. WHEN LogService is initialized, IT SHALL use print() for initialization logging instead of calling itself
11. WHEN PathService is initialized, IT SHALL NOT depend on LogService, and SHALL use print() for initialization logging
12. THE dependency hierarchy SHALL be strictly enforced: LogService and PathService (level 0, no dependencies) → ConfigService and StyleService (level 1, may depend on level 0) → ThreadService (level 2, may depend on level 0 and 1)
13. THE ServiceLayer SHALL maintain an initialization state for each service (NOT_INITIALIZED, INITIALIZING, INITIALIZED) to prevent re-entrant initialization
14. WHEN a service is being initialized (state = INITIALIZING), IF a different service tries to access it, THE ServiceLayer SHALL raise an error to prevent circular dependencies; same-service re-entrant access SHALL be allowed by returning the instance being initialized

### Requirement 2: 线程调度服务

**User Story:** 作为模块开发者，我希望通过统一的 ThreadService 执行异步任务，以便避免直接创建线程并确保资源正确管理

#### Acceptance Criteria

1. THE ThreadService SHALL encapsulate the existing ThreadManager functionality by delegating to a ThreadManager instance
2. WHEN a Module submits an async task, THE ThreadService SHALL execute the task using ThreadManager.run_in_thread()
3. THE ThreadService SHALL expose the following methods: run_async(), cancel_task(), get_thread_usage(), and cleanup()
4. THE run_async() method SHALL accept a task function and optional callbacks, and return a tuple (worker, cancellation_token)
5. THE task function signature SHALL accept cancellation_token as an optional parameter to enable cooperative cancellation
6. THE cancel_task() method SHALL accept a cancellation_token or worker instance to identify which task to cancel
7. THE ThreadService SHALL support callback functions for task completion (on_result, on_error, on_finished, on_progress)
8. WHEN the Application shuts down, THE ThreadService SHALL call ThreadManager.cleanup() to cancel all pending tasks and wait for running tasks to complete
9. THE ThreadService SHALL support cooperative task cancellation through CancellationToken
10. WHEN a task is cancelled, THE ThreadService SHALL set the cancellation flag, but the task must check cancel_token.is_cancelled() periodically to actually stop
11. THE ThreadService SHALL NOT support forced thread termination, only cooperative cancellation

### Requirement 3: 配置访问服务

**User Story:** 作为模块开发者，我希望通过统一的 ConfigService 访问配置，以便避免直接操作 ConfigManager 并确保配置访问的一致性

#### Acceptance Criteria

1. THE ConfigService SHALL manage a registry of ConfigManager instances, one per module
2. WHEN a Module requests configuration for the first time, THE ConfigService SHALL create a new ConfigManager instance for that module
3. WHEN a Module requests configuration subsequently, THE ConfigService SHALL return the cached ConfigManager instance
4. THE ConfigService SHALL provide methods to load, save, and update module configurations by delegating to the appropriate ConfigManager
5. IF configuration file is missing or corrupted, THEN THE ConfigService SHALL delegate to ConfigManager to return default configuration values
6. THE ConfigService SHALL support both synchronous and asynchronous configuration operations as provided by ConfigManager

### Requirement 4: 日志服务

**User Story:** 作为模块开发者，我希望通过统一的 LogService 记录日志，以便简化日志调用并支持集中式日志管理

#### Acceptance Criteria

1. THE LogService SHALL encapsulate the existing Logger singleton by using the global get_logger() function
2. THE LogService SHALL provide a get_logger(name) method that delegates to core.logger.get_logger()
3. WHEN a Module logs a message, THE LogService SHALL include module name and timestamp in the log entry as provided by the existing Logger
4. THE LogService SHALL support structured logging with additional context data through the existing logging.Logger interface
5. THE LogService SHALL allow configuration of log level by delegating to the underlying logging.Logger.setLevel() method
6. THE LogService SHALL integrate with the existing Logger's file and console handlers without modification

### Requirement 5: 样式服务

**User Story:** 作为模块开发者，我希望通过统一的 StyleService 应用样式，以便避免直接调用 StyleSystem 并确保样式应用的一致性

#### Acceptance Criteria

1. THE StyleService SHALL encapsulate the existing StyleSystem singleton instance
2. WHEN a Module requests to apply a theme, THE StyleService SHALL delegate to StyleSystem.apply_theme()
3. THE StyleService SHALL provide methods to get current theme, list available themes, and switch themes
4. THE StyleService SHALL forward StyleSystem.themeChanged signal to allow modules to respond to theme changes
5. THE StyleService SHALL leverage StyleSystem's existing cache mechanism for stylesheet caching
6. THE StyleService SHALL maintain backward compatibility by internally using the global style_system instance
7. THE StyleService SHALL focus on runtime theme loading and application in the initial implementation
8. THE StyleService MAY integrate ThemeBuilder for theme compilation in future iterations, but this is not required for the current refactoring
9. WHERE theme compilation is needed, THE Application SHALL continue to use ThemeBuilder directly until StyleService integration is implemented

### Requirement 6: 路径访问服务

**User Story:** 作为模块开发者，我希望通过统一的 PathService 获取路径，以便避免直接使用 QStandardPaths 或环境变量并确保跨平台兼容性

#### Acceptance Criteria

1. THE PathService SHALL provide methods to get common paths (user data dir, config dir, cache dir, log dir)
2. THE PathService SHALL encapsulate the existing PathUtils class and delegate all path operations to it
3. WHEN a Module requests a path, THE PathService SHALL return an absolute Path object
4. THE PathService SHALL create directories if they do not exist when requested
5. THE PathService SHALL validate that paths exist (creating directories if needed) before returning
6. THE PathService MAY add accessibility validation (read/write permissions) in future iterations, but this is not required for the initial implementation
7. THE PathService SHALL maintain backward compatibility by internally using PathUtils for all platform-specific logic
8. THE PathService SHALL convert string paths from PathUtils to Path objects before returning to ensure type consistency
9. THE PathService SHALL accept both string and Path arguments for method parameters to maintain flexibility
10. WHERE PathUtils returns a string path, THE PathService SHALL wrap it using pathlib.Path() before returning

### Requirement 7: 向后兼容性

**User Story:** 作为项目维护者，我希望重构后的代码保持向后兼容，以便现有模块无需立即修改即可继续工作

#### Acceptance Criteria

1. THE Application SHALL continue to support LegacyCode that directly uses ThreadManager, ConfigManager, Logger, and StyleSystem
2. WHEN LegacyCode accesses old APIs, THE Application SHALL function correctly without errors
3. THE Application SHALL provide deprecation warnings when LegacyCode uses old APIs, but only in debug mode or when explicitly enabled to avoid log noise
4. THE Application SHALL document migration paths from old APIs to new ServiceLayer APIs
5. WHERE possible, THE old utility classes SHALL delegate to ServiceLayer internally to ensure consistency

### Requirement 8: 渐进式迁移

**User Story:** 作为开发者，我希望能够渐进式地将现有模块迁移到新的服务层，以便降低迁移风险并验证每个步骤

#### Acceptance Criteria

1. THE ServiceLayer SHALL coexist with LegacyCode during the migration period
2. WHEN a Module is migrated to use ServiceLayer, THE Module SHALL not break existing functionality
3. THE Application SHALL provide clear examples and documentation for migrating each type of service usage
4. THE Application SHALL allow mixed usage of old and new APIs within the same module during migration
5. THE Application SHALL track migration progress through code comments or migration status file
6. THE migration SHALL follow this priority order: first migrate core/app_manager.py, then migrate ui/ue_main_window.py, then migrate individual modules (asset_manager, ai_assistant, etc.)
7. WHEN migrating a module, THE developer SHALL update imports first, then update service usage, then test functionality before proceeding to the next module

### Requirement 9: 错误处理和日志

**User Story:** 作为开发者，我希望服务层提供清晰的错误处理和日志记录，以便快速定位和解决问题

#### Acceptance Criteria

1. WHEN a service operation fails, THE ServiceLayer SHALL log detailed error information including context
2. THE ServiceLayer SHALL raise specific exceptions for different error types (ConfigError, ThreadError, etc.)
3. IF a service initialization fails, THEN THE Application SHALL log the error and attempt graceful degradation
4. THE ServiceLayer SHALL provide health check methods for each service that verify: ThreadService (active thread count < max), ConfigService (config files readable), LogService (log handlers active), StyleService (current theme loaded), PathService (required directories exist)
5. WHEN a health check fails, THE ServiceLayer SHALL log a warning but SHALL NOT prevent the application from starting or running
6. WHEN debugging is enabled (via DEBUG_SERVICES environment variable or application configuration), THE ServiceLayer SHALL log detailed operation traces

### Requirement 10: 性能和资源管理

**User Story:** 作为用户，我希望重构后的应用保持良好的性能和资源使用，以便应用响应迅速且不占用过多资源

#### Acceptance Criteria

1. THE ServiceLayer SHALL initialize services lazily where possible to reduce startup time
2. THE ServiceLayer SHALL reuse singleton instances to minimize memory overhead
3. WHEN the Application shuts down, THE ServiceLayer SHALL release all resources within 5 seconds under normal conditions, or log a warning if cleanup takes longer
4. THE ServiceLayer SHALL not introduce performance regression compared to LegacyCode
5. THE ServiceLayer SHALL monitor and log the following metrics when debugging is enabled (via DEBUG_SERVICES environment variable or application configuration): active thread count, service initialization time, configuration load/save time
6. WHEN cleaning up services, THE ServiceLayer SHALL follow this order: ThreadService.cleanup() → StyleService.clear_cache() → ConfigService (save cached configurations if modified) → LogService (close handlers if implemented, otherwise skip)

### Requirement 11: 测试和验证策略

**User Story:** 作为开发者，我希望有明确的测试和验证策略，以便确保重构后的代码质量和功能正确性

#### Acceptance Criteria

1. THE Application SHALL verify service layer functionality through manual testing of core workflows (startup, module loading, theme switching, configuration save/load)
2. WHEN a service is implemented, THE developer SHALL test the service by running the application and verifying expected behavior
3. THE Application SHALL maintain a verification checklist documenting which services have been tested and which workflows have been validated
4. THE Application SHALL prioritize functional testing over unit testing during the initial refactoring phase
5. WHERE automated tests exist for legacy code, THE Application SHALL ensure those tests continue to pass after refactoring
6. THE Application SHALL document any breaking changes or behavioral differences discovered during testing
7. WHEN all services are implemented and tested, THE Application SHALL perform end-to-end regression testing of all major features
8. THE Application SHOULD include at least 3 integration tests: service singleton and dependency order, ThreadService cooperative cancellation, ConfigService read/write with backup
