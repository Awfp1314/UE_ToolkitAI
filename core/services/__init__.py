"""
统一服务层入口

提供模块级单例访问接口，支持懒加载和依赖管理

## 架构设计

服务层采用三级依赖架构：
- **Level 0**（无依赖）：LogService, PathService
- **Level 1**（依赖 Level 0）：ConfigService, StyleService
- **Level 2**（依赖 Level 0 和 Level 1）：ThreadService

## 核心特性

1. **单例模式**：每个服务全局唯一实例，避免资源浪费
2. **懒加载**：服务在首次使用时才初始化，加快启动速度
3. **依赖管理**：自动检测循环依赖，确保初始化顺序正确
4. **统一清理**：cleanup_all_services() 按依赖逆序清理所有服务

## 使用方式

### 基础用法
```python
from core.services import log_service, thread_service, config_service

# 获取日志记录器
logger = log_service.get_logger("my_module")

# 运行异步任务 (v5.2.1: 返回3个值)
worker, token, task_id = thread_service.run_async(my_task, on_result=callback)

# 获取配置
config = config_service.get_module_config("my_module", template_path=path)
```

### 服务清理
```python
from core.services import cleanup_all_services

# 应用退出时清理所有服务
cleanup_all_services()
```

### 调试模式
```python
from core.services import is_debug_enabled

if is_debug_enabled():
    print("调试模式已启用")
```

## 注意事项

1. **不要在工作线程中初始化服务**：某些服务（如 StyleService）依赖 Qt 主线程
2. **不要手动创建服务实例**：始终通过模块级单例访问
3. **清理顺序很重要**：cleanup_all_services() 会按依赖逆序清理，不要手动清理单个服务
"""

import os
from enum import Enum
from typing import Optional


# ============================================================================
# 服务初始化状态
# ============================================================================

class ServiceState(Enum):
    """服务初始化状态"""
    NOT_INITIALIZED = 0  # 未初始化
    INITIALIZING = 1     # 正在初始化
    INITIALIZED = 2      # 已初始化


# ============================================================================
# 服务实例和状态（模块级全局变量）
# ============================================================================

_thread_service: Optional['ThreadService'] = None
_config_service: Optional['ConfigService'] = None
_log_service: Optional['LogService'] = None
_style_service: Optional['StyleService'] = None
_path_service: Optional['PathService'] = None

_service_states = {
    'thread': ServiceState.NOT_INITIALIZED,
    'config': ServiceState.NOT_INITIALIZED,
    'log': ServiceState.NOT_INITIALIZED,
    'style': ServiceState.NOT_INITIALIZED,
    'path': ServiceState.NOT_INITIALIZED,
}


# ============================================================================
# 工具函数
# ============================================================================

def is_debug_enabled() -> bool:
    """检查是否启用调试模式

    优先级：环境变量 > 配置文件

    Returns:
        是否启用调试
    """
    # 环境变量优先
    env_debug = os.getenv('DEBUG_SERVICES', '').lower()
    if env_debug in ('1', 'true', 'yes'):
        return True

    # 从配置文件读取
    try:
        app_config = _get_config_service().get_module_config("app")
        return app_config.get("debug_services", False)
    except Exception:
        # 配置文件读取失败，返回 False
        pass

    return False


def _check_circular_dependency(service_name: str, requesting_service: Optional[str] = None) -> None:
    """检查循环依赖
    
    Args:
        service_name: 被请求的服务名称
        requesting_service: 请求服务的名称
        
    Raises:
        CircularDependencyError: 如果检测到循环依赖
    """
    from core.services.exceptions import CircularDependencyError
    
    state = _service_states.get(service_name)
    if state == ServiceState.INITIALIZING:
        if requesting_service and requesting_service != service_name:
            raise CircularDependencyError(
                f"检测到循环依赖: {requesting_service} 试图访问正在初始化的 {service_name}"
            )


# ============================================================================
# 服务 Getter 函数
# ============================================================================

