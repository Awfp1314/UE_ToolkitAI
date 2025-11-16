# -*- coding: utf-8 -*-
"""
构建所有主题

使用方法:
    python build_themes.py              # 详细日志模式
    python build_themes.py --quiet      # 安静模式（批量构建）
"""

from pathlib import Path
import sys
import argparse

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent))

from core.utils.theme_builder import ThemeBuilder


def main():
    """构建所有主题"""
    # 解析命令行参数
    parser = argparse.ArgumentParser(description='构建QSS主题文件')
    parser.add_argument('--quiet', '-q', action='store_true', 
                       help='安静模式（不输出详细日志）')
    parser.add_argument('--theme', '-t', type=str, 
                       help='只构建指定的主题')
    args = parser.parse_args()
    
    # 设置样式根目录
    styles_root = Path(__file__).parent / "resources" / "styles"
    
    # 创建构建器（根据参数设置verbose）
    verbose = not args.quiet
    builder = ThemeBuilder(styles_root, verbose=verbose)
    
    # 构建主题
    if args.theme:
        # 构建单个主题
        print(f"\n{'='*60}")
        print(f"  构建单个主题: {args.theme}")
        print(f"{'='*60}\n")
        
        builder.build_theme(args.theme, save=True)
        output_file = styles_root / "themes" / f"{args.theme}.qss"
        
        if output_file.exists():
            print(f"\n✅ 主题构建成功: {output_file.name}")
            print(f"   文件路径: {output_file}")
            print(f"   文件大小: {output_file.stat().st_size} 字节")
        else:
            print(f"\n❌ 主题构建失败: {args.theme}")
            sys.exit(1)
    else:
        # 构建所有主题
        print(f"\n{'='*60}")
        print(f"  构建所有主题")
        print(f"{'='*60}\n")
        
        output_files = builder.build_all_themes()
        
        if output_files:
            print(f"\n{'='*60}")
            print(f"  构建完成")
            print(f"{'='*60}\n")
            print(f"✅ 成功构建 {len(output_files)} 个主题:\n")
            for file in output_files:
                size = file.stat().st_size if file.exists() else 0
                print(f"   📄 {file.name:<20} ({size:>6} 字节)")
            print()
        else:
            print("\n❌ 没有构建任何主题")
            sys.exit(1)


if __name__ == "__main__":
    main()

