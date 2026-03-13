# -*- coding: utf-8 -*-
"""
授权重置脚本
清除本地所有授权数据 + 缓存 + 服务器端试用记录，恢复到全新状态。
用法: python reset_license.py
"""

import json
import os
import sys
import urllib.error
import urllib.request

# 添加项目根目录
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# 绕过系统代理（本地开发环境有代理，会导致 SSL 握手超时）
os.environ.pop("HTTP_PROXY", None)
os.environ.pop("HTTPS_PROXY", None)
os.environ.pop("http_proxy", None)
os.environ.pop("https_proxy", None)
os.environ.pop("ALL_PROXY", None)
os.environ.pop("all_proxy", None)

# 安装无代理的 opener 作为全局默认
_no_proxy_handler = urllib.request.ProxyHandler({})
_opener = urllib.request.build_opener(_no_proxy_handler)
urllib.request.install_opener(_opener)

APPDATA_DIR = os.path.join(os.environ.get("APPDATA", ""), "ue_toolkit")

# 需要清除的本地文件
_FILES_TO_DELETE = [
    os.path.join(APPDATA_DIR, "license.dat"),           # 授权数据
    os.path.join(APPDATA_DIR, ".hw_cache"),              # 硬件指纹缓存
    os.path.join(APPDATA_DIR, ".server_url_cache"),      # 服务器URL缓存
    os.path.join(os.environ.get("USERPROFILE", ""), ".ue_toolkit_license"),  # 隐藏授权文件
]

# 注册表
_REG_KEY = r"Software\UEToolkit"
_REG_VALUE = "License"


def _delete_files():
    """删除本地授权文件和缓存"""
    for path in _FILES_TO_DELETE:
        try:
            if os.path.exists(path):
                os.remove(path)
                print(f"  [OK] 已删除: {path}")
            else:
                print(f"  [--] 不存在: {path}")
        except Exception as e:
            print(f"  [!!] 删除失败 {path}: {e}")


def _delete_registry():
    """删除注册表中的授权数据"""
    if sys.platform != "win32":
        print("  [--] 非 Windows，跳过注册表")
        return
    try:
        import winreg
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, _REG_KEY, 0, winreg.KEY_SET_VALUE)
        winreg.DeleteValue(key, _REG_VALUE)
        winreg.CloseKey(key)
        print(f"  [OK] 已删除: 注册表 HKCU\\{_REG_KEY}\\{_REG_VALUE}")
    except FileNotFoundError:
        print(f"  [--] 不存在: 注册表 HKCU\\{_REG_KEY}\\{_REG_VALUE}")
    except Exception as e:
        print(f"  [!!] 删除注册表失败: {e}")


def _reset_server_trial():
    """清除服务器端试用记录和用户统计（需要管理员认证）"""
    try:
        from core.security.machine_id import MachineID
        from core.server_config import get_server_base_url
        from core.update_checker import UpdateChecker

        # 创建无代理 opener（确保所有请求都绕过代理）
        no_proxy_handler = urllib.request.ProxyHandler({})
        opener = urllib.request.build_opener(no_proxy_handler)

        base_url = get_server_base_url()
        machine_id = MachineID().get_machine_id()
        
        # 获取 user_id（用于清除用户统计）
        # 注意：必须从 UpdateChecker 获取，因为启动上报用的是它的 user_id
        # （存储在 ~/.ue_toolkit/update_config.json），
        # 而非 ConfigManager 的 user_id（存储在 ~/.ue_toolkit/config.json）
        update_checker = UpdateChecker()
        user_id = update_checker.config.get('user_id')

        # 先登录获取 admin token
        import getpass
        password = getpass.getpass("  请输入管理员密码（跳过请直接回车）: ")
        if not password:
            print("  [--] 跳过服务器端记录清除")
            return

        # 登录
        login_data = json.dumps({"password": password}).encode("utf-8")
        login_req = urllib.request.Request(
            f"{base_url}/api/v2/auth/login",
            data=login_data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with opener.open(login_req, timeout=5) as resp:
            login_result = json.loads(resp.read().decode("utf-8"))

        token = login_result.get("token")
        if not token:
            print("  [!!] 管理员登录失败，密码错误")
            return

        auth_headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {token}",
        }

        # 清除试用记录
        url = f"{base_url}/api/v2/trial/reset"
        data = json.dumps({"machine_id": machine_id}).encode("utf-8")
        req = urllib.request.Request(url, data=data, headers=auth_headers, method="POST")
        try:
            with opener.open(req, timeout=5) as resp:
                result = json.loads(resp.read().decode("utf-8"))
                if result.get("success"):
                    print("  [OK] 已清除: 服务器端试用记录")
                else:
                    print(f"  [!!] 服务器返回失败: {result}")
        except Exception as e:
            print(f"  [!!] 清除试用记录失败: {e}")

        # 清除该用户的统计数据和启动事件
        user_cleared = False
        if user_id:
            url = f"{base_url}/api/v2/admin/users/{user_id}"
            req = urllib.request.Request(url, headers=auth_headers, method="DELETE")
            try:
                with opener.open(req, timeout=5) as resp:
                    result = json.loads(resp.read().decode("utf-8"))
                    print(f"  [OK] 已清除: 用户统计记录 (user_id={user_id[:8]}...)")
                    user_cleared = True
            except urllib.error.HTTPError as e:
                if e.code == 404:
                    print(f"  [--] 未找到 user_id={user_id[:8]}... 的记录，尝试清除所有用户数据...")
                else:
                    print(f"  [!!] 清除用户统计失败: HTTP {e.code}")
            except Exception as e:
                print(f"  [!!] 清除用户统计失败: {e}")

        # 如果按 user_id 没清掉（404 或无 user_id），提示是否清除全部
        if not user_cleared:
            answer = input("  是否清除服务器上所有用户统计数据？(y/N): ").strip().lower()
            if answer == 'y':
                url = f"{base_url}/api/v2/admin/users"
                req = urllib.request.Request(url, headers=auth_headers, method="DELETE")
                try:
                    with opener.open(req, timeout=5) as resp:
                        result = json.loads(resp.read().decode("utf-8"))
                        stats = result.get('stats_deleted', '?')
                        events = result.get('events_deleted', '?')
                        print(f"  [OK] 已清除所有用户数据: {stats}条统计, {events}条事件")
                except Exception as e:
                    print(f"  [!!] 清除所有用户数据失败: {e}")
            else:
                print("  [--] 跳过用户统计清除")
    except Exception as e:
        print(f"  [!!] 清除服务器试用记录失败: {e}")


def main():
    print("=" * 50)
    print("  UE Toolkit 授权重置工具")
    print("=" * 50)
    print()

    print("[1/3] 清除本地授权文件和缓存...")
    _delete_files()
    print()

    print("[2/3] 清除注册表授权数据...")
    _delete_registry()
    print()

    print("[3/3] 清除服务器端试用记录...")
    _reset_server_trial()
    print()

    print("=" * 50)
    print("  重置完成，下次启动将进入全新授权流程")
    print("=" * 50)


if __name__ == "__main__":
    main()
