# 打包检查清单

## 📋 打包前检查

### 1. 版本号

- [ ] 已更新 `version.py` 中的 `VERSION`
- [ ] 版本号格式正确（如 `1.3.2`）
- [ ] 已运行 `update_version.py` 更新 `.iss` 文件

### 2. 代码完整性

- [ ] 所有功能已测试通过
- [ ] 没有调试代码（print、断点等）
- [ ] 没有硬编码的路径
- [ ] 所有导入都正确

### 3. 资源文件

- [ ] `resources/tubiao.ico` 存在
- [ ] `resources/styles/` 目录完整
- [ ] `resources/templates/` 目录完整
- [ ] `License.txt` 存在

### 4. 依赖检查

- [ ] `requirements.txt` 是最新的
- [ ] 所有依赖都已安装
- [ ] PyInstaller 已安装

---

## 📦 打包内容清单

### ✅ 必须打包的文件/目录

#### 核心代码

- ✅ `main.py` - 程序入口
- ✅ `version.py` - 版本信息
- ✅ `core/` - 核心模块
- ✅ `modules/` - 功能模块
- ✅ `ui/` - UI 组件

#### 资源文件

- ✅ `resources/tubiao.ico` - 应用图标
- ✅ `resources/styles/` - QSS 样式文件
  - `config/` - 主题配置
  - `core/` - 核心样式
  - `modules/` - 模块样式
  - `themes/` - 生成的主题
  - `widgets/` - 控件样式
- ✅ `resources/templates/` - 配置模板
- ✅ `resources/icons/` - SVG 图标（如果使用）

#### 许可文件

- ✅ `License.txt` - 用户许可协议

### ❌ 不需要打包的文件/目录

#### 开发文件

- ❌ `tests/` - 测试代码
- ❌ `tools/` - 开发工具
- ❌ `scripts/` - 脚本文件
- ❌ `docs/` - 文档
- ❌ `.kiro/` - Kiro 配置
- ❌ `.github/` - GitHub 配置

#### 临时文件

- ❌ `__pycache__/` - Python 缓存
- ❌ `build/` - 构建临时文件
- ❌ `dist/` - 旧的打包输出
- ❌ `.git/` - Git 仓库

#### 配置文件

- ❌ `.gitignore`
- ❌ `README.md` - 开发文档
- ❌ `requirements.txt` - 依赖列表

#### 数据文件

- ❌ `data/` - 运行时数据（如果存在）
- ❌ `logs/` - 日志文件（如果存在）

### ⚠️ 特殊处理

#### AI 模型

- ⚠️ **不打包** AI 模型文件（约 100MB）
- ✅ 首次运行时自动下载
- 原因：避免 Windows 符号链接权限问题

#### 用户数据

- ⚠️ **不打包** 用户配置和数据
- ✅ 运行时在 `%APPDATA%` 创建
- 位置：`%APPDATA%\ue_toolkit\user_data\`

---

## 🔍 打包后验证

### 1. 文件检查

```bash
# 检查 EXE 文件大小（应该在 50-150MB 之间）
dir dist\UE_Toolkit.exe

# 检查安装包大小
dir packaging\Output\UE_Toolkit_Setup_*.exe
```

### 2. 功能测试

#### 基础功能

- [ ] 程序能正常启动
- [ ] 主窗口正常显示
- [ ] 图标正确显示
- [ ] 版本号正确显示

#### 模块功能

- [ ] 资产管理器模块正常
- [ ] AI 助手模块正常
- [ ] 配置工具模块正常
- [ ] 站点推荐模块正常

#### UI 功能

- [ ] 主题切换正常
- [ ] 对话框正常显示
- [ ] 系统托盘正常
- [ ] 设置界面正常

#### 数据功能

- [ ] 配置保存正常
- [ ] 配置读取正常
- [ ] 日志记录正常

### 3. 安装包测试

#### 安装测试

- [ ] 安装包能正常运行
- [ ] 安装路径正确
- [ ] 快捷方式创建正常
- [ ] 注册表项正确

#### 升级测试

- [ ] 能检测到旧版本
- [ ] 升级提示正确
- [ ] 用户数据保留
- [ ] 配置文件保留

#### 卸载测试

- [ ] 卸载程序正常
- [ ] 文件清理干净
- [ ] 注册表清理正常
- [ ] 用户数据保留（可选）

---

## 🐛 常见问题排查

### 问题1: 程序无法启动

**可能原因**:

- 缺少必要的 DLL 文件
- Python 模块未正确打包
- 资源文件路径错误

**排查方法**:

```bash
# 使用 --debug 模式重新打包
pyinstaller packaging/ue_toolkit.spec --clean --debug=all

