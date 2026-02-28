"""
硬件指纹采集与匹配模块
通过采集多个硬件特征生成唯一的 Machine ID，支持 4 取 3 容错匹配。

性能优化：
- 4 个硬件特征合并为 1 条 PowerShell 命令（只启动一次进程）
- 采集结果缓存到本地文件，后续启动直接读缓存（< 1ms）
- 缓存有效期 7 天，过期后重新采集
"""

import hashlib
import json
import logging
import os
import platform
import subprocess
import sys
import time
from typing import Dict, Optional, Tuple
from uuid import getnode

logger = logging.getLogger(__name__)

_SUBPROCESS_FLAGS = 0
if sys.platform == "win32":
    _SUBPROCESS_FLAGS = subprocess.CREATE_NO_WINDOW

_FEATURE_KEYS = ("cpu_id", "mb_serial", "disk_serial", "win_sid")

# 缓存文件路径和有效期
_CACHE_DIR = os.path.join(os.environ.get("APPDATA", ""), "ue_toolkit")
_CACHE_FILE = os.path.join(_CACHE_DIR, ".hw_cache")
_CACHE_TTL = 7 * 24 * 3600  # 7 天

# 合并的 PowerShell 脚本（一次进程调用采集全部 4 个特征）
_PS_SCRIPT = """
$cpu = (Get-CimInstance Win32_Processor).ProcessorId
$mb = (Get-CimInstance Win32_BaseBoard).SerialNumber
$disk = (Get-CimInstance Win32_DiskDrive -Filter 'Index=0').SerialNumber
$sid = (Get-CimInstance Win32_UserAccount -Filter "Name='%USERNAME%'").SID
Write-Output "CPU:$cpu"
Write-Output "MB:$mb"
Write-Output "DISK:$disk"
Write-Output "SID:$sid"
""".strip().replace("%USERNAME%", os.environ.get("USERNAME", ""))

# wmic 回退命令（逐个执行，仅在 PowerShell 失败时使用）
_WMIC_COMMANDS = {
    "cpu_id": "wmic cpu get ProcessorId",
    "mb_serial": "wmic baseboard get SerialNumber",
    "disk_serial": "wmic diskdrive where Index=0 get SerialNumber",
    "win_sid": f'wmic useraccount where name=\'{os.environ.get("USERNAME", "")}\' get sid',
}


def _sha256(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _parse_ps_output(output: str) -> Dict[str, str]:
    """解析合并 PowerShell 脚本的输出"""
    prefix_map = {"CPU:": "cpu_id", "MB:": "mb_serial", "DISK:": "disk_serial", "SID:": "sid_raw"}
    result = {}
    for line in output.splitlines():
        line = line.strip()
        for prefix, key in prefix_map.items():
            if line.startswith(prefix):
                val = line[len(prefix):].strip()
                if val and val.lower() not in ("", "none", "default string"):
                    result[key] = val
                break
    # 映射 sid_raw → win_sid
    if "sid_raw" in result:
        result["win_sid"] = result.pop("sid_raw")
    return result


def _collect_all_powershell() -> Optional[Dict[str, str]]:
    """一次 PowerShell 调用采集全部 4 个特征"""
    try:
        result = subprocess.run(
            ["powershell", "-NoProfile", "-Command", _PS_SCRIPT],
            capture_output=True, text=True, timeout=8,
            creationflags=_SUBPROCESS_FLAGS,
        )
        if result.returncode == 0 and result.stdout.strip():
            parsed = _parse_ps_output(result.stdout)
            if parsed:
                return parsed
    except Exception as exc:
        logger.debug("PowerShell batch collection failed: %s", exc)
    return None


def _collect_wmic_fallback() -> Dict[str, str]:
    """逐个 wmic 命令回退采集"""
    result = {}
    for key, cmd in _WMIC_COMMANDS.items():
        try:
            proc = subprocess.run(
                cmd, shell=True, capture_output=True, text=True,
                timeout=5, creationflags=_SUBPROCESS_FLAGS,
            )
            lines = [ln.strip() for ln in proc.stdout.splitlines() if ln.strip()]
            if lines:
                val = lines[-1]
                if val.lower() not in ("", "none", "default string"):
                    result[key] = val
        except Exception as exc:
            logger.debug("wmic fallback failed for %s: %s", key, exc)
    return result


def _load_cache() -> Optional[Dict[str, str]]:
    """读取缓存的硬件特征（未过期时直接使用）"""
    try:
        if not os.path.exists(_CACHE_FILE):
            return None
        with open(_CACHE_FILE, "r", encoding="utf-8") as f:
            cache = json.load(f)
        # 检查过期
        if time.time() - cache.get("ts", 0) > _CACHE_TTL:
            return None
        features = cache.get("features")
        if features and isinstance(features, dict):
            return features
    except Exception:
        pass
    return None


def _save_cache(features: Dict[str, str]):
    """保存硬件特征到缓存"""
    try:
        os.makedirs(_CACHE_DIR, exist_ok=True)
        with open(_CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump({"ts": time.time(), "features": features}, f)
    except Exception as exc:
        logger.debug("Failed to save hw cache: %s", exc)


class MachineID:
    """硬件指纹采集与匹配（单例缓存）"""

    _instance: 'MachineID' = None
    _cached_machine_id: str = None
    _cached_feature_hashes: dict = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def _collect_raw_features(self) -> Dict[str, str]:
        """采集原始硬件特征值（优先缓存 → PowerShell 合并 → wmic 回退）"""
        # 1. 尝试缓存
        cached = _load_cache()
        if cached:
            logger.debug("Using cached hardware features")
            return cached

        # 2. 合并 PowerShell（~1-2 秒）
        features = _collect_all_powershell()

        # 3. 回退 wmic
        if not features:
            features = _collect_wmic_fallback()

        # 4. 兜底
        if not features:
            logger.warning("All hardware collection failed, using platform fallback")
            fallback = f"{platform.node()}-{getnode()}"
            features = {key: f"{fallback}-{key}" for key in _FEATURE_KEYS}

        # 保存缓存
        _save_cache(features)
        return features

    def get_feature_hashes(self) -> Dict[str, str]:
        """采集 4 个硬件特征并返回各自的 SHA-256 哈希（带缓存）"""
        if MachineID._cached_feature_hashes is not None:
            return MachineID._cached_feature_hashes
        raw = self._collect_raw_features()
        MachineID._cached_feature_hashes = {key: _sha256(raw.get(key, "UNKNOWN")) for key in _FEATURE_KEYS}
        return MachineID._cached_feature_hashes

    def get_machine_id(self) -> str:
        """生成复合 Machine ID（SHA-256）（带缓存）"""
        if MachineID._cached_machine_id is not None:
            return MachineID._cached_machine_id
        feature_hashes = self.get_feature_hashes()
        combined = "".join(feature_hashes[k] for k in sorted(feature_hashes))
        MachineID._cached_machine_id = _sha256(combined)
        return MachineID._cached_machine_id

    def match_features(
        self, stored_hashes: Dict[str, str]
    ) -> Tuple[bool, Dict[str, str]]:
        """容错匹配：4 个特征中 >= 3 个匹配即视为同一台机器"""
        current_hashes = self.get_feature_hashes()
        match_count = sum(
            1 for key in _FEATURE_KEYS
            if current_hashes.get(key) == stored_hashes.get(key)
        )
        is_match = match_count >= 3
        if is_match:
            return True, {key: current_hashes[key] for key in _FEATURE_KEYS}
        return False, dict(stored_hashes)
