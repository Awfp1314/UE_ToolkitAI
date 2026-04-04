# -*- coding: utf-8 -*-

"""
添加资产对话框
"""

from pathlib import Path
from typing import List, Optional, Tuple
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QLineEdit, QComboBox, QFileDialog, QWidget, QMenu, QSizePolicy
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QPoint
from PyQt6.QtGui import QMouseEvent, QCursor
import logging
import re
import unicodedata

from ..logic.asset_model import AssetType, PackageType
from ..utils.ue_version_detector import UEVersionDetector
from ..utils.archive_extractor import ArchiveExtractor, ARCHIVE_EXTENSIONS
from ..utils.asset_structure_analyzer import AssetStructureAnalyzer, StructureType
from .custom_checkbox import CustomCheckBox
from core.logger import get_logger
from core.utils.custom_widgets import NoContextMenuLineEdit
from ui.dialogs.feedback_dialog import FeedbackDialog

logger = get_logger(__name__)


def _normalize_asset_name(name: str, fallback: str = "") -> str:
    """统一清理资产名称（用于表单预填和批量模式）"""
    if not name:
        return fallback or name

    cleaned = str(name).strip()
    if not cleaned:
        return fallback or cleaned

    # 统一字符形态，尽量减少奇怪编码符号影响
    cleaned = unicodedata.normalize("NFKC", cleaned)

    # 去掉压缩包扩展名
    cleaned = re.sub(r'(\.zip|\.rar|\.7z|\.tar\.gz|\.tar)$', '', cleaned, flags=re.IGNORECASE)

    # 非法路径字符替换为空格
    cleaned = re.sub(r'[<>:"/\\|?*]', ' ', cleaned)

    # 连续分隔符归一化
    cleaned = re.sub(r'[\s._-]+', ' ', cleaned).strip()

    # 尾部噪声：复制后缀 / 版本号 / 日期时间 / 批次序号
    tail_patterns = [
        r'\s*[\(（]\s*\d+\s*[\)）]\s*$',
        r'\s*[\(（]\s*(copy|副本|拷贝|final|最终版)\s*[\)）]\s*$',
        r'\s*[-_ ]\s*(copy|副本|拷贝|final|最终版)\s*$',
        r'\s*[-_ ]\s*v?\d+(?:\.\d+){0,3}\s*$',
        r'\s*[-_ ]\s*(ver|version|版本)\s*\d+(?:\.\d+){0,3}\s*$',
        r'\s*[-_ ]\s*\d{8}(?:[-_ ]?\d{4,6})?\s*$',
        r'\s*[-_ ]\s*\d{4}[-_/]\d{1,2}[-_/]\d{1,2}(?:[ T_-]?\d{1,2}[:._-]?\d{1,2}(?:[:._-]?\d{1,2})?)?\s*$',
    ]

    changed = True
    while changed and cleaned:
        old = cleaned
        for p in tail_patterns:
            cleaned = re.sub(p, '', cleaned, flags=re.IGNORECASE).strip()
        cleaned = re.sub(r'[\s._-]+', ' ', cleaned).strip()
        changed = cleaned != old

    # 乱码兜底：包含替换字符时优先回退
    if '�' in cleaned:
        cleaned = ''

    # 最后再做一次非法字符清理
    cleaned = re.sub(r'[<>:"/\\|?*]', '_', cleaned)
    cleaned = re.sub(r'_+', '_', cleaned).strip(' _.-')

    if not cleaned:
        cleaned = (fallback or "NewAsset").strip()

    return cleaned


class BatchAddThread(QThread):
    """批量添加资产线程"""
    progress = pyqtSignal(int, int, str)  # current, total, message
    asset_added = pyqtSignal(str)  # asset_name
    all_done = pyqtSignal(int, int)  # success_count, fail_count
    
    def __init__(self, controller, batch_files: list, first_asset_settings: dict, parent=None):
        super().__init__(parent)
        self.controller = controller
        self.batch_files = batch_files
        self.first_asset_settings = first_asset_settings
        self._stop_flag = False
    
    def stop(self):
        """停止批量添加"""
        self._stop_flag = True
    
    def run(self):
        """执行批量添加"""
        success_count = 0
        fail_count = 0
        total = len(self.batch_files)
        
        for i, (file_path, asset_type, is_archive) in enumerate(self.batch_files):
            if self._stop_flag:
                logger.info("批量添加被用户取消")
                break
            
            try:
                # 更新进度
                asset_name = _normalize_asset_name(file_path.stem, fallback=file_path.stem)
                self.progress.emit(i + 1, total, asset_name)
                
                # 检测资产的 package_type 和引擎版本
                package_type = PackageType.CONTENT  # 默认值
                engine_version = ''
                archive_content_path = None
                archive_temp_dir = None
                archive_extractor = None
                plugin_folder_name = None
                
                if is_archive:
                    # 压缩包：需要先解压并分析
                    try:
                        from ..utils.archive_extractor import ArchiveExtractor
                        from ..utils.asset_structure_analyzer import AssetStructureAnalyzer, StructureType
                        
                        archive_extractor = ArchiveExtractor()
                        user_password = self.first_asset_settings.get('password', '')
                        default_password = '虚幻4资源站'
                        
                        # 先尝试用户密码（如果提供了），否则直接用默认密码
                        archive_temp_dir = None
                        extract_failed = False
                        try:
                            password_to_use = user_password if user_password else default_password
                            archive_temp_dir = archive_extractor.extract(
                                file_path,
                                password=password_to_use
                            )
                        except RuntimeError as e:
                            error_msg = str(e)
                            if error_msg in ('PASSWORD_REQUIRED', 'PASSWORD_INCORRECT'):
                                # 如果用户提供了密码但失败了，尝试默认密码
                                if user_password and user_password != default_password:
                                    logger.info(f"用户密码失败，尝试默认密码: {file_path.name}")
                                    try:
                                        archive_temp_dir = archive_extractor.extract(
                                            file_path,
                                            password=default_password
                                        )
                                        logger.info(f"✓ 使用默认密码解压成功: {file_path.name}")
                                    except Exception as e2:
                                        logger.error(f"✗ 默认密码也失败: {file_path.name}, {e2}")
                                        extract_failed = True
                                else:
                                    # 默认密码也失败了
                                    logger.error(f"✗ 默认密码失败: {file_path.name}")
                                    extract_failed = True
                            else:
                                raise
                        
                        # 如果解压失败，跳过该文件
                        if extract_failed:
                            fail_count += 1
                            self.error_occurred.emit(f"资源包 {file_path.name} 无法解压")
                            continue
                        
                        if archive_temp_dir:
                            analyzer = AssetStructureAnalyzer()
                            analysis = analyzer.analyze(archive_temp_dir)
                            
                            # 根据分析结果确定类型
                            if analysis.structure_type == StructureType.UE_PROJECT:
                                package_type = PackageType.PROJECT
                            elif analysis.structure_type == StructureType.UE_PLUGIN:
                                package_type = PackageType.PLUGIN
                            elif analysis.structure_type == StructureType.CONTENT_PACKAGE:
                                package_type = PackageType.CONTENT
                            elif analysis.structure_type == StructureType.MODEL_FILES:
                                package_type = PackageType.MODEL
                            else:
                                package_type = PackageType.OTHERS
                            
                            logger.info(f"[批量添加] 分析结果: structure_type={analysis.structure_type}, package_type={package_type}, display_name={package_type.display_name}")
                            
                            # 获取引擎版本
                            if analysis.engine_version:
                                engine_version = analysis.engine_version
                            
                            # 获取实际内容路径（总是使用解压后的路径）
                            archive_content_path = analysis.asset_root if analysis.asset_root else archive_temp_dir
                            if not analysis.asset_root:
                                logger.warning(f"分析器未返回 asset_root，使用临时目录: {archive_temp_dir}")
                            
                            # 插件类型：获取插件文件夹名
                            if package_type == PackageType.PLUGIN and analysis.asset_root:
                                plugin_folder_name = analysis.asset_root.name
                            
                            logger.info(f"批量添加：检测到 {file_path.name} 类型为 {package_type.display_name}，版本 {engine_version}")
                    except Exception as e:
                        logger.warning(f"批量添加：分析压缩包失败，使用默认类型: {e}")
                        # 清理失败的解压
                        if archive_extractor and archive_temp_dir:
                            try:
                                archive_extractor.cleanup(archive_temp_dir)
                            except:
                                pass
                        archive_extractor = None
                        archive_temp_dir = None
                else:
                    # 文件夹：直接分析
                    try:
                        from ..utils.asset_structure_analyzer import AssetStructureAnalyzer, StructureType
                        
                        analyzer = AssetStructureAnalyzer()
                        analysis = analyzer.analyze(file_path)
                        
                        if analysis.structure_type == StructureType.UE_PROJECT:
                            package_type = PackageType.PROJECT
                        elif analysis.structure_type == StructureType.UE_PLUGIN:
                            package_type = PackageType.PLUGIN
                        elif analysis.structure_type == StructureType.CONTENT_PACKAGE:
                            package_type = PackageType.CONTENT
                        elif analysis.structure_type == StructureType.MODEL_FILES:
                            package_type = PackageType.MODEL
                        else:
                            package_type = PackageType.OTHERS
                        
                        # 获取引擎版本
                        if analysis.engine_version:
                            engine_version = analysis.engine_version
                        
                        # 插件类型：获取插件文件夹名
                        if package_type == PackageType.PLUGIN:
                            plugin_folder_name = file_path.name
                        
                        logger.info(f"批量添加：检测到 {file_path.name} 类型为 {package_type.display_name}，版本 {engine_version}")
                    except Exception as e:
                        logger.warning(f"批量添加：分析文件夹失败，使用默认类型: {e}")
                
                # 构建资产信息
                asset_info = {
                    'path': file_path,
                    'type': asset_type,
                    'name': asset_name,
                    'category': self.first_asset_settings['category'],
                    'create_doc': self.first_asset_settings['create_doc'],
                    'engine_version': engine_version,
                    'package_type': package_type,
                    'is_archive': is_archive,
                    'original_source_path': file_path,
                    'password': self.first_asset_settings.get('password', ''),
                }
                
                # 如果是压缩包，传递解压后的路径
                if archive_content_path:
                    asset_info['archive_content_path'] = archive_content_path
                    asset_info['archive_temp_dir'] = archive_temp_dir
                    asset_info['archive_extractor'] = archive_extractor
                    # 转移所有权，不在这里清理
                    archive_extractor = None
                    archive_temp_dir = None
                
                # 如果是插件，传递插件文件夹名
                if plugin_folder_name:
                    asset_info['plugin_folder_name'] = plugin_folder_name
                
                # 创建进度回调函数，将进度转发到信号
                def progress_callback(current, total, message):
                    # 转发到 progress 信号（用于更新 UI）
                    self.progress.emit(current, total, f"{asset_name}: {message}")
                
                # 添加资产（同步调用，带进度回调）
                success = self.controller.add_asset_sync(asset_info, progress_callback=progress_callback)
                
                if success:
                    success_count += 1
                    self.asset_added.emit(asset_name)
                    logger.info(f"✓ 成功添加资产 ({i+1}/{total}): {asset_name}")
                else:
                    fail_count += 1
                    logger.error(f"✗ 添加资产失败 ({i+1}/{total}): {asset_name}")
                    # 添加失败，清理临时文件
                    if archive_extractor and archive_temp_dir:
                        try:
                            archive_extractor.cleanup(archive_temp_dir)
                        except Exception as e:
                            logger.warning(f"清理临时文件失败: {e}")
            
            except Exception as e:
                fail_count += 1
                logger.error(f"✗ 添加资产异常 ({i+1}/{total}): {file_path.name}, {e}", exc_info=True)
                # 异常时清理临时文件
                if 'archive_extractor' in locals() and archive_extractor and 'archive_temp_dir' in locals() and archive_temp_dir:
                    try:
                        archive_extractor.cleanup(archive_temp_dir)
                    except:
                        pass
        
        # 完成
        self.all_done.emit(success_count, fail_count)
    
    @staticmethod
    def _clean_asset_name(name: str) -> str:
        """清理资产名称"""
        return _normalize_asset_name(name, fallback=name)


