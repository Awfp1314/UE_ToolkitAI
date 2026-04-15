#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
诊断 Blueprint Extractor Subsystem 路径
"""

import requests
import json

def test_describe_object(object_path):
    """测试描述对象"""
    try:
        request_data = {
            "objectPath": object_path
        }
        
        response = requests.put(
            'http://127.0.0.1:30010/remote/object/describe',
            json=request_data,
            timeout=5.0
        )
        
        if response.status_code == 200:
            return response.json()
        else:
            return None
            
    except Exception as e:
        return None


def search_subsystems():
    """搜索所有 Subsystem"""
    print("\n" + "=" * 60)
    print("搜索 Editor Subsystems")
    print("=" * 60)
    
    # 尝试不同的路径格式
    possible_paths = [
        "/Script/BlueprintExtractor.Default__BlueprintExtractorSubsystem",
        "/Script/BlueprintExtractor.BlueprintExtractorSubsystem",
        "/Script/BlueprintExtractor.BlueprintExtractorSubsystem_0",
        "BlueprintExtractorSubsystem",
        "/Engine/Transient.BlueprintExtractorSubsystem",
        "/Script/BlueprintExtractor.Default__BlueprintExtractorSubsystem_0",
    ]
    
    print("\n尝试不同的 Subsystem 路径格式:\n")
    
    for path in possible_paths:
        print(f"测试: {path}")
        result = test_describe_object(path)
        
        if result:
            print(f"  ✅ 找到了！")
            print(f"  详情: {json.dumps(result, indent=4, ensure_ascii=False)}")
            return path
        else:
            print(f"  ❌ 不存在")
    
    print("\n⚠️  未找到 BlueprintExtractorSubsystem")
    return None


def test_call_function(subsystem_path):
    """测试调用函数"""
    print("\n" + "=" * 60)
    print(f"测试调用函数: {subsystem_path}")
    print("=" * 60)
    
    try:
        request_data = {
            "objectPath": subsystem_path,
            "functionName": "GetEditorContext",
            "parameters": {},
            "generateTransaction": False
        }
        
        response = requests.put(
            'http://127.0.0.1:30010/remote/object/call',
            json=request_data,
            timeout=5.0
        )
        
        print(f"HTTP 状态码: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            print("✅ 函数调用成功")
            print(f"响应: {json.dumps(result, indent=2, ensure_ascii=False)}")
            return True
        else:
            print(f"❌ 函数调用失败")
            print(f"响应: {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ 异常: {e}")
        return False


def check_plugin_loaded():
    """检查插件是否加载"""
    print("\n" + "=" * 60)
    print("检查 Blueprint Extractor 插件状态")
    print("=" * 60)
    
    print("\n请在 UE 编辑器中检查:")
    print("1. 编辑 → 插件 → 搜索 'Blueprint Extractor'")
    print("2. 确认插件已启用（勾选框打勾）")
    print("3. 查看输出日志（窗口 → 开发者工具 → 输出日志）")
    print("4. 搜索日志中的 'BlueprintExtractor' 关键词")
    print("\n如果插件加载成功，应该能看到类似:")
    print("   LogBlueprintExtractor: BlueprintExtractor module has been loaded")
    print("   LogBlueprintExtractor: BlueprintExtractorSubsystem initialized")


def main():
    print("\n🔍 Blueprint Extractor Subsystem 诊断工具\n")
    
    # 搜索 Subsystem
    subsystem_path = search_subsystems()
    
    if subsystem_path:
        print(f"\n✅ 找到 Subsystem: {subsystem_path}")
        
        # 测试调用函数
        test_call_function(subsystem_path)
        
        print("\n" + "=" * 60)
        print("✅ 诊断完成 - Subsystem 工作正常")
        print("=" * 60)
        print(f"\n请更新代码中的 Subsystem 路径为:")
        print(f"   {subsystem_path}")
        
    else:
        print("\n" + "=" * 60)
        print("❌ 诊断完成 - 未找到 Subsystem")
        print("=" * 60)
        
        check_plugin_loaded()
        
        print("\n📋 可能的问题:")
        print("1. 插件未正确编译")
        print("   - 检查 UE 编辑器的输出日志是否有编译错误")
        print("   - 尝试: 工具 → 刷新 Visual Studio 项目")
        print("   - 重新编译项目")
        print("\n2. 插件未启用")
        print("   - 编辑 → 插件 → 搜索 'Blueprint Extractor'")
        print("   - 确保勾选启用")
        print("   - 重启编辑器")
        print("\n3. 依赖插件未启用")
        print("   - EnhancedInput")
        print("   - PropertyBindingUtils")
        print("   - StateTree")
        print("   - Web Remote Control")
        print("\n4. 插件源码不完整")
        print("   - 检查 Plugins/BlueprintExtractor/Source/ 目录")
        print("   - 确保包含 .cpp 和 .h 文件")


if __name__ == "__main__":
    main()
