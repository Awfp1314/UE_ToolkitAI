# Blueprint Extractor 项目深度分析

基于对 [SunGrow/ue-blueprint-extractor](https://github.com/SunGrow/ue-blueprint-extractor) 的源码分析

---

## 📐 整体架构

### 三层架构设计

```
┌─────────────────────────────────────────────────────────────┐
│                    MCP 客户端 (Claude/Codex)                 │
└────────────────────────┬────────────────────────────────────┘
                         │ MCP Protocol (stdio)
┌────────────────────────▼────────────────────────────────────┐
│              MCP 服务器 (Node.js/TypeScript)                 │
│  - 112 个工具函数                                            │
│  - 38 个资源                                                 │
│  - 12 个提示模板                                             │
└────────────────────────┬────────────────────────────────────┘
                         │ HTTP + JSON
┌────────────────────────▼────────────────────────────────────┐
│         UE Remote Control API (HTTP Server)                 │
│         监听端口: 30010                                      │
└────────────────────────┬────────────────────────────────────┘
                         │ C++ Function Calls
┌────────────────────────▼────────────────────────────────────┐
│      BlueprintExtractorSubsystem (UEditorSubsystem)         │
│      - 所有提取和创建功能的入口                              │
└────────────────────────┬────────────────────────────────────┘
                         │
┌────────────────────────▼────────────────────────────────────┐
│              专门的提取器 (Extractors)                       │
│  - GraphExtractor: 蓝图图表                                 │
│  - NodeExtractors: 各种节点类型                             │
│  - WidgetTreeExtractor: UI 组件树                           │
│  - MaterialGraphExtractor: 材质图表                         │
│  - StateTreeExtractor: 状态树                               │
│  - 等等...                                                  │
└─────────────────────────────────────────────────────────────┘
```

---

## 🔑 核心设计理念

### 1. **使用 Remote Control API 而非直接 C++ 调用**

**优势**：

- ✅ 解耦：MCP 服务器和 UE 插件独立运行
- ✅ 跨进程：可以从外部控制 UE 编辑器
- ✅ 语言无关：MCP 服务器用 TypeScript，插件用 C++
- ✅ 热重载：修改 MCP 服务器无需重启 UE

**实现**：

```typescript
// MCP 服务器通过 HTTP 调用 UE
const response = await fetch("http://127.0.0.1:30010/remote/object/call", {
  method: "POST",
  body: JSON.stringify({
    objectPath:
      "/Script/BlueprintExtractor.Default__BlueprintExtractorSubsystem",
    functionName: "ExtractBlueprint",
    parameters: { AssetPath: "/Game/MyBlueprint", Scope: "Full" },
  }),
});
```

```cpp
// UE 插件通过 UEditorSubsystem 暴露函数
UFUNCTION(BlueprintCallable, Category="Blueprint Extractor")
FString ExtractBlueprint(const FString& AssetPath, const FString& Scope);
```

### 2. **模块化的提取器架构**

每种资产类型都有专门的提取器：

```cpp
// 提取器基类
struct FExtractorBase {
    virtual TSharedPtr<FJsonObject> Extract(UObject* Asset) = 0;
};

// 蓝图图表提取器
struct FGraphExtractor {
    static TSharedPtr<FJsonObject> ExtractGraph(const UEdGraph* Graph);
    static TSharedPtr<FJsonObject> ExtractNode(const UK2Node* Node);
    static TSharedPtr<FJsonObject> ExtractPin(const UEdGraphPin* Pin);
};

// 节点提取器注册表
class FNodeExtractorRegistry {
    TMap<UClass*, TUniquePtr<FNodeExtractorBase>> Extractors;

    void RegisterExtractor(UClass* NodeClass, TUniquePtr<FNodeExtractorBase> Extractor);
    const FNodeExtractorBase* FindExtractor(const UK2Node* Node);
};
```

**节点类型专门提取器**：

- `NodeExtractor_CallFunction`: 函数调用节点
- `NodeExtractor_Event`: 事件节点
- `NodeExtractor_FlowControl`: 流程控制节点
- `NodeExtractor_Variable`: 变量节点
- `NodeExtractor_Timeline`: 时间轴节点
- `NodeExtractor_Macro`: 宏节点

### 3. **分层的 JSON 输出**

```json
{
  "blueprint": {
    "name": "BP_Character",
    "parentClass": "Character",
    "graphs": [
      {
        "graphName": "EventGraph",
        "graphType": "EventGraph",
        "nodes": [
          {
            "nodeGuid": "...",
            "nodeClass": "K2Node_Event",
            "nodeTitle": "Event BeginPlay",
            "extractorType": "Event",
            "typeSpecificData": {
              "eventName": "BeginPlay",
              "isOverride": true
            },
            "pins": [
              {
                "pinName": "then",
                "direction": "Output",
                "type": { "category": "exec" },
                "connections": [
                  { "nodeGuid": "...", "pinName": "execute" }
                ]
              }
            ]
          }
        ]
      }
    ],
    "variables": [...],
    "components": [...]
  }
}
```

---

## 💡 关键技术亮点

### 1. **智能的 Scope 控制**

```cpp
enum class EBlueprintExtractionScope {
    Minimal,    // 只提取基本信息
    Compact,    // 提取主要信息（默认）
    Full        // 提取所有信息
};
```

**对比我们的实现**：

- 我们：只有一种导出模式
- 他们：三种模式，可根据需求选择

### 2. **GraphFilter 功能**

```cpp
// 只提取指定的图表
FString ExtractBlueprint(
    const FString& AssetPath,
    const FString& Scope,
    const FString& GraphFilter,  // "EventGraph,MyFunction"
    const bool bIncludeClassDefaults
);
```

**优势**：

- 减少不必要的数据传输
- 节省 token
- 提高响应速度

### 3. **类型特定数据提取**

```cpp
// 基类
class FNodeExtractorBase {
public:
    virtual FString GetNodeTypeName() const = 0;
    virtual TSharedPtr<FJsonObject> ExtractTypeSpecificData(const UK2Node* Node) const = 0;
};

// 函数调用节点提取器
class FNodeExtractor_CallFunction : public FNodeExtractorBase {
public:
    virtual TSharedPtr<FJsonObject> ExtractTypeSpecificData(const UK2Node* Node) const override {
        const UK2Node_CallFunction* CallNode = Cast<UK2Node_CallFunction>(Node);
        TSharedPtr<FJsonObject> Data = MakeShared<FJsonObject>();

        Data->SetStringField("functionName", CallNode->FunctionReference.GetMemberName().ToString());
        Data->SetStringField("targetClass", CallNode->FunctionReference.GetMemberParentClass()->GetName());
        Data->SetBoolField("isSelfContext", CallNode->FunctionReference.IsSelfContext());

        return Data;
    }
};
```

### 4. **Pin 类型序列化**

```cpp
TSharedPtr<FJsonObject> FBlueprintJsonSchema::SerializePinType(const FEdGraphPinType& PinType) {
    TSharedPtr<FJsonObject> TypeObj = MakeShared<FJsonObject>();

    TypeObj->SetStringField("category", PinType.PinCategory.ToString());

    if (PinType.PinSubCategoryObject.IsValid()) {
        TypeObj->SetStringField("subCategory", PinType.PinSubCategoryObject->GetPathName());
    }

    // 容器类型
    if (PinType.ContainerType == EPinContainerType::Array) {
        TypeObj->SetStringField("container", "Array");
    } else if (PinType.ContainerType == EPinContainerType::Set) {
        TypeObj->SetStringField("container", "Set");
    } else if (PinType.ContainerType == EPinContainerType::Map) {
        TypeObj->SetStringField("container", "Map");
    }

    TypeObj->SetBoolField("isReference", PinType.bIsReference);
    TypeObj->SetBoolField("isConst", PinType.bIsConst);

    return TypeObj;
}
```

### 5. **连接信息的优化表示**

```cpp
// 我们的实现：存储完整的 Pin ID
{
  "linkedTo": [
    {
      "node_guid": "...",
      "pin_id": "...",
      "pin_name": "..."
    }
  ]
}

// blueprint-extractor：只存储必要信息
{
  "connections": [
    {
      "nodeGuid": "...",
      "pinName": "then"
    }
  ]
}
```

**优势**：

- 更简洁
- 更易读
- 节省 token

---

## 🎯 与我们插件的对比

| 特性             | 我们的插件       | blueprint-extractor                                           |
| ---------------- | ---------------- | ------------------------------------------------------------- |
| **架构**         | Python RPC + C++ | MCP + Remote Control + C++                                    |
| **通信方式**     | Socket (9998)    | HTTP (30010)                                                  |
| **协议**         | 自定义 JSON-RPC  | MCP (Model Context Protocol)                                  |
| **提取器数量**   | 1 个通用提取器   | 20+ 个专门提取器                                              |
| **节点类型支持** | 通用处理         | 7 个专门的节点提取器                                          |
| **Scope 控制**   | ❌ 无            | ✅ 3 种模式                                                   |
| **GraphFilter**  | ❌ 无            | ✅ 支持                                                       |
| **资产类型**     | Blueprint        | Blueprint + Widget + Material + StateTree + BehaviorTree + 等 |
| **创建功能**     | ❌ 只读          | ✅ 完整的 CRUD                                                |
| **验证功能**     | ✅ 基础          | ✅ 高级（包含视觉验证）                                       |
| **UE 版本**      | 4.26-5.6         | 5.6-5.7                                                       |
| **学习成本**     | 低               | 高                                                            |
| **功能完整度**   | ⭐⭐⭐           | ⭐⭐⭐⭐⭐                                                    |

---

## 📊 JSON 输出对比

### 我们的输出（简化版）

```json
{
  "name": "BP_Character",
  "parent_class": "Character",
  "graphs": [
    {
      "name": "EventGraph",
      "node_count": 10,
      "nodes": [
        {
          "guid": "...",
          "class": "K2Node_Event",
          "title": "Event BeginPlay",
          "pos": [100, 200],
          "pins": [
            {
              "name": "then",
              "type": "exec",
              "dir": "out",
              "links": ["..."]
            }
          ]
        }
      ]
    }
  ]
}
```

### blueprint-extractor 的输出

```json
{
  "name": "BP_Character",
  "parentClass": "Character",
  "blueprintType": "Normal",
  "graphs": [
    {
      "graphName": "EventGraph",
      "graphGuid": "...",
      "graphType": "EventGraph",
      "nodes": [
        {
          "nodeGuid": "...",
          "nodeClass": "K2Node_Event",
          "nodeTitle": "Event BeginPlay",
          "nodeComment": "",
          "posX": 100,
          "posY": 200,
          "extractorType": "Event",
          "typeSpecificData": {
            "eventName": "BeginPlay",
            "isOverride": true,
            "functionFlags": ["BlueprintEvent"]
          },
          "pins": [
            {
              "pinName": "then",
              "pinId": "...",
              "direction": "Output",
              "type": {
                "category": "exec",
                "container": null,
                "isReference": false
              },
              "connections": [
                {
                  "nodeGuid": "...",
                  "pinName": "execute"
                }
              ]
            }
          ]
        }
      ]
    }
  ],
  "variables": [...],
  "components": [...]
}
```

**差异分析**：

1. **更详细的类型信息**：`type` 对象包含更多细节
2. **类型特定数据**：`typeSpecificData` 提供节点特有信息
3. **更清晰的命名**：`posX/posY` vs `pos: [x, y]`
4. **Graph GUID**：每个图表都有唯一标识
5. **函数元数据**：包含函数标志、访问修饰符等

---

## 🚀 可借鉴的优化点

### 1. **立即可实施**（1-2 天）

#### A. 添加 Scope 控制

```cpp
// 在 BlueprintAIToolsLibrary.h 中添加
enum class EExportScope : uint8 {
    Minimal,    // 只有节点类型和连接
    Compact,    // 添加位置和基本属性（默认）
    Full        // 包含所有信息
};

UFUNCTION(BlueprintCallable, Category = "Blueprint AI Tools")
static FString ExportBlueprintSummary(
    UBlueprint* Blueprint,
    EExportScope Scope = EExportScope::Compact,
    bool bIncludePinDetails = true
);
```

#### B. 添加 GraphFilter

```cpp
UFUNCTION(BlueprintCallable, Category = "Blueprint AI Tools")
static FString ExportBlueprintSummary(
    UBlueprint* Blueprint,
    const TArray<FString>& GraphFilter = {},  // 空数组 = 所有图表
    bool bIncludePinDetails = true
);
```

#### C. 优化 JSON 结构

```cpp
// 当前：
{
  "pos": [100, 200],
  "inputs": 2,
  "outputs": 1
}

// 优化后：
{
  "posX": 100,
  "posY": 200,
  "pins": {
    "inputs": 2,
    "outputs": 1
  }
}
```

### 2. **中期优化**（1-2 周）

#### A. 实现节点提取器注册表

```cpp
// NodeExtractorRegistry.h
class FNodeExtractorRegistry {
public:
    static FNodeExtractorRegistry& Get();

    void RegisterExtractor(UClass* NodeClass, TSharedPtr<INodeExtractor> Extractor);
    TSharedPtr<INodeExtractor> FindExtractor(const UK2Node* Node) const;

private:
    TMap<UClass*, TSharedPtr<INodeExtractor>> Extractors;
};

// INodeExtractor.h
class INodeExtractor {
public:
    virtual ~INodeExtractor() = default;
    virtual FString GetNodeTypeName() const = 0;
    virtual TSharedPtr<FJsonObject> ExtractTypeSpecificData(const UK2Node* Node) const = 0;
};
```

#### B. 实现专门的节点提取器

```cpp
// CallFunctionNodeExtractor.cpp
class FCallFunctionNodeExtractor : public INodeExtractor {
public:
    virtual FString GetNodeTypeName() const override {
        return TEXT("CallFunction");
    }

    virtual TSharedPtr<FJsonObject> ExtractTypeSpecificData(const UK2Node* Node) const override {
        const UK2Node_CallFunction* CallNode = Cast<UK2Node_CallFunction>(Node);
        if (!CallNode) return nullptr;

        TSharedPtr<FJsonObject> Data = MakeShared<FJsonObject>();
        Data->SetStringField(TEXT("functionName"),
            CallNode->FunctionReference.GetMemberName().ToString());
        Data->SetBoolField(TEXT("isSelfContext"),
            CallNode->FunctionReference.IsSelfContext());

        return Data;
    }
};
```

### 3. **长期规划**（1-2 月）

#### A. 迁移到 Remote Control API

**优势**：

- 解耦 Python 和 C++
- 支持外部工具直接调用
- 更好的错误处理
- 支持异步操作

**实现**：

```cpp
// 在 BlueprintExtractorSubsystem.h 中
UCLASS()
class UBlueprintExtractorSubsystem : public UEditorSubsystem {
    GENERATED_BODY()

public:
    // 通过 Remote Control 暴露
    UFUNCTION(BlueprintCallable, Category="Blueprint Extractor")
    FString ExtractBlueprint(const FString& AssetPath, const FString& Scope);
};
```

#### B. 实现 MCP 协议支持

**优势**：

- 标准化的 AI 工具集成
- 支持 Claude Code、Codex 等
- 丰富的工具生态

---

## 📝 总结

### blueprint-extractor 的核心优势

1. **架构设计**：
   - 使用 Remote Control API 实现解耦
   - MCP 协议标准化
   - 模块化的提取器架构

2. **功能完整性**：
   - 支持 20+ 种资产类型
   - 完整的 CRUD 操作
   - 视觉验证功能

3. **优化细节**：
   - Scope 控制节省 token
   - GraphFilter 减少数据传输
   - 类型特定数据提取

4. **可扩展性**：
   - 节点提取器注册表
   - 资源和提示模板系统
   - 工作流作用域管理

### 我们可以学习的点

**短期**（立即实施）：

- ✅ 添加 Scope 控制（Minimal/Compact/Full）
- ✅ 添加 GraphFilter 功能
- ✅ 优化 JSON 输出结构

**中期**（1-2 周）：

- ✅ 实现节点提取器注册表
- ✅ 添加专门的节点提取器
- ✅ 支持更多资产类型（Material、Widget）

**长期**（1-2 月）：

- ⚠️ 考虑迁移到 Remote Control API
- ⚠️ 考虑支持 MCP 协议
- ⚠️ 构建完整的工具生态

---

**作者**：HUTAO  
**日期**：2025-01-XX  
**基于**：blueprint-extractor v2.1.1
