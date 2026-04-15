# Spec: 集成 blueprint-extractor 插件到 UE Toolkit

## 目标

将开源项目 `blueprint-extractor` 集成到 UE Toolkit 中，替换现有的 `BlueprintToAI` 插件，并实现基于 License 的功能分级（免费版 vs 付费版）。

## 背景

- 现有 `BlueprintToAI` 插件功能有限，且存在崩溃问题
- `blueprint-extractor` 是成熟的开源项目，支持 112 个工具，覆盖 Blueprint、UMG、Material、AI 资产等
- 需要实现商业化：免费版只读，付费版完整功能
- 所有权限控制在 Python 层实现，不修改插件源码（保持开源合规）

## 商业模式

### 免费版（18 个工具）

- ✅ 所有 Extract\* 工具（读取蓝图、UMG、Material 等）
- ✅ SearchAssets、ListAssets
- ✅ GetEditorContext
- ❌ 创建/修改/保存功能

### 付费版（94 个工具）

- ✅ 所有免费功能
- ✅ 所有 Create*/Modify* 工具
- ✅ SaveAssets
- ✅ Import\* 工具
- ✅ Capture\* 验证工具
- ✅ PIE 控制、LiveCoding 等

## 架构

```
用户 → AI 助手 → Tools Registry → Feature Gate (权限检查) → UE Tool Client (HTTP) → blueprint-extractor Subsystem → UE Editor
```

## 任务列表

### Task 1: 准备插件文件

**优先级**: P0  
**预计时间**: 10 分钟

**描述**: 将 blueprint-extractor 插件移动到正确位置，删除旧插件

**验收标准**:

- [ ] `Plugins/BlueprintExtractor/` 目录存在
- [ ] `Plugins/BlueprintToAI/` 目录已删除
- [ ] `Plugins/temp_blueprint_extractor/` 目录已删除

**实现步骤**:

1. 重命名 `Plugins/temp_blueprint_extractor/BlueprintExtractor` 为 `Plugins/BlueprintExtractor`
2. 删除 `Plugins/BlueprintToAI/` 目录
3. 删除 `Plugins/temp_blueprint_extractor/` 目录
4. 保留 `Plugins/BlueprintExtractor/` 中的 LICENSE 文件

---

### Task 2: 更新 UE Tool Client

**优先级**: P0  
**预计时间**: 5 分钟

**描述**: 修改 HTTP 客户端，使用 blueprint-extractor 的 Subsystem 路径

**验收标准**:

- [ ] `ue_tool_client.py` 中的 subsystem_path 已更新
- [ ] 连接测试通过

**实现步骤**:

1. 打开 `modules/ai_assistant/clients/ue_tool_client.py`
2. 找到 `subsystem_path` 定义
3. 修改为: `/Script/BlueprintExtractor.Default__BlueprintExtractorSubsystem`

**代码位置**:

```python
# modules/ai_assistant/clients/ue_tool_client.py
# 第 80 行左右

subsystem_path = "/Script/BlueprintExtractor.Default__BlueprintExtractorSubsystem"
```

---

### Task 3: 集成 Feature Gate 到 Tools Registry

**优先级**: P0  
**预计时间**: 15 分钟

**描述**: 在工具注册表中集成权限控制，阻止未授权用户使用付费功能

**验收标准**:

- [ ] `tools_registry.py` 初始化时创建 `feature_gate` 实例
- [ ] `dispatch` 方法中添加权限检查
- [ ] 未授权时返回友好的错误信息

**实现步骤**:

1. 在 `ToolsRegistry.__init__` 中添加:

   ```python
   from modules.ai_assistant.logic.feature_gate import UEFeatureGate
   from core.security.license_manager import LicenseManager

   license_manager = LicenseManager()
   self.feature_gate = UEFeatureGate(license_manager)
   ```

2. 在 `dispatch` 方法开头添加权限检查:
   ```python
   # 权限检查（跳过非 UE 工具）
   if tool_name in self.feature_gate.FREE_TOOLS or tool_name in self.feature_gate.PRO_TOOLS:
       if not self.feature_gate.is_tool_allowed(tool_name):
           return {
               "success": False,
               "error": self.feature_gate.get_blocked_reason(tool_name),
               "locked": True,
               "tier": "pro"
           }
   ```

