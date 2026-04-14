# BlueprintAITools - 蓝图 AI 分析插件

版本：3.0 Readonly（只读稳定版）  
UE 版本：5.4+  
更新时间：2025-11-07

---

## 概述

BlueprintAITools 是一个专注于**蓝图分析和理解**的 UE 插件，让 AI 助手能够：

- 读取和理解蓝图结构
- 分析蓝图功能和逻辑
- 检测潜在错误
- 提供专家级的建议

**设计理念**：稳定优先，只做只读操作，100% 不崩溃。

---

## 核心功能

### 1. 智能蓝图导出

- 自动识别当前打开的蓝图编辑器
- 导出为简化 JSON 格式（节省 40-50% token）
- 包含：节点、Pin、连接关系、变量
- 小型蓝图：约 2000 tokens

### 2. 错误检测

- Pin 类型不匹配检测
- 已优化，减少误报
- 返回清晰的错误描述

### 3. 节点字典

- 常用蓝图节点分类说明
- 节点的 Pin 配置
- 使用场景和示例

### 4. 自动化集成

- 插件加载时自动启动 RPC 服务器
- 与外部 AI 工具无缝通信
- Socket 接口（127.0.0.1:9998）

---

## 安装使用

### 安装

1. 将 `BlueprintAITools` 文件夹放到项目的 `Plugins` 目录
2. 重启 UE 或重新生成项目文件
3. 编译插件（首次使用）

### 使用

1. **启动 UE 编辑器**
   - RPC 服务器自动启动
   - 查看 Output Log 确认：`=== UE RPC 服务器已启动（只读模式）===`

2. **打开蓝图编辑器**
   - 双击任意蓝图资产

3. **在 AI 工具中对话**
   - "这个蓝图做什么？" → AI 自动读取并分析
   - "这个蓝图有什么错误？" → AI 自动检测
   - "可以用哪些蓝图节点？" → AI 展示节点字典

---

## AI 工具集成

### 支持的 RPC Actions

1. `get_current_blueprint_summary` - 读取蓝图
2. `query_available_nodes` - 查询节点字典
3. `validate_blueprint` - 验证错误

### Python API

```python
# 在 UE 的 Python 控制台中
import blueprint_tools

# 读取蓝图
result = blueprint_tools.get_current_blueprint_summary()

# 验证蓝图
result = blueprint_tools.validate_blueprint()

# 查询节点
result = blueprint_tools.query_available_nodes()
```

---

## 技术架构

### 版本兼容性

本插件通过条件编译支持 UE 5.4 及更高版本：

- **FTSTicker API**：使用 `FTSTicker`（UE5）而非 `FTicker`（UE4）
- **Editor API**：使用 `UAssetEditorSubsystem`（UE5）而非 `FAssetEditorManager`（UE4）
- **Python 集成**：使用 UE5 最新的 Python 插件功能

所有版本差异通过 `#if ENGINE_MAJOR_VERSION >= 5` 条件编译自动处理，无需手动修改代码。

### C++ 扩展

**文件**：

- `Source/BlueprintAITools/Public/BlueprintAIToolsLibrary.h`
- `Source/BlueprintAITools/Private/BlueprintAIToolsLibrary.cpp`

**依赖模块**：

- UnrealEd
- BlueprintGraph
- Json / JsonUtilities
- PythonScriptPlugin

### Python 层

**文件**：

- `Content/Python/blueprint_tools.py` - 核心功能
- `Content/Python/ue_rpc_server.py` - RPC 服务器
- `Content/Python/node_dictionary.json` - 节点字典

---

## 性能特性

- **轻量**：只读操作，无状态
- **快速**：响应时间 <1 秒
- **稳定**：100% 不崩溃
- **节省 token**：简化版比完整版节省 40-50%

---

## 限制说明

### 当前版本（只读模式）

**支持**：

- ✅ 读取蓝图结构
- ✅ 分析蓝图功能
- ✅ 检测连接错误
- ✅ 查询节点信息

**不支持**：

- ❌ 创建/删除节点
- ❌ 修改连接
- ❌ 修改变量

**原因**：修改功能需要复杂的线程同步，当前版本为确保稳定性而禁用。

### 工作流

AI 扮演**顾问角色**：

1. 分析蓝图
2. 发现问题
3. 给出详细的修改建议
4. 用户在 UE 中手动修改

---

## 故障排查

### RPC 服务器未启动

检查：

- Output Log 中是否有错误
- Python 插件是否已启用

手动启动：

```python
import ue_rpc_server
ue_rpc_server.start_rpc_server()
```

### 读取蓝图失败

检查：

- 是否已打开蓝图编辑器
- 蓝图是否有效（未损坏）

### 通信不稳定

- 确保 UE 编辑器和 AI 工具都在运行
- 检查防火墙设置（端口 9998）
- 查看双方的日志

---

## 开发信息

**作者**：HUTAO  
**许可**：MIT  
**开发时间**：2025-11-07（6 小时）

---

## 致谢

感谢虚幻引擎社区的支持和贡献。

---

## 更新日志

### v3.0 Readonly (2025-11-07)

- ✅ 完整的蓝图读取和分析功能
- ✅ 智能简化导出（节省 token）
- ✅ 错误检测和验证
- ✅ 节点字典系统
- ✅ 自动启动 RPC 服务器
- ✅ 100% 稳定，只读模式
- ❌ 移除修改功能（线程安全问题）

---

**专注做好一件事：让 AI 深入理解您的蓝图！**
