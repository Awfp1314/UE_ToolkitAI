#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
测试 Blueprint Extractor 插件连接
"""

import requests
import json

def test_remote_control():
    """测试 Remote Control API 是否可用"""
    print("\n" + "=" * 60)
    print("测试 1: Remote Control API")
    print("=" * 60)
    
    try:
        response = requests.get('http://127.0.0.1:30010/remote/info', timeout=5.0)
        
        if response.status_code == 200:
            print("✅ Remote Control API 可用")
            data = response.json()
            print(f"   响应: {json.dumps(data, indent=2, ensure_ascii=False)}")
            return True
        else:
            print(f"❌ Remote Control API 返回错误: {response.status_code}")
            return False
            
    except Exception as e:
        print(f"❌ 连接失败: {e}")
        print("   可能原因:")
        print("   1. UE 编辑器未运行")
        print("   2. Remote Control 插件未启用")
        print("   3. 端口不是 30010")
        return False


def test_blueprint_extractor_subsystem():
    """测试 BlueprintExtractorSubsystem 是否可用"""
    print("\n" + "=" * 60)
    print("测试 2: BlueprintExtractorSubsystem")
    print("=" * 60)
    
    subsystem_path = "/Script/BlueprintExtractor.Default__BlueprintExtractorSubsystem"
    
    try:
        # 尝试调用 GetEditorContext 函数
        request_data = {
            "objectPath": subsystem_path,
            "functionName": "GetEditorContext",
            "parameters": {},
            "generateTransaction": False
        }
        
        print(f"   Subsystem 路径: {subsystem_path}")
        print(f"   调用函数: GetEditorContext")
        
        response = requests.post(
            'http://127.0.0.1:30010/remote/object/call',
            json=request_data,
            timeout=5.0
        )
        
        print(f"   HTTP 状态码: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            print("✅ BlueprintExtractorSubsystem 可用")
            print(f"   响应: {json.dumps(result, indent=2, ensure_ascii=False)}")
            return True
        elif response.status_code == 404:
            print("❌ Subsystem 不存在 (HTTP 404)")
            print("   可能原因:")
            print("   1. Blueprint Extractor 插件未启用")
            print("   2. 插件编译失败")
            print("   3. Subsystem 路径不正确")
            print(f"   响应内容: {response.text}")
            return False
        else:
            print(f"❌ 调用失败: HTTP {response.status_code}")
            print(f"   响应: {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ 调用失败: {e}")
        return False


def test_list_objects():
    """列出所有可用的对象"""
    print("\n" + "=" * 60)
    print("测试 3: 列出可用对象")
    print("=" * 60)
    
    try:
        # 尝试获取对象列表
        response = requests.get(
            'http://127.0.0.1:30010/remote/objects',
            timeout=5.0
        )
        
        if response.status_code == 200:
            objects = response.json()
            print(f"✅ 找到 {len(objects)} 个对象")
            
            # 查找 Blueprint Extractor 相关的对象
            bp_objects = [obj for obj in objects if 'Blueprint' in obj.get('Name', '')]
            
            if bp_objects:
                print("\n   Blueprint 相关对象:")
                for obj in bp_objects[:10]:  # 只显示前10个
                    print(f"   - {obj.get('Name', 'Unknown')}")
                    print(f"     路径: {obj.get('Path', 'Unknown')}")
            else:
                print("   ⚠️  未找到 Blueprint 相关对象")
            
            return True
        else:
            print(f"❌ 获取对象列表失败: HTTP {response.status_code}")
            return False
            
    except Exception as e:
        print(f"❌ 获取对象列表失败: {e}")
        return False


def main():
    """运行所有测试"""
    print("\n🔧 Blueprint Extractor 插件连接测试\n")
    
    # 测试 1: Remote Control API
    test1 = test_remote_control()
    
    if not test1:
        print("\n❌ Remote Control API 不可用，无法继续测试")
        return
    
    # 测试 2: BlueprintExtractorSubsystem
    test2 = test_blueprint_extractor_subsystem()
    
    # 测试 3: 列出对象
    test3 = test_list_objects()
    
    # 总结
    print("\n" + "=" * 60)
    print("测试总结")
    print("=" * 60)
    print(f"Remote Control API:        {'✅ 通过' if test1 else '❌ 失败'}")
    print(f"BlueprintExtractorSubsystem: {'✅ 通过' if test2 else '❌ 失败'}")
    print(f"对象列表:                  {'✅ 通过' if test3 else '❌ 失败'}")
    print("=" * 60)
    
    if test2:
        print("\n✅ Blueprint Extractor 插件工作正常！")
        print("   现在可以在 AI 助手中使用蓝图工具了。")
    else:
        print("\n❌ Blueprint Extractor 插件未正确加载")
        print("\n📋 排查步骤:")
        print("   1. 确认插件已在 UE 编辑器中启用")
        print("   2. 检查输出日志是否有编译错误")
        print("   3. 尝试重启 UE 编辑器")
        print("   4. 检查插件依赖是否都已启用:")
        print("      - EnhancedInput")
        print("      - PropertyBindingUtils")
        print("      - StateTree")
        print("      - Web Remote Control")


if __name__ == "__main__":
    main()
