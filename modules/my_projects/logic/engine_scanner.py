# -*- coding: utf-8 -*-

"""
引擎扫描器 - 扫描已安装的 UE 引擎版本和模板
"""

import json
import sys
from pathlib import Path
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field

from core.logger import get_logger

logger = get_logger(__name__)


@dataclass
class TemplateInfo:
    """模板信息"""
    name: str  # 显示名称
    folder_name: str  # 文件夹名
    path: Path  # 模板路径
    category: str  # 项目类型：游戏/影视与现场活动/建筑/汽车
    description: str = ""
    thumbnail: Optional[str] = None  # 缩略图路径


@dataclass
class EngineInfo:
    """引擎信息"""
    version: str  # 版本号，如 "5.4"
    install_dir: Path  # 安装目录
    editor_path: Path  # 编辑器可执行文件路径
    templates: List[TemplateInfo] = field(default_factory=list)
    has_starter_content: bool = False
    starter_content_path: Optional[Path] = None


# 模板文件夹名 → (分类, 显示名称) 精确/前缀映射
# 匹配顺序：从上到下，越具体的放前面
_TEMPLATE_MAP = {
    # ── 游戏 ──
    "TP_BlankBP": ("游戏", "空白"),
    "TP_Blank": ("游戏", "空白"),
    "TP_ThirdPersonBP": ("游戏", "第三人称"),
    "TP_ThirdPerson": ("游戏", "第三人称"),
    "TP_FirstPersonBP": ("游戏", "第一人称"),
    "TP_FirstPerson": ("游戏", "第一人称"),
    "TP_TopDownBP": ("游戏", "俯视角"),
    "TP_TopDown": ("游戏", "俯视角"),
    "TP_VehicleAdvBP": ("游戏", "载具"),
    "TP_VehicleAdv": ("游戏", "载具"),
    "TP_VehicleBP": ("游戏", "载具"),
    "TP_Vehicle": ("游戏", "载具"),
    "TP_PuzzleBP": ("游戏", "解谜"),
    "TP_Puzzle": ("游戏", "解谜"),
    "TP_HandheldARBP": ("游戏", "手持AR"),
    "TP_HandheldAR": ("游戏", "手持AR"),
    "TP_2DSideScrollerBP": ("游戏", "2D横版"),
    "TP_2DSideScroller": ("游戏", "2D横版"),
    "TP_TwinStickBP": ("游戏", "双摇杆射击"),
    "TP_TwinStick": ("游戏", "双摇杆射击"),
    "TP_SideScrollerBP": ("游戏", "横版卷轴"),
    "TP_SideScroller": ("游戏", "横版卷轴"),
    "TP_FlyingBP": ("游戏", "飞行"),
    "TP_Flying": ("游戏", "飞行"),
    "TP_RollingBP": ("游戏", "滚球"),
    "TP_Rolling": ("游戏", "滚球"),
    "TP_VirtualRealityBP": ("游戏", "虚拟现实"),
    "TP_VirtualReality": ("游戏", "虚拟现实"),
    "TP_HoloLensBP": ("游戏", "HoloLens"),
    "TP_HoloLens": ("游戏", "HoloLens"),
    "TP_Hololens": ("游戏", "HoloLens"),
    # ── 影视与现场活动 ──
    "TP_InCamVFXBP": ("影视与现场活动", "摄像机内VFX"),
    "TP_InCamVFX": ("影视与现场活动", "摄像机内VFX"),
    "TP_DMXBP": ("影视与现场活动", "DMX"),
    "TP_DMX": ("影视与现场活动", "DMX"),
    "TP_nDisplayBP": ("影视与现场活动", "nDisplay"),
    "TP_nDisplay": ("影视与现场活动", "nDisplay"),
    "TP_CollabViewerBP": ("影视与现场活动", "协作查看器"),
    "TP_CollabViewer": ("影视与现场活动", "协作查看器"),
    "TP_SIM_BlankBP": ("影视与现场活动", "空白"),
    "TP_SIM_Blank": ("影视与现场活动", "空白"),
    # ── 建筑、工程与施工 ──
    "TP_AEC_ArchvisBP": ("建筑、工程与施工", "建筑可视化"),
    "TP_AEC_Archvis": ("建筑、工程与施工", "建筑可视化"),
    "TP_AEC_BlankBP": ("建筑、工程与施工", "空白"),
    "TP_AEC_Blank": ("建筑、工程与施工", "空白"),
    "TP_AEC_CollabBP": ("建筑、工程与施工", "协作查看器"),
    "TP_AEC_Collab": ("建筑、工程与施工", "协作查看器"),
    "TP_AEC_HandheldARBP": ("建筑、工程与施工", "手持AR"),
    "TP_AEC_HandheldAR": ("建筑、工程与施工", "手持AR"),
    "TP_AEC_ProdConfigBP": ("建筑、工程与施工", "产品配置"),
    "TP_AEC_ProdConfig": ("建筑、工程与施工", "产品配置"),
    # ── 汽车、产品设计和制造 ──
    "TP_PhotoStudioBP": ("汽车、产品设计和制造", "摄影棚"),
    "TP_PhotoStudio": ("汽车、产品设计和制造", "摄影棚"),
    "TP_ProductConfigBP": ("汽车、产品设计和制造", "产品配置"),
    "TP_ProductConfig": ("汽车、产品设计和制造", "产品配置"),
    "TP_ME_BlankBP": ("汽车、产品设计和制造", "制造空白"),
    "TP_ME_VProdBP": ("汽车、产品设计和制造", "虚拟制片"),
    "TP_ME_VProd": ("汽车、产品设计和制造", "虚拟制片"),
    "TP_MFG_CollabBP": ("汽车、产品设计和制造", "协作查看器"),
    "TP_MFG_Collab": ("汽车、产品设计和制造", "协作查看器"),
    "TP_MFG_HandheldARBP": ("汽车、产品设计和制造", "手持AR"),
    "TP_MFG_HandheldAR": ("汽车、产品设计和制造", "手持AR"),
    "TP_MFG_ProdConfigBP": ("汽车、产品设计和制造", "产品配置"),
    "TP_MFG_ProdConfig": ("汽车、产品设计和制造", "产品配置"),
}

