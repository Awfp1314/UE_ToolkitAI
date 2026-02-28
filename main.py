    # -*- coding: utf-8 -*-

import sys
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# 导入 AppBootstrap
from core.bootstrap import AppBootstrap


def _reset_license():
    """清除本地授权数据（3个存储位置）+ 服务器端试用记录"""
    import os
    appdata = os.path.join(os.environ.get("APPDATA", ""), "ue_toolkit", "license.dat")
    hidden = os.path.join(os.environ.get("USERPROFILE", ""), ".ue_toolkit_license")

    for path in [appdata, hidden]:
        try:
            if os.path.exists(path):
                os.remove(path)
                print(f"已删除: {path}")
        except Exception as e:
            print(f"删除失败 {path}: {e}")

    if sys.platform == "win32":
        try:
            import winreg
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\UEToolkit", 0, winreg.KEY_SET_VALUE)
            winreg.DeleteValue(key, "License")
            winreg.CloseKey(key)
            print("已删除: 注册表 HKCU\\Software\\UEToolkit\\License")
        except FileNotFoundError:
            pass
        except Exception as e:
            print(f"删除注册表失败: {e}")

    # 同时清除服务器端试用记录（需要管理员认证）
    try:
        from core.security.machine_id import MachineID
        from core.security.license_manager import _get_server_url
        import json
        import urllib.request
        import getpass

        password = getpass.getpass("请输入管理员密码以清除服务器端试用记录（跳过请直接回车）: ")
        if password:
            base_url = _get_server_url()
            # 登录
            login_data = json.dumps({"password": password}).encode("utf-8")
            login_req = urllib.request.Request(
                f"{base_url}/api/v2/auth/login",
                data=login_data,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(login_req, timeout=5) as resp:
                login_result = json.loads(resp.read().decode("utf-8"))
            token = login_result.get("token")
            if token:
                machine_id = MachineID().get_machine_id()
                url = f"{base_url}/api/v2/trial/reset"
                data = json.dumps({"machine_id": machine_id}).encode("utf-8")
                req = urllib.request.Request(
                    url, data=data,
                    headers={"Content-Type": "application/json", "Authorization": f"Bearer {token}"},
                    method="POST",
                )
                with urllib.request.urlopen(req, timeout=5) as resp:
                    result = json.loads(resp.read().decode("utf-8"))
                    if result.get("success"):
                        print("已清除: 服务器端试用记录")
                    else:
                        print("服务器端试用记录清除失败")
            else:
                print("管理员登录失败，跳过服务器端清除")
        else:
            print("跳过服务器端试用记录清除")
    except Exception as e:
        print(f"清除服务器端试用记录失败: {e}")

    print("授权数据已清除，下次启动将重新进入授权流程。")


def main():
    """主函数 - 使用 Bootstrap 系统启动应用"""
    # 处理 --reset-license 参数（清除本地授权数据，方便测试）
    if "--reset-license" in sys.argv:
        _reset_license()
        return 0

    # 快速静默授权预检（无 UI）
    # 延迟导入，避免在开发模式下也加载 cryptography 等重量级依赖
    license_pre_ok = False
    from core.security.license_manager import _DEV_MODE
    if not _DEV_MODE:
        from core.security.license_manager import quick_license_check
        result = quick_license_check()
        if result == "ok":
            license_pre_ok = True
        # "needs_ui" → 交给 AppBootstrap 处理

    # 创建 AppBootstrap 实例，传递预检结果避免重复验证
    bootstrap = AppBootstrap()
    
    # 调用 bootstrap.run() 并返回退出码
    return bootstrap.run(license_pre_ok=license_pre_ok)


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
