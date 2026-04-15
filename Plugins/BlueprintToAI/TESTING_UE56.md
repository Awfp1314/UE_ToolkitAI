# BlueprintToAI - UE 5.6 测试指南

> 完整的 UE 5.6 适配测试流程

---

## 📋 前置要求

### 软件要求

- ✅ Unreal Engine 5.6.0 或更高版本
- ✅ Visual Studio 2022
- ✅ Python 3.8+ (用于测试脚本)

### UE 插件要求

必须启用以下插件：

1. **Remote Control** (内置)
2. **Enhanced Input** (内置)

---

## 🚀 安装步骤

### Step 1: 创建测试项目

1. 打开 Epic Games Launcher
2. 启动 UE 5.6
3. 创建新项目：
   - 模板：Third Person (C++)
   - 项目名称：`BlueprintToAI_Test`
   - 位置：任意

### Step 2: 复制插件

```bash
# 复制插件到项目
BlueprintToAI_Test/
└── Plugins/
    └── BlueprintToAI/  ← 复制整个文件夹到这里
```

### Step 3: 启用 Remote Control

1. 打开项目
2. Edit → Project Settings
3. 搜索 "Remote Control"
4. 勾选 "Enable Remote Control Web Server"
5. 设置 "Remote Control Web Server Port" = 30010
6. 重启编辑器

### Step 4: 生成项目文件

1. 关闭 UE 编辑器
2. 右键点击 `BlueprintToAI_Test.uproject`
3. 选择 "Generate Visual Studio project files"
4. 等待完成

### Step 5: 编译插件

1. 打开 `BlueprintToAI_Test.sln`
2. 配置选择：Development Editor
3. 平台选择：Win64
4. 右键项目 → Build
5. 等待编译完成（首次编译可能需要 5-10 分钟）

### Step 6: 验证插件加载

1. 启动 UE 编辑器
2. Edit → Plugins
3. 搜索 "Blueprint To AI"
4. 确认插件已启用且无错误
5. 查看 Output Log，应该看到：
   ```
   LogTemp: BlueprintToAI Subsystem initialized (UE 5.6+)
   ```

---

## 🧪 功能测试

### Test 1: 验证 Remote Control API

**使用浏览器测试**：

1. 打开浏览器
2. 访问：`http://127.0.0.1:30010/remote/info`
3. 应该看到 JSON 响应：

```json
{
  "serverName": "UnrealEditor",
  "serverVersion": "5.6.0",
  ...
}
```

### Test 2: 创建测试蓝图

在 UE 编辑器中：

1. Content Browser → 右键 → Blueprint Class
2. 选择 Actor
3. 命名为 `BP_TestActor`
4. 打开蓝图
5. 添加一个 Print String 节点
6. 保存并关闭

### Test 3: 提取蓝图（Python）

创建测试脚本 `test_extract.py`：

```python
import requests
import json

def test_extract_blueprint():
    url = "http://127.0.0.1:30010/remote/object/call"

    payload = {
        "objectPath": "/Script/BlueprintToAI.Default__BlueprintToAISubsystem",
        "functionName": "ExtractBlueprint",
        "parameters": {
            "AssetPath": "/Game/BP_TestActor",
            "Scope": "Compact"
        }
    }

    response = requests.post(url, json=payload)
    result = response.json()

    print("Status Code:", response.status_code)
    print("Response:")
    print(json.dumps(result, indent=2))

    # 验证
    assert response.status_code == 200, "HTTP 请求失败"
    assert result.get("success") == True, "操作失败"
    assert "blueprint" in result, "缺少 blueprint 字段"

    print("\n✅ 提取蓝图测试通过！")

if __name__ == "__main__":
    test_extract_blueprint()
```

运行测试：

```bash
python test_extract.py
```

预期输出：

```json
{
  "success": true,
  "operation": "ExtractBlueprint",
  "blueprint": {
    "name": "BP_TestActor",
    "parentClass": "/Script/Engine.Actor",
    "graphs": [...],
    "variables": []
  }
}
```

### Test 4: 创建蓝图（Python）

创建测试脚本 `test_create.py`：

```python
import requests
import json

def test_create_blueprint():
    url = "http://127.0.0.1:30010/remote/object/call"

    payload = {
        "objectPath": "/Script/BlueprintToAI.Default__BlueprintToAISubsystem",
        "functionName": "CreateBlueprint",
        "parameters": {
            "AssetPath": "/Game/BP_AICreated",
            "ParentClass": "/Script/Engine.Actor",
            "GraphDSL": "",
            "PayloadJson": "{}"
        }
    }

    response = requests.post(url, json=payload)
    result = response.json()

    print("Status Code:", response.status_code)
    print("Response:")
    print(json.dumps(result, indent=2))

    # 验证
    assert response.status_code == 200, "HTTP 请求失败"
    assert result.get("success") == True, "操作失败"
    assert result.get("assetPath") == "/Game/BP_AICreated", "资产路径不匹配"

    print("\n✅ 创建蓝图测试通过！")
    print("请在 Content Browser 中查看 BP_AICreated")

if __name__ == "__main__":
    test_create_blueprint()
```

