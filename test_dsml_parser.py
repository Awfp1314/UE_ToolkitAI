#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""测试 DSML 解析器"""

import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from modules.ai_assistant.logic.dsml_parser import DSMLParser

# 测试文本（从截图中提取）
test_text = '''我来帮您查看当前在 UE 编辑器中打开的蓝图。✅ 可以看到！当前在 UE 编辑器中打开的是 BP_ThirdPersonCharacter 蓝图，位于路径：/Game/ThirdPerson/Blueprints/BP_ThirdPersonCharacter-BP_ThirdPersonCharacter

现在我来获取这个蓝图的详细构信息：

<|DSML|function_calls> <|DSML|invoke name="GetBlueprintDetails"> <|DSML|function_args> {"assetPath": "/Game/ThirdPerson/Blueprints/BP_ThirdPersonCharacter.BP_ThirdPersonCharacter"} </|DSML|function_args> </|DSML|invoke> </|DSML|function_calls>'''

print("🔍 测试 DSML 解析器")
print("=" * 80)

# 测试 1: 检测 DSML
print("\n测试 1: 检测 DSML 标记")
contains = DSMLParser.contains_dsml(test_text)
print(f"包含 DSML: {contains}")

# 测试 2: 解析工具调用
print("\n测试 2: 解析工具调用")
tool_calls = DSMLParser.parse_tool_calls(test_text)
if tool_calls:
    print(f"找到 {len(tool_calls)} 个工具调用:")
    for i, tc in enumerate(tool_calls):
        print(f"\n工具调用 #{i+1}:")
        print(f"  ID: {tc['id']}")
        print(f"  类型: {tc['type']}")
        print(f"  函数名: {tc['function']['name']}")
        print(f"  参数: {tc['function']['arguments']}")
else:
    print("❌ 未找到工具调用")

# 测试 3: 移除 DSML 标记
print("\n测试 3: 移除 DSML 标记")
clean_text = DSMLParser.remove_dsml_tags(test_text)
print(f"清理后的文本:\n{clean_text}")

print("\n" + "=" * 80)
print("✅ 测试完成")
