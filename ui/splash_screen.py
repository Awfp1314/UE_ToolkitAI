# -*- coding: utf-8 -*-

"""
启动加载界面 - 显示程序启动进度

⚡ 优化方案：使用 QTimer 异步更新进度，避免事件循环冲突
✨ 支持深色/浅色主题切换
✨ 随机进度百分比，更真实的加载体验
✨ 优化的视觉效果（渐变背景、发光效果、动画）
"""

from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel, QProgressBar, QGraphicsDropShadowEffect
from PyQt6.QtCore import Qt, QTimer, QPropertyAnimation, QEasingCurve
from PyQt6.QtGui import QColor, QPixmap
from core.logger import get_logger
from queue import Queue
from pathlib import Path
import random
import logging

# 延迟初始化 logger，避免模块导入时的循环依赖
_logger = None

def _get_logger():
    """获取 logger 实例（延迟初始化）"""
    global _logger
    if _logger is None:
        _logger = get_logger(__name__)
    return _logger


class SplashLogHandler(logging.Handler):
    """自定义日志处理器 - 将关键日志同步到启动界面

    功能：
    1. 捕获关键的日志消息
    2. 自动映射到进度百分比
    3. 更新启动界面的进度条和消息
    """

    def __init__(self, splash_screen):
        """初始化日志处理器

        Args:
            splash_screen: SplashScreen实例
        """
        super().__init__()
        self.splash_screen = splash_screen
        self.current_progress = 0

        # 定义关键日志消息和对应的进度百分比
        self.log_progress_map = [
            # 应用程序初始化阶段 (0-30%)
            ("启动虚幻引擎工具箱", 5, "正在启动应用程序..."),
            ("已设置 Windows AppUserModelID", 8, "正在初始化系统..."),
            ("已设置应用图标", 10, "正在加载资源..."),
            ("正在应用QSS主题", 12, "正在加载主题..."),
            ("QSS主题应用成功", 15, "主题加载完成"),
            ("启动加载界面已显示", 18, "启动界面已显示"),
            ("开始设置应用程序", 20, "正在设置应用程序..."),
            ("初始化 PathUtils", 22, "正在初始化路径工具..."),
            ("初始化 Logger", 24, "正在初始化日志系统..."),
            ("初始化 ConfigManager", 26, "正在初始化配置管理器..."),
            ("初始化 ModuleManager", 28, "正在初始化模块管理器..."),
            ("初始化 ThreadManager", 30, "正在初始化线程管理器..."),
            ("应用程序设置成功", 32, "应用程序设置完成"),
            ("开始异步启动应用程序", 35, "正在准备启动..."),

            # 模块扫描和依赖解析阶段 (35-50%)
            ("开始加载模块（同步模式）", 38, "正在加载模块..."),
            ("开始扫描模块目录", 40, "正在扫描模块目录..."),
            ("发现模块: ModuleInfo(name='ai_assistant'", 42, "发现AI助手模块"),
            ("发现模块: ModuleInfo(name='asset_manager'", 43, "发现资产管理器模块"),
            ("发现模块: ModuleInfo(name='config_tool'", 44, "发现配置工具模块"),
            ("发现模块: ModuleInfo(name='site_recommendations'", 45, "发现站点推荐模块"),
            ("模块扫描完成", 48, "模块扫描完成"),
            ("开始解析模块依赖关系", 50, "正在解析模块依赖..."),
            ("依赖解析完成", 52, "依赖解析完成"),

            # 模块加载阶段 (52-70%)
            ("正在加载模块: ai_assistant", 54, "正在加载AI助手..."),
            ("尝试导入模块: modules.ai_assistant", 55, "正在导入AI助手..."),
            ("模块 ai_assistant 加载成功", 58, "AI助手加载完成"),
            ("正在加载模块: asset_manager", 60, "正在加载资产管理器..."),
            ("尝试导入模块: modules.asset_manager", 61, "正在导入资产管理器..."),
            ("模块 asset_manager 加载成功", 64, "资产管理器加载完成"),
            ("正在加载模块: config_tool", 66, "正在加载配置工具..."),
            ("尝试导入模块: modules.config_tool", 67, "正在导入配置工具..."),
            ("模块 config_tool 加载成功", 68, "配置工具加载完成"),
            ("正在加载模块: site_recommendations", 69, "正在加载站点推荐..."),
            ("模块 site_recommendations 加载成功", 70, "站点推荐加载完成"),
            ("所有模块加载完成", 72, "所有模块加载完成"),

            # 模块初始化阶段 (72-88%)
            ("开始初始化模块（同步模式）", 74, "正在初始化模块..."),
            ("正在初始化模块: ai_assistant", 76, "正在初始化AI助手..."),
            ("模块 ai_assistant 初始化成功", 78, "AI助手初始化完成"),
            ("正在初始化模块: asset_manager", 80, "正在初始化资产管理器..."),
            ("模块 asset_manager 初始化成功", 82, "资产管理器初始化完成"),
            ("正在初始化模块: config_tool", 84, "正在初始化配置工具..."),
            ("模块 config_tool 初始化成功", 85, "配置工具初始化完成"),
            ("正在初始化模块: site_recommendations", 86, "正在初始化站点推荐..."),
            ("模块 site_recommendations 初始化成功", 87, "站点推荐初始化完成"),
            ("所有模块初始化完成", 88, "所有模块初始化完成"),

            # 最终阶段 (88-100%)
            ("应用程序异步启动完成", 90, "应用启动完成"),
            ("开始建立模块间连接", 92, "正在建立模块连接..."),
            ("模块连接流程结束", 93, "模块连接完成"),
            ("创建主窗口", 94, "正在创建主窗口..."),
            ("开始预加载资产管理器内容", 96, "正在预加载资产..."),
            ("资产预加载完成", 98, "资产预加载完成"),
            ("应用程序完全启动完成", 100, "启动完成！"),
        ]

    def emit(self, record):
        """处理日志记录

        Args:
            record: 日志记录对象
        """
        try:
            msg = record.getMessage()

            # 检查是否匹配关键日志
            for log_pattern, progress, display_msg in self.log_progress_map:
                if log_pattern in msg:
                    # 只有进度增加时才更新（避免倒退）
                    if progress > self.current_progress:
                        self.current_progress = progress
                        # 直接放入队列，而不是调用 update_progress
                        if hasattr(self.splash_screen, '_progress_queue'):
                            self.splash_screen._progress_queue.put((progress, display_msg))
                    break
        except Exception:
            # 忽略日志处理器中的错误，避免影响主程序
            pass


