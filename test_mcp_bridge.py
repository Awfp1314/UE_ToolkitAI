#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
测试 Blueprint Extractor MCP Bridge

验证 MCP 桥接服务器是否正常工作
"""

import subprocess
import json
import sys
import time

def test_mcp_bridge():
    """测试 MCP Bridge"""
    print("=" * 80)
    print("测试 Blueprint Extractor MCP Bridge")
    print("=" * 80)
    
    # 启动 MCP Bridge 进程
    print("\n1. 启动 MCP Bridge...")
    process = subprocess.Popen(
        [sys.executable, "scripts/mcp_servers/blueprint_extractor_bridge.py"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1
    )
    
    try:
        # 测试 1: Initialize
        print("\n2. 测试 initialize 请求...")
        init_request = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {
                    "name": "test-client",
                    "version": "1.0.0"
                }
            }
        }
        
        process.stdin.write(json.dumps(init_request) + "\n")
        process.stdin.flush()
        
        response_line = process.stdout.readline()
        if response_line:
            response = json.loads(response_line)
            print(f"✓ Initialize 成功")
            print(f"  服务器: {response['result']['serverInfo']['name']}")
            print(f"  版本: {response['result']['serverInfo']['version']}")
        else:
            print("✗ Initialize 失败：无响应")
            return False
        
        # 测试 2: Tools List
        print("\n3. 测试 tools/list 请求...")
        list_request = {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/list",
            "params": {}
        }
        
        process.stdin.write(json.dumps(list_request) + "\n")
        process.stdin.flush()
        
        response_line = process.stdout.readline()
        if response_line:
            response = json.loads(response_line)
            tools = response['result']['tools']
            print(f"✓ Tools List 成功")
            print(f"  工具数量: {len(tools)}")
            print(f"  前 5 个工具:")
            for tool in tools[:5]:
                print(f"    - {tool['name']}: {tool['description'][:50]}...")
        else:
            print("✗ Tools List 失败：无响应")
            return False
        
        # 测试 3: Tool Call (GetEditorContext)
        print("\n4. 测试 tools/call 请求 (GetEditorContext)...")
        call_request = {
            "jsonrpc": "2.0",
            "id": 3,
            "method": "tools/call",
            "params": {
                "name": "GetEditorContext",
                "arguments": {}
            }
        }
        
        process.stdin.write(json.dumps(call_request) + "\n")
        process.stdin.flush()
        
        response_line = process.stdout.readline()
        if response_line:
            response = json.loads(response_line)
            if 'result' in response:
                content = response['result']['content'][0]['text']
                print(f"✓ Tool Call 成功")
                print(f"  返回内容长度: {len(content)} 字符")
                
                # 尝试解析返回的 JSON
                try:
                    result_data = json.loads(content)
                    if 'ReturnValue' in result_data:
                        print(f"  UE 编辑器已连接")
                    else:
                        print(f"  返回数据: {content[:100]}...")
                except:
                    print(f"  返回数据: {content[:100]}...")
            elif 'error' in response:
                print(f"✗ Tool Call 失败: {response['error']['message']}")
        else:
            print("✗ Tool Call 失败：无响应")
            return False
        
        print("\n" + "=" * 80)
        print("✓ 所有测试通过！MCP Bridge 工作正常")
        print("=" * 80)
        return True
    
    except Exception as e:
        print(f"\n✗ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    finally:
        # 清理进程
        print("\n5. 清理...")
        process.terminate()
        try:
            process.wait(timeout=2)
        except subprocess.TimeoutExpired:
            process.kill()
        print("✓ 进程已终止")


if __name__ == "__main__":
    success = test_mcp_bridge()
    sys.exit(0 if success else 1)
