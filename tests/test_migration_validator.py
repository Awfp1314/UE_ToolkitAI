# -*- coding: utf-8 -*-

"""
Unit tests for MigrationValidator

Tests AST-based scanning for QThread usage violations.
"""

import pytest
import tempfile
from pathlib import Path
from core.utils.migration_validator import (
    MigrationValidator,
    QThreadViolation,
    ModuleScanResult
)


# Sample code with violations
SAMPLE_CODE_WITH_VIOLATIONS = """
from PyQt6.QtCore import QThread, pyqtSignal

class MyWorker(QThread):
    finished = pyqtSignal()
    
    def run(self):
        # Do work
        self.finished.emit()

def create_thread():
    thread = QThread()
    return thread
"""

SAMPLE_CODE_CLEAN = """
from core.utils.thread_manager import get_thread_manager

def do_work(cancel_token):
    # Clean implementation using ThreadManager
    pass

def start_work():
    manager = get_thread_manager()
    manager.run_in_thread("test", "work", do_work)
"""

SAMPLE_CODE_IMPORT_ONLY = """from PyQt6.QtCore import QThread
"""

SAMPLE_CODE_SUBCLASS_ONLY = """
from PyQt6.QtCore import QThread

class Worker(QThread):
    pass
"""

SAMPLE_CODE_INSTANTIATION_ONLY = """
from PyQt6.QtCore import QThread

def create():
    return QThread()
"""


class TestQThreadViolation:
    """Test QThreadViolation data class"""
    
    def test_violation_creation(self):
        """Test creating a violation"""
        violation = QThreadViolation(
            file_path="test.py",
            line_number=10,
            violation_type="import",
            code_snippet="from PyQt6.QtCore import QThread"
        )
        
        assert violation.file_path == "test.py"
        assert violation.line_number == 10
        assert violation.violation_type == "import"
        assert violation.class_name is None
    
    def test_violation_to_dict(self):
        """Test converting violation to dict"""
        violation = QThreadViolation(
            file_path="test.py",
            line_number=10,
            violation_type="subclass",
            code_snippet="class MyWorker(QThread):",
            class_name="MyWorker"
        )
        
        data = violation.to_dict()
        assert data["file_path"] == "test.py"
        assert data["line_number"] == 10
        assert data["violation_type"] == "subclass"
        assert data["class_name"] == "MyWorker"


class TestModuleScanResult:
    """Test ModuleScanResult data class"""
    
    def test_empty_result(self):
        """Test empty scan result"""
        result = ModuleScanResult(module_path="test_module")
        
        assert result.module_path == "test_module"
        assert result.violation_count == 0
        assert not result.has_violations
    
    def test_result_with_violations(self):
        """Test scan result with violations"""
        violations = [
            QThreadViolation("test.py", 1, "import", "import QThread"),
            QThreadViolation("test.py", 5, "subclass", "class W(QThread):", "W")
        ]
        
        result = ModuleScanResult(
            module_path="test_module",
            violations=violations,
            scanned_files=1
        )
        
        assert result.violation_count == 2
        assert result.has_violations
        assert result.scanned_files == 1
    
    def test_result_to_dict(self):
        """Test converting result to dict"""
        violations = [
            QThreadViolation("test.py", 1, "import", "import QThread")
        ]
        
        result = ModuleScanResult(
            module_path="test_module",
            violations=violations,
            scanned_files=1
        )
        
        data = result.to_dict()
        assert data["module_path"] == "test_module"
        assert data["scanned_files"] == 1
        assert data["violation_count"] == 1
        assert len(data["violations"]) == 1


