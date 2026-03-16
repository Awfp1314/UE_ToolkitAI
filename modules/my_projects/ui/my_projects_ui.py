# -*- coding: utf-8 -*-

"""
我的工程 UI - 参考资产库界面风格

启动流程：
1. 有注册表 → 立即显示已知工程 → 后台增量扫描新工程
2. 无注册表 → 全量扫描 → 保存注册表
"""

import json
from pathlib import Path
from datetime import datetime

from PyQt6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QFrame, QScrollArea, QLineEdit, QComboBox,
    QGridLayout, QProgressBar, QMenu, QMessageBox
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QRectF, QPoint, QTimer, QObject, QEvent, QFileSystemWatcher
from PyQt6.QtGui import (
    QFont, QPixmap, QPainter, QColor, QPainterPath, QLinearGradient, QAction
)

from core.logger import get_logger
from modules.base_module_widget import BaseModuleWidget
from modules.my_projects.logic.project_registry import ProjectRegistry, TOOLKIT_CONFIG_DIR

logger = get_logger(__name__)


class RoundedThumbnail(QWidget):
    """圆角缩略图控件"""

    def __init__(self, w=168, h=108, r=0, parent=None):
        super().__init__(parent)
        self.setFixedSize(w, h)
        self.r = r
        self._pixmap = None
        self.bg = "rgba(0,0,0,0.3)"
        self.tc = "#606060"

    def setPixmap(self, p):
        self._pixmap = p if p and not p.isNull() else None
        self.update()

    def set_theme(self, is_dark):
        self.bg = "rgba(0,0,0,0.3)" if is_dark else "rgba(255,255,255,0.5)"
        self.tc = "#606060" if is_dark else "#a0a0a0"
        self.update()

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        path = QPainterPath()
        path.addRoundedRect(QRectF(self.rect()), self.r, self.r)
        p.setClipPath(path)

        if self._pixmap:
            p.drawPixmap(0, 0, self._pixmap)
        else:
            p.fillRect(self.rect(), QColor(self.bg))
            p.setPen(QColor(self.tc))
            p.setFont(QFont("Segoe UI Emoji", 32))
            p.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "📁")
        p.end()


class _MenuAutoClose(QObject):
    """右键菜单自动关闭 - 鼠标离开菜单区域时关闭"""

    def __init__(self, menu, card):
        super().__init__()
        self.menu = menu
        self.card = card
        self._was_inside = True

        app = QApplication.instance()
        if app:
            app.installEventFilter(self)

        self._timer = QTimer()
        self._timer.timeout.connect(self._check)
        self._timer.start(50)

    def eventFilter(self, obj, event):
        try:
            if not self.menu or not self.menu.isVisible():
                return False
        except RuntimeError:
            return False

        if event and event.type() == QEvent.Type.MouseButtonPress:
            from PyQt6.QtGui import QCursor
            pos = QCursor.pos()
            rect = self.menu.rect().translated(self.menu.mapToGlobal(self.menu.rect().topLeft()))
            if not rect.contains(pos):
                self._close()
        return False

    def _check(self):
        try:
            if not self.menu or not self.menu.isVisible():
                self._timer.stop()
                return
        except RuntimeError:
            self._timer.stop()
            return

        from PyQt6.QtGui import QCursor
        pos = QCursor.pos()
        rect = self.menu.rect().translated(self.menu.mapToGlobal(self.menu.rect().topLeft()))
        inside = rect.contains(pos)

        if self._was_inside and not inside:
            self._close()
        if inside:
            self._was_inside = True

    def _close(self):
        try:
            if self.menu and self.menu.isVisible():
                self._timer.stop()
                app = QApplication.instance()
                if app:
                    app.removeEventFilter(self)
                self.menu.hide()
                self.menu.deleteLater()
                self.menu = None
        except RuntimeError:
            self._timer.stop()
            self.menu = None


