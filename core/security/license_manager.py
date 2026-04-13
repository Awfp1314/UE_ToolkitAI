# -*- coding: utf-8 -*-

"""
授权管理器模块 - Freemium 模式
只支持永久卡和天卡，移除试用系统。

提供接口：
- get_license_status(): 获取当前授权状态（用于模块访问控制）
- LicenseManager.activate(): 激活授权（供激活引导对话框调用）
- LicenseStatusCache: 授权状态缓存管理器（优化性能）
"""

import json
import logging
import os
import time
import urllib.error
import urllib.request
from typing import Optional, Literal
from threading import Lock

from .machine_id import MachineID
from .license_crypto import LicenseCrypto

logger = logging.getLogger(__name__)

# Server base URL — auto-detect domain vs IP fallback
from core.server_config import get_server_base_url
_SERVER_BASE_URL = None  # lazy init

def _get_server_url():
    global _SERVER_BASE_URL
    if _SERVER_BASE_URL is None:
        _SERVER_BASE_URL = os.environ.get("UE_LICENSE_SERVER_URL") or get_server_base_url()
    return _SERVER_BASE_URL

# 开发模式：服务器未就绪时设为 True，跳过所有联网验证
# ⚠️ 发布前务必改为 False
_DEV_MODE = False

# Timeout constants (seconds)
_FULL_CHECK_TIMEOUT = 8

# 授权状态类型
LicenseStatus = Literal["none", "permanent", "daily", "expired"]


