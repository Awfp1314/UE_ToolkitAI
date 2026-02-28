"""
服务层异常定义

定义服务层使用的所有异常类型
"""


class ServiceError(Exception):
    """服务层基础异常"""
    pass


class ServiceInitializationError(ServiceError):
    """服务初始化异常"""
    pass


class CircularDependencyError(ServiceError):
    """循环依赖异常"""
    pass


class ConfigError(ServiceError):
    """配置服务异常"""
    pass


class ThreadError(ServiceError):
    """线程服务异常"""
    pass


class StyleError(ServiceError):
    """样式服务异常"""
    pass


class PathError(ServiceError):
    """路径服务异常"""
    pass

