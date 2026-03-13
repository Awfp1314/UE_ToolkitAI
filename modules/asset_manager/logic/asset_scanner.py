# -*- coding: utf-8 -*-

"""
资产扫描模块

从 AssetManagerLogic 提取的资产扫描逻辑，
包括目录扫描、并行扫描、缓存管理等功能。
不包含 Qt 信号和 UI 依赖。
"""

import uuid
import shutil
import logging
from pathlib import Path
from typing import List, Optional, Dict, Any, Callable, Tuple, TYPE_CHECKING
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

from .asset_model import Asset, AssetType, PackageType
from ..utils.ue_version_detector import UEVersionDetector

if TYPE_CHECKING:
    from .thumbnail_manager import ThumbnailManager


class AssetScanner:
    """资产扫描类
    
    负责扫描资产库目录，发现和加载资产。
    支持并行扫描和缓存恢复。
    不包含 Qt 信号、配置持久化逻辑。
    
    Attributes:
        logger: 日志记录器
        _thumbnail_manager: 缩略图管理器（可选）
    """

    def __init__(self, logger: logging.Logger, thumbnail_manager: Optional['ThumbnailManager'] = None):
        self.logger = logger
        self._thumbnail_manager = thumbnail_manager
        self._version_detector = UEVersionDetector(logger)

    def scan_asset_library(
        self,
        library_path: Path,
        cached_assets_data: List[Dict[str, Any]],
        categories: List[str],
        thumbnails_dir: Optional[Path] = None,
        progress_callback: Optional[Callable[[int, int, str], None]] = None,
        max_workers: int = 4
    ) -> List[Asset]:
        """扫描资产库，加载实际存在的资产（使用并行处理优化性能）
        
        Args:
            library_path: 资产库路径
            cached_assets_data: 缓存的资产数据（用于恢复元数据）
            categories: 分类列表
            thumbnails_dir: 缩略图目录路径（可选）
            progress_callback: 进度回调函数 (current, total, message)
            max_workers: 线程池最大工作线程数
            
        Returns:
            扫描到的资产列表
        """
        # 检测盘符是否改变
        current_drive = str(library_path.drive)
        cached_assets_data = self._fix_drive_letter_in_cache(cached_assets_data, current_drive)

        # 创建缓存字典，key为资产路径，value为资产数据
        cached_assets_dict: Dict[str, Dict[str, Any]] = {}
        for asset_data in cached_assets_data:
            asset_path = asset_data.get("path")
            if asset_path:
                cached_assets_dict[asset_path] = asset_data

        self.logger.info(f"开始扫描资产库: {library_path}")

        all_assets: List[Asset] = []

        # 使用线程池并行扫描分类文件夹
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {}
            for category in categories:
                category_folder = library_path / category
                if not category_folder.exists():
                    self.logger.warning(f"分类文件夹不存在: {category_folder}")
                    continue

                future = executor.submit(
                    self.scan_category_folder,
                    category_folder,
                    category,
                    cached_assets_dict,
                    thumbnails_dir
                )
                futures[future] = category

            total_categories = len(futures)
            completed_categories = 0

            for future in as_completed(futures):
                category = futures[future]
                try:
                    category_assets = future.result()
                    all_assets.extend(category_assets)

                    completed_categories += 1
                    if progress_callback:
                        progress_callback(
                            completed_categories,
                            total_categories,
                            f"已扫描分类: {category} ({len(category_assets)} 个资产)"
                        )
                    self.logger.info(
                        f"分类 '{category}' 扫描完成，找到 {len(category_assets)} 个资产"
                    )

                except PermissionError as e:
                    self.logger.error(f"扫描分类 '{category}' 失败 - 权限不足: {e}")
                except OSError as e:
                    self.logger.error(
                        f"扫描分类 '{category}' 失败 - 文件系统错误: {e}", exc_info=True
                    )
                except Exception as e:
                    self.logger.error(
                        f"扫描分类 '{category}' 失败 - 未知错误: {e}", exc_info=True
                    )

        self.logger.info(f"资产库扫描完成，共加载 {len(all_assets)} 个资产")
        return all_assets

    def scan_category_folder(
        self,
        category_folder: Path,
        category: str,
        cached_assets_dict: Dict[str, Dict[str, Any]],
        thumbnails_dir: Optional[Path] = None
    ) -> List[Asset]:
        """扫描单个分类文件夹（线程安全，不修改共享状态）
        
        Args:
            category_folder: 分类文件夹路径
            category: 分类名称
            cached_assets_dict: 缓存的资产数据字典
            thumbnails_dir: 缩略图目录路径
            
        Returns:
            该分类下的资产列表
        """
        assets: List[Asset] = []

        try:
            for item in category_folder.iterdir():
                if item.name.startswith('.'):
                    continue

                try:
                    if item.is_dir():
                        asset_type = AssetType.PACKAGE
                        file_extension = ""
                    else:
                        asset_type = AssetType.FILE
                        file_extension = item.suffix

                    item_path_str = str(item)
                    cached_data = cached_assets_dict.get(item_path_str)

                    if not cached_data:
                        self.logger.info(f"⚠️  未在缓存中找到资产: {item.name}")
                    else:
                        self.logger.info(
                            f"✅ 从缓存中找到资产: {cached_data.get('name', 'unknown')}, "
                            f"缩略图: {cached_data.get('thumbnail_path', 'None')}"
                        )

                    if cached_data:
                        asset = self._create_asset_from_cache(
                            item, cached_data, category, file_extension, thumbnails_dir
                        )
                    else:
                        asset = self._create_new_asset(
                            item, category, asset_type, file_extension, thumbnails_dir
                        )

                    assets.append(asset)

                except PermissionError as e:
                    self.logger.error(f"扫描资产失败 {item} - 权限不足: {e}")
                except OSError as e:
                    self.logger.error(
                        f"扫描资产失败 {item} - 文件系统错误: {e}", exc_info=True
                    )
                except Exception as e:
                    self.logger.error(
                        f"扫描资产失败 {item} - 未知错误: {e}", exc_info=True
                    )

        except PermissionError as e:
            self.logger.error(f"扫描分类文件夹失败 {category_folder} - 权限不足: {e}")
        except OSError as e:
            self.logger.error(
                f"扫描分类文件夹失败 {category_folder} - 文件系统错误: {e}", exc_info=True
            )
        except Exception as e:
            self.logger.error(
                f"扫描分类文件夹失败 {category_folder} - 未知错误: {e}", exc_info=True
            )

        return assets

    def _create_asset_from_cache(
        self,
        item: Path,
        cached_data: Dict[str, Any],
        category: str,
        file_extension: str,
        thumbnails_dir: Optional[Path]
    ) -> Asset:
        """从缓存数据创建资产对象
        
        Args:
            item: 资产文件/文件夹路径
            cached_data: 缓存的资产数据
            category: 分类名称
            file_extension: 文件扩展名
            thumbnails_dir: 缩略图目录路径
            
        Returns:
            Asset 对象
        """
        thumbnail_path = None

        if cached_data.get("thumbnail_path"):
            thumbnail_candidate = Path(cached_data["thumbnail_path"])
            if thumbnail_candidate.exists():
                thumbnail_path = thumbnail_candidate
                self.logger.debug(
                    f"找到有效的缩略图: {cached_data['name']} -> {thumbnail_path}"
                )
            else:
                self.logger.warning(
                    f"缩略图文件不存在（可能路径已改变），尝试在新位置查找: "
                    f"{thumbnail_candidate.name}"
                )
                thumbnail_path = self._delegate_find_thumbnail_by_asset_id(
                    cached_data.get("id"), thumbnails_dir
                )
                if thumbnail_path:
                    self.logger.info(
                        f"✅ 已自动修复缩略图路径: {cached_data['name']} -> {thumbnail_path}"
                    )
                else:
                    thumbnail_path = self._delegate_restore_thumbnail_from_asset(
                        item, cached_data.get("id"), thumbnails_dir
                    )
                    if thumbnail_path:
                        self.logger.info(f"从资产包恢复了缩略图: {cached_data['name']}")
        else:
            self.logger.info(f"缓存中无缩略图路径，尝试查找: {cached_data['name']}")
            thumbnail_path = self._delegate_find_thumbnail_by_asset_id(
                cached_data.get("id"), thumbnails_dir
            )
            if thumbnail_path:
                self.logger.info(
                    f"✅ 找到缩略图文件: {cached_data['name']} -> {thumbnail_path}"
                )
            else:
                self.logger.info(
                    f"通过asset_id未找到，尝试从资产包恢复: {cached_data['name']}"
                )
                thumbnail_path = self._delegate_restore_thumbnail_from_asset(
                    item, cached_data.get("id"), thumbnails_dir
                )
                if thumbnail_path:
                    self.logger.info(f"从资产包恢复了缩略图: {cached_data['name']}")

        # 调试：检查缓存数据
        engine_ver_from_cache = cached_data.get("engine_min_version", "NOT_IN_CACHE")
        if cached_data["name"] in ['女性基础动作包', 'BasicUI']:
            print(f"[DEBUG _restore_from_cache] {cached_data['name']}: cached engine_min_version='{engine_ver_from_cache}'")
        
        # 解析 package_type（向后兼容：旧缓存无此字段默认为 content）
        pkg_type_str = cached_data.get("package_type", "content")
        try:
            package_type = PackageType(pkg_type_str)
        except (ValueError, KeyError):
            package_type = PackageType.CONTENT

        return Asset(
            id=cached_data["id"],
            name=cached_data["name"],
            asset_type=AssetType(cached_data["asset_type"]),
            path=item,
            category=category,
            package_type=package_type,
            file_extension=cached_data.get("file_extension", file_extension),
            thumbnail_path=thumbnail_path,
            thumbnail_source=cached_data.get("thumbnail_source"),
            size=cached_data.get("size", 0),
            created_time=datetime.fromisoformat(
                cached_data.get("created_time", datetime.now().isoformat())
            ),
            description=cached_data.get("description", ""),
            engine_min_version=cached_data.get("engine_min_version", ""),
            project_file=cached_data.get("project_file", "")
        )

    def _create_new_asset(
        self,
        item: Path,
        category: str,
        asset_type: AssetType,
        file_extension: str,
        thumbnails_dir: Optional[Path]
    ) -> Asset:
        """为新发现的文件/文件夹创建资产对象
        
        Args:
            item: 资产文件/文件夹路径
            category: 分类名称
            asset_type: 资产类型
            file_extension: 文件扩展名
            thumbnails_dir: 缩略图目录路径
            
        Returns:
            Asset 对象
        """
        asset_id = str(uuid.uuid4())
        asset_name = item.stem if item.is_file() else item.name

        thumbnail_path = self._delegate_find_existing_thumbnail_for_new_asset(item, thumbnails_dir)
        if thumbnail_path:
            if thumbnails_dir:
                new_thumbnail_path = thumbnails_dir / f"{asset_id}.png"
                shutil.move(str(thumbnail_path), str(new_thumbnail_path))
                thumbnail_path = new_thumbnail_path
                self.logger.info(f"✅ 找到并关联了已存在的缩略图: {asset_name}")
            else:
                self.logger.warning(
                    f"缩略图目录未初始化，跳过缩略图关联: {asset_name}"
                )
                thumbnail_path = None
        else:
            thumbnail_path = self._delegate_restore_thumbnail_from_asset(
                item, asset_id, thumbnails_dir
            )

        # 检测引擎版本（仅影响新添加资产）
        try:
            engine_version = self._version_detector.detect_asset_min_version(item)
        except Exception as e:
            self.logger.warning(f"检测资产引擎版本失败: {asset_name} - {e}")
            engine_version = ""

        # 推断 package_type：检查包装文件夹内的子目录
        package_type = self._infer_package_type(item)

        # Others 类型且无缩略图时，尝试自动生成
        if package_type == PackageType.OTHERS and not thumbnail_path:
            thumbnail_path = self._delegate_generate_others_thumbnail(
                item, asset_id, thumbnails_dir
            )

        return Asset(
            id=asset_id,
            name=asset_name,
            asset_type=asset_type,
            path=item,
            category=category,
            package_type=package_type,
            file_extension=file_extension,
            thumbnail_path=thumbnail_path,
            thumbnail_source="screenshots" if thumbnail_path else None,
            size=self._get_size(item),
            created_time=datetime.now(),
            description="",
            engine_min_version=engine_version
        )

    def _infer_package_type(self, wrapper_path: Path) -> PackageType:
        """从包装文件夹的子目录推断 package_type
        
        检查优先级：
        1. 有 Project/ 子目录 → PROJECT
        2. 有 Plugins/ 子目录 → PLUGIN
        3. 有 Content/ 子目录 → CONTENT
        4. 有 Others/ 子目录 → OTHERS
        5. 默认 → CONTENT（向后兼容旧资产）
        
        Args:
            wrapper_path: 包装文件夹路径
            
        Returns:
            PackageType 枚举值
        """
        if not wrapper_path.is_dir():
            return PackageType.CONTENT
        
        try:
            sub_dirs = {d.name for d in wrapper_path.iterdir() if d.is_dir()}
        except OSError:
            return PackageType.CONTENT
        
        if "Project" in sub_dirs:
            return PackageType.PROJECT
        if "Plugins" in sub_dirs:
            return PackageType.PLUGIN
        if "Content" in sub_dirs:
            return PackageType.CONTENT
        if "Others" in sub_dirs:
            return PackageType.OTHERS
        
        # 默认（旧资产全部是 Content 结构）
        return PackageType.CONTENT

    def _fix_drive_letter_in_cache(
        self,
        cached_assets_data: List[Dict[str, Any]],
        current_drive: str
    ) -> List[Dict[str, Any]]:
        """修复缓存数据中的盘符（当硬盘盘符改变时）
        
        Args:
            cached_assets_data: 缓存的资产数据
            current_drive: 当前的盘符（如 "E:"）
            
        Returns:
            修复后的资产数据
        """
        if not cached_assets_data:
            return cached_assets_data

        first_asset = cached_assets_data[0] if cached_assets_data else None
        if not first_asset or not first_asset.get("path"):
            return cached_assets_data

        old_drive = Path(first_asset["path"]).drive

        if old_drive == current_drive:
            self.logger.debug(f"盘符未改变: {current_drive}")
            return cached_assets_data

        self.logger.info(
            f"🔧 检测到盘符改变: {old_drive} -> {current_drive}，开始自动修复路径..."
        )

        fixed_count = 0
        for asset_data in cached_assets_data:
            if asset_data.get("path"):
                old_path = asset_data["path"]
                new_path = old_path.replace(old_drive, current_drive, 1)
                asset_data["path"] = new_path
                fixed_count += 1

            if asset_data.get("thumbnail_path"):
                old_thumb = asset_data["thumbnail_path"]
                new_thumb = old_thumb.replace(old_drive, current_drive, 1)
                asset_data["thumbnail_path"] = new_thumb

        self.logger.info(
            f"✅ 已自动修复 {fixed_count} 个资产的路径"
            f"（盘符: {old_drive} -> {current_drive}）"
        )
        return cached_assets_data

    def _fix_library_path_in_cache(
        self,
        cached_assets_data: List[Dict[str, Any]],
        old_library_path: str,
        new_library_path: str
    ) -> List[Dict[str, Any]]:
        """修复缓存数据中的资产库路径（当资产库文件夹改名时）
        
        Args:
            cached_assets_data: 缓存的资产数据
            old_library_path: 旧的资产库路径
            new_library_path: 新的资产库路径
            
        Returns:
            修复后的资产数据
        """
        if not cached_assets_data or old_library_path == new_library_path:
            return cached_assets_data

        self.logger.info(
            f"🔧 检测到资产库路径变更: {old_library_path} -> {new_library_path}，开始自动修复路径..."
        )

        fixed_count = 0
        for asset_data in cached_assets_data:
            if asset_data.get("path"):
                old_path = asset_data["path"]
                new_path = old_path.replace(old_library_path, new_library_path, 1)
                asset_data["path"] = new_path
                fixed_count += 1

            if asset_data.get("thumbnail_path"):
                old_thumb = asset_data["thumbnail_path"]
                new_thumb = old_thumb.replace(old_library_path, new_library_path, 1)
                asset_data["thumbnail_path"] = new_thumb

        self.logger.info(
            f"✅ 已自动修复 {fixed_count} 个资产的路径"
            f"（资产库: {old_library_path} -> {new_library_path}）"
        )
        return cached_assets_data

    def _get_size(self, path: Path) -> int:
        """获取文件或文件夹的大小（字节）"""
        if path.is_file():
            return path.stat().st_size
        elif path.is_dir():
            total_size = 0
            try:
                for item in path.rglob('*'):
                    if item.is_file():
                        total_size += item.stat().st_size
            except PermissionError as e:
                self.logger.warning(f"计算文件夹大小失败 {path} - 权限不足: {e}")
            except OSError as e:
                self.logger.warning(f"计算文件夹大小失败 {path} - 文件系统错误: {e}")
            return total_size
        return 0

    def _delegate_find_thumbnail_by_asset_id(
        self,
        asset_id: Optional[str],
        thumbnails_dir: Optional[Path]
    ) -> Optional[Path]:
        """委托给 ThumbnailManager 查找缩略图"""
        if self._thumbnail_manager:
            return self._thumbnail_manager.find_thumbnail_by_asset_id(asset_id, thumbnails_dir)
        return None

    def _delegate_find_existing_thumbnail_for_new_asset(
        self,
        asset_path: Path,
        thumbnails_dir: Optional[Path]
    ) -> Optional[Path]:
        """委托给 ThumbnailManager 查找已存在缩略图"""
        if self._thumbnail_manager:
            return self._thumbnail_manager.find_existing_thumbnail_for_new_asset(asset_path, thumbnails_dir)
        return None

    def _delegate_restore_thumbnail_from_asset(
        self,
        asset_path: Path,
        asset_id: Optional[str],
        thumbnails_dir: Optional[Path]
    ) -> Optional[Path]:
        """委托给 ThumbnailManager 恢复缩略图"""
        if self._thumbnail_manager:
            return self._thumbnail_manager.restore_thumbnail_from_asset(asset_path, asset_id, thumbnails_dir)
        return None

    def _delegate_generate_others_thumbnail(
        self,
        asset_path: Path,
        asset_id: Optional[str],
        thumbnails_dir: Optional[Path]
    ) -> Optional[Path]:
        """委托给 ThumbnailManager 为 Others 类型生成缩略图"""
        if self._thumbnail_manager:
            return self._thumbnail_manager.generate_others_thumbnail(asset_path, asset_id, thumbnails_dir)
        return None