**代码位置**:

- `modules/ai_assistant/logic/tools_registry.py`
- `__init__` 方法（约第 150 行）
- `dispatch` 方法（约第 300 行）

---

### Task 4: 注册 blueprint-extractor 工具

**优先级**: P0  
**预计时间**: 30 分钟

**描述**: 注册 blueprint-extractor 的核心工具到工具注册表

**验收标准**:

- [ ] 至少注册 20 个核心工具
- [ ] 工具描述清晰，参数完整
- [ ] 免费工具和付费工具都已注册

**实现步骤**:

1. 在 `tools_registry.py` 中添加新方法 `_register_blueprint_extractor_tools()`
2. 在 `__init__` 中调用此方法
3. 注册以下核心工具:

**免费工具（优先）**:

- `ExtractBlueprint` - 提取蓝图结构
- `ExtractWidgetBlueprint` - 提取 UMG
- `ExtractMaterial` - 提取材质
- `SearchAssets` - 搜索资产
- `ListAssets` - 列出资产
- `GetActiveBlueprint` - 获取当前激活的蓝图
- `ExtractActiveBlueprint` - 提取当前激活的蓝图

**付费工具（优先）**:

- `CreateBlueprint` - 创建蓝图
- `ModifyBlueprintMembers` - 修改蓝图成员
- `CreateWidgetBlueprint` - 创建 UMG
- `ModifyWidget` - 修改 UMG
- `SaveAssets` - 保存资产

**工具注册模板**:

```python
self.register_tool(ToolDefinition(
    name="ExtractBlueprint",
    description="提取蓝图结构到 JSON（免费功能）",
    parameters={
        "type": "object",
        "properties": {
            "AssetPath": {"type": "string", "description": "资产路径"},
            "Scope": {"type": "string", "enum": ["Minimal", "Compact", "Full"], "default": "Compact"}
        },
        "required": ["AssetPath"]
    },
    function=lambda **kwargs: self._execute_ue_python_tool("ExtractBlueprint", **kwargs),
    requires_confirmation=False
))
```

**参考文档**:

- `Plugins/BlueprintExtractor/README.md` - 工具列表
- `Plugins/BLUEPRINT_EXTRACTOR_INTEGRATION.md` - 集成指南

**代码位置**:

- `modules/ai_assistant/logic/tools_registry.py`
- 新增方法 `_register_blueprint_extractor_tools()`（约第 900 行）

---

### Task 5: 更新 Feature Gate 工具列表

**优先级**: P1  
**预计时间**: 10 分钟

**描述**: 确保 `feature_gate.py` 中的工具列表与 blueprint-extractor 一致

**验收标准**:

- [ ] `FREE_TOOLS` 包含所有 Extract\* 工具
- [ ] `PRO_TOOLS` 包含所有 Create*/Modify*/Save\* 工具
- [ ] 工具名称与 blueprint-extractor 一致

**实现步骤**:

1. 打开 `modules/ai_assistant/logic/feature_gate.py`
2. 检查 `FREE_TOOLS` 和 `PRO_TOOLS` 集合
3. 根据 blueprint-extractor 文档更新工具列表
4. 确保工具名称大小写一致（blueprint-extractor 使用 PascalCase）

**参考**:

- `Plugins/BlueprintExtractor/README.md` - 完整工具列表
- `Plugins/BLUEPRINT_EXTRACTOR_INTEGRATION.md` - 功能分级

**代码位置**:

- `modules/ai_assistant/logic/feature_gate.py`
- `FREE_TOOLS` 集合（约第 20 行）
- `PRO_TOOLS` 集合（约第 40 行）

---

### Task 6: 删除旧的 UE 工具注册

**优先级**: P1  
**预计时间**: 5 分钟

**描述**: 删除 `tools_registry.py` 中旧的 BlueprintToAI 工具注册代码

**验收标准**:

- [ ] `_register_ue_tools()` 方法已删除或清空
- [ ] 不再有对 BlueprintToAI 的引用

**实现步骤**:

