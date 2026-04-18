# -*- coding: utf-8 -*-

"""
编辑工程信息对话框
支持重命名项目、修改路径、设置分类
支持蓝图和C++项目，C++项目重命名前自动备份，编译失败自动回滚
"""

import json
import shutil
import subprocess
import sys
from pathlib import Path
from typing import List, Optional

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QLineEdit, QComboBox, QWidget,
    QFileDialog, QProgressDialog, QApplication,
    QScrollArea, QFrame, QSizePolicy
)
from PyQt6.QtCore import Qt, QPoint, pyqtSignal, QThread, QTimer
from PyQt6.QtGui import QColor, QPainter, QPen

from core.logger import get_logger
from modules.asset_manager.ui.message_dialog import MessageDialog
from modules.asset_manager.ui.confirm_dialog import ConfirmDialog

logger = get_logger(__name__)


def _get_backup_dir() -> Path:
    """获取备份目录"""
    from PyQt6.QtCore import QStandardPaths
    app_data = QStandardPaths.writableLocation(
        QStandardPaths.StandardLocation.AppDataLocation
    )
    return Path(app_data) / "my_projects" / "rename_backup"


def _find_engine_path(version: str) -> Optional[Path]:
    """根据版本号查找引擎安装路径"""
    try:
        from modules.my_projects.logic.engine_scanner import EngineScanner
        engines = EngineScanner.scan_installed_engines()
        for e in engines:
            if e.version == version:
                return e.install_dir
    except Exception as ex:
        logger.warning(f"查找引擎路径失败: {ex}")
    return None


# ══════════════════════════════════════════════════════════════
# 改名详情弹窗
# ══════════════════════════════════════════════════════════════

class _SpinnerLabel(QLabel):
    """旋转加载图标（纯 CSS 动画占位，用定时器驱动文字旋转）"""
    _FRAMES = ["◐", "◓", "◑", "◒"]

    def __init__(self, parent=None):
        super().__init__(parent)
        self._idx = 0
        self.setText(self._FRAMES[0])
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(120)

    def _tick(self):
        self._idx = (self._idx + 1) % len(self._FRAMES)
        self.setText(self._FRAMES[self._idx])

    def stop(self):
        self._timer.stop()


