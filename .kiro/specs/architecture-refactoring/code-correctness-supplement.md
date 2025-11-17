# Code Correctness Supplement

## 完整类型签名

### ThreadService 完整类型签名

```python
from typing import Callable, Optional, Tuple, Dict, Union, Any, TypeVar
from PyQt6.QtCore import QThread
from core.utils.thread_utils import ThreadManager, Worker, CancellationToken

T = TypeVar('T')

class ThreadService:
    """统一的线程调度服务"""

    def __init__(self) -> None:
        """初始化线程服务"""
        self._thread_manager: ThreadManager = ThreadManager()
        print("[ThreadService] 初始化完成")

    def run_async(
        self,
        task_func: Callable[..., T],
        on_result: Optional[Callable[[T], None]] = None,
        on_error: Optional[Callable[[str], None]] = None,
        on_finished: Optional[Callable[[], None]] = None,
        on_progress: Optional[Callable[[int], None]] = None,
        *args: Any,
        **kwargs: Any
    ) -> Tuple[Worker, CancellationToken]:
        """异步执行任务"""
        ...

    def cancel_task(self, task_identifier: Union[Worker, CancellationToken]) -> None:
        """取消任务（协作式取消）"""
        ...

    def get_thread_usage(self) -> Dict[str, Union[int, float]]:
        """获取线程使用情况"""
        ...

    def cleanup(self) -> None:
        """清理所有线程资源"""
        ...
```

### ConfigService 完整类型签名

```python
from typing import Dict, Any, Optional
from pathlib import Path
from core.config.config_manager import ConfigManager

class ConfigService:
    """统一的配置访问服务"""

    def __init__(self) -> None:
        """初始化配置服务"""
        self._config_managers: Dict[str, ConfigManager] = {}
        self._logger: logging.Logger = ...

    def _get_or_create_manager(
        self,
        module_name: str,
        template_path: Optional[Path] = None
    ) -> ConfigManager:
        """获取或创建 ConfigManager 实例"""
        ...

    def get_module_config(
        self,
        module_name: str,
        template_path: Optional[Path] = None,
        force_reload: bool = False
    ) -> Dict[str, Any]:
        """获取模块配置"""
        ...

    def save_module_config(
        self,
        module_name: str,
        config: Dict[str, Any],
        backup_reason: str = "manual_save"
    ) -> bool:
        """保存模块配置"""
        ...

    def update_config_value(
        self,
        module_name: str,
        key: str,
        value: Any
    ) -> bool:
        """更新配置值"""
        ...

    def clear_cache(self, module_name: Optional[str] = None) -> None:
        """清除配置缓存"""
        ...
```

### LogService 完整类型签名

```python
import logging
from core.logger import Logger

class LogService:
    """统一的日志服务"""

    def __init__(self) -> None:
        """初始化日志服务"""
        self._logger_instance: Logger = Logger()
        print("[LogService] 初始化完成")

    def get_logger(self, name: str) -> logging.Logger:
        """获取日志记录器"""
        ...

    def set_level(self, level: int) -> None:
        """设置全局日志级别"""
        ...

    def cleanup(self) -> None:
        """清理日志处理器"""
        ...
```

### StyleService 完整类型签名

```python
from typing import List, Optional
from PyQt6.QtWidgets import QApplication, QWidget
from PyQt6.QtCore import pyqtSignal, QObject
from core.utils.style_system import StyleSystem

class StyleService(QObject):
    """统一的样式服务"""

    themeChanged: pyqtSignal = pyqtSignal(str)

    def __init__(self) -> None:
        """初始化样式服务"""
        super().__init__()
        self._style_system: StyleSystem = ...
        self._logger: logging.Logger = ...

    def apply_theme(
        self,
        theme_name: str,
        app: Optional[QApplication] = None
    ) -> bool:
        """应用主题"""
        ...

    def apply_to_widget(
        self,
        widget: QWidget,
        theme_name: Optional[str] = None
    ) -> bool:
        """应用主题到控件"""
        ...

    def get_current_theme(self) -> Optional[str]:
        """获取当前主题名称"""
        ...

    def list_available_themes(self) -> List[str]:
        """列出所有可用主题"""
        ...

    def preload_themes(self, theme_names: List[str]) -> None:
        """预加载主题到缓存"""
        ...

    def clear_cache(self, theme_name: Optional[str] = None) -> None:
        """清除主题缓存"""
        ...
```

