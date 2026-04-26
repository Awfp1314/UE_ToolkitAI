# Task: 渐进式迁移现有代码

## Description

采用渐进式替换策略，分阶段迁移项目中所有使用旧配置管理器的代码。先在非核心模块进行试点验证，确保应用正常运行后，再批量迁移其他模块。

## Background

项目中有多处代码使用了旧的配置管理器：

- `from core.config_manager import ConfigManager`（约 10+ 处）
- `from core.config.config_manager import ConfigManager`（约 20+ 处）
- `from modules.asset_manager.logic.asset_local_config_manager import AssetLocalConfigManager`（1 处）

为了降低风险，采用渐进式迁移策略，分两个阶段完成迁移。

## Reference Documentation

**Required:**

- 任务 1 的输出：API 映射表
- 任务 2 的实现：统一配置管理器
- 项目中所有使用配置管理器的代码（通过 grep 搜索）

**Note:** 每个阶段完成后必须运行应用验证功能正常。

## Technical Requirements

1. **阶段 1（试点验证）**：
   - 选择 1-2 个非核心模块进行替换（建议：`core/services/_config_service.py`）
   - 更新导入语句
   - 根据 API 映射表调整方法调用
   - 运行应用验证功能正常
2. **验证点**：
   - 应用能够正常启动
   - 配置加载正常
   - 配置保存正常
   - 无异常或错误日志
3. **阶段 2（批量迁移）**：
   - 迁移所有 `from core.config_manager import ConfigManager` 引用
   - 迁移所有 `from modules.asset_manager.logic.asset_local_config_manager import AssetLocalConfigManager` 引用
   - 更新方法调用（根据 API 映射表）
   - 运行应用验证功能正常

4. **迁移范围**：
   - UI 层：`ui/ue_main_window.py`、`ui/settings_widget.py`
   - 模块层：`modules/ai_assistant/`、`modules/asset_manager/`
   - 核心层：`core/module_manager.py`、`core/services/`
   - 文档：`core/README.md`、`core/CONFIG_MANAGER_README.md`、`AGENTS.md`

## Dependencies

- 任务 2 的统一配置管理器实现
- 项目中所有使用配置管理器的代码
- 应用启动和运行环境

## Implementation Approach

1. **阶段 1：试点验证**
   - 使用 grep 搜索 `from core.config_manager import ConfigManager`
   - 选择 `core/services/_config_service.py` 作为试点模块
   - 更新导入语句为统一配置管理器
   - 根据 API 映射表调整方法调用（如果有变化）
   - 运行应用，检查日志，验证配置功能正常
   - 如果发现问题，回滚并修复统一配置管理器

2. **验证点检查**
   - 启动应用，观察启动日志
   - 检查配置文件是否正常加载
   - 测试配置保存功能
   - 检查 `logs/runtime/ue_toolkit.log` 是否有错误

3. **阶段 2：批量迁移**
   - 使用 grep 搜索所有配置管理器的导入
   - 按模块分组（UI 层、模块层、核心层）
   - 逐个模块更新导入和方法调用
   - 每更新 3-5 个文件后运行应用验证
   - 记录迁移进度和遇到的问题

4. **特殊处理**
   - `modules/asset_manager/logic/asset_manager_logic.py`：
     - 移除 `AssetLocalConfigManager` 的导入和实例化
     - 使用统一配置管理器的本地配置方法
   - `core/module_manager.py`：
     - 确保模块加载时使用正确的配置管理器
   - 文档更新：
     - 更新示例代码中的导入语句
     - 更新 API 使用示例

5. **回归测试**
   - 启动应用，测试所有主要功能模块
   - 测试配置加载、保存、升级
   - 测试资产管理器的配置功能
   - 测试 AI 助手的配置功能
   - 检查日志文件，确保无错误

## Acceptance Criteria

1. **阶段 1 试点成功**
   - Given 选定的试点模块
   - When 完成导入和方法调用的更新
   - Then 应用能够正常启动，配置功能正常，无错误日志

2. **验证点通过**
   - Given 阶段 1 完成
   - When 运行应用并测试配置功能
   - Then 所有验证点检查通过（启动、加载、保存、日志）

3. **阶段 2 批量迁移完成**
   - Given 所有使用旧配置管理器的代码
   - When 完成所有导入和方法调用的更新
   - Then 项目中不再有旧配置管理器的导入语句

4. **功能回归测试通过**
   - Given 完成所有代码迁移
   - When 运行应用并测试所有主要功能
   - Then 所有功能正常，无异常或错误

5. **文档更新完成**
   - Given 项目文档
   - When 更新配置管理相关的示例代码
   - Then 所有示例代码使用统一配置管理器

6. **渐进式约束满足**
   - Given 迁移过程
   - When 检查迁移策略
   - Then 严格遵循了"试点验证 → 批量迁移"的渐进式策略

## Metadata

- **Complexity**: Medium
- **Labels**: Refactoring, Migration, Testing, Code Update
- **Required Skills**: Python, Refactoring, Testing, Code Search and Replace
