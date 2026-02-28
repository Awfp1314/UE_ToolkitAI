# -*- coding: utf-8 -*-

"""
配置管理器模块
负责管理应用程序的配置文件，包括用户ID、跳过版本列表和待上报事件队列
"""

import os
import json
import yaml
import uuid
import time
import shutil
import tempfile
import threading
import platform
from pathlib import Path
from typing import Optional, Dict, Any, List
from datetime import datetime

from core.logger import get_logger
from core.exceptions import ConfigError
from core.utils.path_validator import PathValidator
from core.utils.config_utils import ConfigUtils
from core.constants import (
    CONFIG_FILE_LOCK_TIMEOUT_SECONDS,
    CONFIG_RETRY_DELAY_SECONDS,
    CONFIG_PENDING_EVENTS_MAX_SIZE
)

logger = get_logger(__name__)


class ConfigManager:
    """配置管理器类"""
    
    # Class-level thread lock for preventing concurrent writes within the same process
    _save_lock = threading.Lock()
    
    def __init__(self, config_path: Optional[str] = None, format: str = "json"):
        """
        初始化配置管理器
        
        Args:
            config_path: 配置文件路径，默认为用户目录下的隐藏配置文件
            format: 配置文件格式，支持 "json" 或 "yaml"
        """
        self.format = format.lower()
        
        if self.format not in ["json", "yaml"]:
            raise ValueError(f"Unsupported config format: {format}. Use 'json' or 'yaml'.")
        
        # 设置配置文件路径
        if config_path is None:
            user_home = Path.home()
            config_dir = user_home / ".ue_toolkit"
            config_dir.mkdir(exist_ok=True)
            
            # 根据格式选择文件扩展名
            ext = "json" if self.format == "json" else "yaml"
            self.config_path = config_dir / f"config.{ext}"
        else:
            self.config_path = Path(config_path)
        
        # 加载配置
        self.config = self._load_config()
        
        logger.info(f"ConfigManager initialized with config file: {self.config_path}")
    
    def _acquire_file_lock(self, file_obj, timeout: float = CONFIG_FILE_LOCK_TIMEOUT_SECONDS) -> bool:
        """
        获取文件锁（跨平台实现）
        
        Args:
            file_obj: 文件对象
            timeout: 超时时间（秒）
            
        Returns:
            True if lock acquired, False if timeout
            
        Raises:
            TimeoutError: 如果在超时时间内无法获取锁
        """
        start_time = time.time()
        
        if platform.system() == 'Windows':
            # Windows: 使用 msvcrt.locking
            import msvcrt
            
            while True:
                try:
                    # 尝试锁定文件的第一个字节
                    msvcrt.locking(file_obj.fileno(), msvcrt.LK_NBLCK, 1)
                    logger.debug(f"File lock acquired for {self.config_path}")
                    return True
                except IOError:
                    # 锁定失败，检查超时
                    if time.time() - start_time > timeout:
                        logger.error(f"Failed to acquire file lock within {timeout}s for {self.config_path}")
                        raise TimeoutError(f"Failed to acquire file lock within {timeout} seconds")
                    # 短暂等待后重试（100ms）
                    time.sleep(0.1)
        else:
            # Unix/Linux/macOS: 使用 fcntl.flock
            import fcntl
            
            while True:
                try:
                    # 尝试获取排他锁（非阻塞）
                    fcntl.flock(file_obj.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                    logger.debug(f"File lock acquired for {self.config_path}")
                    return True
                except IOError:
                    # 锁定失败，检查超时
                    if time.time() - start_time > timeout:
                        logger.error(f"Failed to acquire file lock within {timeout}s for {self.config_path}")
                        raise TimeoutError(f"Failed to acquire file lock within {timeout} seconds")
                    # 短暂等待后重试（100ms）
                    time.sleep(0.1)
    
    def _release_file_lock(self, file_obj) -> None:
        """
        释放文件锁（跨平台实现）
        
        Args:
            file_obj: 文件对象
        """
        try:
            if platform.system() == 'Windows':
                # Windows: 使用 msvcrt.locking
                import msvcrt
                # 解锁文件的第一个字节
                msvcrt.locking(file_obj.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                # Unix/Linux/macOS: 使用 fcntl.flock
                import fcntl
                # 释放锁
                fcntl.flock(file_obj.fileno(), fcntl.LOCK_UN)
            
            logger.debug(f"File lock released for {self.config_path}")
        except Exception as e:
            logger.warning(f"Failed to release file lock: {e}")
    
    def _load_config(self) -> Dict[str, Any]:
        """
        加载配置文件
        
        使用 ConfigUtils 进行配置文件读取，支持从备份恢复。
        
        Returns:
            配置字典
            
        Raises:
            ConfigError: 当配置文件严重损坏且无法恢复时
        """
        if not self.config_path.exists():
            logger.info(f"Config file not found, creating default config")
            return self._create_default_config()
        
        try:
            # 使用 ConfigUtils 读取配置
            if self.format == "json":
                config = ConfigUtils.read_json(self.config_path)
            else:  # yaml
                config = ConfigUtils.read_yaml(self.config_path)
            
            # ConfigUtils 返回 None 表示文件不存在（但我们已检查过）
            if config is None:
                logger.warning(f"Config file disappeared: {self.config_path}")
                return self._create_default_config()
            
            logger.debug(f"Config loaded from {self.config_path}")
            return config
            
        except ConfigError as e:
            # ConfigUtils 抛出 ConfigError 表示文件格式无效
            logger.error(f"Invalid config file format: {e}")
            
            # 尝试从备份恢复
            backup_path = self.config_path.with_suffix(self.config_path.suffix + '.bak')
            if backup_path.exists():
                try:
                    logger.info(f"Attempting to restore from backup: {backup_path}")
                    if self.format == "json":
                        config = ConfigUtils.read_json(backup_path)
                    else:
                        config = ConfigUtils.read_yaml(backup_path)
                    
                    if config is not None:
                        logger.info("Successfully restored config from backup")
                        return config
                except ConfigError as backup_error:
                    logger.error(f"Failed to restore from backup: {backup_error}")
            
            # 无法恢复，使用默认配置
            logger.warning("Using default config due to config file error")
            return self._create_default_config()
    
    def _create_default_config(self) -> Dict[str, Any]:
        """
        创建默认配置
        
        Returns:
            默认配置字典
            
        Raises:
            ConfigError: 当无法创建或保存默认配置时
        """
        config = {
            "user_id": None,
            "skipped_versions": [],
            "pending_events": [],
            "last_check": None,
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat()
        }
        
        try:
            self._save_config(config)
            logger.info("Default config created")
            return config
        except (PermissionError, OSError) as e:
            logger.error(f"Failed to save default config: {e}", exc_info=True)
            raise ConfigError(f"Cannot create default config: {e}") from e
    
    def _save_config(self, config: Optional[Dict[str, Any]] = None, retry: bool = True) -> None:
        """
        保存配置到文件（使用原子写入和文件锁）
        
        Args:
            config: 要保存的配置字典，如果为None则保存当前配置
            retry: 是否在失败时重试一次
            
        Raises:
            ConfigError: 当配置保存失败且无法恢复时
            TimeoutError: 当文件锁获取超时时
        """
        if config is None:
            config = self.config
        
        # 更新修改时间
        config['updated_at'] = datetime.now().isoformat()
        
        # 使用类级别的线程锁（Layer 1: Thread lock）
        with self._save_lock:
            temp_file = None
            temp_path = None
            
            try:
                # 确保目录存在
                try:
                    PathValidator.ensure_directory_exists(
                        self.config_path.parent,
                        name="Config directory"
                    )
                except (PermissionError, OSError) as e:
                    logger.error(f"Cannot create config directory: {e}")
                    raise ConfigError(f"Cannot create config directory: {e}") from e
                
                # 创建临时文件（在同一目录下，确保原子重命名可行）
                try:
                    temp_fd, temp_path = tempfile.mkstemp(
                        dir=self.config_path.parent,
                        prefix='.tmp_config_',
                        suffix=f'.{self.format}'
                    )
                except PermissionError as e:
                    logger.error(f"No permission to create temp file in: {self.config_path.parent}")
                    raise ConfigError(f"Cannot create temp config file: {e}") from e
                except OSError as e:
                    logger.error(f"OS error creating temp file: {e}", exc_info=True)
                    raise ConfigError(f"Failed to create temp config file: {e}") from e
                
                # 将文件描述符转换为文件对象
                temp_file = os.fdopen(temp_fd, 'w', encoding='utf-8')
                
                try:
                    # Layer 2: File lock
                    self._acquire_file_lock(temp_file, timeout=CONFIG_FILE_LOCK_TIMEOUT_SECONDS)
                    
                    try:
                        # 写入配置数据
                        if self.format == "json":
                            json.dump(config, temp_file, indent=2, ensure_ascii=False)
                        else:  # yaml
                            yaml.safe_dump(config, temp_file, allow_unicode=True, default_flow_style=False)
                        
                        # 刷新缓冲区并确保数据写入磁盘
                        temp_file.flush()
                        os.fsync(temp_file.fileno())
                        
                        logger.debug(f"Config data written to temp file: {temp_path}")
                    
                    finally:
                        # 释放文件锁
                        self._release_file_lock(temp_file)
                
                finally:
                    # 关闭临时文件
                    temp_file.close()
                
                # Layer 3: Atomic rename
                # 在Windows上，如果目标文件存在，需要先删除
                if platform.system() == 'Windows' and self.config_path.exists():
                    # 使用 ConfigUtils 创建备份（保持一致的备份格式）
                    backup_path = self.config_path.with_suffix(self.config_path.suffix + '.bak')
                    try:
                        # 使用 shutil.copy2 创建备份（保留元数据）
                        shutil.copy2(self.config_path, backup_path)
                        logger.debug(f"Created backup before atomic rename: {backup_path}")
                        
                        # 删除原文件
                        self.config_path.unlink()
                        # 移动临时文件到目标位置
                        shutil.move(temp_path, self.config_path)
                        # 原子写入成功后删除备份
                        backup_path.unlink()
                    except PermissionError as e:
                        # 恢复备份
                        if backup_path.exists():
                            try:
                                shutil.move(backup_path, self.config_path)
                            except Exception as restore_error:
                                logger.error(f"Failed to restore backup: {restore_error}")
                        logger.error(f"Permission denied during atomic rename: {e}")
                        raise ConfigError(f"Cannot save config (permission denied): {e}") from e
                    except OSError as e:
                        # 恢复备份
                        if backup_path.exists():
                            try:
                                shutil.move(backup_path, self.config_path)
                            except Exception as restore_error:
                                logger.error(f"Failed to restore backup: {restore_error}")
                        logger.error(f"OS error during atomic rename: {e}", exc_info=True)
                        raise ConfigError(f"Failed to save config: {e}") from e
                else:
                    # Unix/Linux/macOS: 原子重命名（自动覆盖）
                    # 在原子重命名前创建备份以支持恢复
                    if self.config_path.exists():
                        backup_path = self.config_path.with_suffix(self.config_path.suffix + '.bak')
                        try:
                            shutil.copy2(self.config_path, backup_path)
                            logger.debug(f"Created backup before atomic rename: {backup_path}")
                        except (PermissionError, OSError) as backup_error:
                            logger.warning(f"Failed to create backup: {backup_error}")
                    
                    try:
                        shutil.move(temp_path, self.config_path)
                    except PermissionError as e:
                        logger.error(f"Permission denied during atomic rename: {e}")
                        raise ConfigError(f"Cannot save config (permission denied): {e}") from e
                    except OSError as e:
                        logger.error(f"OS error during atomic rename: {e}", exc_info=True)
                        raise ConfigError(f"Failed to save config: {e}") from e
                
                logger.debug(f"Config saved to {self.config_path}")
                
            except TimeoutError as e:
                # 锁获取超时
                logger.error(f"Failed to acquire lock for config save: {e}")
                
                # 清理临时文件
                if temp_path and os.path.exists(temp_path):
                    try:
                        os.unlink(temp_path)
                    except Exception as cleanup_error:
                        logger.warning(f"Failed to cleanup temp file: {cleanup_error}")
                
                # 重试一次
                if retry:
                    logger.info("Retrying config save...")
                    time.sleep(CONFIG_RETRY_DELAY_SECONDS)
                    self._save_config(config, retry=False)
                else:
                    raise
            
            except ConfigError:
                # 重新抛出 ConfigError
                # 清理临时文件
                if temp_file and not temp_file.closed:
                    try:
                        temp_file.close()
                    except Exception:
                        pass
                
                if temp_path and os.path.exists(temp_path):
                    try:
                        os.unlink(temp_path)
                    except Exception:
                        pass
                raise
                
            except Exception as e:
                logger.error(f"Unexpected error saving config: {e}", exc_info=True)
                
                # 清理临时文件
                if temp_file and not temp_file.closed:
                    try:
                        temp_file.close()
                    except Exception:
                        pass
                
                if temp_path and os.path.exists(temp_path):
                    try:
                        os.unlink(temp_path)
                    except Exception:
                        pass
                
                raise ConfigError(f"Unexpected error saving config: {e}") from e
    
    def get_user_id(self) -> Optional[str]:
        """
        获取用户ID
        
        Returns:
            用户ID字符串，如果不存在则返回None
        """
        user_id = self.config.get('user_id')
        
        if user_id and self._validate_uuid(user_id):
            return user_id
        
        return None
    
    def set_user_id(self, user_id: str) -> None:
        """
        设置用户ID
        
        Args:
            user_id: UUID格式的用户ID
            
        Raises:
            ValueError: 如果user_id不是有效的UUID格式
        """
        if not self._validate_uuid(user_id):
            raise ValueError(f"Invalid UUID format: {user_id}")
        
        self.config['user_id'] = user_id
        self._save_config()
        
        logger.info(f"User ID set: {user_id}")
    
    def get_or_create_user_id(self) -> str:
        """
        获取或创建用户ID
        如果用户ID不存在或无效，则生成新的UUID
        
        Returns:
            UUID格式的用户ID
        """
        user_id = self.get_user_id()
        
        if user_id:
            logger.debug(f"Using existing user_id: {user_id}")
            return user_id
        
        # 生成新的UUID
        user_id = str(uuid.uuid4())
        self.set_user_id(user_id)
        
        logger.info(f"Generated new user_id: {user_id}")
        return user_id
    
    def _validate_uuid(self, user_id: str) -> bool:
        """
        验证UUID格式
        
        Args:
            user_id: 要验证的UUID字符串
            
        Returns:
            True if valid, False otherwise
        """
        try:
            uuid.UUID(user_id, version=4)
            return True
        except (ValueError, AttributeError, TypeError):
            return False
    
    def get_skipped_versions(self) -> List[str]:
        """
        获取跳过的版本列表
        
        Returns:
            版本号字符串列表
        """
        return self.config.get('skipped_versions', [])
    
    def add_skipped_version(self, version: str) -> None:
        """
        添加跳过的版本
        
        Args:
            version: 要跳过的版本号
        """
        skipped_versions = self.get_skipped_versions()
        
        if version not in skipped_versions:
            skipped_versions.append(version)
            self.config['skipped_versions'] = skipped_versions
            self._save_config()
            
            logger.info(f"Version {version} added to skipped list")
        else:
            logger.debug(f"Version {version} already in skipped list")
    
    def remove_skipped_version(self, version: str) -> bool:
        """
        移除跳过的版本
        
        Args:
            version: 要移除的版本号
            
        Returns:
            True if removed, False if not found
        """
        skipped_versions = self.get_skipped_versions()
        
        if version in skipped_versions:
            skipped_versions.remove(version)
            self.config['skipped_versions'] = skipped_versions
            self._save_config()
            
            logger.info(f"Version {version} removed from skipped list")
            return True
        
        logger.debug(f"Version {version} not found in skipped list")
        return False
    
    def clear_skipped_versions(self) -> None:
        """清空跳过的版本列表"""
        self.config['skipped_versions'] = []
        self._save_config()
        
        logger.info("Skipped versions list cleared")
    
    def is_version_skipped(self, version: str) -> bool:
        """
        检查版本是否已跳过
        
        Args:
            version: 版本号
            
        Returns:
            True if skipped, False otherwise
        """
        return version in self.get_skipped_versions()
    
    def get_pending_events(self) -> List[Dict[str, Any]]:
        """
        获取待上报的事件列表
        
        Returns:
            事件字典列表
        """
        return self.config.get('pending_events', [])
    
    def add_pending_event(self, event: Dict[str, Any]) -> None:
        """
        添加待上报的事件
        
        Args:
            event: 事件数据字典
        """
        # 添加时间戳（如果没有）
        if 'timestamp' not in event:
            event['timestamp'] = datetime.now().isoformat()
        
        pending_events = self.get_pending_events()
        pending_events.append(event)
        
        # 限制队列大小（最多保留配置的最大值）
        if len(pending_events) > CONFIG_PENDING_EVENTS_MAX_SIZE:
            pending_events = pending_events[-CONFIG_PENDING_EVENTS_MAX_SIZE:]
            logger.warning(f"Pending events queue exceeded {CONFIG_PENDING_EVENTS_MAX_SIZE}, keeping only the latest {CONFIG_PENDING_EVENTS_MAX_SIZE}")
        
        self.config['pending_events'] = pending_events
        self._save_config()
        
        logger.debug(f"Event added to pending queue (total: {len(pending_events)})")
    
    def clear_pending_events(self) -> int:
        """
        清空待上报的事件队列
        
        Returns:
            清空的事件数量
        """
        count = len(self.get_pending_events())
        self.config['pending_events'] = []
        self._save_config()
        
        logger.info(f"Cleared {count} pending events")
        return count
    
    def remove_pending_events(self, indices: List[int]) -> int:
        """
        移除指定索引的待上报事件
        
        Args:
            indices: 要移除的事件索引列表
            
        Returns:
            实际移除的事件数量
        """
        pending_events = self.get_pending_events()
        
        # 按降序排序索引，从后往前删除，避免索引变化
        sorted_indices = sorted(set(indices), reverse=True)
        removed_count = 0
        
        for idx in sorted_indices:
            if 0 <= idx < len(pending_events):
                pending_events.pop(idx)
                removed_count += 1
        
        self.config['pending_events'] = pending_events
        self._save_config()
        
        logger.info(f"Removed {removed_count} pending events")
        return removed_count
    
    def get_config_value(self, key: str, default: Any = None) -> Any:
        """
        获取配置值
        
        Args:
            key: 配置键
            default: 默认值
            
        Returns:
            配置值，如果不存在则返回默认值
        """
        return self.config.get(key, default)
    
    def set_config_value(self, key: str, value: Any) -> None:
        """
        设置配置值
        
        Args:
            key: 配置键
            value: 配置值
        """
        self.config[key] = value
        self._save_config()
        
        logger.debug(f"Config value set: {key} = {value}")
    
    def delete_config_value(self, key: str) -> bool:
        """
        删除配置值
        
        Args:
            key: 配置键
            
        Returns:
            True if deleted, False if not found
        """
        if key in self.config:
            del self.config[key]
            self._save_config()
            
            logger.debug(f"Config value deleted: {key}")
            return True
        
        return False
    
    def get_all_config(self) -> Dict[str, Any]:
        """
        获取所有配置
        
        Returns:
            配置字典的副本
        """
        return self.config.copy()
    
    def reset_config(self) -> None:
        """重置配置为默认值"""
        self.config = self._create_default_config()
        logger.info("Config reset to default")
    
    def export_config(self, export_path: str, format: Optional[str] = None) -> None:
        """
        导出配置到文件
        
        使用 ConfigUtils 进行配置文件写入。
        
        Args:
            export_path: 导出文件路径
            format: 导出格式 ("json" 或 "yaml")，如果为None则使用当前格式
            
        Raises:
            ConfigError: 当导出失败时
        """
        if format is None:
            format = self.format
        
        export_path = Path(export_path)
        
        try:
            # 使用 ConfigUtils 写入配置（不创建备份，因为是导出操作）
            if format == "json":
                ConfigUtils.write_json(export_path, self.config, create_backup=False)
            else:  # yaml
                ConfigUtils.write_yaml(export_path, self.config, create_backup=False)
            
            logger.info(f"Config exported to {export_path}")
            
        except ConfigError:
            # ConfigUtils 已经记录了错误，直接重新抛出
            raise
    
    def import_config(self, import_path: str, merge: bool = False) -> None:
        """
        从文件导入配置
        
        使用 ConfigUtils 进行配置文件读取。
        
        Args:
            import_path: 导入文件路径
            merge: 是否合并配置（True）还是替换配置（False）
            
        Raises:
            ConfigError: 当导入失败时
            FileNotFoundError: 当导入文件不存在时
        """
        import_path = Path(import_path)
        
        if not import_path.exists():
            raise FileNotFoundError(f"Config file not found: {import_path}")
        
        try:
            # 使用 ConfigUtils 读取配置
            # 根据文件扩展名判断格式
            if import_path.suffix.lower() in ['.yaml', '.yml']:
                imported_config = ConfigUtils.read_yaml(import_path, default={})
            else:  # 默认为json
                imported_config = ConfigUtils.read_json(import_path, default={})
            
            # 确保返回的是字典
            if imported_config is None:
                imported_config = {}
            
            if merge:
                # 合并配置
                self.config.update(imported_config)
                logger.info(f"Config merged from {import_path}")
            else:
                # 替换配置
                self.config = imported_config
                logger.info(f"Config replaced from {import_path}")
            
            self._save_config()
            
        except ConfigError:
            # ConfigUtils 已经记录了错误，直接重新抛出
            raise
