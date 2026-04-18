# 路径问题修复说明

## 问题描述

用户在 `AppData\Roaming` 目录下发现了两个配置目录：

1. `C:\Users\wang\AppData\Roaming\ue_toolkit\` - 实际使用的目录（有日志文件）
2. `C:\Users\wang\AppData\Roaming\UE Toolkit\` - Qt 自动创建的目录（只有部分配置）

## 根本原因

1. `version.py` 中定义了 `APP_NAME = "UE Toolkit"`（带空格）
2. `app_initializer.py` 调用 `app.setApplicationName(APP_NAME)` 设置应用名称
3. Qt 的 `QStandardPaths.AppDataLocation` 会使用应用名称创建目录，返回 `C:\Users\wang\AppData\Roaming\UE Toolkit`
4. 但代码中其他地方都硬编码使用 `ue_toolkit`（没有空格），并且在 Qt 返回的路径后又手动拼接 `/ "ue_toolkit"`
5. 最终导致路径变成：`C:\Users\wang\AppData\Roaming\UE Toolkit\ue_toolkit`

## 修复方案

### 1. 修改应用名称定义（version.py）

```python
# 修改前
APP_NAME = "UE Toolkit"

# 修改后
APP_NAME = "ue_toolkit"  # 用于 Qt 标准路径，不应包含空格
APP_DISPLAY_NAME = "UE Toolkit"  # 用于界面显示
```

### 2. 更新界面显示（ui/ue_main_window.py）

```python
# 使用 APP_DISPLAY_NAME 显示窗口标题
self.setWindowTitle(f"{APP_DISPLAY_NAME} {get_version_string()} - 虚幻引擎工具箱")
```

### 3. 移除重复的路径拼接

在所有使用 `QStandardPaths.AppDataLocation` 的地方，移除手动拼接的 `/ "ue_toolkit"`：

**修改前：**

```python
app_data = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.AppDataLocation)
config_dir = Path(app_data) / "ue_toolkit" / "ui_settings.json"
```

**修改后：**

```python
app_data = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.AppDataLocation)
config_dir = Path(app_data) / "ui_settings.json"
```

### 4. 受影响的文件

- `ui/ue_main_window.py` - 主题设置保存路径
- `core/bootstrap/ui_launcher.py` - 主题配置读取路径
- `modules/my_projects/logic/project_registry.py` - 项目注册表路径
- `modules/my_projects/ui/edit_project_dialog.py` - 项目备份路径
- `modules/config_tool/logic/config_storage.py` - 配置模板路径
- `core/config/config_migration_manager.py` - 配置迁移路径

## 修复效果

修复后，Qt 的 `QStandardPaths.AppDataLocation` 将返回：

```
C:\Users\wang\AppData\Roaming\ue_toolkit
```

这与代码中硬编码的路径保持一致，不再产生两个目录。

## 兼容性说明

- 现有的 `C:\Users\wang\AppData\Roaming\ue_toolkit\` 目录中的数据不受影响
- `C:\Users\wang\AppData\Roaming\UE Toolkit\` 目录可以手动删除（如果存在）
- 所有配置和日志文件将统一存储在 `ue_toolkit` 目录下

## 日志文件位置

修复后，日志文件的正确位置为：

```
C:\Users\wang\AppData\Roaming\ue_toolkit\user_data\logs\ue_toolkit.log
```

快速访问方法：

1. 按 `Win + R`
2. 输入：`%APPDATA%\ue_toolkit\user_data\logs`
3. 按回车
