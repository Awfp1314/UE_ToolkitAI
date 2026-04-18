# -*- coding: utf-8 -*-

"""
版本号管理 - 单一真实来源 (Single Source of Truth)

这是整个应用程序版本号的唯一定义位置。
更新版本时，只需修改这个文件中的 VERSION 常量。

版本号格式: MAJOR.MINOR.PATCH
- MAJOR: 主版本号（重大变更、不兼容的API修改）
- MINOR: 次版本号（新功能、向后兼容）
- PATCH: 修订号（bug修复、小改进）
"""

# ============================================
# 版本号定义 - 只需修改这一行
# ============================================
VERSION = "1.2.37"
# ============================================


# 自动生成的版本信息（不要手动修改）
VERSION_INFO = tuple(int(x) for x in VERSION.split('.'))
VERSION_MAJOR = VERSION_INFO[0]
VERSION_MINOR = VERSION_INFO[1]
VERSION_PATCH = VERSION_INFO[2]

# 带 'v' 前缀的版本号（用于显示）
VERSION_STRING = f"v{VERSION}"

# 应用程序信息
APP_NAME = "ue_toolkit"  # 注意：此名称用于 Qt 标准路径，不应包含空格
APP_DISPLAY_NAME = "UE Toolkit"  # 用于界面显示的名称
APP_ID = "HUTAO.UEToolkit"
APP_AUTHOR = "HUTAO"


def get_version() -> str:
    """
    获取版本号（不带v前缀）
    
    Returns:
        版本号字符串，如 "1.2.0"
    """
    return VERSION


def get_version_string() -> str:
    """
    获取版本号字符串（带v前缀）
    
    Returns:
        版本号字符串，如 "v1.2.0"
    """
    return VERSION_STRING


def get_version_info() -> tuple:
    """
    获取版本号元组
    
    Returns:
        版本号元组，如 (1, 2, 0)
    """
    return VERSION_INFO


def get_app_user_model_id() -> str:
    """
    获取 Windows AppUserModelID
    
    Returns:
        AppUserModelID 字符串，如 "HUTAO.UEToolkit.1.2"
    """
    return f"{APP_ID}.{VERSION_MAJOR}.{VERSION_MINOR}"


if __name__ == "__main__":
    # 测试输出
    print(f"应用名称: {APP_NAME}")
    print(f"版本号: {VERSION}")
    print(f"版本字符串: {VERSION_STRING}")
    print(f"版本信息: {VERSION_INFO}")
    print(f"AppUserModelID: {get_app_user_model_id()}")
