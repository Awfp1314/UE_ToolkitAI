# -*- coding: utf-8 -*-

"""
UE Toolkit 自定义异常类
提供具体的异常类型以改进错误处理和调试
"""


class UEToolkitError(Exception):
    """UE Toolkit 基础异常类
    
    所有 UE Toolkit 特定异常的基类
    """
    pass


class ConfigError(UEToolkitError):
    """配置相关错误
    
    当配置文件操作失败、配置数据无效或配置访问出错时抛出
    
    Examples:
        - 配置文件损坏
        - 配置文件锁定超时
        - 必需的配置键缺失
        - 配置值类型错误
    """
    pass


class AssetError(UEToolkitError):
    """资产管理相关错误
    
    当资产操作失败、资产数据无效或资产访问出错时抛出
    
    Examples:
        - 资产文件不存在
        - 资产库路径无效
        - 资产扫描失败
        - 缩略图生成失败
    """
    pass


class ThreadError(UEToolkitError):
    """线程管理相关错误
    
    当线程操作失败、任务队列满或线程资源耗尽时抛出
    
    Examples:
        - 任务队列已满
        - 线程池耗尽
        - 任务超时
        - 任务取消失败
    """
    pass


__all__ = [
    'UEToolkitError',
    'ConfigError',
    'AssetError',
    'ThreadError',
]