1. 打开 `modules/ai_assistant/logic/tools_registry.py`
2. 找到 `_register_ue_tools()` 方法
3. 删除方法内容，或用新的 `_register_blueprint_extractor_tools()` 替换
4. 搜索 "BlueprintToAI" 确保没有残留引用

**代码位置**:

- `modules/ai_assistant/logic/tools_registry.py`
- `_register_ue_tools()` 方法（约第 800 行）

---

### Task 7: 测试免费功能

**优先级**: P0  
**预计时间**: 15 分钟

**描述**: 测试免费版功能是否正常工作

**验收标准**:

- [ ] 未激活时可以使用 ExtractBlueprint
- [ ] 未激活时可以使用 SearchAssets
- [ ] 未激活时可以使用 GetActiveBlueprint
- [ ] 提取的 JSON 数据完整

**测试步骤**:

1. 确保 License 未激活（或使用测试账号）
2. 启动 UE 编辑器并打开测试项目
3. 启动 UE Toolkit
4. 在 AI 助手中测试:
   - "帮我提取 /Game/Blueprints/BP_Character 的结构"
   - "搜索所有蓝图资产"
   - "分析当前打开的蓝图"
5. 验证返回的 JSON 数据格式正确

**测试脚本**:

```python
# test_free_tools.py
from modules.ai_assistant.logic.tools_registry import ToolsRegistry

registry = ToolsRegistry()

# 测试提取蓝图
result = registry.dispatch("ExtractBlueprint", {
    "AssetPath": "/Game/Blueprints/BP_Character",
    "Scope": "Compact"
})
print(result)
```

---

### Task 8: 测试付费功能阻止

**优先级**: P0  
**预计时间**: 10 分钟

**描述**: 测试未激活时付费功能被正确阻止

**验收标准**:

- [ ] 未激活时调用 CreateBlueprint 返回错误
- [ ] 错误信息友好，提示需要激活
- [ ] 错误信息包含 `locked: true` 和 `tier: "pro"`

**测试步骤**:

1. 确保 License 未激活
2. 在 AI 助手中测试:
   - "帮我创建一个新的蓝图"
   - "修改这个蓝图的变量"
   - "保存所有修改"
3. 验证返回错误信息
4. 验证 AI 给出友好提示

**测试脚本**:

```python
# test_pro_tools_blocked.py
from modules.ai_assistant.logic.tools_registry import ToolsRegistry

registry = ToolsRegistry()

# 测试创建蓝图（应该被阻止）
result = registry.dispatch("CreateBlueprint", {
    "AssetPath": "/Game/Test/BP_Test",
    "ParentClass": "/Script/Engine.Actor"
})

assert result["success"] == False
assert result["locked"] == True
assert "付费功能" in result["error"]
print("✅ 付费功能阻止测试通过")
```

---

### Task 9: 测试激活后的付费功能

**优先级**: P1  
**预计时间**: 15 分钟

**描述**: 测试激活后付费功能是否正常工作

**验收标准**:

- [ ] 激活后可以使用 CreateBlueprint
- [ ] 激活后可以使用 ModifyBlueprintMembers
- [ ] 激活后可以使用 SaveAssets
- [ ] 创建的资产在 UE 编辑器中可见

**测试步骤**:

1. 激活 License（使用测试激活码）
2. 在 AI 助手中测试:
   - "创建一个新的 Actor 蓝图 /Game/Test/BP_TestActor"
   - "给这个蓝图添加一个 float 变量 Speed"
   - "保存这个蓝图"
3. 在 UE 编辑器中验证资产已创建

**测试脚本**:

```python
# test_pro_tools_activated.py
from modules.ai_assistant.logic.tools_registry import ToolsRegistry
from core.security.license_manager import LicenseManager

# 激活 License
license_manager = LicenseManager()
license_manager.activate("TEST_ACTIVATION_KEY")

registry = ToolsRegistry()

# 测试创建蓝图
result = registry.dispatch("CreateBlueprint", {
    "AssetPath": "/Game/Test/BP_TestActor",
    "ParentClass": "/Script/Engine.Actor"
})

assert result["success"] == True
print("✅ 付费功能激活测试通过")
```

---

### Task 10: 更新文档

