# -*- coding: utf-8 -*-

"""
资产结构分析器

分析解压后的目录结构，识别 UE 资产类型并定位 Content 文件夹。
支持 7 种常见的 UE 资产压缩包内部结构。
"""

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import List, Optional

from core.logger import get_logger

logger = get_logger(__name__)

# UE 原生资产扩展名
UE_ASSET_EXTENSIONS = {'.uasset', '.umap', '.uexp', '.ubulk'}

# 原始 3D 文件扩展名
RAW_3D_EXTENSIONS = {'.fbx', '.obj', '.gltf', '.glb', '.abc', '.usd', '.usda', '.usdc'}

# 纹理文件扩展名
TEXTURE_EXTENSIONS = {'.png', '.jpg', '.jpeg', '.tga', '.bmp', '.exr', '.hdr', '.tif', '.tiff'}


class StructureType(Enum):
    """资产结构类型"""
    CONTENT_PACKAGE = "content_package"    # 包含 Content/ 文件夹的资产包（最常见）
    UE_PROJECT = "ue_project"              # 完整的 UE 项目（有 .uproject）
    UE_PLUGIN = "ue_plugin"                # UE 插件（有 .uplugin）
    LOOSE_ASSETS = "loose_assets"          # 散装 .uasset/.umap 文件
    RAW_3D_FILES = "raw_3d_files"          # 原始 3D 文件（FBX/OBJ 等）
    MIXED_FILES = "mixed_files"            # 混合文件类型
    UNKNOWN = "unknown"                    # 无法识别


@dataclass
class AnalysisResult:
    """分析结果"""
    structure_type: StructureType
    content_root: Optional[Path] = None       # Content 文件夹路径（如果找到）
    asset_root: Optional[Path] = None         # 要添加到资产库的根目录
    suggested_name: str = ""                  # 建议的资产名称
    uproject_path: Optional[Path] = None      # .uproject 文件路径（如果是完整项目）
    uplugin_path: Optional[Path] = None       # .uplugin 文件路径（如果是插件）
    ue_asset_count: int = 0                   # UE 资产文件数量
    total_file_count: int = 0                 # 总文件数量
    engine_version: str = ""                  # 引擎版本（从 .uproject/.uplugin 读取）
    description: str = ""                     # 人类可读的分析描述
    warnings: List[str] = field(default_factory=list)