# 前缀 → 分类 的兜底规则（用于映射表没有精确匹配的模板）
_PREFIX_CATEGORY_MAP = {
    "TP_MFG_": ("汽车、产品设计和制造", "制造"),
    "TP_ME_": ("汽车、产品设计和制造", "制造"),
    "TP_AEC_": ("建筑、工程与施工", "建筑"),
    "TP_SIM_": ("影视与现场活动", "模拟"),
}

# 所有项目类型（保持顺序）
PROJECT_CATEGORIES = [
    "游戏",
    "影视与现场活动",
    "建筑、工程与施工",
    "汽车、产品设计和制造",
]


def _classify_template(folder_name: str) -> Optional[tuple]:
    """根据文件夹名分类模板，返回 (分类, 显示名称) 或 None（跳过未知模板）"""
    # 第一层：精确/前缀匹配映射表
    for prefix, (cat, display) in _TEMPLATE_MAP.items():
        if folder_name.startswith(prefix):
            return cat, display
    # 第二层：宽泛前缀兜底（MFG_、ME_、AEC_、SIM_ 等）
    for prefix, (cat, base_display) in _PREFIX_CATEGORY_MAP.items():
        if folder_name.startswith(prefix):
            # 从文件夹名提取可读名称
            suffix = folder_name[len(prefix):]
            suffix = suffix.rstrip("BP") if suffix.endswith("BP") else suffix
            display = suffix.replace("_", " ").strip() or base_display
            return cat, display
    # 未匹配任何规则 → 返回 None，扫描器会跳过
    return None


