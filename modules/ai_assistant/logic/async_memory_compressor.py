# -*- coding: utf-8 -*-

"""
异步记忆压缩器

在后台线程执行记忆压缩，避免阻塞主线程
✨ 使用 ThreadManager 进行线程管理

⚡ Requirement 9.1, 9.2, 9.3: 添加超时机制
"""

from typing import List, Dict, Optional
from PyQt6.QtCore import QObject, pyqtSignal, QTimer
from core.utils.thread_models import CancellationToken
import logging


def _get_logger():
    """获取日志记录器"""
    return logging.getLogger("ue_toolkit.modules.ai_assistant.logic.async_memory_compressor")


class AsyncMemoryCompressor(QObject):
    """
    异步记忆压缩器

    职责：
    1. 在后台线程执行记忆压缩
    2. 避免阻塞主线程
    3. 通过信号返回压缩结果
    4. ⚡ 支持超时机制（默认30秒）
    ✨ 使用 ThreadManager 进行线程管理
    """

    # 信号定义
    compression_complete = pyqtSignal(bool)  # 压缩完成：是否成功
    compression_timeout = pyqtSignal()  # 压缩超时

    def __init__(self, memory_manager, conversation_history: List[Dict], timeout_seconds: int = 30):
        """
        初始化异步压缩器

        Args:
            memory_manager: EnhancedMemoryManager 实例
            conversation_history: 对话历史列表
            timeout_seconds: 超时时间（秒），默认30秒
        """
        super().__init__()
        self.logger = _get_logger()
        self.memory_manager = memory_manager
        self.conversation_history = conversation_history.copy()
        self.timeout_seconds = timeout_seconds
        self._is_timeout = False
        self._is_completed = False
        self._task_id: Optional[str] = None
        self._timeout_timer: Optional[QTimer] = None
    
    def _execute_compression(self, cancel_token: CancellationToken):
        """
        在后台线程执行压缩

        Args:
            cancel_token: 取消令牌

        ⚡ Requirement 9.1, 9.2: 添加超时机制
        此方法在独立线程中运行，不会阻塞主线程
        """
        try:
            self.logger.info(f"[异步压缩] 开始压缩（超时: {self.timeout_seconds}秒）...")

            # 启动超时定时器（在主线程中）
            from PyQt6.QtCore import QMetaObject, Qt
            QMetaObject.invokeMethod(
                self,
                "_start_timeout_timer",
                Qt.ConnectionType.QueuedConnection
            )

            # 检查是否被取消
            if cancel_token.is_cancelled():
                self.logger.warning("[异步压缩] 压缩被取消（启动前）")
                return

            # 执行压缩
            success = self.memory_manager.compress_old_context(self.conversation_history)

            # 标记完成
            self._is_completed = True

            # 检查是否超时或被取消
            if self._is_timeout:
                self.logger.warning("⏱️ [异步压缩] 压缩已超时，忽略结果")
                return

            if cancel_token.is_cancelled():
                self.logger.warning("[异步压缩] 压缩被取消（完成后）")
                return

            if success:
                self.logger.info("✅ [异步压缩] 压缩成功")
            else:
                self.logger.info("ℹ️ [异步压缩] 压缩未执行或失败")

            # ⚡ Requirement 9.4: 发送完成信号
            self.compression_complete.emit(success)

        except Exception as e:
            self._is_completed = True

            # 检查是否超时或被取消
            if self._is_timeout:
                self.logger.warning("⏱️ [异步压缩] 压缩已超时，忽略错误")
                return

            if cancel_token.is_cancelled():
                self.logger.warning("[异步压缩] 压缩被取消（错误时）")
                return

            self.logger.error(f"❌ [异步压缩] 压缩失败: {e}", exc_info=True)
            # ⚡ Requirement 9.4: 压缩失败时发送失败信号
            self.compression_complete.emit(False)

    def _start_timeout_timer(self):
        """启动超时定时器（在主线程中调用）

        ⚡ Requirement 9.2: 使用 QTimer 实现超时
        """
        timer = QTimer()
        timer.setSingleShot(True)
        timer.timeout.connect(self._on_timeout)
        timer.start(self.timeout_seconds * 1000)
        self._timeout_timer = timer

    def _on_timeout(self):
        """超时处理

        ⚡ Requirement 9.3: 超时时发送失败信号
        """
        if not self._is_completed:
            self._is_timeout = True
            self.logger.warning(f"⏱️ [异步压缩] 压缩超时（{self.timeout_seconds}秒），取消操作")

            # 发送超时信号
            self.compression_timeout.emit()

            # ⚡ Requirement 9.4: 超时时发送失败信号
            self.compression_complete.emit(False)

            # 取消任务
            if self._task_id:
                from core.utils.thread_manager import get_thread_manager
                thread_manager = get_thread_manager()
                thread_manager.cancel_task(self._task_id)
                self.logger.warning("⚠️ [异步压缩] 已取消超时任务")

    def start(self):
        """启动异步压缩（使用 ThreadManager）"""
        from core.utils.thread_manager import get_thread_manager
        thread_manager = get_thread_manager()

        try:
            _, _, task_id = thread_manager.run_in_thread(
                func=self._execute_compression,
                module_name="ai_assistant",
                task_name="memory_compression"
            )
            self._task_id = task_id
            self.logger.info(f"[异步压缩] 任务已提交，task_id: {task_id}")
        except Exception as e:
            self.logger.error(f"[异步压缩] 提交任务失败: {e}")
            self.compression_complete.emit(False)
