#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
MCP (Model Context Protocol) Client

负责与 MCP Server 通信，动态发现和调用工具。
"""

import json
import subprocess
import threading
from typing import Dict, List, Any, Optional
from pathlib import Path
from core.logger import get_logger

logger = get_logger(__name__)


class MCPClient:
    """MCP Client - 与 MCP Server 通信"""
    
    def __init__(self, server_config: Dict[str, Any]):
        """
        初始化 MCP Client
        
        Args:
            server_config: MCP Server 配置
                {
                    "command": "python",
                    "args": ["path/to/server.py"],
                    "env": {},
                    "disabled": false
                }
        """
        self.server_config = server_config
        self.process: Optional[subprocess.Popen] = None
        self.tools: List[Dict[str, Any]] = []
        self._lock = threading.Lock()
        self._request_id = 0
        
        logger.info(f"初始化 MCP Client: {server_config.get('command')} {' '.join(server_config.get('args', []))}")
    
    def start(self) -> bool:
        """启动 MCP Server 进程"""
        if self.server_config.get("disabled", False):
            logger.info("MCP Server 已禁用，跳过启动")
            return False
        
        try:
            command = self.server_config["command"]
            args = self.server_config.get("args", [])
            env = self.server_config.get("env", {})
            
            # 启动进程
            self.process = subprocess.Popen(
                [command] + args,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1,
                env={**subprocess.os.environ, **env}
            )
            
            logger.info("MCP Server 进程已启动")
            
            # 初始化连接
            if not self._initialize():
                logger.error("MCP Server 初始化失败")
                self.stop()
                return False
            
            # 获取工具列表
            if not self._fetch_tools():
                logger.error("获取工具列表失败")
                self.stop()
                return False
            
            logger.info(f"MCP Client 启动成功，发现 {len(self.tools)} 个工具")
            return True
        
        except Exception as e:
            logger.error(f"启动 MCP Server 失败: {e}", exc_info=True)
            return False
    
    def stop(self):
        """停止 MCP Server 进程"""
        if self.process:
            try:
                self.process.terminate()
                self.process.wait(timeout=2)
                logger.info("MCP Server 进程已终止")
            except subprocess.TimeoutExpired:
                self.process.kill()
                logger.warning("MCP Server 进程强制终止")
            except Exception as e:
                logger.error(f"停止 MCP Server 失败: {e}")
            finally:
                self.process = None
    
    def get_tools(self) -> List[Dict[str, Any]]:
        """获取所有可用工具"""
        return self.tools
    
    def call_tool(self, name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """
        调用工具
        
        Args:
            name: 工具名称
            arguments: 工具参数
            
        Returns:
            Dict: 工具执行结果
                成功: {"success": True, "result": ...}
                失败: {"success": False, "error": ...}
        """
        if not self.process:
            return {
                "success": False,
                "error": "MCP Server 未启动"
            }
        
        try:
            # 发送 tools/call 请求
            request = {
                "jsonrpc": "2.0",
                "id": self._next_request_id(),
                "method": "tools/call",
                "params": {
                    "name": name,
                    "arguments": arguments
                }
            }
            
            response = self._send_request(request)
            
            if "error" in response:
                return {
                    "success": False,
                    "error": response["error"]["message"]
                }
            
            # 解析结果
            result = response.get("result", {})
            content = result.get("content", [])
            
            if content and len(content) > 0:
                text = content[0].get("text", "")
                
                # 检查是否是错误
                if result.get("isError"):
                    return {
                        "success": False,
                        "error": text
                    }
                
                return {
                    "success": True,
                    "result": text
                }
            
            return {
                "success": False,
                "error": "工具返回空结果"
            }
        
        except Exception as e:
            logger.error(f"调用工具失败: {e}", exc_info=True)
            return {
                "success": False,
                "error": str(e)
            }
    
    def _initialize(self) -> bool:
        """初始化 MCP 连接"""
        try:
            request = {
                "jsonrpc": "2.0",
                "id": self._next_request_id(),
                "method": "initialize",
                "params": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {},
                    "clientInfo": {
                        "name": "ue-toolkit-ai-assistant",
                        "version": "1.0.0"
                    }
                }
            }
            
            response = self._send_request(request)
            
            if "error" in response:
                logger.error(f"初始化失败: {response['error']}")
                return False
            
            logger.info("MCP 连接初始化成功")
            return True
        
        except Exception as e:
            logger.error(f"初始化异常: {e}", exc_info=True)
            return False
    
    def _fetch_tools(self) -> bool:
        """获取工具列表"""
        try:
            request = {
                "jsonrpc": "2.0",
                "id": self._next_request_id(),
                "method": "tools/list",
                "params": {}
            }
            
            response = self._send_request(request)
            
            if "error" in response:
                logger.error(f"获取工具列表失败: {response['error']}")
                return False
            
            self.tools = response.get("result", {}).get("tools", [])
            logger.info(f"获取到 {len(self.tools)} 个工具")
            return True
        
        except Exception as e:
            logger.error(f"获取工具列表异常: {e}", exc_info=True)
            return False
    
    def _send_request(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """发送请求并接收响应"""
        with self._lock:
            if not self.process or not self.process.stdin or not self.process.stdout:
                raise Exception("MCP Server 进程未运行")
            
            # 发送请求
            request_line = json.dumps(request) + "\n"
            self.process.stdin.write(request_line)
            self.process.stdin.flush()
            
            # 接收响应
            response_line = self.process.stdout.readline()
            if not response_line:
                raise Exception("MCP Server 无响应")
            
            response = json.loads(response_line)
            return response
    
    def _next_request_id(self) -> int:
        """生成下一个请求 ID"""
        self._request_id += 1
        return self._request_id


class MCPManager:
    """MCP Manager - 管理多个 MCP Client"""
    
    def __init__(self):
        self.clients: Dict[str, MCPClient] = {}
        logger.info("初始化 MCP Manager")
    
    def load_config(self, config_path: Optional[Path] = None) -> bool:
        """
        加载 MCP 配置文件
        
        Args:
            config_path: 配置文件路径，默认为 config/mcp_config.json
            
        Returns:
            bool: 是否成功加载
        """
        if config_path is None:
            # 默认配置路径
            config_path = Path(__file__).parent.parent.parent.parent / "config" / "mcp_config.json"
        
        if not config_path.exists():
            logger.warning(f"MCP 配置文件不存在: {config_path}")
            return False
        
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
            
            servers = config.get("mcpServers", {})
            
            for server_name, server_config in servers.items():
                if server_config.get("disabled", False):
                    logger.info(f"跳过已禁用的 MCP Server: {server_name}")
                    continue
                
                client = MCPClient(server_config)
                if client.start():
                    self.clients[server_name] = client
                    logger.info(f"MCP Server '{server_name}' 启动成功")
                else:
                    logger.error(f"MCP Server '{server_name}' 启动失败")
            
            logger.info(f"加载了 {len(self.clients)} 个 MCP Server")
            return len(self.clients) > 0
        
        except Exception as e:
            logger.error(f"加载 MCP 配置失败: {e}", exc_info=True)
            return False
    
    def get_all_tools(self) -> List[Dict[str, Any]]:
        """获取所有 MCP Server 的工具"""
        all_tools = []
        for server_name, client in self.clients.items():
            tools = client.get_tools()
            # 为每个工具添加 server_name 标记
            for tool in tools:
                tool["_mcp_server"] = server_name
            all_tools.extend(tools)
        return all_tools
    
    def call_tool(self, tool_name: str, arguments: Dict[str, Any], server_name: Optional[str] = None) -> Dict[str, Any]:
        """
        调用工具
        
        Args:
            tool_name: 工具名称
            arguments: 工具参数
            server_name: 指定 MCP Server（可选，如果不指定则自动查找）
            
        Returns:
            Dict: 工具执行结果
        """
        # 如果指定了 server_name，直接调用
        if server_name and server_name in self.clients:
            return self.clients[server_name].call_tool(tool_name, arguments)
        
        # 否则遍历所有 client 查找工具
        for client in self.clients.values():
            tools = client.get_tools()
            if any(tool["name"] == tool_name for tool in tools):
                return client.call_tool(tool_name, arguments)
        
        return {
            "success": False,
            "error": f"未找到工具: {tool_name}"
        }
    
    def stop_all(self):
        """停止所有 MCP Client"""
        for server_name, client in self.clients.items():
            logger.info(f"停止 MCP Server: {server_name}")
            client.stop()
        self.clients.clear()
