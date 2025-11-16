# -*- coding: utf-8 -*-

"""
现代深色主题配置

从 ui/ue_main_window.py 的 _get_dark_theme_stylesheet() 方法中提取的颜色值
"""

THEME_NAME = "modern_dark"
THEME_DISPLAY_NAME = "现代深色"

# ===== 主色调 =====
COLORS = {
    # 主色调（蓝色系）
    'primary': '#4a9eff',
    'primary_hover': '#5aa9ff',
    'primary_active': '#3a8eef',
    'primary_light': 'rgba(74, 158, 255, 0.1)',
    'primary_border': 'rgba(74, 158, 255, 0.3)',
    'primary_border_hover': 'rgba(74, 158, 255, 0.5)',
    'primary_border_active': 'rgba(74, 158, 255, 0.8)',
    
    # 背景色（深色渐变）
    'bg_gradient_start': '#1c1c1c',
    'bg_gradient_end': '#2c2c2c',
    'bg_primary': '#1c1c1c',
    'bg_secondary': '#252525',
    'bg_tertiary': '#2c2c2c',
    'bg_hover': 'rgba(255, 255, 255, 0.05)',
    'bg_active': 'rgba(255, 255, 255, 0.1)',
    'bg_transparent': 'transparent',
    
    # 左侧面板渐变
    'sidebar_gradient_start': '#1c1c1c',
    'sidebar_gradient_mid': '#1a1a1a',
    'sidebar_gradient_end': '#181818',
    
    # 文本色
    'text_primary': '#ffffff',
    'text_secondary': 'rgba(255, 255, 255, 0.7)',
    'text_tertiary': 'rgba(255, 255, 255, 0.55)',
    'text_quaternary': 'rgba(255, 255, 255, 0.5)',
    'text_disabled': 'rgba(255, 255, 255, 0.3)',
    'text_very_disabled': 'rgba(255, 255, 255, 0.2)',
    'text_hover': 'rgba(255, 255, 255, 0.95)',
    
    # 边框色
    'border_primary': 'rgba(255, 255, 255, 0.2)',
    'border_secondary': 'rgba(255, 255, 255, 0.15)',
    'border_tertiary': 'rgba(255, 255, 255, 0.1)',
    'border_quaternary': 'rgba(255, 255, 255, 0.08)',
    'border_focus': 'rgba(74, 158, 255, 0.5)',
    
    # 导航按钮渐变（悬停）
    'nav_hover_gradient_start': 'rgba(74, 158, 255, 0.15)',
    'nav_hover_gradient_mid': 'rgba(74, 158, 255, 0.08)',
    'nav_hover_gradient_end': 'rgba(74, 158, 255, 0.03)',
    
    # 导航按钮渐变（选中）
    'nav_checked_gradient_start': 'rgba(74, 158, 255, 0.4)',
    'nav_checked_gradient_mid': 'rgba(74, 158, 255, 0.25)',
    'nav_checked_gradient_end': 'rgba(74, 158, 255, 0.15)',
    
    # 导航按钮渐变（选中+悬停）
    'nav_checked_hover_gradient_start': 'rgba(74, 158, 255, 0.5)',
    'nav_checked_hover_gradient_mid': 'rgba(74, 158, 255, 0.35)',
    'nav_checked_hover_gradient_end': 'rgba(74, 158, 255, 0.2)',
    
    # 导航按钮渐变（按下）
    'nav_pressed_gradient_start': 'rgba(74, 158, 255, 0.3)',
    'nav_pressed_gradient_end': 'rgba(74, 158, 255, 0.15)',
    
    # 导航按钮边框
    'nav_border_hover': 'rgba(74, 158, 255, 0.3)',
    'nav_border_checked': 'rgba(74, 158, 255, 0.6)',
    'nav_border_checked_hover': 'rgba(74, 158, 255, 0.8)',
    'nav_border_pressed': 'rgba(74, 158, 255, 0.5)',
    
    # 状态色
    'success': '#10a37f',
    'warning': '#ff9800',
    'error': '#ef4444',
    'info': '#4a9eff',
    
    # 滚动条
    'scrollbar_track': 'rgba(255, 255, 255, 0.05)',
    'scrollbar_thumb': 'rgba(255, 255, 255, 0.2)',
    'scrollbar_thumb_hover': 'rgba(255, 255, 255, 0.3)',
    'scrollbar_thumb_pressed': 'rgba(255, 255, 255, 0.4)',
    'scrollbar_handle': 'rgba(255, 255, 255, 0.3)',
    'scrollbar_handle_hover': 'rgba(255, 255, 255, 0.5)',
    
    # 特殊按钮
    'close_button_hover': '#e81123',
    'window_button_hover': 'rgba(255, 255, 255, 0.15)',

    # Logo渐变
    'logo_gradient_start': '#ffffff',
    'logo_gradient_end': 'rgba(255, 255, 255, 0.7)',

    # 分隔线渐变
    'separator_gradient_start': 'transparent',
    'separator_gradient_mid': 'rgba(255, 255, 255, 0.15)',
    'separator_gradient_end': 'transparent',

    # 状态标签（StatusTag）- 保持原样不变量化
    'status_tag_color': 'rgba(74, 158, 255, 1)',
    'status_tag_bg': 'rgba(74, 158, 255, 0.15)',
    'status_tag_border': 'rgba(74, 158, 255, 0.4)',

    # 进度点（ProgressDot）
    'progress_dot_color': 'rgba(74, 158, 255, 0.6)',

    # 主题切换按钮按下状态（保持原样）
    'theme_button_pressed_bg': 'rgba(74, 158, 255, 0.15)',
    'theme_button_pressed_border': 'rgba(74, 158, 255, 0.4)',

    # ===== 启动加载界面 =====
    # 容器渐变
    'splash_container_gradient_start': '#1a2332',
    'splash_container_gradient_mid': '#0f1419',
    'splash_container_gradient_end': '#000000',

    # 边框和文字
    'splash_border': '#4a9eff',
    'splash_title_color': '#ffffff',
    'splash_message_color': '#b0b0b0',
    'splash_percentage_color': '#4a9eff',
    'splash_version_color': '#666666',

    # 进度条
    'splash_progress_bg': 'rgba(45, 45, 45, 0.8)',
    'splash_progress_chunk_start': '#4a9eff',
    'splash_progress_chunk_mid': '#5aa9ff',
    'splash_progress_chunk_end': '#6bb6ff',

    # 发光效果
    'splash_shadow_color': 'rgba(74, 158, 255, 100)',
    
    # ===== 资产管理器 =====
    # 搜索框
    'search_input_bg': '#303030',
    'search_input_bg_focus': '#323232',
    'search_input_border': 'none',
    'search_input_border_focus': 'none',
    'search_input_placeholder': 'rgba(255, 255, 255, 0.5)',
    
    # 卡片
    'card_bg': '#242424',
    'card_bg_hover': '#282828',
    'card_border': 'rgba(255, 255, 255, 0.12)',
    'card_border_hover': 'rgba(255, 255, 255, 0.2)',
    
    # 分类标签渐变
    'category_gradient': 'qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 rgba(74, 158, 255, 0.25), stop:1 rgba(74, 158, 255, 0.15))',
    
    # 类型标签
    'type_label_bg': 'rgba(255, 255, 255, 0.08)',
    'type_label_text': 'rgba(255, 255, 255, 0.65)',
    
    # 分隔线
    'separator': 'rgba(255, 255, 255, 0.12)',
    
    # 次要按钮（预览）
    'button_secondary_bg': 'rgba(255, 255, 255, 0.08)',
    'button_secondary_text': 'rgba(255, 255, 255, 0.8)',
    'button_secondary_border': 'rgba(255, 255, 255, 0.15)',
    'button_secondary_bg_hover': 'rgba(255, 255, 255, 0.15)',
    'button_secondary_border_hover': 'rgba(255, 255, 255, 0.25)',
    'button_secondary_bg_active': 'rgba(255, 255, 255, 0.20)',
    'button_secondary_border_active': 'rgba(255, 255, 255, 0.30)',
    
    # 主要按钮（导入）
    'button_primary_bg': 'rgba(74, 158, 255, 0.15)',
    'button_primary_text': '#4a9eff',
    'button_primary_border': 'rgba(74, 158, 255, 0.3)',
    'button_primary_bg_hover': 'rgba(74, 158, 255, 0.25)',
    'button_primary_border_hover': 'rgba(74, 158, 255, 0.5)',
    'button_primary_bg_active': 'rgba(74, 158, 255, 0.35)',
    'button_primary_border_active': 'rgba(74, 158, 255, 0.6)',
    
    # 菜单
    'menu_bg': '#2c2c2c',
    'menu_border': 'rgba(255, 255, 255, 0.15)',
    'menu_text': 'rgba(255, 255, 255, 0.85)',
    'menu_item_hover': 'rgba(255, 255, 255, 0.1)',
    'menu_separator': 'rgba(255, 255, 255, 0.1)',

    # ===== 资产卡片专属样式 =====
    # 卡片背景渐变
    'asset_card_bg_start': '#383838',
    'asset_card_bg_mid1': '#323232',
    'asset_card_bg_mid2': '#2c2c2c',
    'asset_card_bg_end': '#282828',
    'asset_card_border': '#454545',

    # 卡片悬停渐变
    'asset_card_hover_start': '#424242',
    'asset_card_hover_mid1': '#3c3c3c',
    'asset_card_hover_mid2': '#363636',
    'asset_card_hover_end': '#323232',
    'asset_card_border_hover': 'rgba(255, 255, 255, 0.6)',

    # 分类标签
    'asset_category_bg': '#000000',
    'asset_category_text': '#b0b0b0',

    # 资产名称
    'asset_name_text': '#ffffff',

    # 分隔线渐变
    'asset_separator_start': 'rgba(74, 158, 255, 0.3)',
    'asset_separator_mid': 'rgba(74, 158, 255, 0.5)',
    'asset_separator_end': 'rgba(74, 158, 255, 0.3)',

    # 信息标签
    'asset_info_title_text': '#888888',
    'asset_info_value_text': '#ffffff',

    # 导入按钮
    'asset_import_btn_text': 'rgba(255, 255, 255, 0.7)',
    'asset_import_btn_hover_bg': 'rgba(255, 255, 255, 0.1)',
    'asset_import_btn_active_bg': 'rgba(255, 255, 255, 0.15)',

    # ===== 预览工程选择对话框 =====
    # 对话框背景（使用现有的bg_secondary: #252525）
    # 对话框内容区（使用现有的bg_tertiary: #2c2c2c）
    # 边框（使用现有的border_primary）
    'border_shadow': '#1a1a1a',  # 标题栏阴影色
    'combo_item_hover': '#353535',  # 下拉框项悬停色
}

# ===== 圆角覆盖（主题特定） =====
BORDER_RADIUS_OVERRIDE = {
    'container': '16px',      # 主容器圆角
    'title_bar': '16px',      # 标题栏圆角
    'button': '10px',         # 导航按钮圆角
    'window_button': '6px',   # 窗口控制按钮圆角
    'theme_button': '8px',    # 主题切换按钮圆角
    'input': '8px',           # 输入框圆角
    'small': '6px',           # 小按钮圆角
}

