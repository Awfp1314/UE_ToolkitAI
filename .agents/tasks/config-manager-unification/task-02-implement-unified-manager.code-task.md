# Task: 实现统一配置管理器

## Description

基于任务 1 的 API 映射表和架构设计，实现统一的配置管理器。整合 3 个现有配置管理器的功能，提供统一的接口，并实现向后兼容的适配层。

## Background

任务 1 已经完成了功能分析和架构设计，输出了详细的 API 映射表。现在需要基于 `core/config/config_manager.py` 进行扩展，整合其他两个配置管理器的功能，实现统一的配置管理系统。

## Reference Documentation

**Required:**

- 任务 1 的输出：API 映射表和架构设计文档
- 现有代码文件：
  - `core/config/config_manager.py`（作为基础）
  - `core/config_manager.py`（整合全局配置功能）
  - `modules/asset_manager/logic/asset_local_config_manager.py`（整合本地配置功能）

**Note:** 在开始实现前，必须先提醒用户进行 Git Commit 快照。

## Technical Requirements

1. **前置条件检查**：在开始实现前，输出提醒信息要求用户进行 Git Commit
2. 基于 `core/config/config_manager.py` 扩展实现统一配置管理器
3. 整合 `core/config_manager.py` 的全局配置功能：
   - 用户ID管理（get_user_id, set_user_id, get_or_create_user_id）
   - 跳过版本管理（get_skipped_versions, add_skipped_version, is_version_skipped）
   - 待上报事件队列（get_pending_events, add_pending_event, clear_pending_events）
4. 整合 `asset_local_config_manager.py` 的本地配置功能：
   - 本地配置路径设置（setup_local_paths）
   - 本地配置加载和保存（load_local_config, save_local_config）
   - 配置验证（validate_config_before_save）
   - 智能备份策略（should_create_backup, update_backup_record）
5. 实现向后兼容的适配层（如果需要）
6. 保持现有的核心功能：
   - 模板合并和版本升级
   - 配置缓存机制
   - 备份和恢复
   - 异步配置加载和保存
7. 编写单元测试验证核心功能

## Dependencies

- `core/config/config_manager.py`（基础实现）
- `core/config/config_validator.py`（配置验证器）
- `core/config/config_backup.py`（备份管理器）
- `core/utils/config_utils.py`（配置工具类）
- `core/utils/path_utils.py`（路径工具类）
- `core/utils/thread_utils.py`（线程管理器）
- `core/exceptions.py`（异常定义）

## Implementation Approach

1. **前置检查**：
   - 输出提醒信息：要求用户执行 `git add . && git commit -m "[refactor] 配置管理器重构前快照"`
   - 等待用户确认后再继续

2. **扩展 ConfigManager 类**：
   - 在 `core/config/config_manager.py` 中添加全局配置管理方法
   - 添加本地配置管理方法
   - 保持现有方法的签名和行为不变

3. **整合全局配置功能**：
   - 添加 `_global_config_path` 属性（用户目录下的全局配置文件）
   - 实现用户ID管理方法
   - 实现跳过版本管理方法
   - 实现待上报事件队列管理方法

4. **整合本地配置功能**：
   - 添加 `setup_local_paths()` 方法
   - 添加 `load_local_config()` 和 `save_local_config()` 方法
   - 添加 `validate_config_before_save()` 方法
   - 添加智能备份策略方法

5. **向后兼容适配层**（如果需要）：
   - 创建 `core/config_manager_adapter.py`
   - 实现旧接口到新接口的映射
   - 添加废弃警告（DeprecationWarning）

6. **单元测试**：
   - 测试全局配置功能（用户ID、跳过版本、事件队列）
   - 测试本地配置功能（路径设置、加载保存、验证）
   - 测试配置合并和升级
   - 测试缓存机制
   - 测试备份和恢复

## Acceptance Criteria

1. **前置条件提醒**
   - Given 任务开始执行
   - When 准备开始实现
   - Then 输出 Git Commit 提醒信息并等待用户确认

2. **全局配置功能整合**
   - Given 统一配置管理器实现
   - When 调用用户ID管理方法
   - Then 功能与 `core/config_manager.py` 中的实现一致

3. **本地配置功能整合**
   - Given 统一配置管理器实现
   - When 调用本地配置管理方法
   - Then 功能与 `asset_local_config_manager.py` 中的实现一致

4. **向后兼容性**
   - Given 统一配置管理器实现
   - When 使用旧接口调用（如果有适配层）
   - Then 功能正常且输出废弃警告

5. **单元测试覆盖**
   - Given 统一配置管理器实现
   - When 运行单元测试
   - Then 所有核心功能测试通过，覆盖率 > 80%

6. **代码质量**
   - Given 实现代码
   - When 检查代码质量
   - Then 遵循 PEP 8 规范，包含类型注解和文档字符串

## Metadata

- **Complexity**: High
- **Labels**: Refactoring, Implementation, Configuration Management, Unit Testing
- **Required Skills**: Python, Object-Oriented Design, Unit Testing, Refactoring
