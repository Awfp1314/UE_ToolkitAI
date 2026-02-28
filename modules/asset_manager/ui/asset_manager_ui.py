# -*- coding: utf-8 -*-

"""
资产管理器 UI
"""

from pathlib import Path
from collections import OrderedDict

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QScrollArea,
    QGridLayout, QLineEdit, QPushButton, QApplication, QDialog, QComboBox,
    QLabel
)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QObject, QUrl
from PyQt6.QtGui import QPixmap, QDragEnterEvent, QDropEvent

from core.logger import get_logger
from ui.thumbnail_cache import ThumbnailCache
from modules.base_module_widget import BaseModuleWidget
from modules.asset_manager.logic.asset_controller import AssetController
from .modern_asset_card import ModernAssetCard, CompactAssetCard, format_size, format_time
from .project_selector_dialog import ProjectSelectorDialog
from .add_asset_dialog import AddAssetDialog
from .confirm_dialog import ConfirmDialog
from .asset_detail_dialog import AssetDetailDialog

logger = get_logger(__name__)


class AssetManagerUI(BaseModuleWidget):
    """资产管理器UI"""
    
    # 定义一个信号用于在主线程中重置按钮
    _reset_button_signal = pyqtSignal(str)  # 参数是资产名称
    
    def __init__(self, logic, theme="dark", parent=None):
        super().__init__(parent)
        self.logic = logic
        self.theme = theme
        self.asset_cards = {}
        self.project_search_window = None  # 工程搜索窗口引用

        # 创建资产控制器，委托业务逻辑
        self.controller = AssetController(logic)

        # 从配置文件读取视图模式（通过控制器）
        self.current_view_mode = self.controller.load_view_mode()

        self.card_count = 0

        # ⚡ 性能优化：使用新的ThumbnailCache替代旧的LRU缓存
        self._thumbnail_cache = ThumbnailCache(max_size=300)
        self._thumbnail_cache.thumbnail_loaded.connect(self._on_thumbnail_loaded)
        self._thumbnail_cache.cache_stats_updated.connect(self._on_cache_stats_updated)

        self._init_ui()
        self._connect_signals()

        # 连接重置按钮信号
        self._reset_button_signal.connect(self._handle_reset_button)

        # 初始化时主动加载主题样式（仅更新样式，不重新加载资产）
        self._apply_theme_styles(theme)

        # 不在初始化时加载资产，改为外部控制加载时机
        # 这样可以在启动界面显示期间异步加载，避免阻塞UI
        self._assets_loaded = False
        
        # 懒加载相关
        self._all_assets_data = []  # 存储所有资产数据
        self._loaded_card_count = 0  # 已加载的卡片数量
        self._initial_load_count = 50  # 初始加载数量
        self._load_more_count = 30  # 每次加载更多的数量
        self._is_loading_more = False  # 是否正在加载更多
        
        # 启用拖放功能
        self.setAcceptDrops(True)

    def showEvent(self, event):
        """首次显示时自动加载资产"""
        super().showEvent(event)
        if not self._assets_loaded:
            QTimer.singleShot(10, lambda: self.load_assets_async())
    
    def _init_ui(self):
        """初始化UI"""
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        # 搜索和筛选区域
        filter_area = QWidget()
        filter_area.setObjectName("AssetFilterArea")
        filter_area.setFixedHeight(60)
        filter_layout = QHBoxLayout(filter_area)
        filter_layout.setContentsMargins(20, 10, 20, 20)
        filter_layout.setSpacing(15)

        # 搜索框
        self.search_input = QLineEdit()
        self.search_input.setObjectName("AssetSearchInput")
        self.search_input.setPlaceholderText("输入资产名称或拼音...")
        self.search_input.setFixedHeight(36)
        self.search_input.setMaximumWidth(200)
        self.search_input.setFocusPolicy(Qt.FocusPolicy.ClickFocus)  # 只有点击时才获得焦点
        self.search_input.textChanged.connect(self._on_search_changed)
        filter_layout.addWidget(self.search_input)
        
        # 分类选择框
        self.category_filter = QComboBox()
        self.category_filter.setObjectName("AssetCategoryFilter")
        self.category_filter.setFixedHeight(36)
        self.category_filter.setMinimumWidth(120)
        self.category_filter.setMaximumWidth(180)
        self.category_filter.setFocusPolicy(Qt.FocusPolicy.ClickFocus)
        self.category_filter.setCursor(Qt.CursorShape.PointingHandCursor)
        self.category_filter.addItem("全部分类")  # 默认选项
        self.category_filter.currentTextChanged.connect(self._on_category_changed)
        
        # 使用自定义delegate实现文本居中
        from PyQt6.QtWidgets import QStyledItemDelegate
        class CenterAlignDelegate(QStyledItemDelegate):
            def initStyleOption(self, option, index):
                super().initStyleOption(option, index)
                option.displayAlignment = Qt.AlignmentFlag.AlignCenter
        
        self.category_filter.setItemDelegate(CenterAlignDelegate(self.category_filter))
        filter_layout.addWidget(self.category_filter)
        
        # 排序选择框
        self.sort_combo = QComboBox()
        self.sort_combo.setObjectName("AssetSortCombo")
        self.sort_combo.setFixedHeight(36)
        self.sort_combo.setMinimumWidth(120)
        self.sort_combo.setMaximumWidth(180)
        self.sort_combo.setFocusPolicy(Qt.FocusPolicy.ClickFocus)
        self.sort_combo.setCursor(Qt.CursorShape.PointingHandCursor)
        self.sort_combo.addItems([
            "添加时间（最新）",
            "添加时间（最早）",
            "名称（A-Z）",
            "名称（Z-A）",
            "分类（A-Z）",
            "分类（Z-A）"
        ])
        # 使用 activated 信号而不是 currentTextChanged，这样用户每次主动选择都会触发
        self.sort_combo.activated.connect(lambda: self._on_sort_changed(self.sort_combo.currentText()))
        self.sort_combo.setItemDelegate(CenterAlignDelegate(self.sort_combo))
        filter_layout.addWidget(self.sort_combo)

        # 添加弹性空间
        filter_layout.addStretch()
        
        # 添加资产按钮
        self.add_asset_btn = QPushButton("+ 添加资产")
        self.add_asset_btn.setObjectName("AddAssetButton")
        self.add_asset_btn.setFixedHeight(36)
        self.add_asset_btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.add_asset_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.add_asset_btn.setToolTip("添加资产到资产库")
        self.add_asset_btn.clicked.connect(self._show_add_asset_dialog)
        filter_layout.addWidget(self.add_asset_btn)

        # 视图切换按钮（根据配置初始化）
        self.view_toggle_btn = QPushButton()
        self.view_toggle_btn.setObjectName("ViewToggleIconButton")
        self.view_toggle_btn.setFixedSize(40, 40)
        self.view_toggle_btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.view_toggle_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.view_toggle_btn.clicked.connect(self._toggle_view_mode)

        # 根据当前视图模式设置按钮状态
        self._update_view_toggle_button()

        filter_layout.addWidget(self.view_toggle_btn)

        main_layout.addWidget(filter_area)

        # 创建滚动区域
        scroll_area = QScrollArea()
        scroll_area.setObjectName("AssetScrollArea")
        scroll_area.setWidgetResizable(True)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll_area.setFocusPolicy(Qt.FocusPolicy.StrongFocus)  # 允许滚动区域接收焦点
        
        # 启用自动隐藏滚动条
        from core.utils.auto_hide_scrollbar import enable_auto_hide_scrollbar
        enable_auto_hide_scrollbar(scroll_area)

        # 滚动区域内容
        scroll_content = QWidget()
        scroll_content.setObjectName("AssetScrollContent")
        scroll_content.setFocusPolicy(Qt.FocusPolicy.StrongFocus)  # 允许内容区域接收焦点
        scroll_layout = QVBoxLayout(scroll_content)
        scroll_layout.setContentsMargins(0, 0, 0, 0)
        scroll_layout.setSpacing(20)

        # 创建网格容器（用于放置卡片）
        self.grid_widget = QWidget()
        self.grid_widget.setObjectName("AssetGridWidget")
        self.grid_layout = QGridLayout(self.grid_widget)
        self.grid_layout.setContentsMargins(0, 0, 0, 0)
        # 根据当前视图模式设置间距
        initial_spacing = 30 if self.current_view_mode == "detailed" else 20
        self.grid_layout.setSpacing(initial_spacing)
        self.grid_layout.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)

        scroll_layout.addWidget(self.grid_widget)
        scroll_layout.addStretch()

        scroll_area.setWidget(scroll_content)
        main_layout.addWidget(scroll_area)

        # 保存滚动区域引用，用于后续事件处理
        self.scroll_area = scroll_area
        self.scroll_content = scroll_content
        
        # ⚡ 初始化时显示"加载中"占位符
        self._show_initial_loading_placeholder()

        # 安装事件过滤器，用于处理点击事件
        scroll_area.viewport().installEventFilter(self)
        scroll_content.installEventFilter(self)
        
        # 连接滚动条信号，实现懒加载
        scroll_area.verticalScrollBar().valueChanged.connect(self._on_scroll_changed)

    def eventFilter(self, obj, event):
        """事件过滤器：处理点击事件以清除搜索框焦点"""
        from PyQt6.QtCore import QEvent
        from PyQt6.QtGui import QMouseEvent

        # 如果是鼠标按下事件，并且点击的不是搜索框
        if event.type() == QEvent.Type.MouseButtonPress:
            if isinstance(event, QMouseEvent):
                # 清除搜索框焦点
                if self.search_input.hasFocus():
                    self.search_input.clearFocus()

        return super().eventFilter(obj, event)

    def _connect_signals(self):
        """连接信号"""
        if self.logic:
            self.logic.assets_loaded.connect(self._on_assets_loaded)
            self.logic.error_occurred.connect(self._on_error_occurred)
            self.logic.thumbnail_updated.connect(self._on_thumbnail_updated)

    def _load_categories(self):
        """加载分类列表到下拉框"""
        try:
            # 通过控制器获取所有分类
            categories = self.controller.get_categories()
            
            # 保存当前选中的分类
            current_category = self.category_filter.currentText()
            
            # 清空并重新填充（保留"全部分类"）
            self.category_filter.clear()
            self.category_filter.addItem("全部分类")
            
            # 添加所有分类
            for category in categories:
                self.category_filter.addItem(category)
            
            # 添加"+ 分类管理"选项
            self.category_filter.addItem("+ 分类管理")
            
            # 恢复之前的选择（如果还存在）
            if current_category and current_category != "+ 分类管理":
                index = self.category_filter.findText(current_category)
                if index >= 0:
                    self.category_filter.setCurrentIndex(index)
            
            logger.info(f"已加载 {len(categories)} 个分类")
        except Exception as e:
            logger.error(f"加载分类失败: {e}", exc_info=True)
    
    def _on_category_changed(self, category: str):
        """分类选择改变事件"""
        logger.info(f"分类选择改变: '{category}'")
        
        # 如果选中"+ 分类管理"，显示分类管理对话框
        if category == "+ 分类管理":
            self._show_add_category_dialog()
            # 恢复到"全部分类"
            self.category_filter.setCurrentIndex(0)
            return
        
        # 通过控制器更新分类过滤
        self.controller.set_category(category)
        self._apply_filter_to_ui()
    
    def _on_search_changed(self, search_text: str):
        """搜索文本改变事件（实时搜索，带防抖优化）"""
        self.controller.set_search_text(search_text)
        
        # 添加防抖，避免用户快速输入时频繁过滤
        if not hasattr(self, '_search_timer'):
            self._search_timer = QTimer()
            self._search_timer.setSingleShot(True)
            self._search_timer.timeout.connect(self._perform_search)
        
        # 停止之前的定时器
        self._search_timer.stop()
        
        # 如果搜索文本为空，立即执行（显示全部）
        if not self.controller.search_text:
            self._perform_search()
        else:
            # 否则延迟300ms执行，等待用户输入完成
            self._search_timer.start(300)
    
    def _perform_search(self):
        """执行实际的搜索过滤"""
        logger.info(f"执行搜索: '{self.controller.search_text}'")
        self._apply_filter_to_ui()
    
    def _on_sort_changed(self, sort_method: str):
        """排序方式改变事件"""
        self.controller.set_sort_method(sort_method)
        logger.info(f"排序方式改变: {sort_method}")
        
        # 重新应用筛选和排序
        self._apply_filter_to_ui()

    def _apply_filter_to_ui(self):
        """通过控制器获取过滤结果，并更新 UI 卡片的可见性和布局"""
        try:
            # 通过控制器获取过滤后的资产列表
            matched_assets = self.controller.get_filtered_assets()
            
            # 先隐藏所有卡片
            for card in self.asset_cards.values():
                card.setVisible(False)
            
            # 按顺序重新排列匹配的卡片
            # 懒加载优化：只显示前N个，其余的在滚动时加载
            visible_count = 0
            max_initial_visible = self._initial_load_count  # 初始只显示这么多
            
            for asset in matched_assets:
                card = self.asset_cards.get(asset.id)
                if card:
                    # 只有前N个才立即显示和重新布局
                    if visible_count < max_initial_visible:
                        # 计算新的网格位置
                        if self.current_view_mode == "detailed":
                            row = visible_count // 4
                            col = visible_count % 4
                        else:
                            row = visible_count // 5
                            col = visible_count % 5
                        
                        # 移除旧位置
                        self.grid_layout.removeWidget(card)
                        # 添加到新位置
                        self.grid_layout.addWidget(card, row, col)
                        # 显示卡片
                        card.setVisible(True)
                    
                    visible_count += 1
            
            logger.info(f"搜索结果: 显示 {visible_count} 个资产（初始显示 {min(visible_count, max_initial_visible)} 个）")
            
            # 触发可见缩略图的加载
            QTimer.singleShot(100, self._load_visible_thumbnails)
            
        except Exception as e:
            logger.error(f"过滤资产失败: {e}", exc_info=True)

    def _refresh_assets(self):
        """刷新资产列表（应用搜索过滤，使用批量优化 + 延迟加载缩略图）"""
        if not self.logic:
            logger.warning("Logic 层未初始化")
            return

        try:
            # 通过控制器获取过滤后的资产列表
            assets = self.controller.get_filtered_assets()
            logger.info(f"刷新资产列表: {len(assets)} 个资产")

            # ⚡ 性能优化：禁用更新，避免每次添加卡片时都重绘
            self.grid_widget.setUpdatesEnabled(False)

            try:
                # 清空现有卡片
                self._clear_cards()
                self.card_count = 0

                # 收集需要延迟加载缩略图的卡片
                cards_to_load = []

                # 通过控制器转换 Asset 对象为字典格式并批量创建卡片
                for i, asset in enumerate(assets):
                    asset_dict = self.controller.convert_asset_to_dict(asset)
                    card = self._add_asset_card(asset_dict, i, defer_thumbnail=True)
                    if card:
                        cards_to_load.append(card)
            finally:
                # ⚡ 重新启用更新，一次性重绘所有卡片
                self.grid_widget.setUpdatesEnabled(True)
                logger.debug(f"批量刷新了 {len(assets)} 个资产卡片")

            # ⚡ 延迟加载缩略图，避免阻塞 UI
            if cards_to_load:
                QTimer.singleShot(0, self._load_visible_thumbnails)

        except Exception as e:
            logger.error(f"刷新资产列表失败: {e}", exc_info=True)

    def _apply_theme_styles(self, theme: str):
        """应用主题样式（不重新加载资产）
        
        Args:
            theme: 主题名称 ("dark" 或 "light")
        """
        self.theme = theme
        
        # 不需要手动应用主题，依赖应用程序级别的QSS
        # 因为主窗口已经通过 style_system.apply_theme(app, theme_name) 应用了全局主题
        # 如果我们再调用 widget.setStyleSheet()，会覆盖全局样式
        
        logger.info(f"资产管理器主题样式已更新为: {theme}")
    
    def update_theme(self, theme: str):
        """更新主题

        Args:
            theme: 主题名称 ("dark" 或 "light")
        """
        # 应用主题样式
        self._apply_theme_styles(theme)

        # 只更新现有卡片的主题，不重新创建卡片（避免卡顿）
        for card in self.asset_cards.values():
            if hasattr(card, 'update_theme'):
                card.update_theme(theme)

        logger.info(f"资产管理器主题已更新为: {theme}")
    
    def on_theme_changed(self, theme_name: str) -> None:
        """主题切换回调方法（继承自 BaseModuleWidget）
        
        当应用主题切换时，此方法会被主窗口调用。
        
        Args:
            theme_name: 新主题名称 ('dark' 或 'light')
        """
        # 调用基类实现以刷新样式
        super().on_theme_changed(theme_name)
        
        # 调用现有的 update_theme 方法更新资产卡片
        self.update_theme(theme_name)
        
        logger.debug(f"AssetManagerUI 主题切换完成: {theme_name}")
    
    def load_assets_async(self, on_complete=None, force_reload=False):
        """异步加载资产数据
        
        Args:
            on_complete: 加载完成回调函数
            force_reload: 是否强制重新加载（忽略已加载标志）
        """
        logger.info(f"开始异步加载资产，已加载状态: {self._assets_loaded}, 强制重载: {force_reload}")
        
        if self._assets_loaded and not force_reload:
            logger.info("资产已加载，直接返回")
            if on_complete:
                on_complete()
            return
        
        # ⚡ 显示"加载中"提示
        self._show_loading_placeholder()
            
        # 使用QTimer延迟执行，避免阻塞UI
        from PyQt6.QtCore import QTimer
        QTimer.singleShot(10, lambda: self._load_assets_async(on_complete))
    
    def _create_loading_widget(self):
        """创建统一的加载中占位符控件"""
        loading_container = QWidget()
        loading_container.setObjectName("assetManagerEmptyContainer")
        loading_layout = QVBoxLayout()
        loading_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        # 使用 QProgressBar 不确定模式做旋转动画
        from PyQt6.QtWidgets import QProgressBar
        spinner = QProgressBar()
        spinner.setRange(0, 0)  # 不确定模式
        spinner.setTextVisible(False)
        spinner.setFixedSize(200, 3)
        spinner.setStyleSheet("""
            QProgressBar {
                border: none;
                border-radius: 1px;
                background-color: rgba(255, 255, 255, 0.05);
            }
            QProgressBar::chunk {
                background-color: rgba(255, 255, 255, 0.2);
                border-radius: 1px;
            }
        """)
        loading_layout.addWidget(spinner, 0, Qt.AlignmentFlag.AlignCenter)
        
        loading_layout.addSpacing(12)
        
        loading_label = QLabel("正在加载资产...")
        loading_label.setObjectName("assetManagerEmptyLabel")
        loading_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        loading_layout.addWidget(loading_label)
        
        loading_container.setLayout(loading_layout)
        return loading_container
    
    def _show_loading_placeholder(self):
        """显示加载中占位符"""
        try:
            self.grid_widget.hide()
            
            if hasattr(self, '_loading_container') and self._loading_container:
                try:
                    self._loading_container.deleteLater()
                    self._loading_container = None
                except:
                    pass
            
            loading_container = self._create_loading_widget()
            self.scroll_content.layout().insertWidget(0, loading_container)
            self._loading_container = loading_container
        except Exception as e:
            logger.error(f"显示加载占位符失败: {e}")
    
    def _show_initial_loading_placeholder(self):
        """初始化时显示加载中占位符"""
        try:
            self.grid_widget.hide()
            
            loading_container = self._create_loading_widget()
            self.scroll_content.layout().insertWidget(0, loading_container)
            self._loading_container = loading_container
        except Exception as e:
            logger.error(f"显示初始加载占位符失败: {e}")
    
    def _load_assets_async(self, on_complete=None):
        """实际执行异步加载资产"""
        logger.info("开始执行异步加载资产")
        
        # ⚡ 移除初始加载占位符
        if hasattr(self, '_loading_container') and self._loading_container:
            try:
                self._loading_container.deleteLater()
                self._loading_container = None
            except:
                pass
        
        # 显示网格容器
        self.grid_widget.show()

        # 通过 logic 层获取资产列表
        if not self.logic:
            logger.warning("Logic 层未初始化")
            if on_complete:
                on_complete()
            return

        try:
            # 从 logic 层获取资产列表
            assets = self.logic.assets
            logger.info(f"从 logic 层加载了 {len(assets)} 个资产")

            # 清空现有卡片（使用优化的清空方法）
            self._clear_cards()
            self.card_count = 0
            self._loaded_card_count = 0

            # 立即强制处理事件，让清空操作立即生效
            from PyQt6.QtWidgets import QApplication
            QApplication.processEvents()

            # 转换 Asset 对象为字典格式（通过控制器）
            assets_data = []
            for asset in assets:
                asset_dict = self.controller.convert_asset_to_dict(asset)
                assets_data.append(asset_dict)

            # 保存所有资产数据
            self._all_assets_data = assets_data
            
            # 只加载初始数量的卡片
            initial_count = min(self._initial_load_count, len(assets_data))
            logger.info(f"懒加载：初始加载 {initial_count}/{len(assets_data)} 个资产卡片")
            
            # 立即开始创建第一批卡片
            self._create_assets_batch(assets_data[:initial_count], 0, on_complete)
            
            # 更新已加载计数
            self._loaded_card_count = initial_count

        except Exception as e:
            logger.error(f"加载资产失败: {e}", exc_info=True)
            if on_complete:
                on_complete()
    
    def _create_assets_batch(self, assets, start_index, on_complete):
        """分批创建资产卡片"""
        batch_size = 30  # 进一步增加批次大小，减少批次切换开销
        end_index = min(start_index + batch_size, len(assets))

        logger.info(f"创建资产卡片批次: {start_index}-{end_index-1}/{len(assets)}")

        # 创建当前批次的卡片
        for i in range(start_index, end_index):
            self._add_asset_card(assets[i], i)

        # 如果还有更多资产需要创建，继续创建下一批
        if end_index < len(assets):
            # 使用0ms间隔，立即创建下一批，但通过QTimer让出控制权给UI线程
            from PyQt6.QtCore import QTimer
            QTimer.singleShot(0, lambda: self._create_assets_batch(assets, end_index, on_complete))
        else:
            # 所有资产创建完成
            logger.info("所有资产卡片创建完成")
            self._assets_loaded = True
            
            # 加载分类列表
            self._load_categories()
            
            # 触发初始可见缩略图的加载
            from PyQt6.QtCore import QTimer
            QTimer.singleShot(100, self._load_visible_thumbnails)

            # 触发后台增量扫描，检测缓存外的变化
            if self.logic and hasattr(self.logic, 'rescan_in_background'):
                if not getattr(self, '_background_rescanning', False):
                    QTimer.singleShot(500, self._trigger_background_rescan)
            
            if on_complete:
                on_complete()
    
    def _trigger_background_rescan(self):
        """触发后台增量扫描，扫描完成后刷新 UI"""
        if not self.logic:
            return
        self._background_rescanning = True
        self.logic.rescan_in_background()

        # 延迟检查扫描结果（扫描完成后 logic.assets 会更新）
        from PyQt6.QtCore import QTimer
        self._rescan_check_timer = QTimer()
        self._rescan_check_timer.setSingleShot(True)
        self._rescan_check_timer.timeout.connect(self._check_rescan_result)
        self._rescan_check_timer.start(5000)  # 5 秒后检查

    def _check_rescan_result(self):
        """检查后台扫描是否导致资产数量变化，如有变化则刷新 UI"""
        self._background_rescanning = False
        if not self.logic:
            return
        current_count = len(self._all_assets_data)
        new_count = len(self.logic.assets)
        if current_count != new_count:
            logger.info(f"增量扫描检测到变化: {current_count} -> {new_count}，刷新 UI")
            self._assets_loaded = False
            self.load_assets_async(force_reload=True)

    def _on_scroll_changed(self, value):
        """滚动条位置改变时触发 - 实现懒加载和缩略图按需加载"""
        # 1. 懒加载更多资产卡片
        if not self._is_loading_more and self._loaded_card_count < len(self._all_assets_data):
            scrollbar = self.scroll_area.verticalScrollBar()
            max_value = scrollbar.maximum()
            
            # 当滚动到距离底部200px时，加载更多
            if max_value - value < 200:
                self._load_more_assets()
        
        # 2. 按需加载可见卡片的缩略图（防抖）
        if hasattr(self, '_thumbnail_load_timer'):
            self._thumbnail_load_timer.stop()
        else:
            self._thumbnail_load_timer = QTimer()
            self._thumbnail_load_timer.setSingleShot(True)
            self._thumbnail_load_timer.timeout.connect(self._load_visible_thumbnails)
        
        # 延迟100ms加载，避免滚动时频繁触发
        self._thumbnail_load_timer.start(100)
    
    def _load_more_assets(self):
        """加载更多资产卡片"""
        if self._is_loading_more:
            return
        
        # 计算要加载的资产范围
        start_index = self._loaded_card_count
        end_index = min(start_index + self._load_more_count, len(self._all_assets_data))
        
        if start_index >= end_index:
            return
        
        self._is_loading_more = True
        logger.info(f"懒加载：加载更多资产 {start_index}-{end_index}/{len(self._all_assets_data)}")
        
        # 获取要加载的资产数据
        assets_to_load = self._all_assets_data[start_index:end_index]
        
        # 创建卡片
        for i, asset_data in enumerate(assets_to_load):
            self._add_asset_card(asset_data, start_index + i)
        
        # 更新已加载计数
        self._loaded_card_count = end_index
        self._is_loading_more = False
        
        logger.info(f"懒加载：已加载 {self._loaded_card_count}/{len(self._all_assets_data)} 个资产")
        
        # 加载新创建卡片的缩略图（如果可见）
        QTimer.singleShot(0, self._load_visible_thumbnails)
    
    def _load_visible_thumbnails(self):
        """加载可见区域的缩略图（使用ThumbnailCache）"""
        if not hasattr(self, 'scroll_area') or not self.scroll_area:
            return
        
        # 获取滚动区域的可见矩形
        viewport = self.scroll_area.viewport()
        viewport_rect = viewport.rect()
        
        # 获取滚动偏移
        scroll_offset = self.scroll_area.verticalScrollBar().value()
        
        # 遍历所有卡片，检查可见性
        visible_cards = []
        for asset_id, card in self.asset_cards.items():
            if not card or not card.isVisible():
                continue
            
            # 获取卡片在滚动内容中的位置
            card_pos = card.pos()
            card_rect = card.rect()
            
            # 计算卡片相对于视口的位置
            card_top = card_pos.y() - scroll_offset
            card_bottom = card_top + card_rect.height()
            
            # 检查卡片是否在可见区域内（包含一些预加载边距）
            preload_margin = 300  # 预加载边距（像素）
            if card_bottom >= -preload_margin and card_top <= viewport_rect.height() + preload_margin:
                visible_cards.append((asset_id, card))
        
        # 使用ThumbnailCache加载可见卡片的缩略图
        if visible_cards:
            logger.debug(f"检测到 {len(visible_cards)} 个可见卡片，开始加载缩略图")
            for asset_id, card in visible_cards:
                # 检查卡片是否已经加载过缩略图
                if hasattr(card, '_thumbnail_loaded') and card._thumbnail_loaded:
                    continue
                
                # 获取缩略图路径
                thumbnail_path = None
                if hasattr(card, 'thumbnail_path') and card.thumbnail_path:
                    thumbnail_path = Path(card.thumbnail_path)
                
                # 只有当缩略图路径存在时才使用缓存加载
                if thumbnail_path and thumbnail_path.exists():
                    # 从缓存获取缩略图（如果不在缓存中会触发异步加载）
                    pixmap = self._thumbnail_cache.get(asset_id, thumbnail_path)
                    
                    # 如果返回的不是占位符（即缓存命中），立即更新卡片
                    if pixmap and not pixmap.isNull():
                        self._update_card_thumbnail(card, pixmap)
                else:
                    # 没有缩略图路径，显示默认文字
                    if hasattr(card, '_show_default_icon'):
                        card._show_default_icon()
                        card._thumbnail_loaded = True  # 标记为已加载，避免重复处理
    
    def _on_thumbnail_loaded(self, asset_id: str, pixmap: QPixmap):
        """缩略图加载完成回调
        
        Args:
            asset_id: 资产ID
            pixmap: 加载的缩略图
        """
        # 查找对应的卡片并更新缩略图
        if asset_id in self.asset_cards:
            card = self.asset_cards[asset_id]
            self._update_card_thumbnail(card, pixmap)
            logger.debug(f"更新卡片缩略图: {asset_id}")
    
    def _update_card_thumbnail(self, card, pixmap: QPixmap):
        """更新卡片的缩略图
        
        Args:
            card: 资产卡片对象
            pixmap: 缩略图QPixmap
        """
        if not card or pixmap.isNull():
            return
        
        try:
            # 根据卡片类型缩放缩略图
            if isinstance(card, ModernAssetCard):
                target_w, target_h = 212, 153
            else:  # CompactAssetCard
                target_w, target_h = 172, 110
            
            # 缩放缩略图
            scaled_pixmap = pixmap.scaled(
                target_w, target_h,
                Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                Qt.TransformationMode.SmoothTransformation
            )
            
            # 更新卡片的缩略图
            if hasattr(card, 'thumbnail_label') and card.thumbnail_label:
                card.thumbnail_label.setPixmap(scaled_pixmap)
                card._thumbnail_loaded = True
        except Exception as e:
            logger.error(f"更新卡片缩略图失败: {e}", exc_info=True)
    
    def _on_cache_stats_updated(self, size: int, hits: int, misses: int):
        """缓存统计信息更新回调
        
        Args:
            size: 当前缓存大小
            hits: 缓存命中次数
            misses: 缓存未命中次数
        """
        # 可以在这里添加统计信息的显示或日志
        total = hits + misses
        hit_rate = (hits / total * 100) if total > 0 else 0
        logger.debug(f"缩略图缓存统计: 大小={size}, 命中率={hit_rate:.1f}% ({hits}/{total})")

    
    def _load_assets(self):
        """同步加载资产数据（保留用于主题切换等场景）"""
        if not self.logic:
            logger.warning("Logic 层未初始化")
            return

        try:
            assets = self.logic.assets
            logger.info(f"从 logic 层加载了 {len(assets)} 个资产")

            # 清空现有卡片
            self._clear_cards()
            self.card_count = 0

            # 通过控制器转换 Asset 对象为字典格式
            for i, asset in enumerate(assets):
                asset_dict = self.controller.convert_asset_to_dict(asset)
                self._add_asset_card(asset_dict, i)

        except Exception as e:
            logger.error(f"加载资产失败: {e}", exc_info=True)
    
    def _add_asset_card(self, asset_data, index, defer_thumbnail=True):
        """添加资产卡片

        Args:
            asset_data: 资产数据字典
            index: 索引
            defer_thumbnail: 是否延迟加载缩略图（默认True，使用懒加载）

        Returns:
            创建的卡片对象（用于延迟加载缩略图）
        """
        name = asset_data.get('name', '未命名资产')
        category = asset_data.get('category', '默认分类')
        size = format_size(asset_data.get('size', 0))
        thumbnail_path = asset_data.get('thumbnail_path', '')
        asset_type = "资源包" if asset_data.get('asset_type') == 'package' else "文件"
        created_time = format_time(asset_data.get('created_time', ''))
        asset_path = asset_data.get('path', '')  # 获取资产路径

        # 检查是否有文档（通过控制器）
        asset_id = asset_data.get('id', '')
        has_document = self.controller.check_asset_has_document(asset_id) if asset_id else False

        # 根据当前视图模式创建卡片
        if self.current_view_mode == "detailed":
            card = ModernAssetCard(name, category, size, thumbnail_path, asset_type,
                                  created_time, has_document, theme=self.theme,
                                  defer_thumbnail=defer_thumbnail, asset_path=asset_path)
            row = index // 4
            col = index % 4
        else:
            card = CompactAssetCard(name, category, thumbnail_path, asset_type,
                                   theme=self.theme, defer_thumbnail=defer_thumbnail,
                                   asset_path=asset_path)
            row = index // 5
            col = index % 5

        # 设置卡片的asset_id
        if asset_id:
            card.asset_id = asset_id
        
        # 连接信号（使用Qt.ConnectionType.QueuedConnection确保信号正确传递）
        card.preview_clicked.connect(lambda: self._on_preview_asset(name))
        card.edit_info_requested.connect(self._on_edit_asset_info)
        # open_path_requested 信号不再需要，直接在卡片内部处理
        card.delete_requested.connect(self._on_delete_asset)
        card.detail_requested.connect(self._on_detail_requested, Qt.ConnectionType.QueuedConnection)  # 连接详情请求信号
        card.import_requested.connect(self._on_import_asset)  # 连接导入请求信号
        card.export_requested.connect(self._on_export_asset)  # 连接导出请求信号

        # 添加到网格布局
        self.grid_layout.addWidget(card, row, col)
        self.card_count += 1
        
        # 将卡片添加到字典（用于快速搜索和隐藏/显示）
        if asset_id:
            self.asset_cards[asset_id] = card

        return card

    def _load_view_mode(self) -> str:
        """从配置文件加载视图模式（委托给控制器）

        Returns:
            str: 视图模式 ("detailed" 或 "compact")
        """
        return self.controller.load_view_mode()

    def _save_view_mode(self):
        """保存视图模式到配置文件（委托给控制器）"""
        self.controller.save_view_mode(self.current_view_mode)

    def _update_view_toggle_button(self):
        """更新视图切换按钮的状态"""
        if self.current_view_mode == "detailed":
            self.view_toggle_btn.setText("≡")
            self.view_toggle_btn.setToolTip("切换到简约视图")
        else:
            self.view_toggle_btn.setText("⊞")
            self.view_toggle_btn.setToolTip("切换到详细视图")

    def _toggle_view_mode(self):
        """切换视图模式"""
        # 防抖：避免快速重复点击
        import time
        current_time = time.time() * 1000
        if hasattr(self, '_last_toggle_time'):
            if current_time - self._last_toggle_time < 200:  # 200ms防抖
                logger.info("视图切换过快，已忽略")
                return
        self._last_toggle_time = current_time

        # 切换视图模式
        if self.current_view_mode == "compact":
            self.current_view_mode = "detailed"
        else:
            self.current_view_mode = "compact"

        # 更新按钮状态
        self._update_view_toggle_button()

        # 保存视图模式到配置文件
        self._save_view_mode()

        # 调整网格间距
        if self.current_view_mode == "detailed":
            self.grid_layout.setSpacing(30)  # 详细视图使用较大间距
        else:
            self.grid_layout.setSpacing(20)  # 简约视图使用较小间距

        # 使用异步分批加载，避免卡顿
        self._load_assets_async()

        logger.info(f"切换到{'详细' if self.current_view_mode == 'detailed' else '简约'}视图")
    
    def _clear_cards(self):
        """清空所有卡片（优化版本）"""
        # 清空字典
        self.asset_cards.clear()
        
        # 批量删除，避免逐个删除的开销
        items_to_delete = []
        while self.grid_layout.count():
            child = self.grid_layout.takeAt(0)
            if child:
                widget = child.widget()
                if widget:
                    widget.setParent(None)  # 立即从父控件移除
                    items_to_delete.append(widget)

        # 延迟删除，避免阻塞UI
        from PyQt6.QtCore import QTimer
        for widget in items_to_delete:
            QTimer.singleShot(0, widget.deleteLater)
    
    def _on_assets_loaded(self, assets):
        """资产加载完成"""
        logger.info(f"Logic加载了 {len(assets)} 个资产")
        # 可以选择使用logic的资产或继续使用配置文件
    
    def _on_preview_asset(self, name):
        """预览资产"""
        logger.info(f"预览资产: {name}")

        # 查找对应的卡片和资产ID
        asset_id = None
        preview_card = None
        for aid, card in self.asset_cards.items():
            if hasattr(card, 'name') and card.name == name:
                asset_id = aid
                preview_card = card
                break

        if not asset_id or not preview_card:
            logger.error(f"未找到资产: {name}")
            return

        # 获取可用的预览工程列表
        preview_projects = self.logic.get_additional_preview_projects_with_names()

        # 如果没有可用的预览工程，提示用户
        if not preview_projects:
            logger.warning("没有可用的预览工程，请先在设置中配置预览工程")
            # 显示提示消息框，并提供"去设置"按钮
            from .message_dialog import MessageDialog
            dialog = MessageDialog(
                "预览工程未设置",
                "请先在设置界面中添加预览工程，然后再进行资产预览。",
                "info",
                show_settings_button=True,
                parent=self
            )
            
            if dialog.exec() == MessageDialog.DialogCode.Accepted and dialog.goto_settings:
                # 用户点击了"去设置"，跳转到设置界面
                self._navigate_to_settings()
            return

        # 读取上次选择的预览工程名称
        last_selected_name = None
        try:
            user_config = self.logic.config_manager.load_user_config()
            last_selected_name = user_config.get("last_preview_project_name", "")
            if last_selected_name:
                logger.info(f"读取到上次选择的预览工程: {last_selected_name}")
        except Exception as e:
            logger.warning(f"读取上次选择失败: {e}")

        # 弹出预览工程选择对话框
        dialog = ProjectSelectorDialog(
            preview_projects,
            theme=self.theme,
            last_selected_name=last_selected_name,
            parent=self
        )
        if dialog.exec() != ProjectSelectorDialog.DialogCode.Accepted:
            # 用户取消了选择
            logger.info("用户取消了预览工程选择")
            return

        # 获取用户选择的工程
        selected_project = dialog.get_selected_project()
        if not selected_project:
            logger.error("未能获取选中的预览工程")
            return

        selected_name = selected_project.get("name", "")
        preview_project_path = Path(selected_project.get("path", ""))
        logger.info(f"用户选择了预览工程: {selected_name} -> {preview_project_path}")

        # 保存本次选择到配置文件
        try:
            config = self.logic.config_manager.load_user_config()
            config["last_preview_project_name"] = selected_name
            self.logic.config_manager.save_user_config(config, backup_reason="update_preview_project")
            logger.info(f"已保存预览工程选择: {selected_name}")
        except Exception as e:
            logger.warning(f"保存预览工程选择失败: {e}")

        # 获取预览按钮
        preview_btn = preview_card.preview_btn

        # 定义按钮重置方法
        def reset_button():
            """重置按钮状态"""
            logger.info(f"重置预览按钮: {name}")
            preview_btn.reset_progress()
            preview_btn.update_button_text("▶  预览资产")

        # 简化的进度回调：只显示启动引擎的消息
        def update_progress(current, total, message):
            """简化的进度回调（符号链接很快，不需要显示进度）"""
            # 只在启动引擎时显示消息
            if "启动" in message or "引擎" in message:
                preview_btn.update_button_text("启动中...")
            elif current >= total and total > 0:
                # 链接完成，直接重置（不显示成功提示）
                logger.info(f"资产链接完成: {name}")
                self._reset_button_signal.emit(name)

        # 直接调用logic层的预览功能（不显示初始进度）
        if self.logic:
            self.logic.preview_asset(asset_id, progress_callback=update_progress, preview_project_path=preview_project_path)

        # 监听preview_finished信号，恢复按钮状态
        def on_preview_finished():
            preview_btn.reset_progress()
            preview_btn.update_button_text("▶  预览资产")

        if self.logic:
            # 断开之前的连接（如果有）
            try:
                self.logic.preview_finished.disconnect()
            except:
                pass
            # 连接新的回调
            self.logic.preview_finished.connect(on_preview_finished)
    
    def _handle_reset_button(self, asset_name: str):
        """处理重置按钮信号（在主线程中执行）"""
        logger.info(f"主线程收到重置信号: {asset_name}")
        
        # 查找对应的卡片
        for aid, card in self.asset_cards.items():
            if hasattr(card, 'name') and card.name == asset_name:
                preview_btn = card.preview_btn
                # 在主线程中创建定时器
                QTimer.singleShot(1500, lambda: (
                    preview_btn.reset_progress(),
                    preview_btn.update_button_text("▶  预览资产")
                ))
                logger.info(f"已设置定时器重置按钮: {asset_name}")
                break
    
    def _on_edit_asset_info(self, name):
        """编辑资产信息"""
        logger.info(f"编辑资产信息: {name}")
        
        try:
            # 通过控制器查找资产
            asset = self.controller.find_asset_by_name(name)
            
            if not asset:
                logger.warning(f"未找到资产: {name}")
                return
            
            # 通过控制器获取已有的资产名称和分类列表
            existing_names = self.controller.get_existing_asset_names()
            categories = self.controller.get_categories()
            
            # 检查是否有文档（文档统一存储在 .asset_config/documents/ 目录下）
            has_documentation = False
            if self.logic.documents_dir:
                doc_path = self.logic.documents_dir / f"{asset.id}.txt"
                has_documentation = doc_path.exists()
                logger.debug(f"检查文档: {doc_path}, 存在: {has_documentation}")
            
            # 导入并创建编辑对话框
            from .edit_asset_dialog import EditAssetDialog
            
            dialog = EditAssetDialog(
                logic=self.logic,
                asset_name=asset.name,
                asset_category=asset.category,
                existing_names=existing_names,
                categories=categories,
                has_documentation=has_documentation,
                parent=self
            )
            
            # 显示对话框
            if dialog.exec() == EditAssetDialog.DialogCode.Accepted:
                asset_info = dialog.get_asset_info()
                new_name = asset_info['name']
                new_category = asset_info['category']
                
                # 更新资产信息
                if self.logic.update_asset_info(
                    asset_id=asset.id,
                    new_name=new_name if new_name != asset.name else None,
                    new_category=new_category if new_category != asset.category else None
                ):
                    logger.info(f"资产 {name} 信息更新成功")
                    
                    # 只更新单个卡片，不重新加载整个列表
                    # 1. 如果分类改变，需要重新加载（因为卡片要移动到新分类）
                    if new_category != asset.category:
                        self._assets_loaded = False
                        self.load_assets_async(force_reload=True)
                        self._load_categories()
                    else:
                        # 2. 只是改名，找到对应卡片更新显示即可
                        for card in self.asset_cards:
                            if card.asset_name == name:
                                card.asset_name = new_name
                                card.name_label.setText(new_name)
                                logger.info(f"已更新卡片显示: {name} -> {new_name}")
                                break
                else:
                    logger.error(f"资产 {name} 信息更新失败")
                    
        except Exception as e:
            logger.error(f"编辑资产信息时出错: {e}", exc_info=True)
    
    def _on_detail_requested(self, name):
        """显示资产详情"""
        logger.info(f"[详情请求] 收到请求: {name}")
        
        try:
            # 通过控制器查找资产
            asset = self.controller.find_asset_by_name(name)
            
            if not asset:
                logger.warning(f"未找到资产: {name}")
                return
            
            logger.info(f"[详情请求] 找到资产: {asset.id}")
            
            # 构建资产数据字典
            asset_data = {
                'id': asset.id,
                'name': asset.name,
                'type': asset.asset_type.value if hasattr(asset.asset_type, 'value') else str(asset.asset_type),
                'category': asset.category,
                'path': asset.path,
                'size': asset.size,
                'created_time': asset.created_time,
                'thumbnail_path': str(asset.thumbnail_path) if asset.thumbnail_path else None,
            }
            
            logger.info(f"[详情请求] 开始创建对话框")
            
            # 获取资产库路径
            library_path = self.logic.get_asset_library_path()
            
            # 创建并显示详情对话框
            dialog = AssetDetailDialog(asset_data, library_path=library_path, parent=self)
            
            logger.info(f"[详情请求] 对话框创建成功")
            
            # 连接信号 - 使用 QueuedConnection 确保对话框关闭后再触发
            dialog.preview_requested.connect(
                lambda asset_id: self._on_preview_from_dialog(asset_id),
                Qt.ConnectionType.QueuedConnection
            )
            dialog.import_requested.connect(
                lambda asset_id: self._on_import_from_dialog(asset_id),
                Qt.ConnectionType.QueuedConnection
            )
            
            # 居中显示
            if hasattr(dialog, 'center_on_parent'):
                dialog.center_on_parent()
                logger.info(f"[详情请求] 对话框已居中")
            
            # 显示对话框
            logger.info(f"[详情请求] 开始显示对话框")
            result = dialog.exec()
            logger.info(f"[详情请求] 对话框关闭，结果: {result}")
            
        except Exception as e:
            logger.error(f"显示资产详情时出错: {e}", exc_info=True)
    
    def _on_preview_from_dialog(self, asset_id: str):
        """从详情对话框触发的预览事件"""
        logger.info(f"[预览] 从详情对话框触发预览，资产ID: {asset_id}")
        
        try:
            asset = self.controller.find_asset_by_id(asset_id)
            
            if asset:
                logger.info(f"[预览] 找到资产名称: {asset.name}，触发预览")
                self._on_preview_asset(asset.name)
            else:
                logger.warning(f"[预览] 未找到资产ID: {asset_id}")
                
        except Exception as e:
            logger.error(f"从详情对话框预览资产时出错: {e}", exc_info=True)
    
    def _on_import_from_dialog(self, asset_id: str):
        """从详情对话框触发的导入事件"""
        logger.info(f"[导入] 从详情对话框触发导入，资产ID: {asset_id}")
        
        try:
            asset = self.controller.find_asset_by_id(asset_id)
            
            if asset:
                logger.info(f"[导入] 找到资产名称: {asset.name}，打开工程搜索窗口")
                self._on_import_asset(asset.name)
            else:
                logger.warning(f"[导入] 未找到资产ID: {asset_id}")
                
        except Exception as e:
            logger.error(f"从详情对话框导入资产时出错: {e}", exc_info=True)

    def _on_delete_asset(self, name):
        """删除资产"""
        try:
            # 通过控制器查找资产
            asset = self.controller.find_asset_by_name(name)

            if not asset:
                logger.warning(f"未找到资产: {name}")
                return

            # 显示确认对话框
            dialog = ConfirmDialog(
                "确认删除",
                f"确定要删除资产 \"{asset.name}\" 吗？",
                "注意：这将永久删除资产库中的文件/文件夹，此操作不可恢复！",
                self
            )
            
            # 居中显示
            if hasattr(dialog, 'center_on_parent'):
                dialog.center_on_parent()

            if dialog.exec() == QDialog.DialogCode.Accepted:
                # 删除资产（包括物理文件）
                success = self.logic.remove_asset(asset.id, delete_physical=True)
                if success:
                    logger.info(f"资产删除成功: {name}")
                    # 从UI中移除该资产卡片
                    if asset.id in self.asset_cards:
                        card = self.asset_cards[asset.id]
                        self.grid_layout.removeWidget(card)
                        card.deleteLater()
                        del self.asset_cards[asset.id]
                    # 重新应用筛选（保持当前分类和搜索状态）
                    self._apply_filter_to_ui()
                else:
                    logger.error(f"资产删除失败: {name}")
        except Exception as e:
            logger.error(f"删除资产时发生错误: {e}", exc_info=True)
    
    def _on_error_occurred(self, error_message: str):
        """处理错误信号，显示消息框"""
        from .message_dialog import MessageDialog
        
        # 创建消息对话框
        dialog = MessageDialog(
            "提示",
            error_message,
            "warning",
            self
        )
        dialog.exec()
        
        logger.info(f"已显示错误提示: {error_message}")
    
    def _navigate_to_settings(self):
        """跳转到设置界面"""
        try:
            # 向上查找主窗口
            main_window = None
            parent = self.parent()
            
            while parent:
                # 查找有show_settings方法的窗口（主窗口）
                if hasattr(parent, 'show_settings'):
                    main_window = parent
                    break
                parent = parent.parent()
            
            if main_window:
                logger.info("找到主窗口，准备跳转到设置界面")
                main_window.show_settings()
            else:
                logger.warning("未找到主窗口，无法跳转到设置界面")
        except Exception as e:
            logger.error(f"跳转到设置界面失败: {e}", exc_info=True)
    
    def _on_thumbnail_updated(self, asset_id: str, thumbnail_path: str):
        """处理缩略图更新信号
        
        Args:
            asset_id: 资产ID
            thumbnail_path: 新的缩略图路径
        """
        try:
            logger.info(f"收到缩略图更新信号: asset_id={asset_id}, thumbnail_path={thumbnail_path}")
            
            # 查找对应的卡片
            if asset_id in self.asset_cards:
                card = self.asset_cards[asset_id]
                
                # 从缓存中移除旧缩略图
                if asset_id in self._thumbnail_cache:
                    del self._thumbnail_cache[asset_id]
                    logger.debug(f"已清除资产 {asset_id} 的缩略图缓存")
                
                # 加载新缩略图
                if Path(thumbnail_path).exists():
                    try:
                        pixmap = QPixmap(str(thumbnail_path))
                        if not pixmap.isNull():
                            # 根据视图模式缩放
                            if self.current_view_mode == "detailed":
                                # 详细视图：212x153
                                scaled_pixmap = pixmap.scaled(
                                    212, 153,
                                    Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                                    Qt.TransformationMode.SmoothTransformation
                                )
                            else:
                                # 紧凑视图：172x115
                                scaled_pixmap = pixmap.scaled(
                                    172, 115,
                                    Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                                    Qt.TransformationMode.SmoothTransformation
                                )
                            
                            # 更新缓存
                            self._thumbnail_cache[asset_id] = scaled_pixmap
                            
                            # 更新卡片显示
                            if hasattr(card, 'thumbnail_label'):
                                card.thumbnail_label.setPixmap(scaled_pixmap)
                                logger.info(f"资产 {asset_id} 的缩略图已更新到UI")
                            else:
                                logger.warning(f"卡片 {asset_id} 没有 thumbnail_label 属性")
                    except Exception as e:
                        logger.error(f"加载新缩略图失败: {e}", exc_info=True)
                else:
                    logger.warning(f"缩略图文件不存在: {thumbnail_path}")
            else:
                logger.warning(f"未找到资产 {asset_id} 的卡片")
                
        except Exception as e:
            logger.error(f"处理缩略图更新时出错: {e}", exc_info=True)
    
    def _show_add_asset_dialog(self):
        """显示添加资产对话框"""
        try:
            # 通过控制器获取已有的资产名称和分类列表
            existing_names = self.controller.get_existing_asset_names()
            categories = self.controller.get_existing_categories_list()
            
            # 创建对话框
            dialog = AddAssetDialog(existing_names, categories, parent=self)
            
            # 居中显示
            dialog.center_on_parent()
            
            # 显示对话框
            if dialog.exec() == AddAssetDialog.DialogCode.Accepted:
                asset_info = dialog.get_asset_info()
                logger.info(f"准备添加资产: {asset_info['name']}")
                
                # 异步添加资产
                self._add_asset_async(asset_info)
                    
        except Exception as e:
            logger.error(f"显示添加资产对话框时出错: {e}", exc_info=True)
    
    def _add_asset_async(self, asset_info):
        """异步添加资产（带进度显示）"""
        from PyQt6.QtCore import QThread, pyqtSignal
        
        class AddAssetThread(QThread):
            progress_update = pyqtSignal(int, int, str)  # current, total, message
            finished = pyqtSignal(bool, object)  # success, asset
            
            def __init__(self, logic, asset_info):
                super().__init__()
                self.logic = logic
                self.asset_info = asset_info
            
            def run(self):
                try:
                    # 调用异步版本的 add_asset
                    result = self.logic.add_asset_async(
                        asset_path=self.asset_info['path'],
                        asset_type=self.asset_info['type'],
                        name=self.asset_info['name'],
                        category=self.asset_info['category'],
                        description="",
                        create_markdown=self.asset_info.get('create_doc', False),
                        progress_callback=self._progress_callback
                    )
                    
                    self.finished.emit(result is not None, result)
                except Exception as e:
                    logger.error(f"添加资产线程出错: {e}", exc_info=True)
                    self.finished.emit(False, None)
            
            def _progress_callback(self, current, total, message):
                self.progress_update.emit(current, total, message)
        
        # 创建进度对话框，传入资产名称
        from .add_asset_progress_dialog import AddAssetProgressDialog
        progress_dialog = AddAssetProgressDialog(asset_info['name'], self)
        progress_dialog.setModal(True)
        
        # 创建并启动线程
        self.add_asset_thread = AddAssetThread(self.logic, asset_info)
        
        # 连接信号
        self.add_asset_thread.progress_update.connect(progress_dialog.update_progress)
        self.add_asset_thread.finished.connect(self._on_add_asset_finished)
        self.add_asset_thread.finished.connect(progress_dialog.close)
        
        # 启动线程和对话框
        self.add_asset_thread.start()
        progress_dialog.show()
    
    def _on_add_asset_finished(self, success, asset):
        """添加资产完成回调"""
        if success and asset:
            logger.info(f"资产添加成功: {asset.name}")
            # 刷新UI
            self._assets_loaded = False
            self.load_assets_async(force_reload=True)
            # 更新分类列表
            self._load_categories()
        else:
            logger.error("资产添加失败")
            # 显示错误消息
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.warning(self, "添加失败", "资产添加失败，请检查文件权限和磁盘空间。")
    
    def _show_add_category_dialog(self):
        """显示分类管理对话框"""
        try:
            from .category_management_dialog import CategoryManagementDialog
            
            # 创建对话框
            dialog = CategoryManagementDialog(self.logic, self)
            
            # 连接信号 - 分类更新后刷新列表和资产
            dialog.categories_updated.connect(self._on_categories_updated)
            
            # 显示对话框（showEvent会自动居中）
            dialog.exec()
                    
        except Exception as e:
            logger.error(f"显示分类管理对话框时出错: {e}", exc_info=True)
    
    def _on_categories_updated(self):
        """分类更新后的处理：刷新分类列表和资产显示"""
        # 刷新分类下拉列表
        self._load_categories()
        # 强制重新加载资产，确保分类标签更新
        self._assets_loaded = False
        self.load_assets_async(force_reload=True)
    
    def dragEnterEvent(self, event: QDragEnterEvent):
        """拖入事件"""
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
            logger.debug("接受拖入操作")
        else:
            event.ignore()
    
    def dragMoveEvent(self, event):
        """拖动事件"""
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            event.ignore()
    
    def dropEvent(self, event: QDropEvent):
        """放下事件"""
        try:
            urls = event.mimeData().urls()
            if not urls:
                return
            
            # 只处理第一个文件/文件夹
            file_path = Path(urls[0].toLocalFile())
            
            if not file_path.exists():
                logger.warning(f"拖入的路径不存在: {file_path}")
                return
            
            logger.info(f"拖入文件: {file_path}")
            
            # 识别资产类型
            from ..logic.asset_model import AssetType
            if file_path.is_dir():
                asset_type = AssetType.PACKAGE
                logger.info("识别为资源包类型")
            else:
                asset_type = AssetType.FILE
                logger.info("识别为文件类型")
            
            # 获取当前选中的分类
            current_category = self.category_filter.currentText()
            if current_category == "全部分类" or current_category == "+ 分类管理":
                current_category = "默认分类"
            
            # 显示添加资产对话框，预填充路径和分类
            self._show_add_asset_dialog_with_prefill(file_path, asset_type, current_category)
            
            event.acceptProposedAction()
            
        except Exception as e:
            logger.error(f"处理拖放操作时出错: {e}", exc_info=True)
    
    def _show_add_asset_dialog_with_prefill(self, file_path: Path, asset_type, default_category: str):
        """显示添加资产对话框（预填充路径和分类）
        
        Args:
            file_path: 文件/文件夹路径
            asset_type: 资产类型
            default_category: 默认分类
        """
        try:
            # 通过控制器获取已有的资产名称和分类列表
            existing_names = self.controller.get_existing_asset_names()
            categories = self.controller.get_existing_categories_list()
            
            # 创建对话框，传入预填充信息
            dialog = AddAssetDialog(
                existing_names, 
                categories, 
                parent=self,
                prefill_path=str(file_path),
                prefill_type=asset_type,
                prefill_category=default_category
            )
            
            # 居中显示
            dialog.center_on_parent()
            
            # 显示对话框
            if dialog.exec() == AddAssetDialog.DialogCode.Accepted:
                asset_info = dialog.get_asset_info()
                logger.info(f"准备添加资产: {asset_info['name']}")
                
                # 异步添加资产
                self._add_asset_async(asset_info)
                    
        except Exception as e:
            logger.error(f"显示添加资产对话框时出错: {e}", exc_info=True)

    def _on_import_asset(self, name: str):
        """导入资产 - 打开工程搜索窗口"""
        logger.info(f"导入资产: {name}")
        try:
            from modules.asset_manager.ui.project_search_window import ProjectSearchWindow
            
            # 如果窗口已存在，先关闭
            if self.project_search_window:
                self.project_search_window.close()
                self.project_search_window = None
            
            # 创建工程搜索窗口，传递资产名称和逻辑层引用
            self.project_search_window = ProjectSearchWindow(None, asset_name=name, logic=self.logic)
            
            # 应用当前主题
            from core.utils.style_system import style_system
            current_theme = "modern_dark" if self.theme == "dark" else "modern_light"
            style_system.apply_to_widget(self.project_search_window, current_theme)
            
            # 设置窗口主题（更新卡片样式）
            self.project_search_window.set_theme(self.theme == "dark")
            
            # 显示窗口
            self.project_search_window.show()
            logger.info("工程搜索窗口已打开")
            
        except Exception as e:
            logger.error(f"打开工程搜索窗口时出错: {e}", exc_info=True)

    def _on_export_asset(self, name: str):
        """导出资产 - 压缩并保存到指定位置"""
        logger.info(f"导出资产: {name}")
        try:
            # 通过控制器查找资产
            asset = self.controller.find_asset_by_name(name)
            
            if not asset:
                logger.error(f"未找到资产: {name}")
                return
            
            if not asset.path or not asset.path.exists():
                logger.error(f"资产路径不存在: {asset.path}")
                from PyQt6.QtWidgets import QMessageBox
                QMessageBox.warning(self, "导出失败", "资产路径不存在")
                return
            
            # 创建并显示导出进度对话框
            from modules.asset_manager.ui.export_progress_dialog import ExportProgressDialog
            
            dialog = ExportProgressDialog(name, asset.path, self)
            dialog.start_export()
            dialog.exec()
            
        except Exception as e:
            logger.error(f"导出资产时出错: {e}", exc_info=True)

    def cleanup(self):
        """清理资源"""
        try:
            # 清理缩略图缓存
            if hasattr(self, '_thumbnail_cache') and self._thumbnail_cache:
                self._thumbnail_cache.cleanup()
                logger.info("缩略图缓存已清理")
        except Exception as e:
            logger.error(f"清理资源时出错: {e}", exc_info=True)
    
    def closeEvent(self, event):
        """窗口关闭事件"""
        self.cleanup()
        super().closeEvent(event)
