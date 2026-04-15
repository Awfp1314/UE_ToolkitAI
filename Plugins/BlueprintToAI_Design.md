# BlueprintToAI 插件设计文档

> 专注于蓝图的读取、创建和修改，让 AI 能够理解和生成蓝图

---

## 🎯 核心目标

- ✅ AI 可以读取和理解蓝图结构
- ✅ AI 可以根据需求创建新蓝图
- ✅ AI 可以修改现有蓝图
- ❌ 不做 Widget、材质、动画等其他资产（后续扩展）

---

## 📐 架构设计

### 三层架构

```
┌─────────────────────────────────────────────────────────┐
│              Python 应用 (UE Toolkit)                    │
│  - AI 助手模块                                           │
│  - BlueprintTool (新增)                                  │
│  - 工具注册表                                            │
└────────────────────┬────────────────────────────────────┘
                     │ HTTP (Remote Control API)
┌────────────────────▼────────────────────────────────────┐
│         UE Remote Control API (HTTP Server)             │
│         监听端口: 30010                                  │
└────────────────────┬────────────────────────────────────┘
                     │ C++ Function Calls
┌────────────────────▼────────────────────────────────────┐
│      BlueprintToAISubsystem (UEditorSubsystem)          │
│      - 蓝图提取                                          │
│      - 蓝图创建                                          │
│      - 蓝图修改                                          │
└─────────────────────────────────────────────────────────┘
```

### 为什么选择 Remote Control API？

对比现有的 Socket RPC 方案：

| 特性     | Socket RPC (9998) | Remote Control API (30010) |
| -------- | ----------------- | -------------------------- |
| 协议     | 自定义 JSON-RPC   | HTTP + JSON (UE 官方)      |
| 稳定性   | 需要自己维护      | UE 官方维护                |
| 功能     | 只读              | 读写都支持                 |
| 调试     | 需要自定义工具    | 可以用 Postman/curl        |
| 扩展性   | 需要修改协议      | 标准 HTTP，易扩展          |
| 学习成本 | 高                | 低（标准 HTTP）            |

**结论**：使用 Remote Control API 更简单、更稳定、更易维护。

---

## 🔧 核心功能设计

### 0. 获取激活的蓝图（新增）

**GetActiveBlueprint**

```json
{
  // 无需参数
}
```

**输出**：

```json
{
  "success": true,
  "data": {
    "assetPath": "/Game/Blueprints/BP_Character",
    "name": "BP_Character",
    "parentClass": "/Script/Engine.Character"
  }
}
```

**ExtractActiveBlueprint**（便捷函数）

```json
{
  "Scope": "Compact" // 可选
}
```

直接返回当前激活蓝图的完整结构，相当于 `GetActiveBlueprint` + `ExtractBlueprint` 的组合。

### 1. 蓝图读取（ExtractBlueprint）

**输入**：

```json
{
  "AssetPath": "/Game/Blueprints/BP_Character",
  "Scope": "Compact" // Minimal | Compact | Full
}
```

**输出**：

```json
{
  "success": true,
  "blueprint": {
    "name": "BP_Character",
    "parentClass": "/Script/Engine.Character",
    "graphs": [
      {
        "graphName": "EventGraph",
        "nodes": [
          {
            "nodeGuid": "xxx",
            "nodeClass": "K2Node_Event",
            "nodeTitle": "Event BeginPlay",
            "posX": 100,
            "posY": 200,
            "pins": [...]
          }
        ]
      }
    ],
    "variables": [...],
    "components": [...]
  }
}
```

**Scope 说明**：

- `Minimal`：只有节点类型和连接（最省 token）
- `Compact`：添加位置和基本属性（默认，平衡）
- `Full`：包含所有信息（调试用）

### 2. 蓝图创建（CreateBlueprint）

**方式 A：基础创建**

```json
{
  "AssetPath": "/Game/Blueprints/BP_MyActor",
  "ParentClass": "/Script/Engine.Actor",
  "Variables": [
    {
      "name": "Health",
      "type": "float",
      "defaultValue": 100.0
    }
  ],
  "Components": [
    {
      "name": "Mesh",
      "class": "StaticMeshComponent"
    }
  ]
}
```

**方式 B：DSL 创建（推荐）**

```json
{
  "AssetPath": "/Game/Blueprints/BP_MyActor",
  "ParentClass": "/Script/Engine.Actor",
  "GraphDSL": "Event BeginPlay -> Print(\"Hello World\")"
}
```

