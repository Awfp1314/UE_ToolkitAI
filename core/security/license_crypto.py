"""
授权数据加密存储模块
使用 PBKDF2 密钥派生 + AES-GCM 认证加密，支持 3 处冗余存储与自动恢复。
"""

import ctypes
import hashlib
import json
import logging
import os
import platform
import sys
from typing import Optional

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes

logger = logging.getLogger(__name__)

# Application secret used for key derivation alongside Machine ID
# Security: Use environment variable or derive from machine_id to avoid hardcoding
def _get_app_secret() -> str:
    """
    Get application secret for key derivation.
    Priority: Environment variable > Derived from system entropy
    """
    env_secret = os.environ.get("UE_TOOLKIT_APP_SECRET")
    if env_secret:
        return env_secret
    
    # Fallback: Derive from a combination of system-specific values
    # This is not stored anywhere and will be consistent per system
    import platform
    system_info = f"{platform.node()}-{platform.system()}-{platform.machine()}"
    derived = hashlib.sha256(system_info.encode("utf-8")).hexdigest()
    return f"UeToolkit-{derived[:32]}"

APP_SECRET = _get_app_secret()

# PBKDF2 parameters
_PBKDF2_ITERATIONS = 100_000
_KEY_LENGTH = 32  # 256-bit key for AES-256-GCM
_NONCE_LENGTH = 12  # 96-bit nonce for AES-GCM

# 派生密钥缓存（同一 machine_id 只计算一次）
_derived_key_cache: dict = {}


# Storage paths
_APPDATA_DIR = os.path.join(os.environ.get("APPDATA", ""), "ue_toolkit")
_APPDATA_PATH = os.path.join(_APPDATA_DIR, "license.dat")
_HIDDEN_FILE_PATH = os.path.join(
    os.environ.get("USERPROFILE", ""), ".ue_toolkit_license"
)

# Registry constants
_REG_KEY_PATH = r"Software\UEToolkit"
_REG_VALUE_NAME = "License"


