# 更新检测器模块 (Update Checker)

## 概述

更新检测器模块负责在程序启动时自动检查更新、管理用户标识符和上报启动统计数据。该模块设计为非阻塞式，即使网络不可用也不会影响程序正常启动。

## 功能特性

### 1. 自动更新检查

- 在程序启动时自动检查最新版本
- 支持语义化版本号比较（SemVer）
- 处理 `v1.2.3` 和 `1.2.3` 两种版本号格式
- 3秒网络超时，不阻塞程序启动

### 2. 用户标识符管理

- 使用 UUID v4 生成唯一用户标识符
- 持久化存储在用户目录的隐藏配置文件中
- 自动验证 UUID 格式

### 3. 启动统计上报

- 上报用户ID、客户端版本和操作系统平台
- 网络失败时自动缓存到本地队列
- 网络恢复后自动批量上报待上报事件

### 4. 版本跳过功能

- 用户可以选择跳过特定版本的更新提示
- 跳过的版本列表持久化存储
- 支持强制更新模式（安全漏洞等关键更新）

## 使用方法

### 基本使用

```python
from core.update_checker import UpdateChecker
from core.version import VERSION

# 创建更新检测器实例
checker = UpdateChecker(current_version=VERSION)

# 获取或创建用户ID
user_id = checker.get_or_create_user_id()

# 上报启动事件
checker.report_launch(user_id)

# 检查更新
version_info = checker.check_for_updates()

if version_info:
    latest_version = version_info.get('version')
    force_update = version_info.get('force_update', False)

    # 检查是否应该显示更新提示
    if force_update or checker.should_show_update(latest_version):
        # 显示更新对话框
        print(f"新版本可用: {latest_version}")
        print(f"更新日志: {version_info.get('changelog')}")
```

### 集成到主程序

参考 `core/update_integration_example.py` 文件，展示了完整的集成流程：

```python
from core.update_checker import UpdateChecker
from core.version import VERSION

def check_and_report_on_startup():
    """在程序启动时检查更新并上报统计"""
    try:
        checker = UpdateChecker(current_version=VERSION)

        # 1. 上报启动事件（不阻塞）
        user_id = checker.get_or_create_user_id()
        checker.report_launch(user_id)

        # 2. 检查更新
        version_info = checker.check_for_updates()

        if version_info:
            latest_version = version_info.get('version')
            force_update = version_info.get('force_update', False)

            if force_update or checker.should_show_update(latest_version):
                return version_info

        return None
    except Exception as e:
        # 即使出错也不阻塞程序启动
        return None
```

### 处理用户选择

```python
def handle_update_dialog_result(checker, version_info, user_choice):
    """处理更新对话框的用户选择"""
    latest_version = version_info.get('version')

    if user_choice == 'update':
        # 打开浏览器到下载页面
        import webbrowser
        download_url = version_info.get('download_url')
        webbrowser.open(download_url)

    elif user_choice == 'skip':
        # 跳过此版本
        checker.skip_version(latest_version)

    elif user_choice == 'later':
        # 稍后提醒（不做任何操作）
        pass
```

## API 参考

### UpdateChecker 类

#### 构造函数

```python
UpdateChecker(config_path: Optional[str] = None, current_version: str = "1.3")
```

**参数:**

- `config_path`: 配置文件路径，默认为 `~/.ue_toolkit/update_config.json`
- `current_version`: 当前程序版本号

#### 主要方法

##### check_for_updates()

检查是否有新版本可用。

**返回值:**

- `dict`: 如果有新版本，返回版本信息字典
- `None`: 如果已是最新版本或网络不可用

**版本信息字典结构:**

```python
{
    "version": "v1.4.0",
    "download_url": "https://example.com/download",
    "changelog": "更新内容...",
    "force_update": False,
    "release_date": "2024-01-28T00:00:00Z"
}
```

##### get_or_create_user_id()

获取或创建用户标识符。

