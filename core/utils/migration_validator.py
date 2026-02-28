# -*- coding: utf-8 -*-

"""
MigrationValidator - Static analysis tool for detecting direct QThread usage

This module provides AST-based scanning to identify QThread violations:
- Direct QThread instantiation
- QThread subclassing
- QThread imports

Used to validate migration from direct QThread usage to ThreadManager.
"""

import ast
import json
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import List, Dict, Optional, Set
from core.services import _get_log_service

logger = _get_log_service().get_logger(__name__)


@dataclass
class QThreadViolation:
    """Data class representing a QThread usage violation"""
    
    file_path: str
    line_number: int
    violation_type: str  # 'instantiation', 'subclass', 'import'
    code_snippet: str
    class_name: Optional[str] = None
    
    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization"""
        return asdict(self)


@dataclass
class ModuleScanResult:
    """Result of scanning a single module"""
    
    module_path: str
    violations: List[QThreadViolation] = field(default_factory=list)
    scanned_files: int = 0
    
    @property
    def has_violations(self) -> bool:
        """Check if module has any violations"""
        return len(self.violations) > 0
    
    @property
    def violation_count(self) -> int:
        """Get total violation count"""
        return len(self.violations)
    
    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization"""
        return {
            "module_path": self.module_path,
            "scanned_files": self.scanned_files,
            "violation_count": self.violation_count,
            "violations": [v.to_dict() for v in self.violations]
        }


class QThreadVisitor(ast.NodeVisitor):
    """AST visitor to detect QThread usage patterns"""
    
    def __init__(self, file_path: Path):
        self.file_path = file_path
        self.violations: List[QThreadViolation] = []
        self.qthread_imported = False
        self.source_lines: List[str] = []
        
        # Read source file for code snippets
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                self.source_lines = f.readlines()
        except Exception as e:
            logger.warning(f"Failed to read source file {file_path}: {e}")
    
    def visit_Import(self, node: ast.Import):
        """Detect: import PyQt6.QtCore (contains QThread)"""
        for alias in node.names:
            if 'QtCore' in alias.name or 'QThread' in alias.name:
                self.qthread_imported = True
                snippet = self._get_code_snippet(node.lineno)
                self.violations.append(QThreadViolation(
                    file_path=str(self.file_path),
                    line_number=node.lineno,
                    violation_type='import',
                    code_snippet=snippet
                ))
        self.generic_visit(node)
    
    def visit_ImportFrom(self, node: ast.ImportFrom):
        """Detect: from PyQt6.QtCore import QThread"""
        if node.module and ('QtCore' in node.module or 'QtGui' in node.module):
            for alias in node.names:
                if alias.name == 'QThread':
                    self.qthread_imported = True
                    snippet = self._get_code_snippet(node.lineno)
                    self.violations.append(QThreadViolation(
                        file_path=str(self.file_path),
                        line_number=node.lineno,
                        violation_type='import',
                        code_snippet=snippet
                    ))
        self.generic_visit(node)
    
    def visit_ClassDef(self, node: ast.ClassDef):
        """Detect: class MyWorker(QThread)"""
        for base in node.bases:
            base_name = self._get_name(base)
            if base_name == 'QThread':
                snippet = self._get_code_snippet(node.lineno)
                self.violations.append(QThreadViolation(
                    file_path=str(self.file_path),
                    line_number=node.lineno,
                    violation_type='subclass',
                    code_snippet=snippet,
                    class_name=node.name
                ))
        self.generic_visit(node)
    
    def visit_Call(self, node: ast.Call):
        """Detect: QThread() instantiation"""
        func_name = self._get_name(node.func)
        if func_name == 'QThread':
            snippet = self._get_code_snippet(node.lineno)
            self.violations.append(QThreadViolation(
                file_path=str(self.file_path),
                line_number=node.lineno,
                violation_type='instantiation',
                code_snippet=snippet
            ))
        self.generic_visit(node)
    
    def _get_name(self, node) -> str:
        """Extract name from AST node"""
        if isinstance(node, ast.Name):
            return node.id
        elif isinstance(node, ast.Attribute):
            return node.attr
        return ""
    
    def _get_code_snippet(self, line_number: int) -> str:
        """Get code snippet from source"""
        if 0 < line_number <= len(self.source_lines):
            return self.source_lines[line_number - 1].strip()
        return ""