class SplashScreen(QWidget):
    """启动加载界面

    ⚡ 优化：使用消息队列和定时器异步更新进度，避免事件循环冲突
    ✨ 支持深色/浅色主题切换
    """

    def __init__(self, parent=None, theme="dark"):
        """初始化启动界面

        Args:
            parent: 父窗口
            theme: 主题模式，"dark" 或 "light"
        """
        super().__init__(parent)
        self.theme = theme  # 保存主题设置

        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Tool  # 添加 Tool 标志，避免任务栏显示
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)  # 关闭时自动删除

        # 设置固定大小 - 使用黄金比例（1.618:1）
        # 宽度 600，高度 = 600 / 1.618 ≈ 371
        self.setFixedSize(600, 371)

        # ⚡ 优化：使用消息队列存储待更新的加载消息
        self._progress_queue = Queue()

        # ⚡ 优化：使用定时器定期检查队列并更新UI
        self._update_timer = QTimer(self)
        self._update_timer.timeout.connect(self._process_progress_queue)
        self._update_timer.start(30)  # 每30ms检查一次队列，提高更新频率使动画更平滑

        # 初始化UI
        self._init_ui()

        # 居中显示
        self._center_on_screen()

        # ✨ 添加淡入动画
        self._add_fade_in_animation()

        # 日志处理器将在外部注册（在创建SplashScreen之前）
        self._log_handler = None

        _get_logger().info(f"启动加载界面已创建 - {theme}主题")
    
    def _get_shadow_color(self):
        """获取发光效果颜色（根据主题）

        ⭐ 注意：QGraphicsDropShadowEffect 需要 QColor 对象，无法使用QSS
        """
        if self.theme == "light":
            return QColor(74, 158, 255, 80)  # 浅色主题：较淡的发光
        else:
            return QColor(74, 158, 255, 100)  # 深色主题：较亮的发光

    def _init_ui(self):
        """初始化UI"""
        # ⭐ 不再使用内联样式，改用QSS系统
        # 样式文件: resources/styles/widgets/splash_screen.qss

        # 主容器
        container = QWidget(self)
        container.setObjectName("SplashContainer")

        # ✨ 移除发光效果，避免圆角处出现直角阴影
        # 如果需要阴影效果，可以使用更小的模糊半径
        # shadow = QGraphicsDropShadowEffect()
        # shadow.setBlurRadius(15)  # 减小模糊半径
        # shadow.setColor(self._get_shadow_color())
        # shadow.setOffset(0, 0)
        # container.setGraphicsEffect(shadow)

        # 布局
        layout = QVBoxLayout(container)
        layout.setContentsMargins(40, 30, 40, 30)
        layout.setSpacing(10)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # 顶部留白，给图标更多空间
        layout.addSpacing(15)

        # 图标
        self.icon_label = QLabel()
        self.icon_label.setObjectName("SplashIcon")
        self.icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # 加载图标文件
        icon_path = Path(__file__).parent.parent / "resources" / "tubiao.ico"
        if icon_path.exists():
            pixmap = QPixmap(str(icon_path))
            # 缩放图标到合适大小（保持宽高比）
            scaled_pixmap = pixmap.scaled(100, 100, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            self.icon_label.setPixmap(scaled_pixmap)
            # 设置最小高度而不是固定大小，保持居中
            self.icon_label.setMinimumHeight(120)
        else:
            # 如果图标文件不存在，使用emoji作为后备
            self.icon_label.setText("⚡")
            # ✅ 字体大小已在QSS中定义（#SplashIcon）
            self.icon_label.setMinimumHeight(120)
            _get_logger().warning(f"图标文件不存在: {icon_path}")

        layout.addWidget(self.icon_label)
        layout.addSpacing(25)

        # 标题
        self.title_label = QLabel("虚幻引擎工具箱")
        self.title_label.setObjectName("SplashTitle")
        self.title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.title_label)

        layout.addSpacing(12)

        # 加载消息
        self.message_label = QLabel("正在初始化...")
        self.message_label.setObjectName("SplashMessage")
        self.message_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.message_label)

        layout.addSpacing(5)

        # 不确定进度条（循环动画）
        self.progress_bar = QProgressBar()
        self.progress_bar.setObjectName("SplashProgressBar")  # ⭐ 设置ObjectName关联QSS
        self.progress_bar.setRange(0, 0)  # 设置为不确定模式，显示循环动画
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setFixedHeight(5)  # 设置为细进度条（5像素）
        self.progress_bar.setFixedWidth(400)  # 设置进度条宽度为400像素
        # ⭐ 删除了内联样式，改用QSS系统

        layout.addWidget(self.progress_bar, 0, Qt.AlignmentFlag.AlignCenter)  # 居中显示

        layout.addSpacing(10)

        # ✨ 版本号
        self.version_label = QLabel("v1.0.0")
        self.version_label.setObjectName("SplashVersion")
        self.version_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.version_label)

        # 设置容器布局
        container_layout = QVBoxLayout(self)
        container_layout.setContentsMargins(0, 0, 0, 0)
        container_layout.addWidget(container)
    
    def _center_on_screen(self):
        """将窗口居中显示"""
        screen = self.screen()
        if screen:
            screen_geometry = screen.availableGeometry()
            x = (screen_geometry.width() - self.width()) // 2
            y = (screen_geometry.height() - self.height()) // 2
            self.move(x, y)

    def _add_fade_in_animation(self):
        """添加淡入动画"""
        self.setWindowOpacity(0)
        self.fade_animation = QPropertyAnimation(self, b"windowOpacity")
        self.fade_animation.setDuration(400)  # 400ms
        self.fade_animation.setStartValue(0)
        self.fade_animation.setEndValue(1)
        self.fade_animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        self.fade_animation.start()
    
    def _process_progress_queue(self):
        """处理进度队列（在定时器中调用）

        ⚡ 优化：只更新加载消息，进度条保持循环动画
        """
        try:
            # 从队列中获取最新的消息
            latest_message = None
            while not self._progress_queue.empty():
                try:
                    percent, message = self._progress_queue.get_nowait()
                    # 只保留最新的消息
                    latest_message = message
                except:
                    break

            # 如果有新消息，更新UI
            if latest_message is not None:
                self.message_label.setText(latest_message)
        except Exception as e:
            _get_logger().error(f"处理进度队列时出错: {e}")

    def update_progress(self, percent: int, message: str):
        """更新加载进度（线程安全）

        ⚡ 优化：将进度信息放入队列，由定时器异步更新UI

        Args:
            percent: 进度百分比 (0-100)
            message: 加载消息
        """
        try:
            # 将进度信息放入队列
            self._progress_queue.put((percent, message))
        except Exception as e:
            _get_logger().error(f"更新进度时出错: {e}")
    
    def register_log_handler(self):
        """注册日志处理器，自动同步日志到进度条

        注意：应该在创建SplashScreen之后立即调用此方法
        """
        try:
            # 获取根日志记录器（"ue_toolkit"）
            # 这样可以捕获所有子日志记录器的日志（如 ue_toolkit.main, ue_toolkit.app_manager 等）
            root_logger = logging.getLogger("ue_toolkit")

            # 创建并添加日志处理器
            self._log_handler = SplashLogHandler(self)
            self._log_handler.setLevel(logging.INFO)
            root_logger.addHandler(self._log_handler)

            _get_logger().info("日志处理器已注册到启动界面")
        except Exception as e:
            # 注册失败不影响程序运行
            _get_logger().warning(f"注册日志处理器失败: {e}")

    def unregister_log_handler(self):
        """注销日志处理器"""
        try:
            if self._log_handler:
                root_logger = logging.getLogger("ue_toolkit")
                root_logger.removeHandler(self._log_handler)
                self._log_handler = None
        except Exception:
            # 注销失败不影响程序运行
            pass

    def finish(self):
        """完成加载，关闭启动界面

        ⚡ 优化：停止定时器，清理资源
        ✨ 优化：更新消息后延迟关闭，保持进度条循环动画
        """
        try:
            _get_logger().info("启动加载完成，准备关闭启动界面")

            # 注销日志处理器
            self.unregister_log_handler()

            # 停止更新定时器
            if hasattr(self, '_update_timer') and self._update_timer.isActive():
                self._update_timer.stop()

            # ✨ 更新消息为"加载完成！"，但保持进度条循环动画
            self.message_label.setText("加载完成！")

            # ✨ 延迟200ms后关闭窗口，让用户看到"加载完成"的消息
            QTimer.singleShot(200, self._do_close)
        except RuntimeError:
            # 窗口已被删除，忽略错误
            pass

    def _do_close(self):
        """真正关闭窗口（在延迟后调用）"""
        try:
            _get_logger().info("启动加载界面关闭")
            self.close()
        except RuntimeError:
            # 窗口已被删除，忽略错误
            pass

