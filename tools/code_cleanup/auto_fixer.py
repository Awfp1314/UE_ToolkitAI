# -*- coding: utf-8 -*-

"""
自动修复器

自动修复低风险的代码问题，如删除未使用的导入。
"""

import ast
from typing import List, Dict
from pathlib import Path
from collections import defaultdict

from .models import Issue, CleanupResult


class AutoFixer:
    """自动修复器"""
    
    def __init__(self, dry_run: bool = True, backup: bool = True):
        """初始化修复器
        
        Args:
            dry_run: 是否只模拟不实际修改
            backup: 是否备份原文件
        """
        self.dry_run = dry_run
        self.backup = backup
        self.fixed_count = 0
        self.failed_count = 0
    
    def fix_issues(self, result: CleanupResult, categories: List[str] = None) -> Dict[str, int]:
        """修复问题
        
        Args:
            result: 清理结果
            categories: 要修复的类别列表，None 表示修复所有安全的类别
            
        Returns:
            修复统计信息
        """
        if categories is None:
            # 默认只修复低风险的类别
            categories = ['unused_import']
        
        stats = defaultdict(int)
        
        # 按文件分组问题
        issues_by_file = self._group_issues_by_file(result, categories)
        
        # 逐文件修复
        for file_path, issues in issues_by_file.items():
            try:
                fixed = self._fix_file(file_path, issues)
                stats['fixed'] += fixed
                stats['files_modified'] += 1 if fixed > 0 else 0
            except Exception as e:
                print(f"❌ 修复文件失败 {file_path}: {e}")
                stats['failed'] += 1
        
        return dict(stats)
    
    def _group_issues_by_file(self, result: CleanupResult, categories: List[str]) -> Dict[Path, List[Issue]]:
        """按文件分组问题"""
        issues_by_file = defaultdict(list)
        
        for category in categories:
            if category in result.issues_by_category:
                for issue in result.issues_by_category[category]:
                    issues_by_file[issue.file_path].append(issue)
        
        return issues_by_file
    
    def _fix_file(self, file_path: Path, issues: List[Issue]) -> int:
        """修复单个文件"""
        # 读取文件内容
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
                lines = content.split('\n')
        except Exception as e:
            print(f"❌ 读取文件失败 {file_path}: {e}")
            return 0
        
        # 备份原文件
        if self.backup and not self.dry_run:
            backup_path = file_path.with_suffix(file_path.suffix + '.bak')
            with open(backup_path, 'w', encoding='utf-8') as f:
                f.write(content)
        
        # 按类别修复
        fixed_count = 0
        modified_lines = lines.copy()
        
        # 收集要删除的行号（从大到小排序，避免删除时行号变化）
        lines_to_remove = set()
        
        for issue in issues:
            if issue.category == 'unused_import':
                lines_to_remove.add(issue.line_number - 1)  # 转换为 0-based
                fixed_count += 1
        
        # 删除行（从后往前删除）
        for line_num in sorted(lines_to_remove, reverse=True):
            if 0 <= line_num < len(modified_lines):
                del modified_lines[line_num]
        
        # 写回文件
        if not self.dry_run and fixed_count > 0:
            new_content = '\n'.join(modified_lines)
            try:
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(new_content)
                print(f"✅ 修复 {file_path}: 删除了 {fixed_count} 个未使用的导入")
            except Exception as e:
                print(f"❌ 写入文件失败 {file_path}: {e}")
                return 0
        elif self.dry_run and fixed_count > 0:
            print(f"🔍 [DRY RUN] 将修复 {file_path}: 删除 {fixed_count} 个未使用的导入")
        
        return fixed_count
    
    def fix_unused_imports_advanced(self, file_path: Path) -> bool:
        """使用 AST 高级修复未使用的导入
        
        这个方法更智能，可以处理多行导入等复杂情况
        """
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # 解析 AST
            tree = ast.parse(content)
            
            # 收集所有导入
            imports = []
            for node in ast.walk(tree):
                if isinstance(node, (ast.Import, ast.ImportFrom)):
                    imports.append(node)
            
            # 收集所有使用的名称
            used_names = set()
            for node in ast.walk(tree):
                if isinstance(node, ast.Name):
                    used_names.add(node.id)
            
            # 找出未使用的导入
            unused_imports = []
            for imp in imports:
                if isinstance(imp, ast.Import):
                    for alias in imp.names:
                        name = alias.asname if alias.asname else alias.name
                        if name not in used_names:
                            unused_imports.append(imp)
                elif isinstance(imp, ast.ImportFrom):
                    all_unused = True
                    for alias in imp.names:
                        if alias.name == '*':
                            all_unused = False
                            break
                        name = alias.asname if alias.asname else alias.name
                        if name in used_names:
                            all_unused = False
                            break
                    if all_unused:
                        unused_imports.append(imp)
            
            if not unused_imports:
                return False
            
            # 删除未使用的导入
            lines = content.split('\n')
            lines_to_remove = set()
            
            for imp in unused_imports:
                lines_to_remove.add(imp.lineno - 1)
            
            # 重建内容
            new_lines = [line for i, line in enumerate(lines) if i not in lines_to_remove]
            new_content = '\n'.join(new_lines)
            
            # 写回文件
            if not self.dry_run:
                if self.backup:
                    backup_path = file_path.with_suffix(file_path.suffix + '.bak')
                    with open(backup_path, 'w', encoding='utf-8') as f:
                        f.write(content)
                
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(new_content)
                
                print(f"✅ 修复 {file_path}: 删除了 {len(unused_imports)} 个未使用的导入")
            else:
                print(f"🔍 [DRY RUN] 将修复 {file_path}: 删除 {len(unused_imports)} 个未使用的导入")
            
            return True
        
        except Exception as e:
            print(f"❌ 高级修复失败 {file_path}: {e}")
            return False

