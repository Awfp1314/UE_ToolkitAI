# -*- coding: utf-8 -*-

"""
DSML (DeepSeek Markup Language) 解析器
用于解析 DeepSeek 模型返回的工具调用标记
"""

import re
import json
from typing import List, Dict, Optional


class DSMLParser:
    """DSML 格式解析器"""
    
    # DSML 标记模式
    FUNCTION_CALLS_START = r'<\|DSML\|function_calls>'
    FUNCTION_CALLS_END = r'</\|DSML\|function_calls>'
    INVOKE_START = r'<\|DSML\|invoke\s+name="([^"]+)">'
    INVOKE_END = r'</\|DSML\|invoke>'
    FUNCTION_ARGS_START = r'<\|DSML\|function_args>'
    FUNCTION_ARGS_END = r'</\|DSML\|function_args>'
    
    @staticmethod
    def contains_dsml(text: str) -> bool:
        """
        检查文本是否包含 DSML 标记
        
        Args:
            text: 要检查的文本
            
        Returns:
            bool: 是否包含 DSML 标记
        """
        return '<|DSML|' in text
    
    @staticmethod
    def parse_tool_calls(text: str) -> Optional[List[Dict]]:
        """
        从文本中解析 DSML 格式的工具调用
        
        Args:
            text: 包含 DSML 标记的文本
            
        Returns:
            List[Dict]: 工具调用列表，格式为 OpenAI tool_calls 格式
                       如果没有找到工具调用，返回 None
        """
        if not DSMLParser.contains_dsml(text):
            return None
        
        # 查找 function_calls 块
        function_calls_pattern = (
            rf'{DSMLParser.FUNCTION_CALLS_START}(.*?){DSMLParser.FUNCTION_CALLS_END}'
        )
        match = re.search(function_calls_pattern, text, re.DOTALL)
        
        if not match:
            return None
        
        function_calls_content = match.group(1)
        
        # 解析所有 invoke 块
        tool_calls = []
        invoke_pattern = (
            rf'{DSMLParser.INVOKE_START}(.*?){DSMLParser.INVOKE_END}'
        )
        
        for idx, invoke_match in enumerate(re.finditer(invoke_pattern, function_calls_content, re.DOTALL)):
            function_name = invoke_match.group(1)
            invoke_content = invoke_match.group(2)
            
            # 解析 function_args
            args_pattern = (
                rf'{DSMLParser.FUNCTION_ARGS_START}(.*?){DSMLParser.FUNCTION_ARGS_END}'
            )
            args_match = re.search(args_pattern, invoke_content, re.DOTALL)
            
            if args_match:
                args_content = args_match.group(1).strip()
                
                # 尝试解析 JSON 参数
                try:
                    # 移除可能的额外空白和换行
                    args_content = args_content.strip()
                    if args_content:
                        arguments = json.loads(args_content)
                    else:
                        arguments = {}
                except json.JSONDecodeError:
                    # 如果不是有效的 JSON，尝试解析键值对格式
                    arguments = DSMLParser._parse_key_value_args(args_content)
            else:
                arguments = {}
            
            # 转换为 OpenAI tool_calls 格式
            tool_call = {
                'id': f'call_{idx}',
                'type': 'function',
                'function': {
                    'name': function_name,
                    'arguments': json.dumps(arguments, ensure_ascii=False)
                }
            }
            tool_calls.append(tool_call)
        
        return tool_calls if tool_calls else None
    
    @staticmethod
    def _parse_key_value_args(text: str) -> Dict:
        """
        解析键值对格式的参数
        
        Args:
            text: 键值对文本，如 'key1: value1, key2: value2'
            
        Returns:
            Dict: 解析后的参数字典
        """
        args = {}
        
        # 尝试按行分割
        lines = text.strip().split('\n')
        for line in lines:
            line = line.strip()
            if ':' in line:
                key, value = line.split(':', 1)
                key = key.strip().strip('"\'')
                value = value.strip().strip(',').strip('"\'')
                
                # 尝试转换值类型
                if value.lower() == 'true':
                    value = True
                elif value.lower() == 'false':
                    value = False
                elif value.isdigit():
                    value = int(value)
                elif value.replace('.', '', 1).isdigit():
                    value = float(value)
                
                args[key] = value
        
        return args
    
    @staticmethod
    def remove_dsml_tags(text: str) -> str:
        """
        从文本中移除所有 DSML 标记
        
        Args:
            text: 包含 DSML 标记的文本
            
        Returns:
            str: 移除标记后的文本
        """
        # 移除 function_calls 块
        text = re.sub(
            rf'{DSMLParser.FUNCTION_CALLS_START}.*?{DSMLParser.FUNCTION_CALLS_END}',
            '',
            text,
            flags=re.DOTALL
        )
        
        # 移除其他可能的 DSML 标记
        text = re.sub(r'<\|DSML\|[^>]+>', '', text)
        text = re.sub(r'</\|DSML\|[^>]+>', '', text)
        
        return text.strip()
