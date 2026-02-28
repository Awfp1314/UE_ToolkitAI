# -*- coding: utf-8 -*-

"""
现代浅色主题配置

基于 modern_dark 主题，反转颜色创建浅色版本
"""

THEME_NAME = "modern_light"
THEME_DISPLAY_NAME = "现代浅色"

# ===== 主色调 =====
COLORS = {
    # 主色调（蓝色系 - 保持不变）
    'primary': '#4a9eff',
    'primary_color': '#4a9eff',  # 主色调别名
    'primary_hover': '#5aa9ff',
    'primary_hover_color': '#5aa9ff',  # 主色调悬停别名
    'primary_active': '#3a8eef',
    'primary_pressed_color': '#3a8eef',  # 主色调按下别名
    'primary_light': 'rgba(74, 158, 255, 0.1)',
    'primary_border': 'rgba(74, 158, 255, 0.3)',
    'primary_border_hover': 'rgba(74, 158, 255, 0.5)',
    'primary_border_active': 'rgba(74, 158, 255, 0.8)',
    'button_text_color': '#ffffff',  # 按钮文字颜色
    
    # 背景色（浅色渐变）
    'bg_gradient_start': '#f5f5f5',
    'bg_gradient_end': '#e8e8e8',
    'bg_primary': '#ffffff',
    'bg_secondary': '#f8f8f8',
    'bg_tertiary': '#f0f0f0',
    'bg_hover': 'rgba(0, 0, 0, 0.08)',
    'bg_active': 'rgba(0, 0, 0, 0.15)',
    'bg_transparent': 'transparent',
    'dialog_bg': '#f5f5f5',  # 对话框背景
    
    # 左侧面板渐变（浅色）
    'sidebar_gradient_start': '#fafafa',
    'sidebar_gradient_mid': '#f5f5f5',
    'sidebar_gradient_end': '#f0f0f0',
    
    # 文本色（深色文字）
    'text_primary': '#1a1a1a',
    'text_secondary': 'rgba(0, 0, 0, 0.7)',
    'text_tertiary': 'rgba(0, 0, 0, 0.55)',
    'text_quaternary': 'rgba(0, 0, 0, 0.5)',
    'text_disabled': 'rgba(0, 0, 0, 0.3)',
    'text_very_disabled': 'rgba(0, 0, 0, 0.2)',
    'text_hover': 'rgba(0, 0, 0, 0.95)',
    
    # 边框色（深色边框）
    'border_primary': 'rgba(0, 0, 0, 0.2)',
    'border_secondary': 'rgba(0, 0, 0, 0.15)',
    'border_tertiary': 'rgba(0, 0, 0, 0.1)',
    'border_quaternary': 'rgba(0, 0, 0, 0.08)',
    'border_focus': 'rgba(74, 158, 255, 0.5)',
    'input_border': '1px solid rgba(0, 0, 0, 0.15)',  # 输入框边框
    
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
    
    # 状态色（保持不变）
    'success': '#10a37f',
    'warning': '#ff9800',
    'error': '#ef4444',
    'info': '#4a9eff',
    
    # 滚动条（深色）
    'scrollbar_track': 'rgba(0, 0, 0, 0.05)',
    'scrollbar_thumb': 'rgba(0, 0, 0, 0.2)',
    'scrollbar_thumb_hover': 'rgba(0, 0, 0, 0.3)',
    'scrollbar_thumb_pressed': 'rgba(0, 0, 0, 0.4)',
    'scrollbar_handle': 'rgba(0, 0, 0, 0.3)',
    'scrollbar_handle_hover': 'rgba(0, 0, 0, 0.5)',
    
    # 特殊按钮
    'close_button_hover': '#e81123',
    'window_button_hover': 'rgba(0, 0, 0, 0.15)',

    # Logo渐变（深色文字）
    'logo_gradient_start': '#1a1a1a',
    'logo_gradient_end': 'rgba(0, 0, 0, 0.7)',

    # 分隔线渐变（深色）
    'separator_gradient_start': 'transparent',
    'separator_gradient_mid': 'rgba(0, 0, 0, 0.15)',
    'separator_gradient_end': 'transparent',

    # 状态标签（StatusTag）
    'status_tag_color': 'rgba(74, 158, 255, 1)',
    'status_tag_bg': 'rgba(74, 158, 255, 0.15)',
    'status_tag_border': 'rgba(74, 158, 255, 0.4)',

    # 进度点（ProgressDot）
    'progress_dot_color': 'rgba(74, 158, 255, 0.6)',

    # 主题切换按钮按下状态
    'theme_button_pressed_bg': 'rgba(74, 158, 255, 0.15)',
    'theme_button_pressed_border': 'rgba(74, 158, 255, 0.4)',

    # ===== 启动加载界面 =====
    # 容器渐变
    'splash_container_gradient_start': '#ffffff',
    'splash_container_gradient_mid': '#f5f5f5',
    'splash_container_gradient_end': '#e8e8e8',

    # 边框和文字
    'splash_border': '#4a9eff',
    'splash_title_color': '#1a1a1a',
    'splash_message_color': '#666666',
    'splash_percentage_color': '#4a9eff',
    'splash_version_color': '#999999',

    # 进度条
    'splash_progress_bg': 'rgba(200, 200, 200, 0.5)',
    'splash_progress_chunk_start': '#4a9eff',
    'splash_progress_chunk_mid': '#5aa9ff',
    'splash_progress_chunk_end': '#6bb6ff',

    # 发光效果
    'splash_shadow_color': 'rgba(74, 158, 255, 80)',
    
    # ===== 资产管理器 =====
    # 搜索框（增强对比度）
    'search_input_bg': '#f5f5f5',
    'search_input_bg_focus': '#eeeeee',
    'search_input_border': '1px solid rgba(0, 0, 0, 0.12)',
    'search_input_border_focus': '1px solid rgba(74, 158, 255, 0.5)',
    'search_input_placeholder': 'rgba(0, 0, 0, 0.4)',
    
    # 卡片
    'card_bg': '#ffffff',
    'card_bg_hover': '#fafafa',
    'card_border': 'rgba(0, 0, 0, 0.12)',
    'card_border_hover': 'rgba(0, 0, 0, 0.2)',
    
    # 分类标签渐变
    'category_gradient': 'qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 rgba(74, 158, 255, 0.25), stop:1 rgba(74, 158, 255, 0.15))',
    
    # 类型标签
    'type_label_bg': 'rgba(0, 0, 0, 0.08)',
    'type_label_text': 'rgba(0, 0, 0, 0.65)',
    
    # 分隔线
    'separator': 'rgba(0, 0, 0, 0.12)',
    
    # 次要按钮（预览）
    'button_secondary_bg': 'rgba(0, 0, 0, 0.08)',
    'button_secondary_text': 'rgba(0, 0, 0, 0.8)',
    'button_secondary_border': 'rgba(0, 0, 0, 0.15)',
    'button_secondary_hover': 'rgba(0, 0, 0, 0.12)',
    'button_secondary_active': 'rgba(0, 0, 0, 0.15)',
    'button_secondary_bg_hover': 'rgba(0, 0, 0, 0.15)',
    'button_secondary_border_hover': 'rgba(0, 0, 0, 0.25)',
    'button_secondary_bg_active': 'rgba(0, 0, 0, 0.20)',
    'button_secondary_border_active': 'rgba(0, 0, 0, 0.30)',
    
    # 主要按钮（导入）
    'button_primary_bg': 'rgba(74, 158, 255, 0.15)',
    'button_primary_text': '#4a9eff',
    'button_primary_border': 'rgba(74, 158, 255, 0.3)',
    'button_primary_bg_hover': 'rgba(74, 158, 255, 0.25)',
    'button_primary_border_hover': 'rgba(74, 158, 255, 0.5)',
    'button_primary_bg_active': 'rgba(74, 158, 255, 0.35)',
    'button_primary_border_active': 'rgba(74, 158, 255, 0.6)',
    
    # 菜单
    'menu_bg': '#ffffff',
    'menu_border': 'rgba(0, 0, 0, 0.15)',
    'menu_text': 'rgba(0, 0, 0, 0.85)',
    'menu_item_hover': 'rgba(0, 0, 0, 0.1)',
    'menu_separator': 'rgba(0, 0, 0, 0.1)',

    # ===== 资产卡片专属样式 =====
    # 卡片背景渐变（浅色）
    'asset_card_bg_start': '#ffffff',
    'asset_card_bg_mid1': '#fafafa',
    'asset_card_bg_mid2': '#f5f5f5',
    'asset_card_bg_end': '#f8f9fa',
    'asset_card_border': '#e8e8e8',

    # 卡片悬停渐变（浅色）
    'asset_card_hover_start': '#ffffff',
    'asset_card_hover_mid1': '#fefefe',
    'asset_card_hover_mid2': '#fcfcfc',
    'asset_card_hover_end': '#fafafa',
    'asset_card_border_hover': 'rgba(0, 0, 0, 0.4)',

    # 分类标签（浅色）
    # 使用黑色背景 + 灰白色文字，与深色主题保持一致
    'asset_category_bg': '#000000',
    'asset_category_text': '#b0b0b0',

    # 资产名称（浅色）
    'asset_name_text': '#1a1a1a',

    # 分隔线渐变（浅色）
    'asset_separator_start': 'rgba(74, 158, 255, 0.4)',
    'asset_separator_mid': 'rgba(74, 158, 255, 0.6)',
    'asset_separator_end': 'rgba(74, 158, 255, 0.4)',

    # 信息标签（浅色）
    'asset_info_title_text': '#999999',
    'asset_info_value_text': '#1a1a1a',

    # 导入按钮（浅色）
    'asset_import_btn_text': 'rgba(0, 0, 0, 0.65)',
    'asset_import_btn_hover_bg': 'rgba(0, 0, 0, 0.08)',
    'asset_import_btn_active_bg': 'rgba(0, 0, 0, 0.12)',

    # ===== 预览工程选择对话框 =====
    # 对话框背景（使用现有的bg_secondary: #f8f8f8）
    # 对话框内容区（使用现有的bg_tertiary: #f0f0f0）
    # 边框（使用现有的border_primary）
    'border_shadow': '#909090',  # 标题栏阴影色
    'combo_item_hover': '#e8e8e8',  # 下拉框项悬停色
    
    # ===== 编辑资产对话框 =====
    # 输入框
    'input_bg': 'rgba(0, 0, 0, 0.08)',
    'input_bg_hover': 'rgba(0, 0, 0, 0.12)',
    
    # 文档管理按钮 - 编辑
    'doc_button_bg_start': 'rgba(99, 102, 241, 0.12)',
    'doc_button_bg_end': 'rgba(139, 92, 246, 0.12)',
    'doc_button_text': '#6366f1',
    'doc_button_border': 'rgba(99, 102, 241, 0.25)',
    'doc_button_bg_start_hover': 'rgba(99, 102, 241, 0.18)',
    'doc_button_bg_end_hover': 'rgba(139, 92, 246, 0.18)',
    'doc_button_border_hover': 'rgba(99, 102, 241, 0.4)',
    'doc_button_text_hover': '#4f46e5',
    'doc_button_bg_start_pressed': 'rgba(99, 102, 241, 0.25)',
    'doc_button_bg_end_pressed': 'rgba(139, 92, 246, 0.25)',
    
    # 文档管理按钮 - 删除
    'delete_button_bg_start': 'rgba(239, 68, 68, 0.12)',
    'delete_button_bg_end': 'rgba(220, 38, 38, 0.12)',
    'delete_button_text': '#ef4444',
    'delete_button_border': 'rgba(239, 68, 68, 0.25)',
    'delete_button_bg_start_hover': 'rgba(239, 68, 68, 0.18)',
    'delete_button_bg_end_hover': 'rgba(220, 38, 38, 0.18)',
    'delete_button_border_hover': 'rgba(239, 68, 68, 0.4)',
    'delete_button_text_hover': '#dc2626',
    'delete_button_bg_start_pressed': 'rgba(239, 68, 68, 0.25)',
    'delete_button_bg_end_pressed': 'rgba(220, 38, 38, 0.25)',
    
    # 文档管理按钮 - 创建
    'create_button_bg_start': 'rgba(99, 102, 241, 0.15)',
    'create_button_bg_end': 'rgba(139, 92, 246, 0.15)',
    'create_button_text': '#6366f1',
    'create_button_border': 'rgba(99, 102, 241, 0.3)',
    'create_button_bg_start_hover': 'rgba(99, 102, 241, 0.22)',
    'create_button_bg_end_hover': 'rgba(139, 92, 246, 0.22)',
    'create_button_border_hover': 'rgba(99, 102, 241, 0.5)',
    'create_button_text_hover': '#4f46e5',
    'create_button_bg_start_pressed': 'rgba(99, 102, 241, 0.3)',
    'create_button_bg_end_pressed': 'rgba(139, 92, 246, 0.3)',
    
    # ===== AI助手聊天输入框 =====
    # 聊天区域
    'chat_area_bg': '#EFEFEF',
    
    # 输入框容器
    'chat_input_bg': '#F0F0F0',
    'chat_input_border': 'rgba(0, 0, 0, 0.1)',
    'chat_input_text': '#0D0D0D',
    'chat_input_selection': 'rgba(16, 163, 127, 0.3)',
    
    # 滚动条
    'chat_input_scrollbar': 'rgba(0, 0, 0, 0.2)',
    'chat_input_scrollbar_hover': 'rgba(0, 0, 0, 0.4)',
    
    # 按钮
    'chat_button_hover_bg': 'rgba(200, 200, 200, 0.5)',
    'chat_send_button_bg': '#000000',
    'chat_send_button_hover_bg': '#202123',
    'chat_send_button_disabled_bg': '#DCDCDC',
    
    # ===== 用户消息气泡 =====
    'user_message_bg': '#E3E3E3',  # 更深的灰色，提高可见度
    'user_message_text': '#0D0D0D',
    'user_message_copy_hover': 'rgba(0, 0, 0, 0.15)',  # 悬停背景也加深一些
    
    # ===== AI回复消息 =====
    'ai_message_text': '#0D0D0D',
    
    # ===== AI消息操作按钮 =====
    'action_button_hover_dark': '#40414f',
    'action_button_pressed_dark': '#2a2b32',
    'action_button_hover_light': '#f6f8fa',
    'action_button_pressed_light': '#e1e4e8',
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

