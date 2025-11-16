# -*- coding: utf-8 -*-

"""
资产管理器 UI
"""

from pathlib import Path
from collections import OrderedDict

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QScrollArea,
    QGridLayout, QLineEdit, QPushButton, QApplication
)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QObject
from PyQt6.QtGui import QPixmap

from core.logger import get_logger
from .modern_asset_card import ModernAssetCard, CompactAssetCard, format_size, format_time
from .project_selector_dialog import ProjectSelectorDialog

logger = get_logger(__name__)


class AssetManagerUI(QWidget):
    """资产管理器UI"""
    
    # 定义一个信号用于在主线程中重置按钮
    _reset_button_signal = pyqtSignal(str)  # 参数是资产名称
    
    def __init__(self, logic, theme="dark", parent=None):
        super().__init__(parent)
        self.logic = logic
        self.theme = theme
        self.asset_cards = {}

        # 从配置文件读取视图模式（如果存在）
        self.current_view_mode = self._load_view_mode()

        self.card_count = 0
        self.search_text = ""  # 当前搜索文本

        # ⚡ 性能优化：LRU 缩略图缓存（避免重复加载和缩放）
        self._thumbnail_cache = OrderedDict()  # {asset_id: QPixmap}
        self._thumbnail_cache_max_size = 100  # 最多缓存 100 个缩略图

        self._init_ui()
        self._connect_signals()

        # 连接重置按钮信号
        self._reset_button_signal.connect(self._handle_reset_button)

        # 初始化时主动加载主题样式（仅更新样式，不重新加载资产）
        self._apply_theme_styles(theme)

        # 不在初始化时加载资产，改为外部控制加载时机
        # 这样可以在启动界面显示期间异步加载，避免阻塞UI
        self._assets_loaded = False
    
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

        # 添加弹性空间
        filter_layout.addStretch()

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
        self.grid_layout.setSpacing(30)  # 默认详细视图使用30px间距
        self.grid_layout.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)

        scroll_layout.addWidget(self.grid_widget)
        scroll_layout.addStretch()

        scroll_area.setWidget(scroll_content)
        main_layout.addWidget(scroll_area)

        # 保存滚动区域引用，用于后续事件处理
        self.scroll_area = scroll_area
        self.scroll_content = scroll_content

        # 安装事件过滤器，用于处理点击事件
        scroll_area.viewport().installEventFilter(self)
        scroll_content.installEventFilter(self)

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

    def _on_search_changed(self, search_text: str):
        """搜索文本改变事件（实时搜索，使用隐藏/显示优化）"""
        self.search_text = search_text.strip()
        logger.info(f"搜索文本改变: '{self.search_text}'")

        # 使用隐藏/显示机制，而不是每次都重建
        self._filter_assets_by_visibility()

    def _filter_assets_by_visibility(self):
        """通过隐藏/显示机制过滤资产（极速响应，无重建开销）"""
        if not self.logic:
            return
        
        try:
            # 获取匹配的资产列表（保持顺序）
            if self.search_text:
                matched_assets = self.logic.search_assets(self.search_text)
                logger.debug(f"搜索 '{self.search_text}' 找到 {len(matched_assets)} 个资产")
            else:
                matched_assets = self.logic.assets
                logger.debug("显示全部资产")
            
            # 先隐藏所有卡片
            for card in self.asset_cards.values():
                card.setVisible(False)
            
            # 按顺序重新排列匹配的卡片
            visible_index = 0
            for asset in matched_assets:
                card = self.asset_cards.get(asset.id)
                if card:
                    # 计算新的网格位置
                    if self.current_view_mode == "detailed":
                        row = visible_index // 4
                        col = visible_index % 4
                    else:
                        row = visible_index // 5
                        col = visible_index % 5
                    
                    # 移除旧位置
                    self.grid_layout.removeWidget(card)
                    # 添加到新位置
                    self.grid_layout.addWidget(card, row, col)
                    # 显示卡片
                    card.setVisible(True)
                    visible_index += 1
            
            logger.info(f"搜索结果: 显示 {visible_index} 个资产")
            
        except Exception as e:
            logger.error(f"过滤资产失败: {e}", exc_info=True)

    def _refresh_assets(self):
        """刷新资产列表（应用搜索过滤，使用批量优化 + 延迟加载缩略图）"""
        if not self.logic:
            logger.warning("Logic 层未初始化")
            return

        try:
            # 根据搜索文本获取资产列表
            if self.search_text:
                assets = self.logic.search_assets(self.search_text)
                logger.info(f"搜索 '{self.search_text}' 找到 {len(assets)} 个资产")
            else:
                assets = self.logic.assets
                logger.info(f"显示全部 {len(assets)} 个资产")

            # ⚡ 性能优化：禁用更新，避免每次添加卡片时都重绘
            self.grid_widget.setUpdatesEnabled(False)

            try:
                # 清空现有卡片
                self._clear_cards()
                self.card_count = 0

                # 收集需要延迟加载缩略图的卡片
                cards_to_load = []

                # 转换 Asset 对象为字典格式并批量创建卡片（不加载缩略图）
                for i, asset in enumerate(assets):
                    asset_dict = {
                        'id': asset.id,
                        'name': asset.name,
                        'category': asset.category,
                        'size': asset.size,
                        'thumbnail_path': str(asset.thumbnail_path) if asset.thumbnail_path else None,
                        'asset_type': asset.asset_type.value if hasattr(asset.asset_type, 'value') else str(asset.asset_type),
                        'created_time': asset.created_time.isoformat() if hasattr(asset.created_time, 'isoformat') else str(asset.created_time),
                        'has_document': False
                    }
                    card = self._add_asset_card(asset_dict, i, defer_thumbnail=True)
                    if card:
                        cards_to_load.append(card)
            finally:
                # ⚡ 重新启用更新，一次性重绘所有卡片
                self.grid_widget.setUpdatesEnabled(True)
                logger.debug(f"批量刷新了 {len(assets)} 个资产卡片")

            # ⚡ 延迟加载缩略图，避免阻塞 UI
            if cards_to_load:
                QTimer.singleShot(0, lambda: self._batch_load_thumbnails(cards_to_load))

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
    
    def load_assets_async(self, on_complete=None):
        """异步加载资产数据
        
        Args:
            on_complete: 加载完成回调函数
        """
        logger.info(f"开始异步加载资产，已加载状态: {self._assets_loaded}")
        
        if self._assets_loaded:
            logger.info("资产已加载，直接返回")
            if on_complete:
                on_complete()
            return
            
        # 使用QTimer延迟执行，避免阻塞UI
        from PyQt6.QtCore import QTimer
        QTimer.singleShot(10, lambda: self._load_assets_async(on_complete))
    
    def _load_assets_async(self, on_complete=None):
        """实际执行异步加载资产"""
        logger.info("开始执行异步加载资产")

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

            # 立即强制处理事件，让清空操作立即生效
            from PyQt6.QtWidgets import QApplication
            QApplication.processEvents()

            # 转换 Asset 对象为字典格式（兼容现有的卡片创建逻辑）
            assets_data = []
            for asset in assets:
                asset_dict = {
                    'id': asset.id,
                    'name': asset.name,
                    'category': asset.category,
                    'size': asset.size,
                    'path': str(asset.path) if asset.path else None,  # 添加路径字段
                    'thumbnail_path': str(asset.thumbnail_path) if asset.thumbnail_path else None,
                    'asset_type': asset.asset_type.value if hasattr(asset.asset_type, 'value') else str(asset.asset_type),
                    'created_time': asset.created_time.isoformat() if hasattr(asset.created_time, 'isoformat') else str(asset.created_time),
                    'has_document': False  # 可以根据需要从 asset 对象获取
                }
                assets_data.append(asset_dict)

            # 立即开始创建第一批卡片（不使用QTimer延迟）
            self._create_assets_batch(assets_data, 0, on_complete)

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
            if on_complete:
                on_complete()
    
    def _load_assets(self):
        """同步加载资产数据（保留用于主题切换等场景）"""
        # 通过 logic 层获取资产列表
        if not self.logic:
            logger.warning("Logic 层未初始化")
            return

        try:
            # 从 logic 层获取资产列表
            assets = self.logic.assets
            logger.info(f"从 logic 层加载了 {len(assets)} 个资产")

            # 清空现有卡片
            self._clear_cards()
            self.card_count = 0

            # 转换 Asset 对象为字典格式（兼容现有的卡片创建逻辑）
            for i, asset in enumerate(assets):
                asset_dict = {
                    'id': asset.id,
                    'name': asset.name,
                    'category': asset.category,
                    'size': asset.size,
                    'path': str(asset.path) if asset.path else None,  # 添加路径字段
                    'thumbnail_path': str(asset.thumbnail_path) if asset.thumbnail_path else None,
                    'asset_type': asset.asset_type.value if hasattr(asset.asset_type, 'value') else str(asset.asset_type),
                    'created_time': asset.created_time.isoformat() if hasattr(asset.created_time, 'isoformat') else str(asset.created_time),
                    'has_document': False  # 可以根据需要从 asset 对象获取
                }
                self._add_asset_card(asset_dict, i)

        except Exception as e:
            logger.error(f"加载资产失败: {e}", exc_info=True)
    
    def _add_asset_card(self, asset_data, index, defer_thumbnail=False):
        """添加资产卡片

        Args:
            asset_data: 资产数据字典
            index: 索引
            defer_thumbnail: 是否延迟加载缩略图

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

        # 检查是否有文档
        asset_id = asset_data.get('id', '')
        doc_path = Path("F:/UE_Asset/.asset_config/documents") / f"{asset_id}.txt"
        has_document = doc_path.exists() if asset_id else False

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

        # 连接信号
        card.preview_clicked.connect(lambda: self._on_preview_asset(name))
        card.edit_info_requested.connect(self._on_edit_asset_info)
        # open_path_requested 信号不再需要，直接在卡片内部处理
        card.delete_requested.connect(self._on_delete_asset)

        # 添加到网格布局
        self.grid_layout.addWidget(card, row, col)
        self.card_count += 1
        
        # 将卡片添加到字典（用于快速搜索和隐藏/显示）
        if asset_id:
            self.asset_cards[asset_id] = card

        return card

    def _batch_load_thumbnails(self, cards):
        """批量加载缩略图（使用 LRU 缓存，同步加载但批量更新）

        Args:
            cards: 卡片列表
        """
        if not cards:
            return

        cache_hits = 0
        cache_misses = 0

        # 禁用更新，批量加载
        self.grid_widget.setUpdatesEnabled(False)
        try:
            for card in cards:
                # 获取资产 ID（从卡片名称生成，或使用其他唯一标识）
                asset_id = getattr(card, 'name', '')
                thumbnail_path = getattr(card, 'thumbnail_path', None)

                # 检查 LRU 缓存
                if asset_id in self._thumbnail_cache:
                    # 缓存命中，立即显示
                    cached_pixmap = self._thumbnail_cache[asset_id]
                    if cached_pixmap and not cached_pixmap.isNull():
                        if hasattr(card, 'thumbnail_label'):
                            card.thumbnail_label.setPixmap(cached_pixmap)

                        # LRU：移到最后（最近使用）
                        self._thumbnail_cache.move_to_end(asset_id)
                        cache_hits += 1
                        continue

                # 缓存未命中，加载缩略图
                cache_misses += 1
                if thumbnail_path and Path(thumbnail_path).exists():
                    try:
                        pixmap = QPixmap(str(thumbnail_path))
                        if not pixmap.isNull():
                            # 根据视图模式确定目标尺寸
                            if self.current_view_mode == "detailed":
                                target_w, target_h = 212, 153
                            else:
                                target_w, target_h = 172, 115

                            scaled_pixmap = pixmap.scaled(
                                target_w, target_h,
                                Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                                Qt.TransformationMode.SmoothTransformation
                            )

                            # 更新卡片
                            if hasattr(card, 'thumbnail_label'):
                                card.thumbnail_label.setPixmap(scaled_pixmap)

                            # 添加到缓存
                            self._thumbnail_cache[asset_id] = scaled_pixmap

                            # LRU 淘汰：如果超过最大大小，移除最旧的
                            while len(self._thumbnail_cache) > self._thumbnail_cache_max_size:
                                self._thumbnail_cache.popitem(last=False)
                    except Exception as e:
                        logger.error(f"加载缩略图失败 {thumbnail_path}: {e}")
        finally:
            self.grid_widget.setUpdatesEnabled(True)

        if cache_hits > 0 or cache_misses > 0:
            logger.debug(f"批量加载 {len(cards)} 个缩略图 (缓存命中: {cache_hits}, 缓存未命中: {cache_misses})")

    def _load_view_mode(self) -> str:
        """从配置文件加载视图模式

        Returns:
            str: 视图模式 ("detailed" 或 "compact")
        """
        try:
            if self.logic and self.logic.config_manager:
                config = self.logic.config_manager.load_user_config()
                view_mode = config.get("view_mode", "detailed")
                logger.info(f"从配置加载视图模式: {view_mode}")
                return view_mode
        except Exception as e:
            logger.warning(f"加载视图模式失败，使用默认值: {e}")

        return "detailed"  # 默认详细视图

    def _save_view_mode(self):
        """保存视图模式到配置文件（使用快速保存，避免卡顿）"""
        try:
            if self.logic and self.logic.config_manager:
                config = self.logic.config_manager.load_user_config()
                config["view_mode"] = self.current_view_mode
                # 使用快速保存方法，跳过备份和验证，避免退出时卡顿
                self.logic.config_manager.save_user_config_fast(config)
                logger.debug(f"已快速保存视图模式: {self.current_view_mode}")
        except Exception as e:
            logger.warning(f"保存视图模式失败: {e}")

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

        # 定义进度回调函数
        def update_progress(current, total, message):
            """ProgressButton 进度回调"""
            if total > 0:
                progress = current / total
                preview_btn.set_progress(progress)
                # 显示百分比
                percentage = int(progress * 100)
                preview_btn.update_button_text(f"{percentage}%")

                # 如果进度达到100%（复制完成），显示成功提示
                if progress >= 1.0:
                    logger.info(f"文件复制完成: {name}")
                    preview_btn.update_button_text("✓ 复制成功")
                    # 1.5秒后发送重置信号
                    self._reset_button_signal.emit(name)
            else:
                # 无进度信息时显示消息（如启动引擎等）
                preview_btn.update_button_text(message)

        # 设置初始状态
        preview_btn.update_button_text("0%")
        preview_btn.set_progress(0.0)

        # 调用logic层的预览功能，使用用户选择的预览工程
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

    def _on_delete_asset(self, name):
        """删除资产"""
        try:
            # 通过名称查找资产
            asset = None
            for a in self.logic.assets:
                if a.name == name:
                    asset = a
                    break

            if not asset:
                logger.warning(f"未找到资产: {name}")
                return

            # 导入确认对话框
            from .confirm_dialog import ConfirmDialog

            # 显示确认对话框
            dialog = ConfirmDialog(
                "确认删除",
                f"确定要删除资产 \"{asset.name}\" 吗？",
                "注意：这将永久删除资产库中的文件/文件夹，此操作不可恢复！",
                self
            )

            if dialog.exec() == QDialog.DialogCode.Accepted:
                # 删除资产（包括物理文件）
                success = self.logic.remove_asset(asset.id, delete_physical=True)
                if success:
                    logger.info(f"资产删除成功: {name}")
                    # 重新加载资产列表
                    self._load_assets()
                else:
                    logger.error(f"资产删除失败: {name}")
        except Exception as e:
            logger.error(f"删除资产时发生错误: {e}", exc_info=True)