class RenameProgressDialog(QDialog):
    """改名进度详情弹窗

    生命周期：
    - 改名开始前创建，可立即 show()
    - 改名过程中通过 set_stage_running/set_stage_done 驱动
    - 改名完成后通过 finish(warnings, open_cb) 切换到结果状态
    """

    STAGE_NAMES = [
        "创建安全备份",
        "重命名项目目录",
        "同步项目配置",
        "更新项目文件",
        "完成校验"]

    def __init__(self, old_name: str, new_name: str, total: int, open_cb, parent=None):
        super().__init__(parent)
        self._open_cb = open_cb
        self._total = total
        self._old_name = old_name
        self._new_name = new_name
        self._spinners = {}   # stage_idx -> _SpinnerLabel
        self._status_icons = {}  # stage_idx -> QLabel
        self._finished = False

        self.setModal(False)
        self.setFixedWidth(400)
        self.setWindowTitle("改名进度")
        self.setWindowFlags(Qt.WindowType.Dialog | Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self._init_ui(total)

    def _init_ui(self, total: int):
        # 外层容器
        container = QWidget(self)
        container.setObjectName("RenameResultContainer")
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.addWidget(container)

        self._main = QVBoxLayout(container)
        self._main.setContentsMargins(28, 24, 28, 20)
        self._main.setSpacing(10)

        # ── 标题 ──
        title = QLabel("项目改名进行中")
        title.setObjectName("RenameResultTitle")
        self._main.addWidget(title)
        self._title_label = title

        summary = QLabel(f"{self._old_name}  →  {self._new_name}")
        summary.setObjectName("RenameResultSummary")
        self._main.addWidget(summary)

        self._main.addSpacing(6)

        # ── 阶段列表 ──
        for i in range(total):
            row = QHBoxLayout()
            row.setSpacing(10)

            # 状态图标（初始灰点）
            icon = QLabel("○")
            icon.setObjectName("RenameStageIcon")
            icon.setFixedWidth(18)
            icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
            icon.setStyleSheet("color: #555555; font-size: 14px;")
            self._status_icons[i] = icon
            row.addWidget(icon)

            stage_name = self.STAGE_NAMES[i] if i < len(self.STAGE_NAMES) else f"阶段 {i+1}"
            lbl = QLabel(f"阶段 {i+1}/{total} · {stage_name}")
            lbl.setObjectName("RenameResultDoneItem")
            lbl.setStyleSheet("color: #666666;")
            row.addWidget(lbl, 1)
            self._status_icons[i]._row_label = lbl  # 方便后续改色

            self._main.addLayout(row)

        self._main.addSpacing(8)

        # ── 结果区（初始隐藏）──
        self._result_widget = QWidget()
        result_layout = QVBoxLayout(self._result_widget)
        result_layout.setContentsMargins(0, 0, 0, 0)
        result_layout.setSpacing(6)

        self._compat_label = QLabel("")
        self._compat_label.setObjectName("RenameResultCompat")
        self._compat_label.setWordWrap(True)
        result_layout.addWidget(self._compat_label)

        self._tip_label = QLabel("")
        self._tip_label.setObjectName("RenameResultTip")
        self._tip_label.setWordWrap(True)
        result_layout.addWidget(self._tip_label)

        self._result_widget.setVisible(False)
        self._main.addWidget(self._result_widget)

        # ── 按钮区 ──
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(10)
        btn_layout.addStretch()

        # 「后台执行」按钮：执行中显示，点击后隐藏弹窗，进度继续在状态指示器显示
        self._btn_background = QPushButton("后台执行")
        self._btn_background.setObjectName("CancelButton")
        self._btn_background.setFixedSize(90, 32)
        self._btn_background.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_background.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._btn_background.clicked.connect(self.hide)
        self._btn_background.setVisible(True)
        btn_layout.addWidget(self._btn_background)

        self._btn_close = QPushButton("关闭")
        self._btn_close.setObjectName("RenameResultBtnDone")
        self._btn_close.setFixedSize(80, 32)
        self._btn_close.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_close.clicked.connect(self.accept)
        self._btn_close.setVisible(False)
        btn_layout.addWidget(self._btn_close)

        self._btn_open = QPushButton("打开项目")
        self._btn_open.setObjectName("RenameResultBtnOpen")
        self._btn_open.setFixedSize(100, 32)
        self._btn_open.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_open.setDefault(True)
        self._btn_open.clicked.connect(self._do_open)
        self._btn_open.setVisible(False)
        btn_layout.addWidget(self._btn_open)

        self._main.addLayout(btn_layout)

        self.adjustSize()

    def set_stage_running(self, stage_idx: int):
        """将指定阶段设置为运行中（旋转图标，文字高亮）"""
        icon_lbl = self._status_icons.get(stage_idx)
        if not icon_lbl:
            return
        # 替换为 spinner
        spinner = _SpinnerLabel()
        spinner.setObjectName("RenameStageIcon")
        spinner.setFixedWidth(18)
        spinner.setAlignment(Qt.AlignmentFlag.AlignCenter)
        spinner.setStyleSheet("color: #4A9EFF; font-size: 14px;")
        self._spinners[stage_idx] = spinner

        # 在布局中替换旧图标
        layout = icon_lbl.parent()
        # 遍历父容器的布局行
        for i in range(self._main.count()):
            item = self._main.itemAt(i)
            if item and item.layout():
                row_layout = item.layout()
                for j in range(row_layout.count()):
                    w = row_layout.itemAt(j).widget()
                    if w is icon_lbl:
                        row_layout.removeWidget(icon_lbl)
                        icon_lbl.hide()
                        row_layout.insertWidget(j, spinner)
                        break

        # 文字高亮
        if hasattr(icon_lbl, '_row_label'):
            icon_lbl._row_label.setStyleSheet("color: #e0e0e0; font-weight: bold;")

        self._status_icons[stage_idx] = spinner  # 更新引用备用

    def set_stage_done(self, stage_idx: int):
        """将指定阶段设置为已完成（绿色对号）"""
        # 停止 spinner
        spinner = self._spinners.pop(stage_idx, None)
        if spinner:
            spinner.stop()
            # 替换回静态图标
            for i in range(self._main.count()):
                item = self._main.itemAt(i)
                if item and item.layout():
                    row_layout = item.layout()
                    for j in range(row_layout.count()):
                        w = row_layout.itemAt(j).widget()
                        if w is spinner:
                            row_layout.removeWidget(spinner)
                            spinner.hide()
                            done_icon = QLabel("✓")
                            done_icon.setObjectName("RenameStageIcon")
                            done_icon.setFixedWidth(18)
                            done_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
                            done_icon.setStyleSheet("color: #4CAF50; font-size: 14px; font-weight: bold;")
                            row_layout.insertWidget(j, done_icon)
                            # 更新行文字颜色
                            for k in range(row_layout.count()):
                                lw = row_layout.itemAt(k).widget()
                                if isinstance(lw, QLabel) and lw is not done_icon:
                                    lw.setStyleSheet("color: #4CAF50;")
                            break
        else:
            # 直接修改静态图标
            icon_lbl = self._status_icons.get(stage_idx)
            if icon_lbl and isinstance(icon_lbl, QLabel):
                icon_lbl.setText("✓")
                icon_lbl.setStyleSheet("color: #4CAF50; font-size: 14px; font-weight: bold;")

    def finish(self, warnings: list):
        """改名全部完成：显示结果区和操作按钮"""
        self._finished = True
        self._title_label.setText("项目改名完成")

        high_risk = sum(1 for w in warnings if w.startswith("⚠️"))
        low_risk = len(warnings) - high_risk

        if high_risk > 0:
            self._compat_label.setText(
                f"兼容性状态：已启用兼容处理\n检测到历史引用 {high_risk} 处，已自动映射"
            )
            self._tip_label.setText("建议首次打开项目后检查 GameMode、PlayerController 等关键类")
        elif low_risk > 0:
            self._compat_label.setText(
                "检测到少量普通文本残留\n这些内容通常是显示名称、注释或描述信息，不影响项目运行"
            )
            self._tip_label.setText("核心文件已更新完成，可直接打开项目")
        else:
            self._compat_label.setText(
                "本次改名未发现历史脚本引用\n项目名称、配置和项目文件已全部同步完成"
            )
            self._tip_label.setText("改名已完美完成，可直接打开项目")

        self._result_widget.setVisible(True)
        self._btn_background.setVisible(False)
        self._btn_close.setVisible(True)
        self._btn_open.setVisible(True)
        self.adjustSize()

        # 若弹窗不可见则强制弹出
        if not self.isVisible():
            self.show()
            self._center_on_parent()

    def _do_open(self):
        self.accept()
        if self._open_cb:
            self._open_cb()

    def _center_on_parent(self):
        p = self.parent()
        if p:
            pg = p.geometry()
            x = pg.x() + (pg.width() - self.width()) // 2
            y = pg.y() + (pg.height() - self.height()) // 2
            self.move(x, y)


# ══════════════════════════════════════════════════════════════
# 改名进度控制器（驱动状态指示器平滑动画 + 详情弹窗）
# ══════════════════════════════════════════════════════════════

class _RenameProgressController:
    """
    驱动规则：
    - 总最短时长 TARGET_TOTAL_S = 1.5 秒，分配到每阶段
    - 若某阶段实际耗时超过分配时长，不等待，直接推进
    - 进度条从 0 平滑动画到 100，全程连续（用 QTimer @60fps）
    - 同时驱动 RenameProgressDialog 的阶段图标切换
    """
    TARGET_TOTAL_S = 1.5

    def __init__(self, total: int, main_window, progress_dialog: RenameProgressDialog):
        self._total = total
        self._mw = main_window
        self._dlg = progress_dialog
        self._current_stage = 0          # 当前阶段下标（0-based）
        self._stage_start_times = []     # 各阶段实际开始时间
        self._stage_alloc = self.TARGET_TOTAL_S / total  # 每阶段分配时长（秒）

        # 平滑进度动画
        self._smooth_progress = 0.0      # 当前显示进度（0.0-100.0）
        self._target_progress = 0.0      # 目标进度
        self._anim_timer = QTimer()
        self._anim_timer.timeout.connect(self._anim_tick)
        self._anim_timer.start(16)       # ~60fps

        self._rename_start = None        # 整个改名的开始时间

    def start(self):
        """启动控制器"""
        import time
        self._rename_start = time.time()

    def enter_stage(self, stage: int, title: str, detail: str):
        """进入第 stage 阶段（1-based），更新 UI"""
        import time
        idx = stage - 1
        self._current_stage = idx
        self._stage_start_times.append(time.time())

        # 目标进度：当前阶段开始位置
        self._target_progress = (idx / self._total) * 100.0

        # 驱动详情弹窗
        if self._dlg:
            self._dlg.set_stage_running(idx)

        # 驱动主窗口状态指示器
        if self._mw:
            label = f"阶段 {stage}/{self._total} · {title}"
            self._mw.show_status(label, detail, int(self._smooth_progress))
            QApplication.processEvents()

    def leave_stage(self, stage: int):
        """完成第 stage 阶段，等待该阶段最少时长（如总时长未超预算）"""
        import time
        idx = stage - 1

        # 等待该阶段最短显示时间（从整个改名开始算总预算）
        if self._rename_start is not None:
            elapsed_total = time.time() - self._rename_start
            expected_min = stage * self._stage_alloc   # 到本阶段结束应消耗的最少时间
            remaining = expected_min - elapsed_total
            if remaining > 0:
                deadline = time.time() + remaining
                while time.time() < deadline:
                    QApplication.processEvents()
                    time.sleep(0.016)

        # 驱动详情弹窗图标
        if self._dlg:
            self._dlg.set_stage_done(idx)

        # 进度推进到本阶段结束位置
        self._target_progress = (stage / self._total) * 100.0

    def finish(self, warnings: list):
        """所有阶段完成"""
        self._target_progress = 100.0
        # 等动画跑到 100 再收尾
        import time
        deadline = time.time() + 0.3
        while time.time() < deadline:
            QApplication.processEvents()
            time.sleep(0.016)

        self._anim_timer.stop()
        if self._dlg:
            self._dlg.finish(warnings)
        if self._mw:
            self._mw.hide_status()

    def stop(self):
        """强制停止（出错/回滚时调用）"""
        self._anim_timer.stop()
        if self._mw:
            self._mw.hide_status()

    def _anim_tick(self):
        """60fps 平滑进度动画"""
        if self._smooth_progress < self._target_progress:
            step = max(0.3, min(3.0, (self._target_progress - self._smooth_progress) * 0.12))
            self._smooth_progress = min(self._smooth_progress + step, self._target_progress)
            if self._mw and hasattr(self._mw, 'set_status_progress_smooth'):
                self._mw.set_status_progress_smooth(int(self._smooth_progress))


class _CompileThread(QThread):
    """后台编译线程"""
    
    progress = pyqtSignal(str)  # 实时输出编译日志
    status_updated = pyqtSignal(str)  # 状态更新（用于状态标签）

    def __init__(self, engine_path: Path, project_path: Path, module_name: str):
        super().__init__()
        self.engine_path = engine_path
        self.project_path = project_path
        self.module_name = module_name
        self.success = False
        self.message = ""
        self.full_log = ""  # 完整日志

    @staticmethod
    def _decode_output(raw: bytes) -> str:
        """解码编译输出，UE Build.bat 在中文 Windows 下输出 GBK"""
        if not raw:
            return ""
        for enc in ('utf-8', 'gbk', 'cp936', 'latin-1'):
            try:
                return raw.decode(enc)
            except (UnicodeDecodeError, ValueError):
                continue
        return raw.decode('latin-1')  # latin-1 永远不会失败

    def run(self):
        try:
            build_bat = self.engine_path / "Engine" / "Build" / "BatchFiles" / "Build.bat"
            if not build_bat.exists():
                self.success = False
                self.message = f"找不到 Build.bat: {build_bat}"
                self.progress.emit(f"❌ 错误: {self.message}")
                self.status_updated.emit("❌ 编译失败")
                return

            uproject = list(self.project_path.glob("*.uproject"))
            if not uproject:
                self.success = False
                self.message = "找不到 .uproject 文件"
                self.progress.emit(f"❌ 错误: {self.message}")
                self.status_updated.emit("❌ 编译失败")
                return

            uproject_path = str(uproject[0]).replace("/", "\\")

            cmd = f'cmd /c ""{build_bat}" {self.module_name}Editor Win64 Development -Project="{uproject_path}" -WaitMutex -FromMsBuild"'

            logger.info(f"编译命令: {cmd}")
            self.status_updated.emit("🔨 正在编译...")
            self.progress.emit(f"模块: {self.module_name}")
            self.progress.emit(f"项目: {self.project_path}")
            self.progress.emit(f"引擎: {self.engine_path}")
            self.progress.emit("-" * 60)

            # 使用 Popen 实时读取输出
            process = subprocess.Popen(
                cmd,
                shell=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                cwd=str(self.project_path)
            )

            full_output = []
            while True:
                line = process.stdout.readline()
                if not line and process.poll() is not None:
                    break
                if line:
                    decoded = self._decode_output(line).strip()
                    if decoded:
                        full_output.append(decoded)
                        # 只显示重要的行
                        lower = decoded.lower()
                        if any(x in lower for x in ['compiling', 'linking', 'error', 'warning', 'building', 'generating', 'failed', 'success']):
                            self.progress.emit(decoded)

            return_code = process.wait()
            self.full_log = "\n".join(full_output)

            if self.full_log.strip():
                logger.info(f"编译输出:\n{self.full_log[-2000:]}")

            output_lower = self.full_log.lower()
            has_compile_error = any(
                x in output_lower
                for x in [': error c', ': error lnk', 'build failed', 'unable to build']
            )

            if not has_compile_error and return_code == 0:
                self.success = True
                self.message = "编译成功"
                self.progress.emit("-" * 60)
                self.progress.emit("✅ 编译成功！")
                self.status_updated.emit("✅ 编译成功")
            else:
                lines = [l for l in self.full_log.splitlines() if "error" in l.lower()]
                self.success = False
                self.message = "\n".join(lines[-5:]) if lines else f"编译失败 (返回码: {return_code})"
                self.progress.emit("-" * 60)
                self.progress.emit(f"❌ 编译失败！")
                self.status_updated.emit("❌ 编译失败")
                if lines:
                    self.progress.emit("\n错误信息:")
                    for line in lines[-5:]:
                        self.progress.emit(line)

        except subprocess.TimeoutExpired:
            self.success = False
            self.message = "编译超时（超过10分钟）"
            self.progress.emit(f"❌ {self.message}")
            self.status_updated.emit("❌ 编译超时")
        except Exception as e:
            self.success = False
            self.message = f"编译异常: {e}"
            self.progress.emit(f"❌ {self.message}")
            self.status_updated.emit("❌ 编译异常")


class EditProjectDialog(QDialog):
    """编辑工程信息对话框"""

    project_updated = pyqtSignal(str, str, str, str)
    request_stop_watching = pyqtSignal(str)  # 新增：请求停止监听项目
    rename_completed = pyqtSignal(str, str, str, str)  # (old_path, new_path, new_name, new_category) 改名完成后发射

    def __init__(
        self,
        project_name: str,
        project_path: str,
        project_version: str,
        current_category: str,
        categories: List[str],
        parent=None
    ):
        super().__init__(parent)
        self.project_name = project_name
        self.project_path = project_path
        self.project_version = project_version
        self.current_category = current_category
        self.categories = categories
        self.drag_position = QPoint()

        self.is_cpp_project = self._detect_cpp_project()
        self._backup_path = None  # 备份路径
        self._old_folder_name = None  # 旧文件夹名（用于回滚）

        self._init_ui()

    def _detect_cpp_project(self) -> bool:
        """判断是否为 C++ 项目

        判定规则（更稳健）：
        1) .uproject 的 Modules 非空 → C++ 项目
        2) 或 Source 下存在 *.Target.cs → C++ 项目
        其余视为蓝图项目
        """
        project_dir = Path(self.project_path)

        # 1) 以 .uproject 的 Modules 为主判定
        try:
            uproject_files = list(project_dir.glob("*.uproject"))
            if uproject_files:
                with open(uproject_files[0], 'r', encoding='utf-8') as f:
                    data = json.load(f)
                modules = data.get('Modules', [])
                if isinstance(modules, list) and len(modules) > 0:
                    return True
        except Exception as e:
            logger.warning(f"读取 .uproject 判定项目类型失败: {e}")

        # 2) 回退到 Source/Target 规则
        source_dir = project_dir / "Source"
        return source_dir.exists() and any(source_dir.glob("*.Target.cs"))

    @staticmethod
    @staticmethod
    def _detect_file_encoding(file_path: Path) -> str:
        """检测文件编码：优先读取 BOM，再回退到内容探测

        UE ini 文件常见编码：
        - UTF-16 LE with BOM (FF FE)  → utf-16-le
        - UTF-16 BE with BOM (FE FF)  → utf-16-be
        - UTF-8 with BOM (EF BB BF)   → utf-8-sig
        - UTF-8 without BOM           → utf-8
        """
        try:
            raw = file_path.read_bytes()
        except Exception:
            return 'utf-8'

        # 1. BOM 优先检测（最可靠）
        if raw[:2] == b'\xff\xfe':
            return 'utf-16-le'
        if raw[:2] == b'\xfe\xff':
            return 'utf-16-be'
        if raw[:3] == b'\xef\xbb\xbf':
            return 'utf-8-sig'

        # 2. 无 BOM：尝试 UTF-8，失败则用 GBK
        try:
            raw.decode('utf-8')
            return 'utf-8'
        except (UnicodeDecodeError, ValueError):
            pass
        try:
            raw.decode('gbk')
            return 'gbk'
        except (UnicodeDecodeError, ValueError):
            pass
        return 'utf-8'

    def _check_ue_running(self, project_path: Path) -> bool:
        """检查 UE 编辑器是否正在运行该项目（轻量检测，避免崩溃）"""
        import psutil
        project_name = project_path.name
        
        try:
            for proc in psutil.process_iter(['name']):
                try:
                    proc_name = proc.info.get('name', '')
                    if proc_name not in ['UnrealEditor.exe', 'UE4Editor.exe', 'UnrealEditor-Win64-Debug.exe']:
                        continue
                    
                    # 只检查进程名，不访问 cmdline（避免触发 UE 崩溃）
                    # 如果有 UE 进程在运行，就假设可能在使用该项目
                    return True
                    
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
        except Exception as e:
            logger.warning(f"检测 UE 进程失败: {e}")
            return False
        
        return False

    def _find_and_kill_locking_processes(self, path: Path) -> tuple[bool, str]:
        """查找并停止占用文件夹的非 UE 进程（轻量检测，避免崩溃）
        
        Returns:
            (success, message)
        """
        import psutil
        path_str = str(path).lower()
        killed_processes = []
        
        try:
            for proc in psutil.process_iter(['name', 'pid']):
                try:
                    proc_name = proc.info.get('name', '')
                    
                    # 跳过 UE 进程（不检测是否占用，避免崩溃）
                    if proc_name in ['UnrealEditor.exe', 'UE4Editor.exe', 'UnrealEditor-Win64-Debug.exe']:
                        continue
                    
                    # 只检查工作目录，不检查打开的文件（避免访问敏感信息）
                    try:
                        cwd = proc.cwd()
                        if cwd and cwd.lower().startswith(path_str):
                            proc.kill()
                            killed_processes.append(proc_name)
                            logger.info(f"已停止占用进程: {proc_name} (PID: {proc.info['pid']})")
                    except (psutil.NoSuchProcess, psutil.AccessDenied):
                        continue
                        
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
        except Exception as e:
            logger.warning(f"查找占用进程失败: {e}")
        
        if killed_processes:
            return True, f"已自动停止占用进程: {', '.join(set(killed_processes))}"
        
        return True, ""

    def _init_ui(self):
        self.setModal(True)
        self.setFixedSize(500, 420)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setObjectName("EditAssetDialog")

        container = QWidget()
        container.setObjectName("EditAssetDialogContainer")

        main_layout = QVBoxLayout()
        main_layout.setSpacing(0)
        main_layout.setContentsMargins(0, 0, 0, 0)

        main_layout.addWidget(self._create_title_bar())

        content_widget = QWidget()
        content_widget.setObjectName("EditAssetDialogContent")
        content_layout = QVBoxLayout(content_widget)
        content_layout.setContentsMargins(30, 25, 30, 30)
        content_layout.setSpacing(18)

        content_layout.addLayout(self._create_name_section())
        content_layout.addLayout(self._create_path_section())
        content_layout.addLayout(self._create_category_section())

        type_label = QLabel(f"项目类型: {'C++ 项目' if self.is_cpp_project else '蓝图项目'}")
        type_label.setObjectName("InfoTitleLabel")
        content_layout.addWidget(type_label)

        self.error_label = QLabel("")
        self.error_label.setObjectName("ErrorLabel")
        self.error_label.setWordWrap(True)
        self.error_label.setFixedHeight(25)
        self.error_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        content_layout.addWidget(self.error_label)

        content_layout.addStretch()
        content_layout.addLayout(self._create_button_layout())

        main_layout.addWidget(content_widget)
        container.setLayout(main_layout)

        dialog_layout = QVBoxLayout(self)
        dialog_layout.setContentsMargins(0, 0, 0, 0)
        dialog_layout.addWidget(container)

    def _create_title_bar(self):
        title_bar = QWidget()
        title_bar.setObjectName("EditAssetDialogTitleBar")
        title_bar.setFixedHeight(50)
        title_bar.setCursor(Qt.CursorShape.SizeAllCursor)

        layout = QHBoxLayout(title_bar)
        layout.setContentsMargins(25, 0, 25, 0)
        layout.setSpacing(10)

        title = QLabel("编辑工程信息")
        title.setObjectName("EditAssetDialogTitle")
        layout.addWidget(title)
        layout.addStretch()

        close_btn = QPushButton("✕")
        close_btn.setObjectName("EditAssetDialogCloseButton")
        close_btn.setFixedSize(32, 32)
        close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        close_btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        close_btn.clicked.connect(self.reject)
        layout.addWidget(close_btn)

        title_bar.mousePressEvent = self._title_bar_mouse_press
        title_bar.mouseMoveEvent = self._title_bar_mouse_move
        return title_bar

    def _create_name_section(self):
        layout = QVBoxLayout()
        layout.setSpacing(10)
        label = QLabel("项目名称")
        label.setObjectName("SectionLabel")
        layout.addWidget(label)

        self.name_input = QLineEdit()
        self.name_input.setObjectName("EditAssetInput")
        self.name_input.setText(self.project_name)
        self.name_input.setPlaceholderText("输入项目名称...")
        self.name_input.setFixedHeight(36)
        self.name_input.textChanged.connect(lambda: self.error_label.setText(""))
        layout.addWidget(self.name_input)
        return layout

    def _create_path_section(self):
        layout = QVBoxLayout()
        layout.setSpacing(10)
        label = QLabel("项目路径")
        label.setObjectName("SectionLabel")
        layout.addWidget(label)

        path_layout = QHBoxLayout()
        path_layout.setSpacing(10)

        self.path_input = QLineEdit()
        self.path_input.setObjectName("EditAssetInput")
        self.path_input.setText(self.project_path)
        self.path_input.setFixedHeight(36)
        self.path_input.setReadOnly(True)
        path_layout.addWidget(self.path_input)

        browse_btn = QPushButton("浏览...")
        browse_btn.setObjectName("EditDocButton")
        browse_btn.setFixedSize(80, 36)
        browse_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        browse_btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        browse_btn.clicked.connect(self._on_browse_clicked)
        path_layout.addWidget(browse_btn)

        layout.addLayout(path_layout)
        return layout

    def _create_category_section(self):
        layout = QVBoxLayout()
        layout.setSpacing(10)
        label = QLabel("项目分类")
        label.setObjectName("SectionLabel")
        layout.addWidget(label)

        self.category_combo = QComboBox()
        self.category_combo.setObjectName("EditAssetCategoryCombo")
        self.category_combo.setEditable(False)
        self.category_combo.addItems(self.categories)
        self.category_combo.setCurrentText(self.current_category)
        self.category_combo.setFixedHeight(36)
        self.category_combo.setMaximumWidth(250)

        combo_view = self.category_combo.view()
        combo_view.window().setWindowFlags(
            Qt.WindowType.Popup | Qt.WindowType.FramelessWindowHint | Qt.WindowType.NoDropShadowWindowHint
        )
        combo_view.window().setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, False)
        layout.addWidget(self.category_combo)
        return layout

    def _create_button_layout(self):
        layout = QHBoxLayout()
        layout.setSpacing(15)
        layout.addStretch()

        cancel_btn = QPushButton("取消")
        cancel_btn.setObjectName("CancelButton")
        cancel_btn.setFixedSize(100, 40)
        cancel_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        cancel_btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        cancel_btn.clicked.connect(self.reject)
        layout.addWidget(cancel_btn)

        ok_btn = QPushButton("确定")
        ok_btn.setObjectName("OkButton")
        ok_btn.setFixedSize(100, 40)
        ok_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        ok_btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        ok_btn.clicked.connect(self._on_ok_clicked)
        layout.addWidget(ok_btn)
        return layout

    def _on_browse_clicked(self):
        new_path = QFileDialog.getExistingDirectory(
            self, "选择新的项目位置",
            str(Path(self.project_path).parent),
            QFileDialog.Option.ShowDirsOnly
        )
        if new_path:
            self.path_input.setText(new_path)

    def _on_ok_clicked(self):
        new_name = self.name_input.text().strip()
        new_path = self.path_input.text().strip()
        new_category = self.category_combo.currentText().strip()

        if not new_name:
            self._show_error("项目名称不能为空")
            return

        invalid_chars = '<>:"/\\|?*'
        if any(c in new_name for c in invalid_chars):
            self._show_error(f"项目名称不能包含以下字符: {invalid_chars}")
            return

        name_changed = new_name != self.project_name
        path_changed = new_path != self.project_path
        category_changed = new_category != self.current_category

        if not name_changed and not path_changed and not category_changed:
            self.reject()
            return

        # 暂不支持 C++ 项目改名/迁移
        if self.is_cpp_project and (name_changed or path_changed):
            self._show_error("C++改名逻辑正在完善，敬请期待")
            return

        if name_changed or path_changed:
            # 重命名前确认
            if name_changed:
                if self.is_cpp_project:
                    msg = (
                        f"即将重命名 C++ 项目:\n"
                        f"  {self.project_name} → {new_name}\n\n"
                        f"此操作会修改 Source 目录下的文件并重新编译。\n"
                        f"已自动备份，编译失败会自动回滚。\n\n"
                        f"确定继续？"
                    )
                else:
                    msg = (
                        f"即将重命名项目:\n"
                        f"  {self.project_name} → {new_name}\n\n"
                        f"确定继续？"
                    )
                dialog = ConfirmDialog(
                    "确认重命名",
                    msg,
                    "",
                    self
                )
                if hasattr(dialog, 'center_on_parent'):
                    dialog.center_on_parent()
                if dialog.exec() != QDialog.DialogCode.Accepted:
                    return

            # ── 确认后隐藏编辑对话框（不 accept），开始改名 ──
            # 注意：用 hide() 而非 accept()，避免触发上层 exec() 返回 Accepted 导致提前发射信号
            self.hide()

            # 保存改名前的旧路径（改名过程中 self.project_path 会被更新）
            old_path_for_signal = self.project_path
            old_category = self.current_category

            # 创建详情弹窗（父窗口为主窗口，避免随编辑对话框一起销毁）
            mw = self._get_main_window()
            parent_for_dlg = mw if mw else None
            total_stages = 5
            self._progress_dlg = RenameProgressDialog(
                old_name=self.project_name,
                new_name=new_name,
                total=total_stages,
                open_cb=self._open_project_in_ue,
                parent=parent_for_dlg
            )

            # 确认后直接弹出详情弹窗
            self._progress_dlg.show()
            self._progress_dlg._center_on_parent()

            # 注册「详情」按钮回调：弹窗被后台执行隐藏后可重新打开
            if mw and hasattr(mw, 'set_status_detail_callback'):
                def _show_detail():
                    if not self._progress_dlg.isVisible():
                        self._progress_dlg.show()
                        self._progress_dlg._center_on_parent()
                mw.set_status_detail_callback(_show_detail)

            # 创建进度控制器
            self._prog_ctrl = _RenameProgressController(
                total=total_stages,
                main_window=mw,
                progress_dialog=self._progress_dlg
            )
            self._prog_ctrl.start()

            success = self._rename_project(new_name, new_path)
            if not success:
                self._prog_ctrl.stop()
                if mw and hasattr(mw, 'set_status_detail_callback'):
                    mw.set_status_detail_callback(None)
                # 改名失败，关闭对话框
                self.reject()
            else:
                # 改名成功，发射信号通知上层更新注册表（此时 self.project_path 已是新路径）
                self.rename_completed.emit(
                    old_path_for_signal,
                    self.project_path,
                    self.project_name,
                    new_category
                )
                self.reject()  # 关闭编辑对话框（不触发 Accepted）
                return

        # 只改了分类，直接 accept（上层监听 exec() 返回值处理分类变更）
        self.accept()


    @staticmethod
    def check_pending_backup():
        """检查是否有上次未清理的备份（程序崩溃等情况）
        
        在程序启动时调用，如果有残留备份则提示用户。
        Returns: (has_backup, backup_info_msg)
        """
        backup_dir = _get_backup_dir()
        meta_file = backup_dir / "_meta.json"
        if not meta_file.exists():
            return False, ""
        try:
            with open(meta_file, "r", encoding="utf-8") as f:
                meta = json.load(f)
            return True, (
                f"检测到上次重命名操作的备份未清理:\n"
                f"  原始项目: {meta.get('original_name', '未知')}\n"
                f"  原始路径: {meta.get('original_path', '未知')}\n\n"
                f"备份位置: {backup_dir}\n"
                f"如果项目有问题，可以手动从备份恢复。"
            )
        except Exception:
            return False, ""

    # ── 备份与回滚 ──

    def _backup_project(self, project_path: Path) -> Optional[Path]:
        """备份项目的 Source 目录、Config 目录和 .uproject 文件"""
        try:
            backup_dir = _get_backup_dir()
            # 清理旧备份
            if backup_dir.exists():
                shutil.rmtree(backup_dir)
            backup_dir.mkdir(parents=True, exist_ok=True)

            # 备份 Source 目录
            src = project_path / "Source"
            if src.exists():
                shutil.copytree(src, backup_dir / "Source")

            # 备份 Config 目录（改名会修改 DefaultEngine.ini 等）
            config_dir = project_path / "Config"
            if config_dir.exists():
                shutil.copytree(config_dir, backup_dir / "Config")

            # 备份 .uproject 文件
            for up in project_path.glob("*.uproject"):
                shutil.copy2(up, backup_dir / up.name)

            # 备份 .sln 文件（改名后需要删除重新生成）
            for sln in project_path.glob("*.sln"):
                shutil.copy2(sln, backup_dir / sln.name)

            # 记录原始信息
            meta = {
                "original_path": str(project_path),
                "original_name": self.project_name,
                "original_folder": project_path.name,
            }
            with open(backup_dir / "_meta.json", "w", encoding="utf-8") as f:
                json.dump(meta, f, ensure_ascii=False, indent=2)

            logger.info(f"项目已备份到: {backup_dir}")
            return backup_dir
        except Exception as e:
            logger.error(f"备份失败: {e}", exc_info=True)
            return None


    def _rollback_project(self):
        """从备份回滚项目"""
        backup_dir = _get_backup_dir()
        if not backup_dir.exists():
            logger.warning("没有找到备份，无法回滚")
            return False

        try:
            meta_file = backup_dir / "_meta.json"
            if not meta_file.exists():
                return False

            with open(meta_file, "r", encoding="utf-8") as f:
                meta = json.load(f)

            original_path = Path(meta["original_path"])
            original_name = meta["original_name"]
            current_path = Path(self.project_path)

            # 1. 删除当前（已改名的）Source、Config 和 .uproject
            current_source = current_path / "Source"
            if current_source.exists():
                shutil.rmtree(current_source)
            current_config = current_path / "Config"
            if current_config.exists():
                shutil.rmtree(current_config)
            for up in current_path.glob("*.uproject"):
                up.unlink()

            # 2. 从备份恢复 Source、Config 和 .uproject
            backup_source = backup_dir / "Source"
            if backup_source.exists():
                shutil.copytree(backup_source, current_path / "Source")
            backup_config = backup_dir / "Config"
            if backup_config.exists():
                shutil.copytree(backup_config, current_path / "Config")
            for up in backup_dir.glob("*.uproject"):
                shutil.copy2(up, current_path / up.name)

            # 3. 如果文件夹名也改了，改回去
            if current_path.name != original_path.name:
                restored_path = current_path.parent / original_path.name
                current_path.rename(restored_path)
                self.project_path = str(restored_path)
                logger.info(f"文件夹已回滚: {current_path.name} → {original_path.name}")

            self.project_name = original_name

            # 4. 清理缓存让 UE 重新生成
            final_path = Path(self.project_path)
            for d in ['Intermediate', 'Binaries']:
                p = final_path / d
                if p.exists():
                    shutil.rmtree(p, ignore_errors=True)

            # 5. 清理备份
            shutil.rmtree(backup_dir, ignore_errors=True)

            logger.info("项目已回滚到原始状态")
            return True
        except Exception as e:
            logger.error(f"回滚失败: {e}", exc_info=True)
            return False


    # ── 重命名核心逻辑 ──

    def _rename_project(self, new_name: str, new_path: str) -> bool:
        old_path = Path(self.project_path)
        old_name = self.project_name

        uproject_files = list(old_path.glob("*.uproject"))
        if not uproject_files:
            self._show_error("找不到 .uproject 文件")
            return False

        old_uproject = uproject_files[0]

        if self.is_cpp_project:
            return self._rename_cpp_project_flow(
                new_name, new_path, old_path, old_name, old_uproject
            )
        else:
            return self._rename_blueprint_project_flow(
                new_name, new_path, old_path, old_name, old_uproject
            )

    # ── 蓝图项目改名流程 ──

    def _backup_blueprint_project(
        self, project_path: Path, old_name: str, new_name: str
    ) -> Optional[Path]:
        """蓝图项目轻量备份：.uproject + Config/ + Plugins/*/Config/"""
        from datetime import datetime
        try:
            backup_dir = _get_backup_dir()
            if backup_dir.exists():
                shutil.rmtree(backup_dir)
            backup_dir.mkdir(parents=True, exist_ok=True)

            # 备份 .uproject
            for up in project_path.glob("*.uproject"):
                shutil.copy2(up, backup_dir / up.name)

            # 备份 Config/
            config_dir = project_path / "Config"
            if config_dir.exists():
                shutil.copytree(config_dir, backup_dir / "Config")

            # 备份 Plugins/*/Config/
            plugins_dir = project_path / "Plugins"
            if plugins_dir.exists():
                for plugin_config in plugins_dir.glob("*/Config"):
                    if plugin_config.is_dir():
                        rel = plugin_config.relative_to(project_path)
                        dest = backup_dir / rel
                        dest.parent.mkdir(parents=True, exist_ok=True)
                        shutil.copytree(plugin_config, dest)

            # 写入 _meta.json
            meta = {
                "original_name": old_name,
                "new_name": new_name,
                "original_path": str(project_path),
                "original_folder": project_path.name,
                "backup_time": datetime.now().isoformat(),
                "engine_ini_modified": False,
                "game_ini_modified": False,
                "redirects_added": [],
                "is_blueprint": True,
            }
            with open(backup_dir / "_meta.json", "w", encoding="utf-8") as f:
                json.dump(meta, f, ensure_ascii=False, indent=2)

            logger.info(f"蓝图项目已备份到: {backup_dir}")
            return backup_dir
        except Exception as e:
            logger.error(f"蓝图项目备份失败: {e}", exc_info=True)
            return None

    def _clean_project_cache(self, project_path: Path):
        """清理项目缓存文件（改名后必须清理，否则打包失败）
        
        清理策略：
        - 必须清理：Binaries、Intermediate（包含旧项目名的编译产物）
        - 可选清理：Saved 的部分子目录（临时文件和缓存）
        - 必须保留：Saved/Config（编辑器配置）、Saved/Screenshots（截图）、Saved/SaveGames（存档）
        """
        # 必须清理的文件夹（包含旧项目名的编译产物）
        must_clean = ['Binaries', 'Intermediate']
        
        # 可选清理的文件夹（不影响改名，但可能包含旧数据）
        optional_clean = [
            'Saved/Autosaves',      # 自动保存（可能包含旧项目名）
            'Saved/Backup',         # 备份文件
            'Saved/Logs',           # 日志文件
            'Saved/Cooked',         # 烘焙内容
            'Saved/StagedBuilds',   # 打包构建
            'Saved/ShaderDebugInfo' # Shader 调试信息
        ]
        
        # 清理必须清理的文件夹
        for folder_name in must_clean:
            folder = project_path / folder_name
            if folder.exists():
                try:
                    logger.info(f"清理缓存文件夹: {folder}")
                    shutil.rmtree(folder, ignore_errors=True)
                except Exception as e:
                    logger.warning(f"清理 {folder_name} 失败: {e}")
                    # 不阻断流程，只记录警告
        
        # 清理可选清理的文件夹
        for folder_path in optional_clean:
            folder = project_path / folder_path
            if folder.exists():
                try:
                    logger.info(f"清理可选缓存: {folder}")
                    shutil.rmtree(folder, ignore_errors=True)
                except Exception as e:
                    logger.warning(f"清理 {folder_path} 失败: {e}")
                    # 不阻断流程，只记录警告
        
        logger.info("项目缓存清理完成（保留了 Saved/Config、Saved/Screenshots、Saved/SaveGames）")

    def _scan_script_references(
        self, project_path: Path, old_name: str
    ) -> tuple[list, list]:
        """扫描 Config/*.ini + Plugins/*/Config/*.ini 中的旧名引用

        Returns:
            (high_risk: ["/Script/OldName" 引用列表],
             low_risk: [普通 OldName 引用列表])
        """
        import re
        high_risk = []
        low_risk = []
        old_lower = old_name.lower()
        script_pattern = re.compile(
            rf'/Script/{re.escape(old_name)}', re.IGNORECASE
        )

        ini_files = []
        config_dir = project_path / "Config"
        if config_dir.exists():
            ini_files.extend(config_dir.glob("*.ini"))
        plugins_dir = project_path / "Plugins"
        if plugins_dir.exists():
            for pc in plugins_dir.glob("*/Config/*.ini"):
                ini_files.append(pc)

        for ini_file in ini_files:
            try:
                # 使用编码检测读取文件
                encoding = self._detect_file_encoding(ini_file)
                content = ini_file.read_text(encoding=encoding)
                for i, line in enumerate(content.splitlines(), 1):
                    if script_pattern.search(line):
                        high_risk.append(f"{ini_file.name}:{i} → {line.strip()}")
                    elif old_lower in line.lower():
                        # 排除已经是 redirect 目标的行
                        if 'NewName=' not in line and 'NewGameName=' not in line:
                            low_risk.append(f"{ini_file.name}:{i} → {line.strip()}")
            except Exception as e:
                logger.warning(f"扫描文件失败 {ini_file}: {e}")

        return high_risk, low_risk

    def _has_existing_redirects(self, project_path: Path, old_name: str) -> bool:
        """检查是否已有指向 old_name 的历史 redirect"""
        import re
        config_dir = project_path / "Config"
        engine_ini = config_dir / "DefaultEngine.ini"
        if not engine_ini.exists():
            return False
        try:
            encoding = self._detect_file_encoding(engine_ini)
            content = engine_ini.read_text(encoding=encoding)
            pattern = re.compile(
                rf'OldName="/Script/{re.escape(old_name)}"', re.IGNORECASE
            )
            return bool(pattern.search(content))
        except Exception:
            return False

    def _update_engine_ini_blueprint(
        self, project_path: Path, old_name: str, new_name: str
    ):
        """蓝图项目专用：更新 DefaultEngine.ini（GameName + Redirects）"""
        import re
        config_dir = project_path / "Config"
        config_dir.mkdir(parents=True, exist_ok=True)
        engine_ini = config_dir / "DefaultEngine.ini"

        # 检测原始编码并读取
        if engine_ini.exists():
            encoding = self._detect_file_encoding(engine_ini)
            content = engine_ini.read_text(encoding=encoding)
        else:
            encoding = 'utf-8'
            content = ""

        # 统一换行符为 \n，避免 \r\r\n 导致正则失效
        content = content.replace('\r\n', '\n').replace('\r', '\n')

        # 1. 更新 [URL] GameName
        # 用 [^\n]* 代替 .* 确保只匹配到行尾（不受换行符影响）
        if '[URL]' in content:
            if re.search(r'GameName=', content):
                content = re.sub(r'GameName=[^\n]*', f'GameName={new_name}', content)
            else:
                content = content.replace('[URL]', f'[URL]\nGameName={new_name}')
        else:
            content = f"[URL]\nGameName={new_name}\n\n" + content

        # 2. 检测是否需要 redirect
        # 注意：从备份目录读取原始 Config 做扫描，避免读到本次已修改的内容
        backup_dir = _get_backup_dir()
        scan_path = project_path
        if (backup_dir / "Config").exists():
            # 备份存在时，用备份内容做扫描（更准确）
            import tempfile, shutil as _shutil
            tmp_dir = Path(tempfile.mkdtemp())
            try:
                _shutil.copytree(backup_dir / "Config", tmp_dir / "Config")
                high_risk, _ = self._scan_script_references(tmp_dir, old_name)
            finally:
                _shutil.rmtree(tmp_dir, ignore_errors=True)
        else:
            high_risk, _ = self._scan_script_references(project_path, old_name)
        has_history = self._has_existing_redirects(project_path, old_name)

        if high_risk or has_history:
            use_core_redirects = self._should_use_core_redirects(project_path)
            
            if use_core_redirects:
                core_redirect = (
                    f'+PackageRedirects=(OldName="/Script/{old_name}",'
                    f'NewName="/Script/{new_name}")'
                )
                if '[CoreRedirects]' in content:
                    content = re.sub(
                        rf'NewName="/Script/{re.escape(old_name)}"',
                        f'NewName="/Script/{new_name}"',
                        content, flags=re.IGNORECASE
                    )
                    if f'OldName="/Script/{old_name}"' not in content:
                        content = content.replace(
                            '[CoreRedirects]',
                            f'[CoreRedirects]\n{core_redirect}'
                        )
                else:
                    content += f"\n[CoreRedirects]\n{core_redirect}\n"
                logger.info(f"已添加 CoreRedirects: /Script/{old_name} → /Script/{new_name}")
            else:
                compat_redirect = (
                    f'+ActiveGameNameRedirects=(OldGameName="/Script/{old_name}",'
                    f'NewGameName="/Script/{new_name}")'
                )
                engine_section = "[/Script/Engine.Engine]"
                if engine_section in content:
                    content = re.sub(
                        rf'NewGameName="/Script/{re.escape(old_name)}"',
                        f'NewGameName="/Script/{new_name}"',
                        content, flags=re.IGNORECASE
                    )
                    if f'OldGameName="/Script/{old_name}"' not in content:
                        content = content.replace(
                            engine_section,
                            f"{engine_section}\n{compat_redirect}"
                        )
                else:
                    content += f"\n{engine_section}\n{compat_redirect}\n"
                logger.info(f"已添加 ActiveGameNameRedirects: /Script/{old_name} → /Script/{new_name}")

            self._update_backup_meta(
                redirects_added=[f"/Script/{old_name}"],
                engine_ini_modified=True
            )
        else:
            self._update_backup_meta(engine_ini_modified=True)
            logger.info("未检测到 /Script/ 引用，跳过 redirect")

        # 写回（保持原始编码）
        engine_ini.write_text(content, encoding=encoding)
        logger.info(f"更新 DefaultEngine.ini: GameName={new_name} (编码: {encoding})")

    def _should_use_core_redirects(self, project_path: Path) -> bool:
        """根据 .uproject 的 EngineAssociation 判断使用哪种 redirect
        
        UE5 / UE4.16+ → CoreRedirects（返回 True）
        UE4.15 及更早 → ActiveGameNameRedirects（返回 False）
        """
        try:
            uproject_files = list(project_path.glob("*.uproject"))
            if not uproject_files:
                return True  # 找不到就默认用新版
            
            with open(uproject_files[0], 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            engine_ver = data.get('EngineAssociation', '')
            logger.info(f"检测到引擎版本: {engine_ver}")
            
            # UE5 格式：5.0, 5.1, 5.4 等
            if engine_ver.startswith('5.'):
                return True
            
            # UE4 格式：4.15, 4.16, 4.27 等
            if engine_ver.startswith('4.'):
                try:
                    minor = int(engine_ver.split('.')[1])
                    return minor >= 16  # 4.16+ 支持 CoreRedirects
                except (ValueError, IndexError):
                    return True
            
            # GUID 格式（自编译引擎）或其他格式，默认用新版
            return True
            
        except Exception as e:
            logger.warning(f"读取引擎版本失败: {e}，默认使用 CoreRedirects")
            return True

    def _update_backup_meta(self, **kwargs):
        """更新备份 _meta.json 中的字段"""
        backup_dir = _get_backup_dir()
        meta_file = backup_dir / "_meta.json"
        if not meta_file.exists():
            return
        try:
            with open(meta_file, "r", encoding="utf-8") as f:
                meta = json.load(f)
            meta.update(kwargs)
            with open(meta_file, "w", encoding="utf-8") as f:
                json.dump(meta, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.warning(f"更新 _meta.json 失败: {e}")

    def _rollback_blueprint_project(self, cleanup_backup: bool = False):
        """蓝图项目回滚：从备份还原

        Args:
            cleanup_backup: 是否在回滚成功后删除备份（默认保留，便于二次恢复）
        """
        backup_dir = _get_backup_dir()
        if not backup_dir.exists():
            logger.warning("没有找到备份，无法回滚")
            return False

        try:
            meta_file = backup_dir / "_meta.json"
            if not meta_file.exists():
                return False

            with open(meta_file, "r", encoding="utf-8") as f:
                meta = json.load(f)

            original_path = Path(meta["original_path"])
            original_name = meta["original_name"]

            # 以 meta 记录的原始路径为基准，推算当前文件夹实际位置：
            # - 如果改名成功，self.project_path 已是新路径
            # - 如果改名未完成，self.project_path 还是旧路径
            # 两种情况都要能正确定位到「当前实际存在的文件夹」
            current_path = Path(self.project_path)
            if not current_path.exists():
                # self.project_path 不存在，尝试原始路径
                current_path = original_path

            # 1. 如果文件夹已改名（当前路径名 != 原始路径名），改回去
            if current_path.exists() and current_path.name != original_path.name:
                restored_path = current_path.parent / original_path.name
                if restored_path.exists():
                    # 目标名称已存在，无法回滚文件夹名，只还原文件内容
                    logger.warning(f"回滚文件夹失败：目标已存在 {restored_path}，只还原文件内容")
                else:
                    current_path.rename(restored_path)
                    current_path = restored_path
                    self.project_path = str(restored_path)
                    logger.info(f"文件夹已回滚: → {original_path.name}")

            # 2. 还原 Config/
            backup_config = backup_dir / "Config"
            if backup_config.exists():
                current_config = current_path / "Config"
                if current_config.exists():
                    shutil.rmtree(current_config)
                shutil.copytree(backup_config, current_config)
                logger.info("Config/ 已从备份还原")

            # 3. 还原 Plugins/*/Config/
            backup_plugins = backup_dir / "Plugins"
            if backup_plugins.exists():
                for plugin_config_backup in backup_plugins.glob("*/Config"):
                    rel = plugin_config_backup.relative_to(backup_dir)
                    target = current_path / rel
                    if target.exists():
                        shutil.rmtree(target)
                    target.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copytree(plugin_config_backup, target)

            # 4. 还原 .uproject
            for up_backup in backup_dir.glob("*.uproject"):
                for up_current in current_path.glob("*.uproject"):
                    up_current.unlink()
                shutil.copy2(up_backup, current_path / up_backup.name)

            self.project_name = original_name
            self.project_path = str(current_path)

            # 5. 按策略清理备份（默认保留，避免回滚后无法二次恢复）
            if cleanup_backup:
                shutil.rmtree(backup_dir, ignore_errors=True)
                logger.info("已按策略清理蓝图改名备份")

            logger.info("蓝图项目已回滚到原始状态")
            return True
        except Exception as e:
            logger.error(f"蓝图项目回滚失败: {e}", exc_info=True)
            return False

    def _verify_config_written(
        self, project_path: Path, backup_dir: Path, old_name: str, new_name: str
    ) -> tuple[bool, str]:
        """校验配置写入结果：与备份对照关键字段是否符合预期"""
        try:
            config_dir = project_path / "Config"
            game_ini = config_dir / "DefaultGame.ini"
            engine_ini = config_dir / "DefaultEngine.ini"

            if not game_ini.exists():
                return False, "缺少 DefaultGame.ini"
            if not engine_ini.exists():
                return False, "缺少 DefaultEngine.ini"

            # 读取当前文件
            game_enc = self._detect_file_encoding(game_ini)
            engine_enc = self._detect_file_encoding(engine_ini)
            game_content = game_ini.read_text(encoding=game_enc)
            engine_content = engine_ini.read_text(encoding=engine_enc)

            # 基础健康检查：出现 NUL 字节通常说明编码混写损坏
            if "\x00" in game_content:
                return False, "DefaultGame.ini 含有异常 NUL 字节，疑似编码损坏"
            if "\x00" in engine_content:
                return False, "DefaultEngine.ini 含有异常 NUL 字节，疑似编码损坏"

            # 统一换行便于正则校验
            game_norm = game_content.replace('\r\n', '\n').replace('\r', '\n')
            engine_norm = engine_content.replace('\r\n', '\n').replace('\r', '\n')

            import re
            # 校验 DefaultGame.ini
            if "[/Script/EngineSettings.GeneralProjectSettings]" not in game_norm:
                return False, "DefaultGame.ini 缺少 GeneralProjectSettings 段"
            m_proj = re.search(r'^ProjectName=([^\n]+)$', game_norm, flags=re.MULTILINE)
            if not m_proj:
                return False, "DefaultGame.ini 缺少 ProjectName 字段"
            if m_proj.group(1).strip() != new_name:
                return False, f"ProjectName 写入异常：当前为 {m_proj.group(1).strip()}，期望为 {new_name}"

            # 校验 DefaultEngine.ini
            if "[URL]" not in engine_norm:
                return False, "DefaultEngine.ini 缺少 [URL] 段"
            m_game = re.search(r'^GameName=([^\n]+)$', engine_norm, flags=re.MULTILINE)
            if not m_game:
                return False, "DefaultEngine.ini 缺少 GameName 字段"
            if m_game.group(1).strip() != new_name:
                return False, f"GameName 写入异常：当前为 {m_game.group(1).strip()}，期望为 {new_name}"

            # 与备份对照：若备份里有 ProjectID，必须保持不变
            backup_game = backup_dir / "Config" / "DefaultGame.ini"
            if backup_game.exists():
                b_enc = self._detect_file_encoding(backup_game)
                b_content = backup_game.read_text(encoding=b_enc).replace('\r\n', '\n').replace('\r', '\n')
                b_id = re.search(r'^ProjectID=([^\n]+)$', b_content, flags=re.MULTILINE)
                n_id = re.search(r'^ProjectID=([^\n]+)$', game_norm, flags=re.MULTILINE)
                if b_id and n_id and b_id.group(1).strip() != n_id.group(1).strip():
                    return False, "ProjectID 被意外修改"

            # 关键字段中不应残留旧名
            if re.search(rf'^ProjectName={re.escape(old_name)}$', game_norm, flags=re.MULTILINE):
                return False, "ProjectName 仍为旧名称"
            if re.search(rf'^GameName={re.escape(old_name)}$', engine_norm, flags=re.MULTILINE):
                return False, "GameName 仍为旧名称"

            return True, ""
        except Exception as e:
            return False, f"配置校验异常: {e}"

    def _verify_rename(self, project_path: Path, old_name: str) -> list:
        """改名后验证，返回警告列表
        
        排除 CoreRedirects / ActiveGameNameRedirects 段落内的旧名引用（这些是我们自己写入的兼容映射，不是残留）
        """
        import re
        warnings = []

        # 读取 DefaultEngine.ini，提取需要排除的行（redirect 映射行）
        exclude_lines = set()
        engine_ini = project_path / "Config" / "DefaultEngine.ini"
        if engine_ini.exists():
            try:
                encoding = self._detect_file_encoding(engine_ini)
                ini_content = engine_ini.read_text(encoding=encoding)
                # 排除包含 OldName=/Script/旧名 的 redirect 行
                for line in ini_content.splitlines():
                    stripped = line.strip()
                    if (f'/Script/{old_name}' in stripped and
                            ('OldName=' in stripped or 'OldGameName=' in stripped)):
                        exclude_lines.add(stripped)
            except Exception:
                pass

        high_risk, low_risk = self._scan_script_references_with_exclusions(
            project_path, old_name, exclude_lines
        )

        for ref in high_risk:
            warnings.append(f"⚠️ 高风险残留: {ref}")
        for ref in low_risk[:5]:
            warnings.append(f"ℹ️ 普通残留: {ref}")
        if len(low_risk) > 5:
            warnings.append(f"ℹ️ ...还有 {len(low_risk) - 5} 处普通残留")

        return warnings

    def _scan_script_references_with_exclusions(
        self, project_path: Path, old_name: str, exclude_line_contents: set
    ) -> tuple:
        """同 _scan_script_references，但排除指定行内容（用于过滤 redirect 映射行）"""
        import re
        high_risk = []
        low_risk = []
        old_lower = old_name.lower()
        script_pattern = re.compile(
            rf'/Script/{re.escape(old_name)}', re.IGNORECASE
        )

        ini_files = []
        config_dir = project_path / "Config"
        if config_dir.exists():
            ini_files.extend(config_dir.glob("*.ini"))
        plugins_dir = project_path / "Plugins"
        if plugins_dir.exists():
            for pc in plugins_dir.glob("*/Config/*.ini"):
                ini_files.append(pc)

        for ini_file in ini_files:
            try:
                encoding = self._detect_file_encoding(ini_file)
                content = ini_file.read_text(encoding=encoding)
                for i, line in enumerate(content.splitlines(), 1):
                    stripped = line.strip()
                    # 跳过被排除的行（redirect 映射行）
                    if stripped in exclude_line_contents:
                        continue
                    if script_pattern.search(line):
                        high_risk.append(f"{ini_file.name}:{i} → {stripped}")
                    elif old_lower in line.lower():
                        if 'NewName=' not in line and 'NewGameName=' not in line:
                            low_risk.append(f"{ini_file.name}:{i} → {stripped}")
            except Exception as e:
                logger.warning(f"扫描文件失败 {ini_file}: {e}")

        return high_risk, low_risk

    def _open_project_in_ue(self):
        """用系统关联的 UE 编辑器打开当前项目"""
        import os
        pp = Path(self.project_path)
        ufs = list(pp.glob("*.uproject"))
        if ufs:
            try:
                if sys.platform == "win32":
                    os.startfile(str(ufs[0]))
                else:
                    subprocess.Popen([str(ufs[0])], shell=False)
                logger.info(f"打开工程: {ufs[0]}")
            except Exception as e:
                logger.error(f"打开工程失败: {e}")

    def _show_rename_result(self, old_name: str, new_name: str, warnings: list):
        """显示商业级改名结果弹窗"""
        high_risk_count = sum(1 for w in warnings if w.startswith("⚠️"))
        low_risk_count = len(warnings) - high_risk_count
        logger.info(f"改名完成: {old_name} → {new_name} (高风险:{high_risk_count}, 低风险:{low_risk_count})")

        dlg = QDialog(self)
        dlg.setWindowTitle("项目改名完成")
        dlg.setFixedWidth(420)
        dlg.setWindowFlags(Qt.WindowType.Dialog | Qt.WindowType.FramelessWindowHint)
        dlg.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        # 外层容器（圆角背景）
        container = QWidget(dlg)
        container.setObjectName("RenameResultContainer")
        dlg_layout = QVBoxLayout(dlg)
        dlg_layout.setContentsMargins(0, 0, 0, 0)
        dlg_layout.addWidget(container)

        main_layout = QVBoxLayout(container)
        main_layout.setContentsMargins(28, 24, 28, 20)
        main_layout.setSpacing(12)

        # ── 标题 ──
        title = QLabel("项目改名完成")
        title.setObjectName("RenameResultTitle")
        main_layout.addWidget(title)

        # ── 摘要 ──
        summary = QLabel(f"{old_name}  →  {new_name}")
        summary.setObjectName("RenameResultSummary")
        summary.setWordWrap(True)
        main_layout.addWidget(summary)

        main_layout.addSpacing(4)

        # ── 已完成列表 ──
        done_items = [
            "项目目录重命名",
            "项目文件更新",
            "项目配置同步",
            "历史引用检查",
        ]
        for item in done_items:
            row = QLabel(f"  ✓  {item}")
            row.setObjectName("RenameResultDoneItem")
            main_layout.addWidget(row)

        main_layout.addSpacing(4)

        # ── 兼容性状态 ──
        if high_risk_count > 0:
            compat = QLabel(
                f"兼容性状态：已启用兼容处理\n"
                f"检测到历史引用 {high_risk_count} 处，已自动映射"
            )
        elif low_risk_count > 0:
            compat = QLabel(
                f"检测到少量普通文本残留\n"
                f"这些内容通常是显示名称、注释或描述信息，不影响项目运行"
            )
        else:
            compat = QLabel(
                "本次改名未发现历史脚本引用\n"
                "项目名称、配置和项目文件已全部同步完成"
            )
        compat.setObjectName("RenameResultCompat")
        compat.setWordWrap(True)
        main_layout.addWidget(compat)

        # ── 建议提示 ──
        if high_risk_count > 0:
            tip = QLabel("建议首次打开项目后检查 GameMode、PlayerController 等关键类")
        elif low_risk_count > 0:
            tip = QLabel("核心文件已更新完成，可直接打开项目")
        else:
            tip = QLabel("改名已完美完成，可直接打开项目")
        tip.setObjectName("RenameResultTip")
        tip.setWordWrap(True)
        main_layout.addWidget(tip)

        main_layout.addSpacing(8)

        # ── 按钮区 ──
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(10)
        btn_layout.addStretch()

        btn_done = QPushButton("完成")
        btn_done.setObjectName("RenameResultBtnDone")
        btn_done.setFixedSize(80, 32)
        btn_done.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_done.clicked.connect(dlg.accept)
        btn_layout.addWidget(btn_done)

        btn_open = QPushButton("打开项目")
        btn_open.setObjectName("RenameResultBtnOpen")
        btn_open.setFixedSize(100, 32)
        btn_open.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_open.setDefault(True)

        def _open_project():
            dlg.accept()
            self._open_project_in_ue()

        btn_open.clicked.connect(_open_project)
        btn_layout.addWidget(btn_open)

        main_layout.addLayout(btn_layout)

        dlg.exec()

    def _rename_blueprint_project_flow(
        self, new_name: str, new_path: str,
        old_path: Path, old_name: str, old_uproject: Path
    ) -> bool:
        """蓝图项目改名完整流程"""
        import time
        is_cross_path = (new_path != self.project_path)
        try:
            # ── 阶段 1/6: 创建安全备份 ──
            self._show_stage(1, 6, "创建安全备份", "正在创建回滚点…")
            backup_dir = self._backup_blueprint_project(old_path, old_name, new_name)
            if not backup_dir:
                self._hide_stage()
                self._show_error("备份失败，取消重命名")
                return False
            self._end_stage(1)

            # ── 阶段 2/6: 重命名项目目录 ──
            detail_2 = "正在迁移项目目录…" if is_cross_path else "正在重命名项目目录…"
            self._show_stage(2, 6, "重命名项目目录", detail_2)
            current_path = old_path
            if new_path != self.project_path:
                # 跨路径移动
                final_path = Path(new_path) / (new_name if new_name != old_name else old_path.name)
                if final_path.exists():
                    self._rollback_blueprint_project()
                    self._show_error(f"目标路径已存在: {final_path}")
                    return False
                try:
                    shutil.move(str(current_path), str(final_path))
                    current_path = final_path
                    self.project_path = str(final_path)
                except PermissionError:
                    self._rollback_blueprint_project()
                    self._show_error(
                        "项目目录被占用，无法移动。\n\n"
                        "请先关闭 UE 编辑器、资源管理器中打开该目录的窗口，以及其它可能占用该目录的程序后重试。"
                    )
                    return False
            elif new_name != old_name:
                # 同路径改名
                new_folder = current_path.parent / new_name
                if new_folder.exists():
                    self._rollback_blueprint_project()
                    self._show_error(
                        f"目标文件夹已存在：{new_folder}\n\n请手动处理后重试。\n\n"
                        f"可能原因：\n• 已有同名项目\n• 上次改名失败的残留\n\n建议：手动删除或重命名该文件夹"
                    )
                    return False
                try:
                    max_retries = 3
                    for attempt in range(max_retries):
                        try:
                            current_path.rename(new_folder)
                            current_path = new_folder
                            self.project_path = str(new_folder)
                            break
                        except PermissionError as e:
                            if attempt < max_retries - 1:
                                logger.warning(f"重命名失败，1秒后重试 ({attempt + 1}/{max_retries}): {e}")
                                time.sleep(1)
                            else:
                                raise
                except PermissionError:
                    self._rollback_blueprint_project()
                    self._show_error(
                        "项目目录被占用，无法重命名。\n\n"
                        "请先关闭 UE 编辑器、资源管理器中打开该目录的窗口，以及其它可能占用该目录的程序后重试。"
                    )
                    return False
            self._end_stage(2)

            # ── 阶段 3/6: 同步项目配置 ──
            self._show_stage(3, 6, "同步项目配置", "正在处理历史引用兼容…")
            if new_name != old_name:
                self._update_engine_ini_blueprint(current_path, old_name, new_name)
                config_dir = current_path / "Config"
                config_dir.mkdir(parents=True, exist_ok=True)
                self._update_game_ini(config_dir / "DefaultGame.ini", new_name)
                self._update_backup_meta(game_ini_modified=True)

                # ── 配置文件校验（写入后与备份对比，确认字段正确）──
                ok, reason = self._verify_config_written(current_path, backup_dir, old_name, new_name)
                if not ok:
                    self._rollback_blueprint_project()
                    self._show_error(f"配置文件写入异常，已自动回滚。\n\n原因：{reason}")
                    return False
            self._end_stage(3)

            # ── 阶段 4/6: 清理缓存文件 ──
            self._show_stage(4, 6, "清理缓存文件", "正在清理编译缓存和临时文件…")
            self._clean_project_cache(current_path)
            self._end_stage(4)

            # ── 阶段 5/6: 更新项目文件 ──
            self._show_stage(5, 6, "更新项目文件", "正在更新项目文件…")
            if new_name != old_name:
                old_uproject_in_new_path = current_path / f"{old_name}.uproject"
                new_uproject = current_path / f"{new_name}.uproject"
                if not old_uproject_in_new_path.exists():
                    self._rollback_blueprint_project()
                    self._show_error(f"找不到 .uproject 文件: {old_uproject_in_new_path}")
                    return False
                if new_uproject.exists() and new_uproject != old_uproject_in_new_path:
                    self._rollback_blueprint_project()
                    self._show_error(f"文件 {new_name}.uproject 已存在")
                    return False
                old_uproject_in_new_path.rename(new_uproject)
                logger.info(f"重命名 .uproject: {old_name}.uproject → {new_name}.uproject")
            self.project_name = new_name
            self._end_stage(5)

            # ── 阶段 6/6: 完成校验 ──
            self._show_stage(6, 6, "完成校验", "正在验证改名结果…")
            warnings = self._verify_rename(current_path, old_name)
            self._end_stage(6)

            # 清理备份
            if backup_dir.exists():
                shutil.rmtree(backup_dir, ignore_errors=True)

            # 完成：通过进度控制器显示结果（会自动弹出详情弹窗）
            self._hide_stage()
            ctrl = getattr(self, '_prog_ctrl', None)
            if ctrl:
                ctrl.finish(warnings)
            else:
                # 降级：直接弹出结果弹窗
                self._show_rename_result(old_name, new_name, warnings)

            return True

        except Exception as e:
            logger.error(f"蓝图项目重命名失败: {e}", exc_info=True)
            # 先停止进度控制器动画，再回滚，最后隐藏状态
            ctrl = getattr(self, '_prog_ctrl', None)
            if ctrl:
                ctrl.stop()
            self._rollback_blueprint_project()
            self._hide_stage()
            self._show_error(f"重命名失败: {e}")
            return False

    # ── C++ 项目改名流程 ──

    def _rename_cpp_project_flow(
        self, new_name: str, new_path: str,
        old_path: Path, old_name: str, old_uproject: Path
    ) -> bool:
        """C++ 项目改名流程（保留原有逻辑）"""
        # C++ 项目：先备份
        if new_name != old_name:
            backup = self._backup_project(old_path)
            if not backup:
                self._show_error("备份失败，取消重命名")
                return False
            self._old_folder_name = old_path.name

        try:
            # 1. 重命名 .uproject 文件
            if new_name != old_name:
                new_uproject = old_path / f"{new_name}.uproject"
                if new_uproject.exists() and new_uproject != old_uproject:
                    self._show_error(f"文件 {new_name}.uproject 已存在")
                    return False
                old_uproject.rename(new_uproject)
                logger.info(f"重命名 .uproject: {old_uproject.name} → {new_uproject.name}")

                self._rename_cpp_project(old_path, old_name, new_name)

            # 2. 清理缓存（C++ 项目需要，但不清理 Saved）
            self._clean_cache(old_path)

            # 3. 编译验证
            if new_name != old_name:
                is_consistent, error_msg = self._check_project_naming_consistency(old_path)
                if not is_consistent:
                    dialog = ConfirmDialog(
                        "项目命名不规范",
                        "检测到项目命名不一致，可能导致编译失败。",
                        f"{error_msg}\n\n"
                        f"建议：\n"
                        f"• 跳过编译验证（推荐）- 改名后手动打开项目让 UE 自动修复\n"
                        f"• 取消改名 - 先手动修复项目命名问题\n\n"
                        f"是否跳过编译验证继续改名？",
                        self
                    )
                    if hasattr(dialog, 'center_on_parent'):
                        dialog.center_on_parent()
                    if dialog.exec() != QDialog.DialogCode.Accepted:
                        return False
                    logger.info("用户选择跳过编译验证")
                else:
                    compile_ok = self._compile_and_verify(new_name)
                    if not compile_ok:
                        return False

            # 4. 移动或重命名文件夹
            if new_path != self.project_path:
                final_path = Path(new_path) / (new_name if new_name != old_name else old_path.name)
                if final_path.exists():
                    self._show_error(f"目标路径已存在: {final_path}")
                    return False
                try:
                    shutil.move(str(old_path), str(final_path))
                    self.project_path = str(final_path)
                    self.path_input.setText(str(final_path))
                except PermissionError as e:
                    self._show_error(
                        f"文件夹移动失败：{e}\n\n"
                        f"可能原因：\n"
                        f"• UE 编辑器正在使用该项目\n"
                        f"• 文件管理器正在浏览该文件夹\n"
                        f"• 杀毒软件正在扫描文件\n\n"
                        f"建议：关闭占用进程后重试"
                    )
                    return False
            elif new_name != old_name:
                new_folder = old_path.parent / new_name
                if new_folder.exists():
                    self._show_error(f"文件夹已存在: {new_folder}")
                    return False
                try:
                    old_path.rename(new_folder)
                    self.project_path = str(new_folder)
                    self.path_input.setText(str(new_folder))
                except PermissionError as e:
                    self._show_error(
                        f"文件夹重命名失败：{e}\n\n"
                        f"可能原因：\n"
                        f"• UE 编辑器正在使用该项目\n"
                        f"• 文件管理器正在浏览该文件夹\n"
                        f"• 杀毒软件正在扫描文件\n\n"
                        f"建议：关闭占用进程后重试"
                    )
                    return False

            self.project_name = new_name
            backup_dir = _get_backup_dir()
            if backup_dir.exists():
                shutil.rmtree(backup_dir, ignore_errors=True)
            return True

        except Exception as e:
            logger.error(f"重命名项目失败: {e}", exc_info=True)
            self._show_error(f"重命名失败: {e}")
            return False


    def _get_real_module_name(self, project_path: Path) -> Optional[str]:
        """从 .uproject 文件读取真实的模块名"""
        try:
            uproject_files = list(project_path.glob("*.uproject"))
            if not uproject_files:
                return None
            
            with open(uproject_files[0], 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # 读取第一个模块名（通常是主模块）
            if 'Modules' in data and len(data['Modules']) > 0:
                module_name = data['Modules'][0].get('Name')
                logger.info(f"从 .uproject 读取到模块名: {module_name}")
                return module_name
        except Exception as e:
            logger.warning(f"读取模块名失败: {e}")
        return None

    def _check_project_naming_consistency(self, project_path: Path) -> tuple[bool, str]:
        """检查 C++ 项目命名是否规范
        
        Returns:
            (is_consistent, error_message)
        """
        try:
            source_dir = project_path / "Source"
            if not source_dir.exists():
                return True, ""
            
            # 1. 读取 .uproject 中的模块名
            module_name = self._get_real_module_name(project_path)
            if not module_name:
                return False, "无法读取 .uproject 中的模块名"
            
            # 2. 检查 Source 目录下是否有对应的模块文件夹
            module_dir = source_dir / module_name
            if not module_dir.exists():
                return False, f"Source 目录下找不到模块文件夹: {module_name}"
            
            # 3. 检查 Build.cs 文件名是否匹配
            build_cs = module_dir / f"{module_name}.Build.cs"
            if not build_cs.exists():
                # 列出实际存在的 Build.cs 文件
                actual_build_cs = list(module_dir.glob("*.Build.cs"))
                if actual_build_cs:
                    return False, f"Build.cs 文件名不匹配\n期望: {module_name}.Build.cs\n实际: {actual_build_cs[0].name}"
                else:
                    return False, f"找不到 {module_name}.Build.cs 文件"
            
            # 4. 检查 Target.cs 文件名是否匹配
            target_cs = source_dir / f"{module_name}.Target.cs"
            editor_target_cs = source_dir / f"{module_name}Editor.Target.cs"
            
            if not target_cs.exists():
                actual_target = list(source_dir.glob("*.Target.cs"))
                if actual_target:
                    return False, f"Target.cs 文件名不匹配\n期望: {module_name}.Target.cs\n实际: {actual_target[0].name}"
            
            logger.info(f"项目命名检查通过: {module_name}")
            return True, ""
            
        except Exception as e:
            logger.error(f"检查项目命名一致性失败: {e}", exc_info=True)
            return False, f"检查失败: {e}"

    def _compile_and_verify(self, new_name: str) -> bool:
        """编译验证，失败则回滚
        
        Args:
            new_name: 新的项目名（用于显示，不一定是模块名）
        """
        # 从 .uproject 读取真实的模块名
        module_name = self._get_real_module_name(Path(self.project_path))
        if not module_name:
            logger.warning("无法读取模块名，使用项目名作为模块名")
            module_name = new_name
        
        engine_path = _find_engine_path(self.project_version)
        if not engine_path:
            # 找不到引擎，跳过编译验证，给个警告
            dialog = MessageDialog(
                "无法自动编译",
                "找不到对应版本的引擎，无法自动编译验证。\n"
                "请手动打开项目确认是否正常。\n\n"
                "如果项目打不开，备份文件在配置目录中可手动恢复。",
                "warning",
                parent=self
            )
            dialog.exec()
            return True  # 继续，不阻塞

        # 创建编译进度对话框（参考导出对话框样式）
        from PyQt6.QtWidgets import QTextEdit, QProgressBar
        from PyQt6.QtGui import QFont
        
        progress_dialog = QDialog(self)
        progress_dialog.setWindowTitle("编译验证")
        progress_dialog.setFixedSize(450, 280)
        progress_dialog.setWindowFlags(progress_dialog.windowFlags() & ~Qt.WindowType.WindowContextHelpButtonHint)
        
        layout = QVBoxLayout()
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)
        
        # 标题
        title_label = QLabel(f"🔨 编译项目: {new_name}")
        title_label.setFont(QFont("Microsoft YaHei", 12, QFont.Weight.Bold))
        layout.addWidget(title_label)
        
        # 状态标签
        status_label = QLabel("准备编译...")
        status_label.setObjectName("CompileStatusLabel")
        layout.addWidget(status_label)
        
        # 当前文件标签（显示模块名）
        file_label = QLabel(f"模块: {module_name}")
        file_label.setStyleSheet("color: #888888; font-size: 11px;")
        layout.addWidget(file_label)
        
        # 进度条（不确定模式）
        progress_bar = QProgressBar()
        progress_bar.setMinimum(0)
        progress_bar.setMaximum(0)  # 不确定模式
        progress_bar.setTextVisible(True)
        progress_bar.setFixedHeight(24)
        layout.addWidget(progress_bar)
        
        layout.addStretch()
        
        # 按钮区域
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        
        close_btn = QPushButton("关闭")
        close_btn.setFixedWidth(80)
        close_btn.clicked.connect(progress_dialog.accept)
        close_btn.hide()
        btn_layout.addWidget(close_btn)
        
        layout.addLayout(btn_layout)
        progress_dialog.setLayout(layout)
        progress_dialog.show()
        QApplication.processEvents()

        # 启动编译线程
        thread = _CompileThread(engine_path, Path(self.project_path), module_name)
        
        # 连接信号
        def update_status(text: str):
            status_label.setText(text)
            QApplication.processEvents()
        
        def update_file(text: str):
            file_label.setText(text)
            QApplication.processEvents()
        
        thread.status_updated.connect(update_status)
        thread.progress.connect(update_file)
        thread.start()

        # 等待编译完成
        while thread.isRunning():
            QApplication.processEvents()
            thread.wait(100)

        # 编译完成，停止进度条
        progress_bar.setMaximum(100)
        progress_bar.setValue(100 if thread.success else 0)
        
        # 更新状态标签样式
        if thread.success:
            status_label.setText("✅ 编译成功！")
            status_label.setStyleSheet("color: #4CAF50; font-weight: bold;")
        else:
            status_label.setText("❌ 编译失败")
            status_label.setStyleSheet("color: #F44336; font-weight: bold;")
        
        file_label.setText("")
        close_btn.show()

        # 等待用户查看结果
        progress_dialog.exec()

        if thread.success:
            logger.info("C++ 项目编译验证通过")
            return True
        else:
            logger.error(f"C++ 项目编译失败: {thread.message}")
            
            # 保存完整日志到临时文件
            import tempfile
            log_file = Path(tempfile.gettempdir()) / f"ue_compile_error_{module_name}.log"
            try:
                log_file.write_text(thread.full_log, encoding='utf-8')
                log_path_str = str(log_file)
            except Exception:
                log_path_str = "日志保存失败"
            
            error_dialog = MessageDialog(
                "编译失败 - 自动回滚",
                f"重命名后编译失败，将自动恢复到原始状态。\n\n"
                f"错误信息:\n{thread.message[:300]}\n\n"
                f"完整日志已保存到:\n{log_path_str}",
                "error",
                parent=self
            )
            error_dialog.exec()
            # 自动回滚
            if self._rollback_project():
                ok_dialog = MessageDialog("已恢复", "项目已成功恢复到重命名前的状态。", "success", parent=self)
                ok_dialog.exec()
            else:
                fail_dialog = MessageDialog(
                    "恢复失败",
                    f"自动恢复失败，请手动从备份目录恢复:\n{_get_backup_dir()}",
                    "warning",
                    parent=self
                )
                fail_dialog.exec()
            return False


    # ── C++ 项目重命名 ──

    def _rename_cpp_project(self, project_path: Path, old_name: str, new_name: str):
        """重命名 C++ 项目的所有相关文件和内容

        完整步骤（参考 unrealistic.dev 指南 + Renom 工具 + UE 论坛最佳实践）：
        1. 重命名 Source/模块文件夹及其内部文件
        2. 重命名 .Target.cs 文件
        3. 重命名 .Build.cs 文件
        4. 全量替换 Source 下所有源文件内容（API 宏 + 模块名）
        5. 更新 .uproject 中的模块名
        6. 更新 Config/DefaultEngine.ini（GameName + ActiveGameNameRedirects）
        7. 更新 Config/DefaultGame.ini（ProjectName）
        8. 替换 Config/*.ini 中的 /Script/OldName 引用
        9. 删除旧 .sln 文件
        """
        source_dir = project_path / "Source"
        config_dir = project_path / "Config"
        if not source_dir.exists():
            logger.warning("Source 目录不存在，跳过 C++ 重命名")
            return

        old_api = old_name.upper() + "_API"
        new_api = new_name.upper() + "_API"

        logger.info(f"开始重命名 C++ 项目: {old_name} → {new_name}")

        try:
            # 1. 重命名模块文件夹
            old_module_dir = source_dir / old_name
            new_module_dir = source_dir / new_name
            if old_module_dir.exists():
                old_module_dir.rename(new_module_dir)
                logger.info(f"✓ 重命名模块文件夹: {old_name} → {new_name}")

                # 重命名模块内包含旧名的文件（递归，含子目录）
                for file in list(new_module_dir.rglob("*")):
                    if file.is_file() and old_name in file.name:
                        new_file_name = file.name.replace(old_name, new_name)
                        file.rename(file.parent / new_file_name)
                        logger.info(f"  ✓ 重命名文件: {file.name} → {new_file_name}")
            else:
                logger.warning(f"模块文件夹不存在: {old_module_dir}")

            # 2. 重命名 .Target.cs 文件
            target_files = list(source_dir.glob(f"{old_name}*.Target.cs"))
            for target_file in target_files:
                new_target_name = target_file.name.replace(old_name, new_name)
                target_file.rename(source_dir / new_target_name)
                logger.info(f"✓ 重命名 Target 文件: {target_file.name} → {new_target_name}")

            # 3. 重命名 .Build.cs 文件
            if new_module_dir.exists():
                for build_file in list(new_module_dir.glob("*.Build.cs")):
                    if old_name in build_file.name:
                        new_build_name = build_file.name.replace(old_name, new_name)
                        build_file.rename(new_module_dir / new_build_name)
                        logger.info(f"✓ 重命名 Build 文件: {build_file.name} → {new_build_name}")

            # 4. 全量替换所有源文件内容
            #    先替换 API 宏（更精确），再替换模块名（更宽泛）
            for src_file in source_dir.rglob("*"):
                if not src_file.is_file():
                    continue
                if src_file.suffix not in ('.h', '.cpp', '.cs', '.ini', '.txt'):
                    continue
                self._replace_in_file(src_file, old_api, new_api, old_name, new_name)

            # 5. 更新 .uproject 中的模块名
            for uproject_file in project_path.glob("*.uproject"):
                try:
                    with open(uproject_file, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                    if 'Modules' in data:
                        for module in data['Modules']:
                            if module.get('Name') == old_name:
                                module['Name'] = new_name
                    with open(uproject_file, 'w', encoding='utf-8') as f:
                        json.dump(data, f, indent='\t', ensure_ascii=False)
                    logger.info(f"更新 .uproject 模块名: {old_name} → {new_name}")
                except Exception as e:
                    logger.warning(f"更新 .uproject 失败: {e}")

            # 6. 更新 Config/DefaultEngine.ini
            if config_dir.exists():
                engine_ini = config_dir / "DefaultEngine.ini"
                if engine_ini.exists():
                    self._update_engine_ini(engine_ini, old_name, new_name)

            # 7. 更新 Config/DefaultGame.ini
            if config_dir.exists():
                game_ini = config_dir / "DefaultGame.ini"
                if game_ini.exists():
                    self._update_game_ini(game_ini, new_name)

            # 8. 替换 Config/*.ini 中的 /Script/OldName 引用
            #    例如 GlobalDefaultGameMode=/Script/OldName.OldNameGameMode
            if config_dir.exists():
                for ini_file in config_dir.glob("*.ini"):
                    self._replace_in_file(
                        ini_file,
                        f"/Script/{old_name}", f"/Script/{new_name}",
                        None, None  # 不做通用名称替换，只替换 /Script/ 路径
                    )

            # 9. 删除旧 .sln 文件（让 UE 重新生成）
            for sln_file in project_path.glob("*.sln"):
                try:
                    sln_file.unlink()
                    logger.info(f"已删除旧 .sln: {sln_file.name}")
                except Exception as e:
                    logger.warning(f"删除 .sln 失败: {e}")

        except Exception as e:
            logger.error(f"重命名 C++ 项目文件失败: {e}", exc_info=True)

    def _replace_in_file(self, file_path: Path,
                         old_str1: str, new_str1: str,
                         old_str2: Optional[str], new_str2: Optional[str]):
        """替换文件中的字符串，支持多种编码"""
        try:
            content = None
            for enc in ('utf-8', 'utf-8-sig', 'gbk', 'latin-1'):
                try:
                    content = file_path.read_text(encoding=enc)
                    break
                except (UnicodeDecodeError, ValueError):
                    continue
            if content is None:
                return

            new_content = content
            if old_str1 and new_str1:
                new_content = new_content.replace(old_str1, new_str1)
            if old_str2 and new_str2:
                new_content = new_content.replace(old_str2, new_str2)
            if new_content != content:
                file_path.write_text(new_content, encoding='utf-8')
                logger.info(f"已替换文件内容: {file_path.name}")
        except Exception as e:
            logger.warning(f"替换文件内容失败 {file_path}: {e}")

    def _update_engine_ini(self, engine_ini: Path, old_name: str, new_name: str):
        """更新 DefaultEngine.ini：GameName + ActiveGameNameRedirects"""
        try:
            # 检测原始编码
            encoding = self._detect_file_encoding(engine_ini)
            content = engine_ini.read_text(encoding=encoding)

            # 添加或更新 [URL] GameName
            if '[URL]' in content:
                # 替换已有的 GameName
                import re
                content = re.sub(
                    r'(\[URL\]\s*\n)(GameName=.*\n)?',
                    f'\\1GameName={new_name}\n',
                    content
                )
            else:
                content = f"[URL]\nGameName={new_name}\n\n" + content

            # 添加 ActiveGameNameRedirects
            # 关键：UE 不跟踪重定向链，所有旧名都必须直接指向最终名
            redirect_section = "[/Script/Engine.Engine]"
            new_redirect = (
                f'+ActiveGameNameRedirects=(OldGameName="{old_name}",'
                f'NewGameName="/Script/{new_name}")\n'
                f'+ActiveGameNameRedirects=(OldGameName="/Script/{old_name}",'
                f'NewGameName="/Script/{new_name}")'
            )

            if redirect_section in content:
                # 更新已有的 redirect：把指向旧名的都改为指向新名
                content = content.replace(
                    f'NewGameName="/Script/{old_name}"',
                    f'NewGameName="/Script/{new_name}"'
                )
                # 检查是否已有从 old_name 到 new_name 的 redirect
                if f'OldGameName="{old_name}"' not in content:
                    content = content.replace(
                        redirect_section,
                        f"{redirect_section}\n{new_redirect}"
                    )
            else:
                content += f"\n{redirect_section}\n{new_redirect}\n"

            engine_ini.write_text(content, encoding=encoding)
            logger.info(f"更新 DefaultEngine.ini: GameName={new_name}, 添加 ActiveGameNameRedirects (编码: {encoding})")
        except Exception as e:
            logger.warning(f"更新 DefaultEngine.ini 失败: {e}")

    def _update_game_ini(self, game_ini: Path, new_name: str):
        """更新 DefaultGame.ini：ProjectName"""
        try:
            if game_ini.exists():
                encoding = self._detect_file_encoding(game_ini)
                content = game_ini.read_text(encoding=encoding)
            else:
                encoding = 'utf-8'
                content = ""
            
            # 统一换行符，避免 \r\r\n 导致正则失效
            content = content.replace('\r\n', '\n').replace('\r', '\n')

            section = "[/Script/EngineSettings.GeneralProjectSettings]"
            if section in content:
                import re
                if 'ProjectName=' in content:
                    # 用 [^\n]* 避免 .* 在多余 \r 下失效
                    content = re.sub(r'ProjectName=[^\n]*', f'ProjectName={new_name}', content)
                else:
                    content = content.replace(section, f"{section}\nProjectName={new_name}")
            else:
                content += f"\n{section}\nProjectName={new_name}\n"

            game_ini.write_text(content, encoding=encoding)
            logger.info(f"更新 DefaultGame.ini: ProjectName={new_name} (编码: {encoding})")
        except Exception as e:
            logger.warning(f"更新 DefaultGame.ini 失败: {e}")

    def _clean_cache(self, project_path: Path):
        """清理 C++ 编译缓存（不清理 Saved 目录）"""
        for d in ['Intermediate', 'Binaries', '.vs', 'DerivedDataCache']:
            p = project_path / d
            if p.exists():
                try:
                    shutil.rmtree(p)
                    logger.info(f"已清理缓存: {p}")
                except Exception as e:
                    logger.warning(f"清理缓存失败 {p}: {e}")

    # ── 公共接口 ──

    def get_project_info(self) -> dict:
        return {
            "name": self.name_input.text().strip(),
            "path": self.path_input.text().strip(),
            "category": self.category_combo.currentText().strip()
        }

    def _get_main_window(self):
        """向上查找主窗口实例"""
        widget = self.parent()
        while widget is not None:
            if hasattr(widget, 'show_status') and hasattr(widget, 'hide_status'):
                return widget
            widget = widget.parent() if hasattr(widget, 'parent') else None
        return None

    def _show_stage(self, stage: int, total: int, title: str, detail: str, progress: int = -1):
        """进入改名阶段：委托给进度控制器"""
        ctrl = getattr(self, '_prog_ctrl', None)
        if ctrl:
            ctrl.enter_stage(stage, title, detail)
        else:
            # 降级：直接更新主窗口状态指示器
            mw = self._get_main_window()
            if mw:
                label = f"阶段 {stage}/{total} · {title}"
                actual_progress = progress if progress >= 0 else int((stage - 1) / total * 100)
                mw.show_status(label, detail, actual_progress)
            QApplication.processEvents()

    def _end_stage(self, stage: int):
        """完成改名阶段：委托给进度控制器"""
        ctrl = getattr(self, '_prog_ctrl', None)
        if ctrl:
            ctrl.leave_stage(stage)

    def _hide_stage(self):
        """改名全部完成：隐藏指示器、清理详情按钮（由控制器 finish 负责）"""
        mw = self._get_main_window()
        if mw and hasattr(mw, 'set_status_detail_callback'):
            mw.set_status_detail_callback(None)

    def _show_error(self, message: str):
        """显示错误对话框，并关闭详情弹窗（如果存在）"""
        # 关闭详情弹窗（改名中途出错时详情弹窗仍在屏幕上）
        dlg = getattr(self, '_progress_dlg', None)
        if dlg and dlg.isVisible():
            dlg.hide()

        # 清理主窗口状态指示器详情按钮回调
        mw = self._get_main_window()
        if mw and hasattr(mw, 'set_status_detail_callback'):
            mw.set_status_detail_callback(None)

        dialog = MessageDialog("错误", message, "error", parent=mw or self)
        dialog.exec()

    def _title_bar_mouse_press(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.drag_position = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()

    def _title_bar_mouse_move(self, event):
        if event.buttons() == Qt.MouseButton.LeftButton:
            self.move(event.globalPosition().toPoint() - self.drag_position)
            event.accept()

    def showEvent(self, event):
        super().showEvent(event)
        self.center_on_parent()

    def center_on_parent(self):
        if self.parent():
            parent = self.parent()
            top_window = parent
            while top_window.parent():
                top_window = top_window.parent()
            parent_geo = top_window.geometry()
            parent_pos = top_window.pos()
            x = parent_pos.x() + (parent_geo.width() - self.width()) // 2
            y = parent_pos.y() + (parent_geo.height() - self.height()) // 2
            self.move(x, y)
        else:
            screen = QApplication.primaryScreen().availableGeometry()
            x = screen.x() + (screen.width() - self.width()) // 2
            y = screen.y() + (screen.height() - self.height()) // 2
            self.move(x, y)

    @staticmethod
    def _detect_file_encoding(file_path: Path) -> str:
        """检测文件编码：优先读取 BOM，再回退到内容探测"""
        try:
            raw = file_path.read_bytes()
        except Exception:
            return 'utf-8'
        if raw[:2] == b'\xff\xfe':
            return 'utf-16-le'
        if raw[:2] == b'\xfe\xff':
            return 'utf-16-be'
        if raw[:3] == b'\xef\xbb\xbf':
            return 'utf-8-sig'
        try:
            raw.decode('utf-8')
            return 'utf-8'
        except (UnicodeDecodeError, ValueError):
            pass
        try:
            raw.decode('gbk')
            return 'gbk'
        except (UnicodeDecodeError, ValueError):
            pass
        return 'utf-8'
