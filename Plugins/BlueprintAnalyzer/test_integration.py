#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Blueprint Analyzer 集成测试脚本

测试 Python 客户端与 UE 插件的通信
"""

import sys
import json
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from modules.ai_assistant.clients.blueprint_analyzer_client import BlueprintAnalyzerClient


def test_connection():
    """测试连接"""
    print("=" * 60)
    print("测试 1: 连接测试")
    print("=" * 60)
    
    client = BlueprintAnalyzerClient()
    
    if client.verify_connection():
        print("✅ 成功连接到 UE 编辑器")
        return True
    else:
        print("❌ 无法连接到 UE 编辑器")
        print("请确保：")
        print("  1. UE 编辑器正在运行")
        print("  2. Blueprint Analyzer 插件已启用")
        print("  3. Web Remote Control 插件已启用")
        print("  4. HTTP 服务器正在监听 http://localhost:30010")
        return False


def test_get_editor_context(client):
    """测试获取编辑器上下文"""
    print("\n" + "=" * 60)
    print("测试 2: 获取编辑器上下文")
    print("=" * 60)
    
    result = client.get_editor_context()
    
    if result.get("status") == "error":
        print(f"❌ 错误: {result.get('message')}")
        return False
    
    # 解析 JSON 响应
    data = json.loads(result.get("ReturnValue", "{}"))
    
    if data.get("success"):
        print("✅ 成功获取编辑器上下文")
        print(f"\n项目名称: {data.get('projectName')}")
        print(f"引擎版本: {data.get('engineVersion')}")
        print(f"总资产数: {data.get('totalAssets')}")
        print(f"蓝图数: {data.get('blueprintCount')}")
        print(f"Widget 蓝图数: {data.get('widgetBlueprintCount')}")
        
        open_assets = data.get('openAssets', [])
        if open_assets:
            print(f"\n当前打开的资产:")
            for asset in open_assets[:3]:
                print(f"  - {asset.get('name')} ({asset.get('class')})")
        
        return True
    else:
        print(f"❌ 失败: {data.get('error')}")
        return False


def test_extract_blueprint(client, asset_path):
    """测试提取蓝图"""
    print("\n" + "=" * 60)
    print(f"测试 3: 提取蓝图 - {asset_path}")
    print("=" * 60)
    
    result = client.extract_blueprint(asset_path)
    
    if result.get("status") == "error":
        print(f"❌ 错误: {result.get('message')}")
        return False
    
    # 解析 JSON 响应
    data = json.loads(result.get("ReturnValue", "{}"))
    
    if data.get("success"):
        print("✅ 成功提取蓝图")
        print(f"\n蓝图名称: {data.get('assetName')}")
        print(f"父类: {data.get('parentClass')}")
        
        variables = data.get('variables', [])
        print(f"\n变量数量: {len(variables)}")
        if variables:
            print("前 3 个变量:")
            for var in variables[:3]:
                print(f"  - {var.get('name')}: {var.get('type')}")
        
        functions = data.get('functions', [])
        print(f"\n函数数量: {len(functions)}")
        if functions:
            print("前 3 个函数:")
            for func in functions[:3]:
                print(f"  - {func.get('name')}()")
        
        graphs = data.get('graphs', [])
        print(f"\n图表数量: {len(graphs)}")
        if graphs:
            for graph in graphs:
                print(f"  - {graph.get('name')}: {graph.get('nodeCount')} 个节点")
        
        return True
    else:
        print(f"❌ 失败: {data.get('error')}")
        return False


def test_extract_widget_blueprint(client, asset_path):
    """测试提取 Widget 蓝图"""
    print("\n" + "=" * 60)
    print(f"测试 4: 提取 Widget 蓝图 - {asset_path}")
    print("=" * 60)
    
    result = client.extract_widget_blueprint(asset_path)
    
    if result.get("status") == "error":
        print(f"❌ 错误: {result.get('message')}")
        return False
    
    # 解析 JSON 响应
    data = json.loads(result.get("ReturnValue", "{}"))
    
    if data.get("success"):
        print("✅ 成功提取 Widget 蓝图")
        print(f"\nWidget 名称: {data.get('assetName')}")
        
        widget_tree = data.get('widgetTree', {})
        if widget_tree:
            root = widget_tree.get('root')
            if root:
                print(f"\n根组件: {root.get('name')} ({root.get('class')})")
                children = root.get('children', [])
                if children:
                    print(f"子组件数量: {len(children)}")
                    print("前 3 个子组件:")
                    for child in children[:3]:
                        print(f"  - {child.get('name')} ({child.get('class')})")
        
        return True
    else:
        print(f"❌ 失败: {data.get('error')}")
        return False


def main():
    """主测试流程"""
    print("\n🔧 Blueprint Analyzer 集成测试\n")
    
    # 测试 1: 连接
    if not test_connection():
        print("\n❌ 连接测试失败，终止测试")
        return
    
    client = BlueprintAnalyzerClient()
    
    # 测试 2: 获取编辑器上下文
    test_get_editor_context(client)
    
    # 测试 3 & 4: 提取蓝图（需要用户提供资产路径）
    print("\n" + "=" * 60)
    print("可选测试: 提取蓝图")
    print("=" * 60)
    print("\n如果要测试蓝图提取功能，请提供资产路径")
    print("示例: /Game/Blueprints/MyBlueprint")
    print("留空跳过此测试\n")
    
    blueprint_path = input("蓝图路径: ").strip()
    if blueprint_path:
        test_extract_blueprint(client, blueprint_path)
    
    widget_path = input("Widget 蓝图路径: ").strip()
    if widget_path:
        test_extract_widget_blueprint(client, widget_path)
    
    print("\n" + "=" * 60)
    print("测试完成！")
    print("=" * 60)


if __name__ == "__main__":
    main()
