# Task: 分析与设计统一配置管理器

## Description

分析现有的 3 个配置管理器（`core/config_manager.py`、`core/config/config_manager.py`、`modules/asset_manager/logic/asset_local_config_manager.py`）的功能差异和使用场景，设计统一的配置管理器架构，并输出详细的 API 映射表。

## Background

项目中存在 3 个不同的配置管理器，职责重叠但功能各异：

- `core/config_manager.py`: 全局配置管理（用户ID、跳过版本、待上报事件队列）
- `core/config/config_manager.py`: 模块化配置管理（模板合并、版本升级、备份恢复、缓存机制）
- `modules/asset_manager/logic/asset_local_config_manager.py`: 资产库本地配置管理（资产序列化、配置迁移、备份策略）

这种分散的配置管理导致代码维护困难、功能重复、接口不统一。需要设计一个统一的配置管理器来整合这些功能。

## Reference Documentation

**Required:**

- 现有代码文件：
  - `core/config_manager.py`
  - `core/config/config_manager.py`
  - `modules/asset_manager/logic/asset_local_config_manager.py`
- 项目文档：`AGENTS.md`、`core/README.md`、`core/CONFIG_MANAGER_README.md`

**Note:** 必须仔细阅读 3 个配置管理器的完整实现，理解每个方法的用途和调用场景。

## Technical Requirements

1. 分析 3 个配置管理器的所有公开方法和私有方法
2. 识别功能重叠、功能互补和独特功能
3. 设计统一的配置管理器架构，确定保留、合并、废弃的功能
4. 输出详细的 API 映射表，包括：
   - 旧方法名 → 新方法名的映射
   - 标注废弃的方法及原因
   - 标注需要合并的方法及合并策略
   - 标注新增的方法及用途
5. 设计向后兼容的适配层策略
6. 确定配置文件格式和存储路径的统一方案

## Dependencies

- 现有 3 个配置管理器的源代码
- `core/utils/config_utils.py`（配置工具类）
- `core/exceptions.py`（异常定义）
- 项目中所有使用配置管理器的代码（通过 grep 搜索）

## Implementation Approach

1. **功能清单分析**：
   - 列出 `core/config_manager.py` 的所有方法及功能
   - 列出 `core/config/config_manager.py` 的所有方法及功能
   - 列出 `asset_local_config_manager.py` 的所有方法及功能
2. **使用场景分析**：
   - 搜索项目中所有导入和使用这 3 个管理器的代码
   - 分析每个方法的实际调用场景和频率
   - 识别关键路径和非关键路径
3. **架构设计**：
   - 确定统一配置管理器的核心接口
   - 设计配置类型分层（全局配置、模块配置、本地配置）
   - 设计配置存储路径规范
   - 设计缓存策略和备份策略
4. **API 映射表生成**：
   - 创建详细的方法映射表（旧 → 新）
   - 标注每个方法的状态（保留/合并/废弃/新增）
   - 说明合并或废弃的理由
   - 提供迁移建议

5. **向后兼容策略**：
   - 设计适配层（Adapter Pattern）
   - 确定过渡期的兼容方案
   - 规划废弃警告机制

## Acceptance Criteria

1. **功能清单完整性**
   - Given 3 个配置管理器的源代码
   - When 完成功能分析
   - Then 所有公开方法和关键私有方法都被列出并分类

2. **使用场景覆盖**
   - Given 项目代码库
   - When 搜索所有配置管理器的使用
   - Then 识别出所有调用点和使用模式

3. **API 映射表输出**
   - Given 功能分析结果
   - When 设计统一配置管理器
   - Then 输出包含以下内容的 API 映射表：
     - 每个旧方法的映射关系（保留/合并/废弃）
     - 合并或废弃的理由说明
     - 新增方法的用途说明
     - 向后兼容的适配策略

4. **架构设计文档**
   - Given API 映射表
   - When 完成架构设计
   - Then 输出包含以下内容的设计文档：
     - 统一配置管理器的类结构
     - 配置类型分层和存储路径规范
     - 缓存策略和备份策略
     - 向后兼容的实现方案

5. **防御性约束满足**
   - Given 任务要求
   - When 完成分析和设计
   - Then API 映射表必须在对话中输出并等待用户确认

## Metadata

- **Complexity**: High
- **Labels**: Refactoring, Architecture Design, API Design, Configuration Management
- **Required Skills**: Python, Software Architecture, API Design, Refactoring Patterns
