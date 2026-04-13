# 打包说明

## 文件说明

- `build_installer.py` / `build_installer.bat` - 一键打包脚本
- `ue_toolkit.spec` - PyInstaller 打包配置
- `UeToolkitpack.iss` - Inno Setup 安装包配置
- `runtime_hook_encoding.py` - 运行时钩子（修复编码问题）
- `License.txt` - 用户许可协议

## 打包流程

### 方式一：一键打包（推荐）

```bash
# 双击运行或命令行执行
build_installer.bat
```

执行步骤：

1. 清理旧构建文件（build/、dist/）
2. 运行 PyInstaller 打包 EXE
3. 调用 Inno Setup 编译安装包

输出文件（都在 dist/ 目录）：

- `dist/UE_Toolkit.exe` - 单文件可执行程序
- `dist/UE_Toolkit_Setup_v{版本}.exe` - 安装包

### 方式二：分步执行

#### 1. 打包 EXE

```bash
pyinstaller ue_toolkit.spec --clean
```

输出：`dist/UE_Toolkit.exe`

#### 2. 编译安装包

使用 Inno Setup 打开 `UeToolkitpack.iss` 并编译。

输出：`dist/UE_Toolkit_Setup_v{版本}.exe`

## 版本号管理

版本号由 Kiro Hook 自动管理：

- 修改 `version.py` 中的 `VERSION` 常量
- Hook 会在功能性代码变更且用户验收成功后自动同步版本号到 `UeToolkitpack.iss`

## 注意事项

- 推荐使用 `build_installer.bat` 一键打包
- 版本号由 Kiro Hook 自动管理，无需手动同步
- PyInstaller 配置已优化，排除了未使用的大型库
- 所有配置模板会自动打包

## 打包日志

打包过程会自动生成日志文件到 `dist/` 目录：

- `build.log` - PyInstaller 完整构建日志
- `build_summary.log` - 仅包含错误和警告的摘要
- `inno_setup.log` - Inno Setup 编译日志
- `build_error.log` / `inno_setup_error.log` - 错误日志（如果失败）

控制台输出已优化，只显示关键信息和进度，详细日志请查看上述文件。
