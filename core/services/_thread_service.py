"""ThreadService - 统一的线程调度服务

提供简化的异步任务执行接口，封装 EnhancedThreadManager

v5.2.1: 已迁移到 EnhancedThreadManager
"""

from typing import Callable, Optional, Tuple, Dict, Union, Any
import logging
from PyQt6.QtCore import QThread
from core.utils.thread_models import Worker, CancellationToken
from core.utils.thread_manager import EnhancedThreadManager
from core.config.thread_config import ThreadConfiguration

logger = logging.getLogger("ue_toolkit.services.thread_service")


class ThreadService:
    """统一的线程调度服务
    
    封装 ThreadManager，提供简化的异步任务执行接口
    
    特性：
    - 自动检测任务函数签名，支持 cancel_token 参数注入
    - 提供协作式取消机制
    - 线程使用统计
    - 资源清理
    """
    
    def __init__(self):
        """初始化线程服务
        
        v5.2.1: 使用 EnhancedThreadManager
        """
        config = ThreadConfiguration()
        self._thread_manager = EnhancedThreadManager(config)
    
    def run_async(
        self,
        task_func: Callable,
        on_result: Optional[Callable[[Any], None]] = None,
        on_error: Optional[Callable[[str], None]] = None,
        on_finished: Optional[Callable[[], None]] = None,
        on_progress: Optional[Callable[[int], None]] = None,
        *args,
        **kwargs
    ) -> Tuple[Optional[Worker], CancellationToken, str]:
        """异步执行任务
        
        Args:
            task_func: 任务函数，可选接受 cancel_token 参数
            on_result: 结果回调函数
            on_error: 错误回调函数
            on_finished: 完成回调函数 (v5.2.1: 暂不支持，使用 on_result/on_error 代替)
            on_progress: 进度回调函数 (v5.3.1: 已支持)
            *args: 任务函数的位置参数
            **kwargs: 任务函数的关键字参数
        
        Returns:
            Tuple[Optional[Worker], CancellationToken, str]: Worker 对象（可能为None如果排队）、取消令牌、任务ID
        
        Example:
            def my_task(cancel_token, n):
                for i in range(n):
                    if cancel_token.is_cancelled():
                        return None
                    time.sleep(1)
                return "完成"
            
            worker, token, task_id = thread_service.run_async(
                my_task,
                on_result=lambda result: print(result),
                n=10
            )
            
            # 取消任务
            thread_service.cancel_task(token)
        
        Note:
            v5.2.1: 使用 EnhancedThreadManager，支持队列和并发控制。
            Worker 可能为 None（任务排队中）。
            取消令牌始终可用（v5.2.1 改进）。
        """
        # v5.2.1: EnhancedThreadManager 需要 module_name 和 task_name
        module_name = "ThreadService"
        task_name = task_func.__name__ if hasattr(task_func, '__name__') else "anonymous_task"
        
        # v5.3.1: on_progress 现已支持
        if on_finished:
            logger.warning("on_finished 回调在 v5.2.1 中暂不支持")
        
        thread, worker, task_id = self._thread_manager.run_in_thread(
            task_func,
            module_name=module_name,
            task_name=task_name,
            on_result=on_result,
            on_error=on_error,
            on_progress=on_progress,
            *args,
            **kwargs
        )
        
        # v5.2.1: 始终有 cancel_token（即使任务排队）
        if worker:
            cancel_token = worker.cancel_token
        else:
            # 任务排队中，获取 cancel_token
            cancel_token = self._thread_manager.get_cancel_token(task_id)
        
        return worker, cancel_token, task_id
    
    def cancel_task(self, task_identifier: Union[Worker, CancellationToken]) -> None:
        """取消任务（协作式取消）
        
        Args:
            task_identifier: Worker 对象或 CancellationToken 对象
        
        Note:
            这是协作式取消，任务函数需要主动检查 cancel_token.is_cancelled()
            如果任务函数不检查取消标志，任务仍会继续执行。
            对同一任务多次调用 cancel_task() 是幂等的，不会产生错误。
        """
        if isinstance(task_identifier, Worker):
            task_identifier.cancel()
        elif isinstance(task_identifier, CancellationToken):
            task_identifier.cancel()
        else:
            raise TypeError(
                f"task_identifier 必须是 Worker 或 CancellationToken 类型，"
                f"实际类型: {type(task_identifier)}"
            )
    
    def get_thread_usage(self) -> Dict[str, int]:
        """获取线程使用统计信息
        
        Returns:
            Dict[str, int]: 包含以下键的字典
                - 'active': 当前活跃线程数
                - 'max': 最大线程数
        
        v5.2.1: 使用 EnhancedThreadManager 的监控数据
        """
        active_count = len(self._thread_manager.get_active_threads())
        max_count = self._thread_manager.config.thread_pool_size
        return {
            'active': active_count,
            'max': max_count
        }
    
    def cleanup(self, timeout_ms: Optional[int] = 5000) -> None:
        """清理所有线程资源
        
        Args:
            timeout_ms: 清理超时时间（毫秒），默认5秒
        
        取消所有活跃任务，并等待它们完成
        如果任务在超时时间内未完成，会记录警告但不会阻塞
        
        v5.2.1: 使用 EnhancedThreadManager 的 cleanup 方法
        """
        logger.info("开始清理线程资源...")
        
        # 获取所有活跃线程
        usage = self.get_thread_usage()
        active_count = usage.get('active', 0)
        
        if active_count > 0:
            logger.info("发现 %s 个活跃线程，正在取消...", active_count)
            
            # 记录活跃任务详情
            active_threads = self._thread_manager.get_active_threads()
            if active_threads:
                logger.info("活跃任务详情:")
                for idx, thread_info in enumerate(active_threads, 1):
                    logger.info(
                        "  [%d/%d] %s.%s | 运行时长: %dms | 开始于: %s | [ID: %s]",
                        idx, len(active_threads),
                        thread_info.module_name,
                        thread_info.task_name,
                        thread_info.elapsed_ms,
                        thread_info.started_at,
                        thread_info.task_id
                    )
        
        # v5.2.1: 调用 EnhancedThreadManager 的清理方法
        success = self._thread_manager.cleanup(timeout_ms=timeout_ms)
        
        if success:
            logger.info("线程资源清理完成")
        else:
            logger.warning("线程资源清理超时（部分任务未完成）")
