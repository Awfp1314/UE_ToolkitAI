"""
UE版本检测工具类

提供检测UE资产和工程版本的功能
"""

import struct
from pathlib import Path
from typing import List, Optional, Tuple
from logging import Logger

# 最多抽样检测的 uasset 文件数量
_SAMPLE_LIMIT = 20

# UE4 FileVersionUE4 -> 版本字符串映射表（下界，含）
# 来源：UE 源码 EUnrealEngineObjectUE4Version
_UE4_VERSION_MAP: List[Tuple[int, str]] = [
    (522, "4.27"),
    (520, "4.26"),
    (517, "4.25"),
    (516, "4.24"),
    (513, "4.23"),
    (510, "4.22"),
    (508, "4.21"),
    (504, "4.20"),
    (498, "4.19"),
    (491, "4.18"),
    (484, "4.17"),
    (482, "4.16"),
    (476, "4.15"),
    (472, "4.14"),
    (466, "4.13"),
    (459, "4.12"),
    (452, "4.11"),
    (444, "4.10"),
    (436, "4.9"),
    (352, "4.8"),
    (342, "4.7"),
    (0,   "4.0"),
]

# UE5 EUnrealEngineObjectUE5Version 下界映射
# UE5.0=1000, UE5.1=1001, UE5.2=1002, UE5.3=1003, UE5.4=1004, UE5.5=1005
_UE5_VERSION_MAP: List[Tuple[int, str]] = [
    (1005, "5.5"),
    (1004, "5.4"),
    (1003, "5.3"),
    (1002, "5.2"),
    (1001, "5.1"),
    (1000, "5.0"),
]


def _map_file_version(file_version_ue4: int) -> str:
    """将 FileVersionUE4 整数值映射为版本字符串。"""
    if file_version_ue4 >= 1000:
        for threshold, ver in _UE5_VERSION_MAP:
            if file_version_ue4 >= threshold:
                return ver
        return "5.0"
    for threshold, ver in _UE4_VERSION_MAP:
        if file_version_ue4 >= threshold:
            return ver
    return "4.0"


def _compare_version(a: str, b: str) -> int:
    """比较两个版本字符串，返回 1/-1/0（a>b/a<b/a==b）。"""
    def _parts(v: str) -> Tuple[int, int]:
        try:
            parts = v.split('.')
            major = int(parts[0]) if parts else 0
            minor = int(parts[1]) if len(parts) > 1 else 0
            return major, minor
        except ValueError:
            return 0, 0

    pa, pb = _parts(a), _parts(b)
    if pa > pb:
        return 1
    if pa < pb:
        return -1
    return 0


