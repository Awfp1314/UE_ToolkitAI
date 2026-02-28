# -*- coding: utf-8 -*-

"""
授权管理器模块
协调试用注册、验证、激活和离线宽限等流程。

提供两个入口：
- quick_license_check(): 静默预检，供 main.py 调用（无 UI）
- LicenseManager.check_license(): 完整检查，供 AppBootstrap 调用（有 UI）
"""

import json
import logging
import os
import time
import urllib.error
import urllib.request
from typing import Optional

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

# Grace period constants (seconds)
_GRACE_PERIOD_PERMANENT = 48 * 3600  # 48 hours for permanent license
_GRACE_PERIOD_TRIAL = 0  # 0 hours for trial — must verify online every time

# Timeout constants (seconds)
_QUICK_CHECK_TIMEOUT = 3
_FULL_CHECK_TIMEOUT = 8


class LicenseManager:
    """授权管理器 — 协调所有授权流程"""

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
    # Core helpers (Task 3.1)
    # ------------------------------------------------------------------

    def _call_api(
        self, endpoint: str, payload: dict, timeout: int = _FULL_CHECK_TIMEOUT
    ) -> Optional[dict]:
        """
        Call a server API endpoint using urllib.request.
        显式绕过系统代理，避免用户开代理时请求失败。

        Args:
            endpoint: API path, e.g. "/api/v2/trial/start"
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
                # Return a marker dict to distinguish server errors from network unreachable
                return {"_network_error": True, "_http_code": exc.code}
        except (urllib.error.URLError, OSError, ValueError) as exc:
            logger.warning("API request failed for %s: %s", endpoint, exc)
            return None
        except Exception as exc:
            logger.warning("Unexpected API error for %s: %s", endpoint, exc)
            return None

    @staticmethod
    def _check_time_rollback(data: dict) -> bool:
        """
        Detect system time rollback.

        Returns True if current system time is earlier than stored last_seen_time.
        """
        last_seen = data.get("last_seen_time", 0)
        if last_seen and time.time() < last_seen:
            logger.warning(
                "Time rollback detected: system=%.0f, last_seen=%.0f",
                time.time(),
                last_seen,
            )
            return True
        return False

    @staticmethod
    def _is_within_grace_period(data: dict) -> bool:
        """
        Check whether the current time is within the offline grace period.

        Permanent license: 48 hours from last_seen_time.
        Trial license: 0 hours (always returns False).
        """
        license_type = data.get("license_type", "")
        last_seen = data.get("last_seen_time", 0)

        if license_type == "trial":
            return False  # Trial has 0h grace — must be online

        if license_type == "permanent" and last_seen:
            elapsed = time.time() - last_seen
            if elapsed <= _GRACE_PERIOD_PERMANENT:
                logger.info(
                    "Within grace period: %.1f hours remaining",
                    (_GRACE_PERIOD_PERMANENT - elapsed) / 3600,
                )
                return True

        return False

    # ------------------------------------------------------------------
    # Permanent license verification (Task 3.2)
    # ------------------------------------------------------------------

    def _verify_permanent(self, data: dict) -> bool:
        """
        Verify a license (permanent or time-limited) against the server.

        Flow:
        - Local expire_time check for 天卡
        - On time rollback → force online verification
        - On success → update last_seen_time, save, return True
        - On invalid/expired token → revoke local license, return False
        - On network failure → check grace period (permanent only)
        """
        # 天卡本地过期检查
        expire_time = data.get("expire_time")
        if expire_time and time.time() > expire_time:
            logger.info("Time-limited license expired locally (expire_time=%.0f)", expire_time)
            return False

        time_rollback = self._check_time_rollback(data)

        resp = self._call_api(
            "/api/v2/license/verify",
            {
                "machine_id": self.machine_id,
                "license_token": data.get("license_token", ""),
            },
        )

        if resp is not None:
            if resp.get("_network_error"):
                logger.warning(
                    "Server returned unparseable error (HTTP %s) — treating as rejection",
                    resp.get("_http_code"),
                )
                return False

            if resp.get("valid"):
                server_time = resp.get("server_time", time.time())
                data["last_seen_time"] = server_time
                # 同步服务端的 expire_time（天卡可能被服务端更新）
                if resp.get("expire_time"):
                    data["expire_time"] = resp["expire_time"]
                self.crypto.save(data)
                logger.info("License verified online")
                return True
            else:
                if resp.get("expired"):
                    logger.info("Server reports license expired")
                else:
                    logger.warning("Server rejected license token")
                    self._revoke_local_license()
                return False

        # Network failure
        if time_rollback:
            logger.warning("Time rollback + network failure → blocked")
            return False

        # 永久授权 + 服务器不可达：只要本地曾经成功验证过，就信任本地数据放行
        if data.get("last_seen_time") and not expire_time:
            logger.info(
                "Server unreachable, but permanent license was previously verified — allowing offline use"
            )
            return True

        # 天卡 + 服务器不可达：如果本地还没过期，也放行
        if data.get("last_seen_time") and expire_time and time.time() <= expire_time:
            logger.info("Server unreachable, time-limited license still valid locally")
            return True

        logger.warning("Network unavailable, no previous verification record")
        return False

    def _revoke_local_license(self):
        """Mark local license as revoked (prevents re-trial on next launch)."""
        try:
            data = {
                "license_type": "revoked",
                "feature_hashes": self._feature_hashes,
            }
            self.crypto.save(data)
            logger.info("Local license marked as revoked")
        except Exception as exc:
            logger.error("Failed to revoke local license: %s", exc)

    # ------------------------------------------------------------------
    # Trial verification (Task 3.3)
    # ------------------------------------------------------------------

    def _verify_trial(self, data: dict) -> bool:
        """
        Verify an active trial against the server.

        Trial users MUST verify online every startup (0h grace period).
        - On success with remaining_days > 0 → update last_seen_time, return True
        - On expired (remaining_days == 0) → return False (caller shows ActivationDialog)
        - On network failure → block startup (no offline grace for trial)
        """
        resp = self._call_api(
            "/api/v2/trial/verify",
            {
                "machine_id": self.machine_id,
                "trial_token": data.get("trial_token", ""),
            },
        )

        if resp is not None:
            # Check for unparseable server error (not network unreachable)
            if resp.get("_network_error"):
                logger.warning(
                    "Server returned unparseable error (HTTP %s) — treating as rejection",
                    resp.get("_http_code"),
                )
                return False

            if resp.get("valid") and resp.get("remaining_days", 0) > 0:
                server_time = resp.get("server_time", time.time())
                data["last_seen_time"] = server_time
                self.crypto.save(data)
                logger.info(
                    "Trial verified: %d days remaining",
                    resp.get("remaining_days", 0),
                )
                return True
            else:
                # Trial expired
                logger.info("Trial expired (remaining_days=0)")
                return False

        # Network failure — trial has 0h grace, must block
        logger.warning("Network unavailable, trial requires online verification")
        return False

    # ------------------------------------------------------------------
    # First-use and activation (Task 3.4)
    # ------------------------------------------------------------------

    def _get_purchase_link(self) -> str:
        """从服务端获取购买链接，失败时返回空字符串"""
        try:
            import requests
            from core.server_config import get_server_base_url
            url = f"{get_server_base_url()}/api/site-config/public"
            resp = requests.get(url, timeout=3)
            if resp.status_code == 200:
                data = resp.json()
                configs = data.get('configs', data.get('data', {}))
                return configs.get('purchase_link', '')
        except Exception as e:
            logger.debug(f"Failed to fetch purchase_link: {e}")
        return ""

    def _handle_first_use(self) -> bool:
        """
        Handle first-time launch (no existing license data).

        Show trial-expired dialog (which has both trial info and activation input).
        User must explicitly choose to start trial or enter activation key.
        """
        from ui.dialogs.trial_expired_dialog import TrialExpiredDialog

        purchase_link = self._get_purchase_link()

        while True:
            dialog = TrialExpiredDialog(first_use=True, purchase_link=purchase_link)
            dialog.exec()

            if dialog.result_action == TrialExpiredDialog.RESULT_ACTIVATED:
                key = dialog.get_activation_key()
                if key and self._activate(key):
                    return True
                # 激活失败，重试
                from PyQt6.QtWidgets import QMessageBox
                msg = QMessageBox()
                msg.setWindowTitle("激活失败")
                msg.setText("激活码无效或已被使用，请检查后重试。")
                msg.setIcon(QMessageBox.Icon.Warning)
                msg.addButton("重试", QMessageBox.ButtonRole.AcceptRole)
                quit_btn = msg.addButton("退出", QMessageBox.ButtonRole.RejectRole)
                msg.exec()
                if msg.clickedButton() == quit_btn:
                    return False
                continue

            if getattr(dialog, 'result_action', None) == TrialExpiredDialog.RESULT_START_TRIAL:
                # 用户选择开始试用
                def _trial_task():
                    _get_server_url()
                    return self._start_trial()
                if self._run_with_loading(_trial_task):
                    logger.info("User started 7-day trial")
                    return True
                # 试用注册失败（可能已用过或网络问题）
                from PyQt6.QtWidgets import QMessageBox
                msg = QMessageBox()
                msg.setWindowTitle("试用失败")
                msg.setText("无法开始试用（可能已使用过或网络不可用），请输入激活码。")
                msg.setIcon(QMessageBox.Icon.Warning)
                msg.addButton("确定", QMessageBox.ButtonRole.AcceptRole)
                msg.exec()
                continue

            # 用户关闭了对话框
            return False

    def _start_trial(self) -> bool:
        """Register a new trial via POST /api/v2/trial/start."""
        resp = self._call_api(
            "/api/v2/trial/start",
            {"machine_id": self.machine_id},
        )

        if resp is None:
            logger.warning("Failed to start trial: no server response")
            return False

        if resp.get("error"):
            logger.warning("Trial start error: %s", resp.get("message", ""))
            return False

        # Store trial data
        data = {
            "license_type": "trial",
            "stored_machine_id": self.machine_id,
            "trial_token": resp.get("trial_token", ""),
            "license_token": None,
            "feature_hashes": self._feature_hashes,
            "last_seen_time": resp.get("server_time", time.time()),
            "expire_time": resp.get("expire_time"),
        }
        self.crypto.save(data)
        logger.info("Trial started successfully")
        return True

    def _activate(self, activation_key: str) -> bool:
        """
        Activate a license via POST /api/v2/license/activate.
        Supports both permanent and time-limited (天卡) keys.

        Returns True on success, False on failure.
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
            "trial_token": None,
            "license_token": license_token,
            "activation_key": activation_key,
            "feature_hashes": self._feature_hashes,
            "last_seen_time": time.time(),
            "expire_time": expire_time,
        }
        self.crypto.save(data)
        logger.info("License activated: type=%s, expire=%s", license_type, expire_time)
        return True

    def _show_activation_dialog(self, upgrade_mode: bool = False) -> bool:
        """
        Show the ActivationDialog and attempt activation.
        Loops to allow retry on failure. Returns True only on success.

        Args:
            upgrade_mode: 升级模式，引导用户输入永久激活码
        """
        from ui.dialogs.activation_dialog import ActivationDialog

        purchase_link = self._get_purchase_link()

        while True:
            dialog = ActivationDialog(upgrade_mode=upgrade_mode, purchase_link=purchase_link)
            dialog.exec()

            if dialog.result_action != ActivationDialog.RESULT_ACTIVATED:
                return False

            key = dialog.get_activation_key()
            if not key:
                continue

            if self._activate(key):
                return True

            from PyQt6.QtWidgets import QMessageBox
            msg = QMessageBox()
            msg.setWindowTitle("激活失败")
            msg.setText("激活码无效或已被使用，请检查后重试。")
            msg.setIcon(QMessageBox.Icon.Warning)
            retry_btn = msg.addButton("重试", QMessageBox.ButtonRole.AcceptRole)
            quit_btn = msg.addButton("退出", QMessageBox.ButtonRole.RejectRole)
            msg.exec()

            if msg.clickedButton() == quit_btn:
                return False

    def _show_trial_expired_dialog(self) -> bool:
        """
        Show the TrialExpiredDialog (with group info + activation input).
        Loops to allow retry on activation failure. Returns True only on success.
        """
        from ui.dialogs.trial_expired_dialog import TrialExpiredDialog

        purchase_link = self._get_purchase_link()

        while True:
            dialog = TrialExpiredDialog(purchase_link=purchase_link)
            dialog.exec()

            if dialog.result_action != TrialExpiredDialog.RESULT_ACTIVATED:
                return False

            key = dialog.get_activation_key()
            if not key:
                continue

            if self._activate(key):
                return True

            from PyQt6.QtWidgets import QMessageBox
            msg = QMessageBox()
            msg.setWindowTitle("激活失败")
            msg.setText("激活码无效或已被使用，请检查后重试。")
            msg.setIcon(QMessageBox.Icon.Warning)
            retry_btn = msg.addButton("重试", QMessageBox.ButtonRole.AcceptRole)
            quit_btn = msg.addButton("退出", QMessageBox.ButtonRole.RejectRole)
            msg.exec()

            if msg.clickedButton() == quit_btn:
                return False

    # ------------------------------------------------------------------
    # Orchestrator: check_license() (Task 3.5)
    # ------------------------------------------------------------------

    def check_license(self) -> bool:
        """
        完整授权检查（有 UI 支持）。

        核心原则：
        - 永久卡（无 expire_time）：本地验证过 → 直接放行，不联网
        - 天卡（有 expire_time）：本地未过期 → 直接放行，不联网
        - 试用：必须联网验证
        - 只有首次验证、时间回拨、过期/被拒才需要联网
        """
        if _DEV_MODE:
            logger.info("开发模式：跳过授权验证")
            return True

        data = self.crypto.load()

        # 硬件指纹容差匹配
        if data and data.get("feature_hashes"):
            matched, updated_hashes = self.machine.match_features(
                data["feature_hashes"]
            )
            if not matched:
                logger.warning("Hardware fingerprint mismatch (< 3/4 features)")
                return self._handle_first_use()
            if updated_hashes != data["feature_hashes"]:
                data["feature_hashes"] = updated_hashes
                self.crypto.save(data)

            if data.get("stored_machine_id"):
                self.machine_id = data["stored_machine_id"]
            else:
                data["stored_machine_id"] = self.machine_id
                self.crypto.save(data)

        license_type = data.get("license_type") if data else None

        # ── 永久卡 / 天卡 ──
        if license_type in ("permanent", "daily"):
            expire_time = data.get("expire_time")
            has_verified = bool(data.get("last_seen_time"))
            time_rollback = self._check_time_rollback(data)

            # 永久卡：曾经验证过 + 无时间回拨 → 秒进
            if not expire_time and has_verified and not time_rollback:
                logger.info("永久卡本地放行（已验证过，无需联网）")
                return True

            # 天卡：未过期 + 曾经验证过 + 无时间回拨 → 秒进
            if expire_time and has_verified and not time_rollback:
                if time.time() <= expire_time:
                    logger.info("天卡本地放行（未过期，无需联网）")
                    return True
                # 天卡已过期 → 显示进群领码对话框
                logger.info("天卡已过期")
                return self._show_trial_expired_dialog()

            # 需要联网验证（首次 / 时间回拨）
            def _verify_task():
                _get_server_url()
                return self._verify_permanent(data)

            result = self._run_with_loading(_verify_task)
            if result:
                return True
            if expire_time:
                return self._show_trial_expired_dialog()
            return self._show_activation_dialog()

        # ── 试用 ──
        if license_type == "trial":
            # 试用缓存：4小时内验证过 + 未过期 → 直接放行，不联网
            last_seen = data.get("last_seen_time", 0)
            expire_time = data.get("expire_time")
            time_rollback = self._check_time_rollback(data)

            if last_seen and not time_rollback:
                hours_since = (time.time() - last_seen) / 3600
                if hours_since < 4:
                    # 检查是否过期
                    if expire_time and time.time() > expire_time:
                        logger.info("试用已过期（本地判断）")
                        return self._show_trial_expired_dialog()
                    logger.info("试用本地放行（4小时内已验证，无需联网）")
                    return True

            def _verify_trial_task():
                _get_server_url()
                return self._verify_trial(data)

            result = self._run_with_loading(_verify_trial_task)
            if result:
                return True
            return self._show_trial_expired_dialog()

        # ── 已吊销 ──
        if license_type == "revoked":
            self._run_with_loading(lambda: (_get_server_url(), True)[-1])
            return self._show_activation_dialog()

        # ── 无数据 / 未知 → 首次使用，显示激活/试用对话框 ──
        return self._handle_first_use()

    def _run_with_loading(self, task_fn) -> bool:
        """
        Run a blocking task in a QThread while showing a loading indicator.

        Args:
            task_fn: Callable that returns bool.

        Returns:
            The bool result from task_fn.
        """
        try:
            from PyQt6.QtWidgets import QDialog, QVBoxLayout, QLabel, QApplication
            from PyQt6.QtCore import Qt, QThread, pyqtSignal

            app = QApplication.instance()
            if app is None:
                # No QApplication — just run directly
                return task_fn()

            class _Worker(QThread):
                finished = pyqtSignal(bool)

                def __init__(self, fn):
                    super().__init__()
                    self._fn = fn

                def run(self):
                    try:
                        result = self._fn()
                    except Exception as exc:
                        logger.error("License verification worker exception: %s", exc, exc_info=True)
                        result = False
                    self.finished.emit(result)

            # Create a minimal loading dialog
            loading = QDialog()
            loading.setWindowFlags(
                Qt.WindowType.FramelessWindowHint
                | Qt.WindowType.Dialog
                | Qt.WindowType.WindowStaysOnTopHint
            )
            loading.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
            loading.setFixedSize(260, 80)
            layout = QVBoxLayout(loading)
            label = QLabel("正在验证授权...")
            label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            label.setStyleSheet(
                "background: #1c1c1c; color: #ffffff; border-radius: 8px;"
                " padding: 20px; font-size: 14px;"
            )
            layout.addWidget(label)

            # Center on screen
            screen = app.primaryScreen()
            if screen:
                geo = screen.availableGeometry()
                loading.move(
                    geo.center().x() - loading.width() // 2,
                    geo.center().y() - loading.height() // 2,
                )

            result_holder = [False]

            worker = _Worker(task_fn)

            def on_finished(result):
                result_holder[0] = result
                loading.accept()

            worker.finished.connect(on_finished)
            worker.start()
            loading.exec()
            worker.wait()

            return result_holder[0]

        except ImportError:
            # PyQt6 not available — run directly
            return task_fn()