### PathService 完整类型签名

```python
from pathlib import Path
from typing import Union
from core.utils.path_utils import PathUtils

class PathService:
    """统一的路径访问服务"""

    def __init__(self) -> None:
        """初始化路径服务"""
        self._path_utils: PathUtils = PathUtils()
        print("[PathService] 初始化完成")

    def get_user_data_dir(self, create: bool = True) -> Path:
        """获取用户数据目录"""
        ...

    def get_config_dir(self, create: bool = True) -> Path:
        """获取配置目录"""
        ...

    def get_log_dir(self, create: bool = True) -> Path:
        """获取日志目录"""
        ...

    def get_cache_dir(self, create: bool = True) -> Path:
        """获取缓存目录"""
        ...

    def ensure_dir_exists(self, path: Union[str, Path]) -> Path:
        """确保目录存在"""
        ...

    def create_user_dirs(self) -> None:
        """创建所有用户目录"""
        ...
```

## 线程安全策略

### \_LazyService 线程安全分析

```python
class _LazyService:
    """懒加载服务包装器

    线程安全策略：
    1. _getter 函数内部使用全局锁保护单例创建
    2. _instance 缓存在首次调用后不再改变
    3. __getattr__ 只读取 _instance，不修改状态

    结论：在多线程环境下是安全的
    """
    def __init__(self, getter_func):
        self._getter = getter_func
        self._instance = None  # 只在 __call__ 中写入一次

    def __call__(self):
        # 线程安全：_getter 内部有锁保护
        if self._instance is None:
            self._instance = self._getter()
        return self._instance

    def __getattr__(self, name):
        # 线程安全：只读取，不修改
        return getattr(self(), name)
```

### 服务初始化线程安全

```python
# core/services/__init__.py

import threading

# 全局锁保护服务初始化
_service_init_lock = threading.Lock()

def _get_log_service():
    """获取日志服务单例（线程安全）"""
    global _log_service, _service_states, _service_init_lock

    if _log_service is None:
        with _service_init_lock:  # 使用锁保护
            # 双重检查锁定模式
            if _log_service is None:
                _check_circular_dependency('log')
                _service_states['log'] = ServiceState.INITIALIZING

                from core.services.log_service import LogService
                _log_service = LogService()

                _service_states['log'] = ServiceState.INITIALIZED

    return _log_service
```

### 服务方法线程安全保证

| 服务              | 方法                  | 线程安全 | 说明                             |
| ----------------- | --------------------- | -------- | -------------------------------- |
| **ThreadService** | 所有方法              | ✅ 是    | ThreadManager 内部使用锁和信号量 |
| **ConfigService** | get_module_config     | ✅ 是    | ConfigManager 使用缓存和文件锁   |
| **ConfigService** | save_module_config    | ✅ 是    | 文件写入是原子操作               |
| **ConfigService** | update_config_value   | ✅ 是    | 内部调用 save_module_config      |
| **LogService**    | get_logger            | ✅ 是    | logging 模块是线程安全的         |
| **LogService**    | set_level             | ✅ 是    | logging 模块是线程安全的         |
| **StyleService**  | apply_theme           | ❌ 否    | 必须在主线程调用（Qt 限制）      |
| **StyleService**  | apply_to_widget       | ❌ 否    | 必须在主线程调用（Qt 限制）      |
| **StyleService**  | get_current_theme     | ✅ 是    | 只读取，不修改状态               |
| **StyleService**  | list_available_themes | ✅ 是    | 只读取文件系统                   |
| **PathService**   | 所有方法              | ✅ 是    | Path 操作和 mkdir 是线程安全的   |

### 线程安全使用示例

```python
# ✅ 正确：在工作线程中使用线程安全的服务
def worker_task():
    # 线程安全：可以在工作线程中调用
    logger = log_service.get_logger("worker")
    logger.info("工作线程开始")

    config = config_service.get_module_config("my_module")
    data_dir = path_service.get_user_data_dir()

    # 执行工作
    result = process_data(config, data_dir)

    logger.info("工作线程完成")
    return result

# ❌ 错误：在工作线程中调用非线程安全的方法
def worker_task_wrong():
    # 非线程安全：不能在工作线程中调用
    style_service.apply_theme("dark")  # 会崩溃或失败

# ✅ 正确：在主线程中应用主题
def worker_task_correct():
    return "dark"

def on_result(theme_name):
    # 在主线程中调用
    style_service.apply_theme(theme_name)

thread_service.run_async(worker_task_correct, on_result=on_result)
```

