"""
安全配置管理器
用于安全存储和检索敏感数据（如 API 密钥、密码等）
"""

import os
import json
import logging
import platform
from pathlib import Path
from typing import Optional, Dict, Any

try:
    import keyring
    from keyring.errors import KeyringError
    KEYRING_AVAILABLE = True
except ImportError:
    KEYRING_AVAILABLE = False
    KeyringError = Exception

try:
    from cryptography.fernet import Fernet
    CRYPTOGRAPHY_AVAILABLE = True
except ImportError:
    CRYPTOGRAPHY_AVAILABLE = False

logger = logging.getLogger(__name__)


class SecureConfigManager:
    """管理敏感配置的安全存储"""

    SERVICE_NAME = "ue_toolkit"
    ENCRYPTION_KEY_NAME = "encryption_key"

    def __init__(self, config_dir: Optional[Path] = None):
        """
        初始化安全配置管理器

        Args:
            config_dir: 配置目录路径，默认为用户配置目录
        """
        if config_dir is None:
            # 使用默认配置目录
            if platform.system() == "Windows":
                config_dir = Path(os.environ.get("APPDATA", "")) / "UEToolkit"
            else:
                config_dir = Path.home() / ".config" / "ue_toolkit"

        self.config_dir = Path(config_dir)
        self.config_dir.mkdir(parents=True, exist_ok=True)

        self.secure_config_path = self.config_dir / ".secure_config"
        self._encryption_key: Optional[bytes] = None

        # 检查依赖可用性
        if not KEYRING_AVAILABLE:
            logger.warning("keyring 库不可用，将使用加密文件存储作为备用方案")

        if not CRYPTOGRAPHY_AVAILABLE:
            logger.warning("cryptography 库不可用，加密功能将不可用")

    def save_api_key(self, provider: str, api_key: str) -> bool:
        """
        保存 API 密钥到系统密钥环

        Args:
            provider: 提供商名称（如 'openai', 'anthropic'）
            api_key: API 密钥

        Returns:
            bool: 是否成功保存
        """
        if not api_key:
            logger.warning(f"尝试保存空的 API 密钥: {provider}")
            return False

        key_name = f"api_key_{provider}"

        # 尝试使用系统密钥环
        if KEYRING_AVAILABLE:
            try:
                keyring.set_password(self.SERVICE_NAME, key_name, api_key)
                logger.info(f"API 密钥已安全保存到系统密钥环: {provider}")
                return True
            except KeyringError as e:
                logger.warning(f"无法保存到系统密钥环: {e}，将使用加密文件存储")
            except Exception as e:
                logger.error(f"保存到密钥环时发生未知错误: {e}")

        # 备用方案：加密文件存储
        if CRYPTOGRAPHY_AVAILABLE:
            try:
                self._save_encrypted(key_name, api_key)
                logger.info(f"API 密钥已保存到加密文件: {provider}")
                return True
            except Exception as e:
                logger.error(f"保存到加密文件失败: {e}")
                return False
        else:
            logger.error("无可用的安全存储方法")
            return False

    def get_api_key(self, provider: str) -> Optional[str]:
        """
        从系统密钥环检索 API 密钥

        Args:
            provider: 提供商名称

        Returns:
            Optional[str]: API 密钥，如果不存在则返回 None
        """
        key_name = f"api_key_{provider}"

        # 尝试从系统密钥环读取
        if KEYRING_AVAILABLE:
            try:
                api_key = keyring.get_password(self.SERVICE_NAME, key_name)
                if api_key:
                    logger.debug(f"从系统密钥环读取 API 密钥: {provider}")
                    return api_key
            except KeyringError as e:
                logger.warning(f"从密钥环读取失败: {e}")
            except Exception as e:
                logger.error(f"读取密钥环时发生未知错误: {e}")

        # 备用方案：从加密文件读取
        if CRYPTOGRAPHY_AVAILABLE:
            try:
                api_key = self._load_encrypted(key_name)
                if api_key:
                    logger.debug(f"从加密文件读取 API 密钥: {provider}")
                    return api_key
            except Exception as e:
                logger.error(f"从加密文件读取失败: {e}")

        logger.debug(f"未找到 API 密钥: {provider}")
        return None

    def delete_api_key(self, provider: str) -> bool:
        """
        删除 API 密钥

        Args:
            provider: 提供商名称

        Returns:
            bool: 是否成功删除
        """
        key_name = f"api_key_{provider}"
        success = False

        # 从系统密钥环删除
        if KEYRING_AVAILABLE:
            try:
                keyring.delete_password(self.SERVICE_NAME, key_name)
                logger.info(f"从系统密钥环删除 API 密钥: {provider}")
                success = True
            except KeyringError:
                pass  # 密钥可能不存在
            except Exception as e:
                logger.error(f"从密钥环删除失败: {e}")

        # 从加密文件删除
        if CRYPTOGRAPHY_AVAILABLE:
            try:
                secure_config = self._load_secure_config()
                if key_name in secure_config:
                    del secure_config[key_name]
                    self._save_secure_config(secure_config)
                    logger.info(f"从加密文件删除 API 密钥: {provider}")
                    success = True
            except Exception as e:
                logger.error(f"从加密文件删除失败: {e}")

        return success

    def _get_or_create_encryption_key(self) -> bytes:
        """
        获取或创建加密密钥

        Returns:
            bytes: 加密密钥
        """
        if self._encryption_key:
            return self._encryption_key

        # 尝试从密钥环读取
        if KEYRING_AVAILABLE:
            try:
                key_str = keyring.get_password(self.SERVICE_NAME, self.ENCRYPTION_KEY_NAME)
                if key_str:
                    self._encryption_key = key_str.encode()
                    return self._encryption_key
            except Exception as e:
                logger.debug(f"无法从密钥环读取加密密钥: {e}")

        # 生成新密钥
        self._encryption_key = Fernet.generate_key()

        # 尝试保存到密钥环
        if KEYRING_AVAILABLE:
            try:
                keyring.set_password(
                    self.SERVICE_NAME,
                    self.ENCRYPTION_KEY_NAME,
                    self._encryption_key.decode()
                )
                logger.info("加密密钥已保存到系统密钥环")
            except Exception as e:
                logger.warning(f"无法保存加密密钥到密钥环: {e}")

        return self._encryption_key

    def _save_encrypted(self, key: str, value: str) -> None:
        """
        保存加密值到文件

        Args:
            key: 键名
            value: 要加密的值
        """
        if not CRYPTOGRAPHY_AVAILABLE:
            raise RuntimeError("cryptography 库不可用")

        # 获取加密密钥
        encryption_key = self._get_or_create_encryption_key()
        fernet = Fernet(encryption_key)

        # 加密值
        encrypted_value = fernet.encrypt(value.encode())

        # 加载现有配置
        secure_config = self._load_secure_config()
        secure_config[key] = encrypted_value.decode()

        # 保存配置
        self._save_secure_config(secure_config)

    def _load_encrypted(self, key: str) -> Optional[str]:
        """
        从文件加载加密值

        Args:
            key: 键名

        Returns:
            Optional[str]: 解密后的值，如果不存在则返回 None
        """
        if not CRYPTOGRAPHY_AVAILABLE:
            return None

        # 加载配置
        secure_config = self._load_secure_config()
        encrypted_value = secure_config.get(key)

        if not encrypted_value:
            return None

        try:
            # 获取加密密钥
            encryption_key = self._get_or_create_encryption_key()
            fernet = Fernet(encryption_key)

            # 解密值
            decrypted_value = fernet.decrypt(encrypted_value.encode())
            return decrypted_value.decode()
        except Exception as e:
            logger.error(f"解密失败: {e}")
            return None

    def _load_secure_config(self) -> Dict[str, Any]:
        """
        加载安全配置文件

        Returns:
            Dict[str, Any]: 配置字典
        """
        if not self.secure_config_path.exists():
            return {}

        try:
            with open(self.secure_config_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except json.JSONDecodeError as e:
            logger.error(f"安全配置文件格式错误: {e}")
            return {}
        except Exception as e:
            logger.error(f"读取安全配置文件失败: {e}")
            return {}

    def _save_secure_config(self, config: Dict[str, Any]) -> None:
        """
        保存安全配置文件

        Args:
            config: 配置字典
        """
        try:
            with open(self.secure_config_path, 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=2)

            # 设置限制性文件权限（仅所有者可读写）
            if platform.system() != 'Windows':
                os.chmod(self.secure_config_path, 0o600)
                logger.debug("已设置安全配置文件权限为 0o600")
        except Exception as e:
            logger.error(f"保存安全配置文件失败: {e}")
            raise

    def migrate_plaintext_secrets(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """
        迁移明文密钥到安全存储

        Args:
            config: 包含明文密钥的配置字典

        Returns:
            Dict[str, Any]: 更新后的配置字典（明文密钥已替换为占位符）
        """
        sensitive_keys = ['api_key', 'password', 'token', 'secret']
        migrated_count = 0

        def check_and_migrate(obj: Any, path: str = "") -> Any:
            """递归检查并迁移敏感数据"""
            nonlocal migrated_count

            if isinstance(obj, dict):
                new_obj = {}
                for key, value in obj.items():
                    current_path = f"{path}.{key}" if path else key

                    # 检查是否是敏感键
                    if any(sensitive in key.lower() for sensitive in sensitive_keys):
                        if isinstance(value, str) and value and value != "[ENCRYPTED]":
                            # 保存到安全存储
                            self.save_api_key(current_path, value)
                            new_obj[key] = "[ENCRYPTED]"
                            migrated_count += 1
                            logger.info(f"已迁移敏感数据: {current_path}")
                        else:
                            new_obj[key] = value
                    else:
                        # 递归处理嵌套对象
                        new_obj[key] = check_and_migrate(value, current_path)
                return new_obj
            elif isinstance(obj, list):
                return [check_and_migrate(item, f"{path}[{i}]") for i, item in enumerate(obj)]
            else:
                return obj

        updated_config = check_and_migrate(config)

        if migrated_count > 0:
            logger.info(f"成功迁移 {migrated_count} 个敏感数据到安全存储")
        else:
            logger.info("未发现需要迁移的明文敏感数据")

        return updated_config
