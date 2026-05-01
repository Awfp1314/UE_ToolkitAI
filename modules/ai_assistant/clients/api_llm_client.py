# -*- coding: utf-8 -*-

"""
API LLM 客户端（策略实现）
封装 OpenAI-HK API 或其他兼容的 API 调用逻辑
"""

import json
import os
import time
import requests
from typing import Dict, Any, Generator, List
from .base_llm_client import BaseLLMClient


class ApiLLMClient(BaseLLMClient):
    """
    API LLM 客户端策略
    
    支持 OpenAI-compatible API（如 OpenAI-HK、Anthropic 等）
    """
    
    def __init__(self, config: Dict[str, Any]):
        """
        初始化 API 客户端
        
        Args:
            config: API 配置字典，应包含：
                - api_url: API 端点 URL
                - api_key: API 密钥
                - default_model: 默认模型名称
                - temperature: 温度参数（可选）
                - timeout: 超时时间（可选）
        """
        super().__init__(config)
        
        # 从配置读取（不使用硬编码的默认值）
        self.api_url = config.get('api_url', 'https://api.openai.com/v1/chat/completions')
        self.api_key = config.get('api_key', '')
        self.default_model = config.get('default_model', 'gpt-3.5-turbo')
        self.default_temperature = config.get('temperature', 0.8)
        self.timeout = config.get('timeout', 60)
        
        # ⚡ 智能修正 API URL：自动补全缺失的 /v1/chat/completions 路径
        # 常见错误：用户只填写了域名（如 https://api.deepseek.com）
        if self.api_url and not self.api_url.endswith('/chat/completions'):
            # 检测常见的 API 域名并自动补全路径
            if 'deepseek.com' in self.api_url.lower():
                if not self.api_url.endswith('/v1/chat/completions'):
                    self.api_url = self.api_url.rstrip('/') + '/v1/chat/completions'
                    print(f"[API_URL_FIX] Deepseek URL 自动补全: {self.api_url}")
            elif 'openai.com' in self.api_url.lower() or 'openai-hk.com' in self.api_url.lower():
                if not self.api_url.endswith('/v1/chat/completions'):
                    self.api_url = self.api_url.rstrip('/') + '/v1/chat/completions'
                    print(f"[API_URL_FIX] OpenAI URL 自动补全: {self.api_url}")
            elif 'anthropic.com' in self.api_url.lower():
                # Claude API 使用不同的路径
                if not self.api_url.endswith('/v1/messages'):
                    self.api_url = self.api_url.rstrip('/') + '/v1/messages'
                    print(f"[API_URL_FIX] Claude URL 自动补全: {self.api_url}")
            # 其他通用 OpenAI 兼容 API
            elif '/v1' not in self.api_url:
                self.api_url = self.api_url.rstrip('/') + '/v1/chat/completions'
                print(f"[API_URL_FIX] 通用 API URL 自动补全: {self.api_url}")
        
        # 验证必需的配置
        if not self.api_key:
            raise ValueError(
                "API Key 未配置！\n\n"
                "请在 [设置 → AI 助手设置] 中配置 API Key。\n"
                "如果没有 API Key，可以访问 https://platform.openai.com/api-keys 获取，\n"
                "或使用其他兼容 OpenAI 的 API 服务。"
            )
        
        # 构建请求头（自动补全 Bearer 前缀，兼容各类 OpenAI 兼容 API）
        if self.api_key and not self.api_key.startswith('Bearer '):
            auth_value = f"Bearer {self.api_key}"
        else:
            auth_value = self.api_key
        
        self.headers = {
            "Content-Type": "application/json",
            "Authorization": auth_value
        }
        
        # 创建持久化的Session对象（复用连接，避免每次都建立新连接）
        self._session = requests.Session()
        self._session.trust_env = False  # 禁用环境变量代理
        self._session.proxies = {'http': None, 'https': None}  # 显式禁用代理
        # 设置连接池参数
        adapter = requests.adapters.HTTPAdapter(
            pool_connections=10,  # 连接池大小
            pool_maxsize=20,      # 最大连接数
            max_retries=3,        # 自动重试3次
            pool_block=False
        )
        self._session.mount('http://', adapter)
        self._session.mount('https://', adapter)
        
        # Tool calls 累积缓冲区
        self._tool_calls_buffer = []
        
        # 初始化 logger
        from core.logger import get_logger
        self.logger = get_logger(__name__)
    
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
            temperature: 温度参数（覆盖配置）
            tools: Function Calling 工具列表
            
        Yields:
            str: 响应的 token 块
        """
        # 关键调试：追踪API调用来源
        import traceback
        call_stack = ''.join(traceback.format_stack())
        print(f"\n{'='*80}")
        print(f"[API_CALL] !!! generate_response 被调用！")
        print(f"[API_CALL] 消息数量: {len(context_messages)}")
        print(f"[API_CALL] 工具数量: {len(tools) if tools else 0}")
        print(f"[API_CALL] 调用堆栈:\n{call_stack}")
        print(f"{'='*80}\n")
        
        try:
            # 清除环境变量中的代理设置（临时）
            env_backup = {}
            proxy_vars = ['http_proxy', 'https_proxy', 'HTTP_PROXY', 'HTTPS_PROXY', 'all_proxy', 'ALL_PROXY']
            for var in proxy_vars:
                if var in os.environ:
                    env_backup[var] = os.environ[var]
                    del os.environ[var]
            
            try:
                # 构建请求体
                payload = {
                    "model": self.default_model,
                    "messages": context_messages,
                    "temperature": temperature if temperature is not None else self.default_temperature,
                }
                
                # ⚡ 调试：打印消息内容，检查 reasoning_content
                print(f"[DEBUG] 发送的消息数量: {len(context_messages)}")
                for i, msg in enumerate(context_messages):
                    role = msg.get('role', 'unknown')
                    has_reasoning = 'reasoning_content' in msg
                    has_tool_calls = 'tool_calls' in msg
                    content_preview = str(msg.get('content', ''))[:50]
                    print(f"[DEBUG]   消息 {i+1}: role={role}, has_reasoning={has_reasoning}, has_tool_calls={has_tool_calls}, content={content_preview}...")
                    if has_reasoning:
                        reasoning_preview = msg['reasoning_content'][:100]
                        print(f"[DEBUG]     reasoning_content: {reasoning_preview}...")
                
                # 检查 API 是否为 Gemini 后端
                # 方法1: 检查 URL 中是否包含 gemini/google 关键词
                # 方法2: 检查模型名称是否包含 gemini
                # 方法3: 尝试发送请求，如果返回 "Unknown name 'stream'" 错误则判定为 Gemini
                is_gemini_api = (
                    'gemini' in self.api_url.lower() or 
                    'google' in self.api_url.lower() or
                    'gemini' in self.default_model.lower()
                )
                
                print(f"[DEBUG] API URL: {self.api_url}")
                print(f"[DEBUG] 模型名称: {self.default_model}")
                print(f"[DEBUG] 是否为 Gemini API: {is_gemini_api}")
                print(f"[DEBUG] stream 参数: {stream}")
                
                # 只有非 Gemini API 才在请求体中添加 stream 参数
                if not is_gemini_api:
                    payload["stream"] = stream
                    print(f"[DEBUG] 已添加 stream 到请求体（非 Gemini API）")
                else:
                    print(f"[DEBUG] 跳过 stream 参数（Gemini API）")
                
                # 添加 tools 参数（如果提供）
                if tools:
                    payload["tools"] = tools
                    print(f"[DEBUG] 已添加 tools 参数，工具数量: {len(tools)}")
                    print(f"[DEBUG] 工具列表:")
                    for i, tool in enumerate(tools):
                        tool_name = tool.get('function', {}).get('name', 'unknown')
                        tool_desc = tool.get('function', {}).get('description', '')[:100]
                        print(f"[DEBUG]   {i+1}. {tool_name}: {tool_desc}")
                    
                    # 检查是否有重复或相似的工具名称
                    tool_names = [t.get('function', {}).get('name', '') for t in tools]
                    blueprint_tools = [name for name in tool_names if 'blueprint' in name.lower() or 'extract' in name.lower()]
                    if len(blueprint_tools) > 1:
                        print(f"[WARNING] 检测到多个蓝图相关工具，可能导致混淆: {blueprint_tools}")
                else:
                    print(f"[DEBUG] 未提供 tools 参数")
                
                # 如果是 Gemini API 且需要流式，通过 URL 参数控制
                request_url = self.api_url
                if is_gemini_api and stream:
                    # Gemini API 使用 alt=sse 参数启用流式
                    separator = '&' if '?' in request_url else '?'
                    request_url = f"{request_url}{separator}alt=sse"
                
                # 使用持久化Session发送请求（复用连接）
                # ⚡ 流式请求使用 (connect_timeout, read_timeout) 元组
                # read_timeout 防止流式连接挂住（API 不发 [DONE] 时）
                req_timeout = (10, self.timeout) if stream else self.timeout
                response = self._session.post(
                    request_url,
                    headers=self.headers,
                    json=payload,
                    stream=stream,
                    timeout=req_timeout
                )
            finally:
                # 恢复环境变量
                for var, value in env_backup.items():
                    os.environ[var] = value
            
            # 检查响应状态
            if response.status_code != 200:
                error_text = response.text
                try:
                    error_data = json.loads(error_text)
                    error_msg = error_data.get('error', {}).get('message', error_text)
                except:
                    error_msg = error_text
                
                # 为常见错误提供更友好的提示
                if response.status_code == 404:
                    friendly_msg = (
                        f"API端点不存在 (404)。\n\n"
                        f"可能的原因：\n"
                        f"1. API URL配置错误: {self.api_url}\n"
                        f"2. 该端点需要有效的API密钥\n"
                        f"3. 服务器端点已更改或不可用\n\n"
                        f"请在 [设置 → AI 助手设置] 中检查API URL和API密钥配置。"
                    )
                    raise Exception(friendly_msg)
                elif response.status_code == 401:
                    friendly_msg = (
                        f"API密钥无效或过期 (401)。\n\n"
                        f"可能的原因：\n"
                        f"1. API密钥错误\n"
                        f"2. API密钥已过期\n"
                        f"3. 该API密钥没有访问权限\n\n"
                        f"请在 [设置 → AI 助手设置] 中更新API密钥。"
                    )
                    raise Exception(friendly_msg)
                elif response.status_code == 429:
                    friendly_msg = (
                        f"API请求频率限制 (429)。\n\n"
                        f"可能的原因：\n"
                        f"1. 请求过于频繁\n"
                        f"2. API配额已用完\n\n"
                        f"请稍后重试或检查API服务配额。"
                    )
                    raise Exception(friendly_msg)
                else:
                    raise Exception(f"API 错误 ({response.status_code}): {error_msg}")
            
            # 处理流式响应
            if stream:
                buffer = ""
                last_chunk_time = time.time()
                CHUNK_READ_TIMEOUT = 30  # 单个 chunk 最大等待秒数
                
                for chunk in response.iter_content(chunk_size=512, decode_unicode=False):
                    if not chunk:
                        continue
                    
                    last_chunk_time = time.time()
                    
                    try:
                        # 解码并添加到缓冲区
                        buffer += chunk.decode('utf-8')
                        
                        # 处理缓冲区中的完整行
                        while '\n' in buffer:
                            line, buffer = buffer.split('\n', 1)
                            line = line.strip()
                            
                            if not line or not line.startswith('data: '):
                                continue
                            
                            # 提取数据
                            data_str = line[6:]
                            
                            # 检查结束标记
                            if data_str == '[DONE]':
                                # ⚡ 关键修复：[DONE] 前检查是否有未 yield 的 tool_calls
                                if self._tool_calls_buffer:
                                    print(f"[DEBUG] [流式] [DONE] 时发现未yield的tool_calls，数量: {len(self._tool_calls_buffer)}")
                                    result = {
                                        'type': 'tool_calls',
                                        'tool_calls': self._get_accumulated_tool_calls()
                                    }
                                    # ⚡ DeepSeek thinking mode: 附加 reasoning_content
                                    if hasattr(self, '_reasoning_buffer') and self._reasoning_buffer:
                                        result['reasoning_content'] = self._reasoning_buffer
                                        self._reasoning_buffer = ''
                                    yield result
                                return
                            
                            # 解析并提取内容
                            try:
                                data = json.loads(data_str)
                                
                                # ⚡ 提取 token 使用量（在响应中可能出现）
                                usage = data.get('usage')
                                if usage and isinstance(usage, dict):
                                    yield {
                                        'type': 'token_usage',
                                        'usage': {
                                            'prompt_tokens': usage.get('prompt_tokens', 0),
                                            'completion_tokens': usage.get('completion_tokens', 0),
                                            'total_tokens': usage.get('total_tokens', 0)
                                        }
                                    }
                                
                                if 'choices' in data and len(data['choices']) > 0:
                                    choice = data['choices'][0]
                                    delta = choice.get('delta', {})
                                    
                                    # ⚡ DeepSeek thinking mode: 捕获 reasoning_content
                                    reasoning_content = delta.get('reasoning_content')
                                    if reasoning_content:
                                        # 累积 reasoning_content（可能分多个 chunk）
                                        if not hasattr(self, '_reasoning_buffer'):
                                            self._reasoning_buffer = ''
                                        self._reasoning_buffer += reasoning_content
                                        self.logger.info(f"[API_CLIENT] 捕获 reasoning_content chunk (长度: {len(reasoning_content)}, 总长度: {len(self._reasoning_buffer)})")
                                        # 不 yield reasoning_content，只在内部累积
                                        continue
                                    
                                    # 检测 tool_calls（优先级更高）
                                    tool_calls = delta.get('tool_calls')
                                    if tool_calls:
                                        # 累积 tool_calls（可能分多个 chunk）
                                        self._accumulate_tool_calls(tool_calls)
                                        continue
                                    
                                    # 检测 finish_reason
                                    finish_reason = choice.get('finish_reason')
                                    if finish_reason == 'tool_calls' or finish_reason == 'function_call':
                                        # 返回完整的 tool_calls（包含 reasoning_content）
                                        result = {
                                            'type': 'tool_calls',
                                            'tool_calls': self._get_accumulated_tool_calls()
                                        }
                                        # ⚡ DeepSeek thinking mode: 附加 reasoning_content
                                        if hasattr(self, '_reasoning_buffer') and self._reasoning_buffer:
                                            result['reasoning_content'] = self._reasoning_buffer
                                            self.logger.info(f"[API_CLIENT] ✅ 附加 reasoning_content 到结果 (长度: {len(self._reasoning_buffer)})")
                                            self._reasoning_buffer = ''  # 清空缓冲区
                                        else:
                                            self.logger.warning(f"[API_CLIENT] ⚠️ finish_reason={finish_reason} 但没有 reasoning_content")
                                        yield result
                                        return
                                    
                                    # ⚡ 关键修复：任何 finish_reason（如 'stop'）时，
                                    # 检查是否有累积的 tool_calls 未 yield
                                    if finish_reason and self._tool_calls_buffer:
                                        print(f"[DEBUG] [流式] finish_reason='{finish_reason}' 但有累积的tool_calls，数量: {len(self._tool_calls_buffer)}")
                                        result = {
                                            'type': 'tool_calls',
                                            'tool_calls': self._get_accumulated_tool_calls()
                                        }
                                        # ⚡ DeepSeek thinking mode: 附加 reasoning_content
                                        if hasattr(self, '_reasoning_buffer') and self._reasoning_buffer:
                                            result['reasoning_content'] = self._reasoning_buffer
                                            self._reasoning_buffer = ''
                                        yield result
                                        return
                                    
                                    # 正常的文本内容
                                    content = delta.get('content', '')
                                    
                                    # 尝试其他格式
                                    if not content:
                                        message = choice.get('message', {})
                                        content = message.get('content', '')
                                    
                                    if not content:
                                        content = choice.get('text', '')
                                    
                                    if content:
                                        yield {'type': 'content', 'text': content}
                            
                            except json.JSONDecodeError:
                                continue
                    
                    except UnicodeDecodeError:
                        # 多字节字符被分割，继续累积
                        continue
                
                # ⚡ 关键修复：流结束后（连接关闭/无 [DONE]），检查未 yield 的 tool_calls
                if self._tool_calls_buffer:
                    print(f"[DEBUG] [流式] 流结束时发现未yield的tool_calls，数量: {len(self._tool_calls_buffer)}")
                    result = {
                        'type': 'tool_calls',
                        'tool_calls': self._get_accumulated_tool_calls()
                    }
                    # ⚡ DeepSeek thinking mode: 附加 reasoning_content
                    if hasattr(self, '_reasoning_buffer') and self._reasoning_buffer:
                        result['reasoning_content'] = self._reasoning_buffer
                        self._reasoning_buffer = ''
                    yield result
                    return
            else:
                # 非流式响应
                data = response.json()
                if 'choices' in data and len(data['choices']) > 0:
                    content = data['choices'][0]['message']['content']
                    yield content
        
        except requests.exceptions.Timeout:
            raise Exception("请求超时，请检查网络连接")
        except requests.exceptions.ConnectionError:
            raise Exception("连接失败，请检查网络设置")
        except Exception as e:
            raise Exception(f"API 请求失败: {str(e)}")
    
    def get_model_name(self) -> str:
        """获取模型名称"""
        return self.default_model
    
    def _accumulate_tool_calls(self, tool_calls_delta: List[Dict]):
        """
        累积流式返回的 tool_calls
        
        Args:
            tool_calls_delta: tool_calls 增量数据
        """
        for tc_delta in tool_calls_delta:
            index = tc_delta.get('index', 0)
            
            # 扩展 buffer
            while len(self._tool_calls_buffer) <= index:
                self._tool_calls_buffer.append({
                    'id': '',
                    'type': 'function',
                    'function': {'name': '', 'arguments': ''}
                })
            
            # 累积数据
            if 'id' in tc_delta:
                self._tool_calls_buffer[index]['id'] = tc_delta['id']
            
            if 'function' in tc_delta:
                func = tc_delta['function']
                if 'name' in func:
                    self._tool_calls_buffer[index]['function']['name'] += func['name']
                if 'arguments' in func:
                    self._tool_calls_buffer[index]['function']['arguments'] += func['arguments']
    
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
            temperature: 温度参数（覆盖配置）
            tools: Function Calling 工具列表
            
        Returns:
            Dict: {
                'type': 'tool_calls' | 'content',
                'tool_calls': [...] | None,
                'content': str | None
            }
        """
        try:
            # 清除环境变量中的代理设置（临时）
            env_backup = {}
            proxy_vars = ['http_proxy', 'https_proxy', 'HTTP_PROXY', 'HTTPS_PROXY', 'all_proxy', 'ALL_PROXY']
            for var in proxy_vars:
                if var in os.environ:
                    env_backup[var] = os.environ[var]
                    del os.environ[var]
            
            try:
                # 构建请求体
                payload = {
                    "model": self.default_model,
                    "messages": context_messages,
                    "temperature": temperature if temperature is not None else self.default_temperature,
                    "stream": False
                }
                
                # 添加 tools 参数（如果提供）
                if tools:
                    payload["tools"] = tools
                
                # 使用持久化Session发送请求（复用连接）
                response = self._session.post(
                    self.api_url,
                    headers=self.headers,
                    json=payload,
                    timeout=self.timeout
                )
            finally:
                # 恢复环境变量
                for var, value in env_backup.items():
                    os.environ[var] = value
            
            # 检查响应状态
            if response.status_code != 200:
                error_text = response.text
                try:
                    error_data = json.loads(error_text)
                    error_msg = error_data.get('error', {}).get('message', error_text)
                except:
                    error_msg = error_text
                
                # 为常见错误提供更友好的提示
                if response.status_code == 404:
                    friendly_msg = (
                        f"API端点不存在 (404)。\n\n"
                        f"可能的原因：\n"
                        f"1. API URL配置错误: {self.api_url}\n"
                        f"2. 该端点需要有效的API密钥\n"
                        f"3. 服务器端点已更改或不可用\n\n"
                        f"请在 [设置 → AI 助手设置] 中检查API URL和API密钥配置。"
                    )
                    raise Exception(friendly_msg)
                elif response.status_code == 401:
                    friendly_msg = (
                        f"API密钥无效或过期 (401)。\n\n"
                        f"可能的原因：\n"
                        f"1. API密钥错误\n"
                        f"2. API密钥已过期\n"
                        f"3. 该API密钥没有访问权限\n\n"
                        f"请在 [设置 → AI 助手设置] 中更新API密钥。"
                    )
                    raise Exception(friendly_msg)
                elif response.status_code == 429:
                    friendly_msg = (
                        f"API请求频率限制 (429)。\n\n"
                        f"可能的原因：\n"
                        f"1. 请求过于频繁\n"
                        f"2. API配额已用完\n\n"
                        f"请稍后重试或检查API服务配额。"
                    )
                    raise Exception(friendly_msg)
                else:
                    raise Exception(f"API 错误 ({response.status_code}): {error_msg}")
            
            # 解析响应（防御空响应体）
            response_text = response.text or ""
            if not response_text.strip():
                # 记录详细诊断信息
                diag = (
                    f"API 返回了空响应体\n"
                    f"  状态码: {response.status_code}\n"
                    f"  URL: {self.api_url}\n"
                    f"  模型: {payload.get('model', 'unknown')}\n"
                    f"  响应头 Content-Type: {response.headers.get('Content-Type', 'N/A')}\n"
                    f"  响应头 Content-Length: {response.headers.get('Content-Length', 'N/A')}"
                )
                print(f"[ERROR] {diag}")
                raise Exception(
                    f"API 返回了空响应（状态码 {response.status_code}），"
                    f"模型 '{payload.get('model', '')}' 可能不被该 API 服务支持，"
                    f"请在设置中检查模型名称或更换模型"
                )
            try:
                data = json.loads(response_text)
            except (json.JSONDecodeError, ValueError):
                # 响应不是有效JSON，打印前200字符帮助诊断
                preview = response_text[:200] if len(response_text) > 200 else response_text
                print(f"[ERROR] API 返回了非JSON响应 (status={response.status_code}, len={len(response_text)}):\n{preview}")
                raise Exception(
                    f"API 返回了无法解析的响应（状态码 {response.status_code}），"
                    f"模型 '{payload.get('model', '')}' 可能不被该 API 服务支持。\n"
                    f"响应内容预览: {preview[:100]}"
                )
            
            # ⚡ 提取token使用统计
            usage = data.get('usage', {})
            
            if 'choices' in data and len(data['choices']) > 0:
                choice = data['choices'][0]
                message = choice.get('message', {})
                
                # 检查是否有 tool_calls
                if 'tool_calls' in message and message['tool_calls']:
                    return {
                        'type': 'tool_calls',
                        'tool_calls': message['tool_calls'],
                        'content': None,
                        'usage': usage  # ⚡ 添加token统计
                    }
                else:
                    # 返回普通内容
                    content = message.get('content', '')
                    return {
                        'type': 'content',
                        'tool_calls': None,
                        'content': content,
                        'usage': usage  # ⚡ 添加token统计
                    }
            else:
                raise Exception("API 响应格式错误：缺少 choices")
        
        except requests.exceptions.Timeout:
            raise Exception("请求超时，请检查网络连接")
        except requests.exceptions.ConnectionError:
            raise Exception("连接失败，请检查网络设置")
        except Exception as e:
            raise Exception(f"API 请求失败: {str(e)}")

    @staticmethod
    def fetch_available_models(api_url: str, api_key: str, timeout: int = 10) -> List[str]:
        """
        获取 API 支持的模型列表
        
        通过 GET /v1/models 接口获取，兼容所有 OpenAI 兼容 API。
        
        Args:
            api_url: API 的 chat completions URL（会自动推导 models 端点）
            api_key: API 密钥
            timeout: 超时时间
            
        Returns:
            List[str]: 可用模型名称列表（按字母排序）
        """
        import os
        
        # 从 chat completions URL 推导 models 端点
        models_url = api_url
        if '/chat/completions' in models_url:
            models_url = models_url.replace('/chat/completions', '/models')
        elif models_url.endswith('/v1'):
            models_url = models_url + '/models'
        elif not models_url.endswith('/models'):
            v1_idx = models_url.find('/v1/')
            if v1_idx >= 0:
                models_url = models_url[:v1_idx] + '/v1/models'
            else:
                models_url = models_url.rstrip('/') + '/v1/models'
        
        # 构建 Authorization 头
        if api_key and not api_key.startswith('Bearer '):
            auth_value = f"Bearer {api_key}"
        else:
            auth_value = api_key
        
        headers = {"Authorization": auth_value}
        
        # 临时清除代理
        env_backup = {}
        proxy_vars = ['http_proxy', 'https_proxy', 'HTTP_PROXY', 'HTTPS_PROXY', 'all_proxy', 'ALL_PROXY']
        for var in proxy_vars:
            if var in os.environ:
                env_backup[var] = os.environ[var]
                del os.environ[var]
        
        try:
            session = requests.Session()
            session.trust_env = False  # 禁用系统代理
            response = session.get(models_url, headers=headers, timeout=(5, 10),
                                   proxies={'http': None, 'https': None})
            if response.status_code != 200:
                error_msg = f"HTTP {response.status_code}"
                try:
                    error_data = response.json()
                    error_msg = error_data.get('error', {}).get('message', error_msg)
                except Exception:
                    pass
                raise Exception(error_msg)
            
            data = response.json()
            models = data.get('data', [])
            return sorted([m.get('id', '') for m in models if m.get('id')])
        finally:
            for var, value in env_backup.items():
                os.environ[var] = value

    @staticmethod
    def validate_model(api_url: str, api_key: str, model: str, timeout: int = 10) -> dict:
        """
        验证模型是否在 API 支持的模型列表中（零消耗，不发送实际请求）
        
        通过 /v1/models 接口检查模型是否存在，不会消耗 token，不会触发风控。
        
        Args:
            api_url: API 的 chat completions URL
            api_key: API 密钥
            model: 要验证的模型名称
            timeout: 超时时间
            
        Returns:
            dict: {'valid': bool, 'error': str or None}
        """
        try:
            models = ApiLLMClient.fetch_available_models(api_url, api_key, timeout=timeout)
            if not models:
                # 获取不到模型列表，跳过验证放行
                return {'valid': True, 'error': None}
            
            if model in models:
                return {'valid': True, 'error': None}
            else:
                return {'valid': False, 'error': f'模型不在可用列表中，请在设置中重新选择'}
        except Exception:
            # 获取模型列表失败，跳过验证放行（不阻塞用户）
            return {'valid': True, 'error': None}

    @staticmethod
    def validate_api_key(api_url: str, api_key: str, timeout: int = 10) -> dict:
        """
        验证 API Key 是否有效
        
        通过尝试获取模型列表来验证 API Key，不会消耗 token。
        
        Args:
            api_url: API 的 chat completions URL
            api_key: API 密钥
            timeout: 超时时间
            
        Returns:
            dict: {'valid': bool, 'error': str or None}
        """
        try:
            models = ApiLLMClient.fetch_available_models(api_url, api_key, timeout=timeout)
            # 如果能成功获取模型列表（即使为空），说明 API Key 有效
            return {'valid': True, 'error': None}
        except Exception as e:
            error_msg = str(e)
            # 解析常见错误
            if '401' in error_msg or 'Unauthorized' in error_msg or 'Invalid' in error_msg:
                return {'valid': False, 'error': 'API Key 无效或已过期'}
            elif '403' in error_msg or 'Forbidden' in error_msg:
                return {'valid': False, 'error': 'API Key 没有访问权限'}
            elif 'timeout' in error_msg.lower():
                return {'valid': False, 'error': '连接超时，请检查网络或 API URL'}
            else:
                return {'valid': False, 'error': f'验证失败: {error_msg}'}