class MigrationValidator:
    """Static analysis tool for detecting direct QThread usage"""

    def __init__(self):
        self.results: Dict[str, ModuleScanResult] = {}

    def scan_file(self, file_path: Path) -> List[QThreadViolation]:
        """Scan a single Python file for QThread violations

        Args:
            file_path: Path to Python file

        Returns:
            List of violations found
        """
        violations = []

        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                source = f.read()

            tree = ast.parse(source, filename=str(file_path))
            visitor = QThreadVisitor(file_path)
            visitor.visit(tree)
            violations = visitor.violations

            if violations:
                logger.debug(f"Found {len(violations)} violations in {file_path}")

        except SyntaxError as e:
            logger.warning(f"Syntax error in {file_path}: {e}")
        except Exception as e:
            logger.error(f"Error scanning {file_path}: {e}")

        return violations

    def scan_module(self, module_path: Path) -> ModuleScanResult:
        """Scan a module directory for QThread violations

        Args:
            module_path: Path to module directory

        Returns:
            ModuleScanResult with all violations found
        """
        result = ModuleScanResult(module_path=str(module_path))

        if not module_path.exists():
            logger.error(f"Module path does not exist: {module_path}")
            return result

        # Find all Python files
        python_files = list(module_path.rglob("*.py"))
        result.scanned_files = len(python_files)

        logger.info(f"Scanning {len(python_files)} files in {module_path}")

        for file_path in python_files:
            violations = self.scan_file(file_path)
            result.violations.extend(violations)

        # Store result
        self.results[str(module_path)] = result

        logger.info(f"Scan complete: {result.violation_count} violations in {module_path}")
        return result

    def scan_all_modules(self, module_paths: List[Path]) -> Dict[str, ModuleScanResult]:
        """Scan multiple modules for QThread violations

        Args:
            module_paths: List of module directory paths

        Returns:
            Dictionary mapping module path to scan results
        """
        logger.info(f"Scanning {len(module_paths)} modules")

        for module_path in module_paths:
            self.scan_module(module_path)

        total_violations = sum(r.violation_count for r in self.results.values())
        logger.info(f"Total violations found: {total_violations}")

        return self.results

    def generate_report(self, output_path: Optional[Path] = None) -> dict:
        """Generate JSON report of all scan results

        Args:
            output_path: Optional path to save JSON report

        Returns:
            Report dictionary
        """
        report = {
            "summary": {
                "total_modules": len(self.results),
                "total_violations": sum(r.violation_count for r in self.results.values()),
                "modules_with_violations": sum(1 for r in self.results.values() if r.has_violations),
                "total_files_scanned": sum(r.scanned_files for r in self.results.values())
            },
            "modules": {
                path: result.to_dict()
                for path, result in self.results.items()
            }
        }

        # Save to file if path provided
        if output_path:
            try:
                output_path.parent.mkdir(parents=True, exist_ok=True)
                with open(output_path, 'w', encoding='utf-8') as f:
                    json.dump(report, f, indent=2, ensure_ascii=False)
                logger.info(f"Report saved to {output_path}")
            except Exception as e:
                logger.error(f"Failed to save report to {output_path}: {e}")

        return report

    def get_violations_by_type(self, violation_type: str) -> List[QThreadViolation]:
        """Get all violations of a specific type

        Args:
            violation_type: Type of violation ('import', 'subclass', 'instantiation')

        Returns:
            List of matching violations
        """
        violations = []
        for result in self.results.values():
            violations.extend([v for v in result.violations if v.violation_type == violation_type])
        return violations


__all__ = [
    "QThreadViolation",
    "ModuleScanResult",
    "MigrationValidator",
]