**返回值:**

- `str`: UUID v4 格式的用户标识符

##### report_launch(user_id: Optional[str] = None)

上报启动事件。

**参数:**

- `user_id`: 用户标识符，如果为 None 则自动获取

**返回值:**

- `bool`: 成功返回 True，失败返回 False（失败时会自动缓存到本地队列）

##### should_show_update(latest_version: str)

检查是否应该显示更新提示。

**参数:**

- `latest_version`: 最新版本号

**返回值:**

- `bool`: 如果应该显示返回 True，如果已跳过返回 False

##### skip_version(version: str)

记录跳过的版本。

**参数:**

- `version`: 要跳过的版本号

## 配置文件

配置文件默认位置: `~/.ue_toolkit/update_config.json`

**配置文件结构:**

```json
{
  "user_id": "550e8400-e29b-41d4-a716-446655440000",
  "skipped_versions": ["v1.4.0"],
  "pending_events": [
    {
      "user_id": "550e8400-e29b-41d4-a716-446655440000",
      "client_version": "v1.3.0",
      "platform": "Windows",
      "timestamp": "2024-01-28T10:30:00"
    }
  ],
  "last_check": "2024-01-28T10:30:00"
}
```

**字段说明:**

- `user_id`: 用户唯一标识符（UUID v4）
- `skipped_versions`: 用户跳过的版本列表
- `pending_events`: 待上报的启动事件队列（网络失败时缓存）
- `last_check`: 最后一次检查更新的时间

## API 端点配置

默认 API 地址: `http://localhost:5000/api`

可以通过修改 `UpdateChecker` 类的 `api_base_url` 属性来配置：

```python
checker = UpdateChecker(current_version=VERSION)
checker.api_base_url = "https://your-server.com/api"
```

**使用的 API 端点:**

- `GET /api/version` - 获取最新版本信息
- `POST /api/report/launch` - 上报启动事件

## 错误处理

模块采用优雅的错误处理策略：

1. **网络超时**: 3秒超时后继续启动程序，不阻塞
2. **网络不可用**: 将启动事件缓存到本地队列，下次成功时批量上报
3. **API 错误**: 记录日志，不影响程序正常运行
4. **配置文件错误**: 自动创建默认配置

所有错误都会记录到日志系统，便于调试和监控。

## 测试

运行单元测试：

```bash
cd UE_TOOKITS_AI_NEW
python test_update_checker.py
```

测试覆盖：

- ✅ 版本号规范化
- ✅ 版本号比较
- ✅ 用户ID生成和验证
- ✅ 版本跳过功能
- ✅ 平台检测

## 隐私说明

更新检测器收集以下匿名数据：

- **用户ID**: 随机生成的 UUID，不包含任何个人信息
- **客户端版本**: 程序版本号
- **操作系统平台**: Windows/macOS/Linux
- **启动时间戳**: 用于统计活跃用户

这些数据仅用于：

- 统计用户数量和活跃度
- 改进产品功能
- 了解不同平台的使用情况

用户可以通过删除配置文件 `~/.ue_toolkit/update_config.json` 来重置用户ID。

## 注意事项

1. **非阻塞设计**: 所有网络操作都有超时限制，确保不会阻塞程序启动
2. **离线支持**: 网络不可用时，启动事件会缓存到本地，网络恢复后自动上报
3. **版本格式**: 支持 `v1.2.3` 和 `1.2.3` 两种格式，内部统一规范化为 `v1.2.3`
4. **队列限制**: 待上报事件队列最多保留 100 个事件，防止配置文件过大
5. **强制更新**: 当 `force_update` 为 `true` 时，忽略跳过列表，强制显示更新提示

## 未来改进

- [ ] 支持自定义 API 端点配置
- [ ] 支持代理服务器配置
- [ ] 添加更新下载进度跟踪
- [ ] 支持增量更新
- [ ] 添加更新回滚功能
