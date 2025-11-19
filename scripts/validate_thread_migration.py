"""Local validation script for thread migration.

This script runs the same validation checks as the CI pipeline,
allowing developers to verify their changes before committing.

Usage:
    python scripts/validate_thread_migration.py
"""
import sys
import json
from pathlib import Path
from datetime import datetime

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from core.utils.migration_validator import MigrationValidator


def validate_module(module_name: str, module_path: Path) -> tuple[bool, list]:
    """Validate a single module.

    Args:
        module_name: Name of the module
        module_path: Path to the module directory

    Returns:
        Tuple of (success, violations)
    """
    print(f"\n{'='*60}")
    print(f"Validating {module_name} module...")
    print(f"{'='*60}")

    validator = MigrationValidator()
    result = validator.scan_module(module_path)

    if result.violations:
        print(f"❌ Found {result.violation_count} violations:")
        for v in result.violations:
            print(f"  {v.file_path}:{v.line_number} - {v.violation_type}")
            print(f"    Code: {v.code_snippet}")
        return False, result.violations
    else:
        print(f"✅ No violations found")
        return True, []


def generate_report(results: dict):
    """Generate validation report.
    
    Args:
        results: Dictionary of module results
    """
    report = {
        'timestamp': datetime.now().isoformat(),
        'modules': {},
        'total_violations': 0,
    }
    
    for module_name, (success, violations) in results.items():
        report['modules'][module_name] = {
            'violations': len(violations),
            'status': 'PASS' if success else 'FAIL',
        }
        report['total_violations'] += len(violations)
    
    # Save report
    report_dir = PROJECT_ROOT / "reports"
    report_dir.mkdir(exist_ok=True)
    
    report_path = report_dir / "migration_validation.json"
    with open(report_path, 'w', encoding='utf-8') as f:
        json.dump(report, f, indent=2)
    
    print(f"\n{'='*60}")
    print("Validation Report")
    print(f"{'='*60}")
    print(json.dumps(report, indent=2))
    print(f"\n📊 Report saved to: {report_path}")
    
    return report


def main():
    """Main validation function."""
    print("🔍 Thread Migration Validation")
    print(f"Project: {PROJECT_ROOT}")
    
    # Modules to validate
    modules = {
        'ai_assistant': 'modules/ai_assistant',
        'asset_manager': 'modules/asset_manager',
    }
    
    results = {}
    all_success = True
    
    # Validate each module
    for module_name, module_path in modules.items():
        full_path = PROJECT_ROOT / module_path
        if not full_path.exists():
            print(f"⚠️  Module not found: {module_path}")
            continue

        success, violations = validate_module(module_name, full_path)
        results[module_name] = (success, violations)

        if not success:
            all_success = False
    
    # Generate report
    report = generate_report(results)
    
    # Print summary
    print(f"\n{'='*60}")
    print("Summary")
    print(f"{'='*60}")
    
    if all_success:
        print("✅ All modules passed validation!")
        print("🎉 You can safely commit your changes.")
        return 0
    else:
        print("❌ Validation failed!")
        print(f"Total violations: {report['total_violations']}")
        print("\n⚠️  Please fix the violations before committing.")
        print("\nTips:")
        print("  1. Replace QThread with ThreadManager.run_in_thread()")
        print("  2. Add cancel_token parameter to task functions")
        print("  3. Implement cleanup() method returning CleanupResult")
        print("\nSee documentation:")
        print("  - docs/CANCELLATION_AWARE_TASKS_GUIDE.md")
        print("  - docs/CLEANUP_CONTRACT_GUIDE.md")
        return 1


if __name__ == "__main__":
    sys.exit(main())

