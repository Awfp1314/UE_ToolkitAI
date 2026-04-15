# MCP 集成测试指南

## ✅ 集成状态

MCP (Model Context Protocol) 已成功集成到 AI 助手中！

从日志可以看到：

- ✅ MCP Client 启动成功，发现 28 个工具
- ✅ MCP Server 'blueprint-extractor' 启动成功
- ✅ 工具注册表共注册 34 个工具（6 个内置 + 28 个 MCP）

## 🚀 快速测试

### 1. 确保 UE 编辑器正在运行

```bash
# 启动 UE 编辑器
# 确保 Blueprint Extractor 插件已启用
```

### 2. 启动 UE Toolkit

```bash
python main.py
```

### 3. 打开 AI 助手

点击左侧导航栏的 "AI 助手" 按钮

### 4. 测试工具调用

尝试以下对话：

#### 测试 1：获取编辑器上下文

```
用户：帮我查看一下当前 UE 编辑器的状态

AI：好的，我来获取编辑器上下文...
[自动调用 GetEditorContext 工具]
```

#### 测试 2：搜索资产

```
用户：搜索所有包含 "Character" 的蓝图

AI：我来搜索...
[自动调用 SearchAssets 工具]
```

#### 测试 3：提取蓝图

```
用户：帮我提取当前打开的蓝图

AI：好的，我来提取...
[自动调用 ExtractActiveBlueprint 工具]
```

#### 测试 4：使用 Minimal 模式

```
用户：用最小模式提取 /Game/Blueprints/BP_Character

AI：好的，我会使用 Scope="Minimal" 参数...
[自动调用 ExtractBlueprint 工具，参数包含 Scope: "Minimal"]
```

## 📊 验证工具发现

查看日志文件 `logs/runtime/ue_toolkit.log`，应该看到：

```
MCP Client 启动成功，发现 28 个工具
MCP Server 'blueprint-extractor' 启动成功
从 MCP 注册了 28 个工具
工具注册表初始化完成，共注册 34 个工具
```

## 🔍 可用的 MCP 工具

### 免费工具（18 个）

1. ExtractBlueprint - 提取蓝图结构
2. ExtractActiveBlueprint - 提取当前打开的蓝图
3. GetActiveBlueprint - 获取当前活动蓝图路径
4. ExtractWidgetBlueprint - 提取 UMG Widget
5. ExtractMaterial - 提取材质
6. SearchAssets - 搜索资产
7. ListAssets - 列出资产
8. GetEditorContext - 获取编辑器上下文
9. ExtractDataTable - 提取数据表
10. ExtractEnum - 提取枚举
11. ExtractStruct - 提取结构体
12. ExtractAnimBlueprint - 提取动画蓝图
13. ExtractBehaviorTree - 提取行为树
14. ExtractBlackboard - 提取黑板
15. ExtractStateMachine - 提取状态机
16. ExtractAnimMontage - 提取动画蒙太奇
17. ExtractAnimSequence - 提取动画序列
18. ExtractSoundCue - 提取声音提示

### 付费工具（10 个）

19. CreateBlueprint - 创建新蓝图
20. ModifyBlueprintMembers - 修改蓝图成员
21. AddBlueprintVariable - 添加蓝图变量
22. AddBlueprintFunction - 添加蓝图函数
23. CreateWidgetBlueprint - 创建 Widget 蓝图
24. ModifyWidget - 修改 Widget
25. SaveAssets - 保存资产
26. ImportTexture - 导入纹理
27. StartPIE - 启动 PIE
28. StopPIE - 停止 PIE

## 🐛 故障排查

### 问题 1：MCP Server 未启动

**症状**：日志中没有 "MCP Client 启动成功" 的消息

**解决方案**：

1. 检查 `config/mcp_config.json` 是否存在
2. 检查 Python 路径是否正确
3. 查看 `logs/mcp/blueprint_extractor_bridge.log`

### 问题 2：工具调用失败

**症状**：AI 调用工具时返回连接错误

**解决方案**：

1. 确保 UE 编辑器正在运行
2. 确保 Blueprint Extractor 插件已启用
3. 测试连接：`python test_ue_connection.py`

### 问题 3：工具未被发现

**症状**：日志显示 "发现 0 个工具"

**解决方案**：

1. 检查 `scripts/mcp_servers/blueprint_extractor_tools.json` 是否存在
2. 检查 JSON 文件格式是否正确
3. 重启 UE Toolkit

## 📝 配置文件位置

- MCP 配置：`config/mcp_config.json`
- 工具定义：`scripts/mcp_servers/blueprint_extractor_tools.json`
- MCP Bridge：`scripts/mcp_servers/blueprint_extractor_bridge.py`
- MCP 日志：`logs/mcp/blueprint_extractor_bridge.log`

## 🎯 下一步

1. ✅ MCP 集成完成
2. ✅ 28 个工具自动发现
3. ✅ AI 可以自动调用工具
4. ⏭️ 测试各种工具调用场景
5. ⏭️ 优化工具描述和参数
6. ⏭️ 添加更多 MCP Server（如 Niagara、Sequencer 等）

## 💡 使用技巧

1. **使用 Minimal 模式**：对于大型蓝图，明确要求 AI 使用 `Scope: "Minimal"` 参数
2. **组合工具**：AI 可以自动组合多个工具，如先搜索再提取
3. **自然语言**：直接用自然语言描述需求，AI 会自动选择合适的工具
4. **查看日志**：遇到问题时查看 `logs/runtime/ue_toolkit.log` 和 `logs/mcp/blueprint_extractor_bridge.log`

## 🎉 成功标志

如果看到以下日志，说明 MCP 集成成功：

```
MCP Client 启动成功，发现 28 个工具
MCP Server 'blueprint-extractor' 启动成功
从 MCP 注册了 28 个工具
工具注册表初始化完成，共注册 34 个工具
```

现在你可以直接询问 AI，它会自动调用合适的工具来回答你的问题！
