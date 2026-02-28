# -*- coding: utf-8 -*-

"""
配置管理器集成示例
展示如何在UpdateChecker中使用ConfigManager
"""

from core.config_manager import ConfigManager
from core.update_checker import UpdateChecker


def example_basic_usage():
    """基本使用示例"""
    print("=" * 60)
    print("示例1: 基本使用")
    print("=" * 60)
    
    # 创建配置管理器
    config_mgr = ConfigManager()
    
    # 获取或创建用户ID
    user_id = config_mgr.get_or_create_user_id()
    print(f"用户ID: {user_id}")
    
    # 设置API URL
    config_mgr.set_config_value("api_base_url", "http://localhost:5000/api")
    
    # 获取配置值
    api_url = config_mgr.get_config_value("api_base_url")
    print(f"API URL: {api_url}")
    
    print()


def example_version_skip():
    """版本跳过示例"""
    print("=" * 60)
    print("示例2: 版本跳过管理")
    print("=" * 60)
    
    config_mgr = ConfigManager()
    
    # 模拟用户跳过版本
    latest_version = "v1.4.0"
    config_mgr.add_skipped_version(latest_version)
    print(f"已跳过版本: {latest_version}")
    
    # 检查版本是否已跳过
    if config_mgr.is_version_skipped(latest_version):
        print(f"版本 {latest_version} 已被跳过，不显示更新提示")
    
    # 查看所有跳过的版本
    skipped = config_mgr.get_skipped_versions()
    print(f"所有跳过的版本: {skipped}")
    
    print()


def example_pending_events():
    """待上报事件示例"""
    print("=" * 60)
    print("示例3: 待上报事件管理")
    print("=" * 60)
    
    config_mgr = ConfigManager()
    user_id = config_mgr.get_or_create_user_id()
    
    # 模拟网络失败，添加待上报事件
    event = {
        "user_id": user_id,
        "client_version": "v1.3.0",
        "platform": "Windows"
    }
    
    config_mgr.add_pending_event(event)
    print(f"添加待上报事件: {event}")
    
    # 获取待上报事件
    pending = config_mgr.get_pending_events()
    print(f"待上报事件数量: {len(pending)}")
    
    # 模拟成功上报后清空
    config_mgr.clear_pending_events()
    print("待上报事件已清空")
    
    print()


def example_update_checker_integration():
    """UpdateChecker集成示例"""
    print("=" * 60)
    print("示例4: UpdateChecker集成")
    print("=" * 60)
    
    from pathlib import Path
    
    # 方式1: UpdateChecker使用内置配置管理（使用update_config.json）
    checker = UpdateChecker(current_version="1.3.0")
    user_id = checker.get_or_create_user_id()
    print(f"UpdateChecker用户ID: {user_id}")
    print(f"UpdateChecker配置文件: {checker.config_path}")
    
    # 方式2: 使用独立的ConfigManager（使用config.json）
    config_mgr = ConfigManager()
    user_id_2 = config_mgr.get_or_create_user_id()
    print(f"ConfigManager用户ID: {user_id_2}")
    print(f"ConfigManager配置文件: {config_mgr.config_path}")
    
    # 方式3: 使用ConfigManager管理UpdateChecker的配置文件
    update_config_path = Path.home() / ".ue_toolkit" / "update_config.json"
    config_mgr_for_update = ConfigManager(config_path=str(update_config_path))
    user_id_3 = config_mgr_for_update.get_user_id()
    print(f"ConfigManager(update_config.json)用户ID: {user_id_3}")
    
    # 注意：UpdateChecker和ConfigManager默认使用不同的配置文件
    # 如果需要共享配置，应该使用相同的配置文件路径
    print("✓ 可以使用ConfigManager管理UpdateChecker的配置文件")
    
    print()


def example_config_backup():
    """配置备份示例"""
    print("=" * 60)
    print("示例5: 配置备份和恢复")
    print("=" * 60)
    
    from pathlib import Path
    from datetime import datetime
    
    config_mgr = ConfigManager()
    
    # 设置一些配置
    config_mgr.set_config_value("api_base_url", "http://example.com/api")
    config_mgr.add_skipped_version("v1.2.0")
    
    # 导出配置
    backup_dir = Path.home() / ".ue_toolkit" / "backups"
    backup_dir.mkdir(exist_ok=True)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = backup_dir / f"config_backup_{timestamp}.json"
    
    config_mgr.export_config(str(backup_path))
    print(f"配置已备份到: {backup_path}")
    
    # 模拟配置损坏，重置配置
    config_mgr.reset_config()
    print("配置已重置")
    
    # 从备份恢复
    config_mgr.import_config(str(backup_path))
    print("配置已从备份恢复")
    
    # 验证恢复的配置
    api_url = config_mgr.get_config_value("api_base_url")
    print(f"恢复的API URL: {api_url}")
    
    # 清理备份文件
    if backup_path.exists():
        backup_path.unlink()
        print("备份文件已清理")
    
    print()


def example_yaml_format():
    """YAML格式示例"""
    print("=" * 60)
    print("示例6: 使用YAML格式")
    print("=" * 60)
    
    from pathlib import Path
    
    # 使用YAML格式
    yaml_config_path = Path.home() / ".ue_toolkit" / "config_yaml_example.yaml"
    config_mgr = ConfigManager(config_path=str(yaml_config_path), format="yaml")
    
    # 设置配置
    user_id = config_mgr.get_or_create_user_id()
    config_mgr.set_config_value("theme", "dark")
    config_mgr.set_config_value("language", "zh-CN")
    
    print(f"YAML配置文件: {yaml_config_path}")
    print(f"用户ID: {user_id}")
    print(f"主题: {config_mgr.get_config_value('theme')}")
    print(f"语言: {config_mgr.get_config_value('language')}")
    
    # 清理示例文件
    if yaml_config_path.exists():
        yaml_config_path.unlink()
        print("示例文件已清理")
    
    print()


def example_advanced_usage():
    """高级使用示例"""
    print("=" * 60)
    print("示例7: 高级使用 - 批量上报待上报事件")
    print("=" * 60)
    
    config_mgr = ConfigManager()
    user_id = config_mgr.get_or_create_user_id()
    
    # 模拟添加多个待上报事件
    for i in range(3):
        event = {
            "user_id": user_id,
            "client_version": f"v1.3.{i}",
            "platform": "Windows"
        }
        config_mgr.add_pending_event(event)
    
    print(f"添加了3个待上报事件")
    
    # 获取待上报事件
    pending = config_mgr.get_pending_events()
    print(f"待上报事件数量: {len(pending)}")
    
    # 模拟批量上报
    successful_indices = []
    for idx, event in enumerate(pending):
        # 模拟上报成功
        print(f"  上报事件 {idx}: {event['client_version']}")
        successful_indices.append(idx)
    
    # 移除成功上报的事件
    removed = config_mgr.remove_pending_events(successful_indices)
    print(f"移除了 {removed} 个成功上报的事件")
    
    # 验证队列已清空
    remaining = config_mgr.get_pending_events()
    print(f"剩余待上报事件: {len(remaining)}")
    
    print()


if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("ConfigManager 集成示例")
    print("=" * 60 + "\n")
    
    try:
        example_basic_usage()
        example_version_skip()
        example_pending_events()
        example_update_checker_integration()
        example_config_backup()
        example_yaml_format()
        example_advanced_usage()
        
        print("=" * 60)
        print("✓ 所有示例运行成功！")
        print("=" * 60)
        
    except Exception as e:
        print(f"\n✗ 示例运行失败: {e}")
        import traceback
        traceback.print_exc()
