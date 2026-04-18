# -*- coding: utf-8 -*-

"""
聊天控制器 - 从 ChatWindow 提取的业务逻辑层

负责：
- API 客户端管理
- 消息处理逻辑（构建、发送、历史管理）
- 上下文管理（ContextManager 初始化与维护）
- 工具协调（ToolsRegistry、Function Calling）
- 身份/角色扮演系统提示词构建
"""

import threading
from typing import Optional, List, Dict, Any

from PyQt6.QtCore import QObject, pyqtSignal

from ..logic.api_client import APIClient
from ..logic.config import SYSTEM_PROMPT
from ..logic.context_manager import ContextManager
from ..logic.runtime_context import RuntimeContextManager
from ..logic.tools_registry import ToolsRegistry
from ..logic.memory_compressor import MemoryCompressor
from ..logic.message_manager import MessageManager


class ChatController(QObject):
    """聊天业务逻辑控制器

    将 ChatWindow 中的业务逻辑抽离，ChatWindow 仅保留 UI 代码。
    通过 Qt 信号与 ChatWindow 通信。
    """

    # ===== 信号定义 =====
    chunk_received = pyqtSignal(str)        # 接收到流式数据块
    request_finished = pyqtSignal(str)      # API 请求完成，参数为完整回复文本
    error_occurred = pyqtSignal(str)        # 发生错误
    tool_started = pyqtSignal(str)          # 工具开始执行
    tool_completed = pyqtSignal(str, dict)  # 工具执行完成
    session_title_updated = pyqtSignal(str, str)  # AI 生成标题后通知 UI (session_id, new_title)

    # 工具名称中文映射
    TOOL_NAME_MAP = {
        "search_assets": "搜索资产",
        "query_asset_detail": "查询资产详情",
        "search_configs": "搜索配置",
        "diff_config": "对比配置",
        "search_logs": "搜索日志",
        "search_docs": "搜索文档",
        "import_asset_to_ue": "导入资产到UE",
        "list_importable_assets": "列出可导入资产",
        "export_config_template": "导出配置",
        "batch_rename_preview": "批量重命名",
        "get_current_blueprint_summary": "分析蓝图",
        "read_blueprint_node": "读取蓝图节点",
        "search_blueprint_nodes": "搜索蓝图节点",
    }

    def __init__(self, parent=None):
        super().__init__(parent)

        # ===== 会话管理器 =====
        from ..logic.session_manager import SessionManager
        self.session_manager = SessionManager()

        # ===== 消息管理器（关联会话管理器）=====
        self.message_manager = MessageManager(session_manager=self.session_manager)

        # 向后兼容：conversation_history 属性委托给 message_manager
        # （外部代码可能直接访问 controller.conversation_history）

        # API 客户端
        self.current_api_client: Optional[APIClient] = None

        # Function Calling 协调器
        self.current_coordinator = None

        # ===== 核心逻辑组件 =====
        # 上下文管理器（包含记忆系统）
        self.context_manager: Optional[ContextManager] = None

        # 运行态上下文
        self.runtime_context = RuntimeContextManager()

        # 工具注册表
        self.tools_registry: Optional[ToolsRegistry] = None

        # 其他模块逻辑层引用
        self.asset_manager_logic = None
        self.config_tool_logic = None
        self.site_recommendations_logic = None

        # ===== 渐进式对话压缩器 =====
        self._memory_compressor: Optional[MemoryCompressor] = None

        # ===== 预初始化状态 =====
        self._pre_init_running = False
        self._pre_init_done = False
        self._init_lock = threading.Lock()

    # ------------------------------------------------------------------
    # 向后兼容属性
    # ------------------------------------------------------------------

    @property
    def conversation_history(self) -> List[Dict[str, str]]:
        """向后兼容：委托给 MessageManager"""
        return self.message_manager.conversation_history

    @property
    def _current_response_text(self) -> str:
        """向后兼容：委托给 MessageManager"""
        return self.message_manager.current_response_text

    # ------------------------------------------------------------------
    # 公共接口
    # ------------------------------------------------------------------

    def set_logic_references(
        self,
        asset_manager_logic=None,
        config_tool_logic=None,
        site_recommendations_logic=None,
    ):
        """设置其他模块的逻辑层引用（延迟初始化策略）"""
        # print(f"[DEBUG] ========== ChatController.set_logic_references 被调用 ==========")  # 打包时自动注释
        # print(f"[DEBUG] asset_manager_logic: {asset_manager_logic}")  # 打包时自动注释
        # print(f"[DEBUG] config_tool_logic: {config_tool_logic}")  # 打包时自动注释
        # print(f"[DEBUG] site_recommendations_logic: {site_recommendations_logic}")  # 打包时自动注释

        self.asset_manager_logic = asset_manager_logic
        self.config_tool_logic = config_tool_logic
        self.site_recommendations_logic = site_recommendations_logic

        # 如果已有 ContextManager，热更新引用
        if self.context_manager is not None:
            # print("[DEBUG] 热更新 ContextManager 内部引用...")  # 打包时自动注释
            if hasattr(self.context_manager, 'asset_reader'):
                self.context_manager.asset_reader.asset_manager_logic = asset_manager_logic
            if hasattr(self.context_manager, 'config_reader'):
                self.context_manager.config_reader.config_tool_logic = config_tool_logic
            if hasattr(self.context_manager, 'site_reader'):
                self.context_manager.site_reader.site_logic = site_recommendations_logic
        else:
            # print("[DEBUG] 逻辑层引用已保存，ContextManager 将在首次对话时初始化")  # 打包时自动注释
            pass  # 保持语法正确

        # 如果已有 ToolsRegistry，热更新 readers
        if self.tools_registry is not None:
            # print("[DEBUG] 热更新 ToolsRegistry 内部引用...")  # 打包时自动注释
            pass  # 保持语法正确
            try:
                from ..logic.asset_reader import AssetReader
                from ..logic.config_reader import ConfigReader

                if asset_manager_logic:
                    self.tools_registry.asset_reader = AssetReader(asset_manager_logic)
                    # print("[DEBUG] ToolsRegistry.asset_reader 已更新")  # 打包时自动注释
                if config_tool_logic:
                    self.tools_registry.config_reader = ConfigReader(config_tool_logic)
                    # print("[DEBUG] ToolsRegistry.config_reader 已更新")  # 打包时自动注释
            except Exception as e:
                print(f"[WARNING] 热更新 ToolsRegistry 失败: {e}")

    def pre_initialize_async(self):
        """后台预初始化 ContextManager 和 ToolsRegistry（不阻塞 UI）

        在 ChatWindow 创建时调用，让第一次发消息时不再卡顿。
        """
        if self._pre_init_done or self._pre_init_running:
            return

        self._pre_init_running = True

        def _do_init():
            try:
                # print("[DEBUG] 后台预初始化开始...")  # 打包时自动注释
                # 预检查 AI 模型可用性（涉及模块导入和文件检查）
                self._ensure_ai_model_available()
                # 预初始化 ContextManager + ToolsRegistry
                self._ensure_context_manager_initialized()
                self._pre_init_done = True
                # print("[DEBUG] 后台预初始化完成 ✓")  # 打包时自动注释
            except Exception as e:
                print(f"[WARNING] 后台预初始化失败: {e}")
            finally:
                self._pre_init_running = False

        thread = threading.Thread(target=_do_init, daemon=True)
        thread.start()

    def build_full_message(self, message: str, attachments: list = None) -> tuple:
        """构建完整消息内容（包含附件信息）

        Returns:
            (display_message, full_message) 元组
        """
        return self.message_manager.build_full_message(message, attachments)

    def send_message(self, full_message: str):
        """发送消息并触发 API 调用

        调用方（ChatWindow）应先调用 build_full_message 获取 display/full 消息，
        处理 UI（添加用户气泡、显示思考动画）后，再调用此方法。

        Args:
            full_message: 包含附件信息的完整消息
        """
        # 检查 AI 模型可用性（不阻塞）
        self._ensure_ai_model_available()

        # 延迟初始化 ContextManager（如果后台预初始化已完成，这里直接跳过）
        # 如果后台还在初始化，_init_lock 会短暂等待
        self._ensure_context_manager_initialized()

        # 添加到对话历史（委托给 MessageManager）
        self.message_manager.add_user_message(full_message)

        # 自动设置会话标题（第一条消息时）
        if self.session_manager and self.session_manager.current_session_id:
            self.session_manager.update_session_title_from_message(
                self.session_manager.current_session_id, full_message
            )

        # 重置当前回复文本
        self.message_manager.reset_current_response()

        # 调用 API
        self._call_api()

    def regenerate(self):
        """重新生成最后一条 AI 回复

        Returns:
            bool: 是否可以重新生成（对话历史是否足够）
        """
        if not self.message_manager.has_enough_history_for_regeneration():
            print("[ERROR] 对话历史不足，无法重新生成")
            return False

        # 移除最后一条 AI 回复
        self.message_manager.remove_last_assistant_message()

        # 重置当前回复文本
        self.message_manager.reset_current_response()

        # 重新调用 API
        self._call_api()
        return True

    def get_tool_chinese_name(self, tool_name: str) -> str:
        """获取工具的中文名称"""
        return self.TOOL_NAME_MAP.get(tool_name, tool_name)

    # ------------------------------------------------------------------
    # 内部：初始化
    # ------------------------------------------------------------------

    def _ensure_ai_model_available(self) -> bool:
        """检查 AI 模型是否可用（不阻塞，仅用于语义搜索）"""
        try:
            from modules.ai_assistant.logic.ai_model_manager import AIModelManager
            from core.logger import get_logger
            logger = get_logger(__name__)

            if AIModelManager.check_model_integrity():
                logger.info("AI模型可用")
                return True

            logger.info("AI模型不可用，跳过语义搜索功能")
            return False

        except Exception as e:
            from core.logger import get_logger
            logger = get_logger(__name__)
            logger.error(f"检查AI模型可用性失败: {e}", exc_info=True)
            return True

    def _ensure_context_manager_initialized(self):
        """确保 ContextManager 已初始化（延迟初始化策略，线程安全）"""
        from core.logger import get_logger
        logger = get_logger(__name__)

        with self._init_lock:
            try:
                if self.context_manager is not None:
                    return

                # print("[DEBUG] 开始延迟初始化 ContextManager...")  # 打包时自动注释

                def api_client_factory(messages, model="gemini-2.5-flash"):
                    return APIClient(messages, model=model)

                memory_compressor = MemoryCompressor(
                    api_client_factory=api_client_factory,
                    max_rounds=10,
                    keep_recent=5,
                    compression_model="gemini-2.5-flash",
                )

                self.context_manager = ContextManager(
                    asset_manager_logic=self.asset_manager_logic,
                    config_tool_logic=self.config_tool_logic,
                    site_recommendations_logic=self.site_recommendations_logic,
                    runtime_context=self.runtime_context,
                    max_context_tokens=6000,
                )

                if hasattr(self.context_manager, 'memory'):
                    self.context_manager.memory.memory_compressor = memory_compressor

                self._init_tools_registry()

                logger.info("ContextManager 初始化完成（延迟加载）")

            except Exception as e:
                print(f"[ERROR] 初始化 ContextManager 失败: {e}")
                logger.error(f"初始化 ContextManager 失败: {e}", exc_info=True)
                self.context_manager = None
                import traceback
                traceback.print_exc()

    def _init_tools_registry(self):
        """初始化工具注册表"""
        from core.logger import get_logger
        logger = get_logger(__name__)

        try:
            # print("[DEBUG] 开始初始化 ToolsRegistry...")  # 打包时自动注释

            from ..logic.asset_reader import AssetReader
            from ..logic.config_reader import ConfigReader
            from ..logic.log_analyzer import LogAnalyzer
            from ..logic.document_reader import DocumentReader

            asset_reader = AssetReader(self.asset_manager_logic) if self.asset_manager_logic else None
            config_reader = ConfigReader(self.config_tool_logic) if self.config_tool_logic else None
            log_analyzer = LogAnalyzer()
            document_reader = DocumentReader()

            self.tools_registry = ToolsRegistry(
                asset_reader=asset_reader,
                config_reader=config_reader,
                log_analyzer=log_analyzer,
                document_reader=document_reader,
            )

            tool_count = len(self.tools_registry.openai_tool_schemas()) if self.tools_registry else 0
            logger.info(f"ToolsRegistry 初始化完成，工具数: {tool_count}")

        except Exception as e:
            print(f"[ERROR] 初始化 ToolsRegistry 失败: {e}")
            logger.error(f"初始化 ToolsRegistry 失败: {e}", exc_info=True)
            self.tools_registry = None
            import traceback
            traceback.print_exc()

    # ------------------------------------------------------------------
    # 内部：API 调用
    # ------------------------------------------------------------------

    def _call_api(self):
        """构建请求消息并调用 API"""
        request_messages = []

        # 1. 构建系统提示词
        system_prompt = self._build_system_prompt_with_identity()
        # print(f"[DEBUG] 系统提示词长度: {len(system_prompt)} 字符")  # 打包时自动注释

        request_messages.append({"role": "system", "content": system_prompt})

        # 2. 添加对话历史（使用渐进式压缩：摘要 + 最近 N 轮）
        all_messages = self.message_manager.get_user_and_assistant_messages()
        compressor = self._get_compressor()

        if compressor and compressor.summary:
            # 有摘要：摘要 + 最近 N 轮
            context_msgs = compressor.build_context_messages(all_messages)
        else:
            # 无摘要：最近 10 轮兜底
            max_messages = 20
            context_msgs = all_messages[-max_messages:] if len(all_messages) > max_messages else all_messages

        for msg in context_msgs:
            request_messages.append(msg)

        # 更新历史中的系统提示词（委托给 MessageManager）
        self.message_manager.update_system_prompt(system_prompt)

        # 3. 获取工具定义
        tools = None
        # print(f"[DEBUG] ========== 准备获取工具定义 ==========")  # 打包时自动注释
        # print(f"[DEBUG] self.tools_registry: {self.tools_registry}")  # 打包时自动注释

        if self.tools_registry:
            try:
                tools = self.tools_registry.openai_tool_schemas()
                if tools:
                    for i, tool in enumerate(tools[:3]):
                        # print(f"[DEBUG]   工具{i+1}: {tool.get('function', {}).get('name')}")  # 打包时自动注释
                        pass  # 保持语法正确
            except Exception as e:
                print(f"[WARNING] 获取工具定义失败: {e}")
                import traceback
                traceback.print_exc()

        # print(f"[DEBUG] 发送消息数量: {len(request_messages)}, 工具数量: {len(tools) if tools else 0}")  # 打包时自动注释

        for i, msg in enumerate(request_messages):
            role = msg.get("role", "unknown")
            content = msg.get("content", "")
            preview = content[:100] if isinstance(content, str) else str(content)[:100]
            # print(f"[DEBUG] 消息[{i}] {role}: {preview}...")  # 打包时自动注释

        # 4. 发起请求
        if tools and self.tools_registry:
            # print(f"[DEBUG] 启用 Function Calling 协调器")  # 打包时自动注释
            self._start_with_coordinator(request_messages, tools)
        else:
            # print(f"[DEBUG] 启动普通 API 请求...")  # 打包时自动注释
            self.current_api_client = APIClient(request_messages, tools=None)

            self.current_api_client.chunk_received.connect(self._on_chunk_received)
            self.current_api_client.request_finished.connect(self._on_request_finished)
            self.current_api_client.error_occurred.connect(self._on_error_occurred)

            self.current_api_client.start()

    def _start_with_coordinator(self, messages, tools):
        """使用 Function Calling 协调器启动请求"""
        try:
            from ..logic.function_calling_coordinator import FunctionCallingCoordinator
            from ..clients import create_llm_client
            from core.config.config_manager import ConfigManager
            from pathlib import Path
            from ..config_schema import get_ai_assistant_schema

            template_path = Path(__file__).parent.parent / "config_template.json"
            config_manager = ConfigManager(
                "ai_assistant",
                template_path=template_path,
                config_schema=get_ai_assistant_schema(),
            )
            config = config_manager.get_module_config()

            provider = config.get("llm_provider", "unknown")
            # print(f"[DEBUG] 当前LLM供应商: {provider}")  # 打包时自动注释
            if provider == "api":
                api_config = config.get("api_settings", {})
                # print(f"[DEBUG] API URL: {api_config.get('api_url')}")  # 打包时自动注释
                # print(f"[DEBUG] API 模型: {api_config.get('default_model')}")  # 打包时自动注释
            elif provider == "ollama":
                ollama_config = config.get("ollama_settings", {})
                # print(f"[DEBUG] Ollama URL: {ollama_config.get('base_url')}")  # 打包时自动注释
                # print(f"[DEBUG] Ollama 模型: {ollama_config.get('default_model')}")  # 打包时自动注释

            # print(f"[DEBUG] 开始创建LLM客户端...")  # 打包时自动注释
            llm_client = create_llm_client(config)

            self.current_coordinator = FunctionCallingCoordinator(
                messages=messages,
                tools_registry=self.tools_registry,
                llm_client=llm_client,
                max_iterations=20,  # 支持复杂的多步骤蓝图分析
            )

            self.current_coordinator.tool_start.connect(self._on_tool_start)
            self.current_coordinator.tool_complete.connect(self._on_tool_complete)
            self.current_coordinator.chunk_received.connect(self._on_chunk_received)
            self.current_coordinator.request_finished.connect(self._on_request_finished)
            self.current_coordinator.error_occurred.connect(self._on_error_occurred)

            # print(f"[DEBUG] 启动 Function Calling 协调器...")  # 打包时自动注释
            self.current_coordinator.start()

        except Exception as e:
            print(f"[ERROR] 启动协调器失败: {e}")
            import traceback
            traceback.print_exc()
            self._on_error_occurred(f"启动协调器失败: {str(e)}")

    # ------------------------------------------------------------------
    # 内部：API 回调（转发为控制器信号）
    # ------------------------------------------------------------------

    def _on_chunk_received(self, chunk: str):
        """接收到数据块 → 累积文本并转发信号"""
        self.message_manager.append_to_current_response(chunk)
        self.chunk_received.emit(chunk)

    def _on_request_finished(self):
        """API 请求完成 → 保存到历史，转发信号"""
        # 完成当前回复：添加到历史并获取完整文本
        response_text = self.message_manager.finalize_current_response()

        if response_text:
            # 检测身份设定变更
            last_user_message = self.message_manager.get_last_user_message()
            if last_user_message:
                self._check_and_apply_identity_change(last_user_message)

        # 清理 API 客户端 / 协调器
        self.current_api_client = None
        self.current_coordinator = None

        # 异步触发渐进式压缩（不阻塞 UI）
        self._try_compress_async()

        # 通知 UI
        self.request_finished.emit(response_text)

    def _get_compressor(self) -> Optional[MemoryCompressor]:
        """获取或创建渐进式压缩器（延迟初始化）"""
        if self._memory_compressor is not None:
            return self._memory_compressor

        try:
            def api_client_factory(messages, model="gemini-2.5-flash"):
                return APIClient(messages, model=model)

            self._memory_compressor = MemoryCompressor(
                api_client_factory=api_client_factory,
            )

            # 从 MessageManager 恢复已有摘要
            mm = self.message_manager
            if mm._compressed_summary:
                self._memory_compressor.summary = mm._compressed_summary
                self._memory_compressor.compressed_count = mm._compressed_count
                print(f"[INFO] 已恢复压缩摘要到压缩器")

            return self._memory_compressor
        except Exception as e:
            print(f"[WARNING] 创建压缩器失败: {e}")
            return None

    def _try_compress_async(self):
        """在 AI 回复完成后，异步检查并执行渐进式压缩（后台线程）"""
        from core.services import thread_service

        def do_compress(cancel_token):
            try:
                compressor = self._get_compressor()
                if not compressor:
                    return

                all_messages = self.message_manager.get_user_and_assistant_messages()

                # --- AI 生成标题（压缩时顺便做，或消息够多时单独做）---
                self._try_generate_ai_title(compressor, all_messages)

                if not compressor.needs_compression(len(all_messages)):
                    return

                print(f"[INFO] 触发渐进式压缩（当前 {len(all_messages)} 条消息）...")
                success = compressor.compress_oldest(all_messages)
                if success:
                    # 同步摘要到 MessageManager 并持久化
                    self.message_manager._compressed_summary = compressor.summary
                    self.message_manager._compressed_count = compressor.compressed_count
                    self.message_manager._save_history()
                    print(f"[INFO] 压缩完成并已持久化")
            except Exception as e:
                print(f"[WARNING] 异步压缩失败: {e}")

        thread_service.run_async(
            do_compress,
            on_error=lambda err: print(f"[WARNING] 压缩线程出错: {err}")
        )

    def _try_generate_ai_title(self, compressor, all_messages):
        """尝试用 AI 生成会话标题（在后台线程中调用）

        触发条件：消息数 >= 4（至少2轮对话）且尚未被 AI 命名过
        """
        try:
            if not self.session_manager:
                # print(f"[DEBUG] AI 命名跳过: session_manager 不存在")  # 打包时自动注释
                return

            session_id = self.session_manager.current_session_id
            if not session_id:
                # print(f"[DEBUG] AI 命名跳过: 无当前会话")  # 打包时自动注释
                return

            current_session = self.session_manager.get_current_session()
            if not current_session:
                # print(f"[DEBUG] AI 命名跳过: 无法获取当前会话对象")  # 打包时自动注释
                return

            # 只在有足够对话内容时生成（至少2轮 = 4条消息）
            if len(all_messages) < 4:
                # print(f"[DEBUG] AI 命名跳过: 消息数不足 ({len(all_messages)} < 4)")  # 打包时自动注释
                return

            # 已被 AI 命名过或用户手动改过，跳过
            if current_session.ai_titled:
                # print(f"[DEBUG] AI 命名跳过: 已被 AI 命名过")  # 打包时自动注释
                return

            print(f"[INFO] 尝试用 AI 生成会话标题（消息数: {len(all_messages)}）...")
            new_title = compressor.generate_title(all_messages)
            
            if not new_title:
                print(f"[WARNING] AI 生成标题失败: 返回空标题")
                return
                
            if new_title == current_session.title:
                # print(f"[DEBUG] AI 生成标题与当前标题相同，跳过更新")  # 打包时自动注释
                return
            
            current_session.ai_titled = True
            self.session_manager.rename_session(session_id, new_title)
            # rename_session 会 save_index，但 ai_titled 已经设置了
            print(f"[INFO] ✅ AI 生成标题成功: {new_title}")
            # 通知 UI 刷新
            self.session_title_updated.emit(session_id, new_title)

        except Exception as e:
            import traceback
            print(f"[ERROR] AI 生成标题失败: {e}")
            print(f"[ERROR] 详细错误:\n{traceback.format_exc()}")

    def _on_error_occurred(self, error_message: str):
        """API 请求出错 → 转发信号"""
        self.current_api_client = None
        self.current_coordinator = None
        self.error_occurred.emit(error_message)

    def _on_tool_start(self, tool_name: str):
        """工具开始执行 → 转发信号"""
        self.tool_started.emit(tool_name)

    def _on_tool_complete(self, tool_name: str, result: dict):
        """工具执行完成 → 转发信号"""
        self.tool_completed.emit(tool_name, result)

    # ------------------------------------------------------------------
    # 内部：系统提示词 & 身份管理
    # ------------------------------------------------------------------

    def _build_system_prompt_with_identity(self) -> str:
        """构建包含身份设定的系统提示词（从记忆系统读取）"""
        system_prompt = SYSTEM_PROMPT

        if self.context_manager and hasattr(self.context_manager, 'memory'):
            try:
                user_identity = self.context_manager.memory.get_user_identity()

                if user_identity:
                    roleplay_keywords = ['你是', '扮演', '角色', '人设', '猫娘', '女仆', '助手身份']
                    behavior_request_keywords = ['去掉', '不要', '别', '称呼', '叫我', '喊我', '可以']

                    has_roleplay = any(kw in user_identity for kw in roleplay_keywords)
                    is_only_behavior_request = (
                        '从现在开始' in user_identity
                        and any(kw in user_identity for kw in behavior_request_keywords)
                        and not any(kw in user_identity for kw in ['你是', '扮演', '角色', '人设'])
                    )

                    is_roleplay = has_roleplay and not is_only_behavior_request

                    if is_roleplay:
                        system_prompt = self._build_roleplay_prompt(user_identity)
                    else:
                        system_prompt = f"""{SYSTEM_PROMPT}

## ⚠️ 用户偏好设定（必须严格遵守）
{user_identity}

请根据上述用户偏好调整你的回答方式。"""
            except Exception as e:
                print(f"[WARNING] 构建身份提示词失败: {e}")

        return system_prompt

    def _build_system_prompt_with_new_identity(self, identity_message: str) -> str:
        """构建包含新身份设定的系统提示词（不触发 FAISS）"""
        return self._build_roleplay_prompt(identity_message)

    @staticmethod
    def _build_roleplay_prompt(identity: str) -> str:
        """构建角色扮演专用提示词"""
        return f"""# 角色扮演模式

## 你的角色身份
{identity}

## 核心要求（必须严格遵守）
1. **你就是这个角色本人**，完全沉浸在角色中
2. **说话方式**：使用该角色特有的语气、口癖、用词习惯
3. **性格特点**：展现角色的性格特征（如果是动漫/游戏角色，请按照原作设定）
4. **称呼方式**：使用角色会使用的自称和对用户的称呼
5. **禁止事项**：
   - ❌ 绝对不要说"我是AI"、"作为AI助手"、"我是智能助手"
   - ❌ 不要用"您好，有什么可以帮助您的"这种客服式开场白
   - ❌ 不要在回答中提到"角色扮演"或"扮演"

## 角色知识
- 如果用户问的是你（角色）不了解的现代技术问题，可以用角色的方式表达困惑，但仍然尽力帮助
- 保持角色的世界观和认知范围

## 回答风格
- 完全按照角色的说话方式回答
- 可以使用角色特有的表情、语气词
- 回答要有角色的个性和情感"""

    def _check_and_apply_identity_change(self, user_message: str):
        """检测并立即应用身份设定变更"""
        identity_keywords = [
            '从现在开始', '你是', '你现在是', '你变成', '你扮演',
            '你的身份是', '你的角色是', '你就是', '你要扮演', '你要当',
            '你不是', '不要再', '别再',
        ]

        message_lower = user_message.lower()
        is_identity_change = any(kw in message_lower for kw in identity_keywords)

        if is_identity_change:
            # print(f"[DEBUG] 检测到身份设定变更，立即更新系统提示词")  # 打包时自动注释

            new_system_prompt = self._build_system_prompt_with_new_identity(user_message)

            # 委托给 MessageManager 更新系统提示词
            self.message_manager.update_system_prompt(new_system_prompt)
            # print(f"[DEBUG] 系统提示词已更新，新身份将在下次对话中生效")  # 打包时自动注释
