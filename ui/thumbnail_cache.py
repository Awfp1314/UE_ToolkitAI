# -*- coding: utf-8 -*-

"""
缩略图缓存模块 - 实现LRU缓存和懒加载

优化方案：
- 固定 4 个工作线程 + 共享队列，替代旧的"每张图一个 QThread"
- 快速滚动时不再产生大量线程
- LRU 缓存默认 300（旧值 100 太小，频繁驱逐导致重复加载）
"""

import queue
import threading
from collections import OrderedDict
from pathlib import Path
from typing import Optional

from PyQt6.QtGui import QPixmap, QImage, QPainter, QColor
from PyQt6.QtCore import QObject, pyqtSignal, QThread, Qt

from core.logger import get_logger

logger = get_logger(__name__)

# 工作线程数量
_WORKER_COUNT = 4


class _ThumbnailWorker(QThread):
    """缩略图加载工作线程 — 从共享队列中持续取任务"""

    thumbnail_loaded = pyqtSignal(str, QPixmap)  # asset_id, pixmap

    def __init__(self, task_queue: queue.Queue):
        super().__init__()
        self._queue = task_queue
        self._stop_flag = False

    def stop(self):
        self._stop_flag = True

    def run(self):
        while not self._stop_flag:
            try:
                item = self._queue.get(timeout=0.5)
            except queue.Empty:
                continue
            if item is None:  # 哨兵值，退出
                break
            asset_id, thumbnail_path = item
            try:
                if thumbnail_path and thumbnail_path.exists():
                    pixmap = QPixmap(str(thumbnail_path))
                    if not pixmap.isNull():
                        self.thumbnail_loaded.emit(asset_id, pixmap)
            except Exception as e:
                logger.error(f"异步加载缩略图失败 {asset_id}: {e}")
            finally:
                self._queue.task_done()


