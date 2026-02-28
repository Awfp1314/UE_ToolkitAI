# -*- coding: utf-8 -*-

"""
缩略图管理模块

从 AssetScanner 提取的缩略图相关逻辑，
包括缩略图查找、恢复、迁移等功能。
不包含 Qt 信号和 UI 依赖。
"""

import shutil
import logging
from pathlib import Path
from typing import Optional


class ThumbnailManager:
    """缩略图管理类

    负责缩略图的查找、恢复和迁移操作。
    不包含 Qt 信号、配置持久化逻辑。

    Attributes:
        logger: 日志记录器
    """

    def __init__(self, logger: logging.Logger):
        self.logger = logger

    def find_thumbnail_by_asset_id(
        self,
        asset_id: Optional[str],
        thumbnails_dir: Optional[Path]
    ) -> Optional[Path]:
        """根据资产ID在缩略图目录中查找缩略图

        Args:
            asset_id: 资产ID
            thumbnails_dir: 缩略图目录路径

        Returns:
            如果找到缩略图返回Path对象，否则返回None
        """
        if not asset_id or not thumbnails_dir or not thumbnails_dir.exists():
            return None

        try:
            thumbnail_path = thumbnails_dir / f"{asset_id}.png"
            if thumbnail_path.exists():
                self.logger.debug(f"找到了缩略图文件: {thumbnail_path}")
                return thumbnail_path

            self.logger.debug(f"缩略图不存在: {thumbnail_path}")
            return None

        except Exception as e:
            self.logger.warning(f"查找缩略图失败 (asset_id: {asset_id}): {e}")
            return None

    def find_existing_thumbnail_for_new_asset(
        self,
        asset_path: Path,
        thumbnails_dir: Optional[Path]
    ) -> Optional[Path]:
        """为新资产查找已存在的缩略图文件

        Args:
            asset_path: 资产路径
            thumbnails_dir: 缩略图目录路径

        Returns:
            如果找到返回缩略图路径，否则返回None
        """
        if not thumbnails_dir or not thumbnails_dir.exists():
            return None

        try:
            return None
        except Exception as e:
            self.logger.debug(f"查找已存在缩略图失败: {e}")
            return None

    def restore_thumbnail_from_asset(
        self,
        asset_path: Path,
        asset_id: Optional[str],
        thumbnails_dir: Optional[Path]
    ) -> Optional[Path]:
        """从资产包内的preview.png恢复缩略图

        Args:
            asset_path: 资产路径
            asset_id: 资产ID
            thumbnails_dir: 缩略图目录路径

        Returns:
            如果成功复制返回新的缩略图路径，否则返回None
        """
        if not asset_id or not thumbnails_dir:
            return None

        try:
            preview_path = None
            if asset_path.is_dir():
                potential_preview = asset_path / "preview.png"
                if potential_preview.exists():
                    preview_path = potential_preview

            if not preview_path:
                return None

            if not thumbnails_dir.exists():
                thumbnails_dir.mkdir(parents=True, exist_ok=True)

            thumbnail_path = thumbnails_dir / f"{asset_id}.png"
            shutil.copy2(preview_path, thumbnail_path)
            self.logger.info(f"📋 从资产包复制缩略图: {asset_path.name}/preview.png")

            return thumbnail_path

        except Exception as e:
            self.logger.debug(f"从资产包恢复缩略图失败: {e}")
            return None

    def migrate_thumbnails_and_docs(self) -> None:
        """迁移缩略图和文档到本地目录

        此方法现在只用于日志记录，实际目录创建发生在需要时：
        - 缩略图目录在生成缩略图时创建
        - 文档目录在创建资产文档时创建
        """
        self.logger.debug("本地缩略图和文档目录已准备好（实际创建将在需要时进行）")
