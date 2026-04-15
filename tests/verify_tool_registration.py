#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
工具注册验证脚本

验证 Blueprint Extractor 工具是否正确注册到 Tools Registry。
"""

import sys
import os

# 添加项目根目录到 Python 路径
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from modules.ai_assistant.logic.tools_registry import ToolsRegistry
from core.security.feature_gate import FREE_TOOLS, PRO_TOOLS


def verify_tool_registration():
    """验证工具注册"""
    print("=" * 60)
    print("Blueprint Extractor 工具注册验证")
    print("=" * 60)
    
    # 初始化 Tools Registry
    print("\n[1] 初始化 Tools Registry...")
    try:
        registry = ToolsRegistry()
        print("✓ Tools Registry 初始化成功")
    except Exception as e:
        print(f"✗ Tools Registry 初始化失败: {e}")
        return False
    
    # 检查注册的工具数量
    print("\n[2] 检查注册的工具...")
    all_tools = list(registry.tools.keys())
    print(f"总注册工具数: {len(all_tools)}")
    
    # 检查免费工具
    print("\n[3] 验证免费工具注册...")
    registered_free_tools = [name for name in all_tools if name in FREE_TOOLS]
    print(f"已注册免费工具: {len(registered_free_tools)}/{len(FREE_TOOLS)}")
    
    missing_free_tools = FREE_TOOLS - set(registered_free_tools)
    if missing_free_tools:
        print(f"✗ 缺失的免费工具: {missing_free_tools}")
    else:
        print("✓ 所有免费工具已注册")
    
    # 检查付费工具
    print("\n[4] 验证付费工具注册...")
    registered_pro_tools = [name for name in all_tools if name in PRO_TOOLS]
    print(f"已注册付费工具: {len(registered_pro_tools)}/{len(PRO_TOOLS)}")
    
    # 至少应该注册 10 个核心付费工具
    core_pro_tools = {
        "CreateBlueprint",
        "ModifyBlueprintMembers",
        "AddBlueprintVariable",
        "AddBlueprintFunction",
        "CreateWidgetBlueprint",
        "ModifyWidget",
        "SaveAssets",
        "ImportTexture",
        "StartPIE",
        "StopPIE"
    }
    
    registered_core_pro_tools = [name for name in all_tools if name in core_pro_tools]
    print(f"已注册核心付费工具: {len(registered_core_pro_tools)}/{len(core_pro_tools)}")
    
    missing_core_pro_tools = core_pro_tools - set(registered_core_pro_tools)
    if missing_core_pro_tools:
        print(f"✗ 缺失的核心付费工具: {missing_core_pro_tools}")
    else:
        print("✓ 所有核心付费工具已注册")
    
    # 检查工具定义完整性
    print("\n[5] 验证工具定义完整性...")
    ue_tools = registered_free_tools + registered_pro_tools
    
    issues = []
    for tool_name in ue_tools:
        tool = registry.tools[tool_name]
        
        # 检查必需字段
        if not tool.name:
            issues.append(f"{tool_name}: 缺少 name")
        if not tool.description:
            issues.append(f"{tool_name}: 缺少 description")
        if not tool.parameters:
            issues.append(f"{tool_name}: 缺少 parameters")
        if not tool.function:
            issues.append(f"{tool_name}: 缺少 function")
        
        # 检查描述是否为中文
        if tool.description and not any('\u4e00' <= char <= '\u9fff' for char in tool.description):
            issues.append(f"{tool_name}: description 不是中文")
        
        # 检查参数 schema 是否有效
        if tool.parameters:
            if not isinstance(tool.parameters, dict):
                issues.append(f"{tool_name}: parameters 不是 dict")
            elif "type" not in tool.parameters:
                issues.append(f"{tool_name}: parameters 缺少 type 字段")
    
    if issues:
        print(f"✗ 发现 {len(issues)} 个问题:")
        for issue in issues[:10]:  # 只显示前 10 个
            print(f"  - {issue}")
    else:
        print("✓ 所有工具定义完整")
    
    # 检查工具调度流程
    print("\n[6] 验证工具调度流程...")
    
    # 测试免费工具（应该允许）
    test_free_tool = "ExtractBlueprint"
    if test_free_tool in registry.tools:
        print(f"测试免费工具: {test_free_tool}")
        # 注意：这里不实际调用工具，只检查权限
        permission = registry.feature_gate.check_tool_permission(test_free_tool)
        if permission["allowed"]:
            print(f"✓ {test_free_tool} 权限检查通过（免费工具）")
        else:
            print(f"✗ {test_free_tool} 权限检查失败: {permission['message']}")
    
    # 测试付费工具（未激活时应该被阻止）
    test_pro_tool = "CreateBlueprint"
    if test_pro_tool in registry.tools:
        print(f"测试付费工具: {test_pro_tool}")
        permission = registry.feature_gate.check_tool_permission(test_pro_tool)
        if not permission["allowed"] and permission["locked"]:
            print(f"✓ {test_pro_tool} 正确被阻止（未激活）")
            print(f"  错误消息: {permission['message'][:50]}...")
        else:
            print(f"✗ {test_pro_tool} 应该被阻止但未被阻止")
    
    # 总结
    print("\n" + "=" * 60)
    print("验证总结")
    print("=" * 60)
    
    total_ue_tools = len(registered_free_tools) + len(registered_core_pro_tools)
    print(f"已注册 UE 工具总数: {total_ue_tools}")
    print(f"  - 免费工具: {len(registered_free_tools)}")
    print(f"  - 核心付费工具: {len(registered_core_pro_tools)}")
    
    # 检查是否满足最低要求（至少 20 个核心工具）
    if total_ue_tools >= 20:
        print(f"\n✓ 满足最低要求（至少 20 个核心工具）")
        success = True
    else:
        print(f"\n✗ 不满足最低要求（需要至少 20 个核心工具，当前 {total_ue_tools} 个）")
        success = False
    
    if not missing_free_tools and not missing_core_pro_tools and not issues:
        print("✓ 所有验证通过")
        success = True
    else:
        print("✗ 存在问题需要修复")
        success = False
    
    return success


if __name__ == "__main__":
    success = verify_tool_registration()
    sys.exit(0 if success else 1)
