#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
测试 GetActiveBlueprint 工具
"""

import requests
import json

def test_get_active_blueprint():
    """测试获取当前活动蓝图"""
    print("\n" + "=" * 60)
    print("测试 GetActiveBlueprint")
    print("=" * 60)
    
    subsystem_path = "/Script/BlueprintExtractor.Default__BlueprintExtractorSubsystem"
    
    try:
        request_data = {
            "objectPath": subsystem_path,
            "functionName": "GetActiveBlueprint",
            "parameters": {},
            "generateTransaction": False
        }
        
        print(f"\n发送请求...")
        print(f"  Subsystem: {subsystem_path}")
        print(f"  Function: GetActiveBlueprint")
        
        response = requests.put(
            'http://127.0.0.1:30010/remote/object/call',
            json=request_data,
            timeout=5.0
        )
        
        print(f"\nHTTP 状态码: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            print("\n✅ 调用成功")
            print(f"\n完整响应:")
            print(json.dumps(result, indent=2, ensure_ascii=False))
            
            # 解析 ReturnValue
            if "ReturnValue" in result:
                return_value = result["ReturnValue"]
                print(f"\nReturnValue 类型: {type(return_value)}")
                print(f"ReturnValue 内容: {return_value}")
                
                # 尝试解析为 JSON
                try:
                    parsed = json.loads(return_value)
                    print(f"\n解析后的 JSON:")
                    print(json.dumps(parsed, indent=2, ensure_ascii=False))
                except:
                    print(f"\nReturnValue 不是 JSON 格式")
            
            return True
        else:
            print(f"\n❌ 调用失败")
            print(f"响应: {response.text}")
            return False
            
    except Exception as e:
        print(f"\n❌ 异常: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    print("\n🔍 测试 GetActiveBlueprint 工具\n")
    print("请确保:")
    print("1. UE 编辑器正在运行")
    print("2. 已经打开了一个蓝图（双击打开）")
    print("3. Blueprint Extractor 插件已启用")
    
    test_get_active_blueprint()
