#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
BlueprintToAI - Complete Test Suite for UE 5.6
测试所有核心功能
"""

import requests
import json
import time
from typing import Dict, Any

class BlueprintToAITester:
    """BlueprintToAI 测试类"""
    
    def __init__(self, host="127.0.0.1", port=30010):
        self.base_url = f"http://{host}:{port}"
        self.subsystem_path = "/Script/BlueprintToAI.Default__BlueprintToAISubsystem"
        self.test_results = []
    
    def call_function(self, function_name: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """调用 UE 函数"""
        url = f"{self.base_url}/remote/object/call"
        payload = {
            "objectPath": self.subsystem_path,
            "functionName": function_name,
            "parameters": parameters
        }
        
        try:
            response = requests.post(url, json=payload, timeout=10)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            return {"success": False, "error": str(e)}
    
    def test_connection(self) -> bool:
        """测试 1: 连接测试"""
        print("\n" + "="*60)
        print("测试 1: Remote Control API 连接")
        print("="*60)
        
        try:
            response = requests.get(f"{self.base_url}/remote/info", timeout=5)
            if response.status_code == 200:
                info = response.json()
                print(f"✅ 连接成功")
                print(f"   服务器: {info.get('serverName', 'Unknown')}")
                print(f"   版本: {info.get('serverVersion', 'Unknown')}")
                self.test_results.append(("连接测试", True, ""))
                return True
            else:
                print(f"❌ 连接失败: HTTP {response.status_code}")
                self.test_results.append(("连接测试", False, f"HTTP {response.status_code}"))
                return False
        except Exception as e:
            print(f"❌ 连接失败: {e}")
            self.test_results.append(("连接测试", False, str(e)))
            return False
    
    def test_extract_blueprint(self, asset_path="/Game/ThirdPerson/Blueprints/BP_ThirdPersonCharacter") -> bool:
        """测试 2: 提取蓝图"""
        print("\n" + "="*60)
        print("测试 2: 提取蓝图")
        print("="*60)
        print(f"资产路径: {asset_path}")
        
        result = self.call_function("ExtractBlueprint", {
            "AssetPath": asset_path,
            "Scope": "Compact"
        })
        
        if result.get("success"):
            blueprint = result.get("blueprint", {})
            print(f"✅ 提取成功")
            print(f"   名称: {blueprint.get('name', 'Unknown')}")
            print(f"   父类: {blueprint.get('parentClass', 'Unknown')}")
            print(f"   图表数: {len(blueprint.get('graphs', []))}")
            print(f"   变量数: {len(blueprint.get('variables', []))}")
            self.test_results.append(("提取蓝图", True, ""))
            return True
        else:
            error = result.get("error", "Unknown error")
            print(f"❌ 提取失败: {error}")
            self.test_results.append(("提取蓝图", False, error))
            return False
    
    def test_create_blueprint(self, asset_path="/Game/BP_TestActor") -> bool:
        """测试 3: 创建蓝图"""
        print("\n" + "="*60)
        print("测试 3: 创建蓝图")
        print("="*60)
        print(f"资产路径: {asset_path}")
        
        result = self.call_function("CreateBlueprint", {
            "AssetPath": asset_path,
            "ParentClass": "/Script/Engine.Actor",
            "GraphDSL": "",
            "PayloadJson": "{}"
        })
        
        if result.get("success"):
            print(f"✅ 创建成功")
            print(f"   消息: {result.get('message', '')}")
            self.test_results.append(("创建蓝图", True, ""))
            return True
        else:
            error = result.get("error", "Unknown error")
            print(f"❌ 创建失败: {error}")
            self.test_results.append(("创建蓝图", False, error))
            return False
    
    def test_add_variable(self, asset_path="/Game/BP_TestActor") -> bool:
        """测试 4: 添加变量"""
        print("\n" + "="*60)
        print("测试 4: 添加变量")
        print("="*60)
        print(f"资产路径: {asset_path}")
        
        result = self.call_function("ModifyBlueprint", {
            "AssetPath": asset_path,
            "Operation": "add_variable",
            "PayloadJson": json.dumps({
                "name": "Health",
                "type": "float"
            })
        })
        
        if result.get("success"):
            print(f"✅ 添加变量成功")
            print(f"   消息: {result.get('message', '')}")
            self.test_results.append(("添加变量", True, ""))
            return True
        else:
            error = result.get("error", "Unknown error")
            print(f"❌ 添加变量失败: {error}")
            self.test_results.append(("添加变量", False, error))
            return False
    
    def test_reparent(self, asset_path="/Game/BP_TestActor") -> bool:
        """测试 5: 更改父类"""
        print("\n" + "="*60)
        print("测试 5: 更改父类")
        print("="*60)
        print(f"资产路径: {asset_path}")
        
        result = self.call_function("ModifyBlueprint", {
            "AssetPath": asset_path,
            "Operation": "reparent",
            "PayloadJson": json.dumps({
                "parentClassPath": "/Script/Engine.Pawn"
            })
        })
        
        if result.get("success"):
            print(f"✅ 更改父类成功")
            print(f"   消息: {result.get('message', '')}")
            self.test_results.append(("更改父类", True, ""))
            return True
        else:
            error = result.get("error", "Unknown error")
            print(f"❌ 更改父类失败: {error}")
            self.test_results.append(("更改父类", False, error))
            return False
    
    def test_save_blueprint(self, asset_paths=["/Game/BP_TestActor"]) -> bool:
        """测试 6: 保存蓝图"""
        print("\n" + "="*60)
        print("测试 6: 保存蓝图")
        print("="*60)
        print(f"资产路径: {asset_paths}")
        
        result = self.call_function("SaveBlueprints", {
            "AssetPaths": asset_paths
        })
        
        if result.get("success"):
            saved_count = result.get("savedCount", 0)
            failed_count = result.get("failedCount", 0)
            print(f"✅ 保存完成")
            print(f"   成功: {saved_count}")
            print(f"   失败: {failed_count}")
            self.test_results.append(("保存蓝图", True, ""))
            return True
        else:
            error = result.get("error", "Unknown error")
            print(f"❌ 保存失败: {error}")
            self.test_results.append(("保存蓝图", False, error))
            return False
    
    def test_extract_scopes(self, asset_path="/Game/ThirdPerson/Blueprints/BP_ThirdPersonCharacter") -> bool:
        """测试 7: 不同提取模式"""
        print("\n" + "="*60)
        print("测试 7: 不同提取模式")
        print("="*60)
        
        scopes = ["Minimal", "Compact", "Full"]
        all_success = True
        
        for scope in scopes:
            print(f"\n测试 {scope} 模式...")
            start_time = time.time()
            
            result = self.call_function("ExtractBlueprint", {
                "AssetPath": asset_path,
                "Scope": scope
            })
            
            elapsed = time.time() - start_time
            
            if result.get("success"):
                # 计算 JSON 大小
                json_str = json.dumps(result)
                size_kb = len(json_str) / 1024
                print(f"   ✅ {scope}: {elapsed:.2f}s, {size_kb:.1f} KB")
            else:
                print(f"   ❌ {scope}: 失败")
                all_success = False
        
        self.test_results.append(("提取模式测试", all_success, ""))
        return all_success
    
    def print_summary(self):
        """打印测试总结"""
        print("\n" + "="*60)
        print("测试总结")
        print("="*60)
        
        total = len(self.test_results)
        passed = sum(1 for _, success, _ in self.test_results if success)
        failed = total - passed
        
        print(f"\n总计: {total} 个测试")
        print(f"通过: {passed} ✅")
        print(f"失败: {failed} ❌")
        
        if failed > 0:
            print("\n失败的测试:")
            for name, success, error in self.test_results:
                if not success:
                    print(f"  ❌ {name}: {error}")
        
        print("\n" + "="*60)
        if failed == 0:
            print("🎉 所有测试通过！插件已完全适配 UE 5.6")
        else:
            print("⚠️  部分测试失败，请检查错误信息")
        print("="*60)
        
        return failed == 0

def main():
    """主函数"""
    print("="*60)
    print("BlueprintToAI - UE 5.6 完整测试套件")
    print("="*60)
    print("\n请确保:")
    print("1. UE 5.6 编辑器正在运行")
    print("2. Remote Control Web Server 已启用 (端口 30010)")
    print("3. BlueprintToAI 插件已加载")
    print("\n按 Enter 开始测试...")
    input()
    
    tester = BlueprintToAITester()
    
    # 运行所有测试
    if not tester.test_connection():
        print("\n❌ 无法连接到 UE 编辑器，测试终止")
        return
    
    # 测试提取（使用默认的 ThirdPerson 蓝图）
    tester.test_extract_blueprint()
    
    # 测试创建
    if tester.test_create_blueprint():
        # 只有创建成功才继续测试修改
        time.sleep(0.5)  # 等待资产注册
        tester.test_add_variable()
        time.sleep(0.5)
        tester.test_reparent()
        time.sleep(0.5)
        tester.test_save_blueprint()
    
    # 测试不同提取模式
    tester.test_extract_scopes()
    
    # 打印总结
    success = tester.print_summary()
    
    if success:
        print("\n✅ 插件已完全适配 UE 5.6，可以开始 Phase 2 开发")
    else:
        print("\n⚠️  请修复失败的测试后再继续")

if __name__ == "__main__":
    main()
