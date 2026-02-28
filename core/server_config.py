# -*- coding: utf-8 -*-

"""
服务器地址配置模块
优先使用域名，域名不可用时自动降级到 IP 地址。
结果在进程生命周期内缓存，并持久化到磁盘避免重复探测。
"""

import json
import logging
import os
import time
import urllib.request
import urllib.error

from typing import Optional

logger = logging.getLogger(__name__)

# 主域名（Cloudflare DNS → Vercel）
_DOMAIN_URL = "https://www.unrealenginetookit.top"
# Vercel 备用域名（国内可能被墙，但作为降级仍有意义）
_FALLBACK_URL = "https://ue-toolkit-update-web.vercel.app"

# 缓存：None 表示尚未探测
_cached_base_url: Optional[str] = None

# 磁盘缓存（避免每次启动都探测）
_URL_CACHE_DIR = os.path.join(os.environ.get("APPDATA", ""), "ue_toolkit")
_URL_CACHE_FILE = os.path.join(_URL_CACHE_DIR, ".server_url_cache")
_URL_CACHE_TTL = 3600  # 1小时有效期


def _load_url_cache() -> Optional[str]:
    """从磁盘加载缓存的服务器 URL"""
    try:
        if not os.path.exists(_URL_CACHE_FILE):
            return None
        with open(_URL_CACHE_FILE, "r", encoding="utf-8") as f:
            cache = json.load(f)
        if time.time() - cache.get("ts", 0) > _URL_CACHE_TTL:
            return None
        return cache.get("url")
    except Exception:
        return None


def _save_url_cache(url: str):
    """保存服务器 URL 到磁盘缓存"""
    try:
        os.makedirs(_URL_CACHE_DIR, exist_ok=True)
        with open(_URL_CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump({"ts": time.time(), "url": url}, f)
    except Exception:
        pass


def _probe_url(url: str, timeout: float = 5.0) -> bool:
    """探测 URL 是否可达（HEAD 请求，5秒超时，绕过系统代理）"""
    try:
        handler = urllib.request.ProxyHandler({})
        opener = urllib.request.build_opener(handler)
        req = urllib.request.Request(url, method="HEAD")
        with opener.open(req, timeout=timeout):
            return True
    except Exception:
        return False


def get_server_base_url() -> str:
    """
    获取当前可用的服务器基础 URL（不带尾部斜杠）。
    优先使用磁盘缓存 → 内存缓存 → 探测。
    """
    global _cached_base_url
    if _cached_base_url is not None:
        return _cached_base_url

    # 尝试磁盘缓存
    disk_cached = _load_url_cache()
    if disk_cached:
        _cached_base_url = disk_cached
        logger.info("使用磁盘缓存的服务器地址: %s", disk_cached)
        return _cached_base_url

    # 探测主域名
    if _probe_url(_DOMAIN_URL):
        _cached_base_url = _DOMAIN_URL
        logger.info("使用主域名: %s", _DOMAIN_URL)
    elif _probe_url(_FALLBACK_URL):
        _cached_base_url = _FALLBACK_URL
        logger.info("主域名不可用，使用 Vercel 备用域名: %s", _FALLBACK_URL)
    else:
        # 都不可达时仍默认主域名，后续请求会报错但不会用错地址
        _cached_base_url = _DOMAIN_URL
        logger.warning("所有服务器地址均不可达，默认使用: %s", _DOMAIN_URL)

    _save_url_cache(_cached_base_url)
    return _cached_base_url


def get_api_base_url() -> str:
    """获取 API v2 基础 URL，如 http://xxx/api/v2"""
    return f"{get_server_base_url()}/api/v2"