class ProjectCard(QFrame):
    """工程卡片 - 参考资产卡片风格"""

    open_requested = pyqtSignal(str)
    delete_requested = pyqtSignal(str)
    category_changed = pyqtSignal(str, str)  # (project_path, new_category)
    edit_requested = pyqtSignal(str, str, str, str)  # (old_path, new_path, new_name, new_category)

    def __init__(self, name, path, version, modified, theme, thumb_path=None, categories=None, current_category="默认", parent=None):
        super().__init__(parent)
        self.name = name
        self.path = path
        self.version = version
        self.modified = modified
        self.theme = theme
        self.thumb_path = thumb_path
        self.categories = categories or ["默认"]
        self.current_category = current_category
        self._is_hovered = False

        self.setObjectName("CompactAssetCard")
        self.setFixedSize(180, 200)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setMouseTracking(True)
        self.setAttribute(Qt.WidgetAttribute.WA_Hover, True)

        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # 缩略图区域
        thumb_section = QWidget()
        thumb_section.setObjectName("MyProjectCardThumb")
        thumb_section.setFixedHeight(114)
        thumb_layout = QVBoxLayout(thumb_section)
        thumb_layout.setContentsMargins(4, 4, 4, 4)
        thumb_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.thumb = RoundedThumbnail(172, 106, 0, self)

        if self.thumb_path and Path(self.thumb_path).exists():
            try:
                pixmap = QPixmap(self.thumb_path)
                if not pixmap.isNull():
                    scaled = pixmap.scaled(
                        172, 106,
                        Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                        Qt.TransformationMode.SmoothTransformation
                    )
                    if scaled.width() > 172 or scaled.height() > 106:
                        x = (scaled.width() - 172) // 2
                        y = (scaled.height() - 106) // 2
                        scaled = scaled.copy(x, y, 172, 106)
                    self.thumb.setPixmap(scaled)
            except Exception:
                pass

        thumb_layout.addWidget(self.thumb)
        layout.addWidget(thumb_section)

        # 版本徽标 - 蓝色背景，右上角
        self.version_label = QLabel(f"UE {self.version}")
        self.version_label.setObjectName("MyProjectVersionLabel")
        self.version_label.setParent(self.thumb)
        self.version_label.setStyleSheet("""
            QLabel {
                color: #ffffff;
                font-size: 11px;
                font-weight: bold;
                background-color: rgba(0, 122, 204, 0.85);
                border-radius: 3px;
                padding: 3px 6px;
            }
        """)
        self.version_label.setTextInteractionFlags(Qt.TextInteractionFlag.NoTextInteraction)
        self.version_label.setCursor(Qt.CursorShape.ArrowCursor)
        self.version_label.setFixedSize(self.version_label.sizeHint())
        self.version_label.move(172 - 8 - self.version_label.width(), 8)

        # 分类徽标 - 黑色背景，左下角
        self.category_label = QLabel(self.current_category)
        self.category_label.setObjectName("MyCategoryLabel")
        self.category_label.setParent(self.thumb)
        self.category_label.setStyleSheet("""
            QLabel {
                color: #b0b0b0;
                font-size: 11px;
                font-weight: 600;
                background-color: #000000;
                border-radius: 0px;
                padding: 4px 10px;
            }
        """)
        self.category_label.setTextInteractionFlags(Qt.TextInteractionFlag.NoTextInteraction)
        self.category_label.setCursor(Qt.CursorShape.ArrowCursor)
        self.category_label.setFixedSize(self.category_label.sizeHint())
        self.category_label.move(8, 106 - 8 - self.category_label.height())

        # 信息区域
        info_widget = QWidget()
        info_widget.setObjectName("MyProjectCardInfo")
        info_layout = QVBoxLayout(info_widget)
        info_layout.setContentsMargins(8, 6, 8, 8)
        info_layout.setSpacing(3)

        name_label = QLabel(self.name)
        name_label.setObjectName("NameLabel")
        name_label.setWordWrap(True)
        name_label.setFixedHeight(28)
        name_label.setTextInteractionFlags(Qt.TextInteractionFlag.NoTextInteraction)
        name_color = "#ffffff" if self.theme != "light" else "#1a1a1a"
        f = QFont()
        f.setPointSize(9)
        f.setBold(True)
        name_label.setFont(f)
        name_label.setStyleSheet(f"color: {name_color};")
        info_layout.addWidget(name_label)
        self._name_label = name_label

        if self.modified:
            time_label = QLabel(f"📅 {self.modified}")
            time_label.setObjectName("InfoTitleLabel")
            time_color = "#888888" if self.theme != "light" else "#999999"
            f2 = QFont()
            f2.setPointSize(7)
            time_label.setFont(f2)
            time_label.setStyleSheet(f"color: {time_color};")
            time_label.setTextInteractionFlags(Qt.TextInteractionFlag.NoTextInteraction)
            info_layout.addWidget(time_label)
            self._time_label = time_label
        else:
            self._time_label = None

        self.open_btn = QPushButton("▶  打开工程")
        self.open_btn.setObjectName("PreviewButton")
        self.open_btn.setFixedHeight(28)
        self.open_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.open_btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.open_btn.clicked.connect(lambda: self.open_requested.emit(self.path))
        info_layout.addWidget(self.open_btn)

        layout.addWidget(info_widget)

        # 右键菜单
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self._show_context_menu)

    def update_thumbnail(self, new_thumb_path):
        """更新缩略图（不重建卡片）"""
        if new_thumb_path == self.thumb_path:
            return
        self.thumb_path = new_thumb_path
        if new_thumb_path and Path(new_thumb_path).exists():
            try:
                pixmap = QPixmap(new_thumb_path)
                if not pixmap.isNull():
                    scaled = pixmap.scaled(
                        172, 106,
                        Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                        Qt.TransformationMode.SmoothTransformation
                    )
                    if scaled.width() > 172 or scaled.height() > 106:
                        x = (scaled.width() - 172) // 2
                        y = (scaled.height() - 106) // 2
                        scaled = scaled.copy(x, y, 172, 106)
                    self.thumb.setPixmap(scaled)
                    return
            except Exception:
                pass
        self.thumb.setPixmap(None)

    def set_theme(self, theme):
        self.theme = theme
        self.thumb.set_theme(theme == "dark")
        # 更新文字颜色
        name_color = "#ffffff" if theme != "light" else "#1a1a1a"
        time_color = "#888888" if theme != "light" else "#999999"
        if hasattr(self, '_name_label') and self._name_label:
            self._name_label.setStyleSheet(f"color: {name_color};")
        if hasattr(self, '_time_label') and self._time_label:
            self._time_label.setStyleSheet(f"color: {time_color};")

    def _show_context_menu(self, position):
        menu = QMenu(self)
        menu.setObjectName("AssetCardMenu")

        open_folder_action = QAction("📂 打开工程所在路径", self)
        open_folder_action.triggered.connect(self._open_folder)
        menu.addAction(open_folder_action)

        # 编辑工程
        edit_action = QAction("✏️ 编辑工程", self)
        edit_action.triggered.connect(self._show_edit_dialog)
        menu.addAction(edit_action)

        menu.addSeparator()

        delete_action = QAction("🗑️ 删除工程", self)
        delete_action.triggered.connect(self._confirm_delete)
        menu.addAction(delete_action)

        # 鼠标离开菜单自动关闭
        self._menu_filter = _MenuAutoClose(menu, self)

        menu.exec(self.mapToGlobal(position))

    def _show_edit_dialog(self):
        """显示编辑工程对话框"""
        from .edit_project_dialog import EditProjectDialog
        dialog = EditProjectDialog(
            project_name=self.name,
            project_path=self.path,
            project_version=self.version,
            current_category=self.current_category,
            categories=self.categories,
            parent=self
        )
        if dialog.exec() == EditProjectDialog.DialogCode.Accepted:
            info = dialog.get_project_info()
            # 发送更新信号
            self.edit_requested.emit(self.path, info["path"], info["name"], info["category"])

    def _open_folder(self):
        import subprocess, sys
        try:
            if sys.platform == "win32":
                subprocess.Popen(["explorer", self.path])
            elif sys.platform == "darwin":
                subprocess.Popen(["open", self.path])
            else:
                subprocess.Popen(["xdg-open", self.path])
        except Exception as e:
            logger.error(f"打开路径失败: {e}")

    def _confirm_delete(self):
        from modules.asset_manager.ui.confirm_dialog import ConfirmDialog
        dialog = ConfirmDialog(
            "确认删除",
            f"确定要删除工程 \"{self.name}\" 吗？",
            f"路径: {self.path}\n\n此操作将直接删除整个工程文件夹，不可恢复！",
            self
        )
        if hasattr(dialog, 'center_on_parent'):
            dialog.center_on_parent()
        if dialog.exec() == ConfirmDialog.DialogCode.Accepted:
            self.delete_requested.emit(self.path)

    def enterEvent(self, event):
        self._is_hovered = True
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self._is_hovered = False
        self.update()
        super().leaveEvent(event)

    def paintEvent(self, a0):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        rect = self.rect()

        gradient = QLinearGradient(0, 0, rect.width(), rect.height())
        if self._is_hovered:
            if self.theme == "light":
                gradient.setColorAt(0, QColor("#ffffff"))
                gradient.setColorAt(1, QColor("#fafafa"))
            else:
                gradient.setColorAt(0, QColor("#424242"))
                gradient.setColorAt(1, QColor("#323232"))
        else:
            if self.theme == "light":
                gradient.setColorAt(0, QColor("#ffffff"))
                gradient.setColorAt(1, QColor("#fdfdfd"))
            else:
                gradient.setColorAt(0, QColor("#383838"))
                gradient.setColorAt(1, QColor("#282828"))

        path = QPainterPath()
        path.addRoundedRect(QRectF(rect), 0, 0)
        painter.fillPath(path, gradient)

        from PyQt6.QtGui import QPen
        if self._is_hovered:
            pen = QPen(QColor(255, 255, 255, 153) if self.theme != "light" else QColor(0, 0, 0, 102))
        else:
            pen = QPen(QColor("#454545") if self.theme != "light" else QColor("#e8e8e8"))
        pen.setWidth(2)
        painter.setPen(pen)
        painter.drawRoundedRect(QRectF(rect).adjusted(1, 1, -1, -1), 0, 0)
        painter.end()


