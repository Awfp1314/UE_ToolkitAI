#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
API 诊断脚本
用于测试 API 连接和获取可用模型列表
"""

import requests
import json
import sys

def test_api(api_url, api_key):
    """测试 API 连接并获取模型列表"""
    
    print(f"测试 API: {api_url}")
    print(f"API Key: {api_key[:20]}...")
    print()
    
    # 尝试获取模型列表
    models_url = api_url.replace('/chat/completions', '/models')
    
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    
    try:
        print("正在获取模型列表...")
        response = requests.get(models_url, headers=headers, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            models = data.get('data', [])
            
            print(f"\n✅ 成功！找到 {len(models)} 个模型：\n")
            
            for model in models[:20]:  # 只显示前20个
                model_id = model.get('id', 'unknown')
                print(f"  - {model_id}")
            
            if len(models) > 20:
                print(f"\n  ... 还有 {len(models) - 20} 个模型")
                
        else:
            print(f"\n❌ 获取模型列表失败 ({response.status_code})")
            print(f"响应: {response.text}")
            
    except Exception as e:
        print(f"\n❌ 请求失败: {e}")
    
    # 测试一个简单的聊天请求
    print("\n" + "="*60)
    print("测试聊天请求...")
    
    test_payload = {
        "model": "deepseek-chat",  # 使用常见的模型名
        "messages": [{"role": "user", "content": "Hello"}],
        "max_tokens": 10
    }
    
    try:
        response = requests.post(api_url, headers=headers, json=test_payload, timeout=10)
        
        if response.status_code == 200:
            print("\n✅ 聊天请求成功！")
        else:
            print(f"\n❌ 聊天请求失败 ({response.status_code})")
            print(f"响应: {response.text}")
            
            # 尝试其他常见模型名
            print("\n尝试其他模型名...")
            for model_name in ["gpt-3.5-turbo", "Qwen/Qwen2.5-7B-Instruct", "deepseek-ai/DeepSeek-V2.5"]:
                test_payload["model"] = model_name
                response = requests.post(api_url, headers=headers, json=test_payload, timeout=10)
                if response.status_code == 200:
                    print(f"  ✅ {model_name} 可用")
                else:
                    print(f"  ❌ {model_name} 不可用")
                    
    except Exception as e:
        print(f"\n❌ 请求失败: {e}")


if __name__ == "__main__":
    # 从配置文件读取
    import os
    config_path = os.path.expanduser("~/AppData/Roaming/ue_toolkit/user_data/configs/ai_assistant/ai_assistant_config.json")
    
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
            
        api_settings = config.get('api_settings', {})
        api_url = api_settings.get('api_url')
        api_key = api_settings.get('api_key')
        
        if not api_url or not api_key:
            print("❌ 配置文件中缺少 API URL 或 API Key")
            sys.exit(1)
            
        test_api(api_url, api_key)
        
    except FileNotFoundError:
        print(f"❌ 配置文件不存在: {config_path}")
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"❌ 配置文件 JSON 格式错误: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"❌ 错误: {e}")
        sys.exit(1)
