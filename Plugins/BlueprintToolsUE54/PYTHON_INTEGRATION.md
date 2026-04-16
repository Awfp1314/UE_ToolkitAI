# Blueprint Tools UE5.4 - Python 集成指南

## 概述

Blueprint Tools UE5.4 插件可以通过 Python 客户端与 UE Toolkit 集成，实现蓝图的自动化操作。

## 快速开始

### 1. 使用专用客户端

```python
from modules.ai_assistant.clients.blueprint_tools_ue54_client import BlueprintToolsUE54Client

# 初始化客户端
client = BlueprintToolsUE54Client(base_url="http://127.0.0.1:30010")

# 验证连接
if client.verify_connection():
    print("✅ 已连接到 UE 5.4 编辑器")
else:
    print("❌ 连接失败")
```

### 2. 创建蓝图

```python
result = client.execute_tool_rpc(
    "CreateBlueprint",
    AssetPath="/Game/Blueprints/BP_MyActor",
    ParentClassPath="/Script/Engine.Actor",
    PayloadJson="",
    bValidateOnly=False
)

print(result)
# 输出: {"success": true, "assetPath": "/Game/Blueprints/BP_MyActor.BP_MyActor", ...}
```

### 3. 添加变量

```python
import json

# 构建变量定义
variable_def = {
    "name": "Health",
    "type": {
        "category": "float"
    },
    "defaultValue": "100.0",
    "category": "Stats",
    "tooltip": "Player health value",
    "instanceEditable": True,
    "exposeOnSpawn": False,
    "replicated": False
}

result = client.execute_tool_rpc(
    "ModifyBlueprintMembers",
    AssetPath="/Game/Blueprints/BP_MyActor.BP_MyActor",
    Operation="add_variable",
    PayloadJson=json.dumps(variable_def),
    bValidateOnly=False
)

print(result)
# 输出: {"success": true, "message": "Variable 'Health' added successfully", ...}
```

### 4. 修改变量

```python
modify_def = {
    "name": "Health",
    "defaultValue": "150.0",
    "category": "Player Stats",
    "tooltip": "Updated health value"
}

result = client.execute_tool_rpc(
    "ModifyBlueprintMembers",
    AssetPath="/Game/Blueprints/BP_MyActor.BP_MyActor",
    Operation="modify_variable",
    PayloadJson=json.dumps(modify_def),
    bValidateOnly=False
)
```

### 5. 删除变量

```python
remove_def = {
    "name": "OldVariable"
}

result = client.execute_tool_rpc(
    "ModifyBlueprintMembers",
    AssetPath="/Game/Blueprints/BP_MyActor.BP_MyActor",
    Operation="remove_variable",
    PayloadJson=json.dumps(remove_def),
    bValidateOnly=False
)
```

### 6. 编译蓝图

```python
result = client.execute_tool_rpc(
    "CompileBlueprint",
    AssetPath="/Game/Blueprints/BP_MyActor.BP_MyActor"
)

print(result)
# 输出: {"success": true, "errors": [], "warnings": [], ...}
```

### 7. 保存资产

```python
import json

asset_paths = [
    "/Game/Blueprints/BP_MyActor.BP_MyActor",
    "/Game/Blueprints/BP_Another.BP_Another"
]

result = client.execute_tool_rpc(
    "SaveAssets",
    AssetPathsJson=json.dumps(asset_paths)
)

print(result)
# 输出: {"success": true, "savedCount": 2, "totalCount": 2}
```

## 变量类型定义

### 基础类型

```python
# Float
{"category": "float"}

# Int
{"category": "int"}

# Bool
{"category": "bool"}

# String
{"category": "string"}

# Name
{"category": "name"}

# Text
{"category": "text"}
```

### 对象引用

```python
# Actor 引用
{
    "category": "object",
    "subCategoryObject": "/Script/Engine.Actor"
}

# 自定义类引用
{
    "category": "object",
    "subCategoryObject": "/Game/Blueprints/BP_MyClass.BP_MyClass_C"
}
```

### 结构体

```python
{
    "category": "struct",
    "subCategoryObject": "/Script/CoreUObject.Vector"
}
```

### 枚举

```python
{
    "category": "byte",
    "subCategoryObject": "/Script/Engine.ECollisionChannel"
}
```

### 容器类型

```python
# Array
{
    "category": "float",
    "containerType": "Array"
}

# Set
{
    "category": "int",
    "containerType": "Set"
}

# Map (需要 valueType)
{
    "category": "string",
    "containerType": "Map",
    "valueType": {
        "category": "float"
    }
}
```

## 变量标志

```python
variable_def = {
    "name": "MyVariable",
    "type": {"category": "float"},

    # 实例可编辑（在细节面板中可见和编辑）
    "instanceEditable": True,

    # 生成时暴露（在 SpawnActor 节点上显示）
    "exposeOnSpawn": True,

    # 网络复制
    "replicated": True,

    # 分类（在细节面板中的分组）
    "category": "My Category",

    # 提示文本
    "tooltip": "This is a tooltip"
}
```

