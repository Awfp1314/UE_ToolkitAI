# BlueprintToAI Python 集成说明

> 如何在 Python 应用中使用 BlueprintToAI 插件

---

## 🔄 架构变更

### 旧架构（Socket RPC）

```
Python App → Socket (9998) → UE Python Script
```

- 使用自定义 JSON-RPC 协议
- 需要在 UE 中运行 Python Socket 服务器
- 只支持只读操作

### 新架构（HTTP Remote Control API）

```
Python App → HTTP (30010) → Remote Control API → BlueprintToAISubsystem
```

- 使用 UE 官方的 Remote Control API
- 标准 HTTP + JSON 协议
- 支持读写操作
- 更稳定、更易调试

---

## 📝 已更新的文件

### 1. `ui/ue_main_window.py`

**变更**：连接检测逻辑

```python
# 旧代码：使用 Socket 检测
sock.connect(('127.0.0.1', 9998))

# 新代码：使用 HTTP 检测
response = requests.get('http://127.0.0.1:30010/remote/info', timeout=1.5)
```

**影响**：

- 状态栏的 "UE 未连接" / "UE 已连接" 现在检测的是 Remote Control API
- 每 5 秒自动检查一次连接状态

### 2. `modules/ai_assistant/clients/ue_tool_client.py`

**变更**：完全重写，从 Socket 改为 HTTP

```python
# 旧代码：Socket RPC
class UEToolClient:
    def __init__(self, host: str = "127.0.0.1", port: int = 9998):
        self._socket = socket.socket(...)

# 新代码：HTTP API
class UEToolClient:
    def __init__(self, base_url: str = "http://127.0.0.1:30010"):
        self.base_url = base_url
```

**主要方法**：

- `_check_connection()` - 检查 Remote Control API 是否可用
- `execute_tool_rpc(tool_name, **kwargs)` - 调用 BlueprintToAISubsystem 的函数

### 3. `modules/ai_assistant/logic/tools_registry.py`

**变更**：注册新的蓝图工具

```python
# 新增工具：
- extract_blueprint      # 提取蓝图结构
- create_blueprint       # 创建新蓝图
- modify_blueprint       # 修改现有蓝图
- save_blueprints        # 保存蓝图

# 移除工具：
- get_current_blueprint_summary  # 旧的只读工具
```

---

## 🔧 使用方法

### 1. 启用 Remote Control API

在 UE 编辑器中：

1. 打开 `编辑 → 项目设置`
2. 搜索 "Remote Control"
3. 启用 `Remote Control Web Server`
4. 确认端口为 `30010`

### 2. 安装插件

将 `BlueprintToAI` 插件复制到项目的 `Plugins` 目录，重新生成项目文件并编译。

### 3. 测试连接

在 Python 应用中：

```python
from modules.ai_assistant.clients.ue_tool_client import UEToolClient

client = UEToolClient()
if client.test_connection():
    print("✅ 连接成功")
else:
    print("❌ 连接失败")
```

### 4. 调用工具

通过 AI 助手调用：

```
用户: "帮我看看 BP_Character 这个蓝图"
AI: 调用 extract_blueprint(AssetPath="/Game/Blueprints/BP_Character")

用户: "创建一个新的 Actor 蓝图"
AI: 调用 create_blueprint(AssetPath="/Game/Blueprints/BP_MyActor", ParentClass="/Script/Engine.Actor")
```

---

## 🐛 故障排查

### 问题 1：显示 "UE 未连接"

**原因**：Remote Control API 未启用或端口不对

**解决**：

1. 检查 UE 编辑器是否运行
2. 检查 Remote Control Web Server 是否启用
3. 在浏览器访问 `http://127.0.0.1:30010/remote/info`，应该返回 JSON

### 问题 2：工具调用失败

**原因**：插件未加载或函数名错误

**解决**：

1. 检查插件是否在 UE 中启用
2. 检查 Output Log 中的错误信息
3. 确认函数名拼写正确（区分大小写）

### 问题 3：参数格式错误

**原因**：参数类型不匹配

**解决**：

- `AssetPath` 必须是完整路径（如 `/Game/Blueprints/BP_MyActor`）
- `Scope` 必须是 `Minimal` | `Compact` | `Full`
- `PayloadJson` 必须是有效的 JSON 字符串

---

## 📚 API 参考

### ExtractBlueprint

提取蓝图结构信息。

```python
result = client.execute_tool_rpc(
    "ExtractBlueprint",
    AssetPath="/Game/Blueprints/BP_Character",
    Scope="Compact"  # 可选：Minimal | Compact | Full
)
```

**返回**：

```json
{
  "success": true,
  "blueprint": {
    "name": "BP_Character",
    "parentClass": "/Script/Engine.Character",
    "graphs": [...],
    "variables": [...],
    "components": [...]
  }
}
```

### CreateBlueprint

创建新蓝图。

```python
result = client.execute_tool_rpc(
    "CreateBlueprint",
    AssetPath="/Game/Blueprints/BP_MyActor",
    ParentClass="/Script/Engine.Actor",
    GraphDSL="Event BeginPlay -> Print(\"Hello World\")"  # 可选
)
```

### ModifyBlueprint

修改现有蓝图。

```python
import json

result = client.execute_tool_rpc(
    "ModifyBlueprint",
    AssetPath="/Game/Blueprints/BP_MyActor",
    Operation="add_variable",
    PayloadJson=json.dumps({
        "name": "Health",
        "type": "float",
        "defaultValue": 100.0
    })
)
```

### SaveBlueprints

保存蓝图到磁盘。

```python
import json

result = client.execute_tool_rpc(
    "SaveBlueprints",
    AssetPaths=json.dumps([
        "/Game/Blueprints/BP_MyActor",
        "/Game/Blueprints/BP_MyCharacter"
    ])
)
```

---

## 🎯 下一步

1. 测试连接是否正常
2. 测试基础的 `ExtractBlueprint` 功能
3. 测试 `CreateBlueprint` 功能
4. 完善错误处理和日志

---

**更新日期**：2025-01-XX  
**版本**：v1.0