### 3. 蓝图修改（ModifyBlueprint）

**操作类型**：

- `add_variable` - 添加变量
- `add_component` - 添加组件
- `add_function` - 添加函数
- `modify_graph` - 修改图表（支持 DSL）
- `reparent` - 更改父类

**示例：添加变量**

```json
{
  "AssetPath": "/Game/Blueprints/BP_MyActor",
  "Operation": "add_variable",
  "Payload": {
    "name": "Speed",
    "type": "float",
    "defaultValue": 600.0
  }
}
```

**示例：修改图表（DSL）**

```json
{
  "AssetPath": "/Game/Blueprints/BP_MyActor",
  "Operation": "modify_graph",
  "Payload": {
    "graphName": "EventGraph",
    "dsl": "Event Tick -> GetVelocity as Vel -> Print(Vel)"
  }
}
```

### 4. 保存蓝图（SaveBlueprint）

```json
{
  "AssetPaths": [
    "/Game/Blueprints/BP_MyActor",
    "/Game/Blueprints/BP_MyCharacter"
  ]
}
```

**注意**：所有修改操作不会自动保存，必须显式调用 `SaveBlueprint`。

---

## 🎨 DSL 语法设计

### 基础语法

```
# 事件节点
Event BeginPlay
Event Tick

# 函数调用
FunctionName()
FunctionName(arg1, arg2)

# 带目标的调用
Target.FunctionName()
PC.GetPawn()

# 变量
VariableName          # Get
Set VariableName = 100  # Set

# 类型转换
CastTo(APlayerController)

# 别名（用于后续引用）
GetPlayerController as PC

# 连接（->）
Event BeginPlay -> GetPlayerController -> CastTo(APlayerController) as PC

# 分支
Health > 0 ? Branch
  True -> Print("Alive")
  False -> Print("Dead")
```

### 完整示例

```
EventGraph:
  Event BeginPlay -> GetPlayerController -> CastTo(APlayerController) as PC
  PC.GetPawn -> CastTo(ACharacter) as MyChar
  MyChar.GetVelocity as Vel
  Print(Vel)

CustomFunction:
  Event Tick -> GetActorLocation as Loc
  Loc.Z > 100 ? Branch
    True -> Print("High")
    False -> Print("Low")
```

---

## 🔌 Python 集成

### 新增工具类

```python
# modules/ai_assistant/logic/blueprint_tool.py

class BlueprintTool:
    """蓝图操作工具"""

    def __init__(self, remote_control_url="http://127.0.0.1:30010"):
        self.base_url = remote_control_url
        self.subsystem_path = "/Script/BlueprintToAI.Default__BlueprintToAISubsystem"

    def extract_blueprint(self, asset_path: str, scope: str = "Compact") -> dict:
        """提取蓝图结构"""
        return self._call_subsystem("ExtractBlueprint", {
            "AssetPath": asset_path,
            "Scope": scope
        })

    def create_blueprint(self, asset_path: str, parent_class: str,
                        graph_dsl: str = None, **kwargs) -> dict:
        """创建蓝图"""
        payload = {
            "AssetPath": asset_path,
            "ParentClass": parent_class
        }
        if graph_dsl:
            payload["GraphDSL"] = graph_dsl
        payload.update(kwargs)
        return self._call_subsystem("CreateBlueprint", payload)

    def modify_blueprint(self, asset_path: str, operation: str,
                        payload: dict) -> dict:
        """修改蓝图"""
        return self._call_subsystem("ModifyBlueprint", {
            "AssetPath": asset_path,
            "Operation": operation,
            "Payload": payload
        })

    def save_blueprint(self, asset_paths: list) -> dict:
        """保存蓝图"""
        return self._call_subsystem("SaveBlueprints", {
            "AssetPaths": asset_paths
        })

    def _call_subsystem(self, function_name: str, params: dict) -> dict:
        """调用 UE Remote Control API"""
        import requests
        response = requests.post(
            f"{self.base_url}/remote/object/call",
            json={
                "objectPath": self.subsystem_path,
                "functionName": function_name,
                "parameters": params
            }
        )
        return response.json()
```

### 注册到工具系统

