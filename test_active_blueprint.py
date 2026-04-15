# -*- coding: utf-8 -*-
"""
测试 GetActiveBlueprint 功能
"""

import requests
import json

def test_get_active_blueprint():
    """测试获取激活蓝图功能"""
    print("=" * 60)
    print("测试: GetActiveBlueprint")
    print("=" * 60)
    
    try:
        # 调用 GetActiveBlueprint 函数
        request_data = {
            "objectPath": "/Script/BlueprintToAI.Default__BlueprintToAISubsystem",
            "functionName": "GetActiveBlueprint",
            "parameters": {}
        }
        
        print(f"发送请求: {json.dumps(request_data, indent=2)}")
        
        response = requests.put(
            'http://127.0.0.1:30010/remote/object/call',
            json=request_data,
            timeout=5.0
        )
        
        print(f"\nHTTP 状态码: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            print(f"\n✅ 调用成功")
            print(f"响应: {json.dumps(result, indent=2, ensure_ascii=False)}")
            
            # 检查是否有 ReturnValue
            if "ReturnValue" in result:
                return_value = json.loads(result["ReturnValue"])
                print(f"\n解析后的返回值:")
                print(json.dumps(return_value, indent=2, ensure_ascii=False))
                
                if return_value.get("success"):
                    print(f"\n🎉 成功获取激活蓝图!")
                    print(f"   蓝图路径: {return_value['data']['assetPath']}")
                    print(f"   蓝图名称: {return_value['data']['name']}")
                else:
                    print(f"\n❌ 获取失败: {return_value.get('error')}")
            
            return True
        else:
            print(f"❌ HTTP 状态码错误: {response.status_code}")
            print(f"响应内容: {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ 调用失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_extract_active_blueprint():
    """测试提取激活蓝图功能"""
    print("\n" + "=" * 60)
    print("测试: ExtractActiveBlueprint")
    print("=" * 60)
    
    try:
        # 调用 ExtractActiveBlueprint 函数
        request_data = {
            "objectPath": "/Script/BlueprintToAI.Default__BlueprintToAISubsystem",
            "functionName": "ExtractActiveBlueprint",
            "parameters": {
                "Scope": "Compact"
            }
        }
        
        print(f"发送请求: {json.dumps(request_data, indent=2)}")
        
        response = requests.put(
            'http://127.0.0.1:30010/remote/object/call',
            json=request_data,
            timeout=10.0
        )
        
        print(f"\nHTTP 状态码: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            print(f"\n✅ 调用成功")
            
            # 检查是否有 ReturnValue
            if "ReturnValue" in result:
                return_value = json.loads(result["ReturnValue"])
                
                if return_value.get("success"):
                    print(f"\n🎉 成功提取激活蓝图!")
                    blueprint_data = return_value.get("blueprint", {})
                    print(f"   蓝图名称: {blueprint_data.get('name')}")
                    print(f"   父类: {blueprint_data.get('parentClass')}")
                    print(f"   图表数量: {len(blueprint_data.get('graphs', []))}")
                else:
                    print(f"\n❌ 提取失败: {return_value.get('error')}")
            
            return True
        else:
            print(f"❌ HTTP 状态码错误: {response.status_code}")
            print(f"响应内容: {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ 调用失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    print("\n🔧 测试激活蓝图功能\n")
    print("⚠️  请确保:")
    print("   1. UE 编辑器正在运行")
    print("   2. 已经打开了一个蓝图（双击打开）")
    print("   3. 蓝图编辑器窗口是激活状态")
    print("   4. BlueprintToAI 插件已编译并启用")
    print()
    
    input("按 Enter 键开始测试...")
    
    # 测试 1: GetActiveBlueprint
    test1 = test_get_active_blueprint()
    
    # 测试 2: ExtractActiveBlueprint
    test2 = test_extract_active_blueprint()
    
    # 总结
    print("\n" + "=" * 60)
    print("测试总结")
    print("=" * 60)
    print(f"GetActiveBlueprint:        {'✅ 通过' if test1 else '❌ 失败'}")
    print(f"ExtractActiveBlueprint:    {'✅ 通过' if test2 else '❌ 失败'}")
    
    if not test1 or not test2:
        print("\n❌ 测试失败！")
        print("\n可能的原因:")
        print("1. 插件还没有重新编译")
        print("   解决: 关闭 UE → 右键 .uproject → Generate VS files → 编译")
        print("2. 没有打开蓝图")
        print("   解决: 在 UE 中双击打开一个蓝图")
        print("3. 函数名称错误")
        print("   解决: 检查 C++ 代码中的 UFUNCTION 名称")
    else:
        print("\n🎉 所有测试通过！功能正常工作。")

if __name__ == "__main__":
    main()
