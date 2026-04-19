# Requirements Document

## Introduction

本文档定义了 UE Toolkit 蓝图分析功能增强的需求。当前 AI 助手无法有效分析 Unreal Engine 蓝图，因为 ExtractBlueprint 工具返回的数据不完整，缺少节点连接关系、引脚信息和执行流数据。此外，项目资产浏览效率低下，且存在中文编码问题。本功能旨在解决这些核心痛点，使 AI 能够理解蓝图逻辑并提供精确的修改指导。

## Glossary

- **Blueprint_Analyzer**: C++ UE 插件，负责从 Unreal Engine 中提取蓝图数据
- **MCP_Bridge**: Python 桥接服务，将 Blueprint_Analyzer 的功能暴露给 AI 助手
- **ExtractBlueprint_Tool**: MCP 工具，用于提取蓝图图表数据
- **Node**: 蓝图中的单个节点，包含标题、类型、引脚和位置信息
- **Pin**: 节点上的连接点，包含名称、方向、类别和数据类型
- **Link**: 连接两个引脚的连线，定义数据流或执行流
- **Exec_Flow**: 执行流连线，控制蓝图的执行顺序
- **Data_Flow**: 数据流连线，在节点间传递数据值
- **GetContentTree_Tool**: 新增 MCP 工具，用于获取项目资产的递归树结构
- **Asset_Tree**: 包含文件夹和资产的层级结构
- **Error_Code**: 明确的错误标识符，用于区分不同的错误状态

## Requirements

### Requirement 1: 完整的节点数据提取

**User Story:** 作为 AI 助手，我需要获取完整的蓝图节点数据，以便理解每个节点的功能和属性

#### Acceptance Criteria

1. WHEN ExtractBlueprint_Tool 被调用时，THE Blueprint_Analyzer SHALL 为每个节点返回唯一的节点 ID
2. WHEN ExtractBlueprint_Tool 被调用时，THE Blueprint_Analyzer SHALL 为每个节点返回标题、类名和位置坐标
3. FOR ALL 返回的节点数据，节点 ID SHALL 在同一蓝图内保持唯一性
4. WHEN 节点包含中文字符时，THE Blueprint_Analyzer SHALL 使用 UTF-8 编码返回正确的中文文本

### Requirement 2: 引脚信息提取

**User Story:** 作为 AI 助手，我需要获取节点的引脚信息，以便理解节点的输入输出接口

#### Acceptance Criteria

1. WHEN ExtractBlueprint_Tool 被调用时，THE Blueprint_Analyzer SHALL 为每个节点返回所有引脚的列表
2. FOR ALL 引脚，THE Blueprint_Analyzer SHALL 返回引脚 ID、名称、方向（input/output）、类别（exec/data）和数据类型
3. WHEN 引脚名称包含中文字符时，THE Blueprint_Analyzer SHALL 使用 UTF-8 编码返回正确的中文文本
4. FOR ALL 引脚，引脚 ID SHALL 在同一节点内保持唯一性

### Requirement 3: 连线关系提取

**User Story:** 作为 AI 助手，我需要获取节点间的连线信息，以便理解蓝图的执行流程和数据流动

#### Acceptance Criteria

1. WHEN ExtractBlueprint_Tool 被调用时，THE Blueprint_Analyzer SHALL 返回所有连线的列表
2. FOR ALL 连线，THE Blueprint_Analyzer SHALL 返回源节点 ID、源引脚 ID、目标节点 ID、目标引脚 ID 和连线类型（exec/data）
3. FOR ALL 连线，THE Blueprint_Analyzer SHALL 确保引用的节点 ID 和引脚 ID 在返回的数据中存在
4. WHEN 连线为执行流时，THE Blueprint_Analyzer SHALL 将连线类型标记为 "exec"
5. WHEN 连线为数据流时，THE Blueprint_Analyzer SHALL 将连线类型标记为 "data"

