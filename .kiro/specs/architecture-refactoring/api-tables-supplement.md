# API Tables Supplement

## LogService API 表

| 方法           | 参数       | 返回值         | 异常 | 线程安全 | 说明                                     |
| -------------- | ---------- | -------------- | ---- | -------- | ---------------------------------------- |
| `__init__()`   | 无         | None           | 无   | 是       | 初始化日志服务，确保全局 Logger 已初始化 |
| `get_logger()` | name: str  | logging.Logger | 无   | 是       | 获取指定名称的日志记录器                 |
| `set_level()`  | level: int | None           | 无   | 是       | 设置全局日志级别                         |
| `cleanup()`    | 无         | None           | 无   | 是       | 清理日志处理器，关闭文件句柄             |

### 边界行为

- **重复 get_logger**：多次调用 get_logger(name) 返回同一 logger 实例
- **set_level 影响范围**：影响所有已创建的 logger 和 handler
- **cleanup 后使用**：cleanup 后仍可调用 get_logger，但日志不会写入文件
- **线程安全**：logging 模块本身是线程安全的

## StyleService API 表

| 方法                      | 参数                                                  | 返回值        | 异常 | 线程安全             | 说明                                  |
| ------------------------- | ----------------------------------------------------- | ------------- | ---- | -------------------- | ------------------------------------- |
| `__init__()`              | 无                                                    | None          | 无   | 是                   | 初始化样式服务，连接 StyleSystem 信号 |
| `apply_theme()`           | theme_name: str<br>app: Optional[QApplication] = None | bool          | 无   | 否（需在主线程调用） | 应用主题到应用程序                    |
| `apply_to_widget()`       | widget: QWidget<br>theme_name: Optional[str] = None   | bool          | 无   | 否（需在主线程调用） | 应用主题到单个控件                    |
| `get_current_theme()`     | 无                                                    | Optional[str] | 无   | 是                   | 获取当前主题名称                      |
| `list_available_themes()` | 无                                                    | List[str]     | 无   | 是                   | 列出所有可用主题                      |
| `preload_themes()`        | theme_names: List[str]                                | None          | 无   | 是                   | 预加载主题到缓存                      |
| `clear_cache()`           | theme_name: Optional[str] = None                      | None          | 无   | 是                   | 清除主题缓存                          |

### 边界行为

- **无 QApplication 时 apply_theme**：返回 False 并记录错误日志
- **主题文件不存在**：返回 False 并记录错误日志
- **重复 apply_theme**：可以多次调用，每次都会重新加载并应用主题
- **线程安全**：apply_theme 和 apply_to_widget 必须在主线程调用（Qt 限制）

## PathService API 表

| 方法                  | 参数                   | 返回值 | 异常                | 线程安全 | 说明                                |
| --------------------- | ---------------------- | ------ | ------------------- | -------- | ----------------------------------- |
| `__init__()`          | 无                     | None   | 无                  | 是       | 初始化路径服务，创建 PathUtils 实例 |
| `get_user_data_dir()` | create: bool = True    | Path   | OSError（权限不足） | 是       | 获取用户数据目录                    |
| `get_config_dir()`    | create: bool = True    | Path   | OSError（权限不足） | 是       | 获取配置目录                        |
| `get_log_dir()`       | create: bool = True    | Path   | OSError（权限不足） | 是       | 获取日志目录                        |
| `get_cache_dir()`     | create: bool = True    | Path   | OSError（权限不足） | 是       | 获取缓存目录                        |
| `ensure_dir_exists()` | path: Union[str, Path] | Path   | OSError（权限不足） | 是       | 确保目录存在                        |
| `create_user_dirs()`  | 无                     | None   | OSError（权限不足） | 是       | 创建所有用户目录                    |

### 边界行为

- **create=False 且目录不存在**：返回路径但不创建目录
- **权限不足**：抛出 OSError 异常
- **路径已存在**：不会产生错误，直接返回路径
- **并发创建**：mkdir(parents=True, exist_ok=True) 是线程安全的

## 正式用例

### 用例 1：ThreadService 协作式取消

