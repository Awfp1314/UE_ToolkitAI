# UE 版本兼容性说明

本文档说明 BlueprintAITools 插件如何处理不同 UE 版本之间的 API 差异。

---

## 关键 API 差异

### 1. Editor Subsystem API

**UE 4.26/4.27**：

```cpp
#include "Toolkits/AssetEditorManager.h"

FAssetEditorManager& AssetEditorManager = FAssetEditorManager::Get();
TArray<UObject*> EditedAssets = AssetEditorManager.GetAllEditedAssets();
```

**UE 5.0+**：

```cpp
#include "Subsystems/AssetEditorSubsystem.h"

UAssetEditorSubsystem* AssetEditorSubsystem = GEditor->GetEditorSubsystem<UAssetEditorSubsystem>();
TArray<UObject*> EditedAssets = AssetEditorSubsystem->GetAllEditedAssets();
```

**变更原因**：UE5 引入了新的 Subsystem 架构，`FAssetEditorManager` 被 `UAssetEditorSubsystem` 替代。

---

### 2. Ticker API

**UE 4.x**：

```cpp
#include "Ticker.h"

FTicker::GetCoreTicker().AddTicker(...)
```

**UE 5.x**：

```cpp
#include "Containers/Ticker.h"

FTSTicker::GetCoreTicker().AddTicker(...)
```

**变更原因**：UE5 将 `FTicker` 重命名为 `FTSTicker`（Thread-Safe Ticker）。

---

## 条件编译实现

### 头文件引用

```cpp
// UE 版本兼容性：UE5 使用 UAssetEditorSubsystem，UE4 使用 FAssetEditorManager
#if ENGINE_MAJOR_VERSION >= 5
	#include "Subsystems/AssetEditorSubsystem.h"
#else
	#include "Toolkits/AssetEditorManager.h"
#endif
```

### 函数实现

```cpp
UBlueprint* UBlueprintAIToolsLibrary::GetCurrentOpenBlueprint()
{
	if (!GEditor)
	{
		return nullptr;
	}

	// UE 版本兼容性处理
	TArray<UObject*> EditedAssets;

#if ENGINE_MAJOR_VERSION >= 5
	// UE5: 使用 UAssetEditorSubsystem
	UAssetEditorSubsystem* AssetEditorSubsystem = GEditor->GetEditorSubsystem<UAssetEditorSubsystem>();
	if (!AssetEditorSubsystem)
	{
		return nullptr;
	}
	EditedAssets = AssetEditorSubsystem->GetAllEditedAssets();
#else
	// UE4: 使用 FAssetEditorManager
	FAssetEditorManager& AssetEditorManager = FAssetEditorManager::Get();
	EditedAssets = AssetEditorManager.GetAllEditedAssets();
#endif

	// 后续处理代码相同...
}
```

---

## 受影响的函数

### BlueprintAIToolsLibrary.cpp

1. **GetCurrentOpenBlueprint()**
   - 使用 `UAssetEditorSubsystem` (UE5) 或 `FAssetEditorManager` (UE4)
   - 获取当前打开的蓝图编辑器

2. **GetSelectedNodes()**
   - 使用 `UAssetEditorSubsystem::FindEditorForAsset()` (UE5)
   - 使用 `FAssetEditorManager::FindEditorForAsset()` (UE4)
   - 获取蓝图编辑器中选中的节点

### BlueprintAITools.cpp

1. **StartupModule()**
   - 使用 `FTSTicker` (UE5) 或 `FTicker` (UE4)
   - 定时检查 Python 脚本加载状态

---

## 测试建议

### UE 4.26/4.27 测试

1. 创建纯蓝图项目
2. 安装 `BlueprintAITools_v3.0_UE426` 插件
3. 编译并启动编辑器
4. 打开蓝图编辑器
5. 验证 RPC 服务器启动
6. 测试蓝图读取功能

### UE 5.0-5.3 测试

1. 创建纯蓝图项目
2. 安装 `BlueprintAITools_v3.0_UE50` 插件
3. 编译并启动编辑器
4. 打开蓝图编辑器
5. 验证 RPC 服务器启动
6. 测试蓝图读取功能

### UE 5.4+ 测试

1. 创建纯蓝图项目
2. 安装 `BlueprintAITools_v3.0_UE54` 插件
3. 编译并启动编辑器
4. 打开蓝图编辑器
5. 验证 RPC 服务器启动
6. 测试蓝图读取功能

---

## 维护指南

### 添加新功能时

1. 检查是否使用了版本特定的 API
2. 如果是，添加条件编译：
   ```cpp
   #if ENGINE_MAJOR_VERSION >= 5
       // UE5 代码
   #else
       // UE4 代码
   #endif
   ```
3. 在三个版本中测试

### 常见 API 差异

| 功能             | UE4                   | UE5                     |
| ---------------- | --------------------- | ----------------------- |
| Editor Subsystem | `FAssetEditorManager` | `UAssetEditorSubsystem` |
| Ticker           | `FTicker`             | `FTSTicker`             |
| Python 插件      | 基础功能              | 完整功能                |

---

## 参考资料

- [UE5 Migration Guide](https://docs.unrealengine.com/5.0/en-US/MigrationGuide/)
- [UE Subsystems Documentation](https://docs.unrealengine.com/4.27/en-US/ProgrammingAndScripting/Subsystems/)
- [FAssetEditorManager to UAssetEditorSubsystem Migration](https://forums.unrealengine.com/t/fasseteditormanager-missing-in-ue5/524878)

---

**更新时间**：2025-01-XX  
**作者**：HUTAO
