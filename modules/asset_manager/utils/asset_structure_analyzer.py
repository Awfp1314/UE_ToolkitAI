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
RAW_3D_EXTENSIONS = {
    # 常用格式
    '.fbx', '.obj', '.gltf', '.glb',  # 通用格式
    '.dae',  # Collada
    '.stl',  # 3D 打印
    # USD 格式
    '.usd', '.usda', '.usdc', '.usdz',
    # Alembic
    '.abc',
    # 软件专用格式
    '.blend',  # Blender
    '.ma', '.mb',  # Maya
    '.max',  # 3ds Max
    '.c4d',  # Cinema 4D
    '.skp',  # SketchUp
    '.3ds',  # 3D Studio
    # 动画/角色格式
    '.pmx', '.pmd',  # MikuMikuDance (MMD)
    '.x',  # DirectX
    '.ply',  # Polygon File Format
    '.wrl', '.vrml',  # VRML
}

# 纹理文件扩展名
TEXTURE_EXTENSIONS = {'.png', '.jpg', '.jpeg', '.tga', '.bmp', '.exr', '.hdr', '.tif', '.tiff'}


class StructureType(Enum):
    """资产结构类型"""
    CONTENT_PACKAGE = "content_package"    # 包含 Content/ 文件夹的资产包（最常见）
    UE_PROJECT = "ue_project"              # 完整的 UE 项目（有 .uproject）
    UE_PLUGIN = "ue_plugin"                # UE 插件（有 .uplugin）
    LOOSE_ASSETS = "loose_assets"          # 散装 .uasset/.umap 文件
    MODEL_FILES = "model_files"            # 3D 模型文件（FBX/OBJ 等）
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
    
    def _extract_nested_archives(self, root: Path) -> None:
        """解压嵌套的压缩包（只解压一层，避免无限递归）
        
        Args:
            root: 搜索根目录
        """
        import zipfile
        
        # 可选导入：py7zr 和 rarfile
        try:
            import py7zr
            has_py7zr = True
        except ImportError:
            has_py7zr = False
            logger.debug("[嵌套解压] py7zr 未安装，跳过 .7z 文件")
        
        try:
            import rarfile
            has_rarfile = True
        except ImportError:
            has_rarfile = False
            logger.debug("[嵌套解压] rarfile 未安装，跳过 .rar 文件")
        
        # 根据可用的库确定支持的扩展名
        archive_extensions = {'.zip'}
        if has_py7zr:
            archive_extensions.add('.7z')
        if has_rarfile:
            archive_extensions.add('.rar')
        
        archives_to_extract = []
        
        # 查找所有压缩包文件
        for item in root.rglob('*'):
            if item.is_file() and item.suffix.lower() in archive_extensions:
                archives_to_extract.append(item)
        
        if not archives_to_extract:
            return
        
        logger.info(f"[嵌套解压] 发现 {len(archives_to_extract)} 个嵌套压缩包")
        
        for archive_file in archives_to_extract:
            try:
                # 解压到同级目录
                extract_dir = archive_file.parent / archive_file.stem
                
                # 如果目标目录已存在，跳过
                if extract_dir.exists():
                    logger.debug(f"[嵌套解压] 跳过已存在: {archive_file.name}")
                    continue
                
                extract_dir.mkdir(parents=True, exist_ok=True)
                logger.info(f"[嵌套解压] 解压: {archive_file.name} -> {extract_dir.name}")
                
                ext = archive_file.suffix.lower()
                
                if ext == '.zip':
                    with zipfile.ZipFile(archive_file, 'r') as zip_ref:
                        # 处理中文文件名
                        for z_info in zip_ref.infolist():
                            if z_info.is_dir():
                                continue
                            
                            try:
                                # 尝试 GBK 解码
                                original_name = z_info.filename.encode('cp437').decode('gbk')
                            except:
                                original_name = z_info.filename
                            
                            # 清理文件名
                            parts = original_name.split('/')
                            cleaned_parts = [part.rstrip(' .') or '_' for part in parts]
                            cleaned_name = '/'.join(cleaned_parts)
                            
                            target_path = extract_dir / cleaned_name
                            target_path.parent.mkdir(parents=True, exist_ok=True)
                            
                            with zip_ref.open(z_info) as source:
                                with open(target_path, 'wb') as target:
                                    target.write(source.read())
                
                elif ext == '.7z' and has_py7zr:
                    with py7zr.SevenZipFile(archive_file, mode='r') as z:
                        z.extractall(path=extract_dir)
                
                elif ext == '.rar' and has_rarfile:
                    with rarfile.RarFile(archive_file) as rf:
                        rf.extractall(extract_dir)
                
                # 删除原压缩包文件
                archive_file.unlink()
                logger.info(f"[嵌套解压] 完成并删除原文件: {archive_file.name}")
                
            except Exception as e:
                logger.warning(f"[嵌套解压] 失败: {archive_file.name}, 错误: {e}")
    
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
        
        # 预处理：解压嵌套的压缩包（只解压一层，避免无限递归）
        self._extract_nested_archives(extracted_dir)
        
        # 统计文件
        total_files = list(extracted_dir.rglob('*'))
        total_file_count = sum(1 for f in total_files if f.is_file())
        
        # 诊断：列出所有文件及其扩展名
        logger.info(f"[诊断] 解压目录包含 {total_file_count} 个文件")
        file_extensions = {}
        sample_files = []
        for f in total_files:
            if f.is_file():
                ext = f.suffix.lower()
                file_extensions[ext] = file_extensions.get(ext, 0) + 1
                if len(sample_files) < 20:  # 只记录前20个文件作为样本
                    sample_files.append(f"{f.relative_to(extracted_dir)} ({ext})")
        logger.info(f"[诊断] 文件扩展名统计: {file_extensions}")
        logger.info(f"[诊断] 文件样本（前20个）: {sample_files}")
        
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
        logger.info("[analyze] Step 5: 开始查找 3D 模型文件")
        result = self._find_raw_3d_files(extracted_dir)
        if result:
            logger.info(f"[analyze] Step 5 成功: 找到 MODEL_FILES 类型")
            result.total_file_count = total_file_count
            return result
        else:
            logger.info("[analyze] Step 5 失败: 未找到 3D 模型文件")
        
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
        
        注意：如果 Content 文件夹里只有 3D 模型文件（无 .uasset/.umap），
        返回 None，让后续的 _find_raw_3d_files 处理。
        
        Args:
            root: 搜索根目录
            
        Returns:
            AnalysisResult 或 None
        """
        import os
        
        # 特殊情况 1：检查 root 本身是否就是 Content 文件夹
        if root.name.lower() == 'content':
            logger.info(f"检测到用户直接选择了 Content 文件夹: {root}")

            # 若出现 content/content/... 包装，自动下钻到最内层有效 Content
            effective_content = root
            depth = 0
            while depth < 5:
                try:
                    meaningful_items = [
                        p for p in effective_content.iterdir()
                        if not p.name.startswith('.') and p.name.lower() not in {'__macosx'}
                    ]
                except Exception:
                    break

                if (
                    len(meaningful_items) == 1
                    and meaningful_items[0].is_dir()
                    and meaningful_items[0].name.lower() == 'content'
                ):
                    logger.info(f"检测到嵌套 Content 包装，下钻: {effective_content} -> {meaningful_items[0]}")
                    effective_content = meaningful_items[0]
                    depth += 1
                else:
                    break

            ue_assets = []
            for ext in ('.uasset', '.umap'):
                ue_assets.extend(effective_content.rglob(f'*{ext}'))
            
            # 检查是否有 3D 模型文件
            raw_3d_files = []
            for item in effective_content.rglob('*'):
                if item.is_file() and item.suffix.lower() in RAW_3D_EXTENSIONS:
                    raw_3d_files.append(item)
            
            if ue_assets:
                asset_count = len(ue_assets)
                logger.info(f"Content 文件夹包含 {asset_count} 个 UE 资产")

                # 名称优先取 Content 下首个非 Content 子目录
                suggested_name = ""
                try:
                    sub_dirs = [d for d in effective_content.iterdir() if d.is_dir() and not d.name.startswith('.')]
                    for d in sub_dirs:
                        if d.name.lower() != 'content':
                            suggested_name = d.name
                            break
                except Exception:
                    pass

                if not suggested_name:
                    parent_name = effective_content.parent.name if effective_content.parent else ""
                    if parent_name and parent_name.lower() != 'content':
                        suggested_name = parent_name
                if not suggested_name:
                    suggested_name = "UnnamedAsset"

                return AnalysisResult(
                    structure_type=StructureType.CONTENT_PACKAGE,
                    content_root=effective_content,
                    asset_root=effective_content,
                    suggested_name=suggested_name,
                    ue_asset_count=asset_count,
                    description=f"UE 资产包，包含 {asset_count} 个资产文件",
                    warnings=[]
                )
            elif raw_3d_files:
                # Content 文件夹里只有 3D 模型文件，没有 UE 资产
                # 返回 None，让 _find_raw_3d_files 处理
                logger.info(f"Content 文件夹只包含 {len(raw_3d_files)} 个 3D 模型文件，无 UE 资产，交由 MODEL_FILES 处理")
                return None
        
        # 特殊情况 2：检查 root 的父目录是否是 Content
        if root.parent and root.parent.name.lower() == 'content':
            logger.info(f"检测到用户选择了 Content 的子文件夹: {root}")
            ue_assets = []
            for ext in ('.uasset', '.umap'):
                ue_assets.extend(root.rglob(f'*{ext}'))
            
            # 检查是否有 3D 模型文件
            raw_3d_files = []
            for item in root.rglob('*'):
                if item.is_file() and item.suffix.lower() in RAW_3D_EXTENSIONS:
                    raw_3d_files.append(item)
            
            if ue_assets:
                asset_count = len(ue_assets)
                logger.info(f"Content 子文件夹包含 {asset_count} 个 UE 资产")
                return AnalysisResult(
                    structure_type=StructureType.CONTENT_PACKAGE,
                    content_root=root.parent,
                    asset_root=root.parent,
                    suggested_name=root.name,
                    ue_asset_count=asset_count,
                    description=f"UE 资产包（Content 子文件夹），包含 {asset_count} 个资产文件",
                    warnings=[]
                )
            elif raw_3d_files:
                # Content 子文件夹只有 3D 模型文件
                logger.info(f"Content 子文件夹只包含 {len(raw_3d_files)} 个 3D 模型文件，交由 MODEL_FILES 处理")
                return None
        
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
        
        # 使用 os.walk 遍历（更可靠，避免 rglob 在某些情况下漏掉目录）
        content_dirs = []
        for dirpath, dirnames, filenames in os.walk(str(root)):
            for dirname in dirnames:
                if dirname.lower() == 'content':  # 大小写不敏感匹配
                    content_dirs.append(Path(dirpath) / dirname)
        
        logger.info(f"搜索到的 Content 文件夹: {content_dirs}")
        
        if not content_dirs:
            logger.info("未找到 Content 文件夹，尝试隐式 Content 识别")
            return self._find_implicit_content_package(root)
        
        # 过滤：只保留包含 UE 资产的 Content 文件夹
        valid_contents = []
        model_only_contents = []  # 只有 3D 模型文件的 Content 文件夹
        
        for content_dir in content_dirs:
            ue_assets = []
            for ext in ('.uasset', '.umap'):
                ue_assets.extend(content_dir.rglob(f'*{ext}'))
            
            # 检查是否有 3D 模型文件
            raw_3d_files = []
            for item in content_dir.rglob('*'):
                if item.is_file() and item.suffix.lower() in RAW_3D_EXTENSIONS:
                    raw_3d_files.append(item)
            
            if ue_assets:
                valid_contents.append((content_dir, len(ue_assets)))
                logger.info(f"  有效 Content: {content_dir} ({len(ue_assets)} 个 UE 资产)")
            elif raw_3d_files:
                model_only_contents.append((content_dir, len(raw_3d_files)))
                logger.info(f"  Content 只有 3D 模型: {content_dir} ({len(raw_3d_files)} 个模型文件)")
            else:
                logger.info(f"  空 Content（无 UE 资产）: {content_dir}")
        
        # 如果只找到 3D 模型文件的 Content，返回 None 让 _find_raw_3d_files 处理
        if not valid_contents and model_only_contents:
            logger.info(f"所有 Content 文件夹都只包含 3D 模型文件，交由 MODEL_FILES 处理")
            return None
        
        if not valid_contents:
            return self._find_implicit_content_package(root)
        
        # 选择最佳 Content：优先处理连续嵌套的 content/content/... 场景
        # 规则：
        # 1) 连续 content 链更深的优先（避免选到外层包装 content）
        # 2) 若链深相同，选择层级更浅的（保持原有行为）
        def _content_chain_depth(content_path: Path) -> int:
            depth = 0
            p = content_path
            while p.name.lower() == 'content':
                depth += 1
                p = p.parent
            return depth

        best_content, asset_count = sorted(
            valid_contents,
            key=lambda x: (-_content_chain_depth(x[0]), len(x[0].parts))
        )[0]
        chain_depth = _content_chain_depth(best_content)
        
        suggested_name = self._infer_name_from_content(best_content, root)
        logger.info(f"找到 Content 资产包: {best_content} ({asset_count} 个 UE 资产), content 链深度: {chain_depth}")
        
        warnings = []
        if len(valid_contents) > 1:
            warnings.append(f"发现 {len(valid_contents)} 个 Content 文件夹，已自动选择最匹配路径")
        if chain_depth > 1:
            warnings.append("检测到多层 Content 包装，已自动剥离外层包装")
        
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
        只要满足以下条件即识别为 CONTENT_PACKAGE：
        1. 没有 Content/ 文件夹（调用方已确认）
        2. 有 .uasset 或 .umap 文件
        3. 没有 .uproject 或 .uplugin 文件
        
        结构2：AssetName/AssetName/资产文件夹（无 Content）
        这种情况下取内层文件夹作为 asset_root。
        """
        ue_assets = []
        for ext in ('.uasset', '.umap'):
            ue_assets.extend(root.rglob(f'*{ext}'))
        
        if not ue_assets:
            logger.info("未找到 UE 资产文件")
            return None
        
        logger.info(f"找到 {len(ue_assets)} 个 UE 资产文件，识别为隐式 Content 资产包")
        
        # 剥皮策略：从 root 开始，循环向内剥，直到找到真正的资产层
        # 规则：当前层下有且仅有一个有意义的子目录（忽略广告/系统文件），就继续往内取
        # 终止条件：子目录数量 > 1（多个资产文件夹并列，当前层就是 asset_root）
        #           或当前层下直接有 .uasset/.umap 文件
        _JUNK_EXTS = {'.txt', '.nfo', '.url', '.webloc', '.lnk', '.html', '.htm', '.pdf'}
        _JUNK_DIRS = {'__macosx', '.git', '.svn'}

        def _real_subdirs(path: Path):
            """过滤掉广告/系统目录后的真实子目录列表"""
            return [
                d for d in path.iterdir()
                if d.is_dir() and d.name.lower() not in _JUNK_DIRS and not d.name.startswith('.')
            ]

        def _has_direct_assets(path: Path) -> bool:
            """当前层下是否直接含有 .uasset/.umap（非递归）"""
            return any(
                f.suffix.lower() in ('.uasset', '.umap')
                for f in path.iterdir() if f.is_file()
            )

        asset_root = root
        depth = 0
        while depth < 5:  # 最多剥5层，防止死循环
            subdirs = _real_subdirs(asset_root)
            if len(subdirs) == 1 and not _has_direct_assets(asset_root):
                # 只有一个子目录且当前层没有直接资产文件 → 继续往内
                logger.info(f"剥皮第{depth+1}层：{asset_root.name} -> {subdirs[0].name}")
                asset_root = subdirs[0]
                depth += 1
            else:
                # 多个子目录 或 当前层有直接资产 → 这里就是 asset_root
                break

        logger.info(f"最终 asset_root: {asset_root}")
        
        suggested_name = self._infer_name_from_path(asset_root, root)
        
        return AnalysisResult(
            structure_type=StructureType.CONTENT_PACKAGE,
            content_root=asset_root,
            asset_root=asset_root,
            suggested_name=suggested_name,
            ue_asset_count=len(ue_assets),
            description=f"UE 资产包（无 Content 文件夹），包含 {len(ue_assets)} 个资产文件",
            warnings=["未检测到 Content 文件夹，将以当前目录结构直接包装"]
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
        
        uproject_files.sort(key=lambda x: len(x.parts))
        uproject = uproject_files[0]
        project_dir = uproject.parent
        content_dir = project_dir / 'Content'
        
        ue_asset_count = 0
        if content_dir.exists():
            ue_assets = list(content_dir.rglob('*.uasset')) + list(content_dir.rglob('*.umap'))
            ue_asset_count = len(ue_assets)
        
        suggested_name = uproject.stem
        
        engine_version = ""
        try:
            import json
            with open(uproject, 'r', encoding='utf-8') as f:
                uproject_data = json.load(f)
                engine_assoc = uproject_data.get('EngineAssociation', '')
                if engine_assoc and not engine_assoc.startswith('{'):
                    engine_version = engine_assoc
                    logger.info(f"从 .uproject 读取到引擎版本: {engine_version}")
        except Exception as e:
            logger.warning(f"读取 .uproject 文件版本失败: {e}")
        
        logger.info(f"找到 UE 项目: {uproject} ({ue_asset_count} 个资产)")
        
        # FIX: PROJECT 类型 asset_root 指向完整项目目录，而非仅 Content
        # 保留 .uproject、Config/、Plugins/ 等完整项目结构
        return AnalysisResult(
            structure_type=StructureType.UE_PROJECT,
            content_root=content_dir if content_dir.exists() else None,
            asset_root=project_dir,
            suggested_name=suggested_name,
            uproject_path=uproject,
            ue_asset_count=ue_asset_count,
            engine_version=engine_version,
            description=f"完整 UE 项目「{suggested_name}」，Content 内有 {ue_asset_count} 个资产",
            warnings=["将导入完整项目目录（含 .uproject、Config、Plugins 等）"] if content_dir.exists() else ["项目无 Content 文件夹"]
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
        
        # FIX: 修正 Plugins/ 前缀判断死代码
        # 如果压缩包结构是 Plugins/PluginName/.uplugin，actual_plugin_dir 应该指向
        # plugin_dir（即 PluginName/），因为存储时我们只需要插件目录本身。
        # 如果压缩包结构是 PluginName/.uplugin（无 Plugins/ 前缀），同样指向 plugin_dir。
        # 两种情况 asset_root 都是 plugin_dir，区别在于 warning 提示。
        actual_plugin_dir = plugin_dir
        has_plugins_prefix = plugin_dir.parent.name.lower() == 'plugins'
        if has_plugins_prefix:
            logger.info(f"检测到插件压缩包包含 Plugins/ 前缀，asset_root 指向插件目录: {plugin_dir}")
        
        ue_asset_count = 0
        if content_dir.exists():
            ue_assets = list(content_dir.rglob('*.uasset')) + list(content_dir.rglob('*.umap'))
            ue_asset_count = len(ue_assets)
        
        suggested_name = uplugin.stem
        
        engine_version = ""
        try:
            import json
            with open(uplugin, 'r', encoding='utf-8') as f:
                uplugin_data = json.load(f)
                engine_version_str = uplugin_data.get('EngineVersion', '')
                if engine_version_str:
                    parts = engine_version_str.split('.')
                    if len(parts) >= 2:
                        engine_version = f"{parts[0]}.{parts[1]}"
                    logger.info(f"从 .uplugin 读取到引擎版本: {engine_version}")
        except Exception as e:
            logger.warning(f"读取 .uplugin 文件版本失败: {e}")
        
        logger.info(f"找到 UE 插件: {uplugin}")
        
        warnings = ["检测到插件格式，将导入整个插件目录"]
        if has_plugins_prefix:
            warnings.append("压缩包包含 Plugins/ 前缀，已自动定位到插件根目录")
        
        return AnalysisResult(
            structure_type=StructureType.UE_PLUGIN,
            content_root=content_dir if content_dir.exists() else None,
            asset_root=actual_plugin_dir,
            suggested_name=suggested_name,
            uplugin_path=uplugin,
            ue_asset_count=ue_asset_count,
            engine_version=engine_version,
            description=f"UE 插件「{suggested_name}」",
            warnings=warnings
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
        
        asset_dirs = set()
        for f in ue_files:
            asset_dirs.add(f.parent)
        
        if len(asset_dirs) == 1:
            asset_root = list(asset_dirs)[0]
        else:
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
        """查找 3D 模型文件
        
        Args:
            root: 搜索根目录
            
        Returns:
            AnalysisResult 或 None
        """
        raw_files = []
        # 大小写不敏感匹配
        logger.info(f"[MODEL_FILES] 开始搜索 3D 模型文件，支持的扩展名: {RAW_3D_EXTENSIONS}")
        for item in root.rglob('*'):
            if item.is_file():
                logger.debug(f"[MODEL_FILES] 检查文件: {item.name}, 扩展名: {item.suffix.lower()}")
                if item.suffix.lower() in RAW_3D_EXTENSIONS:
                    logger.info(f"[MODEL_FILES] 找到 3D 模型文件: {item}")
                    raw_files.append(item)
        
        logger.info(f"[MODEL_FILES] 搜索完成，找到 {len(raw_files)} 个 3D 模型文件")
        if not raw_files:
            return None
        
        asset_dirs = set(f.parent for f in raw_files)
        if len(asset_dirs) == 1:
            asset_root = list(asset_dirs)[0]
        else:
            asset_root = self._find_common_parent(list(asset_dirs), root)
        
        suggested_name = self._infer_name_from_path(asset_root, root)
        
        file_types = set(f.suffix.lower() for f in raw_files)
        type_str = ', '.join(sorted(ext.upper().lstrip('.') for ext in file_types))
        
        logger.info(f"找到 3D 模型文件: {type_str} ({len(raw_files)} 个)")
        
        return AnalysisResult(
            structure_type=StructureType.MODEL_FILES,
            content_root=None,
            asset_root=asset_root,
            suggested_name=suggested_name,
            total_file_count=len(raw_files),
            description=f"3D 模型文件（{type_str}），共 {len(raw_files)} 个",
            warnings=["3D 模型资源，需要在 UE 中手动导入"]
        )
    
    def _infer_name_from_content(self, content_dir: Path, root: Path) -> str:
        """从 Content 文件夹位置推断资产名称
        
        优先级：
        1. Content 的父目录名（如果不是解压根目录且不是 "content"）
        2. 解压根目录的名称（如果不是临时目录）
        3. Content 下的第一个子文件夹名
        4. "UnnamedAsset"
        """
        logger.info(f"[_infer_name_from_content] content_dir={content_dir}, root={root}")
        parent = content_dir.parent
        logger.info(f"[_infer_name_from_content] parent={parent}, parent.name={parent.name}")
        
        # 优先级 1: Content 的父目录名（排除解压根目录和 "content" 名称）
        if parent != root:
            name = parent.name
            logger.info(f"[_infer_name_from_content] 优先级1: parent != root, name={name}")
            if name and not name.startswith('temp') and not name.startswith('.') and name.lower() != 'content':
                logger.info(f"[_infer_name_from_content] 优先级1 通过: 返回 {name}")
                return name
            else:
                logger.info(f"[_infer_name_from_content] 优先级1 未通过: name={name}, lower={name.lower() if name else None}")
        else:
            logger.info(f"[_infer_name_from_content] 优先级1 跳过: parent == root")
        
        # 优先级 2: 解压根目录的名称（排除临时目录）
        root_name = root.name
        logger.info(f"[_infer_name_from_content] 优先级2: root_name={root_name}")
        if root_name and not root_name.startswith('temp') and not root_name.startswith('.') and not root_name.startswith('ue_toolkit_extract'):
            logger.info(f"[_infer_name_from_content] 优先级2 通过: 返回 {root_name}")
            return root_name
        else:
            logger.info(f"[_infer_name_from_content] 优先级2 未通过")
        
        # 优先级 3: Content 下的第一个子文件夹名
        sub_dirs = [d for d in content_dir.iterdir() if d.is_dir() and not d.name.startswith('.')]
        logger.info(f"[_infer_name_from_content] 优先级3: sub_dirs={[d.name for d in sub_dirs]}")
        if sub_dirs:
            logger.info(f"[_infer_name_from_content] 优先级3 通过: 返回 {sub_dirs[0].name}")
            return sub_dirs[0].name
        
        # 优先级 4: 默认名称
        logger.info(f"[_infer_name_from_content] 优先级4: 返回 UnnamedAsset")
        return "UnnamedAsset"
    
    def _infer_name_from_path(self, asset_root: Path, extracted_root: Path) -> str:
        """从资产路径推断名称
        
        优先级：
        1. asset_root 的名称（如果不等于 extracted_root）
        2. extracted_root 的名称（如果不是临时目录）
        3. "UnnamedAsset"
        """
        logger.info(f"[_infer_name_from_path] asset_root={asset_root}, extracted_root={extracted_root}")
        
        # 优先级 1: asset_root 的名称（剥皮后的结果）
        if asset_root != extracted_root:
            logger.info(f"[_infer_name_from_path] 优先级1: asset_root != extracted_root, 返回 {asset_root.name}")
            return asset_root.name
        
        # 优先级 2: extracted_root 的名称（如果不是临时目录）
        root_name = extracted_root.name
        logger.info(f"[_infer_name_from_path] 优先级2: root_name={root_name}")
        if root_name and not root_name.startswith('temp') and not root_name.startswith('.') and not root_name.startswith('ue_toolkit_extract'):
            logger.info(f"[_infer_name_from_path] 优先级2 通过: 返回 {root_name}")
            return root_name
        
        # 优先级 3: 默认名称
        logger.info(f"[_infer_name_from_path] 优先级3: 返回 UnnamedAsset")
        return "UnnamedAsset"
    
    def _find_common_parent(self, dirs: List[Path], fallback: Path) -> Path:
        """找到多个目录的最近公共父目录"""
        if not dirs:
            return fallback
        
        if len(dirs) == 1:
            return dirs[0]
        
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
