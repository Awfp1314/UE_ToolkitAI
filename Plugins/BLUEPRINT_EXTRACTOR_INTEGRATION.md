# Blueprint Extractor 商业化集成方案

## 概述

本文档说明如何将开源项目 `blueprint-extractor` 集成到 UE Toolkit 中，并实现基于 License 的功能分级。

## 商业模式

### 免费版（Free Tier）

- ✅ 资产读取和分析功能
- ✅ 蓝图结构提取
- ✅ UMG/Material/动画资产查看
- ✅ 资产搜索和列表
- ❌ 创建/修改功能
- ❌ 保存功能
- ❌ 导入功能

### 付费版（Pro Tier）

- ✅ 所有免费功能
- ✅ 创建和修改所有资产类型
- ✅ 保存资产
- ✅ 导入外部资源
- ✅ 可视化验证（截图、对比）
- ✅ 项目自动化控制
- ✅ 调试功能

## 架构设计

```
用户请求
    ↓
AI 助手
    ↓
Tools Registry
    ↓
Feature Gate (权限检查)
    ↓ (允许)
UE Tool Client (HTTP)
    ↓
blueprint-extractor Subsystem
    ↓
UE Editor
```

## 集成步骤

### 1. 准备插件

```bash
# 方案 A：使用本地副本
cp -r Plugins/temp_blueprint_extractor/BlueprintExtractor Plugins/BlueprintExtractor

# 方案 B：从官方仓库克隆（推荐，便于更新）
cd Plugins
git clone https://github.com/SunGrow/ue-blueprint-extractor.git BlueprintExtractor
```

### 2. 删除旧插件

```bash
# 删除自研插件
rm -rf Plugins/BlueprintToAI

# 删除相关文档
rm Plugins/BlueprintToAI_Design.md
rm Plugins/BLUEPRINT_EXTRACTOR_ANALYSIS.md
```

### 3. 更新 Python 代码

#### 3.1 修改 UE Tool Client

**文件**: `modules/ai_assistant/clients/ue_tool_client.py`

```python
# 修改 Subsystem 路径
subsystem_path = "/Script/BlueprintExtractor.Default__BlueprintExtractorSubsystem"
```

#### 3.2 集成 Feature Gate

**文件**: `modules/ai_assistant/logic/tools_registry.py`

在 `__init__` 方法中添加：

```python
from modules.ai_assistant.logic.feature_gate import UEFeatureGate

def __init__(self, ...):
    # ... 现有代码 ...

    # 初始化功能权限控制
    from core.security.license_manager import LicenseManager
    license_manager = LicenseManager()
    self.feature_gate = UEFeatureGate(license_manager)
```

在 `dispatch` 方法中添加权限检查：

```python
def dispatch(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
    try:
        if tool_name not in self.tools:
            return {"success": False, "error": f"未知工具: {tool_name}"}

        # 权限检查
        if not self.feature_gate.is_tool_allowed(tool_name):
            return {
                "success": False,
                "error": self.feature_gate.get_blocked_reason(tool_name),
                "locked": True,
                "tier": "pro"
            }

        # ... 现有代码 ...
```

#### 3.3 注册 blueprint-extractor 工具

**核心工具注册示例**：

```python
def _register_blueprint_extractor_tools(self):
    """注册 blueprint-extractor 工具"""

    # 1. 提取蓝图（免费）
    self.register_tool(ToolDefinition(
        name="ExtractBlueprint",
        description="提取蓝图结构到 JSON（免费功能）",
        parameters={
            "type": "object",
            "properties": {
                "AssetPath": {"type": "string", "description": "资产路径"},
                "Scope": {"type": "string", "enum": ["Minimal", "Compact", "Full"], "default": "Full"}
            },
            "required": ["AssetPath"]
        },
        function=lambda **kwargs: self._execute_ue_tool("ExtractBlueprint", **kwargs),
        requires_confirmation=False
    ))

    # 2. 创建蓝图（付费）
    self.register_tool(ToolDefinition(
        name="CreateBlueprint",
        description="创建新蓝图（Pro 功能）",
        parameters={
            "type": "object",
            "properties": {
                "AssetPath": {"type": "string"},
                "ParentClassPath": {"type": "string"},
                "PayloadJson": {"type": "string", "default": ""}
            },
            "required": ["AssetPath", "ParentClassPath"]
        },
        function=lambda **kwargs: self._execute_ue_tool("CreateBlueprint", **kwargs),
        requires_confirmation=True
    ))

    # ... 注册其他工具 ...
```

### 4. 用户体验设计

#### 4.1 AI 提示词更新

当用户尝试使用付费功能时，AI 应该：

