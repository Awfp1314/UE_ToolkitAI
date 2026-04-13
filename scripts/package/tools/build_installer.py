#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
自动化打包脚本 - 一键生成安装包（重构版）

步骤:
1. 清理上次构建产物（build/、dist/）
2. 运行 PyInstaller 打包 EXE
3. 调用 Inno Setup 编译安装包
4. 保存日志到新的日志结构
5. 自动清理临时文件

日志结构:
scripts/package/logs/
├── pyinstaller/
│   ├── Error/
│   ├── warn/
│   └── Info/
└── inno/
    ├── Error/
    ├── warn/
    └── Info/
"""

import sys
import shutil
import subprocess
import threading
import time
import re
from pathlib import Path
from datetime import datetime
import glob

# 添加项目根目录到 Python 路径
# build_installer.py 位于 scripts/package/tools/
# 需要回到项目根目录：tools -> package -> scripts -> 根目录
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

# 导入版本信息
try:
    from version import VERSION
except ImportError:
    # 如果导入失败，尝试直接读取版本文件
    version_file = project_root / "version.py"
    if version_file.exists():
        # 简单解析版本文件
        with open(version_file, 'r', encoding='utf-8') as f:
            content = f.read()
            import re
            match = re.search(r'VERSION\s*=\s*["\']([^"\']+)["\']', content)
            if match:
                VERSION = match.group(1)
            else:
                VERSION = "1.0.0"
    else:
        VERSION = "1.0.0"


class ProgressSpinner:
    """进度旋转指示器"""
    
    def __init__(self, message="处理中"):
        self.message = message
        self.running = False
        self.thread = None
        # 使用简单的 ASCII 字符避免编码问题
        self.frames = ['|', '/', '-', '\\']
        self.current_frame = 0
    
    def _spin(self):
        """旋转动画"""
        while self.running:
            frame = self.frames[self.current_frame % len(self.frames)]
            print(f'\r   {frame} {self.message}...', end='', flush=True)
            self.current_frame += 1
            time.sleep(0.1)
    
    def start(self):
        """启动进度指示器"""
        self.running = True
        self.thread = threading.Thread(target=self._spin, daemon=True)
        self.thread.start()
    
    def stop(self, final_message=None):
        """停止进度指示器"""
        self.running = False
        if self.thread:
            self.thread.join()
        # 清除当前行
        print('\r' + ' ' * 80 + '\r', end='', flush=True)
        if final_message:
            print(f'   {final_message}')


def print_header(text):
    """打印标题"""
    print()
    print("=" * 60)
    print(text)
    print("=" * 60)
    print()


def pre_build_checks():
    """打包前检查
    
    检查项：
    1. 环境模式检查（开发/生产）
    2. 依赖检查
    3. 代码质量检查
    4. 版本号检查
    5. 配置文件检查
    """
    print_header("打包前检查")
    
    all_passed = True
    warnings = []
    
    # ========== 1. 环境模式检查 ==========
    print("[检查 1/5] 环境模式检查...")
    
    # 检查是否有调试代码（使用 Python 原生方法，避免依赖 grep）
    debug_patterns = [
        (r'print\s*\(\s*["\'].*DEBUG.*["\']', '发现 DEBUG 打印语句'),
        (r'logger\.debug\s*\(.*\[DEBUG\]', '发现 [DEBUG] 日志'),
        (r'import\s+pdb|pdb\.set_trace', '发现 pdb 调试代码'),
        (r'breakpoint\s*\(', '发现 breakpoint 调试代码'),
    ]
    
    debug_files = []
    search_dirs = [
        project_root / 'core',
        project_root / 'modules',
        project_root / 'ui',
    ]
    
    for search_dir in search_dirs:
        if not search_dir.exists():
            continue
            
        for py_file in search_dir.rglob("*.py"):
            # 跳过缓存目录
            if '__pycache__' in py_file.parts:
                continue
            
            try:
                with open(py_file, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
                    
                for pattern, desc in debug_patterns:
                    if re.search(pattern, content):
                        debug_files.append((desc, str(py_file.relative_to(project_root))))
                        break  # 每个文件只记录一次
                        
            except Exception:
                # 忽略无法读取的文件
                pass
    
    if debug_files:
        warnings.append("发现调试代码")
        print("   [警告] 发现以下调试代码：")
        for desc, file in debug_files[:5]:  # 只显示前5个
            print(f"      - {desc}: {file}")
        if len(debug_files) > 5:
            print(f"      ... 还有 {len(debug_files) - 5} 个文件")
    else:
        print("   [通过] 未发现明显的调试代码")
    
    # ========== 2. 依赖检查 ==========
    print("\n[检查 2/5] 依赖检查...")
    
    requirements_file = project_root / "requirements.txt"
    if requirements_file.exists():
        try:
            # 检查关键依赖（使用正确的导入名称）
            critical_deps = [
                ('PyQt6', 'PyQt6'),
                ('requests', 'requests'),
                ('Pillow', 'PIL'),  # Pillow 的导入名是 PIL
            ]
            missing_deps = []
            
            for dep_name, import_name in critical_deps:
                try:
                    __import__(import_name)
                except ImportError:
                    missing_deps.append(dep_name)
            
            if missing_deps:
                print(f"   [错误] 缺少关键依赖: {', '.join(missing_deps)}")
                all_passed = False
            else:
                print("   [通过] 关键依赖已安装")
        except Exception as e:
            warnings.append(f"依赖检查失败: {e}")
            print(f"   [警告] 依赖检查失败: {e}")
    else:
        warnings.append("未找到 requirements.txt")
        print("   [警告] 未找到 requirements.txt")
    
    # ========== 3. 代码质量检查 ==========
    print("\n[检查 3/5] 代码质量检查...")
    
    # 检查是否有语法错误
    syntax_errors = []
    for py_file in project_root.rglob("*.py"):
        # 跳过虚拟环境和缓存目录
        if any(part in py_file.parts for part in ['venv', '__pycache__', '.git', 'build', 'dist']):
            continue
        
        try:
            with open(py_file, 'r', encoding='utf-8') as f:
                compile(f.read(), str(py_file), 'exec')
        except SyntaxError as e:
            syntax_errors.append((py_file, str(e)))
            if len(syntax_errors) >= 5:  # 最多显示5个
                break
    
    if syntax_errors:
        print("   [错误] 发现语法错误：")
        for file, error in syntax_errors[:3]:
            print(f"      - {file.relative_to(project_root)}: {error[:80]}")
        all_passed = False
    else:
        print("   [通过] 未发现语法错误")
    
    # ========== 4. 版本号检查 ==========
    print("\n[检查 4/5] 版本号检查...")
    
    # 检查 version.py
    version_file = project_root / "version.py"
    if version_file.exists():
        print(f"   [信息] 当前版本: {VERSION}")
        
        # 检查版本号格式
        if not re.match(r'^\d+\.\d+\.\d+$', VERSION):
            warnings.append(f"版本号格式不规范: {VERSION}")
            print(f"   [警告] 版本号格式不规范: {VERSION} (应为 X.Y.Z)")
        else:
            print("   [通过] 版本号格式正确")
        
        # 检查 UeToolkitpack.iss 中的版本号是否一致
        iss_file = project_root / "scripts" / "package" / "config" / "UeToolkitpack.iss"
        if iss_file.exists():
            with open(iss_file, 'r', encoding='utf-8') as f:
                iss_content = f.read()
                iss_version_match = re.search(r'#define MyAppVersion "([^"]+)"', iss_content)
                if iss_version_match:
                    iss_version = iss_version_match.group(1)
                    if iss_version != VERSION:
                        warnings.append(f"版本号不一致: version.py={VERSION}, UeToolkitpack.iss={iss_version}")
                        print(f"   [警告] 版本号不一致")
                        print(f"      version.py: {VERSION}")
                        print(f"      UeToolkitpack.iss: {iss_version}")
                    else:
                        print("   [通过] 版本号一致")
    else:
        print("   [错误] 未找到 version.py")
        all_passed = False
    
    # ========== 5. 配置文件检查 ==========
    print("\n[检查 5/5] 配置文件检查...")
    
    # 检查必要的配置文件
    required_files = [
        ("scripts/package/config/ue_toolkit.spec", "PyInstaller 配置"),
        ("scripts/package/config/UeToolkitpack.iss", "Inno Setup 配置"),
        ("scripts/package/config/runtime_hook_encoding.py", "运行时钩子"),
        ("resources/tubiao.ico", "应用图标"),
    ]
    
    missing_files = []
    for file_path, desc in required_files:
        full_path = project_root / file_path
        if not full_path.exists():
            missing_files.append((file_path, desc))
    
    if missing_files:
        print("   [错误] 缺少必要文件：")
        for file_path, desc in missing_files:
            print(f"      - {desc}: {file_path}")
        all_passed = False
    else:
        print("   [通过] 所有必要文件存在")
    
    # ========== 检查总结 ==========
    print()
    print("=" * 60)
    if all_passed and not warnings:
        print("[结果] 所有检查通过，可以开始打包")
    elif all_passed and warnings:
        print(f"[结果] 检查通过但有 {len(warnings)} 个警告")
        print("\n警告列表：")
        for i, warning in enumerate(warnings, 1):
            print(f"  {i}. {warning}")
    else:
        print("[结果] 检查失败，请修复错误后再打包")
    print("=" * 60)
    print()
    
    return all_passed, warnings


def get_timestamp():
    """获取当前时间戳，格式: YYYYMMDD_HHMMSS"""
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def rotate_logs(log_dir, max_files=10):
    """日志轮转，保留最近 max_files 个文件"""
    if not log_dir.exists():
        return
    
    # 获取所有日志文件
    log_files = list(log_dir.glob("*.log"))
    if len(log_files) <= max_files:
        return
    
    # 按修改时间排序
    log_files.sort(key=lambda x: x.stat().st_mtime)
    
    # 删除最旧的文件
    files_to_delete = log_files[:-max_files]
    for file in files_to_delete:
        try:
            file.unlink()
            print(f"   [清理] 删除旧日志: {file.name}")
        except Exception as e:
            print(f"   [警告] 无法删除日志 {file.name}: {e}")


def save_log(content, log_type, tool, level="Info"):
    """
    保存日志到指定位置
    
    Args:
        content: 日志内容
        log_type: 日志类型 ('full', 'summary', 'error')
        tool: 工具名称 ('pyinstaller', 'inno')
        level: 日志级别 ('Error', 'warn', 'Info')
    """
    timestamp = get_timestamp()
    
    # 日志目录改为项目根目录的 logs/build/
    log_dir = project_root / "logs" / "build" / tool / level
    log_dir.mkdir(parents=True, exist_ok=True)
    
    # 生成文件名
    if log_type == 'full':
        filename = f"{tool}_full_{timestamp}.log"
    elif log_type == 'summary':
        filename = f"{tool}_summary_{timestamp}.log"
    elif log_type == 'error':
        filename = f"{tool}_error_{timestamp}.log"
    else:
        filename = f"{tool}_{log_type}_{timestamp}.log"
    
    log_file = log_dir / filename
    
    # 保存日志
    with open(log_file, 'w', encoding='utf-8') as f:
        f.write(content)
    
    # 日志轮转
    rotate_logs(log_dir)
    
    return log_file


def clean_build():
    """清理上次构建产物"""
    print_header("步骤 1/3: 清理旧构建文件")

    dirs_to_clean = [
        project_root / "build",
        project_root / "dist",
    ]

    cleaned = False
    for d in dirs_to_clean:
        if d.exists():
            size_mb = sum(f.stat().st_size for f in d.rglob("*") if f.is_file()) / (1024 * 1024)
            print(f"   [清理] {d.relative_to(project_root)}/ ({size_mb:.1f} MB)")
            shutil.rmtree(d)
            cleaned = True

    if cleaned:
        print("   [完成] 清理完成")
    else:
        print("   [跳过] 无需清理（没有旧构建文件）")
    return True


def build_exe():
    """使用 PyInstaller 打包 EXE"""
    
    print_header("步骤 2/3: 打包 EXE 文件")
    
    # spec文件现在在config文件夹中
    spec_file = Path(__file__).parent.parent / "config" / "ue_toolkit.spec"
    
    if not spec_file.exists():
        print(f"[错误] 找不到 {spec_file}")
        return False
    
    print(f"[信息] 配置文件: {spec_file.name}")
    print()
    
    # 启动进度指示器
    spinner = ProgressSpinner("正在打包 EXE")
    spinner.start()
    
    try:
        # 捕获 PyInstaller 输出
        result = subprocess.run(
            [sys.executable, "-m", "PyInstaller", str(spec_file), "--clean"],
            cwd=project_root,
            check=True,
            capture_output=True,
            text=True,
            encoding='utf-8',
            errors='replace'
        )
        
        # 停止进度指示器
        spinner.stop("[完成] EXE 打包完成")
        
        # 解析输出，提取错误和警告
        errors = []
        warnings = []
        info_lines = []
        
        for line in result.stdout.splitlines() + result.stderr.splitlines():
            line_lower = line.lower()
            if 'error' in line_lower or 'failed' in line_lower:
                errors.append(line)
            elif 'warning' in line_lower or 'warn' in line_lower:
                warnings.append(line)
            else:
                info_lines.append(line)
        
        # 保存完整日志
        full_log_content = "=" * 80 + "\n"
        full_log_content += "PyInstaller 完整构建日志\n"
        full_log_content += "=" * 80 + "\n\n"
        full_log_content += result.stdout
        if result.stderr:
            full_log_content += "\n" + "=" * 80 + "\n"
            full_log_content += "标准错误输出\n"
            full_log_content += "=" * 80 + "\n\n"
            full_log_content += result.stderr
        
        # 根据是否有错误/警告决定日志级别
        if errors:
            log_level = "Error"
        elif warnings:
            log_level = "warn"
        else:
            log_level = "Info"
        
        full_log_file = save_log(full_log_content, 'full', 'pyinstaller', log_level)
        
        # 生成错误和警告摘要日志
        summary_log_content = "=" * 80 + "\n"
        summary_log_content += "PyInstaller 构建摘要（仅错误和警告）\n"
        summary_log_content += "=" * 80 + "\n\n"
        
        if errors:
            summary_log_content += "[错误]:\n"
            summary_log_content += "-" * 80 + "\n"
            for error in errors:
                summary_log_content += error + "\n"
            summary_log_content += "\n"
        
        if warnings:
            summary_log_content += "[警告]:\n"
            summary_log_content += "-" * 80 + "\n"
            for warning in warnings:
                summary_log_content += warning + "\n"
            summary_log_content += "\n"
        
        if not errors and not warnings:
            summary_log_content += "[成功] 没有错误或警告\n"
        
        summary_log_file = save_log(summary_log_content, 'summary', 'pyinstaller', log_level)
        
        # 显示摘要
        if errors:
            print(f"   [警告] 发现 {len(errors)} 个错误")
        if warnings:
            print(f"   [警告] 发现 {len(warnings)} 个警告")
        
        if errors or warnings:
            print(f"   [日志] 详细日志: {summary_log_file}")
            print(f"   [日志] 完整日志: {full_log_file}")
        else:
            print(f"   [日志] 日志已保存: {full_log_file}")
        
        return True
        
    except subprocess.CalledProcessError as e:
        spinner.stop("[失败] PyInstaller 打包失败")
        
        # 保存错误日志
        error_log_content = "=" * 80 + "\n"
        error_log_content += "PyInstaller 错误日志\n"
        error_log_content += "=" * 80 + "\n\n"
        error_log_content += f"返回码: {e.returncode}\n\n"
        
        if e.stdout:
            error_log_content += "标准输出:\n"
            error_log_content += "-" * 80 + "\n"
            error_log_content += e.stdout
            error_log_content += "\n\n"
        
        if e.stderr:
            error_log_content += "标准错误:\n"
            error_log_content += "-" * 80 + "\n"
            error_log_content += e.stderr
        
        error_log_file = save_log(error_log_content, 'error', 'pyinstaller', 'Error')
        print(f"   [日志] 错误日志: {error_log_file}")
        return False
        
    except FileNotFoundError:
        spinner.stop("[失败] 找不到 pyinstaller 命令")
        print("   [提示] 请先安装: pip install pyinstaller")
        return False
    except Exception as e:
        spinner.stop(f"[失败] 发生错误: {e}")
        return False


def build_installer():
    """使用 Inno Setup 编译安装包"""
    
    print_header("步骤 3/3: 编译安装包")
    
    # iss文件现在在config文件夹中
    iss_file = Path(__file__).parent.parent / "config" / "UeToolkitpack.iss"
    
    # 查找 Inno Setup 编译器
    iscc_paths = [
        r"C:\Program Files (x86)\Inno Setup 6\ISCC.exe",
        r"C:\Program Files\Inno Setup 6\ISCC.exe",
        r"C:\Program Files (x86)\Inno Setup 5\ISCC.exe",
        r"C:\Program Files\Inno Setup 5\ISCC.exe",
    ]
    
    iscc_exe = None
    for path in iscc_paths:
        if Path(path).exists():
            iscc_exe = path
            break
    
    if not iscc_exe:
        print("[警告] 找不到 Inno Setup 编译器")
        print()
        print("请手动执行以下步骤:")
        print(f"1. 打开 Inno Setup")
        print(f"2. 打开文件: {iss_file}")
        print(f"3. 点击 Build -> Compile")
        print()
        print("或者安装 Inno Setup:")
        print("   下载地址: https://jrsoftware.org/isdl.php")
        return False
    
    print(f"[信息] 编译器: {iscc_exe}")
    print(f"[信息] 脚本: {iss_file.name}")
    print()
    
    # 启动进度指示器
    spinner = ProgressSpinner("正在编译安装包")
    spinner.start()
    
    try:
        result = subprocess.run(
            [iscc_exe, str(iss_file)],
            check=True,
            capture_output=True,
            text=True,
            encoding='utf-8',
            errors='replace'
        )
        
        # 停止进度指示器
        spinner.stop("[完成] 安装包编译完成")
        
        # 解析输出，提取错误和警告
        errors = []
        warnings = []
        
        for line in result.stdout.splitlines() + result.stderr.splitlines():
            line_lower = line.lower()
            if 'error' in line_lower or 'failed' in line_lower:
                errors.append(line)
            elif 'warning' in line_lower or 'warn' in line_lower:
                warnings.append(line)
        
        # 保存完整日志
        full_log_content = "=" * 80 + "\n"
        full_log_content += "Inno Setup 编译日志\n"
        full_log_content += "=" * 80 + "\n\n"
        full_log_content += result.stdout
        if result.stderr:
            full_log_content += "\n" + "=" * 80 + "\n"
            full_log_content += "标准错误输出\n"
            full_log_content += "=" * 80 + "\n\n"
            full_log_content += result.stderr
        
        # 根据是否有错误/警告决定日志级别
        if errors:
            log_level = "Error"
        elif warnings:
            log_level = "warn"
        else:
            log_level = "Info"
        
        full_log_file = save_log(full_log_content, 'full', 'inno', log_level)
        
        # 生成错误和警告摘要日志
        if errors or warnings:
            summary_log_content = "=" * 80 + "\n"
            summary_log_content += "Inno Setup 编译摘要（仅错误和警告）\n"
            summary_log_content += "=" * 80 + "\n\n"
            
            if errors:
                summary_log_content += "[错误]:\n"
                summary_log_content += "-" * 80 + "\n"
                for error in errors:
                    summary_log_content += error + "\n"
                summary_log_content += "\n"
            
            if warnings:
                summary_log_content += "[警告]:\n"
                summary_log_content += "-" * 80 + "\n"
                for warning in warnings:
                    summary_log_content += warning + "\n"
                summary_log_content += "\n"
            
            summary_log_file = save_log(summary_log_content, 'summary', 'inno', log_level)
            print(f"   [日志] 详细日志: {summary_log_file}")
        
        print(f"   [日志] 完整日志: {full_log_file}")
        
        # 显示输出文件位置（现在在桌面）
        desktop = Path.home() / "Desktop"
        if desktop.exists():
            output_files = list(desktop.glob("*Setup*.exe"))
            if output_files:
                print()
                print("[输出] 安装包位置（桌面）:")
                for file in output_files:
                    print(f"   {file}")
        
        return True
        
    except subprocess.CalledProcessError as e:
        spinner.stop("[失败] Inno Setup 编译失败")
        
        # 保存错误日志
        error_log_content = "=" * 80 + "\n"
        error_log_content += "Inno Setup 错误日志\n"
        error_log_content += "=" * 80 + "\n\n"
        error_log_content += f"返回码: {e.returncode}\n\n"
        
        if e.stdout:
            error_log_content += "标准输出:\n"
            error_log_content += "-" * 80 + "\n"
            error_log_content += e.stdout
            error_log_content += "\n\n"
        
        if e.stderr:
            error_log_content += "标准错误:\n"
            error_log_content += "-" * 80 + "\n"
            error_log_content += e.stderr
        
        error_log_file = save_log(error_log_content, 'error', 'inno', 'Error')
        print(f"   [日志] 错误日志: {error_log_file}")
        return False
    except Exception as e:
        spinner.stop(f"[失败] 发生错误: {e}")
        return False


def cleanup_after_build():
    """打包完成后清理dist和build文件夹"""
    print_header("清理阶段: 删除临时构建文件")
    
    dirs_to_clean = [
        project_root / "build",
        project_root / "dist",
    ]
    
    cleaned = False
    for d in dirs_to_clean:
        if d.exists():
            try:
                size_mb = sum(f.stat().st_size for f in d.rglob("*") if f.is_file()) / (1024 * 1024)
                print(f"   [清理] 删除 {d.relative_to(project_root)}/ ({size_mb:.1f} MB)")
                shutil.rmtree(d)
                cleaned = True
            except Exception as e:
                print(f"   [警告] 无法删除 {d}: {e}")
    
    if cleaned:
        print("   [完成] 临时文件清理完成")
    else:
        print("   [跳过] 没有临时文件需要清理")
    
    return True

def main():
    """主函数"""
    
    print("=" * 60)
    print("UE Toolkit - 自动化打包脚本（重构版）")
    print("=" * 60)
    print()
    print(f"[版本] {VERSION}")
    print(f"[日志] 日志将保存到: logs/build/")
    print()
    
    # 步骤 0: 打包前检查
    passed, warnings = pre_build_checks()
    
    if not passed:
        print()
        print("[错误] 打包前检查未通过，请修复错误后重试")
        return False
    
    if warnings:
        print()
        response = input(f"检查发现 {len(warnings)} 个警告，是否继续打包? (y/n): ").strip().lower()
        if response not in ['y', 'yes', '是']:
            print()
            print("[取消] 已取消打包")
            return True
    
    # 步骤 1: 清理旧构建
    if not clean_build():
        return False
    
    # 询问是否继续打包
    print()
    response = input("是否继续打包 EXE 和安装包? (y/n): ").strip().lower()
    if response not in ['y', 'yes', '是']:
        print()
        print("[取消] 已取消打包")
        return True
    
    # 步骤 2: 打包 EXE
    if not build_exe():
        print()
        print("[失败] EXE 打包失败")
        return False
    
    # 步骤 3: 编译安装包
    if not build_installer():
        print()
        print("[警告] 安装包编译未完成")
        print("   请手动使用 Inno Setup 编译")
        # 这里不返回False，因为EXE已经打包成功
    
    # 步骤 4: 自动清理临时文件
    print()
    print("正在自动清理临时构建文件...")
    cleanup_after_build()
    
    print()
    print("=" * 60)
    print("[成功] 打包流程完成！")
    print("=" * 60)
    print()
    print(f"[版本] {VERSION}")
    print(f"[日志] 查看详细日志: logs/build/")
    
    # 显示安装包位置
    desktop = Path.home() / "Desktop"
    if desktop.exists():
        output_files = list(desktop.glob("*Setup*.exe"))
        if output_files:
            print(f"[安装包] 桌面位置:")
            for file in output_files:
                print(f"   {file}")
    
    print()
    return True


if __name__ == "__main__":
    try:
        success = main()
        
        if not success:
            sys.exit(1)
            
    except KeyboardInterrupt:
        print()
        print()
        print("[取消] 用户取消操作")
        sys.exit(1)
        
    except Exception as e:
        print()
        print(f"[错误] 发生错误: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    
