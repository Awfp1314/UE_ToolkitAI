"""ThreadService - 统一的线程调度服务

提供简化的异步任务执行接口，封装 ThreadManager
"""

from typing import Callable, Optional, Tuple, Dict, Union, Any
from PyQt5.QtCore import QThread
from core.utils.thread_utils import ThreadManager, Worker, CancellationToken


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
        """初始化线程服务"""
        self._thread_manager = ThreadManager()
        print("[ThreadService] 初始化完成")
    
    def run_async(
        self,
        task_func: Callable,
        on_result: Optional[Callable[[Any], None]] = None,
        on_error: Optional[Callable[[str], None]] = None,
        on_finished: Optional[Callable[[], None]] = None,
        on_progress: Optional[Callable[[int], None]] = None,
        *args,
        **kwargs
    ) -> Tuple[Worker, CancellationToken]:
        """异步执行任务
        
        Args:
            task_func: 任务函数，可选接受 cancel_token 参数
            on_result: 结果回调函数
            on_error: 错误回调函数
            on_finished: 完成回调函数
            on_progress: 进度回调函数
            *args: 任务函数的位置参数
            **kwargs: 任务函数的关键字参数
        
        Returns:
            Tuple[Worker, CancellationToken]: Worker 对象和取消令牌
        
        Example:
            def my_task(cancel_token, n):
                for i in range(n):
                    if cancel_token.is_cancelled():
                        return None
                    time.sleep(1)
                return "完成"
            
            worker, token = thread_service.run_async(
                my_task,
                on_result=lambda result: print(result),
                n=10
            )
            
            # 取消任务
            thread_service.cancel_task(token)
        
        Note:
            ThreadManager 会自动检测任务函数签名，如果函数有 cancel_token 参数，
            则自动注入 CancellationToken 实例。Worker 对象内部持有 cancel_token 属性。
        """
        thread, worker = self._thread_manager.run_in_thread(
            task_func,
            on_result=on_result,
            on_error=on_error,
            on_finished=on_finished,
            on_progress=on_progress,
            *args,
            **kwargs
        )
        # Worker 对象内部已经有 cancel_token 属性（由 ThreadManager 创建）
        return worker, worker.cancel_token
    
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
        """
        return self._thread_manager.get_thread_usage()
    
    def cleanup(self) -> None:
        """清理所有线程资源
        
        取消所有活跃任务，并等待它们完成（最多等待 5 秒）
        如果任务在 5 秒内未完成，会记录警告但不会阻塞
        """
        print("[ThreadService] 开始清理线程资源...")
        
        # 获取所有活跃线程
        usage = self.get_thread_usage()
        active_count = usage.get('active', 0)
        
        if active_count > 0:
            print(f"[ThreadService] 发现 {active_count} 个活跃线程，正在取消...")
            # ThreadManager 会在清理时自动取消所有任务
        
        # 调用 ThreadManager 的清理方法
        self._thread_manager.cleanup()
        
        print("[ThreadService] 线程资源清理完成")