class LicenseStatusCache:
    """
    授权状态缓存管理器
    
    优化性能：
    - 启动时异步预加载授权状态
    - 内存缓存5分钟，避免重复检查
    - 硬件指纹只采集一次
    - 购买链接也缓存，避免重复请求
    """
    
    def __init__(self):
        self._status: Optional[LicenseStatus] = None
        self._last_check_time: float = 0
        self._cache_duration: int = 300  # 5分钟
        self._loading: bool = False
        self._lock = Lock()
        
        # 硬件指纹缓存（整个程序生命周期）
        self._machine_id: Optional[str] = None
        self._feature_hashes: Optional[dict] = None
        self._machine: Optional[MachineID] = None
        
        # 购买链接缓存（1小时有效期）
        self._purchase_link: Optional[str] = None
        self._purchase_link_time: float = 0
        self._purchase_link_duration: int = 3600  # 1小时
        
        # 预加载线程引用
        self._preload_thread = None
    
    def _is_cache_valid(self) -> bool:
        """检查缓存是否有效"""
        if self._status is None:
            return False
        
        # 永久授权：缓存永久有效
        if self._status == "permanent":
            return True
        
        # 其他状态：检查时间
        elapsed = time.time() - self._last_check_time
        return elapsed < self._cache_duration
    
    def _get_machine_info(self):
        """获取硬件信息（只采集一次）"""
        if self._machine_id is None:
            self._machine = MachineID()
            self._machine_id = self._machine.get_machine_id()
            self._feature_hashes = self._machine.get_feature_hashes()
        return self._machine_id, self._feature_hashes, self._machine
    
    def get_status_sync(self) -> LicenseStatus:
        """
        同步获取授权状态（优先返回缓存）
        
        Returns:
            授权状态
        """
        with self._lock:
            # 缓存有效，直接返回
            if self._is_cache_valid():
                return self._status
            
            # 正在加载中，返回上次结果或默认值
            if self._loading:
                return self._status or "none"
            
            # 缓存无效，同步刷新
            return self._refresh_sync()
    
    def _refresh_sync(self) -> LicenseStatus:
        """同步刷新授权状态（内部方法，已加锁）"""
        self._loading = True
        try:
            if _DEV_MODE:
                self._status = "permanent"
                self._last_check_time = time.time()
                return self._status
            
            # 获取硬件信息
            machine_id, feature_hashes, machine = self._get_machine_info()
            
            # 创建加密器
            crypto = LicenseCrypto(machine_id)
            
            # 加载本地授权数据
            data = crypto.load()
            if not data:
                self._status = "none"
                self._last_check_time = time.time()
                return self._status
            
            # 硬件指纹容差匹配
            if data.get("feature_hashes"):
                matched, _ = machine.match_features(data["feature_hashes"])
                if not matched:
                    self._status = "none"
                    self._last_check_time = time.time()
                    return self._status
            
            # 判断授权类型
            license_type = data.get("license_type")
            
            if license_type == "permanent":
                self._status = "permanent"
            elif license_type == "daily":
                expire_time = data.get("expire_time")
                if expire_time and time.time() <= expire_time:
                    self._status = "daily"
                else:
                    self._status = "expired"
            elif license_type == "trial":
                # 旧的试用数据视为无授权
                self._status = "none"
            else:
                self._status = "none"
            
            self._last_check_time = time.time()
            return self._status
            
        except Exception as exc:
            logger.warning(f"刷新授权状态失败: {exc}")
            self._status = "none"
            self._last_check_time = time.time()
            return self._status
        finally:
            self._loading = False
    
    def get_purchase_link_cached(self) -> str:
        """
        获取购买链接（缓存版本）
        
        Returns:
            购买链接，失败时返回空字符串
        """
        with self._lock:
            # 检查缓存是否有效
            if (self._purchase_link is not None and 
                time.time() - self._purchase_link_time < self._purchase_link_duration):
                return self._purchase_link
            
            # 缓存无效，重新获取
            try:
                import requests
                from core.server_config import get_server_base_url
                
                # 创建无代理的 session
                session = requests.Session()
                session.trust_env = False  # 忽略系统代理
                
                url = f"{get_server_base_url()}/api/site-config/public"
                resp = session.get(url, timeout=3)
                if resp.status_code == 200:
                    data = resp.json()
                    configs = data.get('configs', data.get('data', {}))
                    purchase_link = configs.get('purchase_link', '')
                    
                    # 更新缓存
                    self._purchase_link = purchase_link
                    self._purchase_link_time = time.time()
                    
                    return purchase_link
            except Exception as e:
                logger.warning(f"获取购买链接失败: {e}")
            
            # 失败时返回空字符串，但不缓存失败结果
            return ""
    
    def force_refresh(self) -> LicenseStatus:
        """
        强制刷新授权状态（激活成功后调用）
        
        Returns:
            最新的授权状态
        """
        with self._lock:
            self._last_check_time = 0  # 使缓存失效
            return self._refresh_sync()
    
    def start_background_refresh(self):
        """启动后台异步刷新（程序启动时调用）"""
        from PyQt6.QtCore import QThread, pyqtSignal
        
        class RefreshThread(QThread):
            finished = pyqtSignal(str, str)  # status, purchase_link
            
            def __init__(self, cache, parent=None):
                super().__init__(parent)
                self.cache = cache
                self.setObjectName("LicensePreloadThread")
            
            def run(self):
                try:
                    # 同时预加载授权状态和购买链接
                    status = self.cache._refresh_sync()
                    purchase_link = self.cache.get_purchase_link_cached()
                    self.finished.emit(status, purchase_link)
                except Exception as e:
                    logger.error(f"后台预加载失败: {e}")
                    self.finished.emit("none", "")
        
        # 创建线程并保存引用，避免被垃圾回收
        self._preload_thread = RefreshThread(self)
        self._preload_thread.finished.connect(
            lambda status, link: logger.info(f"后台预加载完成: 授权={status}, 购买链接={'已获取' if link else '获取失败'}")
        )
        self._preload_thread.finished.connect(self._preload_thread.deleteLater)  # 完成后自动清理
        self._preload_thread.start()
    
    def cleanup(self):
        """清理资源（程序退出时调用）"""
        if hasattr(self, '_preload_thread') and self._preload_thread:
            try:
                if self._preload_thread.isRunning():
                    self._preload_thread.quit()
                    self._preload_thread.wait(1000)  # 等待最多1秒
                # 清理线程引用
                self._preload_thread = None
            except RuntimeError as e:
                # 对象已被删除，忽略错误
                logger.debug(f"线程对象已被删除: {e}")
            except Exception as e:
                logger.warning(f"清理预加载线程时出错: {e}")


# 全局缓存实例
_license_cache = LicenseStatusCache()


