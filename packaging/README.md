# 打包脚本使用说明

## 📦 文件说明

### 配置文件

- `ue_toolkit.spec` - PyInstaller 打包配置
- `UeToolkitpack.iss` - Inno Setup 安装包配置
- `runtime_hook_*.py` - PyInstaller 运行时钩子

### 自动化脚本

#### 1. `update_version.py` / `update_version.bat`

**功能**: 仅更新 Inno Setup 脚本中的版本号

**使用方法**:

```bash
# 方法1: 双击运行
update_version.bat

# 方法2: 命令行运行
python update_version.py
```

**作用**:

- 从 `version.py` 读取版本号
- 自动更新 `UeToolkitpack.iss` 中的版本号
- 不执行打包操作

---

#### 2. `build_installer.py` / `build_installer.bat` ⭐ 推荐

**功能**: 一键完成所有打包步骤

**使用方法**:

```bash
# 方法1: 双击运行（推荐）
build_installer.bat

# 方法2: 命令行运行
python build_installer.py
```

**执行步骤**:

1. ✅ 从 `version.py` 读取版本号
2. ✅ 更新 `UeToolkitpack.iss` 中的版本号
3. ✅ 运行 PyInstaller 打包 EXE
4. ✅ 调用 Inno Setup 编译安装包

**输出文件**:

- `dist/UE_Toolkit.exe` - 单文件可执行程序
- `packaging/Output/UE_Toolkit_Setup_v{版本号}.exe` - 安装包

---

#### 3. `build_with_ai_model.bat`

**功能**: 原有的打包脚本（包含 AI 模型）

**使用方法**:

```bash
build_with_ai_model.bat
```

---

## 🚀 快速开始

### 方式一：完全自动化（推荐）

1. **修改版本号**

   ```python
   # 编辑 version.py
   VERSION = "1.3.3"  # 修改这里
   ```

2. **一键打包**

   ```bash
   # 双击运行
   packaging/build_installer.bat
   ```

3. **完成！**
   - EXE: `dist/UE_Toolkit.exe`
   - 安装包: `packaging/Output/UE_Toolkit_Setup_v1.3.3.exe`

---

### 方式二：分步执行

#### 步骤1: 更新版本号

```bash
cd packaging
python update_version.py
```

#### 步骤2: 打包 EXE

```bash
cd ..
pyinstaller packaging/ue_toolkit.spec --clean
```

#### 步骤3: 编译安装包

- 打开 Inno Setup
- 打开 `packaging/UeToolkitpack.iss`
- 点击 Build → Compile

---

## 📋 前置要求

### 必需工具

1. **Python 3.8+**

   ```bash
   python --version
   ```

2. **PyInstaller**

   ```bash
   pip install pyinstaller
   ```

3. **Inno Setup 6** (可选，用于编译安装包)
   - 下载地址: https://jrsoftware.org/isdl.php
   - 安装后会自动被脚本检测

### 项目依赖

```bash
pip install -r requirements.txt
```

---

## 🔧 配置说明

### 版本号管理

**唯一真实来源**: `version.py`

```python
# version.py
VERSION = "1.3.2"  # 只需修改这里
```

所有其他地方的版本号都会自动同步：

- ✅ `UeToolkitpack.iss` - 通过脚本自动更新
- ✅ 主窗口标题 - 从 `version.py` 导入
- ✅ 安装包文件名 - 自动使用当前版本

### PyInstaller 配置

编辑 `ue_toolkit.spec` 可以修改：

- 打包模式（单文件/目录）
- 包含的文件和目录
- 隐藏导入的模块
- 图标文件

### Inno Setup 配置

编辑 `UeToolkitpack.iss` 可以修改：

- 应用名称和发布者
- 安装路径
- 快捷方式
- 注册表项
- 安装界面

**注意**: 版本号会被自动更新，无需手动修改！

---

## 📊 打包流程图

```
version.py (VERSION = "1.3.2")
    ↓
update_version.py
    ↓
UeToolkitpack.iss (#define MyAppVersion "1.3.2")
    ↓
PyInstaller (ue_toolkit.spec)
    ↓
dist/UE_Toolkit.exe
    ↓
Inno Setup (UeToolkitpack.iss)
    ↓
packaging/Output/UE_Toolkit_Setup_v1.3.2.exe
```

---

## 🐛 常见问题

### Q: 提示找不到 pyinstaller

```bash
A: pip install pyinstaller
```

### Q: 提示找不到 Inno Setup

```
A: 下载安装 Inno Setup 6
   https://jrsoftware.org/isdl.php

   或者手动编译:
   1. 打开 Inno Setup
   2. 打开 UeToolkitpack.iss
   3. 点击 Build → Compile
```

### Q: 版本号没有更新

```
A: 确保先运行 update_version.py
   或使用 build_installer.py 自动更新
```

### Q: 打包后程序无法运行

```
A: 检查 ue_toolkit.spec 中的配置
   确保所有依赖都已包含
   使用 --debug 选项查看详细错误
```

---

## 📝 最佳实践

### 发布新版本的完整流程

1. **更新代码**
   - 完成新功能开发
   - 测试所有功能

2. **更新版本号**

   ```python
   # version.py
   VERSION = "1.4.0"  # 新版本号
   ```

3. **更新更新日志**

   ```markdown
   # README.md

   ## v1.4.0 (2025-xx-xx)

   - 新增功能...
   ```

4. **一键打包**

   ```bash
   packaging/build_installer.bat
   ```

5. **测试安装包**
   - 在干净的环境中测试安装
   - 验证所有功能正常

6. **发布**
   - 上传到 GitHub Releases
   - 更新下载链接

---

## 🎯 总结

### 优势

✅ **自动化** - 一键完成所有步骤
✅ **版本同步** - 版本号自动同步
✅ **易于维护** - 只需修改 version.py
✅ **减少错误** - 避免手动修改遗漏

### 使用建议

- 🌟 **推荐**: 使用 `build_installer.bat` 一键打包
- 📝 **版本号**: 只在 `version.py` 中修改
- 🧪 **测试**: 打包后务必测试安装包
- 📦 **备份**: 保留每个版本的安装包

---

## 📞 支持

如有问题，请查看：

1. 脚本输出的错误信息
2. PyInstaller 日志
3. Inno Setup 编译日志
