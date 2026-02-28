"""
ConfigService - 统一的配置服务

封装 ConfigManager，提供简化的配置访问接口
Level 1 服务：依赖 LogService 和 PathService
"""

from typing import Dict, Any, Optional
from pathlib import Path

from core.config.config_manager import ConfigManager
from core.config.config_validator import ConfigSchema


class ConfigService:
    """统一的配置服务
    
    管理多个模块的 ConfigManager 实例，提供简化的配置访问接口
    
    特点：
    - Level 1 服务，依赖 LogService 和 PathService
    - 管理多个模块的配置
    - 线程安全（ConfigManager 内部使用锁）
    """
    
    def __init__(self):
        """初始化配置服务

        注意：使用 LogService 记录日志
        """
        # 延迟导入，避免循环依赖
        from core.services import _get_log_service

        # 配置管理器注册表：{module_name: ConfigManager}
        self._config_managers: Dict[str, ConfigManager] = {}

        # 获取 logger（通过内部 getter 函数）
        log_service_instance = _get_log_service()
        self._logger = log_service_instance.get_logger("config_service")
        self._logger.info("ConfigService 初始化完成")

    @staticmethod
    def _get_default_schema(module_name: str) -> Optional[ConfigSchema]:
        """获取模块默认配置 schema（仅用于补齐基础字段白名单）"""
        if module_name != "app":
            return None

        return ConfigSchema(
            required_fields={"_version"},
            optional_fields={
                "application",
                "window",
                "performance",
                "window_state",
                "close_action_preference",
                "debug_services",
            },
            field_types={"_version": str},
            allow_unknown_fields=True,
            strict_mode=False,
        )
    
    def _get_or_create_manager(
        self,
        module_name: str,
        template_path: Optional[Path] = None
    ) -> ConfigManager:
        """获取或创建 ConfigManager 实例
        
        Args:
            module_name: 模块名称
            template_path: 配置模板路径（可选）
            
        Returns:
            ConfigManager 实例
        """
        resolved_template_path = template_path

        # app 配置模板有固定位置，调用方未传时自动补齐，避免出现 template_path=None 的告警。
        if resolved_template_path is None and module_name == "app":
            default_app_template = Path(__file__).resolve().parent.parent / "config_templates" / "app_config_template.json"
            if default_app_template.exists():
                resolved_template_path = default_app_template

        if module_name not in self._config_managers:
            self._logger.debug(f"创建新的 ConfigManager: {module_name}")
            self._config_managers[module_name] = ConfigManager(
                module_name=module_name,
                template_path=resolved_template_path,
                config_schema=self._get_default_schema(module_name),
            )

        manager = self._config_managers[module_name]

        # 兼容旧调用顺序：如果实例先被无模板创建，后续允许补齐模板路径。
        if manager.template_path is None and resolved_template_path is not None:
            manager.template_path = resolved_template_path
            self._logger.debug(f"模块 {module_name} 的模板路径已补齐: {resolved_template_path}")

        return manager
    
    def get_module_config(
        self,
        module_name: str,
        template_path: Optional[Path] = None,
        force_reload: bool = False
    ) -> Dict[str, Any]:
        """获取模块配置
        
        Args:
            module_name: 模块名称
            template_path: 配置模板路径（可选，首次创建时需要）
            force_reload: 是否强制重新加载
            
        Returns:
            模块配置字典
            
        Example:
            config = config_service.get_module_config(
                "asset_manager",
                template_path=Path("core/config_templates/asset_manager_config.json")
            )
        """
        manager = self._get_or_create_manager(module_name, template_path)
        return manager.get_module_config(force_reload=force_reload)
    
    def save_module_config(
        self,
        module_name: str,
        config: Dict[str, Any],
        backup_reason: str = "manual_save"
    ) -> bool:
        """保存模块配置
        
        Args:
            module_name: 模块名称
            config: 配置字典
            backup_reason: 备份原因
            
        Returns:
            是否保存成功
            
        Example:
            success = config_service.save_module_config(
                "asset_manager",
                {"max_items": 200}
            )
        """
        if module_name not in self._config_managers:
            self._logger.error(f"模块 {module_name} 的 ConfigManager 不存在")
            return False
        
        manager = self._config_managers[module_name]
        return manager.save_user_config(config, backup_reason=backup_reason)
    
    def update_config_value(
        self,
        module_name: str,
        key: str,
        value: Any,
        template_path: Optional[Path] = None
    ) -> bool:
        """更新配置值
        
        Args:
            module_name: 模块名称
            key: 配置键（支持点号分隔，如 "database.host"）
            value: 配置值
            template_path: 配置模板路径（可选，首次创建时需要）
            
        Returns:
            是否更新成功
            
        Example:
            success = config_service.update_config_value(
                "asset_manager",
                "settings.max_items",
                200
            )
        """
        manager = self._get_or_create_manager(module_name, template_path)
        return manager.update_config_value(key, value)
    
    def clear_cache(self, module_name: Optional[str] = None) -> None:
        """清除配置缓存
        
        Args:
            module_name: 模块名称，如果为 None 则清除所有模块的缓存
            
        Example:
            # 清除特定模块的缓存
            config_service.clear_cache("asset_manager")
            
            # 清除所有模块的缓存
            config_service.clear_cache()
        """
        if module_name is None:
            # 清除所有模块的缓存
            for manager in self._config_managers.values():
                manager.clear_cache()
            self._logger.info("已清除所有模块的配置缓存")
        elif module_name in self._config_managers:
            # 清除特定模块的缓存
            self._config_managers[module_name].clear_cache()
            self._logger.info(f"已清除模块 {module_name} 的配置缓存")
        else:
            self._logger.warning(f"模块 {module_name} 的 ConfigManager 不存在")
