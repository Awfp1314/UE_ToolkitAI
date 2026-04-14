# BlueprintAITools - UE 插件集合

这个目录包含了 BlueprintAITools 插件的多个版本，支持不同的虚幻引擎版本。

---

## 📦 可用版本

每个版本都是为特定的 UE 版本编译，确保最佳兼容性：

- `BlueprintAITools_UE426/` - UE 4.26.x
- `BlueprintAITools_UE427/` - UE 4.27.x
- `BlueprintAITools_UE50/` - UE 5.0.x
- `BlueprintAITools_UE54/` - UE 5.4.x

---

## 🚀 编译步骤

### 1. 创建测试项目

在 Epic Games Launcher 中创建对应版本的空白 C++ 项目

### 2. 复制插件

```bash
TestProject/
└── Plugins/
    └── BlueprintAITools/  ← 复制对应版本的文件夹
```

### 3. 生成并编译

```bash
# 右键 .uproject → Generate Visual Studio project files
# 打开 .sln → Development Editor → 生成
```

### 4. 提取结果

```bash
# 复制 Binaries/ 文件夹回源码目录
TestProject/Plugins/BlueprintAITools/Binaries/ → BlueprintAITools_UE426/Binaries/
```

---

## 🚀 使用插件

```bash
# 复制编译好的插件到你的项目
YourProject/Plugins/BlueprintAITools/

# 启动 UE 编辑器，插件自动加载
```

---

## 📋 版本对照表

| 插件版本 | UE 版本 | Ticker API | Editor API            |
| -------- | ------- | ---------- | --------------------- |
| UE426    | 4.26.x  | FTicker    | FAssetEditorManager   |
| UE427    | 4.27.x  | FTicker    | FAssetEditorManager   |
| UE50     | 5.0.x   | FTSTicker  | UAssetEditorSubsystem |
| UE54     | 5.4.x   | FTSTicker  | UAssetEditorSubsystem |

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

每个插件版本都包含独立的 README.md 说明文档。

---

## ⚠️ 注意事项

### 版本选择

- 选择与你的 UE 版本精确匹配的插件
- 每个版本都需要单独编译

### 编译要求

- Visual Studio 2019 或 2022
- 对应版本的 UE 引擎

### Python 插件

- 确保在 UE 编辑器中启用 "Python Script Plugin"
- 编辑 → 插件 → 搜索 "Python" → 启用

---

## 🐛 故障排查

### 插件加载失败

1. 检查引擎版本是否匹配
2. 重新生成项目文件并编译

### RPC 服务器未启动

1. 确认 Python 插件已启用
2. 查看 Output Log 中的错误信息

---

## 🔄 更新日志

### v3.0.1 (2025-01-XX)

- ✅ 拆分为 4 个精确版本：UE 4.26、4.27、5.0、5.4
- ✅ 每个版本独立编译，确保最佳兼容性

---

**作者**：HUTAO | **许可**：MIT