class LicenseManager:
    """授权管理器 — Freemium 模式"""

    def __init__(self):
        self.machine = MachineID()
        self.machine_id = self.machine.get_machine_id()
        self.crypto = LicenseCrypto(self.machine_id)
        self._feature_hashes = self.machine.get_feature_hashes()

        # 如果本地有 stored_machine_id，优先使用（容差匹配场景）
        try:
            data = self.crypto.load()
            if data and data.get("stored_machine_id"):
                self.machine_id = data["stored_machine_id"]
        except Exception:
            pass

    # ------------------------------------------------------------------
    # 公共接口
    # ------------------------------------------------------------------

    def get_license_status(self) -> LicenseStatus:
        """
        获取当前授权状态（用于模块访问控制）
        
        Returns:
            "none": 无授权
            "permanent": 永久授权
            "daily": 天卡（未过期）
            "expired": 已过期
        """
        # 使用全局缓存
        return _license_cache.get_status_sync()

    def activate(self, activation_key: str) -> bool:
        """
        激活授权（供激活引导对话框调用）
        
        Args:
            activation_key: 激活码
            
        Returns:
            True: 激活成功
            False: 激活失败
        """
        resp = self._call_api(
            "/api/v2/license/activate",
            {
                "machine_id": self.machine_id,
                "activation_key": activation_key,
            },
        )

        if resp is None:
            logger.warning("Activation failed: no server response")
            return False

        if resp.get("error"):
            logger.warning("Activation error: %s", resp.get("message", ""))
            return False

        license_token = resp.get("license_token")
        if not license_token:
            logger.warning("Activation response missing license_token")
            return False

        # 服务端返回的 license_type 和 expire_time
        license_type = resp.get("license_type", "permanent")
        expire_time = resp.get("expire_time")  # float timestamp or None

        data = {
            "license_type": license_type,
            "stored_machine_id": self.machine_id,
            "license_token": license_token,
            "activation_key": activation_key,
            "feature_hashes": self._feature_hashes,
            "last_seen_time": time.time(),
            "expire_time": expire_time,
        }
        self.crypto.save(data)
        logger.info("License activated: type=%s, expire=%s", license_type, expire_time)
        
        # 激活成功后立即刷新缓存
        _license_cache.force_refresh()
        
        return True

    # ------------------------------------------------------------------
    # 内部辅助方法
    # ------------------------------------------------------------------

    def _call_api(
        self, endpoint: str, payload: dict, timeout: int = _FULL_CHECK_TIMEOUT
    ) -> Optional[dict]:
        """
        Call a server API endpoint using urllib.request.
        显式绕过系统代理，避免用户开代理时请求失败。

        Args:
            endpoint: API path, e.g. "/api/v2/license/activate"
            payload: JSON-serializable dict for the request body
            timeout: Request timeout in seconds

        Returns:
            Parsed JSON response dict, or None on any failure.
        """
        url = f"{_get_server_url()}{endpoint}"
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            # 绕过系统代理，避免代理导致 SSL 握手超时或连接失败
            handler = urllib.request.ProxyHandler({})
            opener = urllib.request.build_opener(handler)
            with opener.open(req, timeout=timeout) as resp:
                body = resp.read().decode("utf-8")
                return json.loads(body)
        except urllib.error.HTTPError as exc:
            # Try to parse error body for structured error responses
            try:
                err_body = exc.read().decode("utf-8")
                return json.loads(err_body)
            except Exception:
                logger.warning("API HTTP error %s for %s", exc.code, endpoint)
                return {"_network_error": True, "_http_code": exc.code}
        except (urllib.error.URLError, OSError, ValueError) as exc:
            logger.warning("API request failed for %s: %s", endpoint, exc)
            return None
        except Exception as exc:
            logger.warning("Unexpected API error for %s: %s", endpoint, exc)
            return None

    def _get_purchase_link(self) -> str:
        """从服务端获取购买链接，失败时返回空字符串"""
        try:
            import requests
            from core.server_config import get_server_base_url
            
            # 创建无代理的 session
            session = requests.Session()
            session.trust_env = False  # 忽略系统代理
            
            url = f"{get_server_base_url()}/api/site-config/public"
            logger.info(f"正在获取购买链接: {url}")
            resp = session.get(url, timeout=3)
            logger.info(f"响应状态码: {resp.status_code}")
            if resp.status_code == 200:
                data = resp.json()
                logger.info(f"响应数据: {data}")
                configs = data.get('configs', data.get('data', {}))
                purchase_link = configs.get('purchase_link', '')
                logger.info(f"获取到购买链接: {purchase_link}")
                return purchase_link
        except Exception as e:
            logger.error(f"获取购买链接失败: {e}", exc_info=True)
        return ""


# ------------------------------------------------------------------
# 模块级别函数
# ------------------------------------------------------------------

def get_license_status() -> LicenseStatus:
    """
    获取当前授权状态（模块级别便捷函数）
    
    Returns:
        "none": 无授权
        "permanent": 永久授权
        "daily": 天卡（未过期）
        "expired": 已过期
    """
    return _license_cache.get_status_sync()


def start_license_cache_preload():
    """
    启动授权状态预加载（程序启动时调用）
    """
    _license_cache.start_background_refresh()


def get_purchase_link_cached() -> str:
    """
    获取购买链接（缓存版本，模块级别便捷函数）
    
    Returns:
        购买链接，失败时返回空字符串
    """
    return _license_cache.get_purchase_link_cached()


def cleanup_license_cache():
    """
    清理授权缓存资源（程序退出时调用）
    """
    _license_cache.cleanup()


def force_refresh_license_cache() -> LicenseStatus:
    """
    强制刷新授权缓存（激活成功后调用）
    
    Returns:
        最新的授权状态
    """
    return _license_cache.force_refresh()
