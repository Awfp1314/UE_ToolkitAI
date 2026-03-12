# -*- coding: utf-8 -*-

"""
资产控制器

从 AssetManagerUI 提取的业务逻辑，负责资产过滤、搜索、排序和选择逻辑。
UI 层通过此控制器获取处理后的资产数据，而非直接操作 logic 层。
"""

from typing import List, Optional, Dict, Any
from core.logger import get_logger

logger = get_logger(__name__)


class AssetController:
    """资产控制器 - 管理资产过滤、搜索、排序的业务逻辑
    
    将 AssetManagerUI 中的业务逻辑提取到此类，
    UI 层只负责展示和事件处理，业务逻辑由控制器处理。
    """

    def __init__(self, logic):
        """初始化资产控制器
        
        Args:
            logic: AssetManagerLogic 实例，提供底层资产操作
        """
        self.logic = logic
        self._search_text: str = ""
        self._selected_category: Optional[str] = None
        self._sort_method: str = "添加时间（最新）"

    @property
    def search_text(self) -> str:
        """当前搜索文本"""
        return self._search_text

    @property
    def selected_category(self) -> Optional[str]:
        """当前选中的分类（None 表示全部）"""
        return self._selected_category

    @property
    def sort_method(self) -> str:
        """当前排序方式"""
        return self._sort_method

    def set_search_text(self, text: str) -> None:
        """设置搜索文本
        
        Args:
            text: 搜索文本（会自动 strip）
        """
        self._search_text = text.strip()

    def set_category(self, category: str) -> None:
        """设置分类过滤
        
        Args:
            category: 分类名称，"全部分类" 表示不过滤
        """
        self._selected_category = None if category == "全部分类" else category

    def set_sort_method(self, sort_method: str) -> None:
        """设置排序方式
        
        Args:
            sort_method: 排序方式名称
        """
        self._sort_method = sort_method

    def get_filtered_assets(self) -> list:
        """根据当前搜索、分类、排序状态获取过滤后的资产列表
        
        Returns:
            过滤并排序后的资产列表
        """
        if not self.logic:
            return []

        try:
            if self._search_text:
                matched_assets = self.logic.search_assets(
                    self._search_text, category=self._selected_category
                )
                logger.debug(
                    f"搜索 '{self._search_text}' "
                    f"(分类: {self._selected_category or '全部'}) "
                    f"找到 {len(matched_assets)} 个资产"
                )
            else:
                if self._selected_category:
                    matched_assets = self.logic.get_all_assets(
                        category=self._selected_category
                    )
                    logger.debug(
                        f"筛选分类 '{self._selected_category}' "
                        f"找到 {len(matched_assets)} 个资产"
                    )
                else:
                    matched_assets = self.logic.assets
                    logger.debug("显示全部资产")

            if matched_assets and self._sort_method:
                matched_assets = self.logic.sort_assets(
                    matched_assets, self._sort_method
                )
                logger.debug(f"应用排序: {self._sort_method}")

            return matched_assets

        except Exception as e:
            logger.error(f"获取过滤资产失败: {e}", exc_info=True)
            return []

    def get_categories(self) -> List[str]:
        """获取所有分类列表
        
        Returns:
            分类名称列表
        """
        if not self.logic:
            return []
        try:
            return self.logic.get_all_categories()
        except Exception as e:
            logger.error(f"获取分类失败: {e}", exc_info=True)
            return []

    def find_asset_by_name(self, name: str):
        """通过名称查找资产
        
        Args:
            name: 资产名称
            
        Returns:
            匹配的 Asset 对象，未找到返回 None
        """
        if not self.logic:
            return None
        for asset in self.logic.assets:
            if asset.name == name:
                return asset
        return None

    def find_asset_by_id(self, asset_id: str):
        """通过 ID 查找资产
        
        Args:
            asset_id: 资产 ID
            
        Returns:
            匹配的 Asset 对象，未找到返回 None
        """
        if not self.logic:
            return None
        for asset in self.logic.assets:
            if asset.id == asset_id:
                return asset
        return None

    def get_existing_asset_names(self) -> List[str]:
        """获取所有已有资产名称列表
        
        Returns:
            资产名称列表
        """
        if not self.logic:
            return []
        return [asset.name for asset in self.logic.get_all_assets()]

    def get_existing_categories_list(self) -> List[str]:
        """获取已有分类列表（用于对话框）
        
        Returns:
            分类列表，确保包含"默认分类"
        """
        if not self.logic:
            return ["默认分类"]
        categories = list(set(
            asset.category for asset in self.logic.get_all_assets() if asset.category
        ))
        if "默认分类" not in categories:
            categories.insert(0, "默认分类")
        return categories

    def convert_asset_to_dict(self, asset) -> Dict[str, Any]:
        """将 Asset 对象转换为字典格式
        
        Args:
            asset: Asset 对象
            
        Returns:
            资产数据字典
        """
        return {
            'id': asset.id,
            'name': asset.name,
            'category': asset.category,
            'size': asset.size,
            'path': str(asset.path) if asset.path else None,
            'thumbnail_path': str(asset.thumbnail_path) if asset.thumbnail_path else None,
            'asset_type': (
                asset.asset_type.value
                if hasattr(asset.asset_type, 'value')
                else str(asset.asset_type)
            ),
            'created_time': (
                asset.created_time.isoformat()
                if hasattr(asset.created_time, 'isoformat')
                else str(asset.created_time)
            ),
            'has_document': False,
        }

    def check_asset_has_document(self, asset_id: str) -> bool:
        """检查资产是否有文档
        
        Args:
            asset_id: 资产 ID
            
        Returns:
            是否有文档
        """
        if not self.logic or not asset_id:
            return False
        library_path = self.logic.get_asset_library_path()
        if not library_path:
            return False
        doc_path_txt = library_path / '.asset_config' / 'documents' / f'{asset_id}.txt'
        doc_path_md = library_path / '.asset_config' / 'documents' / f'{asset_id}.md'
        return doc_path_txt.exists() or doc_path_md.exists()

    def load_ui_state(self, key: str, default=None):
        """从 app_config.ui_states.asset_manager 读取指定字段"""
        try:
            from core.services import config_service
            app_config = config_service.get_module_config("app") or {}
            return app_config.get("ui_states", {}).get("asset_manager", {}).get(key, default)
        except Exception as e:
            logger.warning(f"读取 ui_state[{key}] 失败: {e}")
            return default

    def save_ui_state(self, key: str, value) -> None:
        """保存指定字段到 app_config.ui_states.asset_manager"""
        try:
            from core.services import config_service
            app_config = config_service.get_module_config("app") or {}
            ui_states = app_config.setdefault("ui_states", {})
            am_state = ui_states.setdefault("asset_manager", {})
            am_state[key] = value
            config_service.save_module_config("app", app_config)
        except Exception as e:
            logger.warning(f"保存 ui_state[{key}] 失败: {e}")

    def load_view_mode(self) -> str:
        """从 app_config.ui_states.asset_manager 加载视图模式
        
        Returns:
            视图模式 ("detailed" 或 "compact")
        """
        try:
            from core.services import config_service
            app_config = config_service.get_module_config("app") or {}
            view_mode = app_config.get("ui_states", {}).get("asset_manager", {}).get("view_mode", "")
            if view_mode:
                logger.info(f"从 app_config.ui_states 加载视图模式: {view_mode}")
                return view_mode
        except Exception as e:
            logger.warning(f"从 app_config 加载视图模式失败: {e}")
        # 兼容旧配置（asset_manager_config.view_mode）
        try:
            if self.logic and self.logic.config_manager:
                config = self.logic.config_manager.load_user_config()
                view_mode = config.get("view_mode", "")
                if view_mode:
                    logger.info(f"从旧配置字段加载视图模式: {view_mode}")
                    return view_mode
        except Exception:
            pass
        return "detailed"

    def save_view_mode(self, view_mode: str) -> None:
        """保存视图模式到 app_config.ui_states.asset_manager
        
        Args:
            view_mode: 视图模式 ("detailed" 或 "compact")
        """
        try:
            from core.services import config_service
            app_config = config_service.get_module_config("app") or {}
            ui_states = app_config.setdefault("ui_states", {})
            am_state = ui_states.setdefault("asset_manager", {})
            am_state["view_mode"] = view_mode
            config_service.save_module_config("app", app_config)
            logger.debug(f"视图模式已保存到 app_config.ui_states: {view_mode}")
        except Exception as e:
            logger.warning(f"保存视图模式失败: {e}")
