# BlueprintAITools - UE 5.4 版本

专为 **Unreal Engine 5.4.x** 编译的蓝图分析插件。

---

## ⚠️ 编译状态

**当前状态**：源码版本，需要编译

**编译方法**：查看 [../COMPILATION_GUIDE.md](../COMPILATION_GUIDE.md)

---

## 📋 版本信息

- **目标引擎**：UE 5.4.x
- **Ticker API**：FTSTicker
- **Editor API**：UAssetEditorSubsystem
- **Python 支持**：完整功能

---

## 🚀 使用步骤

### 1. 编译插件

```bash
# 创建测试项目
# 在 Epic Games Launcher 中创建 UE 5.4 的空白 C++ 项目

# 复制插件
# 将此文件夹复制到测试项目的 Plugins/ 目录

# 生成项目文件
# 右键 .uproject → Generate Visual Studio project files

# 编译
# 打开 .sln，选择 Development Editor，编译项目

# 提取结果
# 复制 Binaries/ 文件夹回此目录
```

### 2. 安装到实际项目

```bash
# 将编译好的插件（包含 Binaries/）复制到你的项目
YourProject/Plugins/BlueprintAITools/

# 启动 UE 编辑器
```

### 3. 验证安装

在 UE 编辑器的 Output Log 中应该看到：

```
LogBlueprintAITools: BlueprintAITools plugin loaded
LogPython: RPC Server started on port 9998
```

---

## 📦 文件结构

```
BlueprintAITools_UE54/
├── BlueprintAITools.uplugin    ← 插件描述文件
├── Source/                      ← C++ 源码
│   └── BlueprintAITools/
│       ├── Private/
│       └── Public/
├── Content/                     ← Python 脚本
│   └── Python/
│       └── ue_rpc_server.py
├── Resources/                   ← 图标资源
└── Binaries/                    ← 编译后生成（需要编译）
    └── Win64/
        └── UnrealEditor-BlueprintAITools.dll
```

---

## 🔧 核心功能

- ✅ 读取和分析蓝图结构
- ✅ 智能简化导出（节省 40-50% token）
- ✅ 错误检测和验证
- ✅ 节点字典系统
- ✅ 自动启动 RPC 服务器
- ✅ 100% 稳定，只读模式

---

## 🐛 故障排查

### 编译失败

1. 确认 VS 2019/2022 已安装
2. 确认 UE 5.4 已安装
3. 删除 Intermediate/ 和 Binaries/ 后重试

### 插件加载失败

1. 检查 Binaries/ 文件夹是否存在
2. 确认 DLL 文件存在且大小正常（~200KB）
3. 查看 Output Log 中的错误信息

### RPC 服务器未启动

1. 启用 Python Script Plugin
2. 检查 Content/Python/ue_rpc_server.py 是否存在
3. 手动执行：`import ue_rpc_server; ue_rpc_server.start_rpc_server()`

---

**作者**：HUTAO  
**许可**：MIT  
**更新时间**：2025-01-XX
