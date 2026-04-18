# DSML 格式问题分析与修复

## 问题描述

AI 助手在调用蓝图分析工具时，输出 DSML 格式而不是标准的 OpenAI Function Calling 格式：

```
<｜DSML｜function_calls>
<｜DSML｜invoke name="AnalyzeBlueprint">
<｜DSML｜function_arg name="asset_path">
/Game/NewBlueprint
</｜DSML｜function_arg>
</｜DSML｜invoke>
</｜DSML｜function_calls>
```

## 问题分析

### 1. 根本原因

根据用户描述：

- 插件最初使用标准 Function Calling 格式，DeepSeek 模型工作正常
- 后来为了支持"创建蓝图变量"功能，添加了 DSML 格式支持
- DSML 格式现在污染了对话历史，导致模型继续使用 DSML

### 2. 技术细节

**代码中的 DSML 支持：**

- `dsml_parser.py` - DSML 格式解析器
- `function_calling_coordinator.py` - 检测并解析 DSML 作为后备方案
- 系统提示词已清理，不再包含 DSML 引用

**工具注册问题：**

- 存在两套蓝图分析工具：
  1. `analyze_blueprint` (Blueprint Analyzer 客户端)
  2. `ExtractBlueprint` (MCP 工具)
- AI 混淆了工具名称，编造了不存在的 `AnalyzeBlueprint`

**为什么 GetEditorContext 正常工作：**

- `GetEditorContext` 是 MCP 工具，没有重复定义
- 没有历史 DSML 污染
- 工具名称清晰明确

## 已实施的修复

### 1. 增强系统提示词 (config.py)

**添加了明确的工具调用格式要求：**

```python
- **工具调用格式要求**：
  - ✅ 使用标准的 Function Calling 格式（OpenAI tool_calls 格式）
  - ✅ 工具名称必须与工具定义完全一致（区分大小写）
  - ✅ 参数名称必须与工具定义完全一致
  - ❌ 不要使用任何自定义标记格式
  - ❌ 不要编造不存在的工具名称
```

**明确列出可用工具及其精确名称：**

```python
**可用工具：**
- `get_ue_editor_context` - 获取编辑器状态
- `analyze_blueprint` - 分析普通蓝图
- `analyze_widget_blueprint` - 分析 UMG Widget 蓝图

**使用示例：**
- 用户："我现在打开了什么蓝图" → 调用 `get_ue_editor_context()`
- 用户："帮我看看 BP_Character 蓝图" → 调用 `analyze_blueprint(asset_path="/Game/Blueprints/BP_Character")`
```

### 2. 增强调试日志 (function_calling_coordinator.py)

**DSML 检测时输出详细警告：**

```python
self.logger.warning(f"[DSML检测] ⚠️ 检测到 DSML 格式输出！")
self.logger.warning(f"[DSML检测] 内容预览: {accumulated_content[:500]}")
self.logger.warning(f"[DSML检测] 可能原因：1) 对话历史污染 2) 工具定义不清晰 3) 模型配置问题")
```

### 3. 工具名称冲突检测 (api_llm_client.py)

**检测并警告重复的蓝图工具：**

```python
blueprint_tools = [name for name in tool_names if 'blueprint' in name.lower()]
if len(blueprint_tools) > 1:
    print(f"[WARNING] 检测到多个蓝图相关工具，可能导致混淆: {blueprint_tools}")
```

## 建议的进一步措施

### 1. 清理对话历史（最重要）

**问题：** 对话历史中可能包含 DSML 格式的示例，污染了模型的输出

**解决方案：**

- 建议用户开启新对话测试
- 或者实现对话历史清理功能，移除包含 DSML 的消息

### 2. 统一工具命名

**当前状态：**

- `analyze_blueprint` (Blueprint Analyzer)
- `ExtractBlueprint` (MCP)

**建议：**

- 禁用其中一个工具，避免混淆
- 或者重命名使其功能更明确（如 `analyze_blueprint_http` vs `extract_blueprint_mcp`）

### 3. 移除 DSML 支持（可选）

如果不再需要 DSML 格式：

1. 删除 `dsml_parser.py`
2. 从 `function_calling_coordinator.py` 移除 DSML 检测代码
3. 这样可以强制模型使用标准格式

### 4. 添加工具调用验证

在 `tools_registry.py` 的 `dispatch` 方法中：

```python
# 检查工具名称是否存在
if tool_name not in self.tools:
    available_tools = list(self.tools.keys())
    similar_tools = [t for t in available_tools if tool_name.lower() in t.lower() or t.lower() in tool_name.lower()]

    error_msg = f"工具 '{tool_name}' 不存在。"
    if similar_tools:
        error_msg += f"\n您是否想使用：{', '.join(similar_tools)}？"
    else:
        error_msg += f"\n可用工具：{', '.join(available_tools[:5])}"

    return {"success": False, "error": error_msg}
```

## 测试建议

### 测试步骤：

1. **清理测试：**
   - 开启新对话（清空历史）
   - 发送："分析 NewBlueprint 蓝图"
   - 检查日志中是否还有 DSML 警告

2. **工具名称测试：**
   - 检查日志中的工具列表
   - 确认是否有重复的蓝图工具
   - 记录 AI 实际调用的工具名称

3. **对比测试：**
   - 测试 `GetEditorContext`（已知正常）
   - 测试 `analyze_blueprint`（问题工具）
   - 对比两者的调用过程差异

### 预期结果：

**成功标志：**

- 日志中不再出现 DSML 警告
- AI 使用正确的工具名称（`analyze_blueprint` 而不是 `AnalyzeBlueprint`）
- 工具调用成功返回结果

**如果仍然失败：**

- 检查对话历史是否已清理
- 检查是否有多个同名工具
- 考虑临时禁用 MCP 的 `ExtractBlueprint` 工具

## 总结

这个问题的核心是：

1. **历史污染** - 旧的 DSML 格式示例影响了模型行为
2. **工具混淆** - 多个相似的蓝图工具导致命名混乱
3. **缺乏明确指导** - 系统提示词没有明确说明工具名称和格式

修复措施：

1. ✅ 增强系统提示词，明确工具名称和格式
2. ✅ 添加详细的调试日志
3. ✅ 检测工具名称冲突
4. 🔄 建议清理对话历史（需要用户操作）
5. 🔄 考虑统一或禁用重复工具（需要进一步决策）