```python
# modules/ai_assistant/logic/tools_registry.py

class ToolsRegistry:
    def __init__(self, ..., blueprint_tool: BlueprintTool = None):
        # ... 现有代码 ...
        self.blueprint_tool = blueprint_tool

        # 注册蓝图工具
        if blueprint_tool:
            self._register_blueprint_tools()

    def _register_blueprint_tools(self):
        """注册蓝图相关工具"""

        @self.register_tool(
            name="read_blueprint",
            description="读取蓝图结构，返回节点、变量、组件等信息"
        )
        def read_blueprint(asset_path: str, scope: str = "Compact"):
            return self.blueprint_tool.extract_blueprint(asset_path, scope)

        @self.register_tool(
            name="create_blueprint",
            description="创建新蓝图，支持 DSL 语法快速定义图表"
        )
        def create_blueprint(asset_path: str, parent_class: str,
                           graph_dsl: str = None):
            return self.blueprint_tool.create_blueprint(
                asset_path, parent_class, graph_dsl=graph_dsl
            )

        @self.register_tool(
            name="modify_blueprint",
            description="修改现有蓝图，支持添加变量、组件、修改图表等"
        )
        def modify_blueprint(asset_path: str, operation: str, **kwargs):
            return self.blueprint_tool.modify_blueprint(
                asset_path, operation, kwargs
            )

        @self.register_tool(
            name="save_blueprint",
            description="保存蓝图到磁盘"
        )
        def save_blueprint(asset_paths: list):
            return self.blueprint_tool.save_blueprint(asset_paths)
```

---

## 🏗️ UE 插件实现

### 目录结构

```
BlueprintToAI/
├── Source/
│   └── BlueprintToAI/
│       ├── Public/
│       │   ├── BlueprintToAISubsystem.h
│       │   ├── BlueprintExtractor.h
│       │   ├── BlueprintCreator.h
│       │   ├── BlueprintModifier.h
│       │   └── DSLParser.h
│       └── Private/
│           ├── BlueprintToAISubsystem.cpp
│           ├── BlueprintExtractor.cpp
│           ├── BlueprintCreator.cpp
│           ├── BlueprintModifier.cpp
│           └── DSLParser.cpp
├── Config/
│   └── FilterPlugin.ini
└── BlueprintToAI.uplugin
```

### 核心类设计

```cpp
// BlueprintToAISubsystem.h

UCLASS()
class UBlueprintToAISubsystem : public UEditorSubsystem
{
    GENERATED_BODY()

public:
    // 提取蓝图
    UFUNCTION(BlueprintCallable, Category = "BlueprintToAI")
    FString ExtractBlueprint(const FString& AssetPath, const FString& Scope);

    // 创建蓝图
    UFUNCTION(BlueprintCallable, Category = "BlueprintToAI")
    FString CreateBlueprint(const FString& AssetPath, const FString& ParentClass,
                           const FString& GraphDSL);

    // 修改蓝图
    UFUNCTION(BlueprintCallable, Category = "BlueprintToAI")
    FString ModifyBlueprint(const FString& AssetPath, const FString& Operation,
                           const FString& PayloadJson);

    // 保存蓝图
    UFUNCTION(BlueprintCallable, Category = "BlueprintToAI")
    FString SaveBlueprints(const TArray<FString>& AssetPaths);

private:
    TUniquePtr<FBlueprintExtractor> Extractor;
    TUniquePtr<FBlueprintCreator> Creator;
    TUniquePtr<FBlueprintModifier> Modifier;
    TUniquePtr<FDSLParser> DSLParser;
};
```

### DSL 解析器

```cpp
// DSLParser.h

struct FDSLNode
{
    FString NodeType;  // Event, Call, Variable, Cast, Branch
    FString Name;
    FString Target;
    FString Alias;
    TMap<FString, FString> Args;
    TArray<TSharedPtr<FDSLNode>> Then;
    TMap<FString, TArray<TSharedPtr<FDSLNode>>> Branches;
};

class FDSLParser
{
public:
    // 解析 DSL 字符串
    TArray<FDSLNode> Parse(const FString& DSL);

    // 转换为蓝图节点
    void ApplyToGraph(UEdGraph* Graph, const TArray<FDSLNode>& Nodes);
};
```

---

## 📦 支持的 UE 版本

### 版本策略

采用"先新后旧"策略：

1. **Phase 1**：UE 5.4（1 周）
   - 最新的稳定版本
   - API 最完善
   - 验证核心功能

