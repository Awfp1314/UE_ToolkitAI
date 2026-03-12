# -*- coding: utf-8 -*-
"""
权限诊断脚本 - 检查资产库路径的读写权限
"""

import os
import sys
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from core.config.config_manager import ConfigManager


def check_permissions():
    """检查资产库路径的权限"""
    print("=" * 60)
    print("UE Toolkit 权限诊断工具")
    print("=" * 60)
    print()
    
    # 加载配置
    try:
        module_dir = Path(__file__).parent / "modules" / "asset_manager"
        template_path = module_dir / "config_template.json"
        config_manager = ConfigManager("asset_manager", template_path=template_path)
        config = config_manager.load_user_config()
        
        asset_library_path = config.get("asset_library_path", "")
        
        if not asset_library_path:
            print("X 资产库路径未设置")
            print("   请先在程序中设置资产库路径")
            return
        
        library_path = Path(asset_library_path)
        print(f"资产库路径: {library_path}")
        print()
        
        # 检查路径是否存在
        if not library_path.exists():
            print("X 资产库路径不存在")
            print(f"   路径: {library_path}")
            return
        
        print("OK 资产库路径存在")
        print()
        
        # 检查读权限
        print("检查读权限...")
        try:
            list(library_path.iterdir())
            print("OK 读权限正常")
        except PermissionError as e:
            print(f"X 读权限不足: {e}")
            return
        except Exception as e:
            print(f"X 读取失败: {e}")
            return
        print()
        
        # 检查写权限
        print("检查写权限...")
        test_file = library_path / ".permission_test"
        try:
            # 尝试创建测试文件
            test_file.write_text("test", encoding="utf-8")
            print("OK 写权限正常（文件创建成功）")
            
            # 尝试删除测试文件
            test_file.unlink()
            print("OK 删除权限正常")
        except PermissionError as e:
            print(f"X 写权限不足: {e}")
            print()
            print("可能的原因：")
            print("  1. 资产库路径在受保护的系统目录（如 C:\\Program Files）")
            print("  2. 文件夹被设置为只读")
            print("  3. 需要管理员权限")
            print()
            print("建议解决方案：")
            print("  1. 将资产库路径改到用户目录（如 D:\\UE_Assets）")
            print("  2. 右键资产库文件夹 -> 属性 -> 取消勾选'只读'")
            print("  3. 以管理员身份运行程序")
            return
        except Exception as e:
            print(f"X 写入失败: {e}")
            return
        print()
        
        # 检查 Content 文件夹
        content_folder = library_path / "Content"
        print(f"检查 Content 文件夹: {content_folder}")
        if content_folder.exists():
            print("OK Content 文件夹存在")
            
            # 检查 Content 文件夹的写权限
            test_file = content_folder / ".permission_test"
            try:
                test_file.write_text("test", encoding="utf-8")
                test_file.unlink()
                print("OK Content 文件夹写权限正常")
            except PermissionError as e:
                print(f"X Content 文件夹写权限不足: {e}")
                return
            except Exception as e:
                print(f"X Content 文件夹写入失败: {e}")
                return
        else:
            print("警告: Content 文件夹不存在（首次使用时会自动创建）")
        print()
        
        # 检查分类文件夹
        print("检查分类文件夹...")
        categories = config.get("categories", ["默认分类"])
        for category in categories:
            category_folder = library_path / category
            if category_folder.exists():
                print(f"  OK {category}")
            else:
                print(f"  警告 {category}（不存在，添加资产时会自动创建）")
        print()
        
        print("=" * 60)
        print("OK 权限检查完成，未发现问题")
        print("=" * 60)
        print()
        print("如果添加资产仍然失败，请提供以下信息：")
        print("  1. 完整的错误提示")
        print("  2. 资产库路径")
        print("  3. 要添加的资产路径")
        
    except Exception as e:
        print(f"X 诊断失败: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    check_permissions()
    input("\n按回车键退出...")
