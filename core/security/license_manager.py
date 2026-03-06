# -*- coding: utf-8 -*-

"""
授权管理器模块 - Freemium 模式
只支持永久卡和天卡，移除试用系统。

提供接口：
- get_license_status(): 获取当前授权状态（用于模块访问控制）
- LicenseManager.activate(): 激活授权（供激活引导对话框调用）
"""

import json
import logging
import os
import time
import urllib.error
import urllib.request
from typing import Optional, Literal

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
        if _DEV_MODE:
            return "permanent"

        try:
            data = self.crypto.load()
            if not data:
                return "none"

            # 硬件指纹容差匹配
            if data.get("feature_hashes"):
                matched, _ = self.machine.match_features(data["feature_hashes"])
                if not matched:
                    return "none"

            license_type = data.get("license_type")
            
            if license_type == "permanent":
                return "permanent"
            
            if license_type == "daily":
                expire_time = data.get("expire_time")
                if expire_time and time.time() <= expire_time:
                    return "daily"
                return "expired"
            
            # 旧的试用数据视为无授权
            if license_type == "trial":
                return "none"
            
            return "none"

        except Exception as exc:
            logger.warning(f"获取授权状态失败: {exc}")
            return "none"

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
    try:
        lm = LicenseManager()
        return lm.get_license_status()
    except Exception as exc:
        logger.warning(f"get_license_status error: {exc}")
        return "none"