class UEVersionDetector:
    """UE版本检测器

    提供以下功能：
    - 从 .uasset 文件集合中抽样，取最高版本作为资产最终版本
    - 优先读取 .uproject / .uplugin 的 JSON 版本字段（最权威）
    - 二进制头解析作为主要检测手段
    - UE5 特性扫描作为辅助修正（仅当二进制结果全为 UE4 时触发）
    - 生成版本徽标字符串（如 "UE5.4+"）
    """

    def __init__(self, logger: Optional[Logger] = None):
        """
        Args:
            logger: 日志记录器（可选）
        """
        self._logger = logger

    # ------------------------------------------------------------------
    # 公共接口
    # ------------------------------------------------------------------

    def detect_asset_min_version(self, asset_path: Path) -> str:
        """检测资产的最低引擎版本。

        优先级：
        1. .uproject EngineAssociation（项目类型，最权威）
        2. .uplugin EngineVersion（插件类型，最权威）
        3. 多文件抽样二进制头解析，取最高版本
        4. UE5 特性扫描辅助修正（仅当步骤3全部为 UE4 时）

        Args:
            asset_path: 资产路径（文件或文件夹）

        Returns:
            str: 版本字符串（如 "4.27", "5.4"），检测失败返回空字符串
        """
        if not asset_path.exists():
            return ""

        if asset_path.is_dir():
            # --- 优先级 1：.uproject ---
            for uproject in asset_path.glob("*.uproject"):
                version = self._read_uproject_version(uproject)
                if version:
                    self._log_debug(f"[版本] .uproject 来源: {asset_path.name} -> UE {version}")
                    return version

            # --- 优先级 2：.uplugin（递归，考虑子目录插件）---
            uplugin_files = list(asset_path.rglob("*.uplugin"))
            if uplugin_files:
                # 取最浅层的
                uplugin_files.sort(key=lambda p: len(p.parts))
                version = self._read_uplugin_version(uplugin_files[0])
                if version:
                    self._log_debug(f"[版本] .uplugin 来源: {asset_path.name} -> UE {version}")
                    return version

        # --- 优先级 3：多文件抽样二进制头解析 ---
        uasset_files = self._collect_uasset_samples(asset_path)
        if not uasset_files:
            self._log_warning(f"[版本] 未找到可用 .uasset 文件: {asset_path}")
            return ""

        version = self._detect_by_sampling(uasset_files)

        # --- 优先级 4：UE5 特性辅助修正 ---
        # 只在二进制结果全部为 UE4（或为空）时，才进行特性扫描
        if not version or version.startswith('4.'):
            if self._detect_ue5_features(asset_path):
                old = version or '未知'
                version = "5.0"
                self._log_info(f"[版本] UE5特性修正: {old} -> 5.0 ({asset_path.name})")

        if version:
            self._log_debug(f"[版本] 最终结果: {asset_path.name} -> UE {version}")

        return version

    def format_version_badge(self, version: str, package_type=None) -> str:
        """格式化版本为徽标显示字符串。

        Args:
            version: 版本字符串（如 "4.27", "5.4"）
            package_type: PackageType 枚举或字符串

        Returns:
            str: 如 "UE4.27+"、"UE5.4"（插件无 +）、"UE?"
        """
        if not version:
            return "UE?"

        if package_type:
            pkg_type_str = package_type.value if hasattr(package_type, 'value') else str(package_type)
            if pkg_type_str.lower() == 'plugin':
                return f"UE{version}"

        return f"UE{version}+"

    # ------------------------------------------------------------------
    # 内部：文件收集
    # ------------------------------------------------------------------

    def _collect_uasset_samples(self, asset_path: Path) -> List[Path]:
        """收集用于抽样检测的 .uasset/.umap 文件列表。

        策略：
        - 优先纳入所有 .umap（地图文件通常是版本最高的）
        - 再从 .uasset 中补充，直到达到 _SAMPLE_LIMIT 上限
        - 对 .uasset 按文件大小降序排列（大文件往往是主资产，版本更具代表性）

        Args:
            asset_path: 资产路径（文件或文件夹）

        Returns:
            List[Path]: 待检测文件列表
        """
        if asset_path.is_file():
            if asset_path.suffix in ('.uasset', '.umap'):
                return [asset_path]
            return []

        # 收集所有 .umap（全量，地图文件通常较少）
        umap_files = list(asset_path.rglob("*.umap"))

        # 收集所有 .uasset，按大小降序
        uasset_files = sorted(
            asset_path.rglob("*.uasset"),
            key=lambda p: p.stat().st_size if p.exists() else 0,
            reverse=True
        )

        # 合并：umap 优先，总量不超过 _SAMPLE_LIMIT
        samples: List[Path] = []
        samples.extend(umap_files)
        remaining = _SAMPLE_LIMIT - len(samples)
        if remaining > 0:
            samples.extend(uasset_files[:remaining])

        self._log_debug(
            f"[版本] 抽样 {len(samples)} 个文件 "
            f"({len(umap_files)} umap + {min(len(uasset_files), max(0, remaining))} uasset) "
            f"from {asset_path.name}"
        )
        return samples

    # ------------------------------------------------------------------
    # 内部：多文件抽样，取最高版本
    # ------------------------------------------------------------------

    def _detect_by_sampling(self, uasset_files: List[Path]) -> str:
        """对抽样文件列表逐一读取二进制头，取最高版本。

        Args:
            uasset_files: 待检测文件列表

        Returns:
            str: 最高版本字符串，全部失败返回空字符串
        """
        best_version = ""
        success_count = 0
        fail_count = 0

        for file_path in uasset_files:
            ver = self._read_uasset_version(file_path)
            if ver:
                success_count += 1
                if not best_version or _compare_version(ver, best_version) > 0:
                    best_version = ver
                    self._log_debug(f"[版本] 新高版本: {ver} <- {file_path.name}")
            else:
                fail_count += 1

        self._log_debug(
            f"[版本] 抽样结果: 成功={success_count}, 失败={fail_count}, "
            f"最高版本={best_version or '无'}"
        )
        return best_version

    # ------------------------------------------------------------------
    # 内部：JSON 版本读取
    # ------------------------------------------------------------------

    def _read_uproject_version(self, uproject_file: Path) -> str:
        """从 .uproject 读取 EngineAssociation 版本字段。

        Returns:
            str: 如 "5.4"，GUID 格式或读取失败返回空字符串
        """
        try:
            import json
            with open(uproject_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            engine_assoc = data.get('EngineAssociation', '')
            # GUID 格式如 "{12345678-...}" 无法直接使用
            if engine_assoc and not engine_assoc.startswith('{'):
                return engine_assoc.strip()
        except Exception as e:
            self._log_debug(f"[版本] 读取 .uproject 失败: {uproject_file.name} - {e}")
        return ""

    def _read_uplugin_version(self, uplugin_file: Path) -> str:
        """从 .uplugin 读取 EngineVersion 字段，格式如 "5.4.0" -> "5.4"。

        Returns:
            str: 如 "5.4"，读取失败返回空字符串
        """
        try:
            import json
            with open(uplugin_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            engine_ver = data.get('EngineVersion', '').strip()
            if engine_ver:
                parts = engine_ver.split('.')
                if len(parts) >= 2:
                    return f"{parts[0]}.{parts[1]}"
        except Exception as e:
            self._log_debug(f"[版本] 读取 .uplugin 失败: {uplugin_file.name} - {e}")
        return ""

    # ------------------------------------------------------------------
    # 内部：单文件二进制头解析
    # ------------------------------------------------------------------

    def _read_uasset_version(self, uasset_file: Path) -> str:
        """解析单个 .uasset/.umap 文件的 FPackageFileSummary 头，提取版本号。

        头部布局：
          Tag(4) + LegacyFileVersion(4)
          [+ LegacyUE3Version(4)  -- 仅当 LegacyFileVersion <= -2]
          + FileVersionUE4(4) + ...

        Args:
            uasset_file: 文件路径

        Returns:
            str: 版本字符串，读取失败返回空字符串
        """
        try:
            with open(uasset_file, 'rb') as f:
                # 魔数校验
                tag_bytes = f.read(4)
                if len(tag_bytes) < 4:
                    return ""
                tag = struct.unpack('<I', tag_bytes)[0]
                if tag != 0x9E2A83C1:
                    self._log_debug(
                        f"[版本] 无效魔数 0x{tag:08X}: {uasset_file.name}"
                    )
                    return ""

                # LegacyFileVersion
                legacy_bytes = f.read(4)
                if len(legacy_bytes) < 4:
                    return ""
                legacy_version = struct.unpack('<i', legacy_bytes)[0]

                # 条件跳过 LegacyUE3Version
                if legacy_version <= -2:
                    f.read(4)

                # FileVersionUE4
                fv_bytes = f.read(4)
                if len(fv_bytes) < 4:
                    return ""
                file_version_ue4 = struct.unpack('<i', fv_bytes)[0]

                self._log_debug(
                    f"[版本] 头解析: legacy={legacy_version}, "
                    f"fv_ue4={file_version_ue4} | {uasset_file.name}"
                )

                # 版本映射
                version = _map_file_version(file_version_ue4)
                return version

        except Exception as e:
            self._log_debug(f"[版本] 读取头失败: {uasset_file.name} - {e}")
            return ""

    # ------------------------------------------------------------------
    # 内部：UE5 特性扫描（辅助修正）
    # ------------------------------------------------------------------

    def _detect_ue5_features(self, asset_path: Path) -> bool:
        """扫描文件内容，检测 UE5 专有特性字节串。

        使用较长的、特异性更强的字节串，降低误判率。
        仅作为二进制头解析失败时的辅助修正手段。

        Args:
            asset_path: 资产路径

        Returns:
            bool: 包含 UE5 特性返回 True
        """
        # 特异性较强的 UE5 专有字节串（避免普通资产名误判）
        UE5_SIGNATURES = [
            b'/Script/Lumen',
            b'LumenSceneData',
            b'NaniteVertexFactory',
            b'NaniteResources',
            b'WorldPartitionStreamingPolicy',
            b'/Script/NavigationSystem.WorldPartition',
            b'VirtualShadowMapArray',
            b'HLODLayer',
        ]

        try:
            search_files: List[Path] = []
            if asset_path.is_file():
                search_files = [asset_path]
            else:
                # umap 优先，最多扫 5 个；uasset 补充最多 10 个
                umap_files = list(asset_path.rglob('*.umap'))[:5]
                uasset_files = list(asset_path.rglob('*.uasset'))[:10]
                search_files = umap_files + uasset_files

            for file_path in search_files:
                try:
                    with open(file_path, 'rb') as f:
                        content = f.read(1024 * 1024)  # 最多读 1 MB
                    for sig in UE5_SIGNATURES:
                        if sig in content:
                            self._log_debug(
                                f"[版本] UE5特性命中: {sig.decode('utf-8', errors='replace')}"
                                f" in {file_path.name}"
                            )
                            return True
                except Exception:
                    continue

            return False

        except Exception as e:
            self._log_debug(f"[版本] UE5特性扫描异常: {e}")
            return False

    # ------------------------------------------------------------------
    # 内部：日志辅助
    # ------------------------------------------------------------------

    def _log_debug(self, msg: str) -> None:
        if self._logger:
            self._logger.debug(msg)

    def _log_info(self, msg: str) -> None:
        if self._logger:
            self._logger.info(msg)

    def _log_warning(self, msg: str) -> None:
        if self._logger:
            self._logger.warning(msg)