class LicenseCrypto:
    """授权数据加密存储"""

    def __init__(self, machine_id: str):
        """使用 machine_id + APP_SECRET 派生加密密钥（带缓存）"""
        self._key = self._derive_key(machine_id)

    # ------------------------------------------------------------------
    # Key derivation
    # ------------------------------------------------------------------

    @staticmethod
    def _derive_key(machine_id: str) -> bytes:
        """
        PBKDF2 密钥派生（带内存缓存，同一 machine_id 只计算一次）:
        - Password: machine_id (UTF-8 bytes)
        - Salt: SHA-256(APP_SECRET)[:16]
        - Iterations: 100,000
        - Key length: 32 bytes (256-bit)
        """
        if machine_id in _derived_key_cache:
            return _derived_key_cache[machine_id]

        salt = hashlib.sha256(APP_SECRET.encode("utf-8")).digest()[:16]
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=_KEY_LENGTH,
            salt=salt,
            iterations=_PBKDF2_ITERATIONS,
        )
        key = kdf.derive(machine_id.encode("utf-8"))
        _derived_key_cache[machine_id] = key
        return key

    # ------------------------------------------------------------------
    # Encryption / Decryption
    # ------------------------------------------------------------------

    def _encrypt(self, data: bytes) -> bytes:
        """
        AES-GCM 加密。
        Returns: nonce (12 bytes) + ciphertext (includes GCM tag)
        """
        nonce = os.urandom(_NONCE_LENGTH)
        aesgcm = AESGCM(self._key)
        ciphertext = aesgcm.encrypt(nonce, data, None)
        return nonce + ciphertext

    def _decrypt(self, data: bytes) -> bytes:
        """
        AES-GCM 解密。
        Expects: nonce (12 bytes) + ciphertext
        """
        nonce = data[:_NONCE_LENGTH]
        ciphertext = data[_NONCE_LENGTH:]
        aesgcm = AESGCM(self._key)
        return aesgcm.decrypt(nonce, ciphertext, None)


    # ------------------------------------------------------------------
    # File attribute helpers (Windows)
    # ------------------------------------------------------------------

    @staticmethod
    def _clear_file_attributes(path: str) -> None:
        """Reset file attributes to NORMAL before read/write to avoid PermissionError on hidden/read-only files."""
        if sys.platform != "win32":
            return
        try:
            if os.path.exists(path):
                # FILE_ATTRIBUTE_NORMAL = 0x80
                ctypes.windll.kernel32.SetFileAttributesW(path, 0x80)
        except Exception:
            pass

    @staticmethod
    def _set_hidden_attribute(path: str) -> None:
        """Set hidden attribute on a file (Windows only)."""
        if sys.platform != "win32":
            return
        try:
            # FILE_ATTRIBUTE_HIDDEN = 0x02
            ctypes.windll.kernel32.SetFileAttributesW(path, 0x02)
        except Exception:
            pass  # Non-critical

    # ------------------------------------------------------------------
    # Individual storage writers
    # ------------------------------------------------------------------

    @staticmethod
    def _write_appdata(data: bytes) -> bool:
        """Write encrypted data to %APPDATA%/ue_toolkit/license.dat"""
        try:
            os.makedirs(_APPDATA_DIR, exist_ok=True)
            with open(_APPDATA_PATH, "wb") as f:
                f.write(data)
            return True
        except Exception as exc:
            logger.warning("Failed to write appdata license: %s", exc)
            return False

    @staticmethod
    def _write_registry(data: bytes) -> bool:
        """Write encrypted data to HKCU\\Software\\UEToolkit\\License"""
        if sys.platform != "win32":
            return False
        try:
            import winreg

            key = winreg.CreateKey(winreg.HKEY_CURRENT_USER, _REG_KEY_PATH)
            winreg.SetValueEx(key, _REG_VALUE_NAME, 0, winreg.REG_BINARY, data)
            winreg.CloseKey(key)
            return True
        except Exception as exc:
            logger.warning("Failed to write registry license: %s", exc)
            return False

    @classmethod
    def _write_hidden_file(cls, data: bytes) -> bool:
        """Write encrypted data to %USERPROFILE%/.ue_toolkit_license with hidden attribute"""
        try:
            # Clear hidden/read-only attributes before writing to avoid PermissionError
            cls._clear_file_attributes(_HIDDEN_FILE_PATH)
            with open(_HIDDEN_FILE_PATH, "wb") as f:
                f.write(data)
            cls._set_hidden_attribute(_HIDDEN_FILE_PATH)
            return True
        except Exception as exc:
            logger.warning("Failed to write hidden license file: %s", exc)
            return False

    # ------------------------------------------------------------------
    # Individual storage readers
    # ------------------------------------------------------------------

    @staticmethod
    def _read_appdata() -> Optional[bytes]:
        """Read encrypted data from appdata location."""
        try:
            with open(_APPDATA_PATH, "rb") as f:
                return f.read()
        except Exception:
            return None

    @staticmethod
    def _read_registry() -> Optional[bytes]:
        """Read encrypted data from registry."""
        if sys.platform != "win32":
            return None
        try:
            import winreg

            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, _REG_KEY_PATH)
            value, _ = winreg.QueryValueEx(key, _REG_VALUE_NAME)
            winreg.CloseKey(key)
            return bytes(value) if value else None
        except Exception:
            return None

    @classmethod
    def _read_hidden_file(cls) -> Optional[bytes]:
        """Read encrypted data from hidden file."""
        try:
            with open(_HIDDEN_FILE_PATH, "rb") as f:
                return f.read()
        except PermissionError:
            # Hidden/read-only attribute may block read — clear and retry
            logger.info("PermissionError reading hidden file, clearing attributes and retrying")
            cls._clear_file_attributes(_HIDDEN_FILE_PATH)
            try:
                with open(_HIDDEN_FILE_PATH, "rb") as f:
                    return f.read()
            except Exception:
                return None
        except Exception:
            return None


    # ------------------------------------------------------------------
    # Public API: save / load with redundancy and recovery
    # ------------------------------------------------------------------

    def save(self, data: dict) -> bool:
        """
        JSON-serialize, encrypt, and write to all 3 redundant storage locations.

        Returns True if at least one location was written successfully.
        """
        try:
            raw = json.dumps(data, ensure_ascii=False).encode("utf-8")
            encrypted = self._encrypt(raw)
        except Exception as exc:
            logger.error("Failed to encrypt license data: %s", exc)
            return False

        results = [
            self._write_appdata(encrypted),
            self._write_registry(encrypted),
            self._write_hidden_file(encrypted),
        ]

        success_count = sum(results)
        if success_count == 0:
            logger.error("Failed to write license data to any storage location")
            return False

        logger.info(
            "License data saved to %d/3 storage locations", success_count
        )
        return True

    def load(self) -> Optional[dict]:
        """
        Read from all 3 storage locations, return first valid decrypted data,
        and restore any corrupted/missing locations from the valid copy.

        Returns None if all locations are invalid or missing.
        """
        readers = [
            ("appdata", self._read_appdata),
            ("registry", self._read_registry),
            ("hidden_file", self._read_hidden_file),
        ]
        writers = [
            ("appdata", self._write_appdata),
            ("registry", self._write_registry),
            ("hidden_file", self._write_hidden_file),
        ]

        valid_data: Optional[dict] = None
        valid_encrypted: Optional[bytes] = None
        failed_indices: list[int] = []

        for i, (name, reader) in enumerate(readers):
            encrypted = reader()
            if encrypted is None:
                logger.debug("Storage location '%s' is missing", name)
                failed_indices.append(i)
                continue
            try:
                decrypted = self._decrypt(encrypted)
                data = json.loads(decrypted.decode("utf-8"))
                if valid_data is None:
                    valid_data = data
                    valid_encrypted = encrypted
                    logger.debug("Loaded license data from '%s'", name)
                # Even if we already have valid data, this location is fine
            except Exception as exc:
                logger.warning(
                    "Storage location '%s' is corrupted: %s", name, exc
                )
                failed_indices.append(i)

        # Restore corrupted/missing locations from valid data
        if valid_encrypted is not None and failed_indices:
            for i in failed_indices:
                w_name, writer = writers[i]
                if writer(valid_encrypted):
                    logger.info("Restored storage location '%s'", w_name)
                else:
                    logger.warning(
                        "Failed to restore storage location '%s'", w_name
                    )

        return valid_data