# 查看错误日志
type build\UE_Toolkit\warn-UE_Toolkit.txt
```

### 问题2: 图标不显示

**可能原因**:

- `tubiao.ico` 文件未打包
- 图标路径错误
- 图标文件损坏

**检查方法**:

- 确认 `resources/tubiao.ico` 存在
- 检查 `.spec` 文件中的 `icon` 参数
- 尝试重新生成图标文件

### 问题3: 样式不正确

**可能原因**:

- QSS 文件未打包
- 主题文件缺失
- 样式路径错误

**检查方法**:

- 确认 `resources/styles/` 目录完整
- 检查 `themes/` 目录下的 `.qss` 文件
- 运行 `scripts/build/build_themes.py` 重新生成主题

### 问题4: 模块加载失败

**可能原因**:

- 模块文件未打包
- 模块依赖缺失
- 导入路径错误

**检查方法**:

- 确认 `modules/` 目录完整
- 检查 `hiddenimports` 列表
- 查看模块的 `manifest.json` 文件

### 问题5: 版本号不正确

**可能原因**:

- `version.py` 未更新
- `.iss` 文件未更新
- 缓存文件未清理

**解决方法**:

```bash
# 1. 更新版本号
python packaging/update_version.py

# 2. 清理缓存
rmdir /s /q build dist

# 3. 重新打包
python packaging/build_installer.py
```

---

## 📊 打包文件大小参考

### 单文件 EXE

- **最小**: 50 MB（不含 AI 依赖）
- **正常**: 80-120 MB（含 AI 依赖）
- **最大**: 150 MB（含所有依赖）

### 安装包

- **最小**: 40 MB（压缩后）
- **正常**: 60-100 MB
- **最大**: 120 MB

### 如果文件过大

**优化方法**:

1. 检查 `excludes` 列表，排除不需要的模块
2. 使用 UPX 压缩（已启用）
3. 移除不必要的资源文件
4. 考虑使用目录模式而非单文件模式

---

## 🎯 发布前最终检查

### 代码质量

- [ ] 代码已提交到 Git
- [ ] 没有未提交的更改
- [ ] 版本号已打 Tag

### 文档更新

- [ ] README.md 已更新
- [ ] CHANGELOG.md 已更新
- [ ] 版本说明已准备

### 测试完成

- [ ] 所有功能测试通过
- [ ] 安装包测试通过
- [ ] 升级测试通过
- [ ] 卸载测试通过

### 发布准备

- [ ] 安装包已生成
- [ ] 文件名正确（包含版本号）
- [ ] 文件大小合理
- [ ] 准备好发布说明

---

## 📝 打包命令速查

```bash
# 只更新版本号
python packaging/update_version.py

# 只打包 EXE
pyinstaller packaging/ue_toolkit.spec --clean

# 完整打包（推荐）
python packaging/build_installer.py

# 清理构建文件
rmdir /s /q build dist packaging\Output
```

---

## 🔗 相关文档

- [打包脚本使用说明](README.md)
- [版本更新指南](../docs/zh-CN/version-update.md)
- [PyInstaller 文档](https://pyinstaller.org/)
- [Inno Setup 文档](https://jrsoftware.org/ishelp/)
