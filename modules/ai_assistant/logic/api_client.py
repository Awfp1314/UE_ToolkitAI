"""
API 客户端模块
重构为使用策略模式，支持多种 LLM 供应商（API / Ollama）
"""

import json
import os
import time
import requests
from PyQt6.QtCore import QThread, pyqtSignal
from typing import Dict, Any, Optional
from pathlib import Path
from core.utils.thread_cleanup import ThreadCleanupMixin


class APIClient(QThread, ThreadCleanupMixin):
    """
    API 客户端线程（重构版）

    使用策略模式，通过工厂动态选择 LLM 供应商（API / Ollama）
    支持流式输出
    使用 ThreadCleanupMixin 确保线程资源正确释放（Requirement 4.1, 4.2, 4.3）
    """
    # 信号定义
    chunk_received = pyqtSignal(str)      # 接收到数据块
    request_finished = pyqtSignal()       # 请求完成
    token_usage = pyqtSignal(dict)        # Token使用量统计
    error_occurred = pyqtSignal(str)      # 发生错误
    
    def __init__(self, messages, model=None, temperature=None, tools=None, config=None):
        """
        初始化 API 客户端
        
        Args:
            messages: 消息历史列表
            model: 模型名称（可选，用于覆盖配置，向后兼容）
            temperature: 温度参数（可选，向后兼容）
            tools: Function Calling 工具列表（可选）
            config: LLM 配置字典（可选，如果不提供则从配置文件加载）
        """
        super().__init__()
        self.messages = messages
        self.model = model  # 保留以向后兼容
        self.temperature = temperature if temperature is not None else 0.8
        self.tools = tools
        self.is_running = True
        
        # 加载配置
        self.config = self._load_config() if config is None else config
        
        # 创建策略客户端（延迟到 run() 中，避免初始化阻塞）
        self.strategy_client = None

    def request_stop(self) -> None:
        """请求线程停止（实现 ThreadCleanupMixin 抽象方法）

        Requirement 4.1: 实现 request_stop() 方法
        """
        self.is_running = False

    def _load_config(self) -> Dict[str, Any]:
        """从配置文件加载 AI 助手配置"""
        try:
            from core.config.config_manager import ConfigManager
            
            # 获取模板文件路径
            template_path = Path(__file__).parent.parent / "config_template.json"
            
            # 导入配置模式
            from modules.ai_assistant.config_schema import get_ai_assistant_schema
            
            # 创建 ConfigManager 并传入模板路径和配置模式
            config_manager = ConfigManager(
                "ai_assistant", 
                template_path=template_path,
                config_schema=get_ai_assistant_schema()  # 🔧 修复：添加配置模式
            )
            config = config_manager.get_module_config()
            print(f"[CONFIG] AI 助手配置加载成功，供应商: {config.get('llm_provider', 'unknown')}")
            return config
        except Exception as e:
            print(f"[ERROR] 加载配置失败: {e}")
            import traceback
            traceback.print_exc()
            # 不提供 fallback，强制用户配置
            raise Exception(
                "AI 助手配置加载失败。\n\n"
                "请在设置中配置 API Key 或 Ollama 服务地址。\n\n"
                f"错误详情: {str(e)}"
            )
    
    def run(self):
        """执行 LLM 请求（使用策略模式）"""
        # 关键调试：追踪APIClient启动
        import traceback
        call_stack = ''.join(traceback.format_stack())
        print(f"\n{'='*80}")
        print(f"[API_CLIENT] !!! APIClient.run() 被调用！")
        print(f"[API_CLIENT] 消息数量: {len(self.messages)}")
        print(f"[API_CLIENT] 工具数量: {len(self.tools) if self.tools else 0}")
        print(f"[API_CLIENT] 调用堆栈:\n{call_stack}")
        print(f"{'='*80}\n")
        
        try:
            # 创建策略客户端
            from modules.ai_assistant.clients import create_llm_client
            
            self.strategy_client = create_llm_client(self.config)
            provider = self.config.get('llm_provider', 'api')
            
            print(f"[LLM] 使用供应商: {provider}, 模型: {self.strategy_client.get_model_name()}")
            
            # 调用策略生成响应
            response_generator = self.strategy_client.generate_response(
                context_messages=self.messages,
                stream=True,
                temperature=self.temperature,
                tools=self.tools
            )
            
            # 处理生成器输出，发送信号到 UI
            for chunk in response_generator:
                if not self.is_running:
                    break
                
                if chunk:
                    # 支持新格式（dict）和旧格式（str）
                    if isinstance(chunk, dict):
                        chunk_type = chunk.get('type')
                        
                        # 处理文本内容
                        if chunk_type == 'content':
                            text = chunk.get('text', '')
                            if text:
                                self.chunk_received.emit(text)
                        
                        # ⚡ 处理 token 使用量统计
                        elif chunk_type == 'token_usage':
                            usage = chunk.get('usage', {})
                            self.token_usage.emit(usage)
                        
                        # 忽略 tool_calls 类型（由协调器处理）
                    else:
                        # 旧格式：纯字符串
                        self.chunk_received.emit(chunk)
            
            # 请求完成
            if self.is_running:
                self.request_finished.emit()
        
        except Exception as e:
            error_msg = str(e)
            print(f"[ERROR] LLM 请求失败: {error_msg}")
            self.error_occurred.emit(error_msg)
    
    def stop(self):
        """停止请求"""
        self.is_running = False
        self.quit()
    
    @staticmethod
    def send(
        messages: list,
        model: str = "gemini-2.5-flash",
        temperature: float = 0.8,
        tools: list = None,
        stream: bool = True
    ):
        """
        v0.2 新增：发送请求的便捷工厂方法
        
        封装 OpenAI tools 参数格式，确保兼容性
        
        Args:
            messages: 对话历史
            model: 模型名称
            temperature: 温度参数
            tools: 工具列表（ChatGPT-style格式）
                  格式：[{type:'function', function:{name, description, parameters}}]
            stream: 是否启用流式输出
            
        Returns:
            APIClient: API 客户端实例
        """
        return APIClient(
            messages=messages,
            model=model,
            temperature=temperature,
            tools=tools
        )

