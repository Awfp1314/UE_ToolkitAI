# Task: 清理和文档更新

## Description

删除旧的配置管理器文件，更新项目文档，添加迁移指南，完成配置管理器统一化的最后收尾工作。

## Background

任务 3 已经完成了所有代码的迁移，项目中不再使用旧的配置管理器。现在需要删除旧文件，更新文档，确保项目的整洁性和可维护性。

## Reference Documentation

**Required:**

- 任务 1 的输出：API 映射表和架构设计文档
- 任务 2 的实现：统一配置管理器
- 任务 3 的迁移记录
- 项目文档：`AGENTS.md`、`core/README.md`、`core/CONFIG_MANAGER_README.md`

**Note:** 删除文件前必须确认任务 3 的迁移已完成且验证通过。

## Technical Requirements

1. 删除旧的配置管理器文件：
   - `core/config_manager.py`
   - `modules/asset_manager/logic/asset_local_config_manager.py`
2. 更新 `AGENTS.md` 中的配置管理示例代码
3. 更新 `core/README.md` 中的配置管理说明
4. 更新 `core/CONFIG_MANAGER_README.md`（如果需要重写）
5. 创建迁移指南文档（可选，如果有外部用户或插件开发者）
6. 更新版本号（根据项目规范）

## Dependencies

- 任务 3 的迁移完成和验证通过
- 项目文档文件
- Git 版本控制

## Implementation Approach

1. **前置检查**：
   - 确认任务 3 的所有迁移已完成
   - 确认应用运行正常，所有功能测试通过
   - 使用 grep 搜索确认项目中不再有旧配置管理器的导入

2. **删除旧文件**：
   - 删除 `core/config_manager.py`
   - 删除 `modules/asset_manager/logic/asset_local_config_manager.py`
   - 运行应用验证删除后无影响

3. **更新 AGENTS.md**：
   - 找到"配置管理"章节
   - 更新示例代码，使用统一配置管理器
   - 更新特性说明（如果有新增功能）

4. **更新 core/README.md**：
   - 更新配置管理器的使用说明
   - 更新示例代码
   - 添加新功能的说明（如全局配置、本地配置）

5. **更新 core/CONFIG_MANAGER_README.md**：
   - 检查是否需要重写或大幅更新
   - 更新 API 文档
   - 添加迁移指南章节（如果有外部用户）

6. **创建迁移指南**（可选）：
   - 如果项目有外部用户或插件开发者
   - 创建 `docs/migration/config-manager-migration.md`
   - 包含 API 映射表、迁移步骤、常见问题

7. **版本号更新**：
   - 根据项目规范更新版本号
   - 如果是重大重构，可能需要更新 MINOR 版本

## Acceptance Criteria

1. **旧文件删除**
   - Given 旧的配置管理器文件
   - When 执行删除操作
   - Then 文件被删除且应用运行正常

2. **文档更新完成**
   - Given 项目文档（AGENTS.md、core/README.md、core/CONFIG_MANAGER_README.md）
   - When 更新配置管理相关内容
   - Then 所有示例代码和说明使用统一配置管理器

3. **迁移指南创建**（如果需要）
   - Given 外部用户或插件开发者
   - When 创建迁移指南
   - Then 迁移指南包含 API 映射表、迁移步骤、常见问题

4. **版本号更新**
   - Given 项目版本管理规范
   - When 完成配置管理器统一化
   - Then 版本号已更新（如果需要）

5. **最终验证**
   - Given 所有清理和文档更新完成
   - When 运行应用并检查文档
   - Then 应用正常运行，文档准确无误，项目整洁

6. **Git 提交**
   - Given 所有更改完成
   - When 提交代码
   - Then 提交信息清晰，包含重构说明

## Metadata

- **Complexity**: Low
- **Labels**: Cleanup, Documentation, Refactoring, Version Management
- **Required Skills**: Documentation Writing, Git, Project Management