class ProjectScanner(QThread):
    """工程扫描器 - 支持全量和增量两种模式"""

    found = pyqtSignal(list)
    progress = pyqtSignal(str)

    SCAN_PATHS = [
        Path.home() / "Documents",
        Path.home() / "Desktop",
        Path.home() / "Downloads",
        Path("D:/"), Path("E:/"), Path("F:/"), Path("G:/"),
    ]

    SKIP_DIRS = {
        'system volume information', 'windows', 'program files',
        'program files (x86)', 'programdata', '$recycle.bin',
        'recovery', 'msocache', 'boot', 'perflogs',
        'appdata', 'node_modules', '.git', '__pycache__',
        'venv', '.venv', 'env', '.env',
        'preview', 'samples', 'templates', 'engine',
        'marketplace', 'plugins'
    }

    def __init__(self, known_paths=None, excluded_paths=None):
        """
        Args:
            known_paths: 已知工程路径集合。为 None 时全量扫描，非空时增量扫描（跳过已知）。
            excluded_paths: 需要排除的路径列表（预览工程、资产库等），扫描时会过滤掉这些路径。
        """
        super().__init__()
        self.known_paths = known_paths or set()
        self.excluded_paths = set(excluded_paths or [])
        self.projs = []

    def run(self):
        self.projs = []
        scanned = set()
        mode = "增量" if self.known_paths else "全量"

        for p in self.SCAN_PATHS:
            if not p.exists():
                continue
            try:
                resolved = p.resolve()
                if resolved in scanned:
                    continue
                scanned.add(resolved)
            except Exception:
                pass

            self.progress.emit(f"{mode}扫描: {p}")
            self._scan(p, maxd=4)

        self.progress.emit(f"{mode}扫描完成，找到 {len(self.projs)} 个{'新' if self.known_paths else ''}工程")
        self.found.emit(self.projs)

    def _scan(self, d, depth=0, maxd=4):
        if depth >= maxd:
            return
        try:
            for item in d.iterdir():
                if not item.is_dir():
                    continue
                if item.name.startswith('.') or item.name.startswith('$'):
                    continue
                if item.name.lower() in self.SKIP_DIRS:
                    continue

                # 过滤排除路径（预览工程、资产库等，包括子目录）- 优先检查
                if self.excluded_paths:
                    try:
                        item_resolved = item.resolve()
                        is_excluded = False
                        for excluded_path in self.excluded_paths:
                            try:
                                excluded_resolved = Path(excluded_path).resolve()
                                # 检查 item 是否是排除路径本身，或者排除路径是否是 item 的父目录/祖先目录
                                # 使用 is_relative_to (Python 3.9+) 或者检查 parents
                                try:
                                    # Python 3.9+ 方法
                                    if item_resolved.is_relative_to(excluded_resolved):
                                        is_excluded = True
                                        logger.debug(f"跳过排除路径: {item}")
                                        break
                                except AttributeError:
                                    # Python 3.8 兼容方法
                                    if item_resolved == excluded_resolved or excluded_resolved in item_resolved.parents:
                                        is_excluded = True
                                        logger.debug(f"跳过排除路径: {item}")
                                        break
                            except Exception as e:
                                logger.debug(f"排除路径检查失败: {excluded_path}, 错误: {e}")
                                continue
                        if is_excluded:
                            continue
                    except PermissionError:
                        # 系统目录访问被拒绝是正常的，跳过即可
                        logger.debug(f"无权限访问路径: {item}")
                        continue
                    except Exception as e:
                        logger.debug(f"解析路径失败: {item}, 错误: {e}")
                        pass

                # 增量模式：跳过已知工程
                item_str = str(item)
                if item_str in self.known_paths:
                    continue

                # 增量模式：有 .UeToolkitconfig 标记的也跳过
                if self.known_paths and (item / TOOLKIT_CONFIG_DIR).exists():
                    continue

                ups = list(item.glob("*.uproject"))
                if ups:
                    up = ups[0]
                    ver = self._get_version(up)
                    mt = self._get_last_used_time(item, up)
                    thumb = self._get_thumbnail(item)

                    self.projs.append({
                        'name': item.name,
                        'path': item_str,
                        'version': ver,
                        'modified': mt.strftime("%Y-%m-%d"),
                        'thumbnail': thumb
                    })
                    self.progress.emit(f"找到: {item.name}")
                else:
                    self._scan(item, depth + 1, maxd)
        except Exception:
            pass

    @staticmethod
    def _get_version(f):
        try:
            with open(f, 'r', encoding='utf-8') as fp:
                d = json.load(fp)
                v = d.get('EngineAssociation', '')
                if v:
                    parts = v.split('.')
                    if len(parts) >= 2:
                        return f"{parts[0]}.{parts[1]}"
                return "Unknown"
        except Exception:
            return "Unknown"

    @staticmethod
    def _get_last_used_time(proj_dir, uproject_file):
        """获取项目最后使用时间
        
        优先级：Saved/Logs 下最新日志 > AutoScreenshot > .uproject 修改时间
        """
        try:
            saved_dir = proj_dir / "Saved"
            if saved_dir.exists():
                # 1. 检查日志文件（每次打开项目都会更新）
                logs_dir = saved_dir / "Logs"
                if logs_dir.exists():
                    logs = list(logs_dir.glob("*.log"))
                    if logs:
                        newest = max(logs, key=lambda p: p.stat().st_mtime)
                        return datetime.fromtimestamp(newest.stat().st_mtime)

                # 2. 检查 AutoScreenshot（每次退出项目都会更新）
                screenshot = saved_dir / "AutoScreenshot.png"
                if screenshot.exists():
                    return datetime.fromtimestamp(screenshot.stat().st_mtime)
        except Exception:
            pass

        # 3. 兜底：.uproject 文件修改时间
        try:
            return datetime.fromtimestamp(uproject_file.stat().st_mtime)
        except Exception:
            return datetime.now()

    @staticmethod
    def _get_thumbnail(proj_dir):
        try:
            saved_dir = proj_dir / "Saved"
            if not saved_dir.exists():
                return None
            imgs = list(saved_dir.glob("*.png")) + list(saved_dir.glob("*.jpg"))
            if imgs:
                return str(max(imgs, key=lambda p: p.stat().st_mtime))
        except Exception:
            pass
        return None


