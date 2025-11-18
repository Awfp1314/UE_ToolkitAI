"""分析类结构的工具脚本

分析大类的方法分组、行数分布、职责划分
"""

import ast
import sys
from pathlib import Path
from typing import List, Dict, Any
from collections import defaultdict


class ClassAnalyzer(ast.NodeVisitor):
    """类结构分析器"""
    
    def __init__(self):
        self.classes = []
        self.current_class = None
        
    def visit_ClassDef(self, node):
        """访问类定义"""
        class_info = {
            'name': node.name,
            'line_start': node.lineno,
            'line_end': node.end_lineno,
            'total_lines': node.end_lineno - node.lineno + 1,
            'methods': [],
            'signals': [],
            'attributes': []
        }
        
        # 保存当前类上下文
        old_class = self.current_class
        self.current_class = class_info
        
        # 访问类体
        self.generic_visit(node)
        
        # 恢复上下文
        self.current_class = old_class
        self.classes.append(class_info)
        
    def visit_FunctionDef(self, node):
        """访问函数定义"""
        if self.current_class is not None:
            method_info = {
                'name': node.name,
                'line_start': node.lineno,
                'line_end': node.end_lineno,
                'total_lines': node.end_lineno - node.lineno + 1,
                'is_private': node.name.startswith('_'),
                'is_dunder': node.name.startswith('__') and node.name.endswith('__'),
                'args': [arg.arg for arg in node.args.args]
            }
            self.current_class['methods'].append(method_info)
        
        # 不递归访问嵌套函数
        
    def visit_Assign(self, node):
        """访问赋值语句（查找信号定义）"""
        if self.current_class is not None:
            for target in node.targets:
                if isinstance(target, ast.Name):
                    # 检查是否是 pyqtSignal
                    if isinstance(node.value, ast.Call):
                        if hasattr(node.value.func, 'id') and 'Signal' in node.value.func.id:
                            self.current_class['signals'].append(target.id)


def analyze_file(file_path: Path) -> Dict[str, Any]:
    """分析文件结构"""
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    tree = ast.parse(content)
    analyzer = ClassAnalyzer()
    analyzer.visit(tree)
    
    return {
        'file_path': str(file_path),
        'total_lines': len(content.splitlines()),
        'classes': analyzer.classes
    }


def group_methods_by_prefix(methods: List[Dict]) -> Dict[str, List[Dict]]:
    """根据方法名前缀分组"""
    groups = defaultdict(list)
    
    for method in methods:
        name = method['name']
        
        # 特殊方法
        if method['is_dunder']:
            groups['__dunder__'].append(method)
        # 私有方法
        elif method['is_private']:
            # 尝试提取前缀
            parts = name.split('_')
            if len(parts) >= 3:
                prefix = f"_{parts[1]}"
                groups[prefix].append(method)
            else:
                groups['_private'].append(method)
        # 公共方法
        else:
            # 尝试提取前缀
            parts = name.split('_')
            if len(parts) >= 2:
                prefix = parts[0]
                groups[prefix].append(method)
            else:
                groups['other'].append(method)
    
    return dict(groups)


def print_analysis(analysis: Dict[str, Any]):
    """打印分析结果"""
    print(f"\n{'='*80}")
    print(f"文件: {analysis['file_path']}")
    print(f"总行数: {analysis['total_lines']}")
    print(f"{'='*80}\n")
    
    for cls in analysis['classes']:
        print(f"类: {cls['name']}")
        print(f"  行数: {cls['line_start']}-{cls['line_end']} (共 {cls['total_lines']} 行)")
        print(f"  信号数: {len(cls['signals'])}")
        print(f"  方法数: {len(cls['methods'])}")
        
        # 统计方法行数
        method_lines = [m['total_lines'] for m in cls['methods']]
        if method_lines:
            print(f"  方法行数统计:")
            print(f"    - 平均: {sum(method_lines) / len(method_lines):.1f} 行")
            print(f"    - 最大: {max(method_lines)} 行")
            print(f"    - 最小: {min(method_lines)} 行")
            
            # 找出超过50行的方法
            large_methods = [m for m in cls['methods'] if m['total_lines'] > 50]
            if large_methods:
                print(f"  超过50行的方法 ({len(large_methods)} 个):")
                for m in sorted(large_methods, key=lambda x: x['total_lines'], reverse=True):
                    print(f"    - {m['name']}: {m['total_lines']} 行 (L{m['line_start']}-{m['line_end']})")
        
        # 方法分组
        groups = group_methods_by_prefix(cls['methods'])
        print(f"\n  方法分组 (按前缀):")
        for group_name, group_methods in sorted(groups.items(), key=lambda x: len(x[1]), reverse=True):
            print(f"    - {group_name}: {len(group_methods)} 个方法")
            # 显示前5个方法名
            for m in group_methods[:5]:
                print(f"      · {m['name']} ({m['total_lines']} 行)")
            if len(group_methods) > 5:
                print(f"      ... 还有 {len(group_methods) - 5} 个")
        
        print()


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("用法: python analyze_class_structure.py <文件路径>")
        sys.exit(1)
    
    file_path = Path(sys.argv[1])
    if not file_path.exists():
        print(f"文件不存在: {file_path}")
        sys.exit(1)
    
    analysis = analyze_file(file_path)
    print_analysis(analysis)

