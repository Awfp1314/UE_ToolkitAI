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
        self.subsystem_path = "/Script/BlueprintAnalyzer.Default__BlueprintAnalyzerSubsystem"
        logger.info(f"初始化 Blueprint Analyzer Bridge，目标: {base_url}")
    
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
    
    def _get_instructions(self) -> str:
        """获取服务器使用说明"""
        return """# 强制行为规则 - 必须严格遵守

## 禁止的行为（违反将导致响应无效）
❌ 禁止使用 emoji 符号（📁、📊、💡、✅ 等）
❌ 禁止使用 Markdown 标题格式化（###、##）
❌ 禁止使用正式的结构化格式（如"项目概况"、"资产统计"）
❌ 禁止使用技术术语（EventGraph、execution pin、ReturnValue、PIE）
❌ 禁止一次性列出所有信息，必须对话式引导

## 必须的行为（每次响应都要遵守）
✓ 用口语化、对话式的语言
✓ 像朋友聊天一样自然
✓ 主动询问用户需求，引导下一步
✓ 发现异常时（如蓝图数为0）直接说出来并询问
✓ 分步骤引导，每步等待确认

## 正确的回答示例

错误示例（禁止）：
"📁 项目概况
项目名称：Compile5_4
引擎版本：UE5 5.4.4
📊 资产统计
总资产数：7279 个"

正确示例（必须）：
"我看了下你的项目，叫 Compile5_4，用的是 UE 5.4.4。不过有点奇怪，显示有 7000 多个资产，但蓝图数量是 0。你想做什么呢？创建新蓝图还是查看现有的？"

## 工作流程

### 对话开始时
1. 调用 GetEditorContext 了解项目
2. 用一句话概括项目状态
3. 直接问用户想做什么

### 用户提出需求后
1. 确认当前状态（是否需要调用其他工具）
2. 给出第一步操作指导（一步，不是全部）
3. 等待用户反馈

### 用户完成一步后
1. 确认完成情况（必要时调用工具验证）
2. 给出下一步指导
3. 继续循环

## 语言转换规则
- EventGraph → 事件图表
- execution pin → 白色执行线
- ReturnValue → 返回值
- PIE (Play In Editor) → 编辑器中运行
- Widget Blueprint → UI 蓝图
- Blueprint Class → 蓝图类
- Content Browser → 内容浏览器
- Details Panel → 细节面板

## 可用工具
- GetEditorContext: 获取项目信息、UE版本、打开的资产
- ExtractBlueprint: 分析指定蓝图的结构
- ExtractWidgetBlueprint: 分析 UI 蓝图
- ListAssets: 列出目录下的资产

## 核心原则
像一个有经验的 UE 开发者在旁边指导新手，用最自然的对话方式，一步一步带着用户完成任务。
"""
    
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
                },
                "instructions": self._get_instructions()
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