```python
from core.services import thread_service
import time

def long_running_task(cancel_token):
    """可取消的长时间运行任务"""
    for i in range(100):
        if cancel_token.is_cancelled():
            print("任务被取消")
            return None
        time.sleep(0.1)
        print(f"进度: {i+1}/100")
    return "任务完成"

def on_result(result):
    if result:
        print(f"结果: {result}")

# 启动任务
worker, token = thread_service.run_async(
    long_running_task,
    on_result=on_result
)

# 2秒后取消任务
time.sleep(2)
thread_service.cancel_task(token)
```

### 用例 2：ConfigService 配置管理

```python
from core.services import config_service
from pathlib import Path

# 首次访问，自动创建 ConfigManager
template_path = Path("core/config_templates/my_module_config.json")
config = config_service.get_module_config(
    "my_module",
    template_path=template_path
)

# 更新配置值
config_service.update_config_value(
    "my_module",
    "database.host",
    "localhost"
)

# 保存配置
config_service.save_module_config(
    "my_module",
    config,
    backup_reason="user_update"
)
```

## 实现细节补充

### ThreadManager/Worker 变更计划

**当前状态验证**（基于 `core/utils/thread_utils.py` 检查）：

```python
# Worker 类（第 38-90 行）
class Worker(QObject):
    def __init__(self, func: Callable, *args, **kwargs):
        super().__init__()
        self.func = func
        self.args = args
        self.kwargs = kwargs
        self.cancel_token = CancellationToken()  # ✅ 已存在

        # ✅ 已实现签名检测
        import inspect
        sig = inspect.signature(func)
        self._supports_cancellation = 'cancel_token' in sig.parameters

    def run(self):
        # ✅ 已实现自动注入
        if self._supports_cancellation:
            result = self.func(self.cancel_token, *self.args, **self.kwargs)
        else:
            result = self.func(*self.args, **self.kwargs)
```

**结论**：ThreadManager 和 Worker 已经完全支持所需功能，**无需任何修改**。

### DEBUG_SERVICES 完整实现

#### 读取优先级和方式

```python
# core/services/__init__.py

import os
from typing import Optional

def is_debug_enabled() -> bool:
    """检查是否启用调试模式

    优先级：
    1. 环境变量 DEBUG_SERVICES（最高优先级）
    2. 应用配置文件 app_config.json 中的 debug_services 字段
    3. 默认值 False

    Returns:
        bool: 是否启用调试模式
    """
    # 1. 环境变量优先
    env_debug = os.getenv('DEBUG_SERVICES', '').lower()
    if env_debug in ('1', 'true', 'yes', 'on'):
        return True
    if env_debug in ('0', 'false', 'no', 'off'):
        return False

    # 2. 配置文件次之
    try:
        # 延迟导入避免循环依赖
        from core.services import config_service
        app_config = config_service.get_module_config("app")
        return app_config.get("debug_services", False)
    except Exception:
        # 配置读取失败，使用默认值
        pass

    # 3. 默认值
    return False

# 使用示例
if is_debug_enabled():
    logger.debug(f"服务初始化: {service_name}")
    logger.debug(f"线程使用情况: {thread_usage}")
```

#### 配置文件格式

```json
// core/config_templates/app_config.json
{
  "_version": "1.0.0",
  "debug_services": false,
  "log_level": "INFO",
  "max_threads": 10
}
```

#### 环境变量设置方式

```bash
# Windows CMD
set DEBUG_SERVICES=1
python main.py

# Windows PowerShell
$env:DEBUG_SERVICES="1"
python main.py

# Linux/Mac
export DEBUG_SERVICES=1
python main.py

# 或者在代码中设置（用于测试）
import os
os.environ['DEBUG_SERVICES'] = '1'
```

### Logger 的 set_level/cleanup_handlers 合约

**当前状态**（基于 `core/logger.py` 检查）：

```python
# Logger 类已实现这些方法
class Logger:
    def set_level(self, level: int):
        """设置日志级别

        Args:
            level: 日志级别 (logging.DEBUG, logging.INFO, etc.)
        """
        self.logger.setLevel(level)
        for handler in self.logger.handlers:
            handler.setLevel(level)

    def cleanup_handlers(self):
        """清理日志处理器

        正确关闭所有日志处理器，释放资源。
        """
        for handler in self.logger.handlers[:]:
            try:
                handler.flush()
                handler.close()
                self.logger.removeHandler(handler)
            except Exception as e:
                print(f"警告: 清理日志处理器时出错: {e}")
```

**结论**：Logger 已经实现了所需方法，**无需修改**。

### 健康检查退化处理

