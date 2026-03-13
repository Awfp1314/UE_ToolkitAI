# -*- coding: utf-8 -*-

"""
添加资产对话框
"""

from pathlib import Path
from typing import List, Optional, Tuple
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, 
    QLineEdit, QComboBox, QFileDialog, QCheckBox, QWidget, QMenu, QSizePolicy
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QPoint
from PyQt6.QtGui import QMouseEvent, QCursor
import logging
import re

from ..logic.asset_model import AssetType, PackageType
from ..utils.ue_version_detector import UEVersionDetector
from ..utils.archive_extractor import ArchiveExtractor, ARCHIVE_EXTENSIONS
from ..utils.asset_structure_analyzer import AssetStructureAnalyzer, StructureType
from .custom_checkbox import CustomCheckBox
from core.logger import get_logger
from core.utils.custom_widgets import NoContextMenuLineEdit

logger = get_logger(__name__)


class ArchiveAnalysisThread(QThread):
    """压缩包异步解压+分析线程"""
    progress = pyqtSignal(str)  # 状态消息
    analysis_done = pyqtSignal(dict)  # 分析结果
    analysis_failed = pyqtSignal(str)  # 失败原因
    
    def __init__(self, archive_path: Path, parent=None):
        super().__init__(parent)
        self.archive_path = archive_path
        self.extractor = None
        self.temp_dir = None
    
    def run(self):
        try:
            from ..utils.archive_extractor import ArchiveExtractor
            from ..utils.asset_structure_analyzer import AssetStructureAnalyzer, StructureType
            
            # Phase 1: 解压
            self.progress.emit("正在解压压缩包...")
            self.extractor = ArchiveExtractor()
            
            self.temp_dir = self.extractor.extract(
                self.archive_path,
                progress_callback=lambda c, t, m: self.progress.emit(f"解压: {m}")
            )
            
            if not self.temp_dir:
                self.analysis_failed.emit("解压失败，文件可能损坏或有密码保护")
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
        """清理资产名称，去除括号数字和其他杂乱符号
        
        例如：
        - "女鬼(1).zip" -> "女鬼"
        - "MyAsset (2)" -> "MyAsset"
        - "Asset_v2 (Copy)" -> "Asset_v2"
        - "Test - Copy (3)" -> "Test"
        """
        if not name:
            return name
        
        # 先去除常见的文件复制后缀模式和扩展名
        patterns = [
            r'\s*\(\d+\)$',           # 匹配 (1), (2), (3) 等
            r'\s*\(副本\)$',          # 匹配 (副本)
            r'\s*\(Copy\)$',          # 匹配 (Copy)
            r'\s*-\s*副本$',          # 匹配 - 副本
            r'\s*-\s*Copy$',          # 匹配 - Copy
            r'\s*_copy$',             # 匹配 _copy
            r'\s*_副本$',             # 匹配 _副本
            r'(\.zip|\.rar|\.7z|\.tar\.gz|\.tar)$',  # 压缩包扩展名
        ]
        
        cleaned = name
        for pattern in patterns:
            cleaned = re.sub(pattern, '', cleaned, flags=re.IGNORECASE)
        
        # 去除首尾空格
        cleaned = cleaned.strip()
        
        # 如果清理后为空，返回原名称
        return cleaned if cleaned else name
    
    def __init__(self, existing_asset_names: List[str], categories: List[str], 
                 prefill_path: Optional[str] = None, prefill_type: Optional[AssetType] = None,
                 prefill_category: Optional[str] = None, prefill_name: Optional[str] = None, 
                 is_archive: bool = False, parent=None):
        """初始化对话框
        
        Args:
            existing_asset_names: 已存在的资产名称列表
            categories: 已有的分类列表
            prefill_path: 预填充的资产路径（可选）
            prefill_type: 预填充的资产类型（可选）
            prefill_category: 预填充的分类（可选）
            prefill_name: 预填充的资产名称（可选）
            is_archive: 是否为压缩包（可选）
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
        
        self.init_ui()
    
    def init_ui(self):
        """初始化UI"""
        self.setModal(True)
        self.setFixedSize(550, 680)  # 增加高度，为警告提示预留空间
        
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
        
        title_label = QLabel("添加资产")
        title_label.setObjectName("AddAssetDialogTitleLabel")
        title_bar_layout.addWidget(title_label)
        title_bar_layout.addStretch()
        
        self.title_bar.setLayout(title_bar_layout)
        main_layout.addWidget(self.title_bar)
        
        # 内容区域
        content_widget = QWidget()
        content_widget.setObjectName("AddAssetDialogContent")
        content_layout = QVBoxLayout()
        content_layout.setContentsMargins(30, 20, 30, 25)
        content_layout.setSpacing(12)
        
        # 资产路径选择
        path_label = QLabel("资产路径")
        path_label.setObjectName("AddAssetDialogLabel")
        content_layout.addWidget(path_label)
        
        path_row = QHBoxLayout()
        path_row.setSpacing(10)
        
        self.path_display = NoContextMenuLineEdit()
        self.path_display.setObjectName("AddAssetDialogPathInput")
        self.path_display.setPlaceholderText("请选择资产路径...")
        self.path_display.setReadOnly(True)
        self.path_display.setMinimumHeight(38)
        path_row.addWidget(self.path_display, 1)
        
        browse_btn = QPushButton("浏览")
        browse_btn.setObjectName("AddAssetDialogBrowseBtn")
        browse_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        browse_btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        browse_btn.setFixedHeight(38)
        browse_btn.clicked.connect(self._select_asset_path)
        path_row.addWidget(browse_btn)
        
        content_layout.addLayout(path_row)
        
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
        
        # 引擎版本
        version_label = QLabel("引擎版本")
        version_label.setObjectName("AddAssetDialogLabel")
        content_layout.addWidget(version_label)
        
        self.version_display = NoContextMenuLineEdit()
        self.version_display.setObjectName("AddAssetDialogInput")
        self.version_display.setPlaceholderText("选择路径后自动检测...")
        self.version_display.setReadOnly(True)
        self.version_display.setMinimumHeight(38)
        content_layout.addWidget(self.version_display)
        
        # 导入类型
        type_label = QLabel("导入类型")
        type_label.setObjectName("AddAssetDialogLabel")
        content_layout.addWidget(type_label)
        
        # 类型选择下拉框（可手动修改）
        self.type_combo = QComboBox()
        self.type_combo.setObjectName("AddAssetDialogInput")
        self.type_combo.setMinimumHeight(38)
        self.type_combo.addItems(["Content 资产包", "UE 项目", "UE 插件", "其他资源"])
        self.type_combo.setEditable(False)
        self.type_combo.setEnabled(False)  # 默认禁用，检测后启用
        self.type_combo.setCurrentIndex(-1)  # 默认不选中，待检测
        content_layout.addWidget(self.type_combo)
        
        # 类型提示
        self.type_hint = QLabel("💡 选择资产路径后自动检测")
        self.type_hint.setObjectName("AddAssetDialogHint")
        content_layout.addWidget(self.type_hint)
        
        # 选项
        self.create_doc_checkbox = CustomCheckBox("自动创建说明文档")
        self.create_doc_checkbox.setObjectName("AddAssetDialogCheckbox")
        self.create_doc_checkbox.setChecked(True)
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
        
        self.add_btn = QPushButton("添加")
        self.add_btn.setObjectName("AddAssetDialogAddBtn")
        self.add_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.add_btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.add_btn.setFixedSize(100, 40)
        self.add_btn.clicked.connect(self._on_add_clicked)
        button_layout.addWidget(self.add_btn)
        
        cancel_btn = QPushButton("取消")
        cancel_btn.setObjectName("AddAssetDialogCancelBtn")
        cancel_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        cancel_btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        cancel_btn.setFixedSize(100, 40)
        cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(cancel_btn)
        
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
            self.asset_type = self.prefill_type
            self._original_source_path = prefill_path_obj
            
            logger.info(f"预填充路径: {self.prefill_path}, 类型: {self.prefill_type}, 是否存在: {prefill_path_obj.exists()}, 是否文件夹: {prefill_path_obj.is_dir()}")
            
            # 如果有预填名称，使用预填名称
            if self.prefill_name:
                self.name_input.setText(self.prefill_name)
            # 如果有预填路径但没有预填名称，自动填充名称
            else:
                is_archive = self._is_archive or prefill_path_obj.suffix.lower() in ARCHIVE_EXTENSIONS
                if self.prefill_type == AssetType.FILE or is_archive:
                    auto_name = prefill_path_obj.stem
                else:
                    auto_name = prefill_path_obj.name
                # 清理文件名，去除括号数字等杂乱符号
                auto_name = self.clean_asset_name(auto_name)
                # 使用 UTF-8 编码处理文件名，避免乱码
                try:
                    self.name_input.setText(auto_name)
                except Exception as e:
                    logger.warning(f"文件名编码问题: {e}")
                    self.name_input.setText("NewAsset")
            
            # 如果是压缩包（从拖放识别），立即开始分析
            if self._is_archive:
                logger.info(f"检测到压缩包，开始分析: {self.asset_path}")
                self._start_archive_analysis(self.asset_path)
            # 如果是文件夹（从拖放识别），也需要分析
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
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "选择压缩包",
            "",
            "压缩包 (*.zip *.rar *.7z);;所有文件 (*)"
        )
        
        if file_path:
            self.asset_path = Path(file_path)
            self.asset_type = AssetType.PACKAGE
            self.path_display.setText(str(self.asset_path))
            self._is_archive = True
            self._original_source_path = Path(file_path)
            
            # 自动填充名称（去掉扩展名）
            if not self.name_input.text():
                cleaned_name = self.clean_asset_name(self.asset_path.stem)
                self.name_input.setText(cleaned_name)
            
            logger.info(f"选择了压缩包: {self.asset_path}")
            
            # 立即开始异步解压+分析
            self._start_archive_analysis(self.asset_path)
    
    def _analyze_folder_on_prefill(self, folder_path: Path):
        """拖拽文件夹时的分析（与 _select_package 逻辑一致）"""
        try:
            # 使用 AssetStructureAnalyzer 分析文件夹结构
            from ..utils.asset_structure_analyzer import AssetStructureAnalyzer
            analyzer = AssetStructureAnalyzer()
            analysis_result = analyzer.analyze(folder_path)
            
            # 根据分析结果设置路径和类型
            if analysis_result:
                # 插件必须使用 asset_root（插件根目录），否则会只导入 Content
                if analysis_result.structure_type == StructureType.UE_PLUGIN and analysis_result.asset_root:
                    self.asset_path = analysis_result.asset_root
                elif analysis_result.content_root:
                    self.asset_path = analysis_result.content_root
                elif analysis_result.asset_root:
                    self.asset_path = analysis_result.asset_root
                
                # 更新路径显示
                self.path_display.setText(str(self.asset_path))
                
                # 映射 StructureType → PackageType
                structure_type = analysis_result.structure_type.value
                pkg_map = {
                    'content_package': PackageType.CONTENT,
                    'ue_project': PackageType.PROJECT,
                    'ue_plugin': PackageType.PLUGIN,
                    'loose_assets': PackageType.OTHERS,
                    'raw_3d_files': PackageType.OTHERS,
                    'mixed_files': PackageType.OTHERS,
                    'unknown': PackageType.OTHERS,
                }
                self._package_type = pkg_map.get(structure_type, PackageType.OTHERS)
                self._update_type_display()
                
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
                    # 如果分析结果没有版本，尝试手动检测
                    self._detect_engine_version()
            else:
                # 分析失败，尝试手动检测版本
                self._package_type = PackageType.OTHERS
                self._update_type_display()
                self._detect_engine_version()
                
        except Exception as e:
            logger.error(f"文件夹分析失败: {e}", exc_info=True)
            self._package_type = PackageType.OTHERS
            self._update_type_display()
            self._detect_engine_version()
    
    def _start_archive_analysis(self, archive_path: Path):
        """启动异步压缩包解压+分析"""
        # 清理之前的分析（如果用户重新选择了压缩包）
        self._cleanup_archive()
        
        # 禁用添加按钮，显示分析状态
        self.add_btn.setEnabled(False)
        self.add_btn.setText("分析中...")
        self.version_display.setText("正在分析压缩包...")
        self.error_label.hide()
        
        # 创建并启动分析线程
        self._analysis_thread = ArchiveAnalysisThread(archive_path, self)
        self._analysis_thread.progress.connect(self._on_analysis_progress)
        self._analysis_thread.analysis_done.connect(self._on_analysis_done)
        self._analysis_thread.analysis_failed.connect(self._on_analysis_failed)
        self._analysis_thread.start()
    
    def _on_analysis_progress(self, message: str):
        """分析进度更新"""
        self.version_display.setText(message)
    
    def _on_analysis_done(self, result: dict):
        """分析完成"""
        logger.info(f"压缩包分析完成: {result['description']}")
        
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
            'raw_3d_files': PackageType.OTHERS,
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
        # 如果当前名称是压缩包文件名（未手动修改），用分析结果替换
        if suggested_name and self.asset_path and current_name == self.asset_path.stem:
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
                # 插件必须使用 asset_root（插件根目录），否则会只导入 Content
                if analysis_result.structure_type == StructureType.UE_PLUGIN and analysis_result.asset_root:
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
                    'raw_3d_files': PackageType.OTHERS,
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
        """更新导入类型显示"""
        pkg_type = getattr(self, '_package_type', None)
        if not pkg_type:
            # 未检测到类型，保持未选中状态
            self.type_combo.setCurrentIndex(-1)
            self.type_combo.setEnabled(False)
            self.type_hint.setText("💡 选择资产路径后自动检测")
            return
        
        # 映射 PackageType 到下拉框索引
        type_index_map = {
            PackageType.CONTENT: 0,  # "Content 资产包"
            PackageType.PROJECT: 1,  # "UE 项目"
            PackageType.PLUGIN: 2,   # "UE 插件"
            PackageType.OTHERS: 3,   # "其他资源"
        }
        index = type_index_map.get(pkg_type, 0)
        self.type_combo.setCurrentIndex(index)
        
        # 检测完成后启用下拉框，允许用户手动修改
        self.type_combo.setEnabled(True)
        self.type_hint.setText("💡 自动检测，如有误可手动选择")
    
    def _select_file(self):
        """选择资源文件"""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "选择资产文件",
            "",
            "所有文件 (*);;模型文件 (*.fbx *.obj *.gltf);;贴图文件 (*.png *.jpg *.tga *.bmp)"
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
        
        return True, ""
    
    def _on_add_clicked(self):
        """点击添加按钮"""
        logger.info("点击添加按钮")
        
        valid, error_msg = self.validate_input()
        if not valid:
            self.error_label.setText(f"❌ {error_msg}")
            self.error_label.show()
            return
        
        self.accept()
    
    def get_asset_info(self) -> dict:
        """获取资产信息"""
        # 从下拉框读取用户选择的类型（可能已手动修改）
        index_to_type = {
            0: PackageType.CONTENT,  # "Content 资产包"
            1: PackageType.PROJECT,  # "UE 项目"
            2: PackageType.PLUGIN,   # "UE 插件"
            3: PackageType.OTHERS,   # "其他资源"
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
    
    def _center_dialog(self):
        """居中对话框"""
        if self.parent():
            # 获取父窗口
            parent = self.parent()
            
            # 需要向上查找到顶层窗口
            top_window = parent
            while top_window.parent():
                top_window = top_window.parent()
            
            # 获取顶层窗口的全局位置和大小
            parent_geo = top_window.geometry()
            parent_pos = top_window.pos()
            
            # 获取对话框大小
            dialog_width = self.width()
            dialog_height = self.height()
            
            # 计算居中位置（全局坐标）
            x = parent_pos.x() + (parent_geo.width() - dialog_width) // 2
            y = parent_pos.y() + (parent_geo.height() - dialog_height) // 2
            
            self.move(x, y)
        else:
            # 如果没有父窗口，居中到屏幕
            from PyQt6.QtWidgets import QApplication
            screen = QApplication.primaryScreen().availableGeometry()
            x = screen.x() + (screen.width() - self.width()) // 2
            y = screen.y() + (screen.height() - self.height()) // 2
            self.move(x, y)
    
    def center_on_parent(self):
        """在父窗口中居中显示（兼容旧调用）"""
        # 这个方法保留以兼容现有调用，但实际居中在showEvent中完成
        pass
    
    def reject(self):
        """取消/关闭对话框时清理临时资源"""
        self._cleanup_archive()
        super().reject()
    
    def closeEvent(self, event):
        """窗口关闭事件"""
        self._cleanup_archive()
        super().closeEvent(event)
