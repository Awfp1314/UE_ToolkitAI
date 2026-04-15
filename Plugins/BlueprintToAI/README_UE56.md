# BlueprintToAI Plugin - UE 5.6 Edition

> Enable AI to read, create and modify Blueprints via Remote Control API

**版本**: 1.0.0  
**引擎**: Unreal Engine 5.6.0+  
**状态**: ✅ 核心功能完成并测试

---

## 🎯 核心功能

- ✅ **提取蓝图结构** - 节点、变量、组件、连接关系
- ✅ **创建新蓝图** - 指定父类和初始配置
- ✅ **修改现有蓝图** - 添加变量、更改父类
- ✅ **保存蓝图** - 批量保存到磁盘
- ✅ **三种提取模式** - Minimal/Compact/Full（优化 token 使用）
- ✅ **纯 C++ 实现** - 无外部依赖，不需要 Node.js 或 MCP 服务器
- ✅ **标准 HTTP API** - 通过 UE Remote Control API 通信

---

## 🚀 快速开始

### 1. 前置要求

- Unreal Engine 5.6.0 或更高版本
- Visual Studio 2022
- Python 3.8+ (用于测试，可选)

### 2. 安装插件

```bash
# 复制插件到项目
YourProject/
└── Plugins/
    └── BlueprintToAI/  ← 复制整个文件夹
```

### 3. 启用依赖插件

在 UE 编辑器中：

1. Edit → Plugins
2. 搜索并启用：
   - Remote Control (内置)
   - Enhanced Input (内置)
3. 重启编辑器

### 4. 配置 Remote Control

1. Edit → Project Settings
2. 搜索 "Remote Control"
3. 勾选 "Enable Remote Control Web Server"
4. 设置 "Remote Control Web Server Port" = 30010
5. 重启编辑器

### 5. 编译插件

1. 右键 `.uproject` → Generate Visual Studio project files
2. 打开 `.sln`
3. 配置：Development Editor | Win64
4. 右键项目 → Build
5. 等待编译完成

### 6. 验证安装

1. 启动 UE 编辑器
2. 查看 Output Log，应该看到：
   ```
   LogTemp: BlueprintToAI Subsystem initialized (UE 5.6+)
   ```
3. 浏览器访问：`http://127.0.0.1:30010/remote/info`
4. 应该看到 JSON 响应

---

## 🧪 测试

### 自动化测试套件

```bash
cd Plugins/BlueprintToAI/tests
python test_suite.py
```

测试内容：

- ✅ Remote Control API 连接
- ✅ 提取蓝图（所有模式）
- ✅ 创建蓝图
- ✅ 添加变量
- ✅ 更改父类
- ✅ 保存蓝图

### 详细测试指南

查看 [TESTING_UE56.md](TESTING_UE56.md) 获取完整测试流程。

---

## 📖 API 使用

### Python 示例

```python
import requests
import json

class BlueprintTool:
    def __init__(self):
        self.base_url = "http://127.0.0.1:30010"
        self.subsystem = "/Script/BlueprintToAI.Default__BlueprintToAISubsystem"

    def call(self, function_name, params):
        response = requests.post(
            f"{self.base_url}/remote/object/call",
            json={
                "objectPath": self.subsystem,
                "functionName": function_name,
                "parameters": params
            }
        )
        return response.json()

    # 提取蓝图
    def extract_blueprint(self, asset_path, scope="Compact"):
        return self.call("ExtractBlueprint", {
            "AssetPath": asset_path,
            "Scope": scope
        })

    # 创建蓝图
    def create_blueprint(self, asset_path, parent_class):
        return self.call("CreateBlueprint", {
            "AssetPath": asset_path,
            "ParentClass": parent_class,
            "GraphDSL": "",
            "PayloadJson": "{}"
        })

    # 添加变量
    def add_variable(self, asset_path, var_name, var_type):
        return self.call("ModifyBlueprint", {
            "AssetPath": asset_path,
            "Operation": "add_variable",
            "PayloadJson": json.dumps({
                "name": var_name,
                "type": var_type
            })
        })

    # 保存蓝图
    def save_blueprints(self, asset_paths):
        return self.call("SaveBlueprints", {
            "AssetPaths": asset_paths
        })

# 使用示例
tool = BlueprintTool()

# 读取蓝图
result = tool.extract_blueprint("/Game/BP_MyActor")
print(result)

# 创建蓝图
result = tool.create_blueprint("/Game/BP_NewActor", "/Script/Engine.Actor")

# 添加变量
result = tool.add_variable("/Game/BP_NewActor", "Health", "float")

# 保存
result = tool.save_blueprints(["/Game/BP_NewActor"])
```

---

## 📋 API 参考

### ExtractBlueprint

提取蓝图结构到 JSON。

**参数**：

