# -*- coding: utf-8 -*-

"""
核心常量定义
集中管理所有核心常量，避免魔法数字
"""

# ============================================================================
# 线程管理常量 (Thread Management Constants)
# ============================================================================

# 线程池配置
THREAD_POOL_SIZE = 4  # 默认线程池大小
THREAD_QUEUE_SIZE = 100  # 任务队列最大容量
THREAD_TIMEOUT_MS = 30000  # 默认任务超时时间（毫秒）
THREAD_GRACE_PERIOD_MS = 5000  # 超时后的宽限期（毫秒）
THREAD_CLEANUP_TIMEOUT_MS = 10000  # 清理超时时间（毫秒）
THREAD_RETRY_DELAY_MS = 100  # 重试延迟（毫秒）

# ============================================================================
# 配置管理常量 (Configuration Management Constants)
# ============================================================================

# 配置文件
CONFIG_FILE_LOCK_TIMEOUT_SECONDS = 5.0  # 文件锁超时时间（秒）
CONFIG_RETRY_DELAY_SECONDS = 0.5  # 配置保存重试延迟（秒）
CONFIG_PENDING_EVENTS_MAX_SIZE = 100  # 待上报事件队列最大容量

# 配置缓存
CONFIG_CACHE_TTL_SECONDS = 300  # 配置缓存生存时间（5分钟）

# 配置备份
BACKUP_RETENTION_COUNT = 5  # 保留的备份文件数量
BACKUP_INTERVAL_SECONDS = 3600  # 备份间隔时间（1小时）

# ============================================================================
# UI 常量 (UI Constants)
# ============================================================================

# 窗口尺寸
WINDOW_DEFAULT_WIDTH = 1280  # 默认窗口宽度
WINDOW_DEFAULT_HEIGHT = 800  # 默认窗口高度（16:10 黄金比例）
WINDOW_MIN_WIDTH = 800  # 最小窗口宽度
WINDOW_MIN_HEIGHT = 600  # 最小窗口高度

# 标题栏
TITLEBAR_HEIGHT = 40  # 标题栏高度
TITLEBAR_ICON_SIZE = 24  # 标题栏图标大小
TITLEBAR_BUTTON_WIDTH = 32  # 标题栏按钮宽度
TITLEBAR_BUTTON_HEIGHT = 28  # 标题栏按钮高度

# 左侧导航栏
LEFT_PANEL_WIDTH = 200  # 左侧导航栏宽度
LOGO_CONTAINER_HEIGHT = 60  # Logo 容器高度
NAV_BUTTON_HEIGHT = 38  # 导航按钮高度
FEEDBACK_BUTTON_HEIGHT = 36  # 反馈按钮高度

# 右侧内容区
RIGHT_PANEL_MARGIN_TOP = 40  # 右侧内容区顶部边距
RIGHT_PANEL_MARGIN_BOTTOM = 15  # 右侧内容区底部边距
RIGHT_PANEL_MARGIN_LEFT = 40  # 右侧内容区左侧边距
RIGHT_PANEL_MARGIN_RIGHT = 40  # 右侧内容区右侧边距

# 按钮尺寸
ICON_BUTTON_SIZE = 40  # 图标按钮尺寸（设置、主题切换等）
UPDATE_BUTTON_WIDTH = 80  # 更新按钮宽度
UPDATE_BUTTON_HEIGHT = 28  # 更新按钮高度
UPDATE_BADGE_SIZE = 8  # 更新徽章尺寸

# 动画持续时间
ANIMATION_DURATION_MS = 300  # 默认动画持续时间（毫秒）
FADE_ANIMATION_DURATION_MS = 200  # 淡入淡出动画持续时间（毫秒）
SLIDE_ANIMATION_DURATION_MS = 250  # 滑动动画持续时间（毫秒）

# 防抖延迟
DEBOUNCE_DELAY_MS = 300  # 默认防抖延迟（毫秒）
SEARCH_DEBOUNCE_DELAY_MS = 500  # 搜索防抖延迟（毫秒）
THEME_TOGGLE_DEBOUNCE_MS = 300  # 主题切换防抖延迟（毫秒）

# ============================================================================
# 性能常量 (Performance Constants)
# ============================================================================

# 启动性能目标
STARTUP_TIME_TARGET_MS = 2000  # 启动时间目标（毫秒）
MEMORY_USAGE_TARGET_MB = 400  # 内存使用目标（MB）

# 资产扫描性能
ASSET_SCAN_TARGET_MS = 800  # 资产扫描时间目标（毫秒）
ASSET_SCAN_BATCH_SIZE = 100  # 资产扫描批次大小

# 缩略图性能
THUMBNAIL_LOAD_TARGET_MS = 100  # 缩略图加载时间目标（毫秒）
THUMBNAIL_CACHE_SIZE = 100  # 缩略图缓存大小（项数）
THUMBNAIL_CACHE_MEMORY_TARGET_MB = 30  # 缩略图缓存内存目标（MB）

# ============================================================================
# 文件系统常量 (File System Constants)
# ============================================================================

# 文件权限（Unix）
FILE_PERMISSION_USER_RW = 0o600  # 用户读写权限
FILE_PERMISSION_USER_RWX = 0o700  # 用户读写执行权限

# 临时文件
TEMP_FILE_PREFIX = '.tmp_'  # 临时文件前缀

# ============================================================================
# 网络常量 (Network Constants)
# ============================================================================

# HTTP 超时
HTTP_CONNECT_TIMEOUT_SECONDS = 10  # HTTP 连接超时（秒）
HTTP_READ_TIMEOUT_SECONDS = 30  # HTTP 读取超时（秒）

# 重试配置
HTTP_MAX_RETRIES = 3  # HTTP 最大重试次数
HTTP_RETRY_DELAY_SECONDS = 1  # HTTP 重试延迟（秒）

# ============================================================================
# 日志常量 (Logging Constants)
# ============================================================================

# 日志文件
LOG_MAX_BYTES = 10 * 1024 * 1024  # 日志文件最大大小（10MB）
LOG_BACKUP_COUNT = 5  # 日志备份文件数量
LOG_ROTATION_INTERVAL_DAYS = 7  # 日志轮转间隔（天）

# ============================================================================
# 版本常量 (Version Constants)
# ============================================================================

# 配置版本
CONFIG_VERSION = "2.0.0"  # 配置文件版本

# API 版本
API_VERSION = "1.0"  # API 版本
