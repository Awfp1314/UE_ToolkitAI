# -*- coding: utf-8 -*-

"""
Function Calling 协调器
实现真正的两段式 Function Calling：LLM → 工具执行 → LLM 最终回复
支持多轮工具调用和循环限制
✨ 使用 ThreadManager 进行线程管理
⚠️ 兼容 DSML 格式（DeepSeek 特有格式）作为后备方案
"""

import json
import traceback
import time
from typing import Dict, List, Callable, Optional, Any
from PyQt6.QtCore import QObject, pyqtSignal
from core.utils.error_handler import ErrorHandler
from core.utils.thread_utils import CancellationToken
from core.logger import get_logger
from .dsml_parser import DSMLParser


def format_tool_result(result: Dict) -> str:
    """
    将工具执行结果格式化为 LLM 可理解的文本
    
    Args:
        result: 工具执行结果字典
        
    Returns:
        str: 格式化后的文本
    """
    if result.get('success'):
        tool_result = result.get('result', '')
        
        # 特殊处理：如果result是UE工具返回的dict（包含status字段）
        if isinstance(tool_result, dict):
            ue_status = tool_result.get('status')
            if ue_status == 'success':
                # UE工具执行成功，提取data字段
                ue_data = tool_result.get('data', tool_result)
                if isinstance(ue_data, (dict, list)):
                    ue_data = json.dumps(ue_data, ensure_ascii=False, indent=2)
                
                # ⚡ 截断过大的结果（防止上下文溢出）
                ue_data = _truncate_large_content(ue_data)
                return f"工具执行成功。结果:\n{ue_data}"
            elif ue_status == 'error':
                # UE工具执行失败
                ue_message = tool_result.get('message', '未知错误')
                return f"工具执行失败。错误: {ue_message}"
        
        # 普通工具结果处理
        if isinstance(tool_result, (dict, list)):
            tool_result = json.dumps(tool_result, ensure_ascii=False, indent=2)
        
        # ⚡ 截断过大的结果
        tool_result = _truncate_large_content(tool_result)
        return f"工具执行成功。结果:\n{tool_result}"
    else:
        error_msg = result.get('error', '未知错误')
        return f"工具执行失败。错误: {error_msg}"


def _truncate_large_content(content: str, max_chars: int = 8000) -> str:
    """
    截断过大的内容，防止上下文溢出
    
    Args:
        content: 原始内容
        max_chars: 最大字符数（约 2000 tokens）
        
    Returns:
        str: 截断后的内容
    """
    if len(content) <= max_chars:
        return content
    
    # 截断并添加提示
    truncated = content[:max_chars]
    remaining = len(content) - max_chars
    
    return (
        f"{truncated}\n\n"
        f"[内容过长，已截断。剩余 {remaining} 字符未显示。"
        f"如需完整内容，请要求用户提供更具体的查询条件。]"
    )


