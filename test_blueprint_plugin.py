# -*- coding: utf-8 -*-
"""
测试 BlueprintToAI 插件连接
"""

import requests
import json

def test_remote_control_api():
    """测试 Remote Control API 是否可用"""
    print("=" * 60)
    print("测试 1: Remote Control API 连接")
    print("=" * 60)
    
    try:
        response = requests.get('http://127.0.0.1:30010/remote/info', timeout=2.0)
        if response.status_code == 200:
            data = response.json()
            print("✅ Remote Control API 连接成功")
            print(f"   可用路由数量: {len(data.get('HttpRoutes', []))}")
            print(f"   当前预设: {data.get('ActivePreset', {}).get('Name', 'None')}")
            return True
        else:
            print(f"❌ HTTP 状态码错误: {response.status_code}")
            return False
    except requests.exceptions.ConnectionError:
        print("❌ 连接失败: UE 编辑器可能未运行或 Remote Control API 未启用")
        print("   解决方法:")
        print("   1. 确保 UE 编辑器正在运行")
        print("   2. 打开 编辑 → 项目设置 → Plugins → Remote Control")
        print("   3. 启用 'Enable Remote Control Web Server'")
        return False
    except Exception as e:
        print(f"❌ 连接失败: {e}")
        return False

def test_blueprint_subsystem():
    """测试 BlueprintToAISubsystem 是否可用"""
    print("\n" + "=" * 60)
    print("测试 2: BlueprintToAISubsystem 调用")
    print("=" * 60)
    
    try:
        # 调用 ExtractBlueprint 函数（使用一个不存在的路径来测试）
        request_data = {
            "objectPath": "/Script/BlueprintToAI.Default__BlueprintToAISubsystem",
            "functionName": "ExtractBlueprint",
            "parameters": {
                "AssetPath": "/Game/Test/BP_NonExistent",
                "Scope": "Compact"
            }
        }
        
        response = requests.put(
            'http://127.0.0.1:30010/remote/object/call',
            json=request_data,
            timeout=5.0
        )
        
        if response.status_code == 200:
            result = response.json()
            print("✅ BlueprintToAISubsystem 调用成功")
            print(f"   响应: {json.dumps(result, indent=2, ensure_ascii=False)}")
            return True
        else:
            print(f"❌ HTTP 状态码错误: {response.status_code}")
            print(f"   响应内容: {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ 调用失败: {e}")
        print("   可能原因:")
        print("   1. BlueprintToAI 插件未加载")
        print("   2. 插件编译失败")
        print("   3. 函数名称错误")
        return False

def test_python_client():
    """测试 Python 客户端"""
    print("\n" + "=" * 60)
    print("测试 3: Python UEToolClient")
    print("=" * 60)
    
    try:
        from modules.ai_assistant.clients.ue_tool_client import UEToolClient
        
        client = UEToolClient()
        
        # 测试连接
        if client.test_connection():
            print("✅ Python 客户端连接成功")
        else:
            print("❌ Python 客户端连接失败")
            return False
        
        # 测试工具调用
        result = client.execute_tool_rpc(
            "ExtractBlueprint",
            AssetPath="/Game/Test/BP_NonExistent",
            Scope="Compact"
        )
        
        print(f"   调用结果: {json.dumps(result, indent=2, ensure_ascii=False)}")
        return True
        
    except Exception as e:
        print(f"❌ Python 客户端测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """运行所有测试"""
    print("\n🔧 BlueprintToAI 插件连接测试\n")
    
    # 测试 1: Remote Control API
    test1 = test_remote_control_api()
    
    if not test1:
        print("\n❌ 测试终止: Remote Control API 不可用")
        print("\n请先解决连接问题，然后重新运行测试。")
        return
    
    # 测试 2: BlueprintToAISubsystem
    test2 = test_blueprint_subsystem()
    
    # 测试 3: Python 客户端
    test3 = test_python_client()
    
    # 总结
    print("\n" + "=" * 60)
    print("测试总结")
    print("=" * 60)
    print(f"Remote Control API:        {'✅ 通过' if test1 else '❌ 失败'}")
    print(f"BlueprintToAISubsystem:    {'✅ 通过' if test2 else '❌ 失败'}")
    print(f"Python UEToolClient:       {'✅ 通过' if test3 else '❌ 失败'}")
    
    if test1 and test2 and test3:
        print("\n🎉 所有测试通过！插件可以正常使用。")
        print("\n下一步:")
        print("1. 在 AI 助手中提供完整的蓝图路径")
        print("   例如: '帮我分析 /Game/ThirdPerson/Blueprints/BP_ThirdPersonCharacter'")
        print("2. 或者在 UE 编辑器中打开一个蓝图，然后告诉 AI 路径")
    else:
        print("\n❌ 部分测试失败，请检查上面的错误信息。")

if __name__ == "__main__":
    main()