```python
def perform_health_checks() -> Dict[str, bool]:
    """执行所有服务的健康检查

    Returns:
        Dict[str, bool]: 服务名称 -> 健康状态
    """
    results = {
        'thread_service': health_check_thread_service(),
        'config_service': health_check_config_service(),
        'log_service': health_check_log_service(),
        'style_service': health_check_style_service(),
        'path_service': health_check_path_service(),
    }

    # 统计失败的服务
    failed_services = [name for name, status in results.items() if not status]

    if failed_services:
        print(f"[WARNING] 以下服务健康检查失败: {', '.join(failed_services)}")
        print("[WARNING] 应用将继续运行，但部分功能可能不可用")
    else:
        print("[INFO] 所有服务健康检查通过")

    return results

# 退化处理示例
def safe_apply_theme(theme_name: str) -> bool:
    """安全地应用主题，失败时使用默认主题"""
    try:
        if style_service.apply_theme(theme_name):
            return True
        else:
            # 尝试使用默认主题
            print(f"[WARNING] 主题 {theme_name} 应用失败，使用默认主题")
            return style_service.apply_theme("default")
    except Exception as e:
        print(f"[ERROR] 应用主题时出错: {e}")
        return False
```

### 清理退化处理

```python
def cleanup_all_services_with_timeout(timeout: float = 5.0) -> bool:
    """带超时的服务清理

    Args:
        timeout: 超时时间（秒）

    Returns:
        bool: 是否在超时前完成清理
    """
    import threading
    import time

    cleanup_complete = threading.Event()

    def cleanup_thread():
        try:
            cleanup_all_services()
            cleanup_complete.set()
        except Exception as e:
            print(f"[ERROR] 清理服务时出错: {e}")
            cleanup_complete.set()

    thread = threading.Thread(target=cleanup_thread, daemon=True)
    thread.start()

    # 等待清理完成或超时
    if cleanup_complete.wait(timeout):
        print("[INFO] 服务清理完成")
        return True
    else:
        print(f"[WARNING] 服务清理超时（{timeout}秒），强制退出")
        return False
```

## 可测试性补充

### 集成测试场景表

| 测试场景                   | 前置条件               | 操作步骤                                                   | 预期结果                               | 预期日志                                                                           | 预期状态                                     |
| -------------------------- | ---------------------- | ---------------------------------------------------------- | -------------------------------------- | ---------------------------------------------------------------------------------- | -------------------------------------------- |
| **服务单例验证**           | 无                     | 1. 多次导入 log_service<br>2. 比较实例 ID                  | 所有实例 ID 相同                       | 无                                                                                 | 所有服务状态为 INITIALIZED                   |
| **依赖顺序验证**           | 无                     | 1. 访问 config_service<br>2. 检查 log_service 是否已初始化 | log_service 先于 config_service 初始化 | "[LogService] 初始化完成"<br>"[ConfigService] 已初始化"                            | log: INITIALIZED<br>config: INITIALIZED      |
| **ThreadService 成功场景** | 无                     | 1. 提交任务<br>2. 等待完成                                 | 任务成功执行，回调被调用               | "[ThreadService] 初始化完成"<br>"开始执行任务: task_name"<br>"任务完成: task_name" | thread: INITIALIZED<br>active_threads: 0     |
| **ThreadService 取消场景** | 无                     | 1. 提交长任务<br>2. 立即取消<br>3. 等待完成                | 任务被取消，返回 None                  | "任务取消请求已发送: task_name"<br>"任务被取消: task_name"                         | thread: INITIALIZED<br>active_threads: 0     |
| **ThreadService 失败场景** | 无                     | 1. 提交会抛异常的任务<br>2. 等待完成                       | 错误回调被调用                         | "任务执行失败: task_name, 错误: ..."                                               | thread: INITIALIZED<br>active_threads: 0     |
| **ConfigService 读写**     | 模板文件存在           | 1. 读取配置<br>2. 修改配置<br>3. 保存配置<br>4. 重新读取   | 配置正确保存和读取                     | "成功加载配置模板: ..."<br>"成功保存用户配置: ..."                                 | config: INITIALIZED<br>配置文件已更新        |
| **ConfigService 备份恢复** | 配置文件存在           | 1. 保存配置（触发备份）<br>2. 损坏配置文件<br>3. 重新读取  | 自动从备份恢复                         | "备份当前配置，原因: ..."<br>"使用备份配置作为回退方案"                            | config: INITIALIZED<br>配置已恢复            |
| **StyleService 主题切换**  | QApplication 已创建    | 1. 应用主题 A<br>2. 应用主题 B                             | 主题成功切换，信号被触发               | "成功应用主题到应用程序: theme_a"<br>"成功应用主题到应用程序: theme_b"             | style: INITIALIZED<br>current_theme: theme_b |
| **StyleService 无 QApp**   | QApplication 未创建    | 1. 尝试应用主题                                            | 返回 False，记录错误                   | "无法获取 QApplication 实例"                                                       | style: INITIALIZED<br>current_theme: None    |
| **PathService 目录创建**   | 目录不存在             | 1. 获取用户数据目录                                        | 目录被创建                             | "用户数据目录路径: ..."                                                            | path: INITIALIZED<br>目录已创建              |
| **循环依赖检测**           | 无                     | 1. 模拟 Level 1 服务访问 Level 2 服务                      | 抛出 CircularDependencyError           | "检测到循环依赖: ..."                                                              | 服务初始化失败                               |
| **重入访问**               | 服务正在初始化         | 1. 在服务初始化中访问自身                                  | 返回正在初始化的实例                   | 无错误日志                                                                         | 服务继续初始化                               |
| **清理顺序**               | 所有服务已初始化       | 1. 调用 cleanup_all_services()                             | 按 Level 2→1→0 顺序清理                | "[Services] 清理 ThreadService 时出错: ..."（如果有错误）                          | 所有服务状态为 NOT_INITIALIZED               |
| **清理超时**               | ThreadService 有长任务 | 1. 提交长任务<br>2. 立即清理                               | 等待 5 秒后超时警告                    | "[WARNING] 服务清理超时（5 秒），强制退出"                                         | thread: NOT_INITIALIZED                      |