2. **Phase 2**：UE 5.0（1 周）
   - 处理 API 差异
   - 主要是 Ticker 和 AssetEditor API

3. **Phase 3**：UE 4.27（1 周）
   - 向下兼容
   - 处理更多 API 差异

4. **Phase 4**：UE 4.26（可选）
   - 如果有用户需求

### API 差异处理

```cpp
// 跨版本兼容宏
#if ENGINE_MAJOR_VERSION == 5
    #define BLUEPRINT_TICKER FTSTicker
    #define ASSET_EDITOR_SUBSYSTEM UAssetEditorSubsystem
#else
    #define BLUEPRINT_TICKER FTicker
    #define ASSET_EDITOR_SUBSYSTEM FAssetEditorManager
#endif
```

---

## 🎯 开发路线图

### Week 1：核心框架

- [x] 创建插件骨架
- [ ] 实现 BlueprintToAISubsystem
- [ ] 实现基础的 ExtractBlueprint（Compact 模式）
- [ ] 测试 Remote Control API 通信

### Week 2：创建功能

- [ ] 实现 CreateBlueprint（基础模式）
- [ ] 实现 DSL 解析器（基础语法）
- [ ] 支持基础节点类型（Event, Call, Variable）
- [ ] 测试创建流程

### Week 3：修改功能

- [ ] 实现 ModifyBlueprint
- [ ] 支持添加变量、组件
- [ ] 支持修改图表（DSL）
- [ ] 实现 SaveBlueprints

### Week 4：Python 集成

- [ ] 实现 BlueprintTool 类
- [ ] 注册到工具系统
- [ ] AI 助手集成测试
- [ ] 编写使用文档

### Week 5-6：多版本支持

- [ ] 移植到 UE 5.0
- [ ] 移植到 UE 4.27
- [ ] 处理 API 差异
- [ ] 跨版本测试

---

## 🧪 测试策略

### 单元测试

- DSL 解析器测试
- 节点创建测试
- 连接逻辑测试

### 集成测试

- Python → UE 通信测试
- 完整创建流程测试
- 修改流程测试

### 用户测试

- AI 生成简单蓝图
- AI 修改现有蓝图
- 错误处理测试

---

## 📝 使用示例

### 示例 1：AI 读取当前蓝图（无需路径）

**用户**："帮我看看这个蓝图做了什么"

**AI 调用**：

```python
result = extract_active_blueprint(Scope="Compact")
```

**AI 回复**："这个蓝图继承自 Character 类，在 BeginPlay 事件中获取了 PlayerController..."

### 示例 2：AI 读取指定路径的蓝图

**用户**："帮我看看 BP_Character 这个蓝图做了什么"

**AI 调用**：

```python
result = extract_blueprint(AssetPath="/Game/Blueprints/BP_Character", Scope="Compact")
```

**AI 回复**："这个蓝图继承自 Character 类，在 BeginPlay 事件中获取了 PlayerController..."

### 示例 3：AI 创建蓝图

**用户**："帮我创建一个 Actor，在 BeginPlay 时打印 Hello World"

**AI 调用**：

```python
create_blueprint(
    asset_path="/Game/Blueprints/BP_HelloWorld",
    parent_class="/Script/Engine.Actor",
    graph_dsl="Event BeginPlay -> Print(\"Hello World\")"
)
save_blueprint(["/Game/Blueprints/BP_HelloWorld"])
```

**AI 回复**："已创建 BP_HelloWorld 蓝图，并添加了打印逻辑。"

### 示例 4：AI 修改蓝图

**用户**："给 BP_Character 添加一个 Health 变量，默认值 100"

**AI 调用**：

```python
modify_blueprint(
    asset_path="/Game/Blueprints/BP_Character",
    operation="add_variable",
    name="Health",
    type="float",
    defaultValue=100.0
)
save_blueprint(["/Game/Blueprints/BP_Character"])
```

**AI 回复**："已添加 Health 变量，默认值为 100。"

---

## 🚀 下一步行动

1. **立即开始**：创建 UE 5.4 版本的插件骨架
2. **第一周目标**：实现基础的读取和创建功能
3. **快速迭代**：每周发布可测试版本
4. **用户反馈**：根据实际使用调整功能

---

**作者**：HUTAO  
**日期**：2025-01-XX  
**版本**：v1.0 设计文档