class AssetStructureAnalyzer:
    """资产结构分析器
    
    扫描解压后的目录，识别其资产类型和结构，
    定位 Content 文件夹用于后续添加到资产库。
    """
    
    def analyze(self, extracted_dir: Path) -> AnalysisResult:
        """分析解压后的目录结构
        
        Args:
            extracted_dir: 解压后的根目录
            
        Returns:
            AnalysisResult: 分析结果
        """
        if not extracted_dir.exists() or not extracted_dir.is_dir():
            logger.error(f"目录不存在或不是目录: {extracted_dir}")
            return AnalysisResult(
                structure_type=StructureType.UNKNOWN,
                description="目录不存在"
            )
        
        logger.info(f"开始分析目录结构: {extracted_dir}")
        
        # 统计文件
        total_files = list(extracted_dir.rglob('*'))
        total_file_count = sum(1 for f in total_files if f.is_file())
        
        # Step 1: 优先查找 .uproject（完整 UE 项目）
        result = self._find_ue_project(extracted_dir)
        if result:
            result.total_file_count = total_file_count
            return result
        
        # Step 2: 查找 .uplugin（UE 插件）
        result = self._find_ue_plugin(extracted_dir)
        if result:
            result.total_file_count = total_file_count
            return result
        
        # Step 3: 查找所有 Content 文件夹（包含 UE 资产的）
        result = self._find_content_package(extracted_dir)
        if result:
            result.total_file_count = total_file_count
            return result
        
        # Step 4: 查找散装 .uasset/.umap 文件
        result = self._find_loose_assets(extracted_dir)
        if result:
            result.total_file_count = total_file_count
            return result
        
        # Step 5: 查找原始 3D 文件
        result = self._find_raw_3d_files(extracted_dir)
        if result:
            result.total_file_count = total_file_count
            return result
        
        # Step 6: 无法识别
        logger.warning(f"无法识别资产结构: {extracted_dir}")
        return AnalysisResult(
            structure_type=StructureType.UNKNOWN,
            total_file_count=total_file_count,
            description="无法识别资产类型，未找到 UE 资产文件或 Content 文件夹"
        )
    
    def _find_content_package(self, root: Path) -> Optional[AnalysisResult]:
        """查找包含 UE 资产的 Content 文件夹
        
        处理以下结构：
        - Type A: Content/ 直接在根目录
        - Type B: AssetName/Content/
        - Type C: ProjectName/Content/（带 .uproject）
        - Type D: 多层嵌套/.../Content/
        - Type E: 用户直接选择了 Content 文件夹本身
        
        Args:
            root: 搜索根目录
            
        Returns:
            AnalysisResult 或 None
        """
        import os
        
        # 特殊情况 1：检查 root 本身是否就是 Content 文件夹
        if root.name.lower() == 'content':
            logger.info(f"检测到用户直接选择了 Content 文件夹: {root}")
            # 检查是否包含 UE 资产
            ue_assets = []
            for ext in ('.uasset', '.umap'):
                ue_assets.extend(root.rglob(f'*{ext}'))
            
            if ue_assets:
                asset_count = len(ue_assets)
                logger.info(f"Content 文件夹包含 {asset_count} 个 UE 资产")
                return AnalysisResult(
                    structure_type=StructureType.CONTENT_PACKAGE,
                    content_root=root,
                    asset_root=root,
                    suggested_name=root.parent.name if root.parent.name else "Content",
                    ue_asset_count=asset_count,
                    description=f"UE 资产包，包含 {asset_count} 个资产文件",
                    warnings=[]
                )
        
        # 特殊情况 2：检查 root 的父目录是否是 Content
        # 例如：用户选择了 Content/MyAsset，应识别为 CONTENT 类型
        if root.parent and root.parent.name.lower() == 'content':
            logger.info(f"检测到用户选择了 Content 的子文件夹: {root}")
            # 检查是否包含 UE 资产
            ue_assets = []
            for ext in ('.uasset', '.umap'):
                ue_assets.extend(root.rglob(f'*{ext}'))
            
            if ue_assets:
                asset_count = len(ue_assets)
                logger.info(f"Content 子文件夹包含 {asset_count} 个 UE 资产")
                return AnalysisResult(
                    structure_type=StructureType.CONTENT_PACKAGE,
                    content_root=root.parent,  # Content 文件夹
                    asset_root=root.parent,    # 指向 Content
                    suggested_name=root.name,  # 使用子文件夹名称
                    ue_asset_count=asset_count,
                    description=f"UE 资产包（Content 子文件夹），包含 {asset_count} 个资产文件",
                    warnings=[]
                )
        
        # 诊断日志：列出根目录下的顶层内容
        try:
            top_items = list(root.iterdir())
            logger.info(f"解压根目录内容 ({len(top_items)} 项): {[item.name for item in top_items[:20]]}")
            for item in top_items:
                if item.is_dir():
                    sub_items = list(item.iterdir())
                    logger.info(f"  子目录 '{item.name}' 内容 ({len(sub_items)} 项): {[s.name for s in sub_items[:15]]}")
        except Exception as e:
            logger.warning(f"诊断日志失败: {e}")
        
        # 方法一：使用 os.walk 遍历（更可靠，避免 rglob 在某些情况下漏掉目录）
        content_dirs = []
        for dirpath, dirnames, filenames in os.walk(str(root)):
            for dirname in dirnames:
                if dirname.lower() == 'content':  # 大小写不敏感匹配
                    content_dirs.append(Path(dirpath) / dirname)
        
        logger.info(f"搜索到的 Content 文件夹: {content_dirs}")
        
        if not content_dirs:
            # 没有找到 Content 文件夹，尝试隐式 Content 识别
            logger.info("未找到 Content 文件夹，尝试隐式 Content 识别")
            return self._find_implicit_content_package(root)
        
        # 过滤：只保留包含 UE 资产的 Content 文件夹
        valid_contents = []
        for content_dir in content_dirs:
            ue_assets = []
            for ext in ('.uasset', '.umap'):
                ue_assets.extend(content_dir.rglob(f'*{ext}'))
            if ue_assets:
                valid_contents.append((content_dir, len(ue_assets)))
                logger.info(f"  有效 Content: {content_dir} ({len(ue_assets)} 个 UE 资产)")
            else:
                logger.info(f"  空 Content（无 UE 资产）: {content_dir}")
        
        if not valid_contents:
            # Content 文件夹存在但没有 UE 资产
            # 可能是空的或者只有其他类型文件
            # 尝试兜底逻辑：查找"隐式 Content"（没有 Content 文件夹但有 UE 资产）
            return self._find_implicit_content_package(root)
        
        # 选择最浅层级的 Content（避免嵌套误判）
        valid_contents.sort(key=lambda x: len(x[0].parts))
        best_content, asset_count = valid_contents[0]
        
        # 推断资产名称
        suggested_name = self._infer_name_from_content(best_content, root)
        
        # 确定 asset_root（Content 文件夹本身，后续需要其内容）
        logger.info(f"找到 Content 资产包: {best_content} ({asset_count} 个 UE 资产)")
        
        warnings = []
        if len(valid_contents) > 1:
            warnings.append(f"发现 {len(valid_contents)} 个 Content 文件夹，使用最浅层级的")
        
        return AnalysisResult(
            structure_type=StructureType.CONTENT_PACKAGE,
            content_root=best_content,
            asset_root=best_content,
            suggested_name=suggested_name,
            ue_asset_count=asset_count,
            description=f"UE 资产包，包含 {asset_count} 个资产文件",
            warnings=warnings
        )
    
    def _find_implicit_content_package(self, root: Path) -> Optional[AnalysisResult]:
        """查找"隐式 Content"资产包
        
        处理没有 Content 文件夹，但包含 UE 资产文件的情况。
        只有满足以下所有条件时才识别为 CONTENT_PACKAGE：
        1. 没有 Content/ 文件夹
        2. 有 .uasset 或 .umap 文件
        3. 这些文件分布在至少 1 个典型的 UE 文件夹中
        4. 没有 .uproject 或 .uplugin 文件
        
        Args:
            root: 搜索根目录
            
        Returns:
            AnalysisResult 或 None
        """
        # 典型的 UE Content 子文件夹名称（大小写不敏感）
        TYPICAL_UE_FOLDERS = {
            'blueprints', 'materials', 'meshes', 'textures', 'animations',
            'sounds', 'particles', 'ui', 'maps', 'characters', 'weapons',
            'effects', 'environment', 'props', 'vehicles', 'audio', 'models',
            'fx', 'vfx', 'sfx', 'music', 'cinematics', 'cutscenes'
        }
        
        # 查找所有 UE 资产文件
        ue_assets = []
        for ext in ('.uasset', '.umap'):
            ue_assets.extend(root.rglob(f'*{ext}'))
        
        if not ue_assets:
            logger.info("未找到 UE 资产文件")
            return None
        
        logger.info(f"找到 {len(ue_assets)} 个 UE 资产文件")
        
        # 统计这些资产分布在哪些文件夹中
        asset_folders = set()
        for asset_file in ue_assets:
            # 获取相对于 root 的路径
            try:
                rel_path = asset_file.relative_to(root)
                # 检查所有层级的文件夹名（不只是第一层）
                for part in rel_path.parts[:-1]:  # 排除文件名本身
                    folder_name = part.lower()
                    asset_folders.add(folder_name)
                    logger.debug(f"资产文件夹: {folder_name}")
            except ValueError:
                continue
        
        logger.info(f"资产分布在 {len(asset_folders)} 个文件夹中: {sorted(asset_folders)}")
        
        # 检查是否有至少 1 个典型的 UE 文件夹
        typical_folders_found = asset_folders & TYPICAL_UE_FOLDERS
        
        if len(typical_folders_found) < 1:
            logger.info(f"不满足隐式 Content 条件：没有典型的 UE 文件夹（找到的文件夹：{sorted(asset_folders)}）")
            return None
        
        logger.info(f"检测到隐式 Content 结构：{len(ue_assets)} 个 UE 资产分布在 {len(typical_folders_found)} 个典型文件夹中")
        logger.info(f"典型文件夹：{sorted(typical_folders_found)}")
        
        # 检测双层嵌套结构（资产名/资产名/）
        # 如果根目录只有一个子目录，且子目录名与根目录名相同或相似
        root_subdirs = [d for d in root.iterdir() if d.is_dir() and not d.name.startswith('.')]
        
        asset_root = root
        if len(root_subdirs) == 1:
            subdir = root_subdirs[0]
            # 检查是否是双层嵌套（名称相同或相似）
            if subdir.name.lower() == root.name.lower() or \
               subdir.name.lower().replace('_', '').replace('-', '') == root.name.lower().replace('_', '').replace('-', ''):
                logger.info(f"检测到双层嵌套结构，跳过外层：{root.name} -> {subdir.name}")
                asset_root = subdir
        
        # 推断资产名称
        suggested_name = self._infer_name_from_path(asset_root, root)
        
        return AnalysisResult(
            structure_type=StructureType.CONTENT_PACKAGE,
            content_root=asset_root,  # 将整个目录视为 Content
            asset_root=asset_root,
            suggested_name=suggested_name,
            ue_asset_count=len(ue_assets),
            description=f"UE 资产包（隐式 Content），包含 {len(ue_assets)} 个资产文件",
            warnings=[f"未检测到 Content 文件夹，但包含典型的 UE 资产结构（{', '.join(sorted(typical_folders_found))}），将自动包装"]
        )
    
    def _find_ue_project(self, root: Path) -> Optional[AnalysisResult]:
        """查找完整 UE 项目（.uproject 文件）
        
        Args:
            root: 搜索根目录
            
        Returns:
            AnalysisResult 或 None
        """
        uproject_files = list(root.rglob('*.uproject'))
        if not uproject_files:
            return None
        
        # 选最浅层级的
        uproject_files.sort(key=lambda x: len(x.parts))
        uproject = uproject_files[0]
        project_dir = uproject.parent
        content_dir = project_dir / 'Content'
        
        ue_asset_count = 0
        if content_dir.exists():
            ue_assets = list(content_dir.rglob('*.uasset')) + list(content_dir.rglob('*.umap'))
            ue_asset_count = len(ue_assets)
        
        suggested_name = uproject.stem
        
        # 从 .uproject 文件读取引擎版本
        engine_version = ""
        try:
            import json
            with open(uproject, 'r', encoding='utf-8') as f:
                uproject_data = json.load(f)
                # .uproject 使用 EngineAssociation 字段，格式可能是 "5.4" 或 "{GUID}"
                engine_assoc = uproject_data.get('EngineAssociation', '')
                if engine_assoc and not engine_assoc.startswith('{'):
                    # 如果不是 GUID，直接使用
                    engine_version = engine_assoc
                    logger.info(f"从 .uproject 读取到引擎版本: {engine_version}")
        except Exception as e:
            logger.warning(f"读取 .uproject 文件版本失败: {e}")
        
        logger.info(f"找到 UE 项目: {uproject} ({ue_asset_count} 个资产)")
        
        return AnalysisResult(
            structure_type=StructureType.UE_PROJECT,
            content_root=content_dir if content_dir.exists() else None,
            asset_root=content_dir if content_dir.exists() else project_dir,
            suggested_name=suggested_name,
            uproject_path=uproject,
            ue_asset_count=ue_asset_count,
            engine_version=engine_version,
            description=f"完整 UE 项目「{suggested_name}」，Content 内有 {ue_asset_count} 个资产",
            warnings=["将仅导入 Content 文件夹内容"] if content_dir.exists() else ["项目无 Content 文件夹"]
        )
    
    def _find_ue_plugin(self, root: Path) -> Optional[AnalysisResult]:
        """查找 UE 插件（.uplugin 文件）
        
        Args:
            root: 搜索根目录
            
        Returns:
            AnalysisResult 或 None
        """
        uplugin_files = list(root.rglob('*.uplugin'))
        if not uplugin_files:
            return None
        
        uplugin_files.sort(key=lambda x: len(x.parts))
        uplugin = uplugin_files[0]
        plugin_dir = uplugin.parent
        content_dir = plugin_dir / 'Content'
        
        # 检测是否已包含 Plugins/ 前缀（大小写不敏感）
        # 如果压缩包结构是 Plugins/PluginName/，我们需要去掉 Plugins/ 前缀
        actual_plugin_dir = plugin_dir
        if plugin_dir.parent.name.lower() == 'plugins':
            # 压缩包已包含 Plugins/ 前缀，使用插件目录本身
            actual_plugin_dir = plugin_dir
            logger.info(f"检测到插件压缩包包含 Plugins/ 前缀: {plugin_dir}")
        
        ue_asset_count = 0
        if content_dir.exists():
            ue_assets = list(content_dir.rglob('*.uasset')) + list(content_dir.rglob('*.umap'))
            ue_asset_count = len(ue_assets)
        
        suggested_name = uplugin.stem
        
        # 从 .uplugin 文件读取引擎版本
        engine_version = ""
        try:
            import json
            with open(uplugin, 'r', encoding='utf-8') as f:
                uplugin_data = json.load(f)
                engine_version_str = uplugin_data.get('EngineVersion', '')
                if engine_version_str:
                    # 解析版本号，如 "5.4.0" -> "5.4"
                    parts = engine_version_str.split('.')
                    if len(parts) >= 2:
                        engine_version = f"{parts[0]}.{parts[1]}"
                    logger.info(f"从 .uplugin 读取到引擎版本: {engine_version}")
        except Exception as e:
            logger.warning(f"读取 .uplugin 文件版本失败: {e}")
        
        logger.info(f"找到 UE 插件: {uplugin}")
        
        return AnalysisResult(
            structure_type=StructureType.UE_PLUGIN,
            content_root=content_dir if content_dir.exists() else None,
            asset_root=actual_plugin_dir,
            suggested_name=suggested_name,
            uplugin_path=uplugin,
            ue_asset_count=ue_asset_count,
            engine_version=engine_version,
            description=f"UE 插件「{suggested_name}」",
            warnings=["检测到插件格式，将导入整个插件目录"]
        )
    
    def _find_loose_assets(self, root: Path) -> Optional[AnalysisResult]:
        """查找散装 UE 资产文件（没有 Content 包装）
        
        Args:
            root: 搜索根目录
            
        Returns:
            AnalysisResult 或 None
        """
        ue_files = []
        for ext in UE_ASSET_EXTENSIONS:
            ue_files.extend(root.rglob(f'*{ext}'))
        
        if not ue_files:
            return None
        
        # 找到包含 UE 资产的最浅层目录
        asset_dirs = set()
        for f in ue_files:
            asset_dirs.add(f.parent)
        
        # 找到公共根目录
        if len(asset_dirs) == 1:
            asset_root = list(asset_dirs)[0]
        else:
            # 多个目录，找最浅的公共父目录
            asset_root = self._find_common_parent(list(asset_dirs), root)
        
        suggested_name = self._infer_name_from_path(asset_root, root)
        ue_asset_count = sum(1 for f in ue_files if f.suffix in {'.uasset', '.umap'})
        
        logger.info(f"找到散装 UE 资产: {asset_root} ({ue_asset_count} 个)")
        
        return AnalysisResult(
            structure_type=StructureType.LOOSE_ASSETS,
            content_root=None,
            asset_root=asset_root,
            suggested_name=suggested_name,
            ue_asset_count=ue_asset_count,
            description=f"散装 UE 资产文件，共 {ue_asset_count} 个",
            warnings=["未检测到 Content 文件夹结构，将自动包装"]
        )
    
    def _find_raw_3d_files(self, root: Path) -> Optional[AnalysisResult]:
        """查找原始 3D 文件
        
        Args:
            root: 搜索根目录
            
        Returns:
            AnalysisResult 或 None
        """
        raw_files = []
        for ext in RAW_3D_EXTENSIONS:
            raw_files.extend(root.rglob(f'*{ext}'))
        
        if not raw_files:
            return None
        
        # 找资产根目录
        asset_dirs = set(f.parent for f in raw_files)
        if len(asset_dirs) == 1:
            asset_root = list(asset_dirs)[0]
        else:
            asset_root = self._find_common_parent(list(asset_dirs), root)
        
        suggested_name = self._infer_name_from_path(asset_root, root)
        
        file_types = set(f.suffix.lower() for f in raw_files)
        type_str = ', '.join(sorted(ext.upper().lstrip('.') for ext in file_types))
        
        logger.info(f"找到原始 3D 文件: {type_str} ({len(raw_files)} 个)")
        
        return AnalysisResult(
            structure_type=StructureType.RAW_3D_FILES,
            content_root=None,
            asset_root=asset_root,
            suggested_name=suggested_name,
            total_file_count=len(raw_files),
            description=f"原始 3D 文件（{type_str}），共 {len(raw_files)} 个",
            warnings=["非 UE 原生资产，需要在 UE 中手动导入"]
        )
    
    def _infer_name_from_content(self, content_dir: Path, root: Path) -> str:
        """从 Content 文件夹位置推断资产名称
        
        优先级：
        1. Content 的父目录名（如果不是解压根目录）
        2. Content 下的第一个子文件夹名
        3. 解压根目录下的第一个子目录名
        """
        parent = content_dir.parent
        
        # 如果 Content 的父目录不是解压根目录，用父目录名
        if parent != root:
            # 检查是否是有意义的名称（不是类似 temp_ 的名称）
            name = parent.name
            if name and not name.startswith('temp') and not name.startswith('.'):
                return name
        
        # 用 Content 下的第一个子文件夹名
        sub_dirs = [d for d in content_dir.iterdir() if d.is_dir() and not d.name.startswith('.')]
        if sub_dirs:
            return sub_dirs[0].name
        
        # 最后兜底：用解压根下的第一个文件夹名
        root_dirs = [d for d in root.iterdir() if d.is_dir() and not d.name.startswith('.')]
        if root_dirs:
            return root_dirs[0].name
        
        return "UnnamedAsset"
    
    def _infer_name_from_path(self, asset_root: Path, extracted_root: Path) -> str:
        """从资产路径推断名称"""
        if asset_root != extracted_root:
            return asset_root.name
        
        # 用根目录下第一个有意义的子目录
        sub_dirs = [d for d in extracted_root.iterdir() if d.is_dir() and not d.name.startswith('.')]
        if sub_dirs:
            return sub_dirs[0].name
        
        return "UnnamedAsset"
    
    def _find_common_parent(self, dirs: List[Path], fallback: Path) -> Path:
        """找到多个目录的最近公共父目录"""
        if not dirs:
            return fallback
        
        if len(dirs) == 1:
            return dirs[0]
        
        # 用第一个目录的 parts 作为基准
        common_parts = list(dirs[0].parts)
        
        for d in dirs[1:]:
            d_parts = list(d.parts)
            new_common = []
            for a, b in zip(common_parts, d_parts):
                if a == b:
                    new_common.append(a)
                else:
                    break
            common_parts = new_common
        
        if common_parts:
            return Path(*common_parts)
        
        return fallback
