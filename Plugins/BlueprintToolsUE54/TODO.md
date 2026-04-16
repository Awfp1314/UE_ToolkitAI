# Blueprint Tools UE5.4 - 实现计划

## 阶段 1：核心提取功能 (ExtractBlueprint)

### 1.1 基础蓝图元数据

- [ ] 提取类名、父类、路径
- [ ] 提取蓝图类型（普通、接口、宏库）
- [ ] 提取蓝图标志和设置
- **参考文件**: `BlueprintExtractor/Private/Extractors/BlueprintExtractor.cpp`

### 1.2 变量提取

- [ ] 提取成员变量（名称、类型、默认值）
- [ ] 提取变量元数据（分类、提示、复制）
- [ ] 提取变量标志（生成时暴露、实例可编辑等）
- [ ] 处理复杂类型（数组、映射、集合、结构体）
- **参考文件**: `BlueprintExtractor/Private/Extractors/BlueprintExtractor.cpp::ExtractVariables()`

### 1.3 组件提取

- [ ] 提取组件层级结构
- [ ] 提取组件属性
- [ ] 提取组件变换
- [ ] 处理场景组件 vs Actor 组件
- **参考文件**: `BlueprintExtractor/Private/Extractors/BlueprintExtractor.cpp::ExtractComponents()`

### 1.4 函数提取（浅层）

- [ ] 提取函数签名（名称、输入、输出）
- [ ] 提取函数元数据（分类、关键字、提示）
- [ ] 提取函数标志（纯函数、常量、静态等）
- **参考文件**: `BlueprintExtractor/Private/Extractors/BlueprintExtractor.cpp::ExtractFunctions()`

### 1.5 图表提取（完整）

- [ ] 提取事件图表
- [ ] 提取函数图表
- [ ] 提取构造脚本
- [ ] 提取节点和连接
- [ ] 处理按名称过滤图表
- **参考文件**: `BlueprintExtractor/Private/Extractors/GraphExtractor.cpp`

### 1.6 类默认值 (CDO)

- [ ] 提取 CDO 属性值
- [ ] 与父类默认值比较
- [ ] 只包含修改过的属性
- **参考文件**: `BlueprintExtractor/Private/PropertySerializer.cpp`

## 阶段 2：蓝图创建 (CreateBlueprint)

### 2.1 基础蓝图创建

- [x] 从父类创建蓝图（已实现）
- [ ] 设置蓝图元数据
- [ ] 处理不同的蓝图类型
- **参考文件**: `BlueprintExtractor/Private/Authoring/BlueprintAuthoring.cpp::CreateBlueprint()`

### 2.2 解析 PayloadJson

- [ ] 从 JSON 解析变量数组
- [ ] 从 JSON 解析函数数组
- [ ] 从 JSON 解析组件数组
- [ ] 验证 JSON 结构
- **参考文件**: `BlueprintExtractor/Private/Authoring/AuthoringHelpers.cpp::ParsePayload()`

### 2.3 创建初始成员

- [ ] 从 payload 创建变量
- [ ] 从 payload 创建函数签名
- [ ] 从 payload 创建组件
- [ ] 设置默认值
- **参考文件**: `BlueprintExtractor/Private/Authoring/BlueprintAuthoring.cpp`

## 阶段 3：蓝图修改 (ModifyBlueprintMembers)

### 3.1 变量操作

- [ ] **add_variable**: 添加新成员变量
  - 从 JSON 解析变量类型
  - 设置默认值
  - 设置元数据（分类、提示、标志）
  - **参考文件**: `BlueprintExtractor/Private/Authoring/BlueprintAuthoring.cpp::AddVariable()`
- [ ] **remove_variable**: 删除现有变量
  - 按名称查找变量
  - 删除所有引用（如果有）
  - **参考文件**: `BlueprintExtractor/Private/Authoring/BlueprintAuthoring.cpp::RemoveVariable()`
- [ ] **modify_variable**: 修改现有变量
  - 更新默认值
  - 更新元数据
  - 更新标志
  - **参考文件**: `BlueprintExtractor/Private/Authoring/BlueprintAuthoring.cpp::ModifyVariable()`

### 3.2 函数操作

- [ ] **add_function**: 添加新函数
  - 创建函数图表
  - 添加输入/输出参数
  - 设置函数元数据
  - **参考文件**: `BlueprintExtractor/Private/Authoring/BlueprintAuthoring.cpp::AddFunction()`
- [ ] **remove_function**: 删除现有函数
  - 删除函数图表
  - 删除所有调用点（如果有）
  - **参考文件**: `BlueprintExtractor/Private/Authoring/BlueprintAuthoring.cpp::RemoveFunction()`
- [ ] **modify_function**: 修改函数签名
  - 更新参数
  - 更新元数据
  - **参考文件**: `BlueprintExtractor/Private/Authoring/BlueprintAuthoring.cpp::ModifyFunction()`

### 3.3 组件操作

- [ ] **add_component**: 添加新组件
  - 创建组件实例
  - 设置组件属性
  - 附加到层级结构
  - **参考文件**: `BlueprintExtractor/Private/Authoring/BlueprintAuthoring.cpp::AddComponent()`
