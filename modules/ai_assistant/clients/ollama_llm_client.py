# -*- coding: utf-8 -*-

"""
Ollama LLM 客户端（策略实现）
支持本地 Ollama 模型服务
"""

import json
import os
import time
from typing import Dict, Any, Generator, List
from .base_llm_client import BaseLLMClient

# 代理环境变量名列表
_PROXY_ENV_VARS = [
    'HTTP_PROXY', 'http_proxy',
    'HTTPS_PROXY', 'https_proxy',
    'ALL_PROXY', 'all_proxy',
    'NO_PROXY', 'no_proxy',
]


def _make_no_proxy_client(**kwargs):
    """创建一个完全不走代理的 httpx.Client
    
    临时清除所有代理环境变量，创建完毕后恢复。
    这是最彻底的方式，兼容所有 httpx 版本。
    """
    import httpx
    saved = {}
    for var in _PROXY_ENV_VARS:
        if var in os.environ:
            saved[var] = os.environ.pop(var)
    try:
        return httpx.Client(**kwargs)
    finally:
        os.environ.update(saved)


class OllamaLLMClient(BaseLLMClient):
    """
    Ollama LLM 客户端策略
    
    通过 Ollama 的 HTTP API 调用本地运行的大语言模型
    文档：https://github.com/ollama/ollama/blob/main/docs/api.md
    """
    
    def __init__(self, config: Dict[str, Any]):
        """
        初始化 Ollama 客户端
        
        Args:
            config: Ollama 配置字典，应包含：
                - base_url: Ollama 服务地址（默认 http://localhost:11434）
                - model_name: 模型名称（如 llama3、mistral 等）
                - stream: 是否流式传输（默认 True）
                - timeout: 超时时间（默认 60）
        """
        super().__init__(config)
        
        # 从配置读取，空字符串回退到默认值
        self.base_url = config.get('base_url') or 'http://localhost:11434'
        # 优先使用 default_model（设置界面保存的），回退到 model_name（兼容旧代码）
        self.model_name = config.get('default_model') or config.get('model_name') or 'llama3'
        self.default_temperature = config.get('temperature', 0.9)  # 默认 0.9，提高流畅度
        self.stream = config.get('stream', True)
        # 增加超时时间，支持大模型首次加载（首次加载模型到内存可能需要几分钟）
        self.timeout = max(config.get('timeout', 300), 120)
        
        # 调试日志：显示配置
        print(f"[DEBUG] OllamaLLMClient 初始化:")
        print(f"  - 模型: {self.model_name}")
        print(f"  - 超时: {self.timeout}秒")
        print(f"  - 基础URL: {self.base_url}")
        
        # 构建 API 端点
        self.chat_endpoint = f"{self.base_url}/api/chat"
        
        # Tool calls 累积缓冲区
        self._tool_calls_buffer = []
    
    def generate_response(
        self,
        context_messages: List[Dict[str, str]],
        stream: bool = True,
        temperature: float = None,
        tools: List[Dict] = None
    ) -> Generator[str, None, None]:
        """
        生成响应（流式）
        
        Args:
            context_messages: 消息历史
            stream: 是否流式传输
            temperature: 温度参数（Ollama 支持，可选）
            tools: Function Calling（Ollama 部分模型支持，可选）
            
        Yields:
            str: 响应的 token 块
        """
        try:
            import httpx
        except ImportError:
            raise Exception("httpx 库未安装，请运行: pip install httpx")
        
        try:
            # 构建请求体
            # 预处理消息：将 OpenAI 格式转换为 Ollama 兼容格式
            ollama_messages = self._convert_messages_for_ollama(context_messages)
            payload = {
                "model": self.model_name,
                "messages": ollama_messages,
                "stream": stream,
                "temperature": temperature if temperature is not None else self.default_temperature
            }
            
            # Ollama 的 tools 格式（如果支持）
            if tools:
                payload["tools"] = tools
            
            # 发送请求（使用流式客户端以正确处理超时）
            # httpx.Timeout 需要明确指定 connect/read/write/pool 超时
            timeout = httpx.Timeout(
                connect=10.0,  # 连接超时10秒
                read=self.timeout,  # 读取超时使用配置值
                write=10.0,  # 写入超时10秒
                pool=10.0  # 连接池超时10秒
            )
            # 禁用代理，避免 localhost 请求被系统代理拦截导致超时
            with _make_no_proxy_client(timeout=timeout) as client:
                # 对于流式请求，使用stream方法
                if stream:
                    with client.stream("POST", self.chat_endpoint, json=payload) as response:
                        # 检查响应状态
                        if response.status_code != 200:
                            error_text = response.text
                            try:
                                error_data = json.loads(error_text)
                                error_msg = error_data.get('error', error_text)
                            except:
                                error_msg = error_text
                            raise Exception(f"Ollama API 错误 ({response.status_code}): {error_msg}")
                        
                        # 处理流式响应
                        for line in response.iter_lines():
                            if not line.strip():
                                continue
                            
                            try:
                                # Ollama 返回的每一行都是一个 JSON 对象
                                data = json.loads(line)
                                
                                # 检测 tool_calls（Ollama 格式）
                                if 'message' in data:
                                    message = data['message']
                                    
                                    # 检查是否有 tool_calls
                                    tool_calls = message.get('tool_calls')
                                    if tool_calls:
                                        self._accumulate_tool_calls(tool_calls)
                                        continue
                                    
                                    # 提取普通内容
                                    content = message.get('content', '')
                                    if content:
                                        yield {'type': 'content', 'text': content}
                                
                                # 检查是否完成
                                if data.get('done', False):
                                    # 如果累积了 tool_calls，返回
                                    if self._tool_calls_buffer:
                                        yield {
                                            'type': 'tool_calls',
                                            'tool_calls': self._get_accumulated_tool_calls()
                                        }
                                    return
                            
                            except json.JSONDecodeError:
                                continue
                else:
                    # 非流式响应
                    response = client.post(
                        self.chat_endpoint,
                        json=payload,
                        timeout=self.timeout
                    )
                    
                    # 检查响应状态
                    if response.status_code != 200:
                        error_text = response.text
                        try:
                            error_data = json.loads(error_text)
                            error_msg = error_data.get('error', error_text)
                        except:
                            error_msg = error_text
                        raise Exception(f"Ollama API 错误 ({response.status_code}): {error_msg}")
                    
                    response_text = response.text
                    data = json.loads(response_text)
                    
                    if 'message' in data:
                        message = data['message']
                        
                        # 检查 tool_calls
                        if 'tool_calls' in message:
                            yield {
                                'type': 'tool_calls',
                                'tool_calls': message['tool_calls']
                            }
                        else:
                            content = message.get('content', '')
                            yield {'type': 'content', 'text': content}
        
        except httpx.ConnectError:
            raise Exception(f"无法连接到 Ollama 服务 ({self.base_url})，请确保 Ollama 已启动")
        except httpx.TimeoutException:
            raise Exception(f"Ollama 请求超时（{self.timeout}秒），模型可能在加载中")
        except Exception as e:
            raise Exception(f"Ollama 请求失败: {str(e)}")
    
    def get_model_name(self) -> str:
        """获取模型名称"""
        return self.model_name
    
    def list_available_models(self) -> List[str]:
        """
        列出 Ollama 中可用的模型
        
        Returns:
            List[str]: 模型名称列表
        """
        try:
            import httpx
            
            list_endpoint = f"{self.base_url}/api/tags"
            with _make_no_proxy_client() as client:
                response = client.get(list_endpoint, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                models = data.get('models', [])
                return [model['name'] for model in models]
            else:
                return []
        
        except Exception as e:
            print(f"[WARNING] 获取 Ollama 模型列表失败: {e}")
            return []
    
    def check_ollama_status(self) -> bool:
        """
        检查 Ollama 服务是否可用
        
        Returns:
            bool: 服务是否可用
        """
        try:
            import httpx
            
            with _make_no_proxy_client() as client:
                response = client.get(f"{self.base_url}/api/tags", timeout=5)
            return response.status_code == 200
        
        except:
            return False
    
    @staticmethod
    def _convert_messages_for_ollama(messages: List[Dict]) -> List[Dict]:
        """将 OpenAI 格式的消息转换为 Ollama 兼容格式
        
        主要处理：
        - assistant 消息中的 tool_calls: arguments 从 JSON string → dict
        - tool 消息: 去掉 tool_call_id（Ollama 不需要）
        - content 为 None 的 assistant 消息: 转为空字符串
        """
        converted = []
        for msg in messages:
            role = msg.get('role', '')
            
            if role == 'assistant' and 'tool_calls' in msg:
                # 转换 tool_calls 格式
                new_msg = {'role': 'assistant', 'content': msg.get('content') or ''}
                new_tool_calls = []
                for tc in msg['tool_calls']:
                    new_tc = {'function': {'name': tc['function']['name']}}
                    args = tc['function'].get('arguments', '{}')
                    # JSON string → dict（Ollama 期望 dict）
                    if isinstance(args, str):
                        try:
                            new_tc['function']['arguments'] = json.loads(args)
                        except (json.JSONDecodeError, ValueError):
                            new_tc['function']['arguments'] = {}
                    else:
                        new_tc['function']['arguments'] = args
                    new_tool_calls.append(new_tc)
                new_msg['tool_calls'] = new_tool_calls
                converted.append(new_msg)
            
            elif role == 'tool':
                # Ollama 只需要 role + content，不需要 tool_call_id
                converted.append({
                    'role': 'tool',
                    'content': msg.get('content', '')
                })
            
            else:
                # system / user / 普通 assistant — 原样传递
                converted.append(msg)
        
        return converted
    
    def _accumulate_tool_calls(self, tool_calls_delta: List[Dict]):
        """
        累积 tool_calls
        
        Args:
            tool_calls_delta: tool_calls 数据
        """
        for tc in tool_calls_delta:
            self._tool_calls_buffer.append(tc)
    
    def _get_accumulated_tool_calls(self) -> List[Dict]:
        """
        获取累积的 tool_calls 并清空缓冲区
        
        Returns:
            List[Dict]: 完整的 tool_calls 列表
        """
        result = self._tool_calls_buffer.copy()
        self._tool_calls_buffer = []
        return result
    
    def generate_response_non_streaming(
        self,
        context_messages: List[Dict[str, str]],
        temperature: float = None,
        tools: List[Dict] = None
    ) -> Dict:
        """
        生成响应（非流式，用于工具调用检测）
        
        Args:
            context_messages: 消息历史
            temperature: 温度参数
            tools: Function Calling 工具列表
            
        Returns:
            Dict: {
                'type': 'tool_calls' | 'content',
                'tool_calls': [...] | None,
                'content': str | None
            }
        """
        try:
            import httpx
        except ImportError:
            raise Exception("httpx 库未安装，请运行: pip install httpx")
        
        try:
            # 构建请求体（非流式）
            ollama_messages = self._convert_messages_for_ollama(context_messages)
            payload = {
                "model": self.model_name,
                "messages": ollama_messages,
                "stream": False,
                "temperature": temperature if temperature is not None else self.default_temperature
            }
            
            if tools:
                payload["tools"] = tools
            
            # 发送请求（明确设置所有超时参数）
            # httpx.Timeout 需要明确指定 connect/read/write/pool 超时
            timeout = httpx.Timeout(
                connect=10.0,  # 连接超时10秒
                read=self.timeout,  # 读取超时使用配置的180秒
                write=10.0,  # 写入超时10秒
                pool=10.0  # 连接池超时10秒
            )
            # 禁用代理，避免 localhost 请求被系统代理拦截导致超时
            with _make_no_proxy_client(timeout=timeout) as client:
                response = client.post(
                    self.chat_endpoint,
                    json=payload
                )
            
            # 检查响应状态
            if response.status_code != 200:
                error_text = response.text
                try:
                    error_data = json.loads(error_text)
                    error_msg = error_data.get('error', error_text)
                except:
                    error_msg = error_text
                raise Exception(f"Ollama API 错误 ({response.status_code}): {error_msg}")
            
            # 解析响应
            data = response.json()
            
            if 'message' in data:
                message = data['message']
                
                # 检查是否有 tool_calls
                if 'tool_calls' in message and message['tool_calls']:
                    return {
                        'type': 'tool_calls',
                        'tool_calls': message['tool_calls'],
                        'content': None
                    }
                else:
                    # 返回普通内容
                    content = message.get('content', '')
                    return {
                        'type': 'content',
                        'tool_calls': None,
                        'content': content
                    }
            else:
                raise Exception("Ollama 响应格式错误：缺少 message")
        
        except httpx.ConnectError:
            raise Exception(f"无法连接到 Ollama 服务 ({self.base_url})，请确保 Ollama 已启动")
        except httpx.TimeoutException:
            raise Exception(f"Ollama 请求超时（{self.timeout}秒），模型可能在加载中")
        except Exception as e:
            raise Exception(f"Ollama 请求失败: {str(e)}")

