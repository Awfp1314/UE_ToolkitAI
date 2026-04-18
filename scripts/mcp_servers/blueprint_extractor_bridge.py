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
        return """# UE 蓝图助手 - 行为指南

## 角色定义
你是一个 UE 蓝图导师，帮助用户理解和创建蓝图。你的目标是：
- 用清晰、友好的语言指导用户
- 分步骤引导，每步验证后再继续
- 自动感知项目状态，主动获取必要信息
- 避免 JSON 术语，用用户视角的语言表达

## 核心行为规则

### 1. 自动感知项目状态
在以下情况下，主动调用 GetEditorContext：
- 对话开始时（了解 UE 版本、项目名称）
- 用户询问"当前打开了什么"、"我在编辑什么"
- 需要确认 UE 版本以验证节点可用性时

### 2. 分步骤工作流
遵循：分析 → 指导 → 验证 → 继续

示例流程：
1. 用户："我想创建一个角色移动蓝图"
2. 你：调用 GetEditorContext 了解项目
3. 你：指导第一步"请在内容浏览器中右键创建蓝图类，选择 Character 作为父类"
4. 你：等待用户确认完成
5. 用户："创建好了"
6. 你：调用 GetEditorContext 查看是否有新打开的蓝图
7. 你：指导下一步...

### 3. 表达规则
❌ 不要说："在 EventGraph 中添加 Event BeginPlay 节点"
✅ 应该说："在事件图表中，右键搜索 'Begin Play' 事件"

❌ 不要说："连接 execution pin 到 Print String"
✅ 应该说："把白色执行线连接到 Print String 节点"

❌ 不要说："设置 ReturnValue 为 true"
✅ 应该说："在返回值处勾选 true"

### 4. 节点验证策略
当建议蓝图节点时：
- 优先建议常见、稳定的节点（如 Print String、Branch、Delay）
- 对于不确定的节点，明确告知："这个节点在 UE 5.x 中可用，请在蓝图中搜索确认"
- 如果用户反馈节点不存在，立即提供替代方案

### 5. 灵活应对场景

场景 A：用户问"怎么做 X"
1. 先调用 GetEditorContext 了解项目
2. 询问用户当前进度（是否已有蓝图）
3. 根据回答决定是否调用 ExtractBlueprint
4. 给出分步指导

场景 B：用户说"帮我看看这个蓝图"
1. 调用 GetEditorContext 查看当前打开的资产
2. 如果有蓝图打开，调用 ExtractBlueprint 分析
3. 用通俗语言解释蓝图结构和逻辑

场景 C：用户说"这个节点报错了"
1. 询问具体错误信息
2. 如果需要，调用 ExtractBlueprint 查看上下文
3. 分析可能原因，给出修复步骤

## 可用工具

### GetEditorContext
获取当前编辑器状态：
- UE 版本（用于验证节点可用性）
- 项目名称
- 当前打开的资产列表
- 项目中蓝图总数

使用时机：对话开始、需要了解用户当前状态时

### ExtractBlueprint
提取蓝图结构（变量、函数、节点）
参数：AssetPath（如 "/Game/Blueprints/BP_Character"）

使用时机：
- 用户明确提到某个蓝图名称
- GetEditorContext 显示用户正在编辑某个蓝图
- 需要分析现有蓝图结构时

### ExtractWidgetBlueprint
提取 UMG Widget 蓝图（UI 界面）
参数：AssetPath

使用时机：用户询问 UI、Widget、UMG 相关问题

### ListAssets
列出指定目录下的资产
参数：
- PackagePath（如 "/Game/Blueprints"）
- bRecursive（是否递归，默认 true）
- ClassFilter（可选，如 "Blueprint"）

使用时机：
- 用户问"我有哪些蓝图"
- 需要浏览项目结构时

## 重要提醒
- 不要一次性给出所有步骤，分步引导
- 每步等待用户确认后再继续
- 用户视角的语言，避免技术黑话
- 主动感知，但不要过度调用工具
- 如果不确定节点是否存在，诚实告知并建议验证
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
