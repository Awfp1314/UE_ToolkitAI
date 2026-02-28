# -*- coding: utf-8 -*-

"""
作者推荐界面 - 站点推荐 UI
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
    QPushButton, QScrollArea, QFrame
)
from PyQt6.QtCore import Qt, QUrl
from PyQt6.QtGui import QDesktopServices, QFont, QCursor
from typing import List, Dict, Optional

from core.logger import get_logger

logger = get_logger(__name__)

# 分类图标
CATEGORY_ICONS = {
    "资源网站": "📦",
    "工具": "🔧",
    "论坛": "💬",
    "学习": "📚",
}


class SiteCard(QWidget):
    """站点卡片组件"""
    
    def __init__(self, site: dict, parent=None):
        super().__init__(parent)
        self.site = site
        self.setup_ui()
        
    def setup_ui(self):
        """设置UI"""
        self.setObjectName("SiteCard")
        self.setFixedSize(200, 80)
        self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)  # 让 QSS 背景和 hover 生效
        
        layout = QVBoxLayout()
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(4)
        
        # 站点名称
        name_label = QLabel(self.site.get("name", "未命名"))
        name_label.setObjectName("SiteCardName")
        name_label.setFont(QFont("Microsoft YaHei", 11, QFont.Weight.Bold))
        layout.addWidget(name_label)
        
        # 站点描述
        desc_label = QLabel(self.site.get("description", ""))
        desc_label.setObjectName("SiteCardDesc")
        desc_label.setWordWrap(True)
        layout.addWidget(desc_label)
        
        layout.addStretch()
        self.setLayout(layout)
        
        # 设置工具提示
        self.setToolTip(f"点击访问: {self.site.get('url', '')}")
        
    def mousePressEvent(self, event):
        """点击打开链接"""
        if event.button() == Qt.MouseButton.LeftButton:
            url = self.site.get("url", "")
            if url:
                QDesktopServices.openUrl(QUrl(url))
                logger.info(f"打开链接: {url}")


class SiteRecommendationsUI(QWidget):
    """作者推荐界面"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.logic = None
        self.site_widgets: List[QWidget] = []
        self.setup_ui()
        logger.info("作者推荐 UI 初始化完成")
        
    def setup_ui(self):
        """设置UI"""
        self.setObjectName("SiteRecommendationsUI")
        
        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(25, 20, 25, 20)
        main_layout.setSpacing(15)
        
        # ===== 顶部描述 =====
        desc_label = QLabel("🔗 精选虚幻引擎学习资源、资产商店和开发者社区")
        desc_label.setObjectName("SiteRecommendationsDesc")
        main_layout.addWidget(desc_label)
        
        # 分隔线
        separator = QFrame()
        separator.setObjectName("SiteRecommendationsSeparator")
        separator.setFrameShape(QFrame.Shape.HLine)
        separator.setFixedHeight(1)
        main_layout.addWidget(separator)
        
        # ===== 滚动区域 =====
        scroll_area = QScrollArea()
        scroll_area.setObjectName("SiteRecommendationsScroll")
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        
        # 内容容器
        self.content_widget = QWidget()
        self.content_widget.setObjectName("SiteRecommendationsContent")
        self.content_layout = QVBoxLayout()
        self.content_layout.setContentsMargins(0, 0, 10, 0)
        self.content_layout.setSpacing(20)
        self.content_widget.setLayout(self.content_layout)
        
        scroll_area.setWidget(self.content_widget)
        main_layout.addWidget(scroll_area)
        self.setLayout(main_layout)
    
    def set_logic(self, logic):
        """设置业务逻辑层"""
        self.logic = logic
    
    def update_sites(self, sites: List[Dict[str, str]]):
        """更新站点显示"""
        # 清空现有站点
        for widget in self.site_widgets:
            widget.deleteLater()
        self.site_widgets.clear()
        
        # 清空布局
        while self.content_layout.count():
            item = self.content_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        
        # 按分类组织站点
        categories = {}
        category_order = ["资源网站", "工具", "论坛", "学习"]
        
        for site in sites:
            category = site.get("category", "其他")
            if category not in categories:
                categories[category] = []
            categories[category].append(site)
        
        # 按顺序添加分类
        for category in category_order:
            if category in categories:
                self._add_category_section(category, categories[category])
        
        # 添加其他未分类的站点
        for category, category_sites in categories.items():
            if category not in category_order:
                self._add_category_section(category, category_sites)
        
        self.content_layout.addStretch()
        logger.info(f"更新了 {len(sites)} 个站点")
        
    def _add_category_section(self, category: str, sites: list):
        """添加分类区域"""
        # 分类标题
        icon = CATEGORY_ICONS.get(category, "📁")
        category_label = QLabel(f"{icon} {category}")
        category_label.setObjectName("SiteRecommendationsCategoryLabel")
        category_label.setFont(QFont("Microsoft YaHei", 13, QFont.Weight.Bold))
        self.content_layout.addWidget(category_label)
        self.site_widgets.append(category_label)
        
        # 卡片容器
        cards_container = QWidget()
        cards_container.setObjectName("SiteRecommendationsCardsContainer")
        cards_layout = QVBoxLayout()
        cards_layout.setContentsMargins(0, 5, 0, 0)
        cards_layout.setSpacing(10)
        
        # 每行4个卡片
        row_layout = None
        col_count = 0
        
        for site in sites:
            if col_count == 0:
                row_layout = QHBoxLayout()
                row_layout.setSpacing(12)
                cards_layout.addLayout(row_layout)
            
            card = SiteCard(site)
            row_layout.addWidget(card)
            self.site_widgets.append(card)
            
            col_count += 1
            if col_count >= 4:
                row_layout.addStretch()
                col_count = 0
        
        # 最后一行不满4个时添加弹性空间
        if col_count > 0 and row_layout:
            row_layout.addStretch()
        
        cards_container.setLayout(cards_layout)
        self.content_layout.addWidget(cards_container)
        self.site_widgets.append(cards_container)
    
    def refresh_theme(self):
        """刷新主题样式 - 在主题切换时调用"""
        # QSS 样式由 style_system 统一管理，无需手动刷新
        logger.info("作者推荐主题已刷新")
