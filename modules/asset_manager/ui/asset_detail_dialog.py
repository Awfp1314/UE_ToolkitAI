# -*- coding: utf-8 -*-

"""
资产详情对话框
"""

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
    QPushButton, QWidget, QTextEdit
)
from PyQt6.QtCore import Qt, QPoint, pyqtSignal, QRectF, QRect, QTimer, QEvent
from PyQt6.QtGui import QPixmap, QMouseEvent, QPainterPath, QRegion, QPainter
from pathlib import Path
from core.logger import get_logger
import subprocess

logger = get_logger(__name__)


class DocumentTextEdit(QTextEdit):
    """支持双击打开文档的文本编辑框"""
    
    def __init__(self, asset_id: str, library_path: Path = None, parent=None):
        super().__init__(parent)
        self.asset_id = asset_id
        self.library_path = library_path
    
    def mouseDoubleClickEvent(self, event: QMouseEvent):
        """双击事件 - 打开文档"""
        logger.info(f"[文档] 双击打开文档，资产ID: {self.asset_id}")
        
        try:
            # 使用传入的资产库路径
            if not self.library_path:
                logger.warning("[文档] 资产库路径未设置，无法打开文档")
                return
            
            # 构建文档文件路径（先尝试.txt，再尝试.md）
            doc_path_txt = self.library_path / '.asset_config' / 'documents' / f'{self.asset_id}.txt'
            doc_path_md = self.library_path / '.asset_config' / 'documents' / f'{self.asset_id}.md'
            
            # 优先打开.txt文件
            doc_path = doc_path_txt if doc_path_txt.exists() else doc_path_md
            
            if doc_path.exists():
                # 使用系统默认应用打开文档
                import platform
                if platform.system() == 'Windows':
                    subprocess.Popen(['notepad', str(doc_path)])
                elif platform.system() == 'Darwin':  # macOS
                    subprocess.Popen(['open', str(doc_path)])
                else:  # Linux
                    subprocess.Popen(['xdg-open', str(doc_path)])
                logger.info(f"[文档] 已打开文档: {doc_path}")
            else:
                logger.warning(f"[文档] 文档不存在: {doc_path_txt} 或 {doc_path_md}")
        except Exception as e:
            logger.error(f"[文档] 打开文档时出错: {e}", exc_info=True)