### Requirement 4: 递归资产树获取

**User Story:** 作为 AI 助手，我需要一次性获取完整的项目资产树结构，以便快速定位资产位置

#### Acceptance Criteria

1. THE MCP_Bridge SHALL 提供 GetContentTree_Tool 工具
2. WHEN GetContentTree_Tool 被调用时，THE MCP_Bridge SHALL 返回项目 Content 目录的递归树结构
3. FOR ALL 树节点，THE MCP_Bridge SHALL 返回节点名称、类型（folder/asset）和子节点列表
4. WHEN 树节点为资产时，THE MCP_Bridge SHALL 返回资产的完整路径和资产类型（Blueprint/Texture/Material 等）
5. FOR ALL 返回的资产树，THE MCP_Bridge SHALL 在单次调用中返回完整的层级结构

### Requirement 5: 精确的错误处理

**User Story:** 作为 AI 助手，我需要获取明确的错误信息，以便向用户提供准确的故障排除指导

#### Acceptance Criteria

1. WHEN Unreal Engine 未启动时，THE MCP_Bridge SHALL 返回错误码 "UE_NOT_RUNNING"
2. WHEN Unreal Engine 已启动但项目未打开时，THE MCP_Bridge SHALL 返回错误码 "PROJECT_NOT_LOADED"
3. WHEN 请求的蓝图资产不存在时，THE MCP_Bridge SHALL 返回错误码 "ASSET_NOT_FOUND"
4. FOR ALL 错误响应，THE MCP_Bridge SHALL 包含错误码和人类可读的错误描述
5. WHEN 蓝图数据提取失败时，THE MCP_Bridge SHALL 返回错误码 "EXTRACTION_FAILED" 和失败原因

### Requirement 6: 数据格式往返验证

**User Story:** 作为开发者，我需要确保蓝图数据的序列化和反序列化保持一致性，以便数据传输的可靠性

#### Acceptance Criteria

1. THE Blueprint_Analyzer SHALL 将蓝图数据序列化为 JSON 格式
2. THE MCP_Bridge SHALL 解析 Blueprint_Analyzer 返回的 JSON 数据
3. FOR ALL 有效的蓝图数据，序列化后再反序列化 SHALL 产生等价的数据结构（round-trip property）
4. WHEN JSON 解析失败时，THE MCP_Bridge SHALL 返回错误码 "INVALID_JSON" 和解析错误详情

### Requirement 7: 执行流和数据流区分

**User Story:** 作为 AI 助手，我需要区分执行流和数据流连线，以便理解蓝图的控制逻辑和数据传递

#### Acceptance Criteria

1. FOR ALL 执行流引脚，THE Blueprint_Analyzer SHALL 将引脚类别设置为 "exec"
2. FOR ALL 数据流引脚，THE Blueprint_Analyzer SHALL 将引脚类别设置为 "data" 并包含数据类型信息
3. WHEN AI 助手分析蓝图时，THE AI_Assistant SHALL 能够基于连线类型区分执行顺序和数据依赖
4. FOR ALL 连线，连线类型 SHALL 与源引脚和目标引脚的类别保持一致

### Requirement 8: Widget 蓝图支持

**User Story:** 作为 AI 助手，我需要分析 Widget 蓝图的特殊结构，以便理解 UI 逻辑

#### Acceptance Criteria

1. THE Blueprint_Analyzer SHALL 支持 ExtractWidgetBlueprint_Tool 工具
2. WHEN ExtractWidgetBlueprint_Tool 被调用时，THE Blueprint_Analyzer SHALL 返回 Widget 层级结构
3. FOR ALL Widget 节点，THE Blueprint_Analyzer SHALL 返回 Widget 类型、名称和父子关系
4. WHEN Widget 蓝图包含事件图表时，THE Blueprint_Analyzer SHALL 使用与普通蓝图相同的格式返回图表数据
