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
    QFileDialog, QMessageBox, QProgressDialog, QApplication
)
from PyQt6.QtCore import Qt, QPoint, pyqtSignal, QThread

from core.logger import get_logger

logger = get_logger(__name__)


def _get_backup_dir() -> Path:
    """获取备份目录"""
    from PyQt6.QtCore import QStandardPaths
    app_data = QStandardPaths.writableLocation(
        QStandardPaths.StandardLocation.AppDataLocation
    )
    return Path(app_data) / "ue_toolkit" / "my_projects" / "rename_backup"


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
        source_dir = Path(self.project_path) / "Source"
        return source_dir.exists() and any(source_dir.glob("*.Target.cs"))

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
                ret = QMessageBox.question(
                    self, "确认重命名", msg,
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                    QMessageBox.StandardButton.No
                )
                if ret != QMessageBox.StandardButton.Yes:
                    return

            success = self._rename_project(new_name, new_path)
            if not success:
                # 编译失败已经回滚，关闭对话框
                self.reject()
                return

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
                content = ini_file.read_text(encoding='utf-8')
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
            content = engine_ini.read_text(encoding='utf-8')
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

        if engine_ini.exists():
            content = engine_ini.read_text(encoding='utf-8')
        else:
            content = ""

        # 1. 更新 [URL] GameName
        if '[URL]' in content:
            if re.search(r'GameName=', content):
                content = re.sub(r'GameName=.*', f'GameName={new_name}', content)
            else:
                content = content.replace('[URL]', f'[URL]\nGameName={new_name}')
        else:
            content = f"[URL]\nGameName={new_name}\n\n" + content

        # 2. 检测是否需要 redirect
        high_risk, _ = self._scan_script_references(project_path, old_name)
        has_history = self._has_existing_redirects(project_path, old_name)

        if high_risk or has_history:
            # 写入 CoreRedirects（官方推荐 UE5）
            core_redirect = (
                f'+PackageRedirects=(OldName="/Script/{old_name}",'
                f'NewName="/Script/{new_name}")'
            )
            if '[CoreRedirects]' in content:
                # 更新已有的：把指向旧名的都改为指向新名
                content = re.sub(
                    rf'NewName="/Script/{re.escape(old_name)}"',
                    f'NewName="/Script/{new_name}"',
                    content, flags=re.IGNORECASE
                )
                # 检查是否已有从 old_name 到 new_name 的 redirect
                if f'OldName="/Script/{old_name}"' not in content:
                    content = content.replace(
                        '[CoreRedirects]',
                        f'[CoreRedirects]\n{core_redirect}'
                    )
            else:
                content += f"\n[CoreRedirects]\n{core_redirect}\n"

            # 兼容写法（旧引擎）
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

            # 更新 _meta.json
            self._update_backup_meta(
                redirects_added=[f"/Script/{old_name}"],
                engine_ini_modified=True
            )
            logger.info(f"已添加 redirect: /Script/{old_name} → /Script/{new_name}")
        else:
            self._update_backup_meta(engine_ini_modified=True)
            logger.info("未检测到 /Script/ 引用，跳过 redirect")

        engine_ini.write_text(content, encoding='utf-8')
        logger.info(f"更新 DefaultEngine.ini: GameName={new_name}")

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

    def _rollback_blueprint_project(self):
        """蓝图项目回滚：从备份还原"""
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

            # 1. 如果文件夹已改名，先改回去
            if current_path.name != original_path.name and current_path.exists():
                restored_path = current_path.parent / original_path.name
                if not restored_path.exists():
                    current_path.rename(restored_path)
                    current_path = restored_path
                    self.project_path = str(restored_path)
                    logger.info(f"文件夹已回滚: {current_path.name} → {original_path.name}")

            # 2. 还原 Config/
            backup_config = backup_dir / "Config"
            if backup_config.exists():
                current_config = current_path / "Config"
                if current_config.exists():
                    shutil.rmtree(current_config)
                shutil.copytree(backup_config, current_config)

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
                # 删除当前的 .uproject
                for up_current in current_path.glob("*.uproject"):
                    up_current.unlink()
                shutil.copy2(up_backup, current_path / up_backup.name)

            self.project_name = original_name

            # 5. 清理备份
            shutil.rmtree(backup_dir, ignore_errors=True)

            logger.info("蓝图项目已回滚到原始状态")
            return True
        except Exception as e:
            logger.error(f"蓝图项目回滚失败: {e}", exc_info=True)
            return False

    def _verify_rename(self, project_path: Path, old_name: str) -> list:
        """改名后验证，返回警告列表"""
        warnings = []
        high_risk, low_risk = self._scan_script_references(project_path, old_name)

        for ref in high_risk:
            warnings.append(f"⚠️ 高风险残留: {ref}")
        for ref in low_risk[:5]:  # 普通残留最多显示5条
            warnings.append(f"ℹ️ 普通残留: {ref}")
        if len(low_risk) > 5:
            warnings.append(f"ℹ️ ...还有 {len(low_risk) - 5} 处普通残留")

        return warnings

    def _rename_blueprint_project_flow(
        self, new_name: str, new_path: str,
        old_path: Path, old_name: str, old_uproject: Path
    ) -> bool:
        """蓝图项目改名完整流程"""
        try:
            # Step 1: 轻量备份
            backup_dir = self._backup_blueprint_project(old_path, old_name, new_name)
            if not backup_dir:
                self._show_error("备份失败，取消重命名")
                return False

            # Step 2a: 更新 Config/DefaultEngine.ini
            if new_name != old_name:
                self._update_engine_ini_blueprint(old_path, old_name, new_name)

                # Step 2b: 更新 Config/DefaultGame.ini
                config_dir = old_path / "Config"
                config_dir.mkdir(parents=True, exist_ok=True)
                self._update_game_ini(config_dir / "DefaultGame.ini", new_name)
                self._update_backup_meta(game_ini_modified=True)

            # Step 3: 重命名 .uproject
            if new_name != old_name:
                new_uproject = old_path / f"{new_name}.uproject"
                if new_uproject.exists() and new_uproject != old_uproject:
                    self._rollback_blueprint_project()
                    self._show_error(f"文件 {new_name}.uproject 已存在")
                    return False
                old_uproject.rename(new_uproject)
                logger.info(f"重命名 .uproject: {old_uproject.name} → {new_uproject.name}")

            # Step 4: 重命名项目根目录
            if new_path != self.project_path:
                final_path = Path(new_path) / (new_name if new_name != old_name else old_path.name)
                if final_path.exists():
                    self._rollback_blueprint_project()
                    self._show_error(f"目标路径已存在: {final_path}")
                    return False
                shutil.move(str(old_path), str(final_path))
                self.project_path = str(final_path)
                self.path_input.setText(str(final_path))
            elif new_name != old_name:
                new_folder = old_path.parent / new_name
                if new_folder.exists():
                    self._rollback_blueprint_project()
                    self._show_error(f"文件夹已存在: {new_folder}")
                    return False
                old_path.rename(new_folder)
                self.project_path = str(new_folder)
                self.path_input.setText(str(new_folder))

            self.project_name = new_name

            # Step 5: 验证
            final_project_path = Path(self.project_path)
            warnings = self._verify_rename(final_project_path, old_name)
            if warnings:
                warning_msg = "\n".join(warnings)
                QMessageBox.warning(
                    self, "改名完成 - 请检查",
                    f"项目已成功改名，但检测到以下残留引用：\n\n"
                    f"{warning_msg}\n\n"
                    f"建议打开项目检查：\n"
                    f"• GameMode / PlayerController / HUD 是否正常\n"
                    f"• Project Settings 里名称显示是否正确"
                )
            else:
                logger.info("改名验证通过，未发现残留引用")

            # 清理备份
            if backup_dir.exists():
                shutil.rmtree(backup_dir, ignore_errors=True)
            return True

        except Exception as e:
            logger.error(f"蓝图项目重命名失败: {e}", exc_info=True)
            self._rollback_blueprint_project()
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
                    ret = QMessageBox.warning(
                        self, "项目命名不规范",
                        f"检测到项目命名不一致，可能导致编译失败：\n\n{error_msg}\n\n"
                        f"建议：\n"
                        f"• 跳过编译验证（推荐）- 改名后手动打开项目让 UE 自动修复\n"
                        f"• 取消改名 - 先手动修复项目命名问题\n\n"
                        f"是否跳过编译验证继续改名？",
                        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                        QMessageBox.StandardButton.Yes
                    )
                    if ret == QMessageBox.StandardButton.No:
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
                shutil.move(str(old_path), str(final_path))
                self.project_path = str(final_path)
                self.path_input.setText(str(final_path))
            elif new_name != old_name:
                new_folder = old_path.parent / new_name
                if new_folder.exists():
                    self._show_error(f"文件夹已存在: {new_folder}")
                    return False
                old_path.rename(new_folder)
                self.project_path = str(new_folder)
                self.path_input.setText(str(new_folder))

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
            ret = QMessageBox.warning(
                self, "无法自动编译",
                "找不到对应版本的引擎，无法自动编译验证。\n"
                "请手动打开项目确认是否正常。\n\n"
                "如果项目打不开，备份文件在配置目录中可手动恢复。",
                QMessageBox.StandardButton.Ok
            )
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
            
            QMessageBox.critical(
                self, "编译失败 - 自动回滚",
                f"重命名后编译失败，将自动恢复到原始状态。\n\n"
                f"错误信息:\n{thread.message[:300]}\n\n"
                f"完整日志已保存到:\n{log_path_str}",
                QMessageBox.StandardButton.Ok
            )
            # 自动回滚
            if self._rollback_project():
                QMessageBox.information(self, "已恢复", "项目已成功恢复到重命名前的状态。")
            else:
                QMessageBox.warning(
                    self, "恢复失败",
                    f"自动恢复失败，请手动从备份目录恢复:\n{_get_backup_dir()}"
                )
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
            content = engine_ini.read_text(encoding='utf-8')

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

            engine_ini.write_text(content, encoding='utf-8')
            logger.info(f"更新 DefaultEngine.ini: GameName={new_name}, 添加 ActiveGameNameRedirects")
        except Exception as e:
            logger.warning(f"更新 DefaultEngine.ini 失败: {e}")

    def _update_game_ini(self, game_ini: Path, new_name: str):
        """更新 DefaultGame.ini：ProjectName"""
        try:
            content = game_ini.read_text(encoding='utf-8')
            section = "[/Script/EngineSettings.GeneralProjectSettings]"

            if section in content:
                import re
                if 'ProjectName=' in content:
                    content = re.sub(r'ProjectName=.*', f'ProjectName={new_name}', content)
                else:
                    content = content.replace(section, f"{section}\nProjectName={new_name}")
            else:
                content += f"\n{section}\nProjectName={new_name}\n"

            game_ini.write_text(content, encoding='utf-8')
            logger.info(f"更新 DefaultGame.ini: ProjectName={new_name}")
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

    def _show_error(self, message: str):
        self.error_label.setText(f"⚠ {message}")

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