# Level 0 服务（无依赖）

def _get_log_service() -> 'LogService':
    """获取日志服务单例（内部函数）

    Returns:
        LogService 实例
    """
    global _log_service, _service_states

    if _log_service is None:
        _check_circular_dependency('log')
        _service_states['log'] = ServiceState.INITIALIZING

        if is_debug_enabled():
            print("[DEBUG] 正在初始化 LogService...")

        from core.services._log_service import LogService
        _log_service = LogService()

        _service_states['log'] = ServiceState.INITIALIZED

        if is_debug_enabled():
            print("[DEBUG] LogService 初始化完成")

    return _log_service


def _get_path_service() -> 'PathService':
    """获取路径服务单例（内部函数）

    Returns:
        PathService 实例
    """
    global _path_service, _service_states

    if _path_service is None:
        _check_circular_dependency('path')
        _service_states['path'] = ServiceState.INITIALIZING

        if is_debug_enabled():
            print("[DEBUG] 正在初始化 PathService...")

        from core.services._path_service import PathService
        _path_service = PathService()

        _service_states['path'] = ServiceState.INITIALIZED

        if is_debug_enabled():
            print("[DEBUG] PathService 初始化完成")

    return _path_service


# Level 1 服务（可依赖 Level 0）

def _get_config_service() -> 'ConfigService':
    """获取配置服务单例（内部函数）
    
    Returns:
        ConfigService 实例
    """
    global _config_service, _service_states

    if _config_service is None:
        _check_circular_dependency('config')
        _service_states['config'] = ServiceState.INITIALIZING

        from core.services._config_service import ConfigService
        _config_service = ConfigService()

        _service_states['config'] = ServiceState.INITIALIZED

    return _config_service


def _get_style_service() -> 'StyleService':
    """获取样式服务单例（内部函数）
    
    Returns:
        StyleService 实例
    """
    global _style_service, _service_states

    if _style_service is None:
        _check_circular_dependency('style')
        _service_states['style'] = ServiceState.INITIALIZING

        from core.services._style_service import StyleService
        _style_service = StyleService()

        _service_states['style'] = ServiceState.INITIALIZED

    return _style_service


# Level 2 服务（可依赖 Level 0 和 Level 1）

def _get_thread_service() -> 'ThreadService':
    """获取线程服务单例（内部函数）
    
    Returns:
        ThreadService 实例
    """
    global _thread_service, _service_states

    if _thread_service is None:
        _check_circular_dependency('thread')
        _service_states['thread'] = ServiceState.INITIALIZING

        from core.services._thread_service import ThreadService
        _thread_service = ThreadService()

        _service_states['thread'] = ServiceState.INITIALIZED
        _get_log_service().get_logger("services").info("ThreadService 已初始化")

    return _thread_service


# ============================================================================
# 懒加载服务包装器
# ============================================================================

class _LazyService:
    """懒加载服务包装器

    支持两种访问方式：
    1. 作为函数调用：log_service()
    2. 直接访问属性：log_service.get_logger()

    注意：
    - _getter 函数内部已实现单例模式（通过全局变量）
    - _instance 只是缓存 getter 的返回值，避免重复调用
    - 这种双层缓存设计虽有轻微开销，但保证了访问一致性
    """
    def __init__(self, getter_func):
        self._getter = getter_func
        self._instance = None

    def __call__(self):
        if self._instance is None:
            self._instance = self._getter()
        return self._instance

    def __getattr__(self, name):
        # 支持直接访问服务方法，如 log_service.get_logger()
        return getattr(self(), name)


# ============================================================================
# 服务清理函数
# ============================================================================