class MyProjectsUI(BaseModuleWidget):
    """我的工程 UI

    启动流程：
    1. 有注册表 → 立即显示 → 后台增量扫描新工程
    2. 无注册表 → 全量扫描 → 保存注册表
    """

    def __init__(self, theme="dark", parent=None):
        super().__init__(parent)
        self.theme = theme
        self.all_projects = []
        self.filtered_projects = []
        self.cards = []
        self.scanner = None
        self._assets_loaded = False
        self.registry = ProjectRegistry()
        self._thumb_watcher = None  # 缩略图文件监听器
        self._watched_dirs = {}     # {dir_path: card} 映射

        self._init_ui()

    def showEvent(self, event):
        """首次显示时加载工程"""
        super().showEvent(event)
        if not self._assets_loaded and self.scanner is None:
            QTimer.singleShot(10, self._load_projects)
        
        # 检查排除路径是否变更
        QTimer.singleShot(50, self._check_excluded_paths_changed)

    def _get_excluded_paths(self):
        """获取需要排除的路径列表（预览工程 + 资产库等）"""
        excluded_paths = set()
        
        try:
            from core.services import config_service
            
            # 1. 获取预览工程路径
            asset_config = config_service.get_module_config("asset_manager") or {}
            
            preview_projects = asset_config.get("preview_projects", [])
            for proj in preview_projects:
                path = proj.get("path", "")
                if path:
                    try:
                        excluded_paths.add(str(Path(path).resolve()))
                        logger.debug(f"排除预览工程: {path}")
                    except Exception as e:
                        excluded_paths.add(path)
                        logger.warning(f"预览工程路径解析失败: {e}")
            
            # 2. 获取资产库路径（从 asset_libraries 数组读取）
            asset_libraries = asset_config.get("asset_libraries", [])
            for lib in asset_libraries:
                lib_path = lib.get("path", "")
                if lib_path:
                    try:
                        resolved_path = str(Path(lib_path).resolve())
                        excluded_paths.add(resolved_path)
                        logger.debug(f"排除资产库: {lib_path}")
                    except Exception as e:
                        excluded_paths.add(lib_path)
                        logger.warning(f"资产库路径解析失败: {e}")
            
            # 3. 获取当前资产库路径（兼容旧配置）
            current_library = asset_config.get("current_asset_library", "")
            if current_library:
                try:
                    excluded_paths.add(str(Path(current_library).resolve()))
                    logger.debug(f"排除当前资产库: {current_library}")
                except Exception as e:
                    excluded_paths.add(current_library)
                    logger.warning(f"当前资产库路径解析失败: {e}")
            
            logger.info(f"我的工程排除路径列表: {excluded_paths}")
            
        except Exception as e:
            logger.error(f"获取排除路径失败: {e}", exc_info=True)
        
        return excluded_paths

    def clear_cache_and_rescan(self):
        """清理缓存并重新扫描（用于路径变更后强制刷新）"""
        try:
            logger.info("清理我的工程缓存并重新扫描...")
            
            # 清理注册表缓存
            self.registry.clear_registry()
            
            # 清空当前数据
            self.all_projects = []
            self._clear_cards()
            
            # 重新加载（会触发全量扫描）
            self._load_projects()
            
        except Exception as e:
            logger.error(f"清理缓存并重新扫描失败: {e}")
    
    def _filter_excluded_projects(self, projects):
        """从工程列表中过滤掉被排除的工程"""
        excluded_paths = self._get_excluded_paths()
        if not excluded_paths:
            return projects
        
        filtered = []
        for proj in projects:
            proj_path = proj.get("path", "")
            if not proj_path:
                continue
            
            try:
                proj_resolved = Path(proj_path).resolve()
                is_excluded = False
                
                for excluded_path in excluded_paths:
                    try:
                        excluded_resolved = Path(excluded_path).resolve()
                        # 检查工程是否在排除路径下
                        try:
                            # Python 3.9+ 方法
                            if proj_resolved.is_relative_to(excluded_resolved):
                                is_excluded = True
                                logger.info(f"过滤掉被排除的工程: {proj_path}")
                                break
                        except AttributeError:
                            # Python 3.8 兼容方法
                            if proj_resolved == excluded_resolved or excluded_resolved in proj_resolved.parents:
                                is_excluded = True
                                logger.info(f"过滤掉被排除的工程: {proj_path}")
                                break
                    except Exception:
                        continue
                
                if not is_excluded:
                    filtered.append(proj)
            except Exception:
                # 解析失败的工程保留
                filtered.append(proj)
        
        return filtered

    def _check_excluded_paths_changed(self):
        """检查排除路径是否发生变化，如果变化则重新扫描"""
        try:
            current_excluded = self._get_excluded_paths()
            
            # 如果是首次检查，保存当前路径
            if not hasattr(self, '_last_excluded_paths'):
                self._last_excluded_paths = current_excluded
                return
            
            # 检查是否有变化
            if current_excluded != self._last_excluded_paths:
                logger.info("检测到排除路径变更，重新扫描我的工程...")
                self._last_excluded_paths = current_excluded
                self.clear_cache_and_rescan()
                
        except Exception as e:
            logger.warning(f"检查排除路径变更失败: {e}")

    def _setup_thumb_watcher(self):
        """为当前显示的卡片设置缩略图目录监听"""
        # 清理旧 watcher
        if self._thumb_watcher:
            try:
                dirs = self._thumb_watcher.directories()
                if dirs:
                    self._thumb_watcher.removePaths(dirs)
            except Exception:
                pass
            self._thumb_watcher.deleteLater()
            self._thumb_watcher = None
        self._watched_dirs.clear()

        if not self.cards:
            return

        self._thumb_watcher = QFileSystemWatcher(self)
        self._thumb_watcher.directoryChanged.connect(self._on_thumb_dir_changed)

        dirs_to_watch = []
        for card in self.cards:
            saved_dir = Path(card.path) / "Saved"
            # 确保目录存在且可访问
            if not saved_dir.exists():
                try:
                    saved_dir.mkdir(parents=True, exist_ok=True)
                    logger.debug(f"创建 Saved 目录: {saved_dir}")
                except Exception as e:
                    logger.warning(f"无法创建 Saved 目录 {saved_dir}: {e}")
                    continue
            
            dir_str = str(saved_dir)
            self._watched_dirs[dir_str] = card
            dirs_to_watch.append(dir_str)

        if dirs_to_watch:
            try:
                # 批量添加监听路径，捕获可能的权限错误
                failed_paths = self._thumb_watcher.addPaths(dirs_to_watch)
                if failed_paths:
                    logger.warning(f"以下目录监听失败（可能权限不足）: {failed_paths}")
                    # 从监听列表中移除失败的路径
                    for failed in failed_paths:
                        self._watched_dirs.pop(failed, None)
                
                success_count = len(dirs_to_watch) - len(failed_paths)
                if success_count > 0:
                    logger.debug(f"缩略图监听: {success_count}/{len(dirs_to_watch)} 个目录")
            except Exception as e:
                logger.warning(f"添加文件监听失败: {e}")
                self._watched_dirs.clear()

    def _on_thumb_dir_changed(self, dir_path: str):
        """某个项目的 Saved/ 目录发生变化，更新对应卡片缩略图和时间"""
        try:
            card = self._watched_dirs.get(dir_path)
            if not card:
                return
            
            proj_path = Path(card.path)
            
            # 延迟 500ms 更新，确保文件写入完成
            QTimer.singleShot(500, lambda: self._update_project_thumbnail_and_time(card.path))
        except Exception as e:
            logger.warning(f"处理缩略图变化失败: {e}")
    
    def _update_project_thumbnail_and_time(self, project_path: str):
        """更新项目的缩略图和最后使用时间"""
        try:
            pp = Path(project_path)
            ufs = list(pp.glob("*.uproject"))
            if not ufs:
                return
            
            # 重新获取缩略图和时间
            new_thumb = ProjectScanner._get_thumbnail(pp)
            new_time = ProjectScanner._get_last_used_time(pp, ufs[0])
            new_modified = new_time.strftime("%Y-%m-%d")
            
            # 更新注册表
            data = self.registry.load_registry()
            for proj in data.get("projects", []):
                if proj["path"] == project_path:
                    proj["modified"] = new_modified
                    if new_thumb:
                        proj["thumbnail"] = new_thumb
                    break
            self.registry.save_registry(data)
            
            # 更新内存数据
            for proj in self.all_projects:
                if proj["path"] == project_path:
                    proj["modified"] = new_modified
                    if new_thumb:
                        proj["thumbnail"] = new_thumb
                    break
            
            # 更新对应卡片的缩略图
            for card in self.cards:
                if card.path == project_path:
                    if new_thumb:
                        card.update_thumbnail(new_thumb)
                    logger.info(f"项目缩略图已更新: {project_path}")
                    break
        except Exception as e:
            logger.warning(f"更新项目缩略图和时间失败: {e}")

    def _load_projects(self):
        """加载工程：有注册表则秒加载 + 增量扫描，否则全量扫描"""
        if self.registry.has_registry():
            # 从注册表加载（瞬间）
            projects = self.registry.get_projects()
            # 过滤掉已不存在的工程和排除路径
            valid = self._filter_excluded_projects(projects)
            # 再过滤掉不存在的工程
            valid = [p for p in valid if Path(p["path"]).exists()]
            
            if len(valid) != len(projects):
                logger.info(f"清理 {len(projects) - len(valid)} 个已不存在或排除的工程")
                # 更新注册表，移除无效工程
                self.registry.save_full_scan_result(valid)

            self.all_projects = valid
            self._load_categories()
            self._update_version_filter()
            self._apply_filter()
            self._assets_loaded = True

            # 后台增量扫描新工程
            self.status_label.setText(f"已加载 {len(valid)} 个项目，正在检查新项目...")
            known = {p["path"] for p in valid}
            self._start_scan(known_paths=known)
        else:
            # 首次运行，全量扫描
            self.status_label.setText("首次运行，正在扫描项目...")
            self._start_scan(known_paths=None)

    def _start_scan(self, known_paths, excluded_paths=None):
        """启动扫描线程"""
        # 获取需要排除的路径
        if excluded_paths is None:
            excluded_paths = self._get_excluded_paths()
        
        scanner = ProjectScanner(known_paths=known_paths, excluded_paths=excluded_paths)
        if known_paths:
            scanner.found.connect(self._on_incremental_scan_done)
        else:
            scanner.found.connect(self._on_full_scan_done)
        scanner.progress.connect(self._on_scan_progress)
        scanner.start()
        self.scanner = scanner

    def _on_full_scan_done(self, projects):
        """全量扫描完成"""
        self.all_projects = projects
        self.registry.save_full_scan_result(projects)
        self._load_categories()
        self._update_version_filter()
        self._apply_filter()
        self._assets_loaded = True

    def _on_incremental_scan_done(self, new_projects):
        """增量扫描完成"""
        if new_projects:
            self.registry.add_projects(new_projects)
            self.all_projects.extend(new_projects)
            self._load_categories()
            self._update_version_filter()
            self._apply_filter()
            logger.info(f"增量扫描发现 {len(new_projects)} 个新工程")
        else:
            # 没有新项目，更新状态栏
            self.status_label.setText(f"当前共有 {len(self.filtered_projects)} 个项目")

    def _on_scan_progress(self, msg):
        self.status_label.setText(msg)

    def _init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # 筛选区域
        filter_area = QWidget()
        filter_area.setObjectName("AssetFilterArea")
        filter_area.setMinimumHeight(60)
        filter_layout = QHBoxLayout(filter_area)
        filter_layout.setContentsMargins(20, 10, 20, 20)
        filter_layout.setSpacing(15)

        # 分类标签 + 选择框
        category_container = QWidget()
        category_layout = QHBoxLayout(category_container)
        category_layout.setContentsMargins(0, 0, 0, 0)
        category_layout.setSpacing(3)
        
        category_label = QLabel("分类：")
        category_label.setObjectName("AssetFilterLabel")
        category_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        category_layout.addWidget(category_label)
        
        self.category_filter = QComboBox()
        self.category_filter.setObjectName("AssetCategoryFilter")
        self.category_filter.setFixedHeight(36)
        self.category_filter.setMinimumWidth(120)
        self.category_filter.setMaximumWidth(180)
        self.category_filter.setFocusPolicy(Qt.FocusPolicy.ClickFocus)
        self.category_filter.setCursor(Qt.CursorShape.PointingHandCursor)
        self.category_filter.addItem("全部分类")
        self.category_filter.currentTextChanged.connect(self._on_category_changed)
        category_layout.addWidget(self.category_filter)
        
        filter_layout.addWidget(category_container)

        # 版本标签 + 选择框
        version_container = QWidget()
        version_layout = QHBoxLayout(version_container)
        version_layout.setContentsMargins(0, 0, 0, 0)
        version_layout.setSpacing(3)
        
        version_label = QLabel("版本：")
        version_label.setObjectName("AssetFilterLabel")
        version_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        version_layout.addWidget(version_label)
        
        self.version_filter = QComboBox()
        self.version_filter.setObjectName("AssetCategoryFilter")
        self.version_filter.setFixedHeight(36)
        self.version_filter.setMinimumWidth(120)
        self.version_filter.setMaximumWidth(180)
        self.version_filter.setFocusPolicy(Qt.FocusPolicy.ClickFocus)
        self.version_filter.setCursor(Qt.CursorShape.PointingHandCursor)
        self.version_filter.addItem("所有版本")
        self.version_filter.currentTextChanged.connect(self._on_filter_changed)
        version_layout.addWidget(self.version_filter)
        
        filter_layout.addWidget(version_container)

        # 排序标签 + 选择框
        sort_container = QWidget()
        sort_layout = QHBoxLayout(sort_container)
        sort_layout.setContentsMargins(0, 0, 0, 0)
        sort_layout.setSpacing(3)
        
        sort_label = QLabel("排序：")
        sort_label.setObjectName("AssetFilterLabel")
        sort_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        sort_layout.addWidget(sort_label)
        
        self.sort_combo = QComboBox()
        self.sort_combo.setObjectName("AssetSortCombo")
        self.sort_combo.setFixedHeight(36)
        self.sort_combo.setMinimumWidth(120)
        self.sort_combo.setMaximumWidth(180)
        self.sort_combo.setFocusPolicy(Qt.FocusPolicy.ClickFocus)
        self.sort_combo.setCursor(Qt.CursorShape.PointingHandCursor)
        self.sort_combo.addItems(["最近修改", "工程名称", "引擎版本"])
        self.sort_combo.currentTextChanged.connect(self._on_sort_changed)
        sort_layout.addWidget(self.sort_combo)
        
        filter_layout.addWidget(sort_container)

        # 添加弹性空间
        filter_layout.addStretch()
        
        # 搜索框
        self.search_input = QLineEdit()
        self.search_input.setObjectName("AssetSearchInput")
        self.search_input.setPlaceholderText("搜索工程...")
        self.search_input.setFixedHeight(36)
        self.search_input.setMaximumWidth(200)
        self.search_input.setFocusPolicy(Qt.FocusPolicy.ClickFocus)
        self.search_input.textChanged.connect(self._on_filter_changed)
        filter_layout.addWidget(self.search_input)

        # 刷新按钮
        self.refresh_btn = QPushButton("🔄 刷新")
        self.refresh_btn.setObjectName("BrowseButton")
        self.refresh_btn.setFixedHeight(36)
        self.refresh_btn.setFixedWidth(100)
        self.refresh_btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.refresh_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.refresh_btn.clicked.connect(lambda: self.clear_cache_and_rescan())
        filter_layout.addWidget(self.refresh_btn)

        # 创建工程按钮（点击弹出引擎版本下拉）
        self.add_project_btn = QPushButton("+ 创建工程")
        self.add_project_btn.setObjectName("AddAssetButton")
        self.add_project_btn.setFixedHeight(36)
        self.add_project_btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.add_project_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.add_project_btn.clicked.connect(self._on_create_project_clicked)
        filter_layout.addWidget(self.add_project_btn)

        main_layout.addWidget(filter_area)

        # 滚动区域
        scroll_area = QScrollArea()
        scroll_area.setObjectName("AssetScrollArea")
        scroll_area.setWidgetResizable(True)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        try:
            from core.utils.auto_hide_scrollbar import enable_auto_hide_scrollbar
            enable_auto_hide_scrollbar(scroll_area)
        except Exception:
            pass

        scroll_content = QWidget()
        scroll_content.setObjectName("AssetScrollContent")
        scroll_layout = QVBoxLayout(scroll_content)
        scroll_layout.setContentsMargins(0, 0, 0, 0)
        scroll_layout.setSpacing(20)

        self.status_label = QLabel("正在加载项目...")
        self.status_label.setObjectName("MyProjectStatusLabel")
        if self.theme == "light":
            self.status_label.setStyleSheet("color: rgba(0, 0, 0, 0.5); font-size: 13px;")
        else:
            self.status_label.setStyleSheet("color: rgba(255, 255, 255, 0.6); font-size: 13px;")
        self.status_label.setContentsMargins(20, 5, 20, 5)
        scroll_layout.addWidget(self.status_label)

        self.grid_widget = QWidget()
        self.grid_widget.setObjectName("AssetGridWidget")
        self.grid_layout = QGridLayout(self.grid_widget)
        self.grid_layout.setContentsMargins(0, 0, 0, 0)
        self.grid_layout.setSpacing(20)
        self.grid_layout.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)

        scroll_layout.addWidget(self.grid_widget)
        scroll_layout.addStretch()

        scroll_area.setWidget(scroll_content)
        main_layout.addWidget(scroll_area)
        self.scroll_area = scroll_area

    def _update_version_filter(self):
        versions = sorted(set(p.get('version', '') for p in self.all_projects if p.get('version')), reverse=True)
        current = self.version_filter.currentText()
        self.version_filter.blockSignals(True)
        self.version_filter.clear()
        self.version_filter.addItem("所有版本")
        for v in versions:
            self.version_filter.addItem(v)
        
        # 优先恢复已保存的版本筛选
        saved_version = self._load_ui_state("selected_version", "")
        restore_target = saved_version if saved_version else current
        idx = self.version_filter.findText(restore_target)
        self.version_filter.setCurrentIndex(idx if idx >= 0 else 0)
        self.version_filter.blockSignals(False)

    def _load_categories(self):
        """加载分类列表到下拉框"""
        data = self.registry.load_registry()
        categories = data.get("categories", ["默认"])

        current = self.category_filter.currentText()
        self.category_filter.blockSignals(True)
        self.category_filter.clear()
        self.category_filter.addItem("全部分类")
        for cat in categories:
            self.category_filter.addItem(cat)
        self.category_filter.addItem("+ 分类管理")

        # 优先恢复已保存的分类
        saved_category = self._load_ui_state("selected_category", "")
        restore_target = saved_category if saved_category else current
        if restore_target and restore_target != "+ 分类管理":
            idx = self.category_filter.findText(restore_target)
            if idx >= 0:
                self.category_filter.setCurrentIndex(idx)
        self.category_filter.blockSignals(False)

        # 恢复已保存的排序方式
        saved_sort = self._load_ui_state("sort_method", "")
        if saved_sort:
            sort_idx = self.sort_combo.findText(saved_sort)
            if sort_idx >= 0:
                self.sort_combo.blockSignals(True)
                self.sort_combo.setCurrentIndex(sort_idx)
                self.sort_combo.blockSignals(False)

    @staticmethod
    def _load_ui_state(key: str, default=None):
        """从 app_config.ui_states.my_projects 读取指定字段"""
        try:
            from core.services import config_service
            app_config = config_service.get_module_config("app") or {}
            return app_config.get("ui_states", {}).get("my_projects", {}).get(key, default)
        except Exception:
            return default

    @staticmethod
    def _save_ui_state(key: str, value) -> None:
        """保存指定字段到 app_config.ui_states.my_projects"""
        try:
            from core.services import config_service
            app_config = config_service.get_module_config("app") or {}
            ui_states = app_config.setdefault("ui_states", {})
            mp_state = ui_states.setdefault("my_projects", {})
            mp_state[key] = value
            config_service.save_module_config("app", app_config)
        except Exception:
            pass

    def _on_category_changed(self, category: str):
        """分类选择改变"""
        if category == "+ 分类管理":
            self._show_category_dialog()
            self.category_filter.setCurrentIndex(0)
            return
        self._save_ui_state("selected_category", category)
        self._apply_filter()

    def _show_category_dialog(self):
        """显示分类管理对话框"""
        from .category_dialog import ProjectCategoryDialog
        dialog = ProjectCategoryDialog(self.registry, self)
        dialog.categories_updated.connect(self._on_categories_updated)
        dialog.exec()

    def _on_categories_updated(self):
        """分类更新后刷新"""
        self._load_categories()
        self._apply_filter()

    def _on_filter_changed(self, *args):
        # 保存版本筛选状态
        self._save_ui_state("selected_version", self.version_filter.currentText())
        self._apply_filter()

    def _on_sort_changed(self, *args):
        self._save_ui_state("sort_method", self.sort_combo.currentText())
        self._apply_filter()

    def _apply_filter(self):
        search = self.search_input.text().lower()
        version = self.version_filter.currentText()
        category = self.category_filter.currentText()
        sort_by = self.sort_combo.currentText()

        filtered = []
        for p in self.all_projects:
            if search and search not in p['name'].lower() and search not in p['path'].lower():
                continue
            if version != "所有版本" and p.get('version', '') not in version:
                continue
            if category not in ("全部分类", "+ 分类管理") and p.get('category', '默认') != category:
                continue
            filtered.append(p)

        if sort_by == "工程名称":
            filtered.sort(key=lambda x: x['name'].lower())
        elif sort_by == "引擎版本":
            filtered.sort(key=lambda x: x.get('version', ''), reverse=True)
        else:
            # 按最后使用时间排序（实时获取）
            def _get_sort_time(p):
                pp = Path(p['path'])
                ups = list(pp.glob("*.uproject"))
                t = ProjectScanner._get_last_used_time(pp, ups[0] if ups else None)
                return t if t else datetime.min
            filtered.sort(key=_get_sort_time, reverse=True)

        self.filtered_projects = filtered
        self._refresh_cards()

    def _refresh_cards(self):
        self._clear_cards()

        if not self.filtered_projects:
            self.status_label.setText("没有找到匹配的项目")
            return

        # 获取分类列表
        data = self.registry.load_registry()
        categories = data.get("categories", ["默认"])

        for i, proj in enumerate(self.filtered_projects):
            # 实时获取最新缩略图和最后使用时间
            proj_path = Path(proj['path'])
            thumb = ProjectScanner._get_thumbnail(proj_path)
            uproject_files = list(proj_path.glob("*.uproject"))
            uproject = uproject_files[0] if uproject_files else None
            last_used = ProjectScanner._get_last_used_time(proj_path, uproject)
            modified_str = last_used.strftime("%Y-%m-%d %H:%M") if last_used else proj.get('modified', '')

            card = ProjectCard(
                proj['name'], proj['path'],
                proj.get('version', 'Unknown'),
                modified_str,
                self.theme,
                thumb_path=thumb,
                categories=categories,
                current_category=proj.get('category', '默认')
            )
            card.open_requested.connect(self._open_project)
            card.delete_requested.connect(self._delete_project)
            card.category_changed.connect(self._on_project_category_changed)
            card.edit_requested.connect(self._on_project_edited)

            row = i // 5
            col = i % 5
            self.grid_layout.addWidget(card, row, col)
            self.cards.append(card)

        self.status_label.setText(f"当前共有 {len(self.filtered_projects)} 个项目")

        # 设置缩略图文件监听
        self._setup_thumb_watcher()

    def _clear_cards(self):
        # 先清理 watcher（卡片即将销毁，引用会失效）
        if self._thumb_watcher:
            try:
                dirs = self._thumb_watcher.directories()
                if dirs:
                    self._thumb_watcher.removePaths(dirs)
            except Exception:
                pass
        self._watched_dirs.clear()

        for c in self.cards:
            c.setParent(None)
            c.deleteLater()
        self.cards.clear()

    def _open_project(self, project_path):
        import subprocess, sys
        pp = Path(project_path)
        ufs = list(pp.glob("*.uproject"))
        if ufs:
            try:
                if sys.platform == "win32":
                    import os
                    os.startfile(str(ufs[0]))
                else:
                    subprocess.Popen([str(ufs[0])], shell=False)
                logger.info(f"打开工程: {pp}")
                
                # 为该项目的 Saved 目录设置实时监听
                self._watch_project_saved_dir(project_path)
            except Exception as e:
                logger.error(f"打开工程失败: {e}")

    def _watch_project_saved_dir(self, project_path: str):
        """为打开的项目设置 Saved 目录监听，实时更新缩略图"""
        try:
            saved_dir = Path(project_path) / "Saved"
            if not saved_dir.exists():
                # 如果 Saved 目录不存在，创建它并监听（虚幻引擎会在这里生成文件）
                try:
                    saved_dir.mkdir(parents=True, exist_ok=True)
                    logger.debug(f"创建 Saved 目录: {saved_dir}")
                except Exception as e:
                    logger.warning(f"无法创建 Saved 目录 {saved_dir}: {e}")
                    return
            
            dir_str = str(saved_dir)
            
            # 如果还没有全局监听器，创建一个
            if not self._thumb_watcher:
                self._thumb_watcher = QFileSystemWatcher(self)
                self._thumb_watcher.directoryChanged.connect(self._on_thumb_dir_changed)
            
            # 找到对应的卡片
            card = None
            for c in self.cards:
                if c.path == project_path:
                    card = c
                    break
            
            if card:
                # 添加到监听列表
                if dir_str not in self._watched_dirs:
                    self._watched_dirs[dir_str] = card
                    try:
                        success = self._thumb_watcher.addPath(dir_str)
                        if success:
                            logger.info(f"开始监听项目缩略图: {project_path}")
                        else:
                            logger.warning(f"监听项目缩略图失败（可能权限不足）: {project_path}")
                    except Exception as e:
                        logger.warning(f"添加缩略图监听失败: {e}")
        except Exception as e:
            logger.warning(f"设置项目监听失败: {e}")

    def _on_create_project_clicked(self):
        """点击创建工程 → 后台扫描引擎 → 弹出版本下拉"""
        self.add_project_btn.setEnabled(False)
        self.add_project_btn.setText("扫描引擎中...")

        from modules.my_projects.logic.engine_scanner import EngineScanner
        from PyQt6.QtCore import QThread, pyqtSignal

        class _ScanThread(QThread):
            finished = pyqtSignal(list)
            def run(self):
                self.finished.emit(EngineScanner.scan_installed_engines())

        self._engine_scan_thread = _ScanThread()
        self._engine_scan_thread.finished.connect(self._on_engines_scanned)
        self._engine_scan_thread.start()

    def _on_engines_scanned(self, engines):
        """引擎扫描完成 → 在按钮下方弹出版本下拉菜单"""
        self.add_project_btn.setEnabled(True)
        self.add_project_btn.setText("+ 创建工程")

        if not engines:
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.warning(self, "未找到引擎", "未检测到已安装的虚幻引擎。\n请确认已通过 Epic Games Launcher 安装。")
            return

        # 缓存引擎列表
        self._cached_engines = engines

        # 弹出版本选择下拉菜单
        menu = QMenu(self)
        menu.setObjectName("AssetCardMenu")
        for engine in engines:
            action = QAction(f"UE {engine.version}", self)
            action.triggered.connect(lambda checked, e=engine: self._on_engine_selected(e))
            menu.addAction(action)

        # 在按钮下方弹出
        btn_pos = self.add_project_btn.mapToGlobal(
            QPoint(0, self.add_project_btn.height())
        )
        menu.exec(btn_pos)

    def _on_engine_selected(self, engine):
        """选择引擎版本后 → 启动 UE 项目浏览器

        策略：临时删除 AutoLoadProject.txt（UE5 用这个文件决定自动加载哪个项目），
        启动 UE 后再恢复。
        """
        import subprocess, os, threading, time
        try:
            editor = str(engine.editor_path)
            ver = engine.version  # e.g. "5.4"
            saved_dir = Path(os.environ["LOCALAPPDATA"]) / "UnrealEngine" / ver / "Saved"

            # 关键文件：AutoLoadProject.txt 存储了"上次打开的项目"路径
            auto_load_path = saved_dir / "AutoLoadProject.txt"
            auto_load_bak = saved_dir / "AutoLoadProject.txt._launcher_bak"

            auto_load_removed = False

            if auto_load_path.exists():
                try:
                    if auto_load_bak.exists():
                        auto_load_bak.unlink()
                    auto_load_path.rename(auto_load_bak)
                    auto_load_removed = True
                    logger.info(f"已临时移除 AutoLoadProject.txt")
                except Exception as e:
                    logger.warning(f"移除 AutoLoadProject.txt 失败: {e}")

            subprocess.Popen([editor], cwd=str(engine.install_dir))
            logger.info(f"已启动 UE {engine.version} 项目浏览器: {editor}")

            if auto_load_removed:
                def _restore():
                    # 等 UE 完全启动后再恢复
                    time.sleep(30)
                    try:
                        # UE 可能创建了新的 AutoLoadProject.txt，先删掉
                        if auto_load_path.exists():
                            auto_load_path.unlink()
                        if auto_load_bak.exists():
                            auto_load_bak.rename(auto_load_path)
                            logger.info("已恢复 AutoLoadProject.txt")
                    except Exception as e:
                        logger.warning(f"恢复 AutoLoadProject.txt 失败: {e}")
                t = threading.Thread(target=_restore, daemon=True)
                t.start()

        except Exception as e:
            logger.error(f"启动编辑器失败: {e}")
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.critical(self, "启动失败", f"无法启动 UE {engine.version} 编辑器:\n{e}")

    def _on_project_created(self, uproject_path: str):
        """工程创建完成"""
        pp = Path(uproject_path)
        proj_dir = pp.parent

        # 添加到注册表和列表
        import json
        from datetime import datetime
        try:
            with open(pp, "r", encoding="utf-8") as f:
                data = json.load(f)
            version = data.get("EngineAssociation", "Unknown")
        except Exception:
            version = "Unknown"

        new_proj = {
            "name": proj_dir.name,
            "path": str(proj_dir),
            "version": version,
            "modified": datetime.now().strftime("%Y-%m-%d"),
            "thumbnail": None,
            "category": "默认",
        }
        self.registry.add_projects([new_proj])
        self.all_projects.append(new_proj)
        self._load_categories()
        self._update_version_filter()
        self._apply_filter()
        
        # 刷新UI显示新工程
        self._refresh_cards()
        
        logger.info(f"新工程已添加: {proj_dir.name}")

    def _delete_project(self, project_path):
        import shutil
        pp = Path(project_path)
        try:
            shutil.rmtree(pp)
            logger.info(f"已删除工程: {pp}")
            self.registry.remove_project(project_path)
            self.all_projects = [p for p in self.all_projects if p['path'] != project_path]
            self._update_version_filter()
            self._apply_filter()
        except Exception as e:
            logger.error(f"删除工程失败: {e}")
            QMessageBox.critical(self, "删除失败", f"无法删除工程:\n{e}")

    def _on_project_category_changed(self, project_path: str, new_category: str):
        """工程分类变更"""
        # 更新注册表
        data = self.registry.load_registry()
        for proj in data.get("projects", []):
            if proj["path"] == project_path:
                proj["category"] = new_category
                break
        self.registry.save_registry(data)

        # 更新内存数据
        for proj in self.all_projects:
            if proj["path"] == project_path:
                proj["category"] = new_category
                break

        # 更新 .UeToolkitconfig
        from modules.my_projects.logic.project_registry import TOOLKIT_CONFIG_DIR, PROJECT_CONFIG_FILE
        config_file = Path(project_path) / TOOLKIT_CONFIG_DIR / PROJECT_CONFIG_FILE
        if config_file.exists():
            try:
                with open(config_file, "r", encoding="utf-8") as f:
                    cfg = json.load(f)
                cfg["category"] = new_category
                with open(config_file, "w", encoding="utf-8") as f:
                    json.dump(cfg, f, ensure_ascii=False, indent=2)
            except Exception as e:
                logger.warning(f"更新工程配置失败: {e}")

        self._apply_filter()
        logger.info(f"工程 {project_path} 分类改为: {new_category}")

    def _on_project_edited(self, old_path: str, new_path: str, new_name: str, new_category: str):
        """工程编辑完成"""
        # 重新查找缩略图（路径可能已变）
        new_thumb = ProjectScanner._get_thumbnail(Path(new_path))
        
        # 更新修改时间为当前时间（改名后应该排到最前面）
        from datetime import datetime
        new_modified = datetime.now().strftime("%Y-%m-%d")

        # 更新注册表
        data = self.registry.load_registry()
        for proj in data.get("projects", []):
            if proj["path"] == old_path:
                proj["path"] = new_path
                proj["name"] = new_name
                proj["category"] = new_category
                proj["thumbnail"] = new_thumb
                proj["modified"] = new_modified
                break
        self.registry.save_registry(data)

        # 更新内存数据
        for proj in self.all_projects:
            if proj["path"] == old_path:
                proj["path"] = new_path
                proj["name"] = new_name
                proj["category"] = new_category
                proj["thumbnail"] = new_thumb
                proj["modified"] = new_modified
                break

        # 更新 .UeToolkitconfig
        from modules.my_projects.logic.project_registry import TOOLKIT_CONFIG_DIR, PROJECT_CONFIG_FILE
        config_dir = Path(new_path) / TOOLKIT_CONFIG_DIR
        config_dir.mkdir(parents=True, exist_ok=True)
        config_file = config_dir / PROJECT_CONFIG_FILE
        try:
            cfg = {}
            if config_file.exists():
                with open(config_file, "r", encoding="utf-8") as f:
                    cfg = json.load(f)
            cfg["name"] = new_name
            cfg["category"] = new_category
            with open(config_file, "w", encoding="utf-8") as f:
                json.dump(cfg, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.warning(f"更新工程配置失败: {e}")

        # 更新对应卡片的缩略图
        for card in self.cards:
            if card.path == old_path:
                card.path = new_path
                card.name = new_name
                if new_thumb:
                    card.update_thumbnail(new_thumb)
                break

        self._update_version_filter()
        self._apply_filter()
        logger.info(f"工程已更新: {old_path} → {new_path}, 名称: {new_name}, 分类: {new_category}")

    def update_theme(self, theme: str):
        self.theme = theme
        # 更新状态标签颜色
        if theme == "light":
            self.status_label.setStyleSheet("color: rgba(0, 0, 0, 0.5); font-size: 13px;")
        else:
            self.status_label.setStyleSheet("color: rgba(255, 255, 255, 0.6); font-size: 13px;")
        for card in self.cards:
            card.set_theme(theme)

    def on_theme_changed(self, theme_name: str) -> None:
        super().on_theme_changed(theme_name)
        self.update_theme(theme_name)

    def load_assets_async(self, on_complete=None, force_reload=False):
        """兼容主窗口的异步加载接口"""
        if self._assets_loaded and not force_reload:
            if on_complete:
                on_complete()
            return
        if on_complete:
            QTimer.singleShot(100, on_complete)

    def cleanup(self):
        """清理资源"""
        if self.scanner and self.scanner.isRunning():
            if not self.scanner.wait(500):
                self.scanner.terminate()
                self.scanner.wait(1000)
        self._clear_cards()