class EngineScanner:
    """UE 引擎扫描器"""

    @staticmethod
    def scan_installed_engines() -> List[EngineInfo]:
        """扫描已安装的 UE 引擎版本"""
        engines = []

        if sys.platform != "win32":
            logger.warning("非 Windows 平台，跳过引擎扫描")
            return engines

        # 方法1：从 Windows 注册表读取
        engines = EngineScanner._scan_from_registry()

        # 方法2：从 Epic Games Launcher 配置读取（补充）
        launcher_engines = EngineScanner._scan_from_launcher()
        known_dirs = {str(e.install_dir) for e in engines}
        for e in launcher_engines:
            if str(e.install_dir) not in known_dirs:
                engines.append(e)

        # 按版本号降序排列
        engines.sort(key=lambda e: e.version, reverse=True)

        logger.info(f"扫描到 {len(engines)} 个引擎版本")
        return engines

    @staticmethod
    def _scan_from_registry() -> List[EngineInfo]:
        """从注册表扫描引擎"""
        engines = []
        try:
            import winreg
            key_path = r"SOFTWARE\EpicGames\Unreal Engine"
            try:
                key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, key_path)
            except FileNotFoundError:
                return engines

            i = 0
            while True:
                try:
                    version = winreg.EnumKey(key, i)
                    i += 1
                    try:
                        sub_key = winreg.OpenKey(key, version)
                        install_dir, _ = winreg.QueryValueEx(sub_key, "InstalledDirectory")
                        winreg.CloseKey(sub_key)

                        install_path = Path(install_dir)
                        if install_path.exists():
                            engine = EngineScanner._build_engine_info(version, install_path)
                            if engine:
                                engines.append(engine)
                    except (FileNotFoundError, OSError):
                        pass
                except OSError:
                    break
            winreg.CloseKey(key)
        except ImportError:
            pass
        except Exception as e:
            logger.error(f"注册表扫描失败: {e}")
        return engines

    @staticmethod
    def _scan_from_launcher() -> List[EngineInfo]:
        """从 Epic Games Launcher 配置扫描"""
        engines = []
        try:
            dat_path = Path(r"C:\ProgramData\Epic\UnrealEngineLauncher\LauncherInstalled.dat")
            if not dat_path.exists():
                return engines

            with open(dat_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            for item in data.get("InstallationList", []):
                app_name = item.get("AppName", "")
                install_loc = item.get("InstallLocation", "")

                # UE 引擎的 AppName 通常包含 "UE_"
                if "UE_" in app_name and install_loc:
                    install_path = Path(install_loc)
                    if install_path.exists():
                        # 从 AppName 提取版本号
                        version = app_name.replace("UE_", "")
                        engine = EngineScanner._build_engine_info(version, install_path)
                        if engine:
                            engines.append(engine)
        except Exception as e:
            logger.error(f"Launcher 配置扫描失败: {e}")
        return engines

    @staticmethod
    def _build_engine_info(version: str, install_path: Path) -> Optional[EngineInfo]:
        """构建引擎信息"""
        editor_path = install_path / "Engine" / "Binaries" / "Win64" / "UnrealEditor.exe"
        if not editor_path.exists():
            # 旧版本可能叫 UE4Editor.exe
            editor_path = install_path / "Engine" / "Binaries" / "Win64" / "UE4Editor.exe"
            if not editor_path.exists():
                return None

        engine = EngineInfo(
            version=version,
            install_dir=install_path,
            editor_path=editor_path,
        )

        # 扫描模板
        engine.templates = EngineScanner._scan_templates(install_path)

        # 检查初学者内容包
        starter = install_path / "FeaturePacks" / "StarterContent.upack"
        if starter.exists():
            engine.has_starter_content = True
            engine.starter_content_path = starter

        return engine

    @staticmethod
    def _scan_templates(engine_root: Path) -> List[TemplateInfo]:
        """扫描引擎模板（只扫描 TP_ 前缀的标准模板，BP/非BP去重）"""
        templates_dir = engine_root / "Templates"
        if not templates_dir.exists():
            return []

        # 第一遍：收集所有合法模板文件夹
        raw: Dict[str, Path] = {}  # base_name -> path
        for item in sorted(templates_dir.iterdir()):
            if not item.is_dir() or not item.name.startswith("TP_"):
                continue
            if not list(item.glob("*.uproject")):
                continue
            raw[item.name] = item

        # 第二遍：BP/非BP 去重，优先保留 BP 版本
        seen_bases: Dict[str, str] = {}  # 去掉BP后缀的base → 实际folder_name
        for folder_name in sorted(raw.keys()):
            if folder_name.endswith("BP"):
                base = folder_name[:-2]  # 去掉末尾 "BP"
            else:
                base = folder_name
            if base in seen_bases:
                # 已有同名，优先 BP 版本
                existing = seen_bases[base]
                if folder_name.endswith("BP") and not existing.endswith("BP"):
                    seen_bases[base] = folder_name
                # 否则保留已有的
            else:
                seen_bases[base] = folder_name

        keep = set(seen_bases.values())

        templates = []
        for folder_name, item in raw.items():
            if folder_name not in keep:
                continue

            result = _classify_template(folder_name)
            if result is None:
                # 未知模板，跳过
                logger.debug(f"跳过未识别模板: {folder_name}")
                continue
            category, display_name = result

            # 查找缩略图
            thumb = EngineScanner._find_thumbnail(item, folder_name)

            templates.append(TemplateInfo(
                name=display_name,
                folder_name=folder_name,
                path=item,
                category=category,
                thumbnail=thumb,
            ))

        logger.info(f"扫描到 {len(templates)} 个模板（去重后）")
        return templates

    @staticmethod
    def _find_thumbnail(template_dir: Path, folder_name: str) -> Optional[str]:
        """查找模板缩略图"""
        # 1. 同名 PNG
        png = template_dir / f"{folder_name}.png"
        if png.exists():
            return str(png)
        # 2. Media 目录
        media = template_dir / "Media"
        if media.exists():
            for img in media.glob("*.png"):
                return str(img)
        # 3. 根目录任意 PNG
        for img in template_dir.glob("*.png"):
            return str(img)
        return None
