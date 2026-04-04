# -*- coding: utf-8 -*-

"""
AI 助手模块主类
"""

from PyQt6.QtWidgets import QWidget
from PyQt6.QtCore import QObject, pyqtSignal, QMetaObject, Qt
from typing import Optional
import threading
from contextlib import contextmanager

from core.logger import get_logger
from core.services import thread_service
from core.utils.cleanup_result import CleanupResult
# from modules.ai_assistant.ui.chat_window import ChatWindow  # TODO: 待实现新 UI

logger = get_logger(__name__)


class ModelLoadSignals(QObject):
    """模型加载信号（用于线程间通信）"""
    show_warning = pyqtSignal(str, str)  # title, message


# v0.1/v0.2 新增：延迟导入，避免启动时加载重量级库
try:
    from modules.ai_assistant.logic.runtime_context import RuntimeContextManager
    from modules.ai_assistant.logic.tools_registry import ToolsRegistry
    V01_V02_AVAILABLE = True
except ImportError as e:
    logger.warning(f"v0.1/v0.2 功能不可用（缺少依赖）：{e}")
    RuntimeContextManager = None
    ToolsRegistry = None
    V01_V02_AVAILABLE = False


class AIAssistantModule:
    """AI 助手模块主类"""
    
    def __init__(self, parent=None):
        """初始化模块
        
        Args:
            parent: 父组件（可选）
        """
        self.parent = parent
        self.chat_window: Optional[QWidget] = None  # TODO: 改为具体的 ChatWindow 类型
        self.asset_manager_logic = None  # 存储asset_manager逻辑层引用
        self.config_tool_logic = None  # 存储config_tool逻辑层引用
        self.site_recommendations_logic = None  # 存储site_recommendations逻辑层引用
        
        # v0.1 新增：运行态上下文管理器（全局单例）
        self.runtime_context = RuntimeContextManager() if V01_V02_AVAILABLE and RuntimeContextManager else None
        
        # v0.2 新增：工具注册表（延迟初始化）
        self.tools_registry: Optional[ToolsRegistry] = None
        
        # 模型加载状态标志（供UI查询）
        self._model_loading = False
        self._model_loaded = False
        self._model_load_progress = ""  # 加载进度描述

        # 信号对象（用于线程间通信）
        self._signals = ModelLoadSignals()
        self._signals.show_warning.connect(self._show_warning_dialog)

        status = "（包含运行态上下文 + 工具系统）" if V01_V02_AVAILABLE else "（v0.1/v0.2 功能不可用）"
        logger.info(f"AIAssistantModule 初始化{status}")
    
    def initialize(self, config_dir: str):
        """初始化模块

        Args:
            config_dir: 配置文件目录路径
        """
        logger.info(f"初始化 AI 助手模块，配置目录: {config_dir}")
        try:
            # AI 助手不需要持久化配置，可以跳过

            # v0.1 新增：异步预加载 embedding 模型（避免首次调用卡顿）
            # 注意：预加载会导致退出时卡顿（模型加载是阻塞操作，无法中断）
            # 改为完全延迟加载：模型会在首次真正使用时自动加载
            # self._preload_embedding_model_async()
            logger.info("AI 模型采用延迟加载策略（首次使用时自动加载）")

            # 异步预创建 ChatWindow 并加载历史消息（避免首次点击卡顿）
            self._preload_chat_window_async()

            logger.info("AI 助手模块初始化完成")
        except Exception as e:
            logger.error(f"AI 助手模块初始化失败: {e}", exc_info=True)
            raise
    
    @contextmanager
    def _env_context(self, **env_vars):
        """环境变量上下文管理器（自动恢复）

        Args:
            **env_vars: 要临时设置的环境变量

        Yields:
            None
        """
        import os
        backup = {}

        # 备份并设置新值
        for key, value in env_vars.items():
            if key in os.environ:
                backup[key] = os.environ[key]
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value

        try:
            yield
        finally:
            # 恢复原值
            for key in env_vars.keys():
                if key in backup:
                    os.environ[key] = backup[key]
                else:
                    os.environ.pop(key, None)

    def _show_warning_dialog(self, title: str, message: str):
        """在主线程显示警告对话框

        Args:
            title: 对话框标题
            message: 对话框消息
        """
        try:
            from modules.asset_manager.ui.message_dialog import MessageDialog
            MessageDialog(title, f"语义模型下载失败\n\n{message}", "warning", parent=self.parent).exec()
        except Exception as e:
            logger.warning(f"显示警告对话框失败: {e}")

    def _preload_chat_window_async(self):
        """异步预创建 ChatWindow 并加载历史消息（避免首次点击卡顿）"""
        from PyQt6.QtCore import QTimer
        
        def preload_task():
            """预加载任务"""
            try:
                logger.info("开始异步预创建 ChatWindow...")
                # 调用 get_widget() 会创建 ChatWindow 并触发历史消息加载
                # 由于 ChatWindow.__init__() 中已经将 _restore_chat_history() 改为异步，
                # 所以这里不会阻塞主线程
                widget = self.get_widget()
                logger.info("ChatWindow 预创建完成，历史消息正在后台加载")
            except Exception as e:
                logger.warning(f"ChatWindow 预加载失败（首次点击时会正常创建）: {e}")
        
        # 延迟 500ms 后执行，让主窗口先完成初始化
        QTimer.singleShot(500, preload_task)

    def _preload_embedding_model_async(self):
        """异步预加载 embedding 模型（后台线程）

        优化策略：
        1. 使用 ThreadService 管理线程生命周期
        2. 使用上下文管理器自动恢复环境变量
        3. 通过信号在主线程显示UI提示
        4. 失败时优雅降级
        """
        if not V01_V02_AVAILABLE:
            logger.info("v0.1/v0.2 功能不可用，跳过模型预加载")
            self._model_loaded = True  # 标记为已完成（降级模式）
            return

        self._model_loading = True
        self._model_load_progress = "准备加载模型..."

        def preload_task(cancel_token):
            """预加载任务（支持协作式取消）

            Args:
                cancel_token: 取消令牌，用于检查是否需要取消任务
            """
            try:
                import os
                import time
                start_time = time.time()

                # 检查是否已取消
                if cancel_token.is_cancelled():
                    logger.info("模型预加载任务在启动前被取消")
                    return

                # 使用上下文管理器临时修改环境变量
                proxy_keys = ['HTTP_PROXY', 'HTTPS_PROXY', 'http_proxy', 'https_proxy', 'ALL_PROXY', 'all_proxy']
                proxy_backup = {k: os.environ.get(k) for k in proxy_keys if k in os.environ}

                # 清除代理并设置离线模式
                env_overrides = {k: None for k in proxy_backup.keys()}
                env_overrides.update({
                    "HF_HUB_OFFLINE": "1",
                    "TRANSFORMERS_OFFLINE": "1",
                    "HF_ENDPOINT": os.environ.get("HF_ENDPOINT", "https://hf-mirror.com")
                })

                with self._env_context(**env_overrides):
                    logger.info("开始后台预加载 AI 模型（已启用离线模式）...")
                    self._model_load_progress = "正在加载语义模型..."

                    # 检查是否已取消
                    if cancel_token.is_cancelled():
                        logger.info("模型预加载任务在语义模型加载前被取消")
                        return

                    # 1. 预加载语义模型（仅初始化，不触发模型加载）
                    model_start = time.time()
                    from modules.ai_assistant.logic.intent_parser import IntentEngine

                    # 只创建实例，不调用 parse()，避免阻塞式模型加载
                    # 模型会在首次真正使用时自动加载（延迟加载）
                    temp_engine = IntentEngine(model_type="bge-small")

                    # 检查是否已取消
                    if cancel_token.is_cancelled():
                        logger.info("模型预加载任务在语义模型初始化后被取消")
                        return

                    model_elapsed = time.time() - model_start
                    logger.info(f"语义模型引擎初始化完成（耗时 {model_elapsed:.2f} 秒，模型将在首次使用时加载）")
                    self._model_load_progress = "语义模型引擎初始化完成，正在预热向量数据库..."

                    # 检查是否已取消
                    if cancel_token.is_cancelled():
                        logger.info("模型预加载任务在FAISS初始化前被取消")
                        return

                    # 2. 预热 FAISS 记忆系统
                    try:
                        memory_start = time.time()
                        from core.ai_services import EmbeddingService
                        from modules.ai_assistant.logic.enhanced_memory_manager import EnhancedMemoryManager

                        self._model_load_progress = "正在初始化 FAISS 记忆系统..."
                        embedding_service = EmbeddingService()

                        # 检查是否已取消
                        if cancel_token.is_cancelled():
                            logger.info("模型预加载任务在FAISS初始化中被取消")
                            return

                        temp_memory = EnhancedMemoryManager(
                            user_id="default",
                            embedding_service=embedding_service
                        )
                        memory_elapsed = time.time() - memory_start

                        if temp_memory.faiss_store:
                            logger.info(f"FAISS 记忆系统初始化完成（耗时 {memory_elapsed:.1f} 秒，记忆数: {temp_memory.faiss_store.count()}）")
                        else:
                            logger.warning("FAISS 记忆系统初始化失败（将在运行时重试）")
                    except Exception as e:
                        logger.warning(f"FAISS 记忆系统预热失败（首次对话时会自动初始化）: {e}")

                # 检查是否已取消
                if cancel_token.is_cancelled():
                    logger.info("模型预加载任务在完成前被取消")
                    return

                # 环境变量已自动恢复
                total_elapsed = time.time() - start_time
                logger.info(f"所有 AI 模型预加载完成！总耗时: {total_elapsed:.1f} 秒")

                # 标记加载完成
                self._model_loading = False
                self._model_loaded = True
                self._model_load_progress = f"模型加载完成（耗时 {total_elapsed:.1f} 秒，已启用 FAISS 记忆系统）"

            except Exception as e:
                logger.warning(f"预加载模型失败: {e}", exc_info=True)
                self._model_loading = False
                self._model_loaded = False

                # 检查是否为网络/代理问题
                error_str = str(e)
                if "proxy" in error_str.lower() or "connection" in error_str.lower() or "timeout" in error_str.lower():
                    self._model_load_progress = "模型下载失败（网络问题），已跳过语义分析功能"
                    # 通过信号在主线程显示提示
                    self._signals.show_warning.emit(
                        "模型加载提示",
                        "由于网络问题，AI语义分析模型无法下载。\n\n"
                        "程序将使用基础规则匹配模式运行，功能不受影响。\n\n"
                        "如需完整功能，请检查网络连接后重启程序。"
                    )
                else:
                    self._model_load_progress = "模型预加载失败，首次提问时会自动加载"

        # 使用 ThreadService 管理线程
        thread_service.run_async(
            preload_task,
            on_result=lambda: logger.debug("模型预加载任务完成"),
            on_error=lambda err: logger.error(f"模型预加载任务出错: {err}")
        )
    
    def _init_tools_system(self):
        """
        v0.2 新增：初始化工具系统
        
        在创建 ChatWindow 时调用，确保有完整的数据读取器可用
        """
        try:
            # 只在有数据读取器时才初始化工具系统
            if not self.asset_manager_logic and not self.config_tool_logic:
                logger.warning("数据读取器未初始化，工具系统延迟创建")
                return
            
            # 需要从 ChatWindow 的 context_manager 获取 readers
            # 或者直接在这里创建（更简单）
            from modules.ai_assistant.logic.asset_reader import AssetReader
            from modules.ai_assistant.logic.config_reader import ConfigReader
            from modules.ai_assistant.logic.log_analyzer import LogAnalyzer
            from modules.ai_assistant.logic.document_reader import DocumentReader
            from modules.ai_assistant.logic.asset_importer import AssetImporter
            
            asset_reader = AssetReader(self.asset_manager_logic)
            config_reader = ConfigReader(self.config_tool_logic)
            log_analyzer = LogAnalyzer()
            document_reader = DocumentReader()
            asset_importer = AssetImporter(self.asset_manager_logic)  # 测试功能
            
            # 创建工具注册表
            self.tools_registry = ToolsRegistry(
                asset_reader=asset_reader,
                config_reader=config_reader,
                log_analyzer=log_analyzer,
                document_reader=document_reader,
                asset_importer=asset_importer
            )
            
            logger.info("工具系统初始化完成")
            
        except Exception as e:
            logger.error(f"初始化工具系统失败: {e}", exc_info=True)
            self.tools_registry = None
    
    def get_runtime_context(self) -> RuntimeContextManager:
        """获取运行态上下文管理器（供外部访问）
        
        Returns:
            RuntimeContextManager: 运行态上下文管理器实例
        """
        return self.runtime_context
    
    def is_model_loading(self) -> bool:
        """检查模型是否正在加载
        
        Returns:
            bool: True表示正在加载中
        """
        return self._model_loading
    
    def is_model_loaded(self) -> bool:
        """检查模型是否已加载完成
        
        Returns:
            bool: True表示已加载完成
        """
        return self._model_loaded
    
    def get_model_load_progress(self) -> str:
        """获取模型加载进度描述
        
        Returns:
            str: 进度描述文本
        """
        return self._model_load_progress
    
    def get_widget(self) -> QWidget:
        """获取模块的UI组件

        Returns:
            QWidget: 模块的主UI组件
        """
        logger.info("获取 AI 助手 UI 组件")

        if self.chat_window is None:
            logger.info("创建 AI 助手聊天窗口")
            from modules.ai_assistant.ui import ChatWindow
            from modules.ai_assistant.ui.session_list_widget import SessionListWidget
            from PyQt6.QtWidgets import QWidget, QHBoxLayout
            
            # 创建包装容器
            # 结构: VBox[ HBox[ sidebar | left_spacer | ChatWindow | stretch ] ]
            wrapper = QWidget()
            from PyQt6.QtWidgets import QVBoxLayout, QPushButton, QLabel
            from PyQt6.QtCore import Qt
            outer_layout = QVBoxLayout(wrapper)
            outer_layout.setContentsMargins(0, 0, 0, 0)
            outer_layout.setSpacing(0)
            
            self.chat_window = ChatWindow()
            
            # ===== 聊天区居中 =====
            h_container = QWidget()
            h_layout = QHBoxLayout(h_container)
            h_layout.setContentsMargins(0, 0, 0, 0)
            h_layout.setSpacing(0)
            
            h_layout.addStretch(1)
            h_layout.addWidget(self.chat_window, 10)
            h_layout.addStretch(1)
            
            outer_layout.addWidget(h_container, 1)
            
            # ===== 侧边栏作为浮动层（不参与布局，覆盖在聊天区上方）=====
            sidebar = self.chat_window.session_sidebar
            sidebar.setParent(wrapper)
            sidebar.setVisible(False)
            sidebar.raise_()
            
            # ===== ☰ 按钮作为浮动控件 =====
            sidebar_toggle_btn = QPushButton("☰", wrapper)
            sidebar_toggle_btn.setFixedSize(32, 32)
            sidebar_toggle_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            sidebar_toggle_btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            sidebar_toggle_btn.setToolTip("会话列表")
            sidebar_toggle_btn.clicked.connect(self.chat_window._toggle_sidebar)
            sidebar_toggle_btn.move(4, 4)
            sidebar_toggle_btn.setVisible(True)  # 显式设置可见
            sidebar_toggle_btn.raise_()
            self.chat_window.sidebar_toggle_btn = sidebar_toggle_btn
            
            # 应用浮动按钮样式
            self.chat_window._apply_toolbar_style()
            
            # 保存引用给 ChatWindow
            self.chat_window._wrapper = wrapper
            self.chat_window._h_container = h_container
            
            # wrapper resize 时重新定位浮动元素
            original_resize = wrapper.resizeEvent
            def _wrapper_resize(event):
                original_resize(event)
                if self.chat_window._sidebar_visible:
                    self.chat_window._position_sidebar()
            wrapper.resizeEvent = _wrapper_resize
            
            # wrapper showEvent 时确保按钮可见
            original_show = wrapper.showEvent
            def _wrapper_show(event):
                original_show(event)
                # 确保按钮在最上层且可见
                if hasattr(self.chat_window, 'sidebar_toggle_btn'):
                    self.chat_window.sidebar_toggle_btn.raise_()
                    self.chat_window.sidebar_toggle_btn.setVisible(True)
            wrapper.showEvent = _wrapper_show
            
            # 添加一个方法供外部调用，用于在样式刷新后重新显示按钮
            def _refresh_floating_button():
                if hasattr(self.chat_window, 'sidebar_toggle_btn'):
                    self.chat_window.sidebar_toggle_btn.raise_()
                    self.chat_window.sidebar_toggle_btn.setVisible(True)
                    self.chat_window._apply_toolbar_style()
                    logger.debug("重新显示侧边栏按钮")
            wrapper.refresh_floating_button = _refresh_floating_button
            
            # 设置逻辑层引用（传递给ChatWindow以初始化核心组件）
            if hasattr(self.chat_window, 'set_logic_references'):
                self.chat_window.set_logic_references(
                    asset_manager_logic=self.asset_manager_logic,
                    config_tool_logic=self.config_tool_logic,
                    site_recommendations_logic=self.site_recommendations_logic
                )
                logger.info("已设置 ChatWindow 逻辑层引用")
            
            # 给wrapper添加on_theme_changed和update_theme方法，转发给ChatWindow
            def wrapper_on_theme_changed(theme_name):
                if self.chat_window and hasattr(self.chat_window, 'on_theme_changed'):
                    self.chat_window.on_theme_changed(theme_name)
            wrapper.on_theme_changed = wrapper_on_theme_changed
            
            def wrapper_update_theme(theme_name):
                if self.chat_window and hasattr(self.chat_window, 'update_theme'):
                    self.chat_window.update_theme(theme_name)
            wrapper.update_theme = wrapper_update_theme
            
            logger.info("AI 助手聊天窗口创建完成")
            return wrapper
        else:
            logger.info("返回已存在的 AI 助手窗口实例")
            # 返回wrapper的父widget
            return self.chat_window.parent()
        
        return self.chat_window.parent()
    
    def set_asset_manager_logic(self, asset_manager_logic):
        """设置asset_manager逻辑层引用
        
        Args:
            asset_manager_logic: asset_manager模块的逻辑层实例
        """
        self.asset_manager_logic = asset_manager_logic
        logger.info("AI助手模块已接收asset_manager逻辑层引用")
        
        # 如果chat_window已经创建，更新它的上下文管理器
        if self.chat_window and hasattr(self.chat_window, 'set_asset_manager_logic'):
            self.chat_window.set_asset_manager_logic(asset_manager_logic)
    
    def set_config_tool_logic(self, config_tool_logic):
        """设置config_tool逻辑层引用
        
        Args:
            config_tool_logic: config_tool模块的逻辑层实例
        """
        self.config_tool_logic = config_tool_logic
        logger.info("AI助手模块已接收config_tool逻辑层引用")
        
        # 如果chat_window已经创建，更新它的上下文管理器
        if self.chat_window and hasattr(self.chat_window, 'set_config_tool_logic'):
            self.chat_window.set_config_tool_logic(config_tool_logic)
    
    def request_stop(self) -> None:
        """请求模块停止操作（在 cleanup 之前调用）"""
        logger.info("请求 AI 助手模块停止")
        try:
            if self.chat_window:
                # 停止当前的 API 请求
                if hasattr(self.chat_window, 'current_api_client') and self.chat_window.current_api_client:
                    self.chat_window.current_api_client.stop()
        except Exception as e:
            logger.error(f"请求停止时发生错误: {e}", exc_info=True)

    def cleanup(self) -> CleanupResult:
        """清理资源

        Returns:
            CleanupResult: 清理结果
        """
        logger.info("清理 AI 助手模块资源")
        try:
            if self.chat_window:
                self.chat_window = None

            logger.info("AI 助手模块资源清理完成")
            return CleanupResult.success_result()
        except Exception as e:
            logger.error(f"清理模块资源时发生错误: {e}", exc_info=True)
            return CleanupResult.failure_result(str(e))