class ThumbnailCache(QObject):
    """线程安全的LRU缩略图缓存

    特性:
    - LRU (Least Recently Used) 缓存策略
    - 固定线程池异步加载（4 个工作线程 + 共享队列）
    - 线程安全
    - 占位符支持
    - 缓存大小监控

    Signals:
        thumbnail_loaded: 缩略图加载完成信号 (str: asset_id, QPixmap: pixmap)
        cache_stats_updated: 缓存统计更新信号 (int: size, int: hits, int: misses)
    """

    thumbnail_loaded = pyqtSignal(str, QPixmap)  # asset_id, pixmap
    cache_stats_updated = pyqtSignal(int, int, int)  # size, hits, misses

    def __init__(self, max_size: int = 300):
        """初始化缩略图缓存

        Args:
            max_size: 最大缓存数量（默认300）
        """
        super().__init__()
        self._cache = OrderedDict()
        self._max_size = max_size
        self._lock = threading.Lock()
        self._placeholder = self._create_placeholder()

        # 统计信息
        self._cache_hits = 0
        self._cache_misses = 0

        # 已提交加载的 asset_id 集合（防止重复提交）
        self._pending_ids: set = set()
        self._pending_lock = threading.Lock()

        # 共享任务队列 + 工作线程池
        self._task_queue: queue.Queue = queue.Queue()
        self._workers: list[_ThumbnailWorker] = []
        self._start_workers()

        logger.info(f"缩略图缓存初始化完成，最大容量: {max_size}，工作线程: {_WORKER_COUNT}")

    # ── 工作线程管理 ──

    def _start_workers(self):
        """启动固定数量的工作线程"""
        for i in range(_WORKER_COUNT):
            w = _ThumbnailWorker(self._task_queue)
            w.thumbnail_loaded.connect(self._on_thumbnail_loaded)
            w.start()
            self._workers.append(w)

    # ── 占位符 ──

    def _create_placeholder(self) -> QPixmap:
        """创建占位符缩略图"""
        width, height = 212, 153
        pixmap = QPixmap(width, height)
        pixmap.fill(QColor(50, 50, 50))

        painter = QPainter(pixmap)
        painter.setPen(QColor(120, 120, 120))
        icon_size = 40
        x = (width - icon_size) // 2
        y = (height - icon_size) // 2
        painter.drawRect(x, y, icon_size, icon_size)
        painter.drawLine(x, y, x + icon_size, y + icon_size)
        painter.drawLine(x + icon_size, y, x, y + icon_size)
        painter.end()
        return pixmap

    # ── 容器协议 ──

    def __contains__(self, asset_id: str) -> bool:
        with self._lock:
            return asset_id in self._cache

    def __delitem__(self, asset_id: str) -> None:
        with self._lock:
            if asset_id in self._cache:
                del self._cache[asset_id]

    def __setitem__(self, asset_id: str, pixmap: QPixmap) -> None:
        self._add_to_cache(asset_id, pixmap)

    # ── 核心 API ──

    def get(self, asset_id: str, thumbnail_path: Optional[Path] = None) -> QPixmap:
        """获取缩略图（缓存未命中时返回占位符并触发异步加载）"""
        with self._lock:
            if asset_id in self._cache:
                self._cache.move_to_end(asset_id)
                self._cache_hits += 1
                self._emit_stats_internal()
                return self._cache[asset_id]

        self._cache_misses += 1

        # 触发异步加载
        if thumbnail_path:
            self._enqueue_load(asset_id, thumbnail_path)

        self._emit_stats()
        return self._placeholder

    def preload(self, asset_id: str, thumbnail_path: Path):
        """预加载缩略图（不返回，仅触发加载）"""
        with self._lock:
            if asset_id in self._cache:
                return
        self._enqueue_load(asset_id, thumbnail_path)

    def _enqueue_load(self, asset_id: str, thumbnail_path: Path):
        """将加载任务放入队列（去重）"""
        with self._pending_lock:
            if asset_id in self._pending_ids:
                return
            self._pending_ids.add(asset_id)
        self._task_queue.put((asset_id, thumbnail_path))

    # ── 回调 ──

    def _on_thumbnail_loaded(self, asset_id: str, pixmap: QPixmap):
        """工作线程加载完成回调"""
        # 从 pending 集合移除
        with self._pending_lock:
            self._pending_ids.discard(asset_id)

        self._add_to_cache(asset_id, pixmap)
        self.thumbnail_loaded.emit(asset_id, pixmap)

    # ── 缓存操作 ──

    def _add_to_cache(self, asset_id: str, pixmap: QPixmap):
        """添加缩略图到缓存（带LRU驱逐）"""
        with self._lock:
            if len(self._cache) >= self._max_size:
                self._cache.popitem(last=False)
            self._cache[asset_id] = pixmap
            self._emit_stats_internal()

    def clear(self):
        """清空缓存"""
        with self._lock:
            self._cache.clear()
            self._cache_hits = 0
            self._cache_misses = 0
            logger.info("缓存已清空")
            self._emit_stats_internal()
        with self._pending_lock:
            self._pending_ids.clear()

    # ── 统计 ──

    def get_stats(self) -> dict:
        with self._lock:
            total = self._cache_hits + self._cache_misses
            return {
                'size': len(self._cache),
                'max_size': self._max_size,
                'hits': self._cache_hits,
                'misses': self._cache_misses,
                'hit_rate': (self._cache_hits / total * 100) if total > 0 else 0,
                'pending': len(self._pending_ids),
            }

    def _emit_stats_internal(self):
        """在锁内发送统计信号"""
        self.cache_stats_updated.emit(
            len(self._cache), self._cache_hits, self._cache_misses
        )

    def _emit_stats(self):
        """在锁外发送统计信号"""
        with self._lock:
            size, hits, misses = len(self._cache), self._cache_hits, self._cache_misses
        self.cache_stats_updated.emit(size, hits, misses)

    # ── 清理 ──

    def cleanup(self):
        """清理资源（停止所有工作线程）"""
        # 发送哨兵值让每个工作线程退出
        for _ in self._workers:
            self._task_queue.put(None)

        for w in self._workers:
            try:
                w.stop()
                w.quit()
                # 给 1 秒等待，不阻塞太久
                w.wait(1000)
                w.deleteLater()
            except Exception as e:
                logger.warning(f"清理工作线程失败: {e}")

        self._workers.clear()
        logger.info("缩略图缓存清理完成")