```
用户：帮我创建一个新的蓝图

AI：检测到您尝试使用创建功能，这是 Pro 版本的功能。

免费版支持：
- ✅ 读取和分析蓝图
- ✅ 查看 UMG、Material 等资产
- ✅ 搜索和列出资产

Pro 版本额外支持：
- ✨ 创建和修改所有资产类型
- ✨ 保存资产
- ✨ 导入外部资源
- ✨ 可视化验证和调试

是否需要了解如何激活 Pro 版本？
```

#### 4.2 UI 提示

在工具箱界面添加：

- 免费版标识
- Pro 功能锁定图标
- 升级按钮

### 5. License 验证流程

```python
# core/security/license_manager.py 已有实现

def is_activated(self) -> bool:
    """检查是否已激活"""
    # 现有逻辑
    pass

def get_license_info(self) -> dict:
    """获取 License 信息"""
    return {
        "activated": self.is_activated(),
        "tier": "pro" if self.is_activated() else "free",
        "expires_at": self.get_expiry_date(),
        # ...
    }
```

## 功能分级详细列表

### 免费功能（18 个工具）

**提取/读取**：

- `ExtractBlueprint`
- `ExtractWidgetBlueprint`
- `ExtractMaterial`
- `ExtractMaterialInstance`
- `ExtractDataAsset`
- `ExtractDataTable`
- `ExtractCurve`
- `ExtractCurveTable`
- `ExtractStateTree`
- `ExtractBehaviorTree`
- `ExtractBlackboard`
- `ExtractAnimSequence`
- `ExtractAnimMontage`
- `ExtractBlendSpace`
- `ExtractUserDefinedStruct`
- `ExtractUserDefinedEnum`

**搜索/列表**：

- `SearchAssets`
- `ListAssets`

### 付费功能（94 个工具）

**创建/修改**：所有 `Create*` 和 `Modify*` 函数

**保存**：

- `SaveAssets`

**导入**：

- `ImportAssets`
- `ImportTextures`
- `ImportMeshes`
- `ImportFonts`

**验证**：

- `CaptureWidgetPreview`
- `CaptureEditorScreenshot`
- `CompareCaptureToReference`

**项目控制**：

- `StartPIE`
- `StopPIE`
- `TriggerLiveCoding`
- `RestartEditor`

## 开源协议合规

### blueprint-extractor 许可证

查看项目的 LICENSE 文件，通常是 MIT 或 Apache 2.0。

### 合规要求

1. **保留版权声明**：
   - 在插件目录保留原 LICENSE 文件
   - 在文档中注明来源

2. **不修改插件代码**：
   - 所有权限控制在 Python 层实现
   - 不修改 C++ 源码

3. **文档说明**：

   ```markdown
   ## 第三方组件

   本软件集成了以下开源项目：

   - **blueprint-extractor**
     - 作者：SunGrow
     - 许可证：MIT License
     - 仓库：https://github.com/SunGrow/ue-blueprint-extractor
     - 用途：提供 UE 资产操作能力
   ```

## 更新维护

### 同步上游更新

```bash
cd Plugins/BlueprintExtractor
git pull origin master

# 或者如果是复制的副本
cd Plugins
rm -rf BlueprintExtractor
git clone https://github.com/SunGrow/ue-blueprint-extractor.git BlueprintExtractor
```

### 版本锁定

建议在生产环境锁定特定版本：

```bash
cd Plugins/BlueprintExtractor
git checkout v1.2.3  # 锁定到稳定版本
```

## 测试计划

### 免费功能测试

- [ ] 提取普通蓝图
- [ ] 提取 UMG
- [ ] 搜索资产
- [ ] 列出资产

### 付费功能测试

- [ ] 未激活时被阻止
- [ ] 激活后可用
- [ ] 创建蓝图
- [ ] 修改蓝图
- [ ] 保存资产

### License 测试

- [ ] 免费版限制生效
- [ ] 激活码验证
- [ ] 过期处理
- [ ] 错误提示友好

## 部署清单

- [ ] 删除旧插件 `BlueprintToAI`
- [ ] 集成 `blueprint-extractor`
- [ ] 实现 `feature_gate.py`
- [ ] 更新 `tools_registry.py`
- [ ] 更新 `ue_tool_client.py`
- [ ] 添加 UI 提示
- [ ] 更新用户文档
- [ ] 测试免费功能
- [ ] 测试付费功能
- [ ] 测试 License 验证
- [ ] 添加第三方声明

## 总结

通过在 Python 层实现权限控制，我们可以：

1. ✅ 使用成熟的开源插件
2. ✅ 不修改插件源码，保持合规
3. ✅ 灵活控制功能开放
4. ✅ 便于同步上游更新
5. ✅ 实现商业化目标