class TestMigrationValidator:
    """Test MigrationValidator scanner"""
    
    def test_scan_file_with_violations(self, tmp_path):
        """Test scanning file with violations"""
        # Create test file
        test_file = tmp_path / "test.py"
        test_file.write_text(SAMPLE_CODE_WITH_VIOLATIONS, encoding='utf-8')
        
        validator = MigrationValidator()
        violations = validator.scan_file(test_file)
        
        # Should find: 1 import + 1 subclass + 1 instantiation = 3 violations
        assert len(violations) == 3
        
        # Check violation types
        types = {v.violation_type for v in violations}
        assert types == {'import', 'subclass', 'instantiation'}

    def test_scan_file_clean(self, tmp_path):
        """Test scanning clean file without violations"""
        test_file = tmp_path / "clean.py"
        test_file.write_text(SAMPLE_CODE_CLEAN, encoding='utf-8')

        validator = MigrationValidator()
        violations = validator.scan_file(test_file)

        assert len(violations) == 0

    def test_scan_file_import_violation(self, tmp_path):
        """Test detecting import violation"""
        test_file = tmp_path / "import_test.py"
        test_file.write_text(SAMPLE_CODE_IMPORT_ONLY, encoding='utf-8')

        validator = MigrationValidator()
        violations = validator.scan_file(test_file)

        assert len(violations) == 1
        assert violations[0].violation_type == 'import'
        assert violations[0].line_number == 1

    def test_scan_file_subclass_violation(self, tmp_path):
        """Test detecting subclass violation"""
        test_file = tmp_path / "subclass_test.py"
        test_file.write_text(SAMPLE_CODE_SUBCLASS_ONLY, encoding='utf-8')

        validator = MigrationValidator()
        violations = validator.scan_file(test_file)

        # Should find: 1 import + 1 subclass = 2 violations
        assert len(violations) == 2

        subclass_violations = [v for v in violations if v.violation_type == 'subclass']
        assert len(subclass_violations) == 1
        assert subclass_violations[0].class_name == 'Worker'

    def test_scan_file_instantiation_violation(self, tmp_path):
        """Test detecting instantiation violation"""
        test_file = tmp_path / "instantiation_test.py"
        test_file.write_text(SAMPLE_CODE_INSTANTIATION_ONLY, encoding='utf-8')

        validator = MigrationValidator()
        violations = validator.scan_file(test_file)

        # Should find: 1 import + 1 instantiation = 2 violations
        assert len(violations) == 2

        inst_violations = [v for v in violations if v.violation_type == 'instantiation']
        assert len(inst_violations) == 1

    def test_scan_module(self, tmp_path):
        """Test scanning a module directory"""
        # Create module structure
        module_dir = tmp_path / "test_module"
        module_dir.mkdir()

        (module_dir / "file1.py").write_text(SAMPLE_CODE_WITH_VIOLATIONS, encoding='utf-8')
        (module_dir / "file2.py").write_text(SAMPLE_CODE_CLEAN, encoding='utf-8')
        (module_dir / "file3.py").write_text(SAMPLE_CODE_IMPORT_ONLY, encoding='utf-8')

        validator = MigrationValidator()
        result = validator.scan_module(module_dir)

        assert result.scanned_files == 3
        assert result.violation_count == 4  # 3 from file1 + 1 from file3
        assert result.has_violations

    def test_scan_all_modules(self, tmp_path):
        """Test scanning multiple modules"""
        # Create two modules
        module1 = tmp_path / "module1"
        module1.mkdir()
        (module1 / "test.py").write_text(SAMPLE_CODE_WITH_VIOLATIONS, encoding='utf-8')

        module2 = tmp_path / "module2"
        module2.mkdir()
        (module2 / "test.py").write_text(SAMPLE_CODE_CLEAN, encoding='utf-8')

        validator = MigrationValidator()
        results = validator.scan_all_modules([module1, module2])

        assert len(results) == 2
        assert results[str(module1)].has_violations
        assert not results[str(module2)].has_violations

    def test_generate_report(self, tmp_path):
        """Test generating JSON report"""
        # Create test module
        module_dir = tmp_path / "test_module"
        module_dir.mkdir()
        (module_dir / "test.py").write_text(SAMPLE_CODE_WITH_VIOLATIONS, encoding='utf-8')

        validator = MigrationValidator()
        validator.scan_module(module_dir)

        # Generate report
        report_path = tmp_path / "report.json"
        report = validator.generate_report(report_path)

        # Check report structure
        assert "summary" in report
        assert "modules" in report

        summary = report["summary"]
        assert summary["total_modules"] == 1
        assert summary["total_violations"] == 3
        assert summary["modules_with_violations"] == 1
        assert summary["total_files_scanned"] == 1

        # Check report file was created
        assert report_path.exists()

    def test_get_violations_by_type(self, tmp_path):
        """Test filtering violations by type"""
        # Create test file
        test_file = tmp_path / "test.py"
        test_file.write_text(SAMPLE_CODE_WITH_VIOLATIONS, encoding='utf-8')

        validator = MigrationValidator()
        validator.scan_file(test_file)

        # Store in results
        result = ModuleScanResult(
            module_path=str(tmp_path),
            violations=validator.scan_file(test_file),
            scanned_files=1
        )
        validator.results[str(tmp_path)] = result

        # Get violations by type
        import_violations = validator.get_violations_by_type('import')
        subclass_violations = validator.get_violations_by_type('subclass')
        inst_violations = validator.get_violations_by_type('instantiation')

        assert len(import_violations) == 1
        assert len(subclass_violations) == 1
        assert len(inst_violations) == 1

    def test_scan_nonexistent_module(self, tmp_path):
        """Test scanning non-existent module"""
        nonexistent = tmp_path / "nonexistent"

        validator = MigrationValidator()
        result = validator.scan_module(nonexistent)

        assert result.scanned_files == 0
        assert result.violation_count == 0

    def test_scan_file_with_syntax_error(self, tmp_path):
        """Test scanning file with syntax error"""
        test_file = tmp_path / "syntax_error.py"
        test_file.write_text("def broken(:\n    pass", encoding='utf-8')

        validator = MigrationValidator()
        violations = validator.scan_file(test_file)

        # Should handle gracefully and return empty list
        assert len(violations) == 0

