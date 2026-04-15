# Blueprint Extractor MCP Bridge

将 Blueprint Extractor 插件的 HTTP API 包装为标准 MCP (Model Context Protocol) Server。

## 快速开始

### 1. 测试 MCP Bridge

```bash
# 运行测试脚本
python test_mcp_bridge.py
```

### 2. 手动启动 MCP Bridge

```bash
# 启动服务器（stdio 模式）
python scripts/mcp_servers/blueprint_extractor_bridge.py

# 或指定自定义 URL
python scripts/mcp_servers/blueprint_extractor_bridge.py --base-url http://127.0.0.1:30010
```

### 3. 配置 AI 助手

将 `config/mcp_config_template.json` 复制到 AI 助手配置目录：

```bash
# Windows
copy config\mcp_config_template.json %APPDATA%\ue_toolkit\mcp.json
```

或在 AI 助手设置界面中配置 MCP Server。

## 文件说明

- `blueprint_extractor_bridge.py` - MCP 桥接服务器主程序
- `blueprint_extractor_tools.json` - 工具定义文件（28 个工具）
- `README.md` - 本文件

## MCP 协议

### 请求格式

```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "method": "tools/call",
  "params": {
    "name": "ExtractBlueprint",
    "arguments": {
      "AssetPath": "/Game/Blueprints/BP_Character",
      "Scope": "Minimal"
    }
  }
}
```

### 响应格式

```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "result": {
    "content": [
      {
        "type": "text",
        "text": "{\"ReturnValue\": \"...\"}"
      }
    ]
  }
}
```

## 支持的方法

- `initialize` - 初始化 MCP 连接
- `tools/list` - 获取所有可用工具列表
- `tools/call` - 调用指定工具

## 日志

日志文件位置：`logs/mcp/blueprint_extractor_bridge.log`

## 故障排查

### 问题：MCP Bridge 无法启动

**解决方案**：

1. 检查 Python 版本（需要 3.8+）
2. 安装依赖：`pip install requests`

### 问题：工具调用失败

**解决方案**：

1. 确保 UE 编辑器正在运行
2. 确保 Blueprint Extractor 插件已启用
3. 检查 HTTP 端口（默认 30010）

### 问题：权限错误

**解决方案**：
付费工具需要有效的许可证，权限检查在 UE 插件层实现。

## 开发

### 添加新工具

1. 在 `blueprint_extractor_tools.json` 中添加工具定义
2. 重启 MCP Bridge
3. AI 助手会自动发现新工具

### 修改工具定义

编辑 `blueprint_extractor_tools.json`，格式：

```json
{
  "name": "ToolName",
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

## 参考资料

- [MCP 协议规范](https://modelcontextprotocol.io/)
- [Blueprint Extractor 插件文档](../../Plugins/BLUEPRINT_EXTRACTOR_INTEGRATION.md)
- [MCP 集成指南](../../Docs/MCP_INTEGRATION.md)