### 最小单元测试集合

#### 测试文件结构

```
tests/
├── unit/
│   ├── test_thread_service.py      # ThreadService 单元测试
│   ├── test_config_service.py      # ConfigService 单元测试
│   ├── test_log_service.py         # LogService 单元测试
│   ├── test_style_service.py       # StyleService 单元测试
│   ├── test_path_service.py        # PathService 单元测试
│   └── test_service_layer.py       # 服务层单例和依赖测试
├── integration/
│   ├── test_service_lifecycle.py   # 服务生命周期集成测试
│   ├── test_thread_cancellation.py # 线程取消集成测试
│   └── test_config_backup.py       # 配置备份恢复集成测试
└── fixtures/
    ├── test_config.json             # 测试配置文件
    └── test_theme.qss               # 测试主题文件
```

#### 运行方式

```bash
# 运行所有测试
pytest tests/

# 运行单元测试
pytest tests/unit/

# 运行集成测试
pytest tests/integration/

# 运行特定测试文件
pytest tests/unit/test_thread_service.py

# 运行特定测试用例
pytest tests/unit/test_thread_service.py::test_run_async_success

# 带覆盖率报告
pytest --cov=core/services tests/
```

#### 前置条件

1. 安装测试依赖：`pip install pytest pytest-cov pytest-qt`
2. 确保 `core/services/` 目录已创建
3. 确保测试配置文件和主题文件存在

#### 断言内容示例

```python
# test_thread_service.py
def test_run_async_success():
    """测试异步任务成功执行"""
    from core.services import thread_service
    import time

    result_holder = []

    def task():
        time.sleep(0.1)
        return "success"

    def on_result(result):
        result_holder.append(result)

    worker, token = thread_service.run_async(task, on_result=on_result)

    # 等待任务完成
    time.sleep(0.5)

    # 断言
    assert len(result_holder) == 1
    assert result_holder[0] == "success"
    assert not token.is_cancelled()

def test_cancel_task():
    """测试任务取消"""
    from core.services import thread_service
    import time

    cancelled = []

    def task(cancel_token):
        for i in range(100):
            if cancel_token.is_cancelled():
                cancelled.append(True)
                return None
            time.sleep(0.01)
        return "completed"

    worker, token = thread_service.run_async(task)
    time.sleep(0.1)
    thread_service.cancel_task(token)
    time.sleep(0.2)

    # 断言
    assert len(cancelled) == 1
    assert cancelled[0] is True
    assert token.is_cancelled()
```
