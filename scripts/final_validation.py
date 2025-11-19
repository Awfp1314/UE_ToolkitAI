# -*- coding: utf-8 -*-

"""
Final Migration Validation Script

Scans entire codebase to verify thread migration completeness.
"""

import sys
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from core.utils.migration_validator import MigrationValidator


def main():
    """Run final validation on entire codebase."""
    validator = MigrationValidator()
    
    print('🔍 Scanning entire codebase...')
    print()
    
    # Define modules to scan
    modules_to_scan = [
        ('ai_assistant', PROJECT_ROOT / 'modules' / 'ai_assistant'),
        ('asset_manager', PROJECT_ROOT / 'modules' / 'asset_manager'),
        ('core', PROJECT_ROOT / 'core'),
    ]
    
    results = {}
    
    # Scan each module
    for module_name, module_path in modules_to_scan:
        print(f'Scanning {module_name}...')
        result = validator.scan_module(module_path)
        results[module_name] = result
        
        print(f'  Violations: {result.violation_count}')
        
        if result.violations:
            # Show first 5 violations
            for v in result.violations[:5]:
                print(f'    - {v.file_path}:{v.line_number} ({v.violation_type})')
            
            if result.violation_count > 5:
                print(f'    ... and {result.violation_count - 5} more')
        
        print()
    
    # Generate report
    report_path = PROJECT_ROOT / 'reports' / 'final_migration_validation.json'
    report = validator.generate_report(report_path)
    
    # Print summary
    print('=' * 60)
    print('📊 Final Validation Summary')
    print('=' * 60)
    
    summary = report['summary']
    print(f'  Total modules scanned: {summary["total_modules"]}')
    print(f'  Total violations: {summary["total_violations"]}')
    print(f'  Modules with violations: {summary["modules_with_violations"]}')
    print(f'  Total files scanned: {summary["total_files_scanned"]}')
    print()
    
    # Print per-module breakdown
    print('Per-module breakdown:')
    for module_name, result in results.items():
        status = '✅' if result.violation_count == 0 else '❌'
        print(f'  {status} {module_name}: {result.violation_count} violations')
    
    print()
    print(f'✅ Report saved to: {report_path}')
    print()
    
    # Determine exit code
    migrated_modules = ['ai_assistant', 'asset_manager']
    migrated_violations = sum(
        results[m].violation_count 
        for m in migrated_modules 
        if m in results
    )
    
    if migrated_violations > 0:
        print('❌ FAIL: Migrated modules still have violations!')
        return 1
    else:
        print('✅ SUCCESS: All migrated modules are clean!')
        return 0


if __name__ == '__main__':
    sys.exit(main())

