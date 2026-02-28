# -*- coding: utf-8 -*-
"""
打包优化验证脚本

用于验证打包优化效果，检查文件大小、依赖排除情况等
"""

import os
import sys
import zipfile
from pathlib import Path
from typing import Dict, List, Tuple, Any
from dataclasses import dataclass


@dataclass
class VerificationResult:
    """验证结果数据模型"""
    
    # 文件大小信息
    current_size_mb: float
    baseline_size_mb: float
    reduction_percent: float
    
    # 依赖检查
    excluded_deps_found: List[str]  # 不应该存在但存在的依赖
    required_deps_missing: List[str]  # 应该存在但缺失的依赖
    
    # 总体状态
    success: bool
    warnings: List[str]
    errors: List[str]


class PackagingVerifier:
    """打包优化验证器"""
    
    # 应该被排除的依赖（不应该在打包结果中出现）
    EXCLUDED_DEPS = [
        'torch', 'transformers', 'sentence_transformers',
        'scipy', 'sklearn', 'scikit-learn', 'faiss',
        'numpy', 'moviepy', 'onnxruntime', 'tensorboard',
        'pandas', 'matplotlib', 'tensorflow'
    ]
    
    # 必需的依赖（应该在打包结果中）
    REQUIRED_DEPS = [
        'PyQt6', 'PIL', 'psutil', 'pypinyin',
        'requests', 'httpx', 'github', 'yaml'
    ]
    
    def __init__(self, exe_path: str):
        """初始化验证器
        
        Args:
            exe_path: 打包后的 EXE 文件路径
        """
        self.exe_path = Path(exe_path)
        if not self.exe_path.exists():
            raise FileNotFoundError(f"EXE 文件不存在: {exe_path}")
    
    def verify_size(self, baseline_mb: float = 311.28) -> Dict[str, Any]:
        """验证文件大小
        
        Args:
            baseline_mb: 优化前的基准大小（MB）
            
        Returns:
            包含大小信息和优化百分比的字典
        """
        size_bytes = self.exe_path.stat().st_size
        size_mb = size_bytes / (1024 * 1024)
        reduction_mb = baseline_mb - size_mb
        reduction_percent = (reduction_mb / baseline_mb) * 100
        
        return {
            'current_size_mb': round(size_mb, 2),
            'baseline_size_mb': baseline_mb,
            'reduction_mb': round(reduction_mb, 2),
            'reduction_percent': round(reduction_percent, 2),
            'meets_target': size_mb <= 80.0  # 目标是 50-80MB
        }
    
    def verify_dependencies(self) -> Dict[str, Any]:
        """验证依赖是否正确排除
        
        注意：这是一个简化的检查，只检查文件名
        完整检查需要解压 EXE 并分析内容
        
        Returns:
            依赖检查结果字典
        """
        # 由于 PyInstaller 单文件模式，我们无法直接检查内部依赖
        # 这里返回一个占位结果
        return {
            'excluded_deps_found': [],
            'required_deps_missing': [],
            'note': '单文件模式无法直接检查依赖，请通过运行测试验证'
        }
    
    def generate_report(self, size_info: Dict[str, Any], deps_info: Dict[str, Any]) -> str:
        """生成优化报告
        
        Args:
            size_info: 大小验证结果
            deps_info: 依赖验证结果
            
        Returns:
            格式化的报告文本
        """
        report = []
        report.append("=" * 60)
        report.append("打包优化验证报告")
        report.append("=" * 60)
        report.append("")
        
        # 文件信息
        report.append("📦 文件信息")
        report.append(f"  文件路径: {self.exe_path}")
        report.append(f"  当前大小: {size_info['current_size_mb']} MB")
        report.append(f"  优化前大小: {size_info['baseline_size_mb']} MB")
        report.append("")
        
        # 优化效果
        report.append("📊 优化效果")
        report.append(f"  减少大小: {size_info['reduction_mb']} MB")
        report.append(f"  减少比例: {size_info['reduction_percent']}%")
        
        if size_info['meets_target']:
            report.append(f"  ✅ 达到目标（≤ 80MB）")
        else:
            report.append(f"  ⚠️  未达到目标（目标 50-80MB）")
        report.append("")
        
        # 依赖检查
        report.append("🔍 依赖检查")
        report.append(f"  {deps_info['note']}")
        report.append("")
        
        # 建议
        report.append("💡 建议")
        if size_info['current_size_mb'] > 80:
            report.append("  - 体积仍然较大，可能需要进一步优化")
            report.append("  - 检查是否有其他大型库被意外包含")
        elif size_info['current_size_mb'] < 50:
            report.append("  - 体积非常理想！")
        else:
            report.append("  - 体积在目标范围内，优化效果良好")
        
        report.append("")
        report.append("  下一步：")
        report.append("  1. 运行 EXE 测试基本功能")
        report.append("  2. 测试 Ollama 聊天功能")
        report.append("  3. 测试 API Key 聊天功能")
        report.append("  4. 测试工具调用功能")
        report.append("")
        report.append("=" * 60)
        
        return "\n".join(report)
    
    def run_verification(self, baseline_mb: float = 311.28) -> VerificationResult:
        """运行完整验证
        
        Args:
            baseline_mb: 优化前的基准大小（MB）
            
        Returns:
            验证结果对象
        """
        size_info = self.verify_size(baseline_mb)
        deps_info = self.verify_dependencies()
        
        # 生成报告
        report = self.generate_report(size_info, deps_info)
        print(report)
        
        # 构建结果
        success = size_info['meets_target']
        warnings = []
        errors = []
        
        if not success:
            warnings.append(f"体积 {size_info['current_size_mb']}MB 超过目标 80MB")
        
        return VerificationResult(
            current_size_mb=size_info['current_size_mb'],
            baseline_size_mb=baseline_mb,
            reduction_percent=size_info['reduction_percent'],
            excluded_deps_found=deps_info['excluded_deps_found'],
            required_deps_missing=deps_info['required_deps_missing'],
            success=success,
            warnings=warnings,
            errors=errors
        )


def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description='验证打包优化效果')
    parser.add_argument('exe_path', nargs='?', default='dist/UE_Toolkit.exe',
                        help='EXE 文件路径（默认: dist/UE_Toolkit.exe）')
    parser.add_argument('--baseline', type=float, default=311.28,
                        help='优化前的基准大小（MB，默认: 311.28）')
    
    args = parser.parse_args()
    
    try:
        verifier = PackagingVerifier(args.exe_path)
        result = verifier.run_verification(args.baseline)
        
        # 返回状态码
        sys.exit(0 if result.success else 1)
        
    except FileNotFoundError as e:
        print(f"❌ 错误: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"❌ 验证失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()
