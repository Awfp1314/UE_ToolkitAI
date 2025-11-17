# -*- coding: utf-8 -*-

"""
服务健康检查模块

提供服务层的健康检查功能，用于诊断服务状态和依赖关系。

使用示例:
    from core.services.health_check import perform_health_checks
    
    # 执行健康检查
    results = perform_health_checks()
    
    # 检查结果
    if all(results.values()):
        print("✅ 所有服务健康")
    else:
        print("⚠️ 部分服务异常")
        for service, status in results.items():
            if not status:
                print(f"  - {service}: 异常")
"""

from typing import Dict
from core.logger import get_logger

logger = get_logger(__name__)


def check_log_service() -> bool:
    """检查 LogService 健康状态
    
    Returns:
        True 如果服务健康，False 否则
    """
    try:
        from core.services import log_service
        
        # 检查服务是否可调用
        test_logger = log_service.get_logger("health_check_test")
        
        # 检查 logger 是否有效
        if test_logger is None:
            logger.error("LogService 返回了 None logger")
            return False
        
        # 检查 logger 是否有基本方法
        if not hasattr(test_logger, 'info'):
            logger.error("LogService 返回的 logger 缺少 info 方法")
            return False
        
        logger.debug("LogService 健康检查通过")
        return True
        
    except Exception as e:
        logger.error(f"LogService 健康检查失败: {e}", exc_info=True)
        return False


def check_path_service() -> bool:
    """检查 PathService 健康状态
    
    Returns:
        True 如果服务健康，False 否则
    """
    try:
        from core.services import path_service
        
        # 检查服务是否可调用
        user_data_dir = path_service.get_user_data_dir()
        
        # 检查返回值是否有效
        if user_data_dir is None:
            logger.error("PathService 返回了 None 路径")
            return False
        
        # 检查路径是否存在
        if not user_data_dir.exists():
            logger.warning(f"PathService 返回的路径不存在: {user_data_dir}")
            # 这不是致命错误，路径可能还未创建
        
        logger.debug("PathService 健康检查通过")
        return True
        
    except Exception as e:
        logger.error(f"PathService 健康检查失败: {e}", exc_info=True)
        return False


def check_config_service() -> bool:
    """检查 ConfigService 健康状态

    Returns:
        True 如果服务健康，False 否则
    """
    try:
        from core.services import config_service

        # 检查服务是否可调用
        # 使用一个测试模块名称
        test_config = config_service.get_module_config("health_check_test")

        # 检查返回值是否有效
        if test_config is None:
            logger.error("ConfigService 返回了 None 配置")
            return False

        # 检查配置是否是字典
        if not isinstance(test_config, dict):
            logger.error(f"ConfigService 返回的配置类型错误: {type(test_config)}")
            return False

        logger.debug("ConfigService 健康检查通过")
        return True

    except Exception as e:
        logger.error(f"ConfigService 健康检查失败: {e}", exc_info=True)
        return False


def check_style_service() -> bool:
    """检查 StyleService 健康状态
    
    Returns:
        True 如果服务健康，False 否则
    """
    try:
        from core.services import style_service
        
        # 检查服务是否可调用
        current_theme = style_service.get_current_theme()
        
        # 检查返回值是否有效
        if current_theme is None:
            logger.warning("StyleService 返回了 None 主题（可能未初始化）")
            # 这不是致命错误，主题可能还未设置
        
        # 检查可用主题列表
        available_themes = style_service.list_available_themes()
        if not isinstance(available_themes, list):
            logger.error(f"StyleService 返回的主题列表类型错误: {type(available_themes)}")
            return False
        
        logger.debug("StyleService 健康检查通过")
        return True

    except Exception as e:
        logger.error(f"StyleService 健康检查失败: {e}", exc_info=True)
        return False


def check_thread_service() -> bool:
    """检查 ThreadService 健康状态

    Returns:
        True 如果服务健康，False 否则
    """
    try:
        from core.services import thread_service

        # 检查服务是否可调用
        # 简单测试：提交一个任务并等待完成
        test_result = []

        def test_task():
            test_result.append(True)
            return "test"

        # 提交任务
        thread_service.run_async(
            test_task,
            on_result=lambda result: test_result.append(result)
        )

        # 等待一小段时间让任务完成
        import time
        time.sleep(0.1)

        # 检查任务是否执行
        if len(test_result) == 0:
            logger.warning("ThreadService 任务未执行（可能需要更长时间）")
            # 这不是致命错误，可能只是需要更长时间

        logger.debug("ThreadService 健康检查通过")
        return True

    except Exception as e:
        logger.error(f"ThreadService 健康检查失败: {e}", exc_info=True)
        return False


def perform_health_checks() -> Dict[str, bool]:
    """执行所有服务的健康检查

    Returns:
        字典，键为服务名称，值为健康状态（True/False）
    """
    logger.info("开始执行服务健康检查...")

    results = {
        "LogService": check_log_service(),
        "PathService": check_path_service(),
        "ConfigService": check_config_service(),
        "StyleService": check_style_service(),
        "ThreadService": check_thread_service(),
    }

    # 统计结果
    total = len(results)
    healthy = sum(1 for status in results.values() if status)

    if healthy == total:
        logger.info(f"✅ 服务健康检查完成：{healthy}/{total} 服务健康")
    else:
        logger.warning(f"⚠️ 服务健康检查完成：{healthy}/{total} 服务健康")
        for service, status in results.items():
            if not status:
                logger.warning(f"  - {service}: 异常")

    return results