- [ ] **remove_component**: 删除现有组件
  - 从层级结构中移除
  - 清理引用
  - **参考文件**: `BlueprintExtractor/Private/Authoring/BlueprintAuthoring.cpp::RemoveComponent()`
- [ ] **modify_component**: 修改组件属性
  - 更新属性
  - 更新变换
  - **参考文件**: `BlueprintExtractor/Private/Authoring/BlueprintAuthoring.cpp::ModifyComponent()`

## 阶段 4：类型系统与辅助工具

### 4.1 类型解析

- [ ] 解析基础类型（int, float, bool, string, name, text）
- [ ] 解析对象引用
- [ ] 解析结构体类型
- [ ] 解析枚举类型
- [ ] 解析容器类型（array, set, map）
- **参考文件**: `BlueprintExtractor/Private/Authoring/AuthoringHelpers.cpp::ParsePinType()`

### 4.2 属性序列化

- [ ] 将属性值序列化为 JSON
- [ ] 将 JSON 反序列化为属性值
- [ ] 处理嵌套结构
- [ ] 处理资产引用
- **参考文件**: `BlueprintExtractor/Private/PropertySerializer.cpp`

### 4.3 验证

- [ ] 验证变量名（无重复、有效标识符）
- [ ] 验证类型（存在且可访问）
- [ ] 验证默认值（匹配类型）
- [ ] 验证组件层级结构
- **参考文件**: `BlueprintExtractor/Private/Authoring/AuthoringHelpers.cpp::ValidatePayload()`

## 阶段 5：编译与错误处理

### 5.1 蓝图编译

- [x] 基础编译（已实现）
- [ ] 收集编译错误
- [ ] 收集编译警告
- [ ] 格式化错误消息为 JSON 输出
- **参考文件**: `BlueprintExtractor/Private/Extractors/BlueprintExtractor.cpp::CompileBlueprint()`

### 5.2 错误响应格式

- [ ] 标准化错误 JSON 格式
- [ ] 包含错误位置（节点、引脚、行）
- [ ] 包含错误严重性
- [ ] 包含建议修复
- **参考文件**: `BlueprintExtractor/Private/BlueprintExtractorSubsystem.cpp`

## 阶段 6：资产管理

### 6.1 资产搜索与列表

- [x] 基础搜索（已实现）
- [x] 基础列表（已实现）
- [ ] 添加更多过滤选项
- [ ] 添加排序选项
- [ ] 添加分页支持

### 6.2 资产保存

- [x] 基础保存（已实现）
- [ ] 优雅处理保存失败
- [ ] 保存前标记包为脏
- [ ] 保存前验证资产

## 阶段 7：测试与验证

### 7.1 单元测试

- [ ] 测试所有类型的变量创建
- [ ] 测试函数创建
- [ ] 测试组件创建
- [ ] 测试提取准确性

### 7.2 集成测试

- [ ] 测试完整工作流：创建 → 修改 → 编译 → 保存
- [ ] 测试错误处理
- [ ] 测试复杂蓝图
- [ ] 测试不同父类

## 实现优先级

### 高优先级（核心功能）

1. 阶段 3.1: 变量操作（添加、删除、修改）
2. 阶段 4.1: 类型解析
3. 阶段 1.2: 变量提取
4. 阶段 2.2 & 2.3: PayloadJson 解析和初始成员创建

### 中优先级（扩展功能）

5. 阶段 3.2: 函数操作
6. 阶段 3.3: 组件操作
7. 阶段 1.3: 组件提取
8. 阶段 1.4: 函数提取

### 低优先级（高级功能）

9. 阶段 1.5: 图表提取（完整）
10. 阶段 5: 增强的编译和错误处理
11. 阶段 7: 测试

## BlueprintExtractor 中的关键参考文件

### 必读（核心实现）

1. `Private/Authoring/BlueprintAuthoring.cpp` - 所有创建和修改操作
2. `Private/Authoring/AuthoringHelpers.cpp` - 类型解析、验证
3. `Private/Extractors/BlueprintExtractor.cpp` - 提取逻辑
4. `Private/PropertySerializer.cpp` - 属性序列化

### 支持文件

5. `Private/Extractors/GraphExtractor.cpp` - 图表提取
6. `Private/BlueprintExtractorSubsystem.cpp` - API 入口点
7. `Public/BlueprintExtractorTypes.h` - 类型定义

## 重要注意事项

- 始终使用官方 UE 蓝图 API（FBlueprintEditorUtils, FKismetEditorUtilities）
- 永远不要直接修改 Blueprint->NewVariables 数组
- 修改后始终编译
- 保存前始终标记包为脏
- 使用 FBlueprintEditorUtils::AddMemberVariable() 而不是手动操作数组
- 参考 BlueprintExtractor 实现 - 它经过测试并使用官方 API

## 下一步行动

建议从 **阶段 3.1 的 add_variable** 开始实现，这是最常用的功能，实现后可以立即测试并验证整个架构。
