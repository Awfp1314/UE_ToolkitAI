"""
统一服务层入口

提供模块级单例访问接口，支持懒加载和依赖管理

使用方式:
    from core.services import log_service, thread_service, config_service
    
    # 获取日志记录器
    logger = log_service.get_logger("my_module")
    
    # 运行异步任务
    worker, token = thread_service.run_async(my_task, on_result=callback)
    
    # 获取配置
    config = config_service.get_module_config("my_module", template_path=path)
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
    
    # TODO: 从配置文件读取（未来实现）
    # try:
    #     from core.services import config_service
    #     app_config = config_service.get_module_config("app")
    #     return app_config.get("debug_services", False)
    # except:
    #     pass
    
    return False


def _check_circular_dependency(service_name: str, requesting_service: Optional[str] = None):
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

def _get_log_service():
    """获取日志服务单例（内部函数）

    Returns:
        LogService 实例
    """
    global _log_service, _service_states

    if _log_service is None:
        _check_circular_dependency('log')
        _service_states['log'] = ServiceState.INITIALIZING

        from core.services.log_service import LogService
        _log_service = LogService()

        _service_states['log'] = ServiceState.INITIALIZED

    return _log_service


def _get_path_service():
    """获取路径服务单例（内部函数）

    Returns:
        PathService 实例
    """
    global _path_service, _service_states

    if _path_service is None:
        _check_circular_dependency('path')
        _service_states['path'] = ServiceState.INITIALIZING

        from core.services.path_service import PathService
        _path_service = PathService()

        _service_states['path'] = ServiceState.INITIALIZED

    return _path_service


# Level 1 服务（可依赖 Level 0）
# def _get_config_service(): ...
# def _get_style_service(): ...

# Level 2 服务（可依赖 Level 0 和 Level 1）
# def _get_thread_service(): ...


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
# 服务清理函数（将在后续任务中实现）
# ============================================================================

# def cleanup_all_services(): ...


# ============================================================================
# 模块级导出（支持 from core.services import log_service）
# ============================================================================

log_service = _LazyService(_get_log_service)
path_service = _LazyService(_get_path_service)


# ============================================================================
# 模块导出
# ============================================================================

__all__ = [
    # 工具函数
    'is_debug_enabled',
    # Level 0 服务
    'log_service',
    'path_service',
    # 服务实例（将在后续任务中添加）
    # 'config_service',
    # 'style_service',
    # 'thread_service',
    # 'cleanup_all_services',
]

