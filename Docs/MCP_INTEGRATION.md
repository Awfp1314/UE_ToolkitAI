# MCP 集成指南

## 概述

UE Toolkit 的 AI 助手现在支持标准的 MCP (Model Context Protocol) 协议，可以动态发现和调用 Blueprint Extractor 插件的所有工具。

## 架构

```
AI 助手 (ChatWindow)
    ↓
MCP Client (动态工具发现)
    ↓
Blueprint Extractor MCP Bridge (stdio 协议)
    ↓
UE Editor HTTP API (Blueprint Extractor 插件)
```

## 文件结构

```
scripts/mcp_servers/
├── blueprint_extractor_bridge.py    # MCP 桥接服务器
└── blueprint_extractor_tools.json   # 工具定义文件（26 个工具）

config/
└── mcp_config_template.json         # MCP 配置模板
```

## 配置步骤

### 1. 确保 Blueprint Extractor 插件正常运行

```bash
# 测试插件连接
python test_ue_connection.py
```

### 2. 配置 MCP Server

将 `config/mcp_config_template.json` 复制到 AI 助手的配置目录：

```bash
# Windows
copy config\mcp_config_template.json %APPDATA%\ue_toolkit\mcp.json

# 或者直接在 AI 助手设置中配置
```

### 3. 测试 MCP Bridge

```bash
# 手动测试 MCP 桥接服务器
python scripts/mcp_servers/blueprint_extractor_bridge.py

# 发送测试请求（stdin）
{"jsonrpc":"2.0","id":1,"method":"initialize","params":{}}
{"jsonrpc":"2.0","id":2,"method":"tools/list","params":{}}
```

### 4. 在 AI 助手中使用

启动 UE Toolkit，打开 AI 助手，直接询问：

```
用户：帮我提取当前打开的蓝图
AI：好的，我来调用 ExtractActiveBlueprint 工具...
```

AI 会自动：

1. 发现 Blueprint Extractor 的 26 个工具
2. 根据用户需求选择合适的工具
3. 调用工具并返回结果

## 可用工具列表

### 免费工具（18 个，只读操作）

1. **ExtractBlueprint** - 提取指定蓝图的结构
2. **ExtractActiveBlueprint** - 提取当前打开的蓝图
3. **GetActiveBlueprint** - 获取当前活动蓝图路径
4. **ExtractWidgetBlueprint** - 提取 UMG Widget
5. **ExtractMaterial** - 提取材质
6. **SearchAssets** - 搜索资产
7. **ListAssets** - 列出资产
8. **GetEditorContext** - 获取编辑器上下文
9. **ExtractDataTable** - 提取数据表
10. **ExtractEnum** - 提取枚举
11. **ExtractStruct** - 提取结构体
12. **ExtractAnimBlueprint** - 提取动画蓝图
13. **ExtractBehaviorTree** - 提取行为树
14. **ExtractBlackboard** - 提取黑板
15. **ExtractStateMachine** - 提取状态机
16. **ExtractAnimMontage** - 提取动画蒙太奇
17. **ExtractAnimSequence** - 提取动画序列
18. **ExtractSoundCue** - 提取声音提示

### 付费工具（10 个，创建/修改操作）

19. **CreateBlueprint** - 创建新蓝图
20. **ModifyBlueprintMembers** - 修改蓝图成员
21. **AddBlueprintVariable** - 添加蓝图变量
22. **AddBlueprintFunction** - 添加蓝图函数
23. **CreateWidgetBlueprint** - 创建 Widget 蓝图
24. **ModifyWidget** - 修改 Widget
25. **SaveAssets** - 保存资产
26. **ImportTexture** - 导入纹理
27. **StartPIE** - 启动 PIE
28. **StopPIE** - 停止 PIE

## 权限控制

权限控制在 UE 插件层实现（通过许可证检查），MCP Bridge 只负责转发错误消息。

付费工具调用时，如果许可证无效，插件会返回：

```json
{
  "status": "error",
  "message": "此功能需要付费许可证",
  "locked": true,
  "tier": "pro"
}
```

## 自动批准

在 `mcp.json` 中配置 `autoApprove` 列表，这些工具调用时不需要用户确认：

```json
{
  "autoApprove": ["ExtractBlueprint", "GetEditorContext", "SearchAssets"]
}
```

## 故障排查

### 1. MCP Bridge 无法启动

检查 Python 环境和依赖：

```bash
python --version  # 需要 Python 3.8+
pip install requests
```

### 2. 工具调用失败

查看日志：

```bash
# MCP Bridge 日志
logs/mcp/blueprint_extractor_bridge.log

# AI 助手日志
logs/runtime/ue_toolkit.log
```

### 3. UE 编辑器连接失败

确保：

- UE 编辑器正在运行
- Blueprint Extractor 插件已启用
- HTTP 服务器监听 30010 端口

## 开发指南

### 添加新工具

1. 在 UE 插件中实现新的 Subsystem 函数
2. 更新 `blueprint_extractor_tools.json`，添加工具定义
3. 重启 MCP Bridge（AI 助手会自动重新发现工具）

### 修改工具定义

编辑 `scripts/mcp_servers/blueprint_extractor_tools.json`：

```json
{
  "name": "MyNewTool",
  "description": "工具描述",
  "inputSchema": {
    "type": "object",
    "properties": {
      "param1": {
        "type": "string",
        "description": "参数描述"
      }
    },
    "required": ["param1"]
  }
}
```

### 调试 MCP 协议

启用详细日志：

```python
# 在 blueprint_extractor_bridge.py 中
logging.basicConfig(level=logging.DEBUG)
```

## 性能优化

### 1. 工具结果截断

大型蓝图数据会被自动截断（8000 字符），建议使用 `Scope: "Minimal"` 参数：

```
用户：用最小模式提取蓝图
AI：好的，我会使用 Scope="Minimal" 参数
```

### 2. 批量操作

对于多个资产的操作，建议使用批量工具（如 `SearchAssets` + 过滤）而不是逐个调用。

## 未来计划

- [ ] 支持 SSE 协议（实时推送）
- [ ] 支持工具组合（Pipeline）
- [ ] 支持自定义工具插件
- [ ] 集成更多 UE 插件（Niagara、Sequencer 等）

## 参考资料

- [MCP 协议规范](https://modelcontextprotocol.io/)
- [Blueprint Extractor 插件文档](../Plugins/BLUEPRINT_EXTRACTOR_INTEGRATION.md)
- [AI 助手开发指南](../core/README.md)