**优先级**: P2  
**预计时间**: 20 分钟

**描述**: 更新用户文档，说明新的功能和限制

**验收标准**:

- [ ] README.md 中添加 blueprint-extractor 说明
- [ ] 添加第三方组件声明
- [ ] 更新功能列表（免费 vs 付费）

**实现步骤**:

1. 在 README.md 中添加:

   ```markdown
   ## 第三方组件

   本软件集成了以下开源项目：

   - **blueprint-extractor**
     - 作者：SunGrow
     - 许可证：MIT License
     - 仓库：https://github.com/SunGrow/ue-blueprint-extractor
     - 用途：提供 UE 资产操作能力
   ```

2. 更新功能说明:

   ```markdown
   ### AI 助手 - UE 资产操作

   #### 免费功能

   - ✅ 读取和分析蓝图结构
   - ✅ 查看 UMG、Material 等资产
   - ✅ 搜索和列出资产

   #### Pro 功能

   - ✨ 创建和修改所有资产类型
   - ✨ 保存资产
   - ✨ 导入外部资源
   - ✨ 可视化验证和调试
   ```

**代码位置**:

- `README.md`
- 新增章节 "第三方组件"
- 更新章节 "AI 助手"

---

### Task 11: 清理临时文件

**优先级**: P2  
**预计时间**: 5 分钟

**描述**: 删除不再需要的文档和测试文件

**验收标准**:

- [ ] 旧的设计文档已删除
- [ ] 旧的测试脚本已删除
- [ ] 保留必要的集成文档

**实现步骤**:

1. 删除以下文件:
   - `Plugins/BlueprintToAI_Design.md`
   - `Plugins/BLUEPRINT_EXTRACTOR_ANALYSIS.md`
   - `Plugins/BlueprintToAI/README.md`
   - `Plugins/BlueprintToAI/TESTING_UE56.md`
   - `test_blueprint_plugin.py`
   - `test_active_blueprint.py`
   - `test_add_variable_fixed.py`

2. 保留以下文件:
   - `Plugins/BLUEPRINT_EXTRACTOR_INTEGRATION.md`（集成指南）
   - `Plugins/BlueprintExtractor/README.md`（官方文档）
   - `Plugins/BlueprintExtractor/LICENSE`（开源许可证）

---

## 依赖关系

```
Task 1 (准备插件) → Task 2 (更新客户端) → Task 3 (集成权限) → Task 4 (注册工具)
                                                                    ↓
Task 5 (更新工具列表) ← Task 6 (删除旧代码) ← Task 7 (测试免费) ← Task 8 (测试阻止)
                                                                    ↓
                                                            Task 9 (测试付费)
                                                                    ↓
                                                Task 10 (更新文档) → Task 11 (清理)
```

## 风险和注意事项

1. **版本兼容性**: blueprint-extractor 只支持 UE 5.6 和 5.7
   - 短期：先支持 5.6
   - 长期：根据用户需求适配其他版本

2. **开源合规**: 不修改插件源码
   - 所有权限控制在 Python 层
   - 保留原始 LICENSE 文件
   - 添加第三方声明

3. **工具名称**: blueprint-extractor 使用 PascalCase
   - 确保 Python 代码中的工具名称大小写一致
   - 更新 feature_gate.py 中的工具列表

4. **错误处理**: 友好的错误提示
   - 未激活时提示升级
   - 连接失败时提示检查 UE 编辑器
   - 参数错误时提示正确格式

## 成功标准

- [ ] 所有 11 个任务完成
- [ ] 免费功能正常工作
- [ ] 付费功能被正确阻止
- [ ] 激活后付费功能正常工作
- [ ] 文档完整，包含第三方声明
- [ ] 无编译错误，无运行时错误
- [ ] 代码通过 code review

## 时间估算

- P0 任务（核心功能）: 1.5 小时
- P1 任务（测试和优化）: 0.5 小时
- P2 任务（文档和清理）: 0.5 小时
- **总计**: 2.5 小时

## 后续优化

1. 注册更多工具（UMG、Material、AI 资产等）
2. 添加工具使用统计
3. 优化错误提示文案
4. 添加工具使用示例
5. 支持更多 UE 版本