class ArchiveAnalysisThread(QThread):
    """压缩包异步解压+分析线程"""
    progress = pyqtSignal(str)  # 状态消息
    analysis_done = pyqtSignal(dict)  # 分析结果
    analysis_failed = pyqtSignal(str)  # 失败原因
    password_required = pyqtSignal()  # 需要密码
    password_incorrect = pyqtSignal()  # 密码错误
    
    def __init__(self, archive_path: Path, password: str = "", parent=None):
        super().__init__(parent)
        self.archive_path = archive_path
        self.password = password
        self.extractor = None
        self.temp_dir = None
    
    def run(self):
        try:
            from ..utils.archive_extractor import ArchiveExtractor
            from ..utils.asset_structure_analyzer import AssetStructureAnalyzer, StructureType
            
            # Phase 1: 解压
            self.progress.emit("正在解压压缩包...")
            self.extractor = ArchiveExtractor()
            
            try:
                self.temp_dir = self.extractor.extract(
                    self.archive_path,
                    progress_callback=lambda c, t, m: self.progress.emit(m),
                    password=self.password if self.password else None
                )
            except RuntimeError as e:
                error_msg = str(e)
                if error_msg == "PASSWORD_REQUIRED":
                    self.password_required.emit()
                    return
                elif error_msg == "PASSWORD_INCORRECT":
                    self.password_incorrect.emit()
                    return
                elif error_msg == "MISSING_7Z_EXE":
                    self.analysis_failed.emit("7z 文件使用了不支持的压缩方法，且未找到 7-Zip 程序。\n请安装 7-Zip: https://www.7-zip.org/")
                    return
                else:
                    raise
            
            if not self.temp_dir:
                self.analysis_failed.emit("解压失败，文件可能损坏")
                return
            
            # Phase 2: 分析结构
            self.progress.emit("正在分析资产结构...")
            analyzer = AssetStructureAnalyzer()
            analysis = analyzer.analyze(self.temp_dir)
            
            if analysis.structure_type == StructureType.UNKNOWN:
                self.analysis_failed.emit("无法识别资产类型，未找到 UE 资产或 Content 文件夹")
                return
            
            # Phase 3: 检测引擎版本
            self.progress.emit("正在检测引擎版本...")
            # 优先使用分析结果中的版本（从 .uplugin/.uproject 读取）
            engine_version = analysis.engine_version or ""
            # 如果分析结果没有版本，才从 .uasset 文件检测
            if not engine_version:
                detect_path = analysis.content_root or analysis.asset_root
                if detect_path and detect_path.exists():
                    try:
                        detector = UEVersionDetector(logger)
                        engine_version = detector.detect_asset_min_version(detect_path) or ""
                    except Exception:
                        pass
            
            # 返回结果
            self.analysis_done.emit({
                "structure_type": analysis.structure_type.value,
                "content_root": str(analysis.content_root) if analysis.content_root else None,
                "asset_root": str(analysis.asset_root) if analysis.asset_root else None,
                "suggested_name": analysis.suggested_name,
                "engine_version": engine_version,
                "description": analysis.description,
                "warnings": analysis.warnings,
                "ue_asset_count": analysis.ue_asset_count,
                "temp_dir": str(self.temp_dir),
            })
            
        except Exception as e:
            logger.error(f"压缩包分析线程出错: {e}", exc_info=True)
            self.analysis_failed.emit(f"分析出错: {e}")


