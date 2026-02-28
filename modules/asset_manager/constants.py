# -*- coding: utf-8 -*-

"""
资产管理器模块常量定义
集中管理资产管理器相关的常量
"""

# ============================================================================
# 缩略图常量 (Thumbnail Constants)
# ============================================================================

# 缩略图缓存
THUMBNAIL_CACHE_SIZE = 100  # LRU 缓存大小（项数）
THUMBNAIL_CACHE_MEMORY_MB = 30  # 缓存内存目标（MB）

# 缩略图尺寸
THUMBNAIL_SIZE_PX = 256  # 缩略图尺寸（像素）
THUMBNAIL_QUALITY = 85  # JPEG 质量（0-100）

# 缩略图加载
THUMBNAIL_LOAD_TIMEOUT_MS = 5000  # 缩略图加载超时（毫秒）
THUMBNAIL_BATCH_SIZE = 20  # 批量加载缩略图数量

# ============================================================================
# 资产扫描常量 (Asset Scanning Constants)
# ============================================================================

# 扫描配置
ASSET_SCAN_BATCH_SIZE = 100  # 扫描批次大小
ASSET_SCAN_TIMEOUT_MS = 30000  # 扫描超时时间（毫秒）
ASSET_SCAN_PARALLEL_WORKERS = 4  # 并行扫描工作线程数

# 扫描性能目标
ASSET_SCAN_TARGET_MS = 800  # 扫描时间目标（毫秒）

# ============================================================================
# 资产列表常量 (Asset List Constants)
# ============================================================================

# 列表显示
ASSET_LIST_ITEM_HEIGHT = 80  # 列表项高度
ASSET_LIST_ICON_SIZE = 64  # 列表图标大小
ASSET_LIST_PAGE_SIZE = 50  # 分页大小（虚拟滚动）

# 列表性能
ASSET_LIST_SCROLL_DEBOUNCE_MS = 100  # 滚动防抖延迟（毫秒）
ASSET_LIST_RENDER_BATCH_SIZE = 10  # 渲染批次大小

# ============================================================================
# 搜索常量 (Search Constants)
# ============================================================================

# 搜索配置
SEARCH_DEBOUNCE_DELAY_MS = 500  # 搜索防抖延迟（毫秒）
SEARCH_MIN_QUERY_LENGTH = 2  # 最小搜索查询长度
SEARCH_MAX_RESULTS = 1000  # 最大搜索结果数

# ============================================================================
# 文件类型常量 (File Type Constants)
# ============================================================================

# 支持的资产类型
SUPPORTED_MODEL_EXTENSIONS = ['.fbx', '.obj', '.blend', '.ma', '.mb']
SUPPORTED_TEXTURE_EXTENSIONS = ['.png', '.jpg', '.jpeg', '.tga', '.bmp', '.tif', '.tiff']
SUPPORTED_MATERIAL_EXTENSIONS = ['.mat', '.mtl']
SUPPORTED_AUDIO_EXTENSIONS = ['.wav', '.mp3', '.ogg', '.flac']
SUPPORTED_VIDEO_EXTENSIONS = ['.mp4', '.avi', '.mov', '.mkv']

# ============================================================================
# 资产库常量 (Asset Library Constants)
# ============================================================================

# 库配置
ASSET_LIBRARY_MAX_SIZE_GB = 100  # 资产库最大大小（GB）
ASSET_LIBRARY_SCAN_DEPTH = 10  # 最大扫描深度

# 分类
DEFAULT_CATEGORIES = [
    "Models",
    "Textures",
    "Materials",
    "Audio",
    "Video",
    "Blueprints",
    "Animations",
    "Particles",
    "Other"
]

# ============================================================================
# 导入导出常量 (Import/Export Constants)
# ============================================================================

# 导入配置
IMPORT_BATCH_SIZE = 50  # 批量导入大小
IMPORT_TIMEOUT_MS = 60000  # 导入超时时间（毫秒）

# 导出配置
EXPORT_BATCH_SIZE = 50  # 批量导出大小
EXPORT_TIMEOUT_MS = 60000  # 导出超时时间（毫秒）

# ============================================================================
# 预览常量 (Preview Constants)
# ============================================================================

# 预览窗口
PREVIEW_WINDOW_WIDTH = 800  # 预览窗口宽度
PREVIEW_WINDOW_HEIGHT = 600  # 预览窗口高度

# 预览加载
PREVIEW_LOAD_TIMEOUT_MS = 10000  # 预览加载超时（毫秒）