def cleanup_all_services() -> None:
    """清理所有服务（按依赖顺序：Level 2 → Level 1 → Level 0）

    清理顺序：
    1. Level 2: ThreadService
    2. Level 1: StyleService, ConfigService
    3. Level 0: PathService, LogService

    注意：
    - 按照依赖关系逆序清理，避免依赖问题
    - 清理后重置服务实例和状态
    - 清理失败不会中断整个流程，会记录错误并继续
    """
    global _thread_service, _style_service, _config_service, _path_service, _log_service
    global _service_states

    # 获取 logger（在清理前）
    logger = None
    if _log_service is not None:
        try:
            logger = _log_service.get_logger("services")
            logger.info("开始清理所有服务...")
        except:
            pass

    # Level 2: ThreadService
    if _thread_service is not None:
        try:
            if logger:
                logger.info("清理 ThreadService...")
            _thread_service.cleanup()
            _thread_service = None
            _service_states['thread'] = ServiceState.NOT_INITIALIZED
            if logger:
                logger.info("ThreadService 清理完成")
        except Exception as e:
            if logger:
                logger.error(f"ThreadService 清理失败: {e}", exc_info=True)
            else:
                try:
                    from core.logger import safe_print
                    safe_print(f"[ERROR] ThreadService 清理失败: {e}")
                except Exception:
                    pass

    # Level 1: StyleService
    if _style_service is not None:
        try:
            if logger:
                logger.info("清理 StyleService...")
            # StyleService 没有 cleanup() 方法，直接重置
            _style_service = None
            _service_states['style'] = ServiceState.NOT_INITIALIZED
            if logger:
                logger.info("StyleService 清理完成")
        except Exception as e:
            if logger:
                logger.error(f"StyleService 清理失败: {e}", exc_info=True)
            else:
                try:
                    from core.logger import safe_print
                    safe_print(f"[ERROR] StyleService 清理失败: {e}")
                except Exception:
                    pass

    # Level 1: ConfigService
    if _config_service is not None:
        try:
            if logger:
                logger.info("清理 ConfigService...")
            # ConfigService 没有 cleanup() 方法，直接重置
            _config_service = None
            _service_states['config'] = ServiceState.NOT_INITIALIZED
            if logger:
                logger.info("ConfigService 清理完成")
        except Exception as e:
            if logger:
                logger.error(f"ConfigService 清理失败: {e}", exc_info=True)
            else:
                try:
                    from core.logger import safe_print
                    safe_print(f"[ERROR] ConfigService 清理失败: {e}")
                except Exception:
                    pass

    # Level 0: PathService
    if _path_service is not None:
        try:
            if logger:
                logger.info("清理 PathService...")
            # PathService 没有 cleanup() 方法，直接重置
            _path_service = None
            _service_states['path'] = ServiceState.NOT_INITIALIZED
            if logger:
                logger.info("PathService 清理完成")
        except Exception as e:
            if logger:
                logger.error(f"PathService 清理失败: {e}", exc_info=True)
            else:
                try:
                    from core.logger import safe_print
                    safe_print(f"[ERROR] PathService 清理失败: {e}")
                except Exception:
                    pass

    # Level 0: LogService（最后清理）
    if _log_service is not None:
        try:
            if logger:
                logger.info("清理 LogService...")
            _log_service.cleanup()
            _log_service = None
            _service_states['log'] = ServiceState.NOT_INITIALIZED
        except Exception as e:
            try:
                from core.logger import safe_print
                safe_print(f"[ERROR] LogService 清理失败: {e}")
            except Exception:
                pass


# ============================================================================
# 模块级导出（支持 from core.services import log_service）
# ============================================================================

log_service = _LazyService(_get_log_service)
path_service = _LazyService(_get_path_service)
config_service = _LazyService(_get_config_service)
style_service = _LazyService(_get_style_service)
thread_service = _LazyService(_get_thread_service)


# ============================================================================
# 模块导出
# ============================================================================

__all__ = [
    # 工具函数
    'is_debug_enabled',
    'cleanup_all_services',
    # Level 0 服务
    'log_service',
    'path_service',
    # Level 1 服务
    'config_service',
    'style_service',
    # Level 2 服务
    'thread_service',
    # 枚举和异常（供高级用户使用）
    'ServiceState',
]