# ------------------------------------------------------------------
# Module-level quick check (Task 3.5)
# ------------------------------------------------------------------


def quick_license_check() -> str:
    """
    静默预检（无 UI），供 main.py 调用。

    逻辑与 check_license 对齐：
    - 永久卡：验证过 → "ok"
    - 天卡：未过期 + 验证过 → "ok"
    - 试用：4小时内验证过 → "ok"
    - 其他情况 → "needs_ui"

    Returns:
        "ok"       — 本地数据有效，直接进入
        "needs_ui" — 需要 UI 交互（联网验证/激活/试用）
    """
    if _DEV_MODE:
        return "ok"

    try:
        machine = MachineID()
        machine_id = machine.get_machine_id()
        crypto = LicenseCrypto(machine_id)
        data = crypto.load()

        if data is None:
            return "needs_ui"

        # 硬件指纹容差
        stored_hashes = data.get("feature_hashes")
        if stored_hashes:
            matched, updated_hashes = machine.match_features(stored_hashes)
            if not matched:
                return "needs_ui"
            if updated_hashes != stored_hashes:
                data["feature_hashes"] = updated_hashes
                crypto.save(data)
            if not data.get("stored_machine_id"):
                data["stored_machine_id"] = machine_id
                crypto.save(data)

        license_type = data.get("license_type")

        # 时间回拨 → 需要联网
        if LicenseManager._check_time_rollback(data):
            return "needs_ui"

        if license_type in ("permanent", "daily"):
            expire_time = data.get("expire_time")
            # 天卡已过期
            if expire_time and time.time() > expire_time:
                return "needs_ui"
            # 曾经验证过 → 直接放行
            if data.get("last_seen_time"):
                return "ok"
            return "needs_ui"

        if license_type == "trial":
            last_seen = data.get("last_seen_time", 0)
            if last_seen and (time.time() - last_seen) < 4 * 3600:
                return "ok"
            return "needs_ui"

        if license_type == "revoked":
            return "needs_ui"

        return "needs_ui"

    except Exception as exc:
        logger.warning("quick_license_check error: %s", exc)
        return "needs_ui"
