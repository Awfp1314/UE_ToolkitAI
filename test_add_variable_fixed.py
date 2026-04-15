#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
测试修复后的添加变量功能
"""

import requests
import json

BASE_URL = "http://127.0.0.1:30010"

def test_add_variable(asset_path, var_name, var_type, default_value=None):
    """测试添加变量"""
    print(f"\n{'='*60}")
    print(f"测试添加变量: {var_name} ({var_type})", end="")
    if default_value is not None:
        print(f" = {default_value}")
    else:
        print()
    print(f"{'='*60}")
    
    payload = {
        "name": var_name,
        "type": var_type
    }
    
    if default_value is not None:
        payload["defaultValue"] = str(default_value)
    
    data = {
        "objectPath": "/Script/BlueprintToAI.Default__BlueprintToAISubsystem",
        "functionName": "ModifyBlueprint",
        "parameters": {
            "AssetPath": asset_path,
            "Operation": "add_variable",
            "PayloadJson": json.dumps(payload)
        },
        "generateTransaction": True
    }
    
    try:
        response = requests.put(
            f"{BASE_URL}/remote/object/call",
            json=data,
            headers={"Content-Type": "application/json"}
        )
        
        print(f"状态码: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            print(f"响应: {json.dumps(result, indent=2, ensure_ascii=False)}")
            
            # 解析返回值
            if "ReturnValue" in result:
                return_value = json.loads(result["ReturnValue"])
                if return_value.get("success"):
                    print(f"✓ 成功: {return_value.get('data', {}).get('message', 'OK')}")
                    return True
                else:
                    print(f"✗ 失败: {return_value.get('error', 'Unknown error')}")
                    return False
        else:
            print(f"✗ HTTP错误: {response.text}")
            return False
            
    except Exception as e:
        print(f"✗ 异常: {e}")
        return False

def main():
    """主测试流程"""
    asset_path = "/Game/NewBlueprint"
    
    # 测试各种类型（包含默认值）
    test_cases = [
        ("Speed", "float", 1.0),
        ("MaxHealth", "int", 100),
        ("IsAlive", "bool", "true"),
        ("PlayerName", "string", "Player"),
        ("Position", "vector", None),
        ("Rotation", "rotator", None),
        ("MyTransform", "transform", None),
        ("TintColor", "color", None),
        ("Score", "int64", None),
        ("TeamID", "byte", None),
    ]
    
    print("\n" + "="*60)
    print("开始测试添加变量功能（修复版）")
    print("="*60)
    
    results = []
    for var_name, var_type, default_value in test_cases:
        success = test_add_variable(asset_path, var_name, var_type, default_value)
        results.append((var_name, var_type, default_value, success))
    
    # 汇总结果
    print("\n" + "="*60)
    print("测试结果汇总")
    print("="*60)
    
    success_count = sum(1 for _, _, _, success in results if success)
    total_count = len(results)
    
    for var_name, var_type, default_value, success in results:
        status = "✓" if success else "✗"
        default_str = f" = {default_value}" if default_value is not None else ""
        print(f"{status} {var_name:20s} ({var_type:10s}){default_str}")
    
    print(f"\n成功: {success_count}/{total_count}")
    
    if success_count == total_count:
        print("\n✓ 所有测试通过！现在可以保存蓝图了。")
        print("\n提示：在UE编辑器中打开蓝图查看新添加的变量")
    else:
        print("\n✗ 部分测试失败，请检查错误信息")

if __name__ == "__main__":
    main()