class AssetDetailDialog(QDialog):
    """资产详情对话框"""
    
    # 信号
    preview_requested = pyqtSignal(str)  # 预览资产信号
    import_requested = pyqtSignal(str)   # 导入资产信号
    
    def __init__(self, asset_data: dict, library_path: Path = None, parent=None):
        """
        初始化资产详情对话框
        
        Args:
            asset_data: 资产数据字典
            library_path: 资产库路径
            parent: 父窗口
        """
        super().__init__(parent)
        self.asset_data = asset_data
        self.library_path = library_path  # 资产库路径
        self.drag_position = QPoint()
        
        # 设置对话框属性
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setModal(True)
        self.setFixedSize(500, 660)
        
        self._init_ui()
    
    def _init_ui(self):
        """初始化UI"""
        
        # 主容器
        container = QWidget()
        container.setObjectName("AssetDetailContainer")
        
        main_layout = QVBoxLayout()
        main_layout.setSpacing(0)
        main_layout.setContentsMargins(1, 1, 1, 1)  # 留出1px边距以显示容器边框
        
        # 标题栏
        title_bar = self._create_title_bar()
        main_layout.addWidget(title_bar)
        
        # 内容容器
        content_widget = QWidget()
        content_layout = QVBoxLayout(content_widget)
        content_layout.setContentsMargins(25, 15, 25, 15)
        content_layout.setSpacing(15)
        
        # 缩略图
        thumbnail_section = self._create_thumbnail_section()
        content_layout.addWidget(thumbnail_section)
        
        # 资产信息
        info_section = self._create_info_section()
        content_layout.addWidget(info_section)
        
        # 文档区域
        doc_section = self._create_documentation_section()
        content_layout.addWidget(doc_section, 1)
        
        main_layout.addWidget(content_widget, 1)
        
        # 底部按钮
        button_bar = self._create_button_bar()
        main_layout.addWidget(button_bar)
        
        container.setLayout(main_layout)
        
        dialog_layout = QVBoxLayout(self)
        dialog_layout.setContentsMargins(0, 0, 0, 0)
        dialog_layout.addWidget(container)
    
    def _create_title_bar(self) -> QWidget:
        """创建标题栏"""
        title_bar = QWidget()
        title_bar.setObjectName("AssetDetailTitleBar")
        title_bar.setFixedHeight(50)
        
        layout = QHBoxLayout(title_bar)
        layout.setContentsMargins(20, 0, 20, 0)
        
        title_label = QLabel("资产详情")
        title_label.setObjectName("DialogTitle")
        layout.addWidget(title_label)
        
        layout.addStretch()
        
        close_btn = QPushButton("×")
        close_btn.setObjectName("CloseButton")
        close_btn.setFixedSize(36, 36)
        close_btn.clicked.connect(self.reject)
        layout.addWidget(close_btn)
        
        return title_bar
    
    def _create_thumbnail_section(self) -> QWidget:
        """创建缩略图区域"""
        section = QWidget()
        layout = QVBoxLayout(section)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)  # 居中对齐
        
        thumbnail_container = QWidget()
        thumbnail_container.setObjectName("ThumbnailContainer")
        thumbnail_container.setFixedSize(400, 180)  # 固定容器大小与缩略图一致
        
        thumbnail_layout = QVBoxLayout(thumbnail_container)
        thumbnail_layout.setContentsMargins(0, 0, 0, 0)
        thumbnail_layout.setSpacing(0)
        
        self.thumbnail_label = QLabel()
        self.thumbnail_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.thumbnail_label.setFixedSize(400, 180)
        
        # 加载缩略图
        thumbnail_path = self.asset_data.get('thumbnail_path')
        if thumbnail_path and Path(thumbnail_path).exists():
            pixmap = QPixmap(thumbnail_path)
            if not pixmap.isNull():
                target_w, target_h = 400, 180
                
                # 填充裁剪：铺满整个区域
                scaled = pixmap.scaled(target_w, target_h, 
                                      Qt.AspectRatioMode.KeepAspectRatioByExpanding, 
                                      Qt.TransformationMode.SmoothTransformation)
                x = (scaled.width() - target_w) // 2
                y = (scaled.height() - target_h) // 2
                cropped = scaled.copy(x, y, target_w, target_h)
                
                rounded_pixmap = self._create_rounded_pixmap(cropped, 10)
                self.thumbnail_label.setPixmap(rounded_pixmap)
                self.thumbnail_label.setScaledContents(False)
            else:
                self.thumbnail_label.setText("📦")
                self.thumbnail_label.setObjectName("ThumbnailPlaceholder")
        else:
            self.thumbnail_label.setText("📦")
            self.thumbnail_label.setObjectName("ThumbnailPlaceholder")
        
        thumbnail_layout.addWidget(self.thumbnail_label)
        layout.addWidget(thumbnail_container)
        
        return section
    
    def _create_info_section(self) -> QWidget:
        """创建资产信息区域"""
        section = QWidget()
        section.setObjectName("InfoSection")
        layout = QVBoxLayout(section)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(6)
        
        # 直接添加信息行
        layout.addLayout(self._create_info_row("名称", self.asset_data.get('name', '未知')))
        layout.addLayout(self._create_info_row("分类", self.asset_data.get('category', '未分类')))
        
        # 资产类型
        from ..logic.asset_model import PackageType
        package_type = self.asset_data.get('package_type', 'content')
        type_text = "资源包"
        if package_type:
            try:
                if hasattr(package_type, 'display_name'):
                    type_text = package_type.display_name
                elif isinstance(package_type, str):
                    type_text = PackageType(package_type).display_name
            except (ValueError, AttributeError):
                type_text = str(package_type)
        layout.addLayout(self._create_info_row("资产类型", type_text))
        
        # 引擎版本
        from ..utils.ue_version_detector import UEVersionDetector
        version_detector = UEVersionDetector()
        engine_version = self.asset_data.get('engine_min_version', '')
        version_badge = version_detector.format_version_badge(engine_version, package_type) if engine_version else "未知"
        layout.addLayout(self._create_info_row("引擎版本", version_badge))
        
        # 大小
        size = self.asset_data.get('size', 0)
        layout.addLayout(self._create_info_row("大小", self._format_size(size)))
        
        return section
    
    def _create_info_row(self, label: str, value: str) -> QHBoxLayout:
        """创建信息行"""
        row = QHBoxLayout()
        row.setSpacing(12)
        
        label_widget = QLabel(label)
        label_widget.setObjectName("InfoLabel")
        label_widget.setFixedWidth(50)
        row.addWidget(label_widget)
        
        value_widget = QLabel(value)
        value_widget.setObjectName("InfoValue")
        value_widget.setWordWrap(True)
        row.addWidget(value_widget, 1)
        
        return row
    
    def _create_documentation_section(self) -> QWidget:
        """创建文档区域"""
        section = QWidget()
        layout = QVBoxLayout(section)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        
        # 文档标题
        title_label = QLabel("文档（双击打开文档）")
        title_label.setObjectName("DocTitle")
        layout.addWidget(title_label)
        
        # 读取资产文档文件
        documentation = self._load_asset_documentation()
        
        if documentation:
            # 使用自定义DocumentTextEdit实现可滚动文档区域，支持双击打开
            asset_id = self.asset_data.get('id', '')
            doc_text = DocumentTextEdit(asset_id, library_path=self.library_path)
            doc_text.setObjectName("DocText")
            doc_text.setReadOnly(True)
            doc_text.setPlainText(documentation)
            doc_text.setMinimumHeight(120)  # 最小高度，自动填充剩余空间
            doc_text.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
            
            # 动态应用主题样式
            self._apply_doc_text_style(doc_text)
            
            layout.addWidget(doc_text)
        else:
            no_doc = QLabel("暂无文档")
            no_doc.setObjectName("NoDoc")
            layout.addWidget(no_doc)
        
        return section
    
    def _apply_doc_text_style(self, doc_text: QTextEdit):
        """动态应用文档区域样式"""
        try:
            # 简单的主题检测：通过检查应用程序的样式表来判断主题
            from PyQt6.QtWidgets import QApplication
            app_stylesheet = QApplication.instance().styleSheet()
            is_dark_theme = '#1c1c1c' in app_stylesheet or 'rgba(255, 255, 255' in app_stylesheet
            
            # 根据主题获取颜色
            if is_dark_theme:
                bg_color = '#2c2c2c'
                text_color = 'rgba(255, 255, 255, 0.7)'
                scrollbar_track = 'rgba(255, 255, 255, 0.05)'
                scrollbar_thumb = 'rgba(255, 255, 255, 0.2)'
                scrollbar_thumb_hover = 'rgba(255, 255, 255, 0.3)'
                scrollbar_thumb_pressed = 'rgba(255, 255, 255, 0.4)'
            else:  # light theme
                bg_color = '#f5f5f5'
                text_color = 'rgba(0, 0, 0, 0.7)'
                scrollbar_track = 'rgba(0, 0, 0, 0.05)'
                scrollbar_thumb = 'rgba(0, 0, 0, 0.2)'
                scrollbar_thumb_hover = 'rgba(0, 0, 0, 0.3)'
                scrollbar_thumb_pressed = 'rgba(0, 0, 0, 0.4)'
            
            # 应用样式
            doc_text.setStyleSheet(f"""
                QTextEdit {{
                    background: {bg_color};
                    border: none;
                    border-radius: 6px;
                    padding: 10px;
                    color: {text_color};
                    font-size: 12px;
                }}
                QScrollBar:vertical {{
                    background: {scrollbar_track};
                    width: 8px;
                    margin: 0px;
                    border-radius: 4px;
                }}
                QScrollBar::handle:vertical {{
                    background: {scrollbar_thumb};
                    border-radius: 4px;
                    min-height: 20px;
                }}
                QScrollBar::handle:vertical:hover {{
                    background: {scrollbar_thumb_hover};
                }}
                QScrollBar::handle:vertical:pressed {{
                    background: {scrollbar_thumb_pressed};
                }}
                QScrollBar::add-line:vertical,
                QScrollBar::sub-line:vertical {{
                    height: 0px;
                }}
                QScrollBar::add-page:vertical,
                QScrollBar::sub-page:vertical {{
                    background: none;
                }}
            """)
            
        except Exception as e:
            logger.warning(f"应用文档区域样式失败: {e}")
            # 回退到默认样式
            doc_text.setStyleSheet("")
    
    def _load_asset_documentation(self) -> str:
        """加载资产文档内容"""
        asset_id = self.asset_data.get('id', '')
        if not asset_id:
            logger.info("[文档] 资产ID为空，无法加载文档")
            return ''
        
        # 使用传入的资产库路径
        if not self.library_path:
            logger.warning("[文档] 资产库路径未设置，无法加载文档")
            return ''
        
        # 构建文档文件路径（先尝试.txt，再尝试.md）
        doc_path_txt = self.library_path / '.asset_config' / 'documents' / f'{asset_id}.txt'
        doc_path_md = self.library_path / '.asset_config' / 'documents' / f'{asset_id}.md'
        
        logger.info(f"[文档] 尝试加载文档: {doc_path_txt}")
        
        # 优先读取.txt文件
        doc_path = doc_path_txt if doc_path_txt.exists() else doc_path_md
        
        # 读取文档文件
        if doc_path.exists():
            try:
                with open(doc_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                    logger.info(f"[文档] 成功加载文档，长度: {len(content)} 字符")
                    return content
            except Exception as e:
                logger.error(f"[文档] 读取文档失败: {e}")
                return ''
        else:
            logger.info(f"[文档] 文档文件不存在: {doc_path}")
        return ''
    
    def _create_button_bar(self) -> QWidget:
        """创建底部按钮栏"""
        button_bar = QWidget()
        button_bar.setObjectName("AssetDetailButtonBar")
        button_bar.setFixedHeight(70)
        
        layout = QHBoxLayout(button_bar)
        layout.setContentsMargins(25, 12, 25, 12)
        layout.setSpacing(12)
        
        preview_btn = QPushButton("预览资产")
        preview_btn.setObjectName("PreviewButton")
        preview_btn.setFixedHeight(40)
        preview_btn.clicked.connect(self._on_preview_clicked)
        layout.addWidget(preview_btn, 1)
        
        import_btn = QPushButton("导入到工程")
        import_btn.setObjectName("ImportButton")
        import_btn.setFixedHeight(40)
        import_btn.clicked.connect(self._on_import_clicked)
        layout.addWidget(import_btn, 1)
        
        return button_bar
    
    def _create_rounded_pixmap(self, pixmap: QPixmap, radius: int) -> QPixmap:
        """创建带圆角的图片（使用抗锯齿）"""
        # 创建一个透明的画布
        rounded = QPixmap(pixmap.size())
        rounded.fill(Qt.GlobalColor.transparent)
        
        # 创建QPainter并启用抗锯齿
        painter = QPainter(rounded)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
        
        # 创建圆角路径
        path = QPainterPath()
        path.addRoundedRect(QRectF(0, 0, pixmap.width(), pixmap.height()), radius, radius)
        
        # 设置裁剪区域
        painter.setClipPath(path)
        
        # 绘制原始图片
        painter.drawPixmap(0, 0, pixmap)
        painter.end()
        
        return rounded
    
    def _on_preview_clicked(self):
        """预览按钮点击事件"""
        asset_id = self.asset_data.get('id', '')
        logger.info(f"[详情对话框] 预览按钮点击，资产ID: {asset_id}")
        
        # 先关闭对话框
        self.accept()
        
        # 发射预览信号
        self.preview_requested.emit(asset_id)
    
    def _on_import_clicked(self):
        """导入按钮点击事件"""
        asset_id = self.asset_data.get('id', '')
        logger.info(f"[详情对话框] 导入按钮点击，资产ID: {asset_id}")
        
        # 先关闭对话框
        self.accept()
        
        # 发射导入信号
        self.import_requested.emit(asset_id)
    
    def _format_size(self, size_bytes: int) -> str:
        """格式化文件大小"""
        if size_bytes < 1024:
            return f"{size_bytes} B"
        elif size_bytes < 1024 * 1024:
            return f"{size_bytes / 1024:.1f} KB"
        elif size_bytes < 1024 * 1024 * 1024:
            return f"{size_bytes / (1024 * 1024):.1f} MB"
        else:
            return f"{size_bytes / (1024 * 1024 * 1024):.2f} GB"
    
    def mousePressEvent(self, event: QMouseEvent):
        """鼠标按下事件"""
        if event.button() == Qt.MouseButton.LeftButton and event.position().y() <= 50:
            self.drag_position = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
    
    def mouseMoveEvent(self, event: QMouseEvent):
        """鼠标移动事件"""
        if event.buttons() == Qt.MouseButton.LeftButton and not self.drag_position.isNull():
            self.move(event.globalPosition().toPoint() - self.drag_position)
    
    def center_on_parent(self):
        """在父窗口或屏幕中居中"""
        # 尝试查找顶层窗口（主窗口）
        top_window = None
        parent = self.parent()
        
        # 向上遍历找到顶层窗口
        while parent:
            if parent.isWindow():
                top_window = parent
                break
            parent = parent.parent()
        
        if top_window:
            # 在顶层窗口中居中
            parent_geo = top_window.geometry()
            x = parent_geo.x() + (parent_geo.width() - self.width()) // 2
            y = parent_geo.y() + (parent_geo.height() - self.height()) // 2
            self.move(x, y)
        else:
            # 在屏幕中居中
            from PyQt6.QtWidgets import QApplication
            screen = QApplication.primaryScreen().geometry()
            x = (screen.width() - self.width()) // 2
            y = (screen.height() - self.height()) // 2
            self.move(x, y)
