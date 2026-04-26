# UE Toolkit 文档索引

## 📚 文档概览

本文档集为 AI 助手提供了 UE Toolkit 代码库的全面知识库。通过这个索引，AI 助手可以快速定位所需信息，有效地协助开发工作。

## 🎯 如何使用本文档

### 对于 AI 助手

1. **首次接触项目**: 从 `codebase_info.md` 开始，了解项目基本信息
2. **理解架构**: 查看 `architecture.md` 了解系统设计
3. **查找组件**: 在 `components.md` 中查找具体组件的实现
4. **使用 API**: 参考 `interfaces.md` 了解接口定义
5. **理解数据**: 查看 `data_models.md` 了解数据结构
6. **跟踪流程**: 参考 `workflows.md` 了解业务流程
7. **管理依赖**: 查看 `dependencies.md` 了解依赖关系

### 快速查询指南

**我需要...**

- **了解项目是什么** → `codebase_info.md`
- **理解系统如何组织** → `architecture.md`
- **找到特定功能的实现** → `components.md`
- **调用某个 API** → `interfaces.md`
- **理解数据结构** → `data_models.md`
- **了解某个流程如何工作** → `workflows.md`
- **添加或更新依赖** → `dependencies.md`

## 📄 文档文件详解

### 1. codebase_info.md

**用途**: 项目基本信息和概览

**包含内容**:

- 项目名称、版本、作者
- 项目描述和目标
- 技术栈和主要依赖
- 项目结构概览
- 支持的编程语言
- 许可证模式
- 构建和打包信息

**何时查阅**:

- 首次了解项目
- 需要项目基本信息
- 了解技术栈
- 查看项目统计

**关键信息**:

- 版本: v1.2.52
- 主要语言: Python
- UI 框架: PyQt6
- 架构: 模块化插件架构

---

### 2. architecture.md

**用途**: 系统架构和设计模式

**包含内容**:

- 架构概览和分层设计
- 应用层、引导层、核心层、模块层、UI 层、服务层
- 启动流程详解
- 模块管理系统
- 配置管理系统
- 安全模块
- 设计模式应用
- 数据流和通信机制
- 性能优化策略

**何时查阅**:

- 理解系统整体设计
- 添加新模块
- 修改核心功能
- 优化性能
- 理解模块间通信

**关键概念**:

- 分层架构
- 模块化设计
- 依赖注入
- 事件驱动
- 异步加载

---

### 3. components.md

**用途**: 主要组件的详细说明

**包含内容**:

- 核心组件（Bootstrap、ModuleManager、ConfigManager 等）
- 模块组件（AI 助手、资产管理、工程管理等）
- UI 组件（主窗口、设置界面、系统托盘等）
- 服务组件（MCP 桥接、更新检查等）
- 工具脚本
- 组件间通信
- 组件生命周期

**何时查阅**:

- 查找特定组件的实现
- 理解组件职责
- 修改组件功能
- 添加新组件
- 调试组件问题

**核心组件**:

- AppBootstrap: 启动协调器
- ModuleManager: 模块管理
- ConfigManager: 配置管理
- LicenseManager: 许可证管理
- AIAssistantModule: AI 助手
- AssetManagerModule: 资产管理

---

### 4. interfaces.md

**用途**: API 和接口定义

**包含内容**:

- 模块接口（ModuleInterface）
- 配置接口（ConfigManager API）
- 许可证接口（LicenseManager API）
- AI 助手接口（LLM 客户端、工具系统）
- MCP 协议接口
- UE Editor HTTP API
- 日志接口
- 事件与信号
- 数据模型
- 错误处理

**何时查阅**:

- 调用 API
- 实现接口
- 集成外部服务
- 处理事件
- 错误处理

**关键接口**:

- ModuleInterface: 模块标准接口
- ConfigManager: 配置管理 API
- LicenseManager: 许可证 API
- BaseLLMClient: LLM 客户端接口
- MCP JSON-RPC: MCP 协议

---

### 5. data_models.md

**用途**: 数据结构和模型定义

**包含内容**:

- 核心数据模型（ModuleInfo、ConfigSchema 等）
- 许可证模型（LicenseStatus）
- 资产模型（Asset、AssetType）
- 工程模型（Project）
- 配置工具模型（ConfigSnapshot）
- AI 助手模型（Message、ToolDefinition）
- MCP 模型（MCPRequest、MCPResponse）
- 蓝图模型（BlueprintData）
- 数据持久化
- 数据验证
- 数据迁移

**何时查阅**:

- 理解数据结构
- 创建新数据模型
- 数据验证
- 数据库设计
- 数据迁移

**核心模型**:

- Asset: 资产数据
- Project: 工程数据
- LicenseStatus: 许可证状态
- Message: 聊天消息
- BlueprintData: 蓝图数据

---

### 6. workflows.md

**用途**: 业务流程和工作流

**包含内容**:

- 应用启动流程
- 模块生命周期
- 配置管理流程
- 资产管理流程（导入、导出、预览）
- AI 助手工作流程（对话、工具调用）
- 工程管理流程
- 配置工具流程
- 许可证验证流程
- 更新检查流程
- 错误处理流程
- 资源清理流程

**何时查阅**:

- 理解业务流程
- 优化流程
- 调试流程问题
- 添加新流程
- 性能优化

**关键流程**:

- 应用启动: 从 main.py 到主窗口显示
- 模块加载: 发现、加载、初始化
- 资产导入: 识别、过滤、保存
- AI 对话: 消息、工具调用、响应

---

### 7. dependencies.md

