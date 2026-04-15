# 激活蓝图功能说明

> 无需输入路径，直接分析当前打开的蓝图

---

## 🎯 功能概述

新增了两个便捷函数，让 AI 能够自动获取当前在 UE 编辑器中打开的蓝图，无需手动输入路径。

---

## 🆕 新增函数

### 1. GetActiveBlueprint

获取当前激活的蓝图信息。

**C++ 签名**：

```cpp
UFUNCTION(BlueprintCallable, Category = "BlueprintToAI")
FString GetActiveBlueprint();
```

**返回示例**：

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

### 2. ExtractActiveBlueprint

提取当前激活蓝图的完整结构（便捷函数）。

**C++ 签名**：

```cpp
UFUNCTION(BlueprintCallable, Category = "BlueprintToAI")
FString ExtractActiveBlueprint(const FString& Scope);
```

**参数**：

- `Scope`（可选）：提取范围
  - `"Minimal"` - 只有节点类型和连接
  - `"Compact"` - 默认，包含位置和基本属性
  - `"Full"` - 包含所有信息

**返回**：与 `ExtractBlueprint` 相同的结构。

---

## 💡 使用场景

### 场景 1：快速分析当前蓝图

**操作**：

1. 在 UE 编辑器中双击打开一个蓝图
2. 在 AI 助手中输入："帮我看看这个蓝图"

**AI 行为**：

- 自动调用 `extract_active_blueprint` 工具
- 无需用户提供路径
- 直接分析当前打开的蓝图

### 场景 2：对比多个蓝图

**操作**：

1. 打开蓝图 A，问 AI："这个蓝图做了什么？"
2. 切换到蓝图 B，问 AI："这个蓝图呢？"
3. 问 AI："这两个蓝图有什么区别？"

**AI 行为**：

- 每次自动获取当前激活的蓝图
- 记住之前分析的结果
- 进行对比分析

### 场景 3：调试蓝图

**操作**：

1. 打开有问题的蓝图
2. 问 AI："这个蓝图有什么问题？"

**AI 行为**：

- 自动分析当前蓝图
- 检测常见错误（如未连接的节点、循环引用等）
- 提供修复建议

---

## 🔧 实现原理

### UE 端

使用 `UAssetEditorSubsystem` 获取当前打开的资产：

```cpp
UAssetEditorSubsystem* AssetEditorSubsystem = GEditor->GetEditorSubsystem<UAssetEditorSubsystem>();
TArray<UObject*> EditedAssets = AssetEditorSubsystem->GetAllEditedAssets();

// 找到第一个 Blueprint
for (UObject* Asset : EditedAssets)
{
    if (UBlueprint* Blueprint = Cast<UBlueprint>(Asset))
    {
        // 找到了！
        return Blueprint->GetPathName();
    }
}
```

### Python 端

注册了两个新工具：

```python
# 工具 1: 获取激活蓝图信息
self.register_tool(ToolDefinition(
    name="get_active_blueprint",
    description="获取当前在 UE 编辑器中激活的蓝图信息",
    ...
))

# 工具 2: 提取激活蓝图结构（便捷函数）
self.register_tool(ToolDefinition(
    name="extract_active_blueprint",
    description="提取当前激活蓝图的结构信息",
    ...
))
```

---

## 📝 AI 提示词优化

AI 现在能够理解以下表达：

**无需路径的表达**：

- "帮我看看这个蓝图"
- "分析一下当前蓝图"
- "这个蓝图做了什么？"
- "检查一下这个蓝图有没有问题"

**需要路径的表达**：

- "帮我看看 BP_Character 这个蓝图"
- "分析 /Game/Blueprints/BP_Player"

AI 会根据用户是否提供路径，自动选择合适的工具：

- 没有路径 → 使用 `extract_active_blueprint`
- 有路径 → 使用 `extract_blueprint`

---

## ⚠️ 注意事项

### 1. 必须先打开蓝图

如果没有打开任何蓝图，会返回错误：

```json
{
  "success": false,
  "error": "No Blueprint is currently open in the editor"
}
```

**解决方法**：在 UE 编辑器中双击打开一个蓝图。

### 2. 多个蓝图打开时

如果同时打开了多个蓝图，会返回第一个（通常是最近激活的）。

**建议**：如果要分析特定蓝图，确保它是当前激活的窗口。

### 3. 非蓝图资产

如果当前打开的是其他类型的资产（如材质、Widget），会返回错误。

**解决方法**：切换到蓝图编辑器窗口。

---

## 🧪 测试步骤

### 1. 编译插件

```bash
# 在 UE 项目目录
# 右键 .uproject → Generate Visual Studio project files
# 打开 .sln → 编译 Development Editor
```

### 2. 启动 UE 编辑器

确保 BlueprintToAI 插件已启用。

### 3. 打开一个蓝图

在 Content Browser 中双击任意蓝图。

### 4. 测试 Python 调用

```python
from modules.ai_assistant.clients.ue_tool_client import UEToolClient

client = UEToolClient()

# 测试 1: 获取激活蓝图
result = client.execute_tool_rpc("GetActiveBlueprint")
print(result)

# 测试 2: 提取激活蓝图
result = client.execute_tool_rpc("ExtractActiveBlueprint", Scope="Compact")
print(result)
```

### 5. 测试 AI 助手

在 AI 助手中输入：

```
帮我看看这个蓝图
```

应该能够自动分析当前打开的蓝图。

---

## 🎉 总结

这个功能大大提升了用户体验：

**之前**：

- 用户："帮我看看这个蓝图"
- AI："请提供蓝图路径"
- 用户："/Game/Blueprints/BP_Character"
- AI：（分析蓝图）

**现在**：

- 用户："帮我看看这个蓝图"
- AI：（自动获取并分析当前打开的蓝图）

更自然、更高效！

---

**更新日期**：2025-01-XX  
**版本**：v1.1 - 新增激活蓝图功能