运行测试：

```bash
python test_create.py
```

在 UE 编辑器中验证：

1. Content Browser → 刷新
2. 应该看到 `BP_AICreated`
3. 双击打开，确认是空的 Actor 蓝图

### Test 5: 修改蓝图（添加变量）

创建测试脚本 `test_modify.py`：

```python
import requests
import json

def test_modify_blueprint():
    url = "http://127.0.0.1:30010/remote/object/call"

    # 添加变量
    payload = {
        "objectPath": "/Script/BlueprintToAI.Default__BlueprintToAISubsystem",
        "functionName": "ModifyBlueprint",
        "parameters": {
            "AssetPath": "/Game/BP_AICreated",
            "Operation": "add_variable",
            "PayloadJson": json.dumps({
                "name": "Health",
                "type": "float"
            })
        }
    }

    response = requests.post(url, json=payload)
    result = response.json()

    print("Status Code:", response.status_code)
    print("Response:")
    print(json.dumps(result, indent=2))

    # 验证
    assert response.status_code == 200, "HTTP 请求失败"
    assert result.get("success") == True, "操作失败"

    print("\n✅ 修改蓝图测试通过！")
    print("请在 BP_AICreated 中查看 Health 变量")

if __name__ == "__main__":
    test_modify_blueprint()
```

在 UE 编辑器中验证：

1. 打开 `BP_AICreated`
2. 查看 Variables 面板
3. 应该看到 `Health` (Float) 变量

### Test 6: 保存蓝图

创建测试脚本 `test_save.py`：

```python
import requests
import json

def test_save_blueprint():
    url = "http://127.0.0.1:30010/remote/object/call"

    payload = {
        "objectPath": "/Script/BlueprintToAI.Default__BlueprintToAISubsystem",
        "functionName": "SaveBlueprints",
        "parameters": {
            "AssetPaths": [
                "/Game/BP_AICreated"
            ]
        }
    }

    response = requests.post(url, json=payload)
    result = response.json()

    print("Status Code:", response.status_code)
    print("Response:")
    print(json.dumps(result, indent=2))

    # 验证
    assert response.status_code == 200, "HTTP 请求失败"
    assert result.get("success") == True, "操作失败"
    assert result.get("savedCount") == 1, "保存数量不匹配"

    print("\n✅ 保存蓝图测试通过！")

if __name__ == "__main__":
    test_save_blueprint()
```

---

## 🐛 常见问题

### 问题 1: 编译错误 - 找不到 RemoteControlCommon

**解决方案**：

1. 确认 Remote Control 插件已启用
2. 重新生成项目文件
3. 清理并重新编译

### 问题 2: HTTP 请求返回 404

**可能原因**：

- Remote Control Web Server 未启用
- 端口号不正确
- 编辑器未运行

**解决方案**：

1. 检查 Project Settings → Remote Control
2. 确认端口为 30010
3. 重启编辑器

### 问题 3: 找不到 Subsystem

**错误信息**：

```json
{
  "errorCode": "ObjectNotFound",
  "errorMessage": "Object not found: /Script/BlueprintToAI.Default__BlueprintToAISubsystem"
}
```

**解决方案**：

1. 确认插件已编译
2. 确认插件已启用
3. 重启编辑器
4. 检查 Output Log 是否有初始化日志

### 问题 4: 蓝图创建失败

**可能原因**：

- 父类路径错误
- 资产路径已存在
- 权限问题

**解决方案**：

1. 使用正确的父类路径（如 `/Script/Engine.Actor`）
2. 确保资产路径不存在
3. 检查 Content 文件夹权限

---

## 📊 性能基准

在 UE 5.6 上的预期性能：

| 操作                       | 耗时    | 说明     |
| -------------------------- | ------- | -------- |
| ExtractBlueprint (Minimal) | < 100ms | 小型蓝图 |
| ExtractBlueprint (Compact) | < 500ms | 中型蓝图 |
| ExtractBlueprint (Full)    | < 2s    | 大型蓝图 |
| CreateBlueprint            | < 200ms | 空蓝图   |
| ModifyBlueprint            | < 100ms | 单个操作 |
| SaveBlueprints             | < 500ms | 单个蓝图 |

---

## ✅ 测试清单

完成以下所有测试后，插件即为完全适配 UE 5.6：

- [ ] 插件编译成功
- [ ] 插件加载无错误
- [ ] Remote Control API 可访问
- [ ] ExtractBlueprint 功能正常
- [ ] CreateBlueprint 功能正常
- [ ] ModifyBlueprint (add_variable) 功能正常
- [ ] ModifyBlueprint (reparent) 功能正常
- [ ] SaveBlueprints 功能正常
- [ ] 所有 Python 测试脚本通过
- [ ] 性能符合预期

---

## 📝 下一步

完成 UE 5.6 适配后：

1. **Phase 2**: 实现 DSL 解析器
2. **Phase 3**: 添加更多节点类型支持
3. **Phase 4**: 移植到 UE 5.4、5.0、4.27

---

**测试负责人**：HUTAO  
**测试日期**：2025-01-XX  
**UE 版本**：5.6.0