## 搜索和列表

### 搜索资产

```python
result = client.execute_tool_rpc(
    "SearchAssets",
    Query="Character",
    ClassFilter="Blueprint",
    MaxResults=50
)

for asset in result.get("assets", []):
    print(f"{asset['assetName']}: {asset['assetPath']}")
```

### 列出目录

```python
result = client.execute_tool_rpc(
    "ListAssets",
    PackagePath="/Game/Blueprints",
    bRecursive=True,
    ClassFilter="Blueprint"
)

for asset in result.get("assets", []):
    print(f"{asset['assetName']}: {asset['assetPath']}")
```

## 错误处理

```python
result = client.execute_tool_rpc(
    "CreateBlueprint",
    AssetPath="/Game/Test",
    ParentClassPath="/Script/Engine.Actor"
)

if result.get("success"):
    print(f"✅ 成功: {result.get('message')}")
else:
    print(f"❌ 失败: {result.get('error')}")
```

## 完整示例：创建带变量的蓝图

```python
import json
from modules.ai_assistant.clients.blueprint_tools_ue54_client import BlueprintToolsUE54Client

def create_character_blueprint():
    client = BlueprintToolsUE54Client()

    # 1. 验证连接
    if not client.verify_connection():
        print("❌ 无法连接到 UE 编辑器")
        return

    # 2. 创建蓝图
    print("创建蓝图...")
    result = client.execute_tool_rpc(
        "CreateBlueprint",
        AssetPath="/Game/Characters/BP_MyCharacter",
        ParentClassPath="/Script/Engine.Character"
    )

    if not result.get("success"):
        print(f"❌ 创建失败: {result.get('error')}")
        return

    asset_path = result["assetPath"]
    print(f"✅ 蓝图已创建: {asset_path}")

    # 3. 添加变量
    variables = [
        {
            "name": "Health",
            "type": {"category": "float"},
            "defaultValue": "100.0",
            "category": "Stats",
            "instanceEditable": True
        },
        {
            "name": "MaxHealth",
            "type": {"category": "float"},
            "defaultValue": "100.0",
            "category": "Stats"
        },
        {
            "name": "IsAlive",
            "type": {"category": "bool"},
            "defaultValue": "true",
            "category": "Status",
            "exposeOnSpawn": True
        }
    ]

    for var in variables:
        print(f"添加变量: {var['name']}...")
        result = client.execute_tool_rpc(
            "ModifyBlueprintMembers",
            AssetPath=asset_path,
            Operation="add_variable",
            PayloadJson=json.dumps(var)
        )

        if result.get("success"):
            print(f"  ✅ {var['name']} 已添加")
        else:
            print(f"  ❌ 失败: {result.get('error')}")

    # 4. 编译蓝图
    print("编译蓝图...")
    result = client.execute_tool_rpc(
        "CompileBlueprint",
        AssetPath=asset_path
    )

    if result.get("success"):
        print("✅ 编译成功")
    else:
        print(f"❌ 编译失败")

    # 5. 保存
    print("保存资产...")
    result = client.execute_tool_rpc(
        "SaveAssets",
        AssetPathsJson=json.dumps([asset_path])
    )

    if result.get("success"):
        print(f"✅ 已保存 {result.get('savedCount')} 个资产")
    else:
        print(f"❌ 保存失败")

if __name__ == "__main__":
    create_character_blueprint()
```

## 与 BlueprintExtractor 的区别

| 功能        | BlueprintExtractor | BlueprintToolsUE54  |
| ----------- | ------------------ | ------------------- |
| 蓝图提取    | ✅ 完整            | ⚠️ 基础（仅元数据） |
| 创建蓝图    | ✅                 | ✅                  |
| 变量操作    | ✅                 | ✅                  |
| 函数操作    | ✅                 | ❌ 未实现           |
| 组件操作    | ✅                 | ❌ 未实现           |
| Widget 蓝图 | ✅                 | ❌ 未实现           |
| 材质操作    | ✅                 | ❌ 未实现           |
| 版本支持    | UE 5.3+            | UE 5.4 专用         |

## 注意事项

1. **资产路径格式**：必须使用完整路径，如 `/Game/BP.BP`，不是 `/Game/BP`
2. **父类路径**：使用完整的类路径，如 `/Script/Engine.Actor`
3. **编译**：修改后建议手动编译一次以确保完全更新
4. **保存**：所有修改不会自动保存，必须调用 `SaveAssets`
5. **连接检测**：使用 `verify_connection()` 确保 UE 编辑器正在运行

## 故障排除

### 连接失败

- 确保 UE 编辑器正在运行
- 确保 Blueprint Tools UE5.4 插件已启用
- 检查 Remote Control 设置（项目设置 → Remote Control → 启用 Web Server）
- 确认端口 30010 未被占用

### 创建失败

- 检查资产路径格式是否正确
- 确认父类路径存在
- 查看 UE 输出日志获取详细错误

### 变量添加失败

- 检查类型定义是否正确
- 确认变量名不重复
- 验证 subCategoryObject 路径是否存在
