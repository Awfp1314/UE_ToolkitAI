# -*- coding: utf-8 -*-

"""
更新检测器模块
负责检查程序更新、管理用户标识符和上报启动统计
"""

import os
import uuid
import platform
import requests
import yaml
from pathlib import Path
from typing import Optional, Dict, Any, List
from datetime import datetime

from core.logger import get_logger
from core.utils.config_utils import ConfigUtils
from core.exceptions import ConfigError

# 导入版本信息
try:
    from version import get_version
    DEFAULT_VERSION = get_version()
except ImportError:
    # 如果无法导入，使用默认值
    DEFAULT_VERSION = "1.2.0"

logger = get_logger(__name__)

# 创建绕过系统代理的 requests Session（避免用户开代理导致请求失败）
_no_proxy_session = requests.Session()
_no_proxy_session.trust_env = False
_no_proxy_session.proxies = {"http": None, "https": None}


class UpdateChecker:
    """更新检测器类"""
    
    def __init__(self, config_path: Optional[str] = None, current_version: Optional[str] = None):
        """
        初始化更新检测器
        
        Args:
            config_path: 配置文件路径，默认为用户目录下的隐藏配置文件
            current_version: 当前程序版本号，如果不提供则从 version.py 读取
        """
        # 优先使用 version.py 中的版本号
        if current_version is None:
            current_version = DEFAULT_VERSION
        
        self.current_version = self._normalize_version(current_version)
        
        # 设置配置文件路径
        if config_path is None:
            user_home = Path.home()
            config_dir = user_home / ".ue_toolkit"
            config_dir.mkdir(exist_ok=True)
            self.config_path = config_dir / "update_config.json"
        else:
            self.config_path = Path(config_path)
        
        # 加载系统配置（从YAML文件）
        self._load_system_config()
        
        # 加载用户配置
        self.config = self._load_config()
        
        logger.info(f"UpdateChecker initialized with version {self.current_version}, API: {self.api_base_url}")
    
    def _normalize_version(self, version: str) -> str:
        """
        规范化版本号格式
        
        Args:
            version: 版本号字符串（如 "1.3" 或 "v1.3.0"）
            
        Returns:
            规范化的版本号（如 "v1.3.0"）
        """
        # 移除 'v' 前缀
        version = version.lstrip('v')
        
        # 分割版本号
        parts = version.split('.')
        
        # 补齐到三位
        while len(parts) < 3:
            parts.append('0')
        
        # 返回带 'v' 前缀的版本号
        return f"v{'.'.join(parts[:3])}"
    
    def _load_system_config(self) -> None:
        """
        加载系统配置（从YAML文件）
        注意：版本号现在从 version.py 读取，不再从配置文件读取
        """
        try:
            # 获取项目根目录
            project_root = Path(__file__).parent.parent
            system_config_path = project_root / "config" / "update_config.yaml"
            
            if system_config_path.exists():
                with open(system_config_path, 'r', encoding='utf-8') as f:
                    system_config = yaml.safe_load(f)
                
                # 设置API配置
                api_config = system_config.get('api', {})
                self.timeout = api_config.get('timeout', 8)
                
                # 使用自动降级的服务器地址
                from core.server_config import get_api_base_url
                self.api_base_url = get_api_base_url()
                
                # 注意：不再从配置文件读取版本号，版本号由 version.py 统一管理
                
                logger.debug(f"System config loaded from {system_config_path}")
            else:
                # 使用默认配置
                self.timeout = 8
                from core.server_config import get_api_base_url
                self.api_base_url = get_api_base_url()
                
        except Exception as e:
            # 使用默认配置
            self.timeout = 8
            from core.server_config import get_api_base_url
            self.api_base_url = get_api_base_url()
    
    def _load_config(self) -> Dict[str, Any]:
        """
        加载配置文件
        
        Returns:
            配置字典
        """
        if self.config_path.exists():
            try:
                config = ConfigUtils.read_json(self.config_path, default=None)
                if config is None:
                    return self._create_default_config()
                logger.debug(f"Config loaded from {self.config_path}")
                return config
            except ConfigError as e:
                logger.error(f"Failed to load config: {e}")
                return self._create_default_config()
            except Exception as e:
                logger.error(f"Failed to load config: {e}")
                return self._create_default_config()
        else:
            return self._create_default_config()
    
    def _create_default_config(self) -> Dict[str, Any]:
        """
        创建默认配置
        
        Returns:
            默认配置字典
        """
        config = {
            "user_id": None,
            "skipped_versions": [],
            "pending_events": [],
            "last_check": None
        }
        self._save_config(config)
        return config
    
    def _save_config(self, config: Optional[Dict[str, Any]] = None) -> None:
        """
        保存配置到文件
        
        Args:
            config: 要保存的配置字典，如果为None则保存当前配置
        """
        if config is None:
            config = self.config
        
        try:
            self.config_path.parent.mkdir(parents=True, exist_ok=True)
            ConfigUtils.write_json(self.config_path, config, create_backup=False, indent=2)
            logger.debug(f"Config saved to {self.config_path}")
        except ConfigError as e:
            logger.error(f"Failed to save config: {e}")
        except Exception as e:
            logger.error(f"Failed to save config: {e}")
    
    def check_for_updates(self) -> Optional[Dict[str, Any]]:
        """
        检查更新
        
        Returns:
            如果有新版本，返回版本信息字典；否则返回None
            版本信息包含: version, changelog_summary, changelog_full, force_update, release_date, download_links
        """
        try:
            logger.info("Checking for updates...")
            
            # 调用新的统一版本API
            url = f"{self.api_base_url}/versions/current"
            response = _no_proxy_session.get(url, timeout=self.timeout)
            
            if response.status_code == 200:
                data = response.json()
                
                # 检查是否为错误响应
                if data.get('error'):
                    logger.warning(f"API returned error: {data.get('message', 'Unknown error')}")
                    return None
                
                # 兼容两种响应格式：
                # 格式1（旧）: {"success": true, "version": {...}}
                # 格式2（当前）: {"version": "1.0.0", "changelog_summary": ..., ...}
                if data.get('success') and isinstance(data.get('version'), dict):
                    version_info = data['version']
                elif 'version' in data and isinstance(data['version'], str):
                    # 服务端直接返回版本对象，version 字段是字符串
                    version_info = data
                else:
                    logger.warning(f"Unexpected API response format: {list(data.keys())}")
                    return None
                
                latest_version = version_info.get('version', '')
                
                logger.info(f"Latest version: {latest_version}, Current version: {self.current_version}")
                
                # 比较版本号
                if self._compare_versions(latest_version, self.current_version) > 0:
                    logger.info(f"New version available: {latest_version}")
                    
                    # 如果响应中没有 download_links，尝试单独获取
                    if not version_info.get('download_links'):
                        download_links = self._get_download_links()
                        if download_links:
                            version_info['download_links'] = download_links
                    
                    # 更新最后检查时间
                    self.config['last_check'] = datetime.now().isoformat()
                    self._save_config()
                    
                    return version_info
                else:
                    logger.info("Already using the latest version")
                    return None
            else:
                logger.warning(f"Failed to check updates: HTTP {response.status_code}")
                return None
                
        except requests.Timeout:
            logger.warning("Update check timed out")
            return None
        except requests.RequestException as e:
            logger.warning(f"Network error during update check: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error during update check: {e}")
            return None
    
    def _get_download_links(self) -> List[Dict[str, Any]]:
        """
        获取当前版本的下载链接
        
        Returns:
            下载链接列表
        """
        try:
            url = f"{self.api_base_url}/downloads/current"
            response = _no_proxy_session.get(url, timeout=self.timeout)
            
            if response.status_code == 200:
                data = response.json()
                if data.get('success'):
                    return data.get('links', [])
            
            return []
        except Exception as e:
            logger.warning(f"Failed to get download links: {e}")
            return []
    
    def _compare_versions(self, v1: str, v2: str) -> int:
        """
        比较两个版本号
        
        Args:
            v1: 版本号1
            v2: 版本号2
            
        Returns:
            -1 if v1 < v2
             0 if v1 == v2
             1 if v1 > v2
        """
        # 规范化版本号
        v1 = self._normalize_version(v1)
        v2 = self._normalize_version(v2)
        
        # 移除 'v' 前缀并分割
        parts1 = [int(x) for x in v1.lstrip('v').split('.')]
        parts2 = [int(x) for x in v2.lstrip('v').split('.')]
        
        # 逐位比较
        for p1, p2 in zip(parts1, parts2):
            if p1 < p2:
                return -1
            elif p1 > p2:
                return 1
        
        return 0
    
    def get_or_create_user_id(self) -> str:
        """
        获取或创建用户标识符
        
        Returns:
            UUID格式的用户标识符
        """
        user_id = self.config.get('user_id')
        
        if user_id and self._validate_uuid(user_id):
            logger.debug(f"Using existing user_id: {user_id}")
            return user_id
        
        # 生成新的UUID
        user_id = str(uuid.uuid4())
        self.config['user_id'] = user_id
        self._save_config()
        
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
        except (ValueError, AttributeError):
            return False
    
    def report_launch(self, user_id: Optional[str] = None) -> bool:
        """
        上报启动事件
        
        Args:
            user_id: 用户标识符，如果为None则自动获取
            
        Returns:
            True if successful, False otherwise
        """
        if user_id is None:
            user_id = self.get_or_create_user_id()
        
        # 获取平台信息
        platform_name = self._get_platform()
        
        # 构建上报数据
        launch_data = {
            "user_id": user_id,
            "client_version": self.current_version,
            "platform": platform_name
        }
        
        try:
            logger.info(f"Reporting launch event for user {user_id}")
            
            # 调用API上报
            url = f"{self.api_base_url}/analytics/launch"
            response = _no_proxy_session.post(url, json=launch_data, timeout=self.timeout)
            
            if response.status_code == 200:
                logger.info("Launch event reported successfully")
                
                # 尝试上报待上报的事件
                self._report_pending_events()
                
                return True
            else:
                logger.warning(f"Failed to report launch: HTTP {response.status_code}")
                self._add_pending_event(launch_data)
                return False
                
        except requests.Timeout:
            logger.warning("Launch report timed out")
            self._add_pending_event(launch_data)
            return False
        except requests.RequestException as e:
            logger.warning(f"Network error during launch report: {e}")
            self._add_pending_event(launch_data)
            return False
        except Exception as e:
            logger.error(f"Unexpected error during launch report: {e}")
            return False
    
    def _get_platform(self) -> str:
        """
        获取操作系统平台信息
        
        Returns:
            平台名称 (Windows/macOS/Linux)
        """
        system = platform.system()
        if system == "Windows":
            return "Windows"
        elif system == "Darwin":
            return "macOS"
        elif system == "Linux":
            return "Linux"
        else:
            return system
    
    def _add_pending_event(self, event_data: Dict[str, Any]) -> None:
        """
        添加待上报事件到队列
        
        Args:
            event_data: 事件数据
        """
        # 添加时间戳
        event_data['timestamp'] = datetime.now().isoformat()
        
        # 添加到待上报队列
        pending_events = self.config.get('pending_events', [])
        pending_events.append(event_data)
        
        # 限制队列大小（最多保留100个）
        if len(pending_events) > 100:
            pending_events = pending_events[-100:]
        
        self.config['pending_events'] = pending_events
        self._save_config()
        
        logger.debug(f"Added event to pending queue (total: {len(pending_events)})")
    
    def _report_pending_events(self) -> None:
        """批量上报待上报的事件"""
        pending_events = self.config.get('pending_events', [])
        
        if not pending_events:
            return
        
        logger.info(f"Attempting to report {len(pending_events)} pending events")
        
        successful_count = 0
        failed_events = []
        
        for event in pending_events:
            try:
                # 移除时间戳字段（API不需要）
                event_data = {k: v for k, v in event.items() if k != 'timestamp'}
                
                url = f"{self.api_base_url}/analytics/launch"
                response = _no_proxy_session.post(url, json=event_data, timeout=self.timeout)
                
                if response.status_code == 200:
                    successful_count += 1
                else:
                    failed_events.append(event)
            except Exception as e:
                logger.debug(f"Failed to report pending event: {e}")
                failed_events.append(event)
        
        # 更新待上报队列
        self.config['pending_events'] = failed_events
        self._save_config()
        
        if successful_count > 0:
            logger.info(f"Successfully reported {successful_count} pending events")
    
    def should_show_update(self, latest_version: str) -> bool:
        """
        检查是否应该显示更新提示
        
        Args:
            latest_version: 最新版本号
            
        Returns:
            True if should show, False if skipped
        """
        skipped_versions = self.config.get('skipped_versions', [])
        normalized_version = self._normalize_version(latest_version)
        
        is_skipped = normalized_version in skipped_versions
        
        if is_skipped:
            logger.info(f"Version {normalized_version} has been skipped")
        
        return not is_skipped
    
    def skip_version(self, version: str) -> None:
        """
        记录跳过的版本
        
        Args:
            version: 要跳过的版本号
        """
        normalized_version = self._normalize_version(version)
        skipped_versions = self.config.get('skipped_versions', [])
        
        if normalized_version not in skipped_versions:
            skipped_versions.append(normalized_version)
            self.config['skipped_versions'] = skipped_versions
            self._save_config()
            
            logger.info(f"Version {normalized_version} marked as skipped")
    
    def clear_skipped_versions(self) -> None:
        """
        清除所有跳过的版本记录
        用于手动检查更新时重置跳过列表
        """
        self.config['skipped_versions'] = []
        self._save_config()
        logger.info("All skipped versions cleared")
    
    def remove_skipped_version(self, version: str) -> None:
        """
        移除特定的跳过版本记录
        
        Args:
            version: 要移除的版本号
        """
        normalized_version = self._normalize_version(version)
        skipped_versions = self.config.get('skipped_versions', [])
        
        if normalized_version in skipped_versions:
            skipped_versions.remove(normalized_version)
            self.config['skipped_versions'] = skipped_versions
            self._save_config()
            logger.info(f"Removed skipped version: {normalized_version}")
    
    def check_for_updates_force(self) -> Optional[Dict[str, Any]]:
        """
        强制检查更新（忽略跳过列表）
        用于用户手动点击"检查更新"按钮时
        
        Returns:
            如果有新版本，返回版本信息字典；否则返回None
        """
        try:
            logger.info("Force checking for updates (ignoring skip list)...")
            
            # 调用新的统一版本API
            url = f"{self.api_base_url}/versions/current"
            response = _no_proxy_session.get(url, timeout=self.timeout)
            
            if response.status_code == 200:
                data = response.json()
                
                # 检查是否为错误响应
                if data.get('error'):
                    logger.warning(f"API returned error: {data.get('message', 'Unknown error')}")
                    return None
                
                # 兼容两种响应格式
                if data.get('success') and isinstance(data.get('version'), dict):
                    version_info = data['version']
                elif 'version' in data and isinstance(data['version'], str):
                    version_info = data
                else:
                    logger.warning(f"Unexpected API response format: {list(data.keys())}")
                    return None
                
                latest_version = version_info.get('version', '')
                
                logger.info(f"Latest version: {latest_version}, Current version: {self.current_version}")
                
                # 比较版本号（不检查跳过列表）
                if self._compare_versions(latest_version, self.current_version) > 0:
                    logger.info(f"New version available: {latest_version}")
                    
                    # 如果响应中没有 download_links，尝试单独获取
                    if not version_info.get('download_links'):
                        download_links = self._get_download_links()
                        if download_links:
                            version_info['download_links'] = download_links
                    
                    # 更新最后检查时间
                    self.config['last_check'] = datetime.now().isoformat()
                    self._save_config()
                    
                    return version_info
                else:
                    logger.info("Already using the latest version")
                    return None
            else:
                logger.warning(f"Failed to check updates: HTTP {response.status_code}")
                return None
                
        except requests.Timeout:
            logger.warning("Update check timed out")
            return None
        except requests.RequestException as e:
            logger.warning(f"Network error during update check: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error during update check: {e}")
            return None
