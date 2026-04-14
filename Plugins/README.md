# BlueprintAITools - UE 插件集合

这个目录包含了 BlueprintAITools 插件的多个版本，支持不同的虚幻引擎版本。

---

## 📦 可用版本

### 1. UE 4.26+ 版本

**目录**：`BlueprintAITools_v3.0_UE426/`  
**支持引擎**：UE 4.26, 4.27  
**特点**：

- 使用 UE4 的 FTicker API
- 兼容 UE4 的 Python 插件
- 核心功能与 UE5 版本一致

### 2. UE 5.0+ 版本

**目录**：`BlueprintAITools_v3.0_UE50/`  
**支持引擎**：UE 5.0, 5.1, 5.2, 5.3  
**特点**：

- 使用 UE5 的 FTSTicker API
- 改进的 Python 集成
- 更好的蓝图编辑器 API

### 3. UE 5.4+ 版本

**目录**：`BlueprintAITools_v3.0_UE54/`  
**支持引擎**：UE 5.4, 5.5, 5.6  
**特点**：

- 最新的 UE5 API
- 完整的功能支持
- 推荐用于新项目

---

## 🚀 快速开始

### 选择合适的版本

1. 查看你的 UE 项目版本
2. 选择对应的插件文件夹
3. 复制到项目的 `Plugins/` 目录

### 安装步骤

```bash
# 1. 复制插件到项目
YourProject/
└── Plugins/
    └── BlueprintAITools/  ← 复制对应版本的文件夹到这里

# 2. 重新生成项目文件
右键 .uproject → Generate Visual Studio project files

# 3. 编译项目
打开 .sln 文件，编译项目

# 4. 启动 UE 编辑器
插件会自动启动 RPC 服务器
```

---

## 📋 版本对照表

| 插件版本 | UE 版本   | Ticker API | Editor API            | Python 支持 | 推荐度     |
| -------- | --------- | ---------- | --------------------- | ----------- | ---------- |
| UE426    | 4.26-4.27 | FTicker    | FAssetEditorManager   | 基础        | ⭐⭐⭐     |
| UE50     | 5.0-5.3   | FTSTicker  | UAssetEditorSubsystem | 改进        | ⭐⭐⭐⭐   |
| UE54     | 5.4+      | FTSTicker  | UAssetEditorSubsystem | 完整        | ⭐⭐⭐⭐⭐ |

---

## 🔧 核心功能（所有版本）

- ✅ 读取和分析蓝图结构
- ✅ 智能简化导出（节省 40-50% token）
- ✅ 错误检测和验证
- ✅ 节点字典系统
- ✅ 自动启动 RPC 服务器
- ✅ 100% 稳定，只读模式

---

## 📖 详细文档

每个插件版本都包含完整的 README.md 文档：

- `BlueprintAITools_v3.0_UE426/README.md` - UE 4.26 版本说明
- `BlueprintAITools_v3.0_UE50/README.md` - UE 5.0 版本说明
- `BlueprintAITools_v3.0_UE54/README.md` - UE 5.4 版本说明

---

## ⚠️ 注意事项

### 版本选择

- **不要混用版本**：每个项目只使用一个版本
- **引擎版本匹配**：选择与你的 UE 版本最接近的插件版本
- **向后兼容**：高版本插件通常兼容低版本引擎（同一大版本内）
- **API 差异**：插件通过条件编译自动适配不同版本的 UE API，无需手动修改

### 编译要求

- **Visual Studio**：需要安装 VS 2019 或 2022
- **C++ 工作负载**：选择"使用 C++ 的游戏开发"
- **首次编译**：可能需要 2-5 分钟

### Python 插件

- 确保在 UE 编辑器中启用 "Python Script Plugin"
- 编辑 → 插件 → 搜索 "Python" → 启用

---

## 🎯 使用场景

### 适用项目类型

- ✅ 纯蓝图项目（Blueprint Only）
- ✅ C++ + 蓝图混合项目
- ✅ 蓝图函数库项目
- ✅ 任何包含蓝图的 UE 项目

### 典型工作流

1. 在 UE 中打开蓝图编辑器
2. 在 UE Toolkit AI 助手中询问："这个蓝图做什么？"
3. AI 自动读取并分析蓝图
4. AI 提供专家级的建议
5. 用户在 UE 中手动修改

---

## 🐛 故障排查

### 插件加载失败

**症状**：UE 提示插件无法加载

**解决方案**：

1. 检查引擎版本是否匹配
2. 重新生成项目文件
3. 清理 `Intermediate/` 和 `Binaries/` 目录
4. 重新编译项目

### RPC 服务器未启动

**症状**：AI 助手无法连接

**解决方案**：

1. 检查 Output Log 中的错误信息
2. 确认 Python 插件已启用
3. 手动启动：在 UE Python 控制台执行
   ```python
   import ue_rpc_server
   ue_rpc_server.start_rpc_server()
   ```

### 通信不稳定

**症状**：连接时断时续

**解决方案**：

1. 检查防火墙设置（端口 9998）
2. 确保 UE 编辑器和 UE Toolkit 都在运行
3. 查看双方的日志文件

---

## 📞 技术支持

**作者**：HUTAO  
**许可**：MIT  
**项目**：UE Toolkit

---

## 🔄 更新日志

### v3.0.1 (2025-01-XX)

- ✅ 优化 UE 版本兼容性：通过条件编译支持 UE4 和 UE5 的不同 API
- ✅ UE 4.26/4.27：使用 `FAssetEditorManager` API
- ✅ UE 5.0+：使用 `UAssetEditorSubsystem` API
- ✅ 所有版本共享相同的核心功能代码

### v3.0 (2025-11-07)

- ✅ 支持 UE 4.26, 5.0, 5.4 三个版本
- ✅ 完整的蓝图读取和分析功能
- ✅ 智能简化导出（节省 token）
- ✅ 错误检测和验证
- ✅ 节点字典系统
- ✅ 自动启动 RPC 服务器
- ✅ 100% 稳定，只读模式

---

**专注做好一件事：让 AI 深入理解您的蓝图！**