- `AssetPath` (string): 蓝图资产路径，如 `/Game/Blueprints/BP_MyActor`
- `Scope` (string): 提取模式
  - `Minimal` - 只有节点类型和连接（最省 token）
  - `Compact` - 添加位置和基本属性（默认）
  - `Full` - 所有信息（调试用）

**返回**：

```json
{
  "success": true,
  "operation": "ExtractBlueprint",
  "blueprint": {
    "name": "BP_MyActor",
    "parentClass": "/Script/Engine.Actor",
    "graphs": [...],
    "variables": [...]
  }
}
```

### CreateBlueprint

创建新蓝图。

**参数**：

- `AssetPath` (string): 新蓝图路径
- `ParentClass` (string): 父类路径，如 `/Script/Engine.Actor`
- `GraphDSL` (string): 图表 DSL（Phase 2 实现）
- `PayloadJson` (string): 额外配置 JSON

**返回**：

```json
{
  "success": true,
  "operation": "CreateBlueprint",
  "assetPath": "/Game/BP_NewActor",
  "message": "Blueprint created successfully"
}
```

### ModifyBlueprint

修改现有蓝图。

**参数**：

- `AssetPath` (string): 蓝图路径
- `Operation` (string): 操作类型
  - `add_variable` - 添加变量
  - `reparent` - 更改父类
- `PayloadJson` (string): 操作参数 JSON

**示例 - 添加变量**：

```json
{
  "AssetPath": "/Game/BP_MyActor",
  "Operation": "add_variable",
  "PayloadJson": "{\"name\":\"Health\",\"type\":\"float\"}"
}
```

**示例 - 更改父类**：

```json
{
  "AssetPath": "/Game/BP_MyActor",
  "Operation": "reparent",
  "PayloadJson": "{\"parentClassPath\":\"/Script/Engine.Pawn\"}"
}
```

### SaveBlueprints

保存蓝图到磁盘。

**参数**：

- `AssetPaths` (array): 要保存的蓝图路径列表

**返回**：

```json
{
  "success": true,
  "operation": "SaveBlueprints",
  "savedCount": 2,
  "failedCount": 0,
  "saved": ["/Game/BP_Actor1", "/Game/BP_Actor2"]
}
```

---

## 🐛 故障排查

### 编译错误

**问题**: 找不到 RemoteControlCommon 模块

**解决**:

1. 确认 Remote Control 插件已启用
2. 重新生成项目文件
3. 清理并重新编译

### 连接失败

**问题**: HTTP 请求返回 404 或超时

**解决**:

1. 确认 Remote Control Web Server 已启用
2. 确认端口为 30010
3. 确认编辑器正在运行
4. 检查防火墙设置

### Subsystem 未找到

**问题**: `Object not found: /Script/BlueprintToAI.Default__BlueprintToAISubsystem`

**解决**:

1. 确认插件已编译
2. 确认插件已启用（Edit → Plugins）
3. 重启编辑器
4. 检查 Output Log 是否有初始化日志

---

## 📊 性能基准

在 UE 5.6 上的测试结果：

| 操作                       | 耗时    | 说明     |
| -------------------------- | ------- | -------- |
| ExtractBlueprint (Minimal) | < 100ms | 小型蓝图 |
| ExtractBlueprint (Compact) | < 500ms | 中型蓝图 |
| ExtractBlueprint (Full)    | < 2s    | 大型蓝图 |
| CreateBlueprint            | < 200ms | 空蓝图   |
| ModifyBlueprint            | < 100ms | 单个操作 |
| SaveBlueprints             | < 500ms | 单个蓝图 |

---

## 🗺️ 开发路线图

### Phase 1: 核心功能 ✅ (已完成)

- [x] 插件骨架
- [x] ExtractBlueprint (3 种模式)
- [x] CreateBlueprint
- [x] ModifyBlueprint (add_variable, reparent)
- [x] SaveBlueprints
- [x] 完整测试套件

### Phase 2: DSL 支持 🚧 (进行中)

- [ ] DSL 解析器
- [ ] 支持 Event 节点
- [ ] 支持 CallFunction 节点
- [ ] 支持 Variable 节点
- [ ] 支持 Cast 节点
- [ ] 支持 Branch 节点

### Phase 3: 高级功能 📅 (计划中)

- [ ] 添加组件
- [ ] 添加函数
- [ ] 修改图表（DSL）
- [ ] 更多节点类型

### Phase 4: 多版本支持 📅 (计划中)

- [ ] UE 5.4
- [ ] UE 5.0
- [ ] UE 4.27

---

## 📄 许可证

MIT License - Copyright (c) 2025 HUTAO

---

## 🤝 贡献

欢迎贡献！这是一个专注于蓝图 AI 操作的插件。

---

**作者**: HUTAO  
**版本**: 1.0.0  
**日期**: 2025-01-XX  
**引擎**: Unreal Engine 5.6.0+