class FunctionCallingCoordinator(QObject):
    """
    Function Calling 协调器

    职责：
    1. 协调 LLM 和工具执行的多轮交互
    2. 检测 tool_calls 并执行工具
    3. 将工具结果返回 LLM 生成最终回复
    4. 提供 UI 回调支持
    ✨ 使用 ThreadManager 进行线程管理
    """

    # 信号定义
    tool_start = pyqtSignal(str)  # 工具开始执行：tool_name
    tool_complete = pyqtSignal(str, dict)  # 工具完成：tool_name, result
    chunk_received = pyqtSignal(str)  # 文本块接收：chunk
    request_finished = pyqtSignal()  # 请求完成
    token_usage = pyqtSignal(dict)  # Token 使用量统计
    error_occurred = pyqtSignal(str)  # 错误发生：error_message

    def __init__(
        self,
        messages: List[Dict],
        tools_registry,
        llm_client,
        max_iterations: int = 5
    ):
        """
        初始化协调器

        Args:
            messages: 初始消息列表
            tools_registry: 工具注册表实例
            llm_client: LLM 客户端实例
            max_iterations: 最大迭代次数（防止无限循环）
        """
        super().__init__()
        self.messages = messages.copy()
        self.tools_registry = tools_registry
        self.llm_client = llm_client
        self.max_iterations = max_iterations
        self._task_id: Optional[str] = None
        self._should_stop = False  # 用于控制流式输出的停止标志
        self.logger = get_logger(__name__)

        # API 调用计数器（用于测试和监控）
        self.api_call_count = 0
        
        # ⚡ 工具调用历史记录（用于检测重复调用）
        self.tool_call_history = []  # 格式: [(tool_name, tool_args_str), ...]
    
    def _execute_coordination(self, cancel_token: CancellationToken):
        """
        执行 Function Calling 流程

        Args:
            cancel_token: 取消令牌

        流程：
        1. 调用 LLM（带 tools 参数）
        2. 检查响应是否包含 tool_calls
        3. 如果有，执行工具并将结果追加到消息
        4. 重复步骤 1-3，直到 LLM 返回最终文本或达到最大迭代次数
        """
        # 关键调试：追踪协调器启动
        import traceback
        call_stack = ''.join(traceback.format_stack())
        print(f"\n{'='*80}")
        print(f"[COORDINATOR] !!! FunctionCallingCoordinator._execute_coordination() 被调用！")
        print(f"[COORDINATOR] 消息数量: {len(self.messages)}")
        tools_count = len(self.tools_registry.openai_tool_schemas()) if self.tools_registry else 0
        print(f"[COORDINATOR] 工具数量: {tools_count}")
        print(f"[COORDINATOR] 调用堆栈:\n{call_stack}")
        print(f"{'='*80}\n")

        try:
            iteration = 0

            while iteration < self.max_iterations and not cancel_token.is_cancelled():
                # 获取工具定义
                tools = self.tools_registry.openai_tool_schemas() if self.tools_registry else None
                
                # 所有轮次都使用流式请求，这样用户可以看到实时输出
                # 避免在工具调用后等待 API 响应时 UI 看起来卡住
                response_data = self._call_llm_streaming_with_tools(self.messages, tools, cancel_token)

                # ⚡ 递增迭代计数器（放在调用后，避免第一次判断错误）
                iteration += 1

                if cancel_token.is_cancelled():
                    break

                # 检查响应类型
                if response_data['type'] == 'stream_fallback':
                    # 流式回退：模型不支持工具，直接使用流式输出
                    # print("[DEBUG] [主循环] 收到stream_fallback标记，开始流式输出")  # 打包时自动注释
                    try:
                        self._stream_final_response(self.messages, tools=None)
                    except Exception as stream_error:
                        self.logger.error(f"[主循环] 流式输出失败: {stream_error}")
                        import traceback
                        traceback.print_exc()
                        # 发送错误信号
                        self.error_occurred.emit(f"流式输出失败: {str(stream_error)}")
                    break  # 跳出循环
                    
                elif response_data['type'] == 'tool_calls':
                    # LLM 决定调用工具
                    tool_calls = response_data['tool_calls']
                    streamed_prefix = response_data.get('content', '')
                    has_streamed_prefix = response_data.get('has_streamed_prefix', False)

                    # 标准化 tool_calls 格式（Ollama 缺少 id/type 字段）
                    for i, tc in enumerate(tool_calls):
                        if 'id' not in tc:
                            tc['id'] = f"call_{i}_{tc['function']['name']}"
                        if 'type' not in tc:
                            tc['type'] = 'function'
                        # arguments: dict → JSON string（OpenAI 格式要求）
                        args = tc['function'].get('arguments', {})
                        if isinstance(args, dict):
                            tc['function']['arguments'] = json.dumps(args, ensure_ascii=False)

                    # 构建 assistant 消息（包含 tool_calls 和可能的前置文本）
                    assistant_message = {
                        "role": "assistant",
                        "content": streamed_prefix if streamed_prefix else None,
                        "tool_calls": tool_calls
                    }
                    self.messages.append(assistant_message)

                    # 执行每个工具
                    for tool_call in tool_calls:
                        if cancel_token.is_cancelled():
                            break
                        
                        tool_name = tool_call['function']['name']
                        tool_args_str = tool_call['function']['arguments']
                        tool_call_id = tool_call['id']
                        
                        
                        # 通知 UI 工具开始
                        self.tool_start.emit(tool_name)
                        
                        # 执行工具
                        result = self._execute_tool(tool_name, tool_args_str)
                        
                        # 通知 UI 工具完成
                        self.tool_complete.emit(tool_name, result)
                        
                        # 将工具结果追加到消息
                        tool_message = {
                            "role": "tool",
                            "tool_call_id": tool_call_id,
                            "content": format_tool_result(result)
                        }
                        self.messages.append(tool_message)
                    
                    # 工具执行完毕，继续循环让模型决定下一步
                    # 模型可以选择：
                    # 1. 继续调用其他工具（如果需要更多信息）
                    # 2. 输出最终的文本回复
                    # 不要 break，让循环继续
                    continue
                    
                elif response_data['type'] == 'content':
                    # LLM 返回纯文本（不需要调用工具）
                    content = response_data.get('content', '')
                    usage = response_data.get('usage')
                    
                    # print(f"[DEBUG] [流式输出] 收到content响应，长度: {len(content)}, iteration: {iteration}")  # 打包时自动注释
                    
                    if response_data.get('already_streamed'):
                        # 第一轮流式已经直接输出了，不需要再处理
                        pass
                    elif content:
                        # 工具调用后的最终回复，用模拟打字
                        self._emit_content_with_typing(content)
                    else:
                        # content 为空，回退到流式重新请求
                        # print("[DEBUG] [content为空] 回退到流式输出重新请求")  # 打包时自动注释
                        try:
                            self._stream_final_response(self.messages, tools=None)
                        except Exception as stream_error:
                            self.logger.error(f"[回退流式] 失败: {stream_error}")
                            self.error_occurred.emit(f"获取回复失败: {str(stream_error)}")
                    
                    if usage:
                        self.token_usage.emit(usage)
                    
                    self.request_finished.emit()
                    break
                
                else:
                    # 未知响应类型
                    raise Exception(f"未知的响应类型: {response_data['type']}")
            
            if iteration >= self.max_iterations:
                # 超过最大迭代次数
                error_msg = f"工具调用次数过多（{self.max_iterations} 次），已终止"
                print(f"[WARNING] [FunctionCalling] {error_msg}")
                self.error_occurred.emit(error_msg)
        
        except Exception as e:
            # 使用 ErrorHandler 格式化和记录错误
            error_code = getattr(e, 'status_code', None) or getattr(e, 'code', None)
            ErrorHandler.log_error(e, "FunctionCallingCoordinator.run", error_code)

            # 格式化用户友好的错误消息
            formatted_error = ErrorHandler.format_error(e, error_code)
            user_error_msg = f"{formatted_error.title}: {formatted_error.message}"
            if formatted_error.suggestions:
                user_error_msg += f"\n建议: {formatted_error.suggestions[0]}"

            print(f"[ERROR] [FunctionCalling] {user_error_msg}")
            print(traceback.format_exc())

            # 向 UI 发送友好的错误消息
            self.error_occurred.emit(user_error_msg)
    
    def _call_llm_streaming_with_tools(self, messages: List[Dict], tools, cancel_token) -> Dict:
        """第一轮用流式请求，同时检测 tool_calls 和实时输出文本

        如果 LLM 返回 tool_calls → 收集完整 tool_calls 后返回
        如果 LLM 返回纯文本 → 边收边通过 chunk_received 信号输出，返回 already_streamed 标记
        """
        import time
        start_time = time.time()
        self.api_call_count += 1

        try:
            got_tool_calls = False
            accumulated_content = ""
            accumulated_usage = None

            for chunk in self.llm_client.generate_response(messages, stream=True, tools=tools):
                if self._should_stop or cancel_token.is_cancelled():
                    break

                if isinstance(chunk, dict):
                    chunk_type = chunk.get('type')

                    if chunk_type == 'tool_calls':
                        # 收到完整的 tool_calls
                        got_tool_calls = True
                        elapsed = time.time() - start_time
                        self.logger.info(f"[API调用 #{self.api_call_count}] 流式检测到tool_calls - 耗时: {elapsed:.2f}s")
                        return {
                            'type': 'tool_calls',
                            'tool_calls': chunk.get('tool_calls'),
                            'content': accumulated_content or None,  # 保留已输出的前置文本
                            'usage': accumulated_usage,
                            'has_streamed_prefix': bool(accumulated_content),  # 标记有前置文本
                        }

                    elif chunk_type == 'content':
                        text = chunk.get('text', '')
                        if text:
                            accumulated_content += text
                            
                            # ⚡ 实时检测 DSML 标记（提前中断）
                            if '<' in text and ('DSML' in accumulated_content or 'dsml' in accumulated_content.lower()):
                                # 可能开始输出 DSML，继续累积但不发送到 UI
                                self.logger.warning(f"[DSML检测] 检测到可能的 DSML 输出，暂停发送到 UI")
                                continue
                            
                            # 正常文本，发送到 UI
                            self.chunk_received.emit(text)

                    elif chunk_type == 'token_usage':
                        accumulated_usage = chunk.get('usage', {})
                        self.token_usage.emit(accumulated_usage)
                else:
                    # 字符串（向后兼容）
                    text = str(chunk)
                    accumulated_content += text
                    
                    # ⚡ 实时检测 DSML 标记（提前中断）
                    if '<' in text and ('DSML' in accumulated_content or 'dsml' in accumulated_content.lower()):
                        # 可能开始输出 DSML，继续累积但不发送到 UI
                        self.logger.warning(f"[DSML检测] 检测到可能的 DSML 输出，暂停发送到 UI")
                        continue
                    
                    # 正常文本，发送到 UI
                    self.chunk_received.emit(text)

            elapsed = time.time() - start_time
            self.logger.info(f"[API调用 #{self.api_call_count}] 流式完成 - 耗时: {elapsed:.2f}s, 内容长度: {len(accumulated_content)}")

            # ⚡ 兼容 DSML 格式（DeepSeek 特有格式，作为后备方案）
            if DSMLParser.contains_dsml(accumulated_content):
                self.logger.warning(f"[API调用 #{self.api_call_count}] ⚠️ 检测到 DSML 格式输出！")
                self.logger.warning(f"[DSML检测] 内容预览: {accumulated_content[:500]}")
                self.logger.warning(f"[DSML检测] 这表明模型没有使用标准 Function Calling 格式")
                self.logger.warning(f"[DSML检测] 可能原因：1) 对话历史污染 2) 工具定义不清晰 3) 模型配置问题")
                
                tool_calls = DSMLParser.parse_tool_calls(accumulated_content)
                
                if tool_calls:
                    self.logger.warning(f"[DSML解析] 成功解析出 {len(tool_calls)} 个工具调用")
                    for i, tc in enumerate(tool_calls):
                        tool_name = tc.get('function', {}).get('name', 'unknown')
                        self.logger.warning(f"[DSML解析] 工具 {i+1}: {tool_name}")
                    
                    # 移除 DSML 标记，保留前置文本
                    clean_content = DSMLParser.remove_dsml_tags(accumulated_content)
                    
                    return {
                        'type': 'tool_calls',
                        'tool_calls': tool_calls,
                        'content': clean_content or None,
                        'usage': accumulated_usage,
                        'has_streamed_prefix': bool(clean_content),
                    }
                else:
                    self.logger.error(f"[DSML解析] 检测到 DSML 标记但解析失败")
                    self.logger.error(f"[DSML解析] 内容: {accumulated_content}")

            return {
                'type': 'content',
                'content': accumulated_content,
                'usage': accumulated_usage,
                'already_streamed': True,  # 标记已经通过信号输出了
            }

        except Exception as e:
            # 检测 "does not support tools" 错误
            error_msg = str(e)
            if ('does not support tools' in error_msg.lower()
                    or 'tool' in error_msg.lower() and 'not supported' in error_msg.lower()):
                self.logger.warning(f"[FunctionCalling] 模型不支持工具，回退到无工具流式")
                return {
                    'type': 'stream_fallback',
                    'tool_calls': None,
                    'content': None,
                    'usage': None,
                }
            raise

    def _call_llm_non_streaming(self, messages: List[Dict], tools: List[Dict]) -> Dict:
        """
        调用 LLM（非流式）用于检测 tool_calls
        
        Args:
            messages: 消息列表
            tools: 工具定义列表
            
        Returns:
            Dict: {
                'type': 'tool_calls' | 'content',
                'tool_calls': [...] | None,
                'content': str | None,
                'usage': dict | None
            }
        """
        # 记录 API 调用时间戳
        start_time = time.time()
        self.api_call_count += 1
        
        self.logger.info(f"[API调用 #{self.api_call_count}] 开始时间: {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(start_time))}")
        
        try:
            # 调用 LLM 客户端的非流式方法
            response = self.llm_client.generate_response_non_streaming(messages, tools=tools)
            
            # 记录 API 调用完成和 Token 消耗
            elapsed_time = time.time() - start_time
            usage = response.get('usage', {})
            self.logger.info(
                f"[API调用 #{self.api_call_count}] 完成 - "
                f"耗时: {elapsed_time:.2f}s, "
                f"Token消耗: {usage.get('total_tokens', 'N/A')} "
                f"(prompt: {usage.get('prompt_tokens', 'N/A')}, "
                f"completion: {usage.get('completion_tokens', 'N/A')})"
            )
            
            return response
            
        except AttributeError:
            # 如果 LLM 客户端不支持非流式方法，回退到流式并累积
            self.logger.warning("[FunctionCalling] LLM 客户端不支持非流式调用，使用流式回退")
            
            accumulated_content = ""
            accumulated_tool_calls = None
            accumulated_usage = None
            
            for chunk in self.llm_client.generate_response(messages, stream=True, tools=tools):
                if isinstance(chunk, dict):
                    chunk_type = chunk.get('type')
                    
                    if chunk_type == 'tool_calls':
                        accumulated_tool_calls = chunk.get('tool_calls')
                    elif chunk_type == 'content':
                        accumulated_content += chunk.get('text', '')
                    elif chunk_type == 'token_usage':
                        accumulated_usage = chunk.get('usage', {})
                        # ⚡ 转发 token 使用量
                        self.token_usage.emit(accumulated_usage)
                else:
                    accumulated_content += str(chunk)
            
            # 记录 API 调用完成和 Token 消耗
            elapsed_time = time.time() - start_time
            if accumulated_usage:
                self.logger.info(
                    f"[API调用 #{self.api_call_count}] 完成 - "
                    f"耗时: {elapsed_time:.2f}s, "
                    f"Token消耗: {accumulated_usage.get('total_tokens', 'N/A')} "
                    f"(prompt: {accumulated_usage.get('prompt_tokens', 'N/A')}, "
                    f"completion: {accumulated_usage.get('completion_tokens', 'N/A')})"
                )
            else:
                self.logger.info(f"[API调用 #{self.api_call_count}] 完成 - 耗时: {elapsed_time:.2f}s")
            
            if accumulated_tool_calls:
                return {
                    'type': 'tool_calls',
                    'tool_calls': accumulated_tool_calls,
                    'content': None,
                    'usage': accumulated_usage
                }
            else:
                return {
                    'type': 'content',
                    'tool_calls': None,
                    'content': accumulated_content,
                    'usage': accumulated_usage
                }
                
        except Exception as e:
            # 记录 API 调用失败
            elapsed_time = time.time() - start_time
            self.logger.error(f"[API调用 #{self.api_call_count}] 失败 - 耗时: {elapsed_time:.2f}s")

            # 使用 ErrorHandler 格式化和记录错误
            error_code = getattr(e, 'status_code', None) or getattr(e, 'code', None)
            ErrorHandler.log_error(e, "FunctionCallingCoordinator._call_llm_non_streaming", error_code)

            # 检测 "does not support tools" 错误
            error_msg = str(e)
            if ('does not support tools' in error_msg.lower() 
                or 'function call is not supported' in error_msg.lower()
                or 'tool' in error_msg.lower() and 'not supported' in error_msg.lower()):
                # 使用 ErrorHandler 格式化错误消息
                formatted_error = ErrorHandler.format_error(e, error_code)
                self.logger.warning(
                    f"[FunctionCalling] {formatted_error.title}: {formatted_error.message}"
                )
                self.logger.warning(f"  回退方案: 禁用工具调用，使用普通聊天模式")

                # ⚡ 回退到无工具模式：使用流式API实现快速响应
                self.logger.info("[FunctionCalling] 回退到流式模式（无工具）...")
                # print("[DEBUG] [回退] 返回stream_fallback标记，将使用流式输出")  # 打包时自动注释
                
                # 返回一个特殊标记，告诉主循环使用流式输出
                return {
                    'type': 'stream_fallback',  # 特殊类型：流式回退
                    'tool_calls': None,
                    'content': None,
                    'usage': None
                }

            # ⚡ 关键修复：其他错误直接抛出，不重试
            # 原因：重试逻辑会导致重复 API 调用，浪费 Token
            raise
    
    def _emit_content_with_typing(self, content: str):
        """模拟自然的打字效果输出已有内容"""
        import time
        import random
        for char in content:
            self.chunk_received.emit(char)
            base_delay = 0.008
            random_variation = random.uniform(-0.002, 0.005)
            delay = base_delay + random_variation
            if char in '，。！？；：、,.:;!?\n':
                delay += random.uniform(0.02, 0.04)
            time.sleep(max(0.001, delay))

    def _stream_final_response(self, messages: List[Dict], tools, recursion_depth: int = 0, max_recursion: int = 5):
        """
        流式输出最终响应
        
        Args:
            messages: 消息列表
            tools: 工具定义列表（可以为None表示无工具模式）
            recursion_depth: 当前递归深度
            max_recursion: 最大递归深度（设置为999以观察循环行为）
        
        ⚠️ 修复说明：移除了重试逻辑，避免重复 API 调用
        如果模型不支持工具，应该在初始化时检测，而不是在运行时重试
        """
        # ⚡ 递归深度检查（仅用于日志，不终止）
        if recursion_depth >= max_recursion:
            self.logger.error(f"[流式输出] 递归深度超过限制 ({max_recursion})，停止递归")
            error_msg = f"工具调用递归次数过多（{max_recursion} 次），已终止。请检查 LLM 是否陷入循环。"
            self.chunk_received.emit(f"\n\n⚠️ {error_msg}")
            self.error_occurred.emit(error_msg)
            self.request_finished.emit()
            return
        
        # 记录递归深度（用于调试）
        self.logger.info(f"[流式输出] 开始流式输出最终响应，消息数:{len(messages)}，递归深度:{recursion_depth}/{max_recursion}")
        
        chunk_count = 0
        accumulated_content = ""  # ⚡ 累积内容用于检测
        
        # ⚡ 关键修复：移除重试逻辑，直接抛出异常
        # 原因：重试逻辑会导致重复 API 调用，浪费 Token
        for chunk in self.llm_client.generate_response(messages, stream=True, tools=tools):
            if self._should_stop:
                # print(f"[DEBUG] [流式输出] 收到停止信号，已输出{chunk_count}个chunk")  # 打包时自动注释
                break
            
            chunk_count += 1
            
            # 只处理文本内容和token统计
            if isinstance(chunk, dict):
                chunk_type = chunk.get('type')
                
                if chunk_type == 'content':
                    text = chunk.get('text', '')
                    if text:
                        accumulated_content += text
                        self.chunk_received.emit(text)
                            
                elif chunk_type == 'token_usage':
                    # ⚡ 转发 token 使用量
                    self.token_usage.emit(chunk.get('usage', {}))
            else:
                # 字符串类型（向后兼容）
                text = str(chunk)
                accumulated_content += text
                self.chunk_received.emit(text)
        
        # print(f"[DEBUG] [流式输出] 完成！共输出{chunk_count}个chunk")  # 打包时自动注释
        self.logger.info(f"[流式输出] 流式输出完成，共{chunk_count}个chunk")
        
        self.request_finished.emit()
    
    def _execute_tool(self, tool_name: str, tool_args_str: str) -> Dict:
        """
        执行工具
        
        Args:
            tool_name: 工具名称
            tool_args_str: 工具参数（JSON 字符串）
            
        Returns:
            Dict: {
                'success': bool,
                'result': Any | None,
                'error': str | None
            }
        """
        try:
            # 解析参数
            tool_args = json.loads(tool_args_str)
            
            # 调用工具注册表
            result = self.tools_registry.dispatch(tool_name, tool_args)
            
            # 检查结果格式
            if isinstance(result, dict) and 'success' in result:
                return result
            else:
                # 兼容旧格式
                return {
                    'success': True,
                    'result': result,
                    'error': None
                }
        
        except json.JSONDecodeError as e:
            return {
                'success': False,
                'result': None,
                'error': f"参数解析失败: {str(e)}"
            }
        
        except Exception as e:
            return {
                'success': False,
                'result': None,
                'error': f"工具执行异常: {str(e)}"
            }

    def start(self):
        """启动协调器（使用 ThreadManager）"""
        from core.utils.thread_utils import get_thread_manager
        thread_manager = get_thread_manager()

        try:
            # run_in_thread 返回 (QThread, Worker) 两个值
            thread, worker = thread_manager.run_in_thread(
                func=self._execute_coordination
            )
            self._thread = thread
            self._worker = worker
            self.logger.info(f"[COORDINATOR] 任务已提交")
        except Exception as e:
            self.logger.error(f"[COORDINATOR] 提交任务失败: {e}")
            import traceback
            traceback.print_exc()
            self.error_occurred.emit(str(e))

    def stop(self):
        """停止协调器"""
        self._should_stop = True  # 设置停止标志
        if self._task_id:
            from core.utils.thread_utils import get_thread_manager
            thread_manager = get_thread_manager()
            thread_manager.cancel_task(self._task_id)
            self.logger.info(f"[COORDINATOR] 任务已取消，task_id: {self._task_id}")

