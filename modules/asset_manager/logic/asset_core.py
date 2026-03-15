# -*- coding: utf-8 -*-

"""
资产核心 CRUD 操作模块

从 AssetManagerLogic 提取的核心资产管理操作，
包括添加、删除、获取、更新资产等功能。
不包含 Qt 信号和 UI 依赖。
"""

from pathlib import Path
from typing import List, Optional, Dict, Any
from datetime import datetime
import uuid
import logging

from .asset_model import Asset, AssetType


class AssetCore:
    """核心资产 CRUD 操作类
    
    管理资产列表和分类的内存操作。
    不包含 Qt 信号、文件 I/O 或配置持久化逻辑。
    这些由 AssetManagerLogic（门面层）负责协调。
    
    Attributes:
        assets: 资产列表
        categories: 分类列表
        logger: 日志记录器
    """

    def __init__(self, logger: logging.Logger):
        self.logger = logger
        self.assets: List[Asset] = []
        self.categories: List[str] = ["默认分类"]

    def add_asset(self, asset: Asset) -> bool:
        """将资产添加到内存列表
        
        Args:
            asset: 要添加的资产对象
            
        Returns:
            添加成功返回 True，失败返回 False
        """
        if not asset or not asset.id:
            self.logger.error("无法添加无效的资产对象")
            return False

        # 检查是否已存在相同 ID 的资产
        if self.get_asset(asset.id) is not None:
            self.logger.warning(f"资产 ID 已存在，跳过添加: {asset.id}")
            return False

        self.assets.append(asset)
        self.logger.info(f"资产已添加到列表: {asset.name} ({asset.id})")
        return True

    def remove_asset(self, asset_id: str) -> Optional[Asset]:
        """从内存列表中移除资产
        
        Args:
            asset_id: 要移除的资产 ID
            
        Returns:
            被移除的资产对象，未找到返回 None
        """
        asset = self.get_asset(asset_id)
        if not asset:
            self.logger.warning(f"未找到要移除的资产: {asset_id}")
            return None

        self.assets[:] = [a for a in self.assets if a.id != asset_id]
        self.logger.info(f"资产已从列表移除: {asset.name} ({asset_id})")
        return asset

    def get_asset(self, asset_id: str) -> Optional[Asset]:
        """根据 ID 获取资产
        
        Args:
            asset_id: 资产 ID
            
        Returns:
            匹配的资产对象，未找到返回 None
        """
        for asset in self.assets:
            if asset.id == asset_id:
                return asset
        return None

    def get_all_assets(self, category: Optional[str] = None) -> List[Asset]:
        """获取所有资产，可按分类过滤
        
        Args:
            category: 可选的分类名称过滤
            
        Returns:
            资产列表的副本
        """
        if category is None:
            return self.assets.copy()
        return [asset for asset in self.assets if asset.category == category]

    def update_asset(self, asset_id: str, name: Optional[str] = None,
                     category: Optional[str] = None,
                     description: Optional[str] = None,
                     path: Optional[str] = None) -> bool:
        """更新资产信息
        
        Args:
            asset_id: 资产 ID
            name: 新名称（可选）
            category: 新分类（可选）
            description: 新描述（可选）
            path: 新路径（可选）
            
        Returns:
            更新成功返回 True，资产不存在返回 False
        """
        asset = self.get_asset(asset_id)
        if not asset:
            self.logger.warning(f"资产不存在，无法更新: {asset_id}")
            return False

        if name is not None and name.strip():
            asset.name = name.strip()

        if category is not None and category.strip():
            asset.category = category.strip()

        if description is not None:
            asset.description = description
        
        if path is not None:
            from pathlib import Path
            asset.path = Path(path)

        self.logger.info(f"资产信息已更新: {asset.name} ({asset_id})")
        return True

    def get_all_categories(self) -> List[str]:
        """获取所有分类
        
        Returns:
            分类列表的副本
        """
        if "默认分类" not in self.categories:
            self.categories.insert(0, "默认分类")
        return self.categories.copy()

    def add_category(self, category_name: str) -> bool:
        """添加新分类
        
        Args:
            category_name: 分类名称
            
        Returns:
            添加成功返回 True，已存在或无效返回 False
        """
        if not category_name or not category_name.strip():
            return False

        category_name = category_name.strip()
        if category_name in self.categories:
            return False

        self.categories.append(category_name)
        self.logger.info(f"已添加新分类: {category_name}")
        return True

    def remove_category(self, category_name: str) -> List[Asset]:
        """移除分类，返回该分类下的资产列表
        
        不能移除默认分类。移除后，该分类下的资产会被
        标记为默认分类（由调用方处理物理移动）。
        
        Args:
            category_name: 分类名称
            
        Returns:
            该分类下的资产列表（空列表表示无资产或分类不存在）
            如果是默认分类，返回空列表且不执行移除
        """
        if category_name == "默认分类":
            self.logger.warning("不能删除默认分类")
            return []

        if category_name not in self.categories:
            return []

        # 找到该分类下的资产
        affected_assets = [a for a in self.assets if a.category == category_name]

        # 将受影响的资产移至默认分类
        for asset in affected_assets:
            asset.category = "默认分类"

        self.categories.remove(category_name)
        self.logger.info(f"已删除分类: {category_name}，{len(affected_assets)} 个资产移至默认分类")
        return affected_assets

    def clear_assets(self) -> None:
        """清空资产列表"""
        self.assets.clear()

    def get_asset_count(self) -> int:
        """获取资产总数"""
        return len(self.assets)
