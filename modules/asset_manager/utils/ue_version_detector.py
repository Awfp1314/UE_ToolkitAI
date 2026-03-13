"""
UE版本检测工具类

提供检测UE资产和工程版本的功能
"""

import struct
from pathlib import Path
from typing import Optional
from logging import Logger


class UEVersionDetector:
    """UE版本检测器
    
    提供以下功能：
    - 从.uasset文件检测资产的引擎版本
    - 检测资产包中所有.uasset文件的最高版本
    - 生成版本显示字符串（如"UE5.4+"）
    """
    
    def __init__(self, logger: Optional[Logger] = None):
        """初始化版本检测器
        
        Args:
            logger: 日志记录器（可选）
        """
        self._logger = logger
    
    def detect_asset_min_version(self, asset_path: Path) -> str:
        """检测资产的最低引擎版本
        
        Args:
            asset_path: 资产路径（文件或文件夹）
            
        Returns:
            str: 版本字符串（如"4.27", "5.0"），检测失败返回空字符串
        """
        if not asset_path.exists():
            return ""
        
        # 查找.uasset文件
        uasset_files = []
        if asset_path.is_file() and asset_path.suffix == '.uasset':
            uasset_files = [asset_path]
        elif asset_path.is_dir():
            uasset_files = list(asset_path.rglob("*.uasset"))
        
        if not uasset_files:
            if self._logger:
                self._logger.warning(f"未找到.uasset文件: {asset_path}")
            return ""
        
        # 先检测UE5特性（Lumen、Nanite等）
        has_ue5_features = self._detect_ue5_features(asset_path)
        
        # 读取第一个.uasset文件的版本
        version = self._read_uasset_version(uasset_files[0])
        
        # 如果检测到UE5特性，但版本号显示为UE4，则修正为UE5
        if has_ue5_features and version and version.startswith('4.'):
            if self._logger:
                self._logger.info(f"检测到UE5特性（Lumen/Nanite），修正版本: {version} -> 5.0")
            version = "5.0"
        
        if self._logger and version:
            self._logger.debug(f"检测到资产版本: {asset_path.name} -> UE {version}")
        
        return version
    
    def _detect_ue5_features(self, asset_path: Path) -> bool:
        """检测资产是否包含UE5特性（Lumen、Nanite等）
        
        Args:
            asset_path: 资产路径
            
        Returns:
            bool: 包含UE5特性返回True
        """
        try:
            # 检测关键字：Lumen、Nanite、VirtualShadowMap等UE5特性
            ue5_keywords = [
                b'Lumen',
                b'Nanite',
                b'VirtualShadowMap',
                b'WorldPartition',
                b'HLODLayer'
            ]
            
            # 搜索所有.uasset和.umap文件
            search_files = []
            if asset_path.is_file():
                search_files = [asset_path]
            else:
                search_files = list(asset_path.rglob("*.uasset"))[:10]  # 只检查前10个文件
                search_files.extend(list(asset_path.rglob("*.umap"))[:5])
            
            for file_path in search_files:
                try:
                    with open(file_path, 'rb') as f:
                        # 读取文件内容（最多1MB）
                        content = f.read(1024 * 1024)
                        
                        # 检查是否包含UE5关键字
                        for keyword in ue5_keywords:
                            if keyword in content:
                                if self._logger:
                                    self._logger.debug(f"检测到UE5特性: {keyword.decode('utf-8')} in {file_path.name}")
                                return True
                except Exception:
                    continue
            
            return False
            
        except Exception as e:
            if self._logger:
                self._logger.debug(f"UE5特性检测失败: {e}")
            return False
    
    def _read_uasset_version(self, uasset_file: Path) -> str:
        """从.uasset文件读取引擎版本
        
        Args:
            uasset_file: .uasset文件路径
            
        Returns:
            str: 版本字符串（如"4.27", "5.4"），读取失败返回空字符串
        """
        try:
            with open(uasset_file, 'rb') as f:
                # 跳过文件头标识（4字节）
                f.seek(4)
                # 读取Legacy Version（4字节，小端序整数）
                version_bytes = f.read(4)
                if len(version_bytes) < 4:
                    return ""
                
                legacy_version = struct.unpack('<I', version_bytes)[0]
                
                # Legacy Version 是一个负数或特定值，需要跳过
                # 继续读取实际的 UE Version
                # 偏移到正确位置：跳过 Legacy Version (4) + Legacy UE3 Version (4) + File Version UE4 (4) + File Version Licensee UE4 (4)
                # 实际上更简单的方法：直接读取偏移 20 的位置（Custom Version Container）之前的版本信息
                
                # 重新定位：读取文件版本信息
                # 实际UE版本存储在不同位置，让我们使用更可靠的方法
                # 读取 Package File Summary 中的版本号
                
                # 跳过前面的字段，定位到版本号
                # 格式：Tag(4) + LegacyVersion(4) + LegacyUE3Version(4) + FileVersionUE4(4) + FileVersionLicenseeUE4(4) + CustomVersions...
                # FileVersionUE4 包含实际版本
                
                f.seek(12)  # 跳过 Tag(4) + LegacyVersion(4) + LegacyUE3Version(4)
                file_version_ue4_bytes = f.read(4)
                if len(file_version_ue4_bytes) < 4:
                    return ""
                
                file_version_ue4 = struct.unpack('<i', file_version_ue4_bytes)[0]  # 有符号整数
                
                # 解析版本号：FileVersionUE4 是一个枚举值，需要映射到实际版本
                # 通常 UE4.27 对应 522, UE5.0 对应 1000+
                # 更简单的方法：读取自定义版本中的引擎版本
                
                # 使用更直接的方法：读取偏移 4 位置的数据作为版本指示
                # 实际上最可靠的是读取 Package 的 Compatible 和 SavedByEngineVersion
                
                # 使用正确的UE版本映射表
                if file_version_ue4 >= 1000:  # UE5
                    # UE5 版本映射
                    if file_version_ue4 >= 1004:
                        return "5.4"
                    elif file_version_ue4 >= 1003:
                        return "5.3"
                    elif file_version_ue4 >= 1002:
                        return "5.2"
                    elif file_version_ue4 >= 1001:
                        return "5.1"
                    else:
                        return "5.0"
                elif file_version_ue4 >= 522:
                    return "4.27"
                elif file_version_ue4 >= 520:
                    return "4.26"
                elif file_version_ue4 >= 517:
                    return "4.25"
                elif file_version_ue4 >= 504:
                    return "4.20"  # 4.20-4.24 使用 4.20 代表
                elif file_version_ue4 >= 482:
                    return "4.16"  # 4.16-4.19 使用 4.16 代表
                elif file_version_ue4 >= 352:
                    return "4.11"  # 4.11-4.15 使用 4.11 代表
                elif file_version_ue4 >= 342:
                    return "4.7"   # 4.7-4.10 使用 4.7 代表
                else:
                    return "4.0"   # 4.0-4.6 及更早版本
                
        except Exception as e:
            if self._logger:
                self._logger.debug(f"读取uasset版本失败: {uasset_file} - {e}")
            return ""
    
    def format_version_badge(self, version: str, package_type = None) -> str:
        """格式化版本为徽标显示字符串
        
        Args:
            version: 版本字符串（如"4.27", "5.4"）
            package_type: 资产包类型（PackageType 枚举或字符串，如 PackageType.PLUGIN 或 "plugin"）
            
        Returns:
            str: 徽标字符串（如"UE4.27+", "UE5.4+"），插件类型返回精确版本"UE5.4"，空版本返回"UE?"
        """
        if not version:
            return "UE?"
        
        # 插件类型需要精确版本，不添加 +（UE 插件不向上兼容）
        # 支持 PackageType 枚举对象和字符串
        if package_type:
            # 如果是枚举对象，获取其 value 属性
            pkg_type_str = package_type.value if hasattr(package_type, 'value') else str(package_type)
            if pkg_type_str.lower() == 'plugin':
                return f"UE{version}"
        
        # 其他类型（资产包、项目等）显示向上兼容标识
        return f"UE{version}+"