## 健康检查容错处理

### 增强的健康检查实现

```python
from typing import Dict, Optional, Callable
from enum import Enum

class HealthStatus(Enum):
    """健康状态枚举"""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"

class HealthCheckResult:
    """健康检查结果"""
    def __init__(
        self,
        status: HealthStatus,
        message: str = "",
        details: Optional[Dict[str, Any]] = None
    ):
        self.status = status
        self.message = message
        self.details = details or {}

    def is_healthy(self) -> bool:
        return self.status == HealthStatus.HEALTHY

    def __repr__(self) -> str:
        return f"HealthCheckResult(status={self.status.value}, message={self.message})"

def health_check_thread_service_enhanced() -> HealthCheckResult:
    """增强的 ThreadService 健康检查"""
    try:
        usage = thread_service.get_thread_usage()
        active = usage['active']
        max_threads = usage['max']
        usage_percent = usage['usage_percent']

        if active < max_threads * 0.8:
            return HealthCheckResult(
                HealthStatus.HEALTHY,
                f"线程池健康，使用率 {usage_percent:.1f}%",
                usage
            )
        elif active < max_threads:
            return HealthCheckResult(
                HealthStatus.DEGRADED,
                f"线程池接近满载，使用率 {usage_percent:.1f}%",
                usage
            )
        else:
            return HealthCheckResult(
                HealthStatus.UNHEALTHY,
                f"线程池已满，使用率 {usage_percent:.1f}%",
                usage
            )
    except Exception as e:
        return HealthCheckResult(
            HealthStatus.UNKNOWN,
            f"健康检查失败: {e}"
        )

def perform_health_checks_enhanced() -> Dict[str, HealthCheckResult]:
    """执行所有服务的增强健康检查"""
    checks: Dict[str, Callable[[], HealthCheckResult]] = {
        'thread_service': health_check_thread_service_enhanced,
        'config_service': health_check_config_service_enhanced,
        'log_service': health_check_log_service_enhanced,
        'style_service': health_check_style_service_enhanced,
        'path_service': health_check_path_service_enhanced,
    }

    results = {}
    for service_name, check_func in checks.items():
        try:
            results[service_name] = check_func()
        except Exception as e:
            results[service_name] = HealthCheckResult(
                HealthStatus.UNKNOWN,
                f"健康检查异常: {e}"
            )

    # 打印摘要
    healthy_count = sum(1 for r in results.values() if r.is_healthy())
    total_count = len(results)

    if healthy_count == total_count:
        print(f"[INFO] 所有服务健康 ({healthy_count}/{total_count})")
    else:
        print(f"[WARNING] 部分服务不健康 ({healthy_count}/{total_count})")
        for service_name, result in results.items():
            if not result.is_healthy():
                print(f"  - {service_name}: {result.status.value} - {result.message}")

    return results
```

## 避免伪代码歧义

### 明确的实现示例

**❌ 歧义的伪代码**：

```python
# 不清楚具体如何实现
def cleanup():
    # 清理资源
    ...
```

**✅ 明确的实现**：

```python
def cleanup(self) -> None:
    """清理所有线程资源

    实现细节：
    1. 调用 ThreadManager.cleanup()
    2. ThreadManager 会：
       - 调用所有 Worker 的 cancel() 方法
       - 等待所有线程完成（最多5秒）
       - 如果超时，记录警告但不阻塞
    3. 清理完成后，线程列表被清空
    """
    self._thread_manager.cleanup()
```

### 明确的错误处理

**❌ 歧义的错误处理**：

```python
try:
    do_something()
except:
    # 处理错误
    pass
```

**✅ 明确的错误处理**：

```python
try:
    config = config_service.get_module_config("my_module")
except FileNotFoundError as e:
    # 模板文件不存在
    logger.error(f"配置模板不存在: {e}")
    # 使用默认配置
    config = {"key": "default_value"}
except json.JSONDecodeError as e:
    # 配置文件格式错误
    logger.error(f"配置文件格式错误: {e}")
    # 尝试从备份恢复
    config = config_service._config_managers["my_module"].restore_from_backup()
    if not config:
        # 备份也失败，使用默认配置
        config = {"key": "default_value"}
except Exception as e:
    # 其他未预期的错误
    logger.error(f"加载配置时出错: {e}", exc_info=True)
    raise
```
