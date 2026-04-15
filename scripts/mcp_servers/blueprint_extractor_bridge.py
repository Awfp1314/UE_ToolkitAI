#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Blueprint Extractor MCP Bridge Server

将 Blueprint Extractor 插件的 HTTP API 包装为标准 MCP Server。
实现 MCP stdio 协议，支持工具发现和调用。

协议：https://modelcontextprotocol.io/
"""

import sys
import json
import logging
from typing import Dict, Any, List
import requests
from pathlib import Path

# 配置日志
log_dir = Path(__file__).parent.parent.parent / "logs" / "mcp"
log_dir.mkdir(parents=True, exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_dir / "blueprint_extractor_bridge.log"),
        logging.StreamHandler(sys.stderr)  # MCP 要求日志输出到 stderr
    ]
)
logger = logging.getLogger(__name__)


class BlueprintExtractorBridge:
    """Blueprint Extractor MCP Bridge"""
    
    def __init__(self, base_url: str = "http://127.0.0.1:30010"):
        self.base_url = base_url
        self.subsystem_path = "/Script/BlueprintExtractor.Default__BlueprintExtractorSubsystem"
        logger.info(f"初始化 Blueprint Extractor Bridge，目标: {base_url}")
    
    def get_tools(self) -> List[Dict[str, Any]]:
        """返回所有可用工具的定义"""
        # 从外部文件加载工具定义
        tools_file = Path(__file__).parent / "blueprint_extractor_tools.json"
        
        if tools_file.exists():
            with open(tools_file, 'r', encoding='utf-8') as f:
                tools = json.load(f)
                logger.info(f"从文件加载了 {len(tools)} 个工具定义")
                return tools
        else:
            logger.warning("工具定义文件不存在，返回空列表")
            return []
    
    def call_tool(self, name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """调用 UE 插件的 HTTP API"""
        try:
            logger.info(f"调用工具: {name}, 参数: {arguments}")
            
            # 调用 UE Remote Control API
            response = requests.put(
                f"{self.base_url}/remote/object/call",
                json={
                    "objectPath": self.subsystem_path,
                    "functionName": name,
                    "parameters": arguments
                },
                timeout=30
            )
            
            if response.status_code == 200:
                result = response.json()
                logger.info(f"工具调用成功: {name}")
                return {
                    "content": [
                        {
                            "type": "text",
                            "text": json.dumps(result, ensure_ascii=False, indent=2)
                        }
                    ]
                }
            else:
                error_msg = f"HTTP 错误 {response.status_code}: {response.text}"
                logger.error(error_msg)
                return {
                    "content": [
                        {
                            "type": "text",
                            "text": f"工具调用失败: {error_msg}"
                        }
                    ],
                    "isError": True
                }
        
        except requests.exceptions.ConnectionError:
            error_msg = "无法连接到 UE 编辑器。请确保 UE 正在运行且 Blueprint Extractor 插件已启用。"
            logger.error(error_msg)
            return {
                "content": [
                    {
                        "type": "text",
                        "text": error_msg
                    }
                ],
                "isError": True
            }
        
        except Exception as e:
            error_msg = f"工具调用异常: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return {
                "content": [
                    {
                        "type": "text",
                        "text": error_msg
                    }
                ],
                "isError": True
            }


class MCPServer:
    """MCP stdio 协议服务器"""
    
    def __init__(self, bridge: BlueprintExtractorBridge):
        self.bridge = bridge
        logger.info("MCP Server 初始化完成")
    
    def handle_request(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """处理 MCP 请求"""
        method = request.get("method")
        request_id = request.get("id")
        
        logger.info(f"收到请求: method={method}, id={request_id}")
        
        try:
            if method == "initialize":
                return self._handle_initialize(request_id)
            
            elif method == "tools/list":
                return self._handle_tools_list(request_id)
            
            elif method == "tools/call":
                return self._handle_tools_call(request_id, request.get("params", {}))
            
            else:
                return self._error_response(request_id, -32601, f"未知方法: {method}")
        
        except Exception as e:
            logger.error(f"处理请求失败: {e}", exc_info=True)
            return self._error_response(request_id, -32603, str(e))
    
    def _handle_initialize(self, request_id) -> Dict[str, Any]:
        """处理初始化请求"""
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "result": {
                "protocolVersion": "2024-11-05",
                "capabilities": {
                    "tools": {}
                },
                "serverInfo": {
                    "name": "blueprint-extractor-bridge",
                    "version": "1.0.0"
                }
            }
        }
    
    def _handle_tools_list(self, request_id) -> Dict[str, Any]:
        """处理工具列表请求"""
        tools = self.bridge.get_tools()
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "result": {
                "tools": tools
            }
        }
    
    def _handle_tools_call(self, request_id, params: Dict[str, Any]) -> Dict[str, Any]:
        """处理工具调用请求"""
        tool_name = params.get("name")
        arguments = params.get("arguments", {})
        
        if not tool_name:
            return self._error_response(request_id, -32602, "缺少工具名称")
        
        result = self.bridge.call_tool(tool_name, arguments)
        
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "result": result
        }
    
    def _error_response(self, request_id, code: int, message: str) -> Dict[str, Any]:
        """生成错误响应"""
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "error": {
                "code": code,
                "message": message
            }
        }
    
    def run(self):
        """运行 MCP Server（stdio 主循环）"""
        logger.info("MCP Server 启动，等待请求...")
        
        try:
            for line in sys.stdin:
                line = line.strip()
                if not line:
                    continue
                
                try:
                    request = json.loads(line)
                    response = self.handle_request(request)
                    
                    # 输出响应到 stdout
                    print(json.dumps(response), flush=True)
                
                except json.JSONDecodeError as e:
                    logger.error(f"JSON 解析失败: {e}")
                    error_response = self._error_response(None, -32700, "JSON 解析错误")
                    print(json.dumps(error_response), flush=True)
        
        except KeyboardInterrupt:
            logger.info("收到中断信号，退出...")
        
        except Exception as e:
            logger.error(f"MCP Server 异常: {e}", exc_info=True)


def main():
    """主函数"""
    # 从命令行参数获取配置
    import argparse
    parser = argparse.ArgumentParser(description="Blueprint Extractor MCP Bridge")
    parser.add_argument("--base-url", default="http://127.0.0.1:30010", help="UE HTTP API 地址")
    args = parser.parse_args()
    
    # 创建桥接和服务器
    bridge = BlueprintExtractorBridge(base_url=args.base_url)
    server = MCPServer(bridge)
    
    # 运行服务器
    server.run()


if __name__ == "__main__":
    main()