class AddAssetDialog(QDialog):
    """添加资产对话框"""
    
    @staticmethod
    def clean_asset_name(name: str) -> str:
        """清理资产名称，去除序号/版本/时间等尾部噪声"""
        return _normalize_asset_name(name, fallback=name)
    
    def __init__(self, existing_asset_names: List[str], categories: List[str], 
                 prefill_path: Optional[str] = None, prefill_type: Optional[AssetType] = None,
                 prefill_category: Optional[str] = None, prefill_name: Optional[str] = None,
                 prefill_analysis: Optional[dict] = None,
                 is_archive: bool = False, 
                 batch_mode: bool = False, batch_files: Optional[list] = None,
                 parent=None):
        """初始化对话框
        
        Args:
            existing_asset_names: 已存在的资产名称列表
            categories: 已有的分类列表
            prefill_path: 预填充的资产路径（可选）
            prefill_type: 预填充的资产类型（可选）
            prefill_category: 预填充的分类（可选）
            prefill_name: 预填充的资产名称（可选）
            is_archive: 是否为压缩包（可选）
            batch_mode: 是否为批量模式（可选）
            batch_files: 批量文件列表 [(file_path, asset_type, is_archive), ...]（可选）
            parent: 父组件
        """
        super().__init__(parent)
        
        self.existing_asset_names = existing_asset_names
        self.categories = categories
        self.asset_path = None
        self.asset_type = None
        self.prefill_path = prefill_path
        self.prefill_type = prefill_type
        self.prefill_category = prefill_category
        self.prefill_name = prefill_name
        self.prefill_analysis = prefill_analysis or {}
        self.drag_position = QPoint()
        self.engine_version = ""
        self._is_archive = is_archive  # 在 init_ui 之前设置
        self._archive_content_path = None  # 解压后的 Content 路径（预分析结果）
        self._archive_temp_dir = None       # 临时解压目录
        self._archive_extractor = None      # 解压器实例（用于清理）
        self._analysis_thread = None        # 分析线程
        self._original_source_path = None   # 原始源路径（用于删除确认）
        self._plugin_folder_name = ""       # 插件原始文件夹名（压缩包解压后获取）
        self.version_detector = UEVersionDetector(logger)
        
        # 批量模式相关
        self.batch_mode = batch_mode
        self.batch_files = batch_files or []  # [(file_path, asset_type, is_archive), ...]
        self.current_batch_index = 0
        self.first_asset_settings = None  # 第一个资产的设置（用于批量添加）
        self.batch_added_assets = []  # 已添加的资产列表
        
        self.init_ui()
    
    def init_ui(self):
        """初始化UI"""
        self.setModal(True)
        self.setFixedSize(550, 620)  # 高度适配内容区域，避免超出主窗口
        
        # 无边框
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        
        # 设置ObjectName
        self.setObjectName("AddAssetDialog")
        
        # 主容器
        container = QWidget()
        container.setObjectName("AddAssetDialogContainer")
        
        main_layout = QVBoxLayout()
        main_layout.setSpacing(0)
        main_layout.setContentsMargins(0, 0, 0, 0)
        
        # 标题栏
        self.title_bar = QWidget()
        self.title_bar.setObjectName("AddAssetDialogTitleBar")
        self.title_bar.setFixedHeight(50)
        title_bar_layout = QHBoxLayout()
        title_bar_layout.setContentsMargins(20, 0, 20, 0)
        
        title_icon = QLabel("📦")
        title_icon.setObjectName("AddAssetDialogTitleIcon")
        title_bar_layout.addWidget(title_icon)
        
        # 批量模式：显示进度
        if self.batch_mode:
            title_text = f"批量添加资产 ({self.current_batch_index + 1}/{len(self.batch_files)})"
        else:
            title_text = "添加资产"
        
        self.title_label = QLabel(title_text)
        self.title_label.setObjectName("AddAssetDialogTitleLabel")
        title_bar_layout.addWidget(self.title_label)
        title_bar_layout.addStretch()
        
        self.title_bar.setLayout(title_bar_layout)
        main_layout.addWidget(self.title_bar)
        
        # 内容区域
        content_widget = QWidget()
        content_widget.setObjectName("AddAssetDialogContent")
        content_layout = QVBoxLayout()
        content_layout.setContentsMargins(30, 20, 30, 25)
        content_layout.setSpacing(12)
        
        # 资产名称
        name_label = QLabel("资产名称")
        name_label.setObjectName("AddAssetDialogLabel")
        content_layout.addWidget(name_label)
        
        self.name_input = NoContextMenuLineEdit()
        self.name_input.setObjectName("AddAssetDialogInput")
        self.name_input.setPlaceholderText("输入资产名称...")
        self.name_input.setMinimumHeight(38)
        self.name_input.textChanged.connect(self._on_name_changed)
        content_layout.addWidget(self.name_input)
        
        # 资产分类
        category_label = QLabel("资产分类")
        category_label.setObjectName("AddAssetDialogLabel")
        content_layout.addWidget(category_label)
        
        category_row = QHBoxLayout()
        self.category_combo = QComboBox()
        self.category_combo.setObjectName("AddAssetDialogCombo")
        self.category_combo.setEditable(False)
        self.category_combo.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.category_combo.setMinimumHeight(38)
        self.category_combo.addItems(self.categories if self.categories else ["默认分类"])
        self.category_combo.setCurrentText("默认分类")
        self.category_combo.setMinimumWidth(180)
        self.category_combo.setMaximumWidth(280)
        category_row.addWidget(self.category_combo)
        category_row.addStretch()
        content_layout.addLayout(category_row)
        
        # 引擎版本（只读）
        version_label = QLabel("引擎版本")
        version_label.setObjectName("AddAssetDialogLabel")
        content_layout.addWidget(version_label)

        self.version_display = QLabel("--")
        self.version_display.setObjectName("AddAssetDialogReadOnlyValue")
        self.version_display.setMinimumHeight(36)
        self.version_display.setAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)
        content_layout.addWidget(self.version_display)

        # 资产类型
        type_label = QLabel("资产类型")
        type_label.setObjectName("AddAssetDialogLabel")
        content_layout.addWidget(type_label)

        # 类型选择下拉框（可手动修改）
        self.type_combo = QComboBox()
        self.type_combo.setObjectName("AddAssetDialogCombo")
        self.type_combo.setMinimumHeight(38)
        self.type_combo.addItems(["资产包", "UE 项目", "UE 插件", "3D 模型", "其他资源"])
        self.type_combo.setEditable(False)
        self.type_combo.setCurrentIndex(0)
        content_layout.addWidget(self.type_combo)

        # 识别反馈入口
        self.feedback_hint_label = QLabel("版本或者资产类型识别有误？点击反馈")
        self.feedback_hint_label.setObjectName("AddAssetDialogHint")
        content_layout.addWidget(self.feedback_hint_label)

        self.feedback_btn = QPushButton("反馈")
        self.feedback_btn.setObjectName("AddAssetDialogBrowseBtn")
        self.feedback_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.feedback_btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.feedback_btn.setFixedSize(100, 34)
        self.feedback_btn.clicked.connect(self._on_feedback_clicked)
        content_layout.addWidget(self.feedback_btn, 0, Qt.AlignmentFlag.AlignLeft)

        # 隐藏路径输入（保留内部字段兼容旧逻辑）
        self.path_display = NoContextMenuLineEdit()
        self.path_display.setObjectName("AddAssetDialogPathInput")
        self.path_display.setVisible(False)
        content_layout.addWidget(self.path_display)

        # 选项
        self.create_doc_checkbox = CustomCheckBox("自动创建说明文档")
        self.create_doc_checkbox.setObjectName("AddAssetDialogCheckbox")
        self.create_doc_checkbox.setChecked(False)
        content_layout.addWidget(self.create_doc_checkbox)
        
        # 错误提示
        self.error_label = QLabel("")
        self.error_label.setObjectName("AddAssetDialogErrorLabel")
        self.error_label.setWordWrap(True)
        self.error_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.error_label.setMaximumHeight(60)
        self.error_label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.error_label.hide()
        content_layout.addWidget(self.error_label)
        
        content_layout.addStretch()
        
        # 按钮区域
        button_layout = QHBoxLayout()
        button_layout.setSpacing(10)
        button_layout.addStretch()
        
        # 批量模式：添加"全部添加"按钮
        if self.batch_mode:
            self.batch_add_all_btn = QPushButton("全部添加")
            self.batch_add_all_btn.setObjectName("AddAssetDialogAddBtn")
            self.batch_add_all_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            self.batch_add_all_btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            self.batch_add_all_btn.setFixedSize(100, 40)
            self.batch_add_all_btn.clicked.connect(self._on_batch_add_all_clicked)
            button_layout.addWidget(self.batch_add_all_btn)
        
        self.add_btn = QPushButton("添加" if not self.batch_mode else "下一个")
        self.add_btn.setObjectName("AddAssetDialogAddBtn")
        self.add_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.add_btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.add_btn.setFixedSize(100, 40)
        self.add_btn.clicked.connect(self._on_add_clicked)
        button_layout.addWidget(self.add_btn)
        
        self.cancel_btn = QPushButton("取消")
        self.cancel_btn.setObjectName("AddAssetDialogCancelBtn")
        self.cancel_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.cancel_btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.cancel_btn.setFixedSize(100, 40)
        self.cancel_btn.clicked.connect(self._on_cancel_clicked)
        button_layout.addWidget(self.cancel_btn)
        
        content_layout.addLayout(button_layout)
        
        content_widget.setLayout(content_layout)
        main_layout.addWidget(content_widget, 1)
        
        container.setLayout(main_layout)
        
        # 对话框布局
        dialog_layout = QVBoxLayout()
        dialog_layout.setContentsMargins(0, 0, 0, 0)
        dialog_layout.addWidget(container)
        self.setLayout(dialog_layout)
        
        # 如果有预填数据，则填充
        if self.prefill_path:
            prefill_path_obj = Path(self.prefill_path)
            self.path_display.setText(self.prefill_path)
            self.asset_path = prefill_path_obj
            self.asset_type = self.prefill_type or AssetType.PACKAGE
            self._original_source_path = prefill_path_obj

            logger.info(f"预填充路径: {self.prefill_path}, 类型: {self.prefill_type}, 是否存在: {prefill_path_obj.exists()}, 是否文件夹: {prefill_path_obj.is_dir()}")

            # 如果有预填名称，使用预填名称（先规范化）
            if self.prefill_name:
                normalized_prefill = self.clean_asset_name(self.prefill_name)
                logger.info(f"[名称设置] 使用预填名称: {normalized_prefill}")
                self.name_input.setText(normalized_prefill)
            else:
                is_archive = self._is_archive or prefill_path_obj.suffix.lower() in ARCHIVE_EXTENSIONS
                auto_name = prefill_path_obj.stem if is_archive else prefill_path_obj.name
                logger.info(f"[名称设置] 初始化: is_archive={is_archive}, auto_name={auto_name}")
                # 如果是压缩包且文件名是 "content"，不设置名称，等待分析结果
                if not (is_archive and auto_name.lower() == 'content'):
                    auto_name = self.clean_asset_name(auto_name)
                    try:
                        logger.info(f"[名称设置] 设置初始名称: {auto_name}")
                        self.name_input.setText(auto_name)
                    except Exception as e:
                        logger.warning(f"文件名编码问题: {e}")
                        self.name_input.setText("NewAsset")
                else:
                    logger.info(f"[名称设置] 跳过 content 压缩包的初始名称设置，等待分析结果")

            # 优先应用外部传入的分析结果，避免重复分析
            if self.prefill_analysis:
                self._apply_prefill_analysis(self.prefill_analysis)
            elif self._is_archive:
                logger.info(f"检测到压缩包，开始分析: {self.asset_path}")
                self._start_archive_analysis(self.asset_path)
            elif prefill_path_obj.exists() and prefill_path_obj.is_dir():
                logger.info(f"检测到文件夹，开始分析: {self.asset_path}")
                self._analyze_folder_on_prefill(self.asset_path)
            else:
                logger.warning(f"未触发分析: _is_archive={self._is_archive}, exists={prefill_path_obj.exists()}, is_dir={prefill_path_obj.is_dir() if prefill_path_obj.exists() else 'path_not_exists'}, path={self.prefill_path}")
        
        # 如果有预填分类，设置默认分类
        if self.prefill_category:
            index = self.category_combo.findText(self.prefill_category)
            if index >= 0:
                self.category_combo.setCurrentIndex(index)
    
    def _on_feedback_clicked(self):
        """打开识别反馈窗口"""
        try:
            dlg = FeedbackDialog(self)
            dlg.exec()
        except Exception as e:
            logger.error(f"打开反馈窗口失败: {e}", exc_info=True)

    def _apply_prefill_analysis(self, analysis: dict):
        """应用外部分析结果，跳过本地重复分析"""
        try:
            self._is_archive = bool(analysis.get("is_archive", self._is_archive))
            self.engine_version = analysis.get("engine_version", "") or ""
            self._package_type = analysis.get("package_type", PackageType.CONTENT)

            resolved_asset_path = analysis.get("resolved_asset_path")
            archive_content_path = analysis.get("archive_content_path")
            archive_temp_dir = analysis.get("archive_temp_dir")
            archive_extractor = analysis.get("archive_extractor")
            plugin_folder_name = analysis.get("plugin_folder_name", "")

            if resolved_asset_path:
                self.asset_path = Path(resolved_asset_path)
                self.path_display.setText(str(self.asset_path))

            if archive_content_path:
                self._archive_content_path = Path(archive_content_path)
            if archive_temp_dir:
                self._archive_temp_dir = Path(archive_temp_dir)
            if archive_extractor:
                self._archive_extractor = archive_extractor
            if plugin_folder_name:
                self._plugin_folder_name = plugin_folder_name

            self._update_type_display()

            if self.engine_version:
                pkg_type_str = self._package_type.value if hasattr(self._package_type, 'value') else str(self._package_type)
                self.version_display.setText(self.version_detector.format_version_badge(self.engine_version, pkg_type_str))
            else:
                self.version_display.setText("未检测到版本")

            logger.info("已应用预分析结果到添加资产表单")
        except Exception as e:
            logger.error(f"应用预分析结果失败: {e}", exc_info=True)

    def mousePressEvent(self, event: QMouseEvent):
        """鼠标按下事件 - 只在标题栏区域响应"""
        if event.button() == Qt.MouseButton.LeftButton:
            # 获取鼠标位置下的控件
            widget = self.childAt(event.pos())
            # 检查是否点击在标题栏或其子控件上
            is_title_bar = False
            if widget:
                # 向上查找父控件，看是否是标题栏
                parent = widget
                while parent and parent != self:
                    if parent == self.title_bar:
                        is_title_bar = True
                        break
                    parent = parent.parentWidget()
            
            if is_title_bar or widget == self.title_bar:
                # 在标题栏上，启用拖动
                self.drag_position = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
                event.accept()
            else:
                # 不在标题栏，不处理，让子控件接收事件
                super().mousePressEvent(event)
    
    def mouseMoveEvent(self, event: QMouseEvent):
        """鼠标移动事件 - 只在拖动标题栏时响应"""
        if event.buttons() == Qt.MouseButton.LeftButton and not self.drag_position.isNull():
            self.move(event.globalPosition().toPoint() - self.drag_position)
            event.accept()
        else:
            super().mouseMoveEvent(event)
    
    def _select_asset_path(self):
        """选择资产路径"""
        menu = QMenu(self)
        menu.setObjectName("AddAssetDialogMenu")
        
        archive_action = menu.addAction("📦 选择压缩包")
        package_action = menu.addAction("📁 选择资源包（文件夹）")
        
        action = menu.exec(QCursor.pos())
        
        if action == archive_action:
            self._select_archive()
        elif action == package_action:
            self._select_package()
    
    def _select_archive(self):
        """选择压缩包文件"""
        file_path, selected_filter = QFileDialog.getOpenFileName(
            self,
            "选择压缩包",
            "",
            "压缩包 (*.zip *.rar *.7z);;所有文件 (*)",
            "压缩包 (*.zip *.rar *.7z)"  # 默认选中压缩包过滤器
        )
        
        if file_path:
            archive_path = Path(file_path)
            
            # 检查是否需要密码
            from ..utils.archive_extractor import ArchiveExtractor
            needs_password = ArchiveExtractor.check_password_required(archive_path)
            
            password = ""
            if needs_password:
                # 先尝试使用缓存的密码
                cached_password = ArchiveExtractor.get_cached_password()
                if cached_password:
                    logger.info("使用缓存的密码")
                    password = cached_password
                else:
                    # 弹出密码输入对话框
                    from .password_dialog import PasswordDialog
                    dialog = PasswordDialog(archive_path.name, parent=self)
                    if dialog.exec() == QDialog.DialogCode.Accepted:
                        password = dialog.get_password()
                    else:
                        # 用户取消
                        return
            
            # 设置路径并开始分析
            self.asset_path = archive_path
            self.asset_type = AssetType.PACKAGE
            self.path_display.setText(str(self.asset_path))
            self._is_archive = True
            self._original_source_path = Path(file_path)
            
            # 自动填充名称（去掉扩展名）
            if not self.name_input.text():
                cleaned_name = self.clean_asset_name(self.asset_path.stem)
                self.name_input.setText(cleaned_name)
            
            logger.info(f"选择了压缩包: {self.asset_path}, 密码: {'有' if password else '无'}")
            
            # 立即开始异步解压+分析，传递密码
            self._start_archive_analysis(self.asset_path, password)
    
    def _analyze_folder_on_prefill(self, folder_path: Path):
        """拖拽文件夹时的分析（与 _select_package 逻辑一致）"""
        try:
            self._cleanup_archive()  # 清理之前的压缩包分析
            self._is_archive = False
            self._original_source_path = folder_path
            
            # 使用 AssetStructureAnalyzer 分析文件夹结构
            from ..utils.asset_structure_analyzer import AssetStructureAnalyzer
            analyzer = AssetStructureAnalyzer()
            analysis_result = analyzer.analyze(folder_path)
            
            # 根据分析结果设置路径和类型
            if analysis_result:
                # 插件和项目必须使用 asset_root（完整目录），否则会只导入 Content
                if analysis_result.structure_type in [StructureType.UE_PLUGIN, StructureType.UE_PROJECT] and analysis_result.asset_root:
                    self.asset_path = analysis_result.asset_root
                elif analysis_result.content_root:
                    self.asset_path = analysis_result.content_root
                elif analysis_result.asset_root:
                    self.asset_path = analysis_result.asset_root
                else:
                    self.asset_path = folder_path
                
                # 映射 StructureType → PackageType
                structure_type = analysis_result.structure_type.value
                pkg_map = {
                    'content_package': PackageType.CONTENT,
                    'ue_project': PackageType.PROJECT,
                    'ue_plugin': PackageType.PLUGIN,
                    'loose_assets': PackageType.OTHERS,
                    'model_files': PackageType.MODEL,
                    'mixed_files': PackageType.OTHERS,
                    'unknown': PackageType.OTHERS,
                }
                self._package_type = pkg_map.get(structure_type, PackageType.OTHERS)
                
                # 使用分析结果的建议名称
                suggested_name = analysis_result.suggested_name
                if suggested_name and not self.name_input.text():
                    cleaned_name = self.clean_asset_name(suggested_name)
                    self.name_input.setText(cleaned_name)
                
                # 保存引擎版本
                if analysis_result.engine_version:
                    self.engine_version = analysis_result.engine_version
                    pkg_type_str = self._package_type.value if hasattr(self._package_type, 'value') else str(self._package_type)
                    version_badge = self.version_detector.format_version_badge(analysis_result.engine_version, pkg_type_str)
                    self.version_display.setText(version_badge)
                    logger.info(f"拖拽检测到引擎版本: {version_badge}")
            else:
                # 分析失败，使用原始路径
                self.asset_path = folder_path
                self._package_type = PackageType.OTHERS
            
            self.asset_type = AssetType.PACKAGE
            self.path_display.setText(str(self.asset_path))
            self._update_type_display()
            
            # 自动填充名称（如果还没有）
            if not self.name_input.text():
                cleaned_name = self.clean_asset_name(self.asset_path.name)
                self.name_input.setText(cleaned_name)
            
            # 检测引擎版本
            self._detect_engine_version()
                
        except Exception as e:
            logger.error(f"文件夹分析失败: {e}", exc_info=True)
            self.asset_path = folder_path
            self._package_type = PackageType.OTHERS
            self.asset_type = AssetType.PACKAGE
            self.path_display.setText(str(self.asset_path))
            self._update_type_display()
            self._detect_engine_version()
    
    def _start_archive_analysis(self, archive_path: Path, password: str = ""):
        """启动异步压缩包解压+分析
        
        Args:
            archive_path: 压缩包路径
            password: 解压密码（可选）
        """
        # 清理之前的分析（如果用户重新选择了压缩包）
        self._cleanup_archive()
        
        # 禁用添加按钮，显示分析状态
        self.add_btn.setEnabled(False)
        self.add_btn.setText("分析中...")
        self.version_display.setText("正在分析压缩包...")
        self.error_label.hide()
        
        # 创建并启动分析线程
        self._analysis_thread = ArchiveAnalysisThread(archive_path, password, self)
        self._analysis_thread.progress.connect(self._on_analysis_progress)
        self._analysis_thread.analysis_done.connect(self._on_analysis_done)
        self._analysis_thread.analysis_failed.connect(self._on_analysis_failed)
        self._analysis_thread.password_required.connect(self._on_password_required)
        self._analysis_thread.password_incorrect.connect(self._on_password_incorrect)
        self._analysis_thread.start()
    
    def _on_password_required(self):
        """需要密码时的处理"""
        from ..utils.archive_extractor import ArchiveExtractor
        from .password_dialog import PasswordDialog
        
        # 先尝试使用缓存的密码
        cached_password = ArchiveExtractor.get_cached_password()
        if cached_password:
            logger.info("尝试使用缓存的密码")
            self._start_archive_analysis(self.asset_path, cached_password)
            return
        
        # 弹出密码输入对话框
        dialog = PasswordDialog(self.asset_path.name, parent=self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            password = dialog.get_password()
            if password:
                # 重新启动分析，带上密码
                self._start_archive_analysis(self.asset_path, password)
        else:
            # 用户取消
            self.add_btn.setEnabled(True)
            self.add_btn.setText("添加资产")
            self.version_display.setText("已取消")
    
    def _on_password_incorrect(self):
        """密码错误时的处理"""
        from .password_dialog import PasswordDialog
        
        # 弹出密码输入对话框，显示错误提示
        dialog = PasswordDialog(
            self.asset_path.name,
            error_message="密码错误，请输入正确的密码",
            parent=self
        )
        if dialog.exec() == QDialog.DialogCode.Accepted:
            password = dialog.get_password()
            if password:
                # 重新启动分析，带上新密码
                self._start_archive_analysis(self.asset_path, password)
        else:
            # 用户取消
            self.add_btn.setEnabled(True)
            self.add_btn.setText("添加资产")
            self.version_display.setText("已取消")
    
    def _on_analysis_progress(self, message: str):
        """分析进度更新"""
        self.version_display.setText(message)
    
    def _on_analysis_done(self, result: dict):
        """分析完成"""
        logger.info(f"压缩包分析完成: {result['description']}")
        
        # 缓存成功的密码
        if self._analysis_thread and self._analysis_thread.password:
            from ..utils.archive_extractor import ArchiveExtractor
            ArchiveExtractor.set_cached_password(self._analysis_thread.password)
        
        # 保存分析结果
        content_root = result.get('content_root')
        asset_root = result.get('asset_root')
        structure_type = result.get('structure_type')
        # 插件需要传递整个插件目录（asset_root），否则会只复制 Content
        if structure_type == StructureType.UE_PLUGIN.value:
            self._archive_content_path = Path(asset_root) if asset_root else None
            # 保存插件原始文件夹名（从解压后的路径获取）
            if asset_root:
                self._plugin_folder_name = Path(asset_root).name
        else:
            self._archive_content_path = Path(content_root) if content_root else (Path(asset_root) if asset_root else None)
            self._plugin_folder_name = ""
        self._archive_temp_dir = Path(result['temp_dir'])
        
        # 映射 StructureType → PackageType
        structure_type = result.get('structure_type', '')
        pkg_map = {
            'content_package': PackageType.CONTENT,
            'ue_project': PackageType.PROJECT,
            'ue_plugin': PackageType.PLUGIN,
            'loose_assets': PackageType.OTHERS,
            'model_files': PackageType.MODEL,
            'mixed_files': PackageType.OTHERS,
            'unknown': PackageType.OTHERS,
        }
        self._package_type = pkg_map.get(structure_type, PackageType.CONTENT)
        self._update_type_display()
        
        # 保存解压器引用用于后续清理
        if self._analysis_thread and self._analysis_thread.extractor:
            self._archive_extractor = self._analysis_thread.extractor
        
        # 自动填充名称（如果用户没有手动修改）
        suggested_name = result.get('suggested_name', '')
        current_name = self.name_input.text().strip()
        
        # 对于压缩包，优先使用原始文件名，不使用分析器推断的名称
        # 因为分析器可能从临时解压目录推断出不准确的名称
        # 但如果压缩包文件名是 "content"，则使用分析器推断的名称
        if self._is_archive and self._original_source_path:
            # 保持使用压缩包原始文件名（去掉扩展名）
            if not current_name or current_name == self.asset_path.stem:
                original_name = self._original_source_path.stem
                logger.info(f"[名称设置] 压缩包原始文件名: {original_name}, suggested_name: {suggested_name}")
                # 如果压缩包文件名是 "content"，必须使用分析器推断的名称
                if original_name.lower() == 'content':
                    if suggested_name:
                        cleaned_name = self.clean_asset_name(suggested_name)
                        logger.info(f"[名称设置] content 压缩包使用 suggested_name: {cleaned_name}")
                    else:
                        # 如果分析器也没有推断出名称，使用默认值
                        cleaned_name = "UnnamedAsset"
                        logger.warning(f"[名称设置] content 压缩包但 suggested_name 为空，使用默认值: {cleaned_name}")
                else:
                    cleaned_name = self.clean_asset_name(original_name)
                    logger.info(f"[名称设置] 使用压缩包原始文件名: {cleaned_name}")
                self.name_input.setText(cleaned_name)
        elif suggested_name and self.asset_path and current_name == self.asset_path.stem:
            # 非压缩包情况，使用分析结果的建议名称
            cleaned_name = self.clean_asset_name(suggested_name)
            self.name_input.setText(cleaned_name)
        
        # 填充引擎版本
        engine_version = result.get('engine_version', '')
        if engine_version:
            self.engine_version = engine_version
            pkg_type_str = self._package_type.value if hasattr(self._package_type, 'value') else str(self._package_type)
            version_badge = self.version_detector.format_version_badge(engine_version, pkg_type_str)
            self.version_display.setText(version_badge)
        else:
            self.engine_version = ""
            self.version_display.setText("未检测到版本")
        
        # 显示警告（如果有）
        if result.get('warnings'):
            warnings_text = '\n'.join(result['warnings'])
            self.error_label.setText(f"⚠️ {warnings_text}")
            self.error_label.setStyleSheet("color: #e6a817;")
            self.error_label.show()
        
        # 恢复添加按钮
        self.add_btn.setEnabled(True)
        self.add_btn.setText("添加")
    
    def _on_analysis_failed(self, error_msg: str):
        """分析失败"""
        logger.error(f"压缩包分析失败: {error_msg}")
        
        self.version_display.setText("分析失败")
        self.error_label.setText(f"❌ {error_msg}")
        self.error_label.setStyleSheet("")
        self.error_label.show()
        
        # 恢复添加按钮（但清除压缩包标记，让用户重新选择）
        self.add_btn.setEnabled(True)
        self.add_btn.setText("添加")
        self._is_archive = False
        self._archive_content_path = None
    
    def _cleanup_archive(self):
        """清理压缩包临时资源"""
        if self._archive_extractor and self._archive_temp_dir:
            try:
                self._archive_extractor.cleanup(self._archive_temp_dir)
                logger.info("已清理压缩包临时目录")
            except Exception as e:
                logger.warning(f"清理临时目录失败: {e}")
        self._archive_content_path = None
        self._archive_temp_dir = None
        self._archive_extractor = None
    
    def _select_package(self):
        """选择资源包"""
        dir_path = QFileDialog.getExistingDirectory(
            self,
            "选择资源包文件夹",
            "",
            QFileDialog.Option.ShowDirsOnly
        )
        
        if dir_path:
            self._cleanup_archive()  # 清理之前的压缩包分析
            self._is_archive = False
            selected_path = Path(dir_path)
            self._original_source_path = selected_path
            
            # 使用 AssetStructureAnalyzer 分析文件夹结构
            from ..utils.asset_structure_analyzer import AssetStructureAnalyzer
            analyzer = AssetStructureAnalyzer()
            analysis_result = analyzer.analyze(selected_path)
            
            # 根据分析结果设置路径和类型
            if analysis_result:
                # 插件和项目必须使用 asset_root（完整目录），否则会只导入 Content
                if analysis_result.structure_type in [StructureType.UE_PLUGIN, StructureType.UE_PROJECT] and analysis_result.asset_root:
                    self.asset_path = analysis_result.asset_root
                elif analysis_result.content_root:
                    self.asset_path = analysis_result.content_root
                elif analysis_result.asset_root:
                    self.asset_path = analysis_result.asset_root
                else:
                    self.asset_path = selected_path
                
                # 映射 StructureType → PackageType
                structure_type = analysis_result.structure_type.value
                pkg_map = {
                    'content_package': PackageType.CONTENT,
                    'ue_project': PackageType.PROJECT,
                    'ue_plugin': PackageType.PLUGIN,
                    'loose_assets': PackageType.OTHERS,
                    'model_files': PackageType.MODEL,
                    'mixed_files': PackageType.OTHERS,
                    'unknown': PackageType.OTHERS,
                }
                self._package_type = pkg_map.get(structure_type, PackageType.OTHERS)
                
                # 使用分析结果的建议名称
                suggested_name = analysis_result.suggested_name
                if suggested_name and not self.name_input.text():
                    cleaned_name = self.clean_asset_name(suggested_name)
                    self.name_input.setText(cleaned_name)
                
                # 保存引擎版本
                if analysis_result.engine_version:
                    self.engine_version = analysis_result.engine_version
                    pkg_type_str = self._package_type.value if hasattr(self._package_type, 'value') else str(self._package_type)
                    version_badge = self.version_detector.format_version_badge(analysis_result.engine_version, pkg_type_str)
                    self.version_display.setText(version_badge)
                    logger.info(f"选择文件夹检测到引擎版本: {version_badge}")
            else:
                # 分析失败，使用原始路径
                self.asset_path = selected_path
                self._package_type = PackageType.OTHERS
            
            self.asset_type = AssetType.PACKAGE
            self.path_display.setText(str(self.asset_path))
            self._update_type_display()
            
            # 自动填充名称（如果还没有）
            if not self.name_input.text():
                cleaned_name = self.clean_asset_name(self.asset_path.name)
                self.name_input.setText(cleaned_name)
            
            # 检测引擎版本
            self._detect_engine_version()
    
    def _detect_folder_package_type(self, folder_path: Path) -> PackageType:
        """从文件夹结构自动推断 PackageType
        
        检测优先级：
        1. 有 .uproject → PROJECT
        2. 有 .uplugin → PLUGIN
        3. 有 Content/ 且含 .uasset → CONTENT
        4. 其余 → OTHERS
        """
        try:
            # 检查 .uproject
            uproject_files = list(folder_path.rglob("*.uproject"))
            if uproject_files:
                return PackageType.PROJECT
            
            # 检查 .uplugin
            uplugin_files = list(folder_path.rglob("*.uplugin"))
            if uplugin_files:
                return PackageType.PLUGIN
            
            # 检查 Content 文件夹（大小写不敏感）
            for item in folder_path.iterdir():
                if item.is_dir() and item.name.lower() == 'content':
                    # 检查是否含 UE 资产
                    ue_assets = list(item.rglob("*.uasset")) + list(item.rglob("*.umap"))
                    if ue_assets:
                        return PackageType.CONTENT
            
            # 检查根目录是否直接有 .uasset（Content 本身被选中的情况）
            if folder_path.name.lower() == 'content':
                ue_assets = list(folder_path.rglob("*.uasset")) + list(folder_path.rglob("*.umap"))
                if ue_assets:
                    return PackageType.CONTENT
            
            return PackageType.OTHERS
        except Exception as e:
            logger.warning(f"检测文件夹类型失败: {e}")
            return PackageType.OTHERS
    
    def _update_type_display(self):
        """更新资产类型显示"""
        pkg_type = getattr(self, '_package_type', None)
        if not pkg_type:
            self.type_combo.setCurrentIndex(0)
            return

        type_index_map = {
            PackageType.CONTENT: 0,
            PackageType.PROJECT: 1,
            PackageType.PLUGIN: 2,
            PackageType.MODEL: 3,
            PackageType.OTHERS: 4,
        }
        index = type_index_map.get(pkg_type, 0)
        self.type_combo.setCurrentIndex(index)
    
    def _select_file(self):
        """选择资源文件"""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "选择资产文件",
            "",
            "所有文件 (*);;模型文件 (*.fbx *.obj *.gltf *.glb *.dae *.stl *.pmx *.pmd *.blend *.ma *.mb);;贴图文件 (*.png *.jpg *.tga *.bmp)"
        )
        
        if file_path:
            self._cleanup_archive()  # 清理之前的压缩包分析
            self._is_archive = False
            self.asset_path = Path(file_path)
            self.asset_type = AssetType.FILE
    
    def _detect_engine_version(self):
        """检测资产的引擎版本"""
        if not self.asset_path:
            return
        
        try:
            # 显示分析中的提示
            self.version_display.setText("正在分析版本...")
            
            version = self.version_detector.detect_asset_min_version(self.asset_path)
            if version:
                self.engine_version = version
                pkg_type_str = self._package_type.value if hasattr(self._package_type, 'value') else str(self._package_type)
                version_badge = self.version_detector.format_version_badge(version, pkg_type_str)
                self.version_display.setText(version_badge)
                logger.info(f"检测到引擎版本: {version_badge}")
            else:
                self.engine_version = ""
                self.version_display.setText("未检测到版本")
                logger.warning(f"无法检测引擎版本: {self.asset_path}")
        except Exception as e:
            logger.error(f"版本检测失败: {e}", exc_info=True)
            self.engine_version = ""
            self.version_display.setText("检测失败")
    
    def _on_name_changed(self, text):
        """名称改变时隐藏错误提示"""
        if text:
            self.error_label.hide()
    
    def validate_input(self) -> Tuple[bool, str]:
        """验证输入
        
        Returns:
            (是否有效, 错误信息)
        """
        if not self.asset_path:
            return False, "请先选择资产路径"
        
        name = self.name_input.text().strip()
        if not name:
            return False, "资产名称不能为空"
        
        if name in self.existing_asset_names:
            return False, f"资产名称 \"{name}\" 已存在，请使用其他名称"
        
        # 如果是 OTHERS 类型，验证文件夹是否包含有效文件
        if hasattr(self, '_package_type') and self._package_type == PackageType.OTHERS:
            if not self._validate_others_folder():
                return False, "文件夹中没有找到有效的资源文件（图片、视频、音频、模型等），请选择包含资源文件的文件夹"
        
        return True, ""
    
    def _validate_others_folder(self) -> bool:
        """验证 OTHERS 类型文件夹是否包含有效文件
        
        Returns:
            True: 包含有效文件
            False: 不包含有效文件
        """
        # 如果是压缩包且已解压，检查解压后的路径
        if self._is_archive and self._archive_content_path:
            check_path = Path(self._archive_content_path)
        elif self.asset_path:
            check_path = Path(self.asset_path)
        else:
            return False
        
        if not check_path.exists():
            return False
        
        # 定义有效的文件扩展名
        valid_extensions = {
            # 模型
            '.fbx', '.obj', '.gltf', '.glb',  # 通用格式
            '.dae',  # Collada
            '.stl',  # 3D 打印
            '.usd', '.usda', '.usdc', '.usdz',  # USD 格式
            '.abc',  # Alembic
            '.blend',  # Blender
            '.ma', '.mb',  # Maya
            '.max',  # 3ds Max
            '.c4d',  # Cinema 4D
            '.skp',  # SketchUp
            '.3ds',  # 3D Studio
            '.pmx', '.pmd',  # MikuMikuDance (MMD)
            '.x',  # DirectX
            '.ply',  # Polygon File Format
            '.wrl', '.vrml',  # VRML
            # 贴图
            '.png', '.jpg', '.jpeg', '.tga', '.bmp', '.exr', '.hdr', '.tif', '.tiff',
            # 音频
            '.wav', '.mp3', '.ogg', '.flac', '.aac', '.m4a',
            # 视频
            '.mp4', '.avi', '.mov', '.mkv', '.wmv', '.flv', '.webm',
            # UE 资产
            '.uasset', '.umap', '.uexp', '.ubulk'
        }
        
        # 递归扫描文件夹
        for item in check_path.rglob('*'):
            if item.is_file():
                ext = item.suffix.lower()
                if ext in valid_extensions:
                    return True
                # 检查是否是嵌套的压缩包
                if ext == '.zip':
                    return True
        
        return False
    
    def _on_add_clicked(self):
        """点击添加按钮"""
        logger.info("点击添加按钮")
        
        valid, error_msg = self.validate_input()
        if not valid:
            self.error_label.setText(f"❌ {error_msg}")
            self.error_label.show()
            return
        
        # 批量模式：处理"下一个"逻辑
        if self.batch_mode:
            # 保存第一个资产的设置（如果还没保存）
            if self.first_asset_settings is None:
                self.first_asset_settings = {
                    'category': self.category_combo.currentText().strip(),
                    'create_doc': self.create_doc_checkbox.isChecked(),
                    'password': getattr(self, '_archive_password', ''),
                }
                logger.info(f"保存第一个资产的设置: {self.first_asset_settings}")
            
            # 添加当前资产
            if not self._add_current_asset():
                return
            
            # 移动到下一个
            self.current_batch_index += 1
            
            if self.current_batch_index < len(self.batch_files):
                # 还有下一个，加载它
                self._load_batch_file(self.current_batch_index)
            else:
                # 全部完成，关闭对话框
                logger.info(f"批量添加完成，共添加 {len(self.batch_added_assets)} 个资产")
                self.accept()
        else:
            # 单个模式：直接关闭
            self.accept()
    
    def get_asset_info(self) -> dict:
        """获取资产信息"""
        # 从下拉框读取用户选择的类型（可能已手动修改）
        index_to_type = {
            0: PackageType.CONTENT,  # "资产包"
            1: PackageType.PROJECT,  # "UE 项目"
            2: PackageType.PLUGIN,   # "UE 插件"
            3: PackageType.MODEL,    # "3D 模型"
            4: PackageType.OTHERS,   # "其他资源"
        }
        selected_package_type = index_to_type.get(
            self.type_combo.currentIndex(),
            getattr(self, "_package_type", PackageType.CONTENT)
        )
        
        info = {
            "path": self.asset_path,
            "type": self.asset_type,
            "name": self.name_input.text().strip(),
            "category": self.category_combo.currentText().strip(),
            "create_doc": self.create_doc_checkbox.isChecked(),
            "engine_version": self.engine_version,
            "package_type": selected_package_type,  # 使用用户选择的类型
            "is_archive": self._is_archive,
            "original_source_path": self._original_source_path,
        }
        
        # 如果是插件类型，传递原始文件夹名称
        if selected_package_type == PackageType.PLUGIN:
            # 优先使用压缩包分析时保存的插件文件夹名
            if hasattr(self, '_plugin_folder_name') and self._plugin_folder_name:
                info["plugin_folder_name"] = self._plugin_folder_name
            # 否则从当前路径获取（文件夹选择的情况）
            elif self.asset_path:
                info["plugin_folder_name"] = self.asset_path.name
        
        # 如果是压缩包且已完成预分析，传递预解压的内容路径
        if self._is_archive and self._archive_content_path:
            info["archive_content_path"] = self._archive_content_path
            info["archive_temp_dir"] = self._archive_temp_dir
            info["archive_extractor"] = self._archive_extractor
            # 转移所有权给调用方，dialog 不再清理
            self._archive_extractor = None
            self._archive_temp_dir = None
            self._archive_content_path = None
        
        return info
    
    def showEvent(self, event):
        """显示事件 - 在这里居中显示"""
        super().showEvent(event)
        # 在对话框显示时居中
        self._center_dialog()
        
        # 批量模式：加载第一个文件
        if self.batch_mode and self.batch_files:
            self._load_batch_file(self.current_batch_index)
    
    def _center_dialog(self):
        """左右居中，垂直居中，底部不超出主窗口"""
        self.adjustSize()
        host = self._find_content_stack()

        if host:
            host_global = host.mapToGlobal(host.rect().topLeft())
            x = host_global.x() + (host.width() - self.width()) // 2
            y = host_global.y() + (host.height() - self.height()) // 2

            # 安全边界：确保弹窗不超出 host（content_stack）的上下边界
            host_top = host_global.y()
            host_bottom = host_global.y() + host.height()
            if y < host_top + 10:
                y = host_top + 10
            if y + self.height() > host_bottom - 10:
                y = host_bottom - self.height() - 10

            self.move(x, y)
        else:
            from PyQt6.QtWidgets import QApplication
            screen = QApplication.primaryScreen().availableGeometry()
            x = screen.x() + (screen.width() - self.width()) // 2
            y = screen.y() + (screen.height() - self.height()) // 2
            self.move(x, y)

    def _find_content_stack(self):
        """向上遍历 parent 链，找到 QStackedWidget（右侧 content_stack）"""
        from PyQt6.QtWidgets import QStackedWidget
        w = self.parent()
        while w is not None:
            if isinstance(w, QStackedWidget):
                return w
            w = w.parent()
        return self.parent()
    
    def center_on_parent(self):
        """在父窗口中居中显示（兼容旧调用，直接执行居中）"""
        self._center_dialog()
    
    def reject(self):
        """取消/关闭对话框时清理临时资源"""
        self._cleanup_archive()
        super().reject()
    
    def closeEvent(self, event):
        """窗口关闭事件"""
        self._cleanup_archive()
        super().closeEvent(event)

    # ==================== 批量模式相关方法 ====================
    
    def _load_batch_file(self, index: int):
        """加载批量文件列表中的指定文件
        
        Args:
            index: 文件索引
        """
        if index >= len(self.batch_files):
            logger.warning(f"批量文件索引超出范围: {index}/{len(self.batch_files)}")
            return
        
        file_path, asset_type, is_archive = self.batch_files[index]
        
        logger.info(f"加载批量文件 [{index + 1}/{len(self.batch_files)}]: {file_path}")
        
        # 更新标题
        self.title_label.setText(f"批量添加资产 ({index + 1}/{len(self.batch_files)})")
        
        # 重置状态
        self._is_archive = is_archive
        self.asset_type = asset_type
        self.asset_path = file_path
        self._original_source_path = file_path
        
        # 清理之前的临时文件
        self._cleanup_archive()
        
        # 自动填充名称
        suggested_name = self.clean_asset_name(file_path.stem)
        self.name_input.setText(suggested_name)
        
        # 显示路径
        self.path_display.setText(str(file_path))
        
        # 如果是压缩包，开始分析
        if is_archive:
            logger.info(f"检测到压缩包，开始分析: {file_path}")
            self._start_archive_analysis(file_path)
        # 如果是文件夹，也需要分析
        elif file_path.exists() and file_path.is_dir():
            logger.info(f"检测到文件夹，开始分析: {file_path}")
            self._analyze_folder_on_prefill(file_path)
        
        # 更新按钮状态
        if index == len(self.batch_files) - 1:
            # 最后一个文件，"下一个"按钮改为"添加"
            self.add_btn.setText("添加")
        else:
            self.add_btn.setText("下一个")
    
    def _on_batch_add_all_clicked(self):
        """批量添加所有剩余资产"""
        try:
            # 验证第一个资产的输入
            is_valid, error_msg = self.validate_input()
            if not is_valid:
                from .message_dialog import MessageDialog
                MessageDialog("输入错误", error_msg, "warning", parent=self).exec()
                return
            
            # 保存第一个资产的设置
            if self.first_asset_settings is None:
                self.first_asset_settings = {
                    'category': self.category_combo.currentText().strip(),
                    'create_doc': self.create_doc_checkbox.isChecked(),
                    'password': getattr(self, '_archive_password', ''),
                }
                logger.info(f"保存第一个资产的设置: {self.first_asset_settings}")
            
            logger.info(f"开始批量添加 {len(self.batch_files)} 个资产")
            
            # 创建批量添加进度对话框
            from .batch_add_progress_dialog import BatchAddProgressDialog
            progress_dialog = BatchAddProgressDialog(len(self.batch_files), self.parent())
            
            # 创建并启动批量添加线程
            batch_thread = BatchAddThread(
                self.parent().controller if self.parent() else None,
                self.batch_files,
                self.first_asset_settings,
                self
            )
            
            # 连接信号
            batch_thread.progress.connect(progress_dialog.update_progress)
            batch_thread.all_done.connect(lambda s, f: progress_dialog.show_complete(s, f))
            
            # 停止按钮连接
            def on_stop_clicked():
                from .confirm_dialog import ConfirmDialog
                dialog = ConfirmDialog(
                    "确认停止",
                    "确定要停止批量添加吗？",
                    "已添加的资产不会被删除。",
                    progress_dialog
                )
                if hasattr(dialog, 'center_on_parent'):
                    dialog.center_on_parent()
                if dialog.exec() == QDialog.DialogCode.Accepted:
                    batch_thread.stop()
                    progress_dialog.accept()
            
            progress_dialog.stop_btn.clicked.connect(on_stop_clicked)
            
            # 启动线程
            batch_thread.start()
            
            # 关闭添加资产对话框
            self.accept()
            
            # 显示进度对话框（模态）
            progress_dialog.exec()
        
        except Exception as e:
            logger.error(f"启动批量添加失败: {e}", exc_info=True)
            from .message_dialog import MessageDialog
            MessageDialog("错误", f"启动批量添加失败: {e}", "error", parent=self).exec()
    
    def _on_cancel_clicked(self):
        """取消按钮点击处理"""
        # 正常取消
        self.reject()
    
    def _add_current_asset(self) -> bool:
        """添加当前资产
        
        Returns:
            bool: 成功返回 True
        """
        try:
            # 验证输入
            is_valid, error_msg = self.validate_input()
            if not is_valid:
                from .message_dialog import MessageDialog
                MessageDialog("输入错误", error_msg, "warning", parent=self).exec()
                return False
            
            # 获取资产信息
            asset_info = self.get_asset_info()
            
            # 添加资产（同步）
            return self._add_asset_sync(asset_info)
        
        except Exception as e:
            logger.error(f"添加当前资产失败: {e}", exc_info=True)
            return False
    
    def _add_asset_sync(self, asset_info: dict) -> bool:
        """同步添加资产
        
        Args:
            asset_info: 资产信息
            
        Returns:
            bool: 成功返回 True
        """
        try:
            # 这里需要调用父窗口的添加方法
            # 由于是同步操作，我们需要直接调用 logic 层
            if self.parent():
                parent = self.parent()
                if hasattr(parent, 'controller') and hasattr(parent.controller, 'add_asset_sync'):
                    success = parent.controller.add_asset_sync(asset_info)
                    if success:
                        self.batch_added_assets.append(asset_info['name'])
                        logger.info(f"成功添加资产: {asset_info['name']}")
                        return True
                    else:
                        logger.error(f"添加资产失败: {asset_info['name']}")
                        return False
            
            logger.warning("无法找到父窗口的 controller，跳过添加")
            return False
        
        except Exception as e:
            logger.error(f"同步添加资产失败: {e}", exc_info=True)
            return False