**用途**: 依赖关系和管理

**包含内容**:

- Python 依赖（必需、可选、AI、安全、开发）
- 模块依赖关系
- 外部服务依赖
- 系统依赖
- 打包依赖
- 依赖管理（安装、更新、冲突解决）
- 依赖安全
- 国内镜像源
- 依赖许可证

**何时查阅**:

- 安装依赖
- 更新依赖
- 解决依赖冲突
- 添加新依赖
- 打包应用
- 安全审计

**关键依赖**:

- PyQt6: UI 框架
- Pillow: 图片处理
- requests: HTTP 请求
- cryptography: 加密
- sentence-transformers: AI 模型

---

### 8. review_notes.md

**用途**: 文档审查和改进建议

**包含内容**:

- 文档一致性检查结果
- 文档完整性评估
- 发现的问题和差异
- 改进建议
- 待补充内容

**何时查阅**:

- 改进文档
- 查找文档问题
- 了解文档限制

---

## 🔍 常见问题快速索引

### 项目相关

**Q: UE Toolkit 是什么？**
A: 查看 `codebase_info.md` → 项目概述

**Q: 支持哪些 UE 版本？**
A: 查看 `codebase_info.md` → 关键特性

**Q: 如何构建和打包？**
A: 查看 `codebase_info.md` → 构建与打包

### 架构相关

**Q: 应用如何启动？**
A: 查看 `architecture.md` → 架构概览 → 启动流程
或 `workflows.md` → 应用启动流程

**Q: 模块如何加载？**
A: 查看 `architecture.md` → 核心层 → 模块管理
或 `workflows.md` → 模块生命周期

**Q: 配置如何管理？**
A: 查看 `architecture.md` → 核心层 → 配置管理
或 `workflows.md` → 配置管理流程

### 开发相关

**Q: 如何添加新模块？**
A: 查看 `architecture.md` → 扩展性 → 添加新模块
和 `interfaces.md` → 模块接口

**Q: 如何调用 API？**
A: 查看 `interfaces.md` → 对应的 API 部分

**Q: 如何处理错误？**
A: 查看 `interfaces.md` → 错误处理
或 `workflows.md` → 错误处理流程

**Q: 如何添加依赖？**
A: 查看 `dependencies.md` → 依赖管理

### 功能相关

**Q: AI 助手如何工作？**
A: 查看 `components.md` → AI 助手模块
和 `workflows.md` → AI 助手工作流程

**Q: 资产如何导入？**
A: 查看 `workflows.md` → 资产管理流程 → 资产导入流程

**Q: 许可证如何验证？**
A: 查看 `components.md` → 安全与许可证管理
和 `workflows.md` → 许可证验证流程

**Q: MCP 协议如何使用？**
A: 查看 `interfaces.md` → MCP 协议接口
和 `components.md` → MCP 桥接服务

## 📊 文档统计

- **总文档数**: 8 个
- **总字数**: 约 50,000+ 字
- **覆盖范围**:
  - 核心架构: 100%
  - 主要组件: 100%
  - API 接口: 100%
  - 数据模型: 100%
  - 业务流程: 100%
  - 依赖关系: 100%

## 🔄 文档更新

**最后更新**: 2026-04-26

**更新频率**:

- 主要版本发布时更新
- 架构变更时更新
- 新功能添加时更新

**如何更新**:

1. 运行 codebase-summary 技能
2. 审查生成的文档
3. 手动补充特定内容
4. 提交更新

## 💡 使用技巧

### 对于 AI 助手

1. **分层查询**: 先查索引，再查具体文档
2. **关键词搜索**: 使用文档中的关键词快速定位
3. **交叉引用**: 多个文档结合使用，获得完整信息
4. **图表优先**: 优先查看 Mermaid 图表，快速理解结构
5. **代码示例**: 参考代码示例，理解实际用法

### 对于开发者

1. **新手入门**: 按顺序阅读 codebase_info → architecture → components
2. **功能开发**: 查看 interfaces → data_models → workflows
3. **问题调试**: 查看 workflows → components → architecture
4. **性能优化**: 查看 architecture → workflows → dependencies

## 🎓 学习路径

### 初级（了解项目）

1. `codebase_info.md`: 项目概览
2. `architecture.md`: 系统架构（概览部分）
3. `components.md`: 核心组件（概览部分）

### 中级（开发功能）

1. `interfaces.md`: API 接口
2. `data_models.md`: 数据模型
3. `workflows.md`: 业务流程
4. `dependencies.md`: 依赖管理

### 高级（架构设计）

1. `architecture.md`: 完整架构
2. `components.md`: 所有组件
3. `workflows.md`: 所有流程
4. `review_notes.md`: 改进建议

## 📞 获取帮助

如果文档中没有找到所需信息：

1. **检查代码**: 直接查看源代码和注释
2. **查看日志**: 运行时日志可能包含有用信息
3. **调试运行**: 使用调试器跟踪执行流程
4. **查看测试**: 测试代码展示了如何使用 API
5. **联系开发者**: 通过 QQ 群 1048699469 联系

## 🔗 相关资源

- **用户指南**: `Docs/USER_GUIDE.md`
- **MCP 集成**: `Docs/MCP_INTEGRATION.md`
- **核心模块**: `core/README.md`
- **配置管理**: `core/CONFIG_MANAGER_README.md`
- **更新检查**: `core/UPDATE_CHECKER_README.md`

---

**提示**: 本索引文件是 AI 助手的主要入口点。将此文件添加到 AI 助手的上下文中，可以快速访问整个知识库。
