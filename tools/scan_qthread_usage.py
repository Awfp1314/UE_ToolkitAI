# -*- coding: utf-8 -*-

"""
扫描项目中的 QThread 使用情况

使用 MigrationValidator 扫描整个项目，生成违规报告。
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from core.utils.migration_validator import MigrationValidator


def main():
    """扫描项目中的 QThread 使用"""
    print("=" * 80)
    print("🔍 扫描项目中的 QThread 使用情况")
    print("=" * 80)
    print()
    
    # 创建验证器
    validator = MigrationValidator()
    
    # 定义要扫描的模块
    modules_to_scan = [
        project_root / "modules" / "ai_assistant",
        project_root / "modules" / "asset_manager",
        project_root / "core",
        project_root / "ui",
    ]
    
    # 过滤存在的模块
    existing_modules = [m for m in modules_to_scan if m.exists()]
    
    print(f"📂 扫描 {len(existing_modules)} 个模块：")
    for module in existing_modules:
        print(f"   - {module.relative_to(project_root)}")
    print()
    
    # 扫描所有模块
    results = validator.scan_all_modules(existing_modules)
    
    # 生成报告
    report_path = project_root / "reports" / "qthread_violations.json"
    report = validator.generate_report(report_path)
    
    # 打印摘要
    print()
    print("=" * 80)
    print("📊 扫描结果摘要")
    print("=" * 80)
    print()
    
    summary = report["summary"]
    print(f"✅ 扫描模块数：{summary['total_modules']}")
    print(f"📄 扫描文件数：{summary['total_files_scanned']}")
    print(f"⚠️  违规总数：{summary['total_violations']}")
    print(f"❌ 有违规的模块数：{summary['modules_with_violations']}")
    print()
    
    # 按类型统计违规
    import_violations = validator.get_violations_by_type('import')
    subclass_violations = validator.get_violations_by_type('subclass')
    instantiation_violations = validator.get_violations_by_type('instantiation')
    
    print("📈 违规类型分布：")
    print(f"   - Import 违规：{len(import_violations)}")
    print(f"   - Subclass 违规：{len(subclass_violations)}")
    print(f"   - Instantiation 违规：{len(instantiation_violations)}")
    print()
    
    # 打印每个模块的详细信息
    print("=" * 80)
    print("📋 各模块详细信息")
    print("=" * 80)
    print()
    
    for module_path, result in results.items():
        module_name = Path(module_path).relative_to(project_root)
        status = "❌" if result.has_violations else "✅"
        print(f"{status} {module_name}")
        print(f"   扫描文件：{result.scanned_files}")
        print(f"   违规数量：{result.violation_count}")
        
        if result.has_violations:
            # 按类型分组
            violations_by_type = {}
            for v in result.violations:
                violations_by_type.setdefault(v.violation_type, []).append(v)
            
            for vtype, violations in violations_by_type.items():
                print(f"   - {vtype}: {len(violations)} 个")
                # 打印前 3 个违规示例
                for v in violations[:3]:
                    file_name = Path(v.file_path).name
                    print(f"     * {file_name}:{v.line_number} - {v.code_snippet[:60]}")
                if len(violations) > 3:
                    print(f"     ... 还有 {len(violations) - 3} 个")
        print()
    
    # 打印报告路径
    print("=" * 80)
    print(f"📄 详细报告已保存到：{report_path}")
    print("=" * 80)
    print()
    
    # 如果有违规，返回非零退出码
    if summary['total_violations'] > 0:
        print("⚠️  发现 QThread 违规，需要迁移到 ThreadManager")
        return 1
    else:
        print("✅ 未发现 QThread 违规，代码符合规范！")
        return 0


if __name__ == "__main__":
    sys.exit(main())

